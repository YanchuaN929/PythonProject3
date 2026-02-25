"""Resolve 32-hex user IDs via USER and DEPARTMENT tables."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

HEX32_RE = re.compile(r"(?i)\b[0-9a-f]{32}\b")
ZH_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")


def normalize_hex32(value: Any) -> Optional[str]:
    """Normalize possible 32-hex token."""

    if value is None:
        return None
    text = str(value).strip().strip("\"'{}[]()")
    if not text:
        return None
    upper = text.upper()
    if re.fullmatch(r"[0-9A-F]{32}", upper):
        return upper
    return None


def extract_hex32_ids(value: Any, max_ids: int = 64) -> List[str]:
    """Extract unique 32-hex IDs from any value."""

    if value is None:
        return []
    text = str(value)
    if not text:
        return []

    seen = set()
    result: List[str] = []
    for token in HEX32_RE.findall(text):
        normalized = normalize_hex32(token)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
        if len(result) >= max_ids:
            break
    return result


def _is_pymssql_connection(conn: Any) -> bool:
    module_name = str(getattr(conn.__class__, "__module__", "")).lower()
    class_name = str(getattr(conn.__class__, "__name__", "")).lower()
    text = f"{module_name}.{class_name}"
    return ("pymssql" in text) or ("_mssql" in text)


def _execute_with_driver_params(
    conn: Any, cursor: Any, sql_with_qmark: str, params: Sequence[Any]
) -> None:
    """Execute SQL with driver-specific placeholders."""

    if _is_pymssql_connection(conn):
        cursor.execute(sql_with_qmark.replace("?", "%s"), tuple(params))
    else:
        cursor.execute(sql_with_qmark, tuple(params))


def _quote_ident(name: str) -> str:
    return f"[{str(name).replace(']', ']]')}]"


def _quote_table(schema_name: str, table_name: str) -> str:
    return f"{_quote_ident(schema_name)}.{_quote_ident(table_name)}"


def _find_table_entry(
    schema_snapshot: Optional[Dict[str, Any]],
    table_name: str,
    schema_whitelist: Optional[Sequence[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not schema_snapshot:
        return None

    entries = []
    whitelist = {item.lower() for item in (schema_whitelist or [])}
    for item in (schema_snapshot.get("tables") or []):
        if str(item.get("table", "")).strip("[] ").lower() != table_name.lower():
            continue
        schema_name = str(item.get("schema", "")).lower()
        if whitelist and schema_name not in whitelist:
            continue
        entries.append(item)
    return entries[0] if entries else None


def _pick_column(table_entry: Dict[str, Any], candidates: Sequence[str]) -> Optional[str]:
    available = {
        str(col.get("name", "")).lower(): str(col.get("name", ""))
        for col in (table_entry.get("columns") or [])
    }
    for cand in candidates:
        hit = available.get(cand.lower())
        if hit:
            return hit
    return None


def _best_name(record: Dict[str, Any]) -> str:
    first_name = str(record.get("first_name", "") or "").strip()
    last_name = str(record.get("last_name", "") or "").strip()
    full_name = f"{last_name}{first_name}".strip()
    keyed_name = str(record.get("keyed_name", "") or "").strip()
    login_name = str(record.get("login_name", "") or "").strip()

    if full_name:
        zh = ZH_NAME_RE.search(full_name)
        if zh:
            return zh.group(0)
        return full_name

    if keyed_name and normalize_hex32(keyed_name) is None:
        zh = ZH_NAME_RE.search(keyed_name)
        if zh:
            return zh.group(0)
        return keyed_name

    return login_name


def _identity_score(item: Dict[str, Any]) -> float:
    score = 0.0
    if str(item.get("user_name", "")).strip():
        score += 2.0
    if str(item.get("dept_name", "")).strip():
        score += 1.0
    if str(item.get("login_name", "")).strip():
        score += 0.5
    return score


def _load_department_map(conn: Any, table_entry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    schema_name = str(table_entry.get("schema", "dbo"))
    table_name = str(table_entry.get("table", "DEPARTMENT"))

    id_col = _pick_column(table_entry, ("ID", "id"))
    if not id_col:
        return {}
    name_col = _pick_column(table_entry, ("NAME", "NAME_MEMO", "KEYED_NAME"))
    dept_number_col = _pick_column(table_entry, ("DEPT_NUMBER",))
    parent_col = _pick_column(table_entry, ("PARENT",))
    is_current_col = _pick_column(table_entry, ("IS_CURRENT",))

    select_parts = [f"{_quote_ident(id_col)} AS id"]
    if name_col:
        select_parts.append(f"{_quote_ident(name_col)} AS dept_name")
    if dept_number_col:
        select_parts.append(f"{_quote_ident(dept_number_col)} AS dept_number")
    if parent_col:
        select_parts.append(f"{_quote_ident(parent_col)} AS parent_id")

    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {_quote_table(schema_name, table_name)}"
    )
    params: List[Any] = []
    if is_current_col:
        sql += (
            f" WHERE ({_quote_ident(is_current_col)} = ? "
            f"OR {_quote_ident(is_current_col)} = 1 "
            f"OR {_quote_ident(is_current_col)} IS NULL)"
        )
        params.append("1")

    cursor = conn.cursor()
    _execute_with_driver_params(conn, cursor, sql, params)
    rows = cursor.fetchall()
    col_names = [str(item[0]).lower() for item in (cursor.description or [])]

    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rec = {col_names[idx]: row[idx] for idx in range(len(col_names))}
        dept_id = normalize_hex32(rec.get("id"))
        if not dept_id:
            continue
        result[dept_id] = {
            "dept_id": dept_id,
            "dept_name": str(rec.get("dept_name", "") or "").strip(),
            "dept_number": str(rec.get("dept_number", "") or "").strip(),
            "parent_id": normalize_hex32(rec.get("parent_id")) or "",
        }
    return result


def _load_user_map(
    conn: Any,
    table_entry: Dict[str, Any],
    department_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    schema_name = str(table_entry.get("schema", "dbo"))
    table_name = str(table_entry.get("table", "USER"))

    id_col = _pick_column(table_entry, ("ID", "id"))
    if not id_col:
        return {}
    keyed_name_col = _pick_column(table_entry, ("KEYED_NAME",))
    first_name_col = _pick_column(table_entry, ("FIRST_NAME",))
    last_name_col = _pick_column(table_entry, ("LAST_NAME",))
    login_name_col = _pick_column(table_entry, ("LOGIN_NAME",))
    department_col = _pick_column(table_entry, ("DEPARTMENT",))
    is_current_col = _pick_column(table_entry, ("IS_CURRENT",))

    select_parts = [f"{_quote_ident(id_col)} AS user_id"]
    if keyed_name_col:
        select_parts.append(f"{_quote_ident(keyed_name_col)} AS keyed_name")
    if first_name_col:
        select_parts.append(f"{_quote_ident(first_name_col)} AS first_name")
    if last_name_col:
        select_parts.append(f"{_quote_ident(last_name_col)} AS last_name")
    if login_name_col:
        select_parts.append(f"{_quote_ident(login_name_col)} AS login_name")
    if department_col:
        select_parts.append(f"{_quote_ident(department_col)} AS dept_id")

    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {_quote_table(schema_name, table_name)}"
    )
    params: List[Any] = []
    if is_current_col:
        sql += (
            f" WHERE ({_quote_ident(is_current_col)} = ? "
            f"OR {_quote_ident(is_current_col)} = 1 "
            f"OR {_quote_ident(is_current_col)} IS NULL)"
        )
        params.append("1")

    cursor = conn.cursor()
    _execute_with_driver_params(conn, cursor, sql, params)
    rows = cursor.fetchall()
    col_names = [str(item[0]).lower() for item in (cursor.description or [])]

    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rec = {col_names[idx]: row[idx] for idx in range(len(col_names))}
        user_id = normalize_hex32(rec.get("user_id"))
        if not user_id:
            continue

        dept_id = normalize_hex32(rec.get("dept_id")) or ""
        dept_info = department_map.get(dept_id, {})

        item = {
            "user_id": user_id,
            "user_name": _best_name(rec),
            "login_name": str(rec.get("login_name", "") or "").strip(),
            "keyed_name": str(rec.get("keyed_name", "") or "").strip(),
            "dept_id": dept_id,
            "dept_name": str(dept_info.get("dept_name", "") or "").strip(),
            "dept_number": str(dept_info.get("dept_number", "") or "").strip(),
        }
        exists = result.get(user_id)
        if not exists or _identity_score(item) > _identity_score(exists):
            result[user_id] = item
    return result


def build_identity_context(
    conn: Any,
    schema_snapshot: Optional[Dict[str, Any]] = None,
    schema_whitelist: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Build USER/DEPARTMENT identity maps.

    Returns:
    - user_id_map: {32hex -> {user_name, dept_name, ...}}
    - department_map: {32hex -> {dept_name, dept_number, ...}}
    - warnings: list[str]
    """

    warnings: List[str] = []
    user_entry = _find_table_entry(schema_snapshot, "USER", schema_whitelist=schema_whitelist)
    dept_entry = _find_table_entry(
        schema_snapshot, "DEPARTMENT", schema_whitelist=schema_whitelist
    )

    if not user_entry:
        warnings.append("未在 schema 快照中找到 USER 表，无法解析 32位用户ID。")
    if not dept_entry:
        warnings.append("未在 schema 快照中找到 DEPARTMENT 表，无法补充部门信息。")

    department_map: Dict[str, Dict[str, Any]] = {}
    user_id_map: Dict[str, Dict[str, Any]] = {}

    if dept_entry:
        try:
            department_map = _load_department_map(conn, dept_entry)
        except Exception as exc:
            warnings.append(f"加载 DEPARTMENT 映射失败: {exc}")
    if user_entry:
        try:
            user_id_map = _load_user_map(conn, user_entry, department_map)
        except Exception as exc:
            warnings.append(f"加载 USER 映射失败: {exc}")

    return {
        "user_id_map": user_id_map,
        "department_map": department_map,
        "user_count": len(user_id_map),
        "department_count": len(department_map),
        "user_schema": str(user_entry.get("schema", "")) if user_entry else "",
        "department_schema": str(dept_entry.get("schema", "")) if dept_entry else "",
        "warnings": warnings,
    }


def resolve_owner_value(
    value: Any,
    user_id_map: Dict[str, Dict[str, Any]],
    max_ids: int = 64,
) -> Dict[str, Any]:
    """Resolve IDs in a value into user/dept details."""

    id_tokens = extract_hex32_ids(value, max_ids=max_ids)
    resolved_users: List[Dict[str, Any]] = []
    unresolved_ids: List[str] = []

    for uid in id_tokens:
        matched = user_id_map.get(uid)
        if not matched:
            unresolved_ids.append(uid)
            continue
        resolved_users.append(
            {
                "user_id": uid,
                "user_name": str(matched.get("user_name", "") or "").strip(),
                "login_name": str(matched.get("login_name", "") or "").strip(),
                "dept_id": str(matched.get("dept_id", "") or "").strip(),
                "dept_name": str(matched.get("dept_name", "") or "").strip(),
                "dept_number": str(matched.get("dept_number", "") or "").strip(),
            }
        )

    seen_names = set()
    resolved_names: List[str] = []
    for item in resolved_users:
        name = str(item.get("user_name", "")).strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        resolved_names.append(name)

    resolved_dept_count = 0
    for item in resolved_users:
        if str(item.get("dept_name", "")).strip():
            resolved_dept_count += 1

    return {
        "id_tokens": id_tokens,
        "resolved_users": resolved_users,
        "resolved_names": resolved_names,
        "resolved_dept_count": resolved_dept_count,
        "unresolved_ids": unresolved_ids,
    }
