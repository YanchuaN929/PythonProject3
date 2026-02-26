#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""待处理文件1数据库数据源（只读）。"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from utils.adjust import adjust_date_for_project
from utils.dept_config import get_department_codes, map_code_to_department

FILE1_DB_SOURCE_PREFIX = "db://file1/"
HEX32_RE = re.compile(r"(?i)\b[0-9a-f]{32}\b")
ZH_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")

RESULT_COLUMNS = [
    "接口号",
    "接口时间",
    "责任人",
    "科室",
    "项目号",
    "原始行号",
    "source_file",
]

EXPORT_COLUMNS = ["接口号", "接口日期", "责任人", "所属科室"]


def build_file1_virtual_source(project_id: str) -> str:
    """生成文件1数据库虚拟源路径。"""
    return f"{FILE1_DB_SOURCE_PREFIX}{str(project_id or '').strip()}"


def is_file1_db_virtual_source(path: str) -> bool:
    """判断路径是否是文件1数据库虚拟源。"""
    return str(path or "").strip().lower().startswith(FILE1_DB_SOURCE_PREFIX)


def is_file1_db_source_list(source_files: Sequence[str]) -> bool:
    """判断 source_files 是否全部为文件1数据库虚拟源。"""
    if not source_files:
        return False
    return all(is_file1_db_virtual_source(item) for item in source_files)


def extract_project_id_from_virtual_source(path: str) -> str:
    """从文件1数据库虚拟源提取项目号。"""
    text = str(path or "").strip()
    if not is_file1_db_virtual_source(text):
        return ""
    return text[len(FILE1_DB_SOURCE_PREFIX) :].strip()


def get_file1_db_connection_status() -> Dict[str, str]:
    """获取文件1数据库连接状态。"""
    conn = None
    connector = ""
    try:
        conn, connector = create_connection_from_saved_profile()
        cursor = conn.cursor()
        cursor.execute("SELECT DB_NAME()")
        row = cursor.fetchone()
        db_name = str(row[0]) if row and row[0] is not None else ""
        msg = f"已连接（{connector}）"
        if db_name:
            msg += f"，数据库: {db_name}"
        return {"connected": "1", "message": msg, "connector": connector}
    except Exception as exc:
        return {"connected": "0", "message": f"未连接：{exc}", "connector": ""}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def fetch_file1_db_dataframe(project_id: str, current_datetime: datetime.datetime) -> pd.DataFrame:
    """查询文件1数据库数据并返回标准 DataFrame。"""
    project = str(project_id or "").strip()
    if not project:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    conn = None
    try:
        conn, _connector = create_connection_from_saved_profile()
        raw_rows = _query_file1_latest_rows(conn, project)
        user_map = _query_user_name_map(conn)
        return _build_file1_dataframe(raw_rows, user_map, project, current_datetime)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def build_file1_export_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """将文件1处理结果收敛为导出4列。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=EXPORT_COLUMNS)

    out = pd.DataFrame(
        {
            "接口号": _series_first(df, ("接口号",), ""),
            "接口日期": _series_first(df, ("接口时间", "接口日期"), ""),
            "责任人": _series_first(df, ("责任人",), "无"),
            "所属科室": _series_first(df, ("科室", "所属科室"), ""),
        }
    )
    out["接口号"] = out["接口号"].map(lambda x: str(x or "").strip())
    out["接口日期"] = out["接口日期"].map(lambda x: str(x or "").strip())
    out["责任人"] = out["责任人"].map(lambda x: str(x or "").strip() or "无")
    out["所属科室"] = out["所属科室"].map(lambda x: str(x or "").strip())
    return out


def create_connection_from_saved_profile() -> Tuple[Any, str]:
    """按 sql_explorer 方式创建 SQL Server 连接。"""
    profile = _load_saved_profile()
    from scripts.db_tools.sql_explorer.connect import connect_sql_server

    return connect_sql_server(profile)


def _load_saved_profile() -> Any:
    from scripts.db_tools.sql_explorer.config_store import load_profile

    profile = load_profile()
    if profile is None:
        raise RuntimeError("未找到 sql_explorer 连接配置，请先执行一次连接向导。")
    if not str(getattr(profile, "host", "")).strip():
        raise RuntimeError("sql_explorer 连接配置缺少 host。")
    if not str(getattr(profile, "username", "")).strip():
        raise RuntimeError("sql_explorer 连接配置缺少 username。")
    if not str(getattr(profile, "password", "")).strip():
        raise RuntimeError("sql_explorer 连接配置缺少 password。")
    return profile


def _is_pymssql_connection(conn: Any) -> bool:
    text = f"{getattr(conn.__class__, '__module__', '')}.{getattr(conn.__class__, '__name__', '')}".lower()
    return ("pymssql" in text) or ("_mssql" in text)


def _execute_with_params(conn: Any, cursor: Any, sql_qmark: str, params: Sequence[Any]) -> None:
    if _is_pymssql_connection(conn):
        cursor.execute(sql_qmark.replace("?", "%s"), tuple(params))
    else:
        cursor.execute(sql_qmark, tuple(params))


def _query_file1_latest_rows(conn: Any, project_id: str) -> List[Tuple[Any, ...]]:
    errors: List[str] = []
    sql_template = """
WITH ranked AS (
    SELECT
        [ITEM_NUMBER],
        [RELEASE_PARTY],
        [SWAP_START_DATE],
        [ACTUAL_OPEN_DATE],
        [DEPART_USER],
        [CREATED_BY_ID],
        [MODIFIED_ON],
        [IS_CURRENT],
        ROW_NUMBER() OVER (
            PARTITION BY [ITEM_NUMBER]
            ORDER BY
                CASE WHEN ([IS_CURRENT] = ? OR [IS_CURRENT] = 1) THEN 0 ELSE 1 END,
                TRY_CONVERT(datetime2, [MODIFIED_ON]) DESC,
                TRY_CONVERT(datetime2, [SWAP_START_DATE]) DESC
        ) AS rn
    FROM [{schema}].[IDIACP1000]
    WHERE [PROJ_NUM] = ?
)
SELECT
    [ITEM_NUMBER],
    [RELEASE_PARTY],
    [SWAP_START_DATE],
    [ACTUAL_OPEN_DATE],
    [DEPART_USER],
    [CREATED_BY_ID]
FROM ranked
WHERE rn = 1
"""
    for schema in ("innovator", "dbo"):
        try:
            cursor = conn.cursor()
            sql = sql_template.format(schema=schema)
            _execute_with_params(conn, cursor, sql, ("1", project_id))
            return list(cursor.fetchall() or [])
        except Exception as exc:
            errors.append(f"{schema}.IDIACP1000: {exc}")
    raise RuntimeError(" ; ".join(errors))


def _query_user_name_map(conn: Any) -> Dict[str, str]:
    errors: List[str] = []
    sql_template = """
SELECT
    [ID],
    [LAST_NAME],
    [FIRST_NAME],
    [KEYED_NAME],
    [LOGIN_NAME]
FROM [{schema}].[USER]
WHERE ([IS_CURRENT] = ? OR [IS_CURRENT] = 1 OR [IS_CURRENT] IS NULL)
"""
    for schema in ("innovator", "dbo"):
        try:
            cursor = conn.cursor()
            sql = sql_template.format(schema=schema)
            _execute_with_params(conn, cursor, sql, ("1",))
            result: Dict[str, str] = {}
            for row in cursor.fetchall() or []:
                user_id = _normalize_hex32(row[0])
                if not user_id:
                    continue
                display_name = _best_user_name(row[1], row[2], row[3], row[4])
                if display_name:
                    result[user_id] = display_name
            return result
        except Exception as exc:
            errors.append(f"{schema}.USER: {exc}")
    if errors:
        print(f"[File1-DB] USER映射加载失败，责任人将降级解析: {' ; '.join(errors)}")
    return {}


def _build_file1_dataframe(
    raw_rows: Iterable[Tuple[Any, ...]],
    user_map: Dict[str, str],
    project_id: str,
    current_datetime: datetime.datetime,
) -> pd.DataFrame:
    dept_codes = list(get_department_codes() or [])
    virtual_source = build_file1_virtual_source(project_id)

    records: List[Dict[str, Any]] = []
    for row in raw_rows:
        interface_id = str(row[0] or "").strip()
        release_party = str(row[1] or "").strip()
        swap_start_date = row[2]
        actual_open_date = row[3]
        depart_user = row[4]
        created_by_id = row[5]

        if not interface_id:
            continue
        if not _contains_any_code(release_party, dept_codes):
            continue
        if not _is_empty_value(actual_open_date):
            continue

        interface_date = _pick_interface_date(swap_start_date, actual_open_date)
        if interface_date is None:
            continue
        if not _in_file1_time_window(interface_date, current_datetime, project_id):
            continue

        owner_name = _resolve_owner_name(depart_user, created_by_id, user_map)
        dept_name = map_code_to_department(release_party) or release_party

        records.append(
            {
                "接口号": interface_id,
                "接口时间": interface_date.strftime("%Y.%m.%d"),
                "责任人": owner_name or "无",
                "科室": dept_name,
                "项目号": project_id,
                "source_file": virtual_source,
            }
        )

    if not records:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    out = pd.DataFrame(records)
    out = out.sort_values(by=["接口时间", "接口号"], ascending=[True, True]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    out = out[RESULT_COLUMNS]
    return out


def _contains_any_code(text: str, codes: Sequence[str]) -> bool:
    if not text or not codes:
        return False
    return any(code and code in text for code in codes)


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def _pick_interface_date(swap_start_date: Any, actual_open_date: Any) -> Optional[datetime.datetime]:
    for value in (swap_start_date, actual_open_date):
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            continue
        return parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed
    return None


def _in_file1_time_window(
    interface_date: datetime.datetime,
    current_datetime: datetime.datetime,
    project_id: str,
) -> bool:
    current_day = current_datetime.day
    current_year = current_datetime.year
    current_month = current_datetime.month

    start_date = datetime.datetime(current_year, 1, 1)
    if current_day <= 19:
        if current_month == 12:
            end_date = datetime.datetime(current_year, 12, 31)
        else:
            end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)
    else:
        if current_month == 12:
            end_date = datetime.datetime(current_year + 1, 2, 1) - datetime.timedelta(days=1)
        elif current_month == 11:
            end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(current_year, current_month + 2, 1) - datetime.timedelta(days=1)

    adjusted = adjust_date_for_project(interface_date, project_id)
    return start_date <= adjusted <= end_date


def _resolve_owner_name(depart_user: Any, created_by_id: Any, user_map: Dict[str, str]) -> str:
    for value in (depart_user, created_by_id):
        for user_id in _extract_hex32_ids(value):
            mapped = user_map.get(user_id, "")
            if mapped:
                return mapped

    depart_user_text = str(depart_user or "").strip()
    if depart_user_text:
        before_at = depart_user_text.split("@", 1)[0].strip()
        zh = ZH_NAME_RE.search(before_at)
        if zh:
            return _normalize_person_name(zh.group(0))
        zh_full = ZH_NAME_RE.search(depart_user_text)
        if zh_full:
            return _normalize_person_name(zh_full.group(0))

    return ""


def _extract_hex32_ids(value: Any) -> List[str]:
    text = str(value or "")
    if not text:
        return []
    seen = set()
    ids: List[str] = []
    for token in HEX32_RE.findall(text):
        normalized = _normalize_hex32(token)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ids.append(normalized)
    return ids


def _normalize_hex32(value: Any) -> str:
    text = str(value or "").strip().strip("\"'[]{}()")
    if re.fullmatch(r"[0-9a-fA-F]{32}", text):
        return text.upper()
    return ""


def _best_user_name(last_name: Any, first_name: Any, keyed_name: Any, login_name: Any) -> str:
    full_name = f"{str(last_name or '').strip()}{str(first_name or '').strip()}".strip()
    if full_name:
        zh = ZH_NAME_RE.search(full_name)
        if zh:
            return _normalize_person_name(zh.group(0))
        return full_name

    keyed = str(keyed_name or "").strip()
    if keyed:
        before_at = keyed.split("@", 1)[0].strip()
        zh = ZH_NAME_RE.search(before_at)
        if zh:
            return _normalize_person_name(zh.group(0))
        return before_at

    login = str(login_name or "").strip()
    return login.split("@", 1)[0].strip()


def _normalize_person_name(name: str) -> str:
    text = str(name or "").strip()
    if len(text) >= 3 and text[-1:].isascii() and text[-1:].isalpha():
        return text[:-1]
    return text


def _series_or_default(df: pd.DataFrame, col: str, default: Any) -> pd.Series:
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df))


def _series_first(df: pd.DataFrame, columns: Sequence[str], default: Any) -> pd.Series:
    for col in columns:
        if col in df.columns:
            return df[col]
    return pd.Series([default] * len(df))

