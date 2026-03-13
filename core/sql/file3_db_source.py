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
        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue
        if _clean(row.get("RELEASE_PARTY")) != "B":
            continue
        resp_depart = _clean(row.get("RESP_DEPART"))
        if not resp_depart.startswith(get_organization_filter()):
            continue

        final_forecast = _parse_dt(row.get("FINAL_FORECAST_DATE"))
        pre_forecast = _parse_dt(row.get("PRE_FORECAST_DATE"))
        final_open = _clean(row.get("FINAL_OPEN_DATE"))
        pre_open = _clean(row.get("PRE_OPEN_DATE"))

        route = ""
        interface_time: Optional[datetime.datetime] = None
        if final_forecast is not None and not final_open and _in_time_window(final_forecast, current_datetime, project):
            route = "FINAL"
            interface_time = final_forecast
        elif pre_forecast is not None and not pre_open and _in_time_window(pre_forecast, current_datetime, project):
            route = "PRE"
            interface_time = pre_forecast
        else:
            continue

        owner_name = resolve_user_name(row.get("RESP_SHEZONG"), user_map) or ""
        rows_by_project[project].append(
            {
                "接口号": item_number,
                "接口时间": interface_time.strftime("%Y.%m.%d") if interface_time else "",
                "责任人": owner_name or "无",
                "科室": _normalize_department(resp_depart),
                "项目号": project,
                "source_file": build_file3_virtual_source(project),
                "发布方": _clean(row.get("RELEASE_PARTY")),
                "主办所": resp_depart,
                "初版预报日期": _fmt(pre_forecast),
                "终版预报日期": _fmt(final_forecast),
                "初版打开日期": _fmt(row.get("PRE_OPEN_DATE")),
                "终版打开日期": _fmt(row.get("FINAL_OPEN_DATE")),
                "_source_column": "M" if route == "FINAL" else "L",
            }
        )

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
        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue
        if _clean(row.get("RELEASE_PARTY")) != "B":
            continue
        resp_depart = _clean(row.get("RESP_DEPART"))
        if not resp_depart.startswith(get_organization_filter()):
            continue

        final_forecast = _parse_dt(row.get("FINAL_FORECAST_DATE"))
        pre_forecast = _parse_dt(row.get("PRE_FORECAST_DATE"))
        final_open = _clean(row.get("FINAL_OPEN_DATE"))
        pre_open = _clean(row.get("PRE_OPEN_DATE"))

        route = ""
        interface_time: Optional[datetime.datetime] = None
        if final_forecast is not None and not final_open and _in_time_window(final_forecast, current_datetime, project):
            route = "FINAL"
            interface_time = final_forecast
        elif pre_forecast is not None and not pre_open and _in_time_window(pre_forecast, current_datetime, project):
            route = "PRE"
            interface_time = pre_forecast
        else:
            continue

        owner_name = resolve_user_name(row.get("RESP_SHEZONG"), user_map) or ""
        rows.append(
            {
                "接口号": item_number,
                "接口时间": interface_time.strftime("%Y.%m.%d") if interface_time else "",
                "责任人": owner_name or "无",
                "科室": _normalize_department(resp_depart),
                "项目号": project,
                "source_file": build_file3_virtual_source(project),
                "发布方": _clean(row.get("RELEASE_PARTY")),
                "主办所": resp_depart,
                "初版预报日期": _fmt(pre_forecast),
                "终版预报日期": _fmt(final_forecast),
                "初版打开日期": _fmt(row.get("PRE_OPEN_DATE")),
                "终版打开日期": _fmt(row.get("FINAL_OPEN_DATE")),
                "_source_column": "M" if route == "FINAL" else "L",
            }
        )

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
        "release_party_b_rows": 0,
        "resp_depart_match_rows": 0,
        "final_candidate_rows": 0,
        "pre_candidate_rows": 0,
        "window_match_rows": 0,
        "final_rows": 0,
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
        debug["release_party_b_rows"] += 1
        resp_depart = _clean(row.get("RESP_DEPART"))
        if not resp_depart.startswith(get_organization_filter()):
            continue
        debug["resp_depart_match_rows"] += 1

        final_forecast = _parse_dt(row.get("FINAL_FORECAST_DATE"))
        pre_forecast = _parse_dt(row.get("PRE_FORECAST_DATE"))
        final_open = _clean(row.get("FINAL_OPEN_DATE"))
        pre_open = _clean(row.get("PRE_OPEN_DATE"))

        route = ""
        interface_time: Optional[datetime.datetime] = None
        if final_forecast is not None and not final_open and _in_time_window(final_forecast, current_datetime, project):
            route = "FINAL"
            interface_time = final_forecast
            debug["final_candidate_rows"] += 1
        elif pre_forecast is not None and not pre_open and _in_time_window(pre_forecast, current_datetime, project):
            route = "PRE"
            interface_time = pre_forecast
            debug["pre_candidate_rows"] += 1
        else:
            continue
        debug["window_match_rows"] += 1

        owner_name = resolve_user_name(row.get("RESP_SHEZONG"), user_map) or ""
        rows.append(
            {
                "接口号": item_number,
                "接口时间": interface_time.strftime("%Y.%m.%d") if interface_time else "",
                "责任人": owner_name or "无",
                "科室": _normalize_department(resp_depart),
                "项目号": project,
                "source_file": build_file3_virtual_source(project),
                "发布方": _clean(row.get("RELEASE_PARTY")),
                "主办所": resp_depart,
                "初版预报日期": _fmt(pre_forecast),
                "终版预报日期": _fmt(final_forecast),
                "初版打开日期": _fmt(row.get("PRE_OPEN_DATE")),
                "终版打开日期": _fmt(row.get("FINAL_OPEN_DATE")),
                "_source_column": "M" if route == "FINAL" else "L",
            }
        )

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
