#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File3 SQL-backed data source."""

from __future__ import annotations

import copy
import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from core.sql.offline_dump_utils import iter_filtered_insert_dicts
from core.sql.provider import get_active_provider, resolve_user_name
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import parse_create_columns
from utils.adjust import adjust_date_for_project
from utils.dept_config import get_organization_filter, match_department_name


FILE3_DB_SOURCE_PREFIX = "db://file3/"

RESULT_COLUMNS = [
    "接口号",
    "接口时间",
    "责任人",
    "科室",
    "项目号",
    "原始行号",
    "source_file",
    "发布方",
    "主办所",
    "初版预报日期",
    "终版预报日期",
    "初版打开日期",
    "终版打开日期",
]

_FILE3_WARM_CACHE: Dict[Tuple[str, str], Dict[str, pd.DataFrame]] = {}
_FILE3_DEBUG_SNAPSHOTS: Dict[str, Dict[str, Any]] = {}


def build_file3_virtual_source(project_id: str) -> str:
    return f"{FILE3_DB_SOURCE_PREFIX}{str(project_id or '').strip()}"


def is_file3_db_virtual_source(path: str) -> bool:
    return str(path or "").strip().lower().startswith(FILE3_DB_SOURCE_PREFIX)


def extract_project_id_from_virtual_source(path: str) -> str:
    text = str(path or "").strip()
    if not is_file3_db_virtual_source(text):
        return ""
    return text[len(FILE3_DB_SOURCE_PREFIX) :].strip()


def get_file3_debug_snapshots() -> Dict[str, Dict[str, Any]]:
    return copy.deepcopy(_FILE3_DEBUG_SNAPSHOTS)


def prime_file3_db_cache(project_ids, current_datetime: datetime.datetime, provider=None) -> Dict[str, pd.DataFrame]:
    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return {}
    projects = sorted({str(item or "").strip() for item in (project_ids or []) if str(item or "").strip()})
    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    if not projects:
        _FILE3_WARM_CACHE[cache_key] = {}
        return {}

    path = provider.get_table_path("ICMACP1000")
    if not path:
        frames = {project: pd.DataFrame(columns=RESULT_COLUMNS) for project in projects}
        _FILE3_WARM_CACHE[cache_key] = frames
        return {project: frame.copy() for project, frame in frames.items()}

    user_map = provider.get_user_map()
    columns = parse_create_columns(path)
    project_set = set(projects)
    project_tokens = []
    for project in projects:
        project_tokens.extend([f"N'{project}'", f"'{project}'"])

    rows_by_project: Dict[str, List[Dict[str, Any]]] = {project: [] for project in projects}
    for row in iter_filtered_insert_dicts(path, columns, project_tokens):
        if not _is_current(row):
            continue
        project = _clean(row.get("PROJ_NUM"))
        if project not in project_set:
            continue
        result_row = _build_file3_result_row(row, project, current_datetime, user_map)
        if result_row is not None:
            rows_by_project[project].append(result_row)

    frames: Dict[str, pd.DataFrame] = {}
    for project in projects:
        rows = rows_by_project.get(project, [])
        if rows:
            out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号"]).reset_index(drop=True)
            out["原始行号"] = out.index + 2
            frames[project] = out[RESULT_COLUMNS + ["_source_column"]]
        else:
            frames[project] = pd.DataFrame(columns=RESULT_COLUMNS + ["_source_column"])

    _FILE3_WARM_CACHE[cache_key] = frames
    return {project: frame.copy() for project, frame in frames.items()}


def fetch_file3_db_dataframe(project_id: str, current_datetime: datetime.datetime, provider=None) -> pd.DataFrame:
    project = str(project_id or "").strip()
    if not project:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return _fetch_file3_live_dataframe(project, current_datetime, provider)
    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    cached = _FILE3_WARM_CACHE.get(cache_key)
    if cached is not None and project in cached:
        return cached[project].copy()
    user_map = provider.get_user_map()
    path = provider.get_table_path("ICMACP1000")
    if not path:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    columns = parse_create_columns(path)
    project_tokens = [f"N'{project}'", f"'{project}'"]

    rows: List[Dict[str, Any]] = []
    for row in iter_filtered_insert_dicts(path, columns, project_tokens):
        if not _is_current(row):
            continue
        if _clean(row.get("PROJ_NUM")) != project:
            continue
        result_row = _build_file3_result_row(row, project, current_datetime, user_map)
        if result_row is not None:
            rows.append(result_row)

    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号"]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    return out[RESULT_COLUMNS + ["_source_column"]]


def _fetch_file3_live_dataframe(project: str, current_datetime: datetime.datetime, provider) -> pd.DataFrame:
    user_map = provider.get_user_map()
    debug: Dict[str, Any] = {
        "backend": provider.source_label(),
        "project_id": project,
        "query_date": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "query_rows_total": 0,
        "item_number_rows": 0,
        "p1_release_party_b_rows": 0,
        "p2_resp_depart_prefix_rows": 0,
        "p3_final_window_rows": 0,
        "p4_pre_window_rows": 0,
        "p5_pre_open_empty_rows": 0,
        "p6_final_open_empty_rows": 0,
        "route_final_rows": 0,
        "route_pre_rows": 0,
        "final_rows": 0,
        "sample_resp_depart_rows": [],
    }
    sql_template = """
SELECT
    [ID],
    [ITEM_NUMBER],
    [RELEASE_PARTY],
    [RESP_DEPART],
    [RESP_SHEZONG],
    [PRE_FORECAST_DATE],
    [FINAL_FORECAST_DATE],
    [PRE_OPEN_DATE],
    [FINAL_OPEN_DATE],
    [PROJ_NUM],
    [IS_CURRENT]
FROM [{schema}].[ICMACP1000]
WHERE [PROJ_NUM] = ?
  AND ([IS_CURRENT] = ? OR [IS_CURRENT] = 1 OR [IS_CURRENT] IS NULL)
"""
    live_rows = provider.fetch_rows(sql_template, params=(project, "1"))
    debug["query_rows_total"] = len(live_rows)

    rows: List[Dict[str, Any]] = []
    for row in live_rows:
        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue
        debug["item_number_rows"] += 1

        if _clean(row.get("RELEASE_PARTY")) != "B":
            continue
        debug["p1_release_party_b_rows"] += 1

        resp_depart = _clean(row.get("RESP_DEPART"))
        if not _matches_file3_dept(resp_depart):
            continue
        debug["p2_resp_depart_prefix_rows"] += 1
        if len(debug["sample_resp_depart_rows"]) < 5:
            debug["sample_resp_depart_rows"].append(
                {
                    "item_number": item_number,
                    "pre_forecast_date": _fmt(row.get("PRE_FORECAST_DATE")),
                    "final_forecast_date": _fmt(row.get("FINAL_FORECAST_DATE")),
                    "pre_open_date": _fmt(row.get("PRE_OPEN_DATE")),
                    "final_open_date": _fmt(row.get("FINAL_OPEN_DATE")),
                }
            )

        p3_final = _is_valid_file3_forecast(row.get("FINAL_FORECAST_DATE"), current_datetime, project)
        p4_pre = _is_valid_file3_forecast(row.get("PRE_FORECAST_DATE"), current_datetime, project)
        p5_pre_open_empty = _is_blank_excel_value(row.get("PRE_OPEN_DATE"))
        p6_final_open_empty = _is_blank_excel_value(row.get("FINAL_OPEN_DATE"))
        if p3_final:
            debug["p3_final_window_rows"] += 1
        if p4_pre:
            debug["p4_pre_window_rows"] += 1
        if p5_pre_open_empty:
            debug["p5_pre_open_empty_rows"] += 1
        if p6_final_open_empty:
            debug["p6_final_open_empty_rows"] += 1

        result_row = _build_file3_result_row(row, project, current_datetime, user_map)
        if result_row is None:
            continue
        if result_row.get("_source_column") == "M":
            debug["route_final_rows"] += 1
        else:
            debug["route_pre_rows"] += 1
        rows.append(result_row)

    debug["final_rows"] = len(rows)
    debug["sample_interface_ids"] = [str(item.get("接口号", "")) for item in rows[:5]]
    _FILE3_DEBUG_SNAPSHOTS[project] = debug
    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS + ["_source_column"])
    out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号"]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    return out[RESULT_COLUMNS + ["_source_column"]]


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "nan", "nat"}:
        return ""
    return text


def _is_current(row: Dict[str, Any]) -> bool:
    return _clean(row.get("IS_CURRENT")).upper() in {"", "1", "Y", "TRUE", "T"}


def _parse_dt(value: Any) -> Optional[datetime.datetime]:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed


def _fmt(value: Any) -> str:
    dt = _parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%Y.%m.%d")


def _normalize_department(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "请室主任确认"
    matched = match_department_name(text)
    return matched if matched and matched != text else "请室主任确认"


def _matches_file3_dept(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    return text.startswith(get_organization_filter())


def _is_blank_excel_value(value: Any) -> bool:
    return _clean(value) == ""


def _is_valid_file3_forecast(value: Any, current_datetime: datetime.datetime, project_id: str) -> bool:
    text = _clean(value)
    if not text or text.startswith("4444"):
        return False
    target = _parse_dt(value)
    if target is None:
        return False
    return _in_time_window(target, current_datetime, project_id)


def _build_file3_result_row(
    row: Dict[str, Any],
    project: str,
    current_datetime: datetime.datetime,
    user_map: Dict[str, Dict[str, str]],
) -> Optional[Dict[str, Any]]:
    item_number = _clean(row.get("ITEM_NUMBER"))
    if not item_number:
        return None
    if _clean(row.get("RELEASE_PARTY")) != "B":
        return None

    resp_depart = _clean(row.get("RESP_DEPART"))
    if not _matches_file3_dept(resp_depart):
        return None

    final_match = _is_valid_file3_forecast(row.get("FINAL_FORECAST_DATE"), current_datetime, project) and _is_blank_excel_value(
        row.get("FINAL_OPEN_DATE")
    )
    pre_match = _is_valid_file3_forecast(row.get("PRE_FORECAST_DATE"), current_datetime, project) and _is_blank_excel_value(
        row.get("PRE_OPEN_DATE")
    )
    if not final_match and not pre_match:
        return None

    route = "M" if final_match else "L"
    interface_time = _parse_dt(row.get("FINAL_FORECAST_DATE")) if route == "M" else _parse_dt(row.get("PRE_FORECAST_DATE"))
    owner_name = resolve_user_name(row.get("RESP_SHEZONG"), user_map) or ""
    return {
        "接口号": item_number,
        "接口时间": interface_time.strftime("%Y.%m.%d") if interface_time else "",
        "责任人": owner_name or "无",
        "科室": _normalize_department(resp_depart),
        "项目号": project,
        "source_file": build_file3_virtual_source(project),
        "发布方": _clean(row.get("RELEASE_PARTY")),
        "主办所": resp_depart,
        "初版预报日期": _fmt(row.get("PRE_FORECAST_DATE")),
        "终版预报日期": _fmt(row.get("FINAL_FORECAST_DATE")),
        "初版打开日期": _fmt(row.get("PRE_OPEN_DATE")),
        "终版打开日期": _fmt(row.get("FINAL_OPEN_DATE")),
        "_source_column": route,
    }


def _in_time_window(target_date: datetime.datetime, current_datetime: datetime.datetime, project_id: str) -> bool:
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
        if current_month == 11:
            end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
        elif current_month == 12:
            end_date = datetime.datetime(current_year + 1, 2, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(current_year, current_month + 2, 1) - datetime.timedelta(days=1)
    adjusted = adjust_date_for_project(target_date, project_id)
    return start_date <= adjusted <= end_date
