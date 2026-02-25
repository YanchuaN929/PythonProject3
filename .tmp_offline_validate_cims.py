from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from scripts.db_tools.sql_explorer.identity_resolver import extract_hex32_ids, normalize_hex32
from scripts.db_tools.sql_explorer.roster import load_roster_names, normalize_owner_tokens

BASE_DIR = Path("sql_explorer_output/CIMS-sql")

SKIP_TABLES = {"USER", "DEPARTMENT", "INNOVATOR"}
OWNER_HINTS = (
    "owner",
    "responsible",
    "assignee",
    "person",
    "principal",
    "created_by_id",
    "owned_by_id",
    "managed_by_id",
    "modified_by_id",
    "dept_user",
    "shezong",
    "relevant_person",
    "compile_user",
    "delay_open_person",
    "reopen_person",
    "责任人",
    "负责人",
    "经办",
    "主办",
    "办理人",
    "设计人",
)
HEX32_RE = re.compile(r"(?i)\b[0-9a-f]{32}\b")
ZH_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")


@dataclass
class ColumnDef:
    name: str
    data_type: str


def parse_columns(sql_path: Path) -> List[ColumnDef]:
    cols: List[ColumnDef] = []
    in_create = False
    with sql_path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            text = line.strip()
            upper = text.upper()
            if not in_create:
                if upper.startswith("CREATE TABLE"):
                    in_create = True
                continue
            if text.startswith(")"):
                break
            if not text.startswith("["):
                continue
            right = text.find("]")
            if right <= 1:
                continue
            col_name = text[1:right]
            rest = text[right + 1 :].strip().rstrip(",")
            data_type = rest.split()[0].lower() if rest else ""
            cols.append(ColumnDef(name=col_name, data_type=data_type))
    return cols


def _clean_token(token: str) -> Optional[str]:
    raw = token.strip()
    if not raw:
        return None
    if raw.upper() == "NULL":
        return None
    return raw


def parse_insert_values(line: str, max_fields: Optional[int] = None) -> Optional[List[Optional[str]]]:
    upper = line.upper()
    pos = upper.find("VALUES")
    if pos < 0:
        return None
    left = line.find("(", pos)
    if left < 0:
        return None

    values: List[Optional[str]] = []
    buf: List[str] = []
    in_str = False
    i = left + 1
    n = len(line)

    while i < n:
        ch = line[i]
        if in_str:
            if ch == "'":
                if i + 1 < n and line[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch == "N" and i + 1 < n and line[i + 1] == "'":
            in_str = True
            i += 2
            continue
        if ch == "'":
            in_str = True
            i += 1
            continue
        if ch == ",":
            values.append(_clean_token("".join(buf)))
            buf = []
            i += 1
            if max_fields and len(values) >= max_fields:
                break
            continue
        if ch == ")":
            values.append(_clean_token("".join(buf)))
            break
        buf.append(ch)
        i += 1

    return values


def iter_insert_rows(
    sql_path: Path, max_fields: Optional[int] = None, max_rows: Optional[int] = None
) -> Iterable[List[Optional[str]]]:
    count = 0
    with sql_path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            if "INSERT INTO" not in line.upper():
                continue
            row = parse_insert_values(line, max_fields=max_fields)
            if row is None:
                continue
            yield row
            count += 1
            if max_rows is not None and count >= max_rows:
                break


def _best_name(
    first_name: Optional[str],
    last_name: Optional[str],
    keyed_name: Optional[str],
    login_name: Optional[str],
) -> str:
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    full = f"{last}{first}".strip()
    if full:
        hit = ZH_NAME_RE.search(full)
        return hit.group(0) if hit else full

    keyed = (keyed_name or "").strip()
    if keyed and normalize_hex32(keyed) is None:
        hit = ZH_NAME_RE.search(keyed)
        return hit.group(0) if hit else keyed

    return (login_name or "").strip()


def _idx_map(columns: List[ColumnDef]) -> Dict[str, int]:
    return {item.name.lower(): idx for idx, item in enumerate(columns)}


def _col_name(idx: Dict[str, int], *candidates: str) -> Optional[str]:
    for name in candidates:
        if name.lower() in idx:
            return name.lower()
    return None


def _is_current(value: Optional[str]) -> bool:
    if value is None:
        return True
    text = str(value).strip().lower()
    return text in {"1", "true", "y", "yes"}


def _sample_limit(path: Path) -> Optional[int]:
    size = path.stat().st_size
    if size >= 400 * 1024 * 1024:
        return 180_000
    if size >= 200 * 1024 * 1024:
        return 220_000
    return None


def build_department_map(sql_path: Path) -> Dict[str, Dict[str, str]]:
    cols = parse_columns(sql_path)
    idx = _idx_map(cols)
    id_key = _col_name(idx, "id")
    if not id_key:
        return {}

    name_key = _col_name(idx, "name", "name_memo", "keyed_name")
    dept_num_key = _col_name(idx, "dept_number")
    is_current_key = _col_name(idx, "is_current")
    max_idx = max(
        idx[id_key],
        idx[name_key] if name_key else 0,
        idx[dept_num_key] if dept_num_key else 0,
        idx[is_current_key] if is_current_key else 0,
    )

    mapping: Dict[str, Dict[str, str]] = {}
    for row in iter_insert_rows(sql_path, max_fields=max_idx + 1):
        dep_id = normalize_hex32(row[idx[id_key]] if idx[id_key] < len(row) else None)
        if not dep_id:
            continue
        is_curr = True
        if is_current_key:
            raw = row[idx[is_current_key]] if idx[is_current_key] < len(row) else None
            is_curr = _is_current(raw)

        dep_name = ""
        if name_key and idx[name_key] < len(row):
            dep_name = (row[idx[name_key]] or "").strip()
        dep_num = ""
        if dept_num_key and idx[dept_num_key] < len(row):
            dep_num = (row[idx[dept_num_key]] or "").strip()

        old = mapping.get(dep_id)
        new_score = (2.0 if is_curr else 0.0) + (1.0 if dep_name else 0.0)
        old_score = (
            (2.0 if old.get("is_current") == "1" else 0.0) + (1.0 if old.get("dept_name") else 0.0)
            if old
            else -1.0
        )
        if old is None or new_score > old_score:
            mapping[dep_id] = {
                "dept_name": dep_name,
                "dept_number": dep_num,
                "is_current": "1" if is_curr else "0",
            }
    return mapping


def build_user_map(sql_path: Path, department_map: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    cols = parse_columns(sql_path)
    idx = _idx_map(cols)
    id_key = _col_name(idx, "id")
    if not id_key:
        return {}

    dept_key = _col_name(idx, "department")
    first_key = _col_name(idx, "first_name")
    last_key = _col_name(idx, "last_name")
    keyed_key = _col_name(idx, "keyed_name")
    login_key = _col_name(idx, "login_name")
    is_current_key = _col_name(idx, "is_current")

    max_idx = max(
        idx[id_key],
        idx[dept_key] if dept_key else 0,
        idx[first_key] if first_key else 0,
        idx[last_key] if last_key else 0,
        idx[keyed_key] if keyed_key else 0,
        idx[login_key] if login_key else 0,
        idx[is_current_key] if is_current_key else 0,
    )

    user_map: Dict[str, Dict[str, str]] = {}
    for row in iter_insert_rows(sql_path, max_fields=max_idx + 1):
        uid = normalize_hex32(row[idx[id_key]] if idx[id_key] < len(row) else None)
        if not uid:
            continue
        dep_id = normalize_hex32(row[idx[dept_key]] if dept_key and idx[dept_key] < len(row) else None)
        dept = department_map.get(dep_id or "", {})
        first_name = row[idx[first_key]] if first_key and idx[first_key] < len(row) else None
        last_name = row[idx[last_key]] if last_key and idx[last_key] < len(row) else None
        keyed_name = row[idx[keyed_key]] if keyed_key and idx[keyed_key] < len(row) else None
        login_name = row[idx[login_key]] if login_key and idx[login_key] < len(row) else None
        is_curr_raw = row[idx[is_current_key]] if is_current_key and idx[is_current_key] < len(row) else None

        user_name = _best_name(first_name, last_name, keyed_name, login_name)
        is_curr = _is_current(is_curr_raw)
        info = {
            "user_name": user_name,
            "login_name": (login_name or "").strip(),
            "dept_id": dep_id or "",
            "dept_name": dept.get("dept_name", ""),
            "dept_number": dept.get("dept_number", ""),
            "is_current": "1" if is_curr else "0",
        }
        old = user_map.get(uid)
        new_score = (
            (2.0 if user_name else 0.0)
            + (1.0 if info["dept_name"] else 0.0)
            + (1.0 if is_curr else 0.0)
            + (0.5 if info["login_name"] else 0.0)
        )
        old_score = (
            (2.0 if old.get("user_name") else 0.0)
            + (1.0 if old.get("dept_name") else 0.0)
            + (1.0 if old.get("is_current") == "1" else 0.0)
            + (0.5 if old.get("login_name") else 0.0)
            if old
            else -1.0
        )
        if old is None or new_score > old_score:
            user_map[uid] = info
    return user_map


def is_owner_column(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in OWNER_HINTS)


def analyze_table_owner_fields(
    sql_path: Path,
    user_map: Dict[str, Dict[str, str]],
    roster_names: set[str],
) -> Dict[str, Any]:
    cols = parse_columns(sql_path)
    idx = _idx_map(cols)
    is_current_idx = idx.get("is_current")

    owner_cols = [item for item in cols if is_owner_column(item.name)]
    if not owner_cols:
        return {
            "table": sql_path.stem.upper(),
            "file": str(sql_path),
            "sample_limit": 0,
            "processed_rows": 0,
            "owner_columns": [],
        }

    max_idx = max([idx[item.name.lower()] for item in owner_cols] + ([is_current_idx] if is_current_idx is not None else [0]))
    limit = _sample_limit(sql_path)

    per_col: Dict[str, Dict[str, Any]] = {}
    for item in owner_cols:
        per_col[item.name] = {
            "column": item.name,
            "data_type": item.data_type,
            "non_null_rows": 0,
            "rows_with_id": 0,
            "id_token_count": 0,
            "resolved_id_count": 0,
            "resolved_dept_count": 0,
            "resolved_name_tokens": 0,
            "resolved_name_in_roster": 0,
            "direct_name_tokens": 0,
            "direct_name_in_roster": 0,
            "unresolved_id_examples": Counter(),
            "resolved_user_examples": Counter(),
        }

    processed = 0
    for row in iter_insert_rows(sql_path, max_fields=max_idx + 1, max_rows=limit):
        if is_current_idx is not None and is_current_idx < len(row):
            if not _is_current(row[is_current_idx]):
                continue
        processed += 1
        for item in owner_cols:
            cidx = idx[item.name.lower()]
            if cidx >= len(row):
                continue
            raw = row[cidx]
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            stat = per_col[item.name]
            stat["non_null_rows"] += 1

            ids = extract_hex32_ids(text, max_ids=256)
            if ids:
                stat["rows_with_id"] += 1
                stat["id_token_count"] += len(ids)
                for uid in ids:
                    info = user_map.get(uid)
                    if not info:
                        stat["unresolved_id_examples"][uid] += 1
                        continue
                    stat["resolved_id_count"] += 1
                    if info.get("dept_name"):
                        stat["resolved_dept_count"] += 1
                    uname = (info.get("user_name") or "").strip()
                    if uname:
                        stat["resolved_name_tokens"] += 1
                        if uname in roster_names:
                            stat["resolved_name_in_roster"] += 1
                        key = f"{uname}@{info.get('dept_name','')}".strip("@")
                        stat["resolved_user_examples"][key] += 1
                continue

            tokens = normalize_owner_tokens(text)
            if not tokens:
                continue
            stat["direct_name_tokens"] += len(tokens)
            for token in tokens:
                if token in roster_names:
                    stat["direct_name_in_roster"] += 1

    owner_rows: List[Dict[str, Any]] = []
    for item in owner_cols:
        row = per_col[item.name]
        id_count = int(row["id_token_count"])
        resolved = int(row["resolved_id_count"])
        resolved_names = int(row["resolved_name_tokens"])
        resolved_name_in_roster = int(row["resolved_name_in_roster"])
        direct_tokens = int(row["direct_name_tokens"])
        direct_in_roster = int(row["direct_name_in_roster"])
        overall_tokens = resolved_names + direct_tokens
        overall_in_roster = resolved_name_in_roster + direct_in_roster

        owner_rows.append(
            {
                "column": row["column"],
                "data_type": row["data_type"],
                "non_null_rows": int(row["non_null_rows"]),
                "rows_with_id": int(row["rows_with_id"]),
                "id_token_count": id_count,
                "resolved_id_count": resolved,
                "id_resolved_rate": round((resolved / id_count), 6) if id_count else 0.0,
                "resolved_dept_rate": round((int(row["resolved_dept_count"]) / resolved), 6)
                if resolved
                else 0.0,
                "resolved_name_in_roster_rate": round(
                    (resolved_name_in_roster / resolved_names), 6
                )
                if resolved_names
                else 0.0,
                "direct_name_tokens": direct_tokens,
                "direct_name_in_roster_rate": round((direct_in_roster / direct_tokens), 6)
                if direct_tokens
                else 0.0,
                "overall_name_in_roster_rate": round((overall_in_roster / overall_tokens), 6)
                if overall_tokens
                else 0.0,
                "unresolved_id_examples": [k for k, _v in row["unresolved_id_examples"].most_common(10)],
                "resolved_user_examples": [k for k, _v in row["resolved_user_examples"].most_common(10)],
            }
        )

    owner_rows.sort(
        key=lambda x: (
            float(x["overall_name_in_roster_rate"]),
            float(x["id_resolved_rate"]),
            int(x["id_token_count"]),
        ),
        reverse=True,
    )
    return {
        "table": sql_path.stem.upper(),
        "file": str(sql_path),
        "sample_limit": limit if limit is not None else -1,
        "processed_rows": processed,
        "owner_columns": owner_rows,
    }


def main() -> int:
    if not BASE_DIR.exists():
        raise SystemExit(f"Missing folder: {BASE_DIR}")

    roster_names = load_roster_names(None)

    dep_path = BASE_DIR / "DEPARTMENT.sql"
    user_path = BASE_DIR / "USER.sql"
    if not dep_path.exists() or not user_path.exists():
        raise SystemExit("USER.sql/DEPARTMENT.sql not found in CIMS-sql")

    department_map = build_department_map(dep_path)
    user_map = build_user_map(user_path, department_map)

    users_with_dept = sum(1 for v in user_map.values() if (v.get("dept_name") or "").strip())
    users_with_name = sum(1 for v in user_map.values() if (v.get("user_name") or "").strip())
    users_in_roster = sum(
        1 for v in user_map.values() if (v.get("user_name") or "").strip() in roster_names
    )

    tables: List[Path] = []
    for path in sorted(BASE_DIR.glob("*.sql")):
        stem = path.stem.upper()
        if stem in SKIP_TABLES:
            continue
        tables.append(path)

    table_results: List[Dict[str, Any]] = []
    for path in tables:
        table_results.append(analyze_table_owner_fields(path, user_map, roster_names))

    summary_rows: List[Dict[str, Any]] = []
    for table in table_results:
        owner_cols = table.get("owner_columns") or []
        if not owner_cols:
            continue
        best = owner_cols[0]
        summary_rows.append(
            {
                "table": table["table"],
                "processed_rows": table["processed_rows"],
                "sample_limit": table["sample_limit"],
                "best_owner_column": best["column"],
                "best_id_resolved_rate": best["id_resolved_rate"],
                "best_resolved_dept_rate": best["resolved_dept_rate"],
                "best_overall_name_in_roster_rate": best["overall_name_in_roster_rate"],
                "best_id_token_count": best["id_token_count"],
            }
        )

    summary_rows.sort(
        key=lambda x: (
            float(x["best_overall_name_in_roster_rate"]),
            float(x["best_id_resolved_rate"]),
            int(x["best_id_token_count"]),
        ),
        reverse=True,
    )

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = BASE_DIR / f"offline_owner_validation_{now}.json"
    payload = {
        "generated_at": now,
        "base_dir": str(BASE_DIR),
        "roster_count": len(roster_names),
        "user_mapping": {
            "user_count": len(user_map),
            "department_count": len(department_map),
            "users_with_name": users_with_name,
            "users_with_dept": users_with_dept,
            "users_name_in_roster": users_in_roster,
            "users_name_in_roster_rate": round((users_in_roster / users_with_name), 6)
            if users_with_name
            else 0.0,
        },
        "table_summary": summary_rows,
        "table_details": table_results,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] report: {out_json}")
    print(
        "[INFO] user_map:"
        f" user={len(user_map)}, dept={len(department_map)},"
        f" users_with_name={users_with_name}, users_with_dept={users_with_dept},"
        f" users_name_in_roster={users_in_roster}/{users_with_name or 1}"
    )
    for item in summary_rows[:8]:
        limit_text = "ALL" if int(item["sample_limit"]) < 0 else str(item["sample_limit"])
        print(
            f"[TOP] {item['table']}: {item['best_owner_column']}, "
            f"id_resolved={item['best_id_resolved_rate']}, "
            f"dept_resolved={item['best_resolved_dept_rate']}, "
            f"roster_rate={item['best_overall_name_in_roster_rate']}, "
            f"rows={item['processed_rows']}, sample={limit_text}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
