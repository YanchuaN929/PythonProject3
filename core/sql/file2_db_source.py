#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File2 SQL-backed data source."""

from __future__ import annotations

import copy
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from core.sql.offline_dump_utils import iter_filtered_insert_dicts, iter_insert_dicts_by_first_id
from core.sql.provider import get_active_provider, resolve_user_name
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import parse_create_columns
from utils.adjust import adjust_date_for_project
from utils.dept_config import contains_department_code, get_organization_filter, match_department_name


FILE2_DB_SOURCE_PREFIX = "db://file2/"

RESULT_COLUMNS = [
    "接口号",
    "接口时间",
    "责任人",
    "科室",
    "项目号",
    "原始行号",
    "source_file",
    "信息单编号",
    "提出日期",
    "回文期限",
    "回文日期",
    "对方文号",
]

_FILE2_WARM_CACHE: Dict[Tuple[str, str], Dict[str, pd.DataFrame]] = {}
_FILE2_DEBUG_SNAPSHOTS: Dict[str, Dict[str, Any]] = {}


def build_file2_virtual_source(project_id: str) -> str:
    return f"{FILE2_DB_SOURCE_PREFIX}{str(project_id or '').strip()}"


def is_file2_db_virtual_source(path: str) -> bool:
    return str(path or "").strip().lower().startswith(FILE2_DB_SOURCE_PREFIX)


def extract_project_id_from_virtual_source(path: str) -> str:
    text = str(path or "").strip()
    if not is_file2_db_virtual_source(text):
        return ""
    return text[len(FILE2_DB_SOURCE_PREFIX) :].strip()


def get_file2_debug_snapshots() -> Dict[str, Dict[str, Any]]:
    return copy.deepcopy(_FILE2_DEBUG_SNAPSHOTS)


def prime_file2_db_cache(project_ids, current_datetime: datetime.datetime, provider=None) -> Dict[str, pd.DataFrame]:
    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return {}
    projects = sorted({str(item or "").strip() for item in (project_ids or []) if str(item or "").strip()})
    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    if not projects:
        _FILE2_WARM_CACHE[cache_key] = {}
        return {}

    project_set = set(projects)
    user_map = provider.get_user_map()
    int_path = provider.get_table_path("INTINTERFACEDOC")
    if not int_path:
        frames = {project: pd.DataFrame(columns=RESULT_COLUMNS) for project in projects}
        _FILE2_WARM_CACHE[cache_key] = frames
        return {project: frame.copy() for project, frame in frames.items()}

    int_columns = parse_create_columns(int_path)
    project_tokens = []
    for project in projects:
        project_tokens.extend([f"N'{project}'", f"'{project}'"])

    reply_by_ref: Dict[Tuple[str, str], Dict[str, Any]] = {}
    candidates_by_project: Dict[str, List[Dict[str, Any]]] = {project: [] for project in projects}
    candidate_source_ids: Set[str] = set()
    direct_related_ids: Set[str] = set()

    for row in iter_filtered_insert_dicts(int_path, int_columns, project_tokens):
        if not _is_current(row):
            continue

        project = _clean(row.get("PROJ_NUM"))
        if project not in project_set:
            continue

        ref_item = _clean(row.get("REF_ITEM_NUMBER"))
        if ref_item:
            reply_key = (project, ref_item)
            prev = reply_by_ref.get(reply_key)
            if prev is None or _sort_key(row) >= _sort_key(prev):
                reply_by_ref[reply_key] = row

        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue

        dept_text = _pick_first_non_empty(row.get("PROPOSED_DEPT"), row.get("RECEIVE_DEPT"), row.get("RELEASE_PARTY"))
        if not _matches_internal_dept(dept_text):
            continue

        submit_date = _parse_dt(row.get("SUBMIT_DATE"))
        if submit_date is None:
            continue

        due_date = submit_date + datetime.timedelta(days=14)
        if not _in_file2_window(due_date, current_datetime, project):
            continue

        source_id = _clean(row.get("ID")).upper()
        if source_id:
            candidate_source_ids.add(source_id)
        direct_related_id = _clean(row.get("IDIACP1000")).upper()
        if direct_related_id:
            direct_related_ids.add(direct_related_id)

        candidates_by_project[project].append(
            {
                "row": row,
                "item_number": item_number,
                "dept_text": dept_text,
                "submit_date": submit_date,
                "due_date": due_date,
                "source_id": source_id,
                "direct_related_id": direct_related_id,
            }
        )

    link_map: Dict[str, List[str]] = {}
    bridge_path = provider.get_table_path("INTINTERFACEDOCIDIACP1000")
    if bridge_path and candidate_source_ids:
        bridge_columns = parse_create_columns(bridge_path)
        for row in iter_filtered_insert_dicts(bridge_path, bridge_columns, list(candidate_source_ids)):
            if not _is_current(row):
                continue
            source_id = _clean(row.get("SOURCE_ID")).upper()
            related_id = _clean(row.get("RELATED_ID")).upper()
            if source_id and related_id and source_id in candidate_source_ids:
                link_map.setdefault(source_id, []).append(related_id)

    related_ids: Set[str] = set(direct_related_ids)
    for values in link_map.values():
        related_ids.update(value for value in values if value)

    idi_by_id: Dict[str, str] = {}
    idi_path = provider.get_table_path("IDIACP1000")
    if idi_path and related_ids:
        idi_columns = parse_create_columns(idi_path)
        for row in iter_insert_dicts_by_first_id(idi_path, idi_columns, list(related_ids)):
            if not _is_current(row):
                continue
            row_id = _clean(row.get("ID")).upper()
            if row_id not in related_ids:
                continue
            item_number = _clean(row.get("ITEM_NUMBER"))
            if item_number:
                idi_by_id[row_id] = item_number

    frames: Dict[str, pd.DataFrame] = {}
    for project in projects:
        rows: List[Dict[str, Any]] = []
        for candidate in candidates_by_project.get(project, []):
            item_number = candidate["item_number"]
            reply_row = reply_by_ref.get((project, item_number))
            reply_release = _parse_dt(reply_row.get("RELEASE_DATE")) if reply_row else None
            if reply_release is not None:
                continue

            row = candidate["row"]
            interface_id = ""
            if candidate["direct_related_id"]:
                interface_id = idi_by_id.get(candidate["direct_related_id"], "")
            if not interface_id:
                for related_id in link_map.get(candidate["source_id"], []):
                    interface_id = idi_by_id.get(related_id, "")
                    if interface_id:
                        break
            if not interface_id:
                interface_id = _clean(row.get("REF_ITEM_NUMBER"))
            if not interface_id:
                continue

            owner_name = (
                resolve_user_name(row.get("MODIFIED_BY_ID"), user_map)
                or resolve_user_name(row.get("CREATED_BY_ID"), user_map)
                or "无"
            )

            rows.append(
                {
                    "接口号": interface_id,
                    "接口时间": candidate["due_date"].strftime("%Y.%m.%d"),
                    "责任人": owner_name,
                    "科室": _normalize_department(candidate["dept_text"]),
                    "项目号": project,
                    "source_file": build_file2_virtual_source(project),
                    "信息单编号": item_number,
                    "提出日期": candidate["submit_date"].strftime("%Y.%m.%d"),
                    "回文期限": candidate["due_date"].strftime("%Y.%m.%d"),
                    "回文日期": "",
                    "对方文号": _clean(row.get("REF_ITEM_NUMBER")),
                }
            )

        if rows:
            out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号", "信息单编号"]).reset_index(drop=True)
            out["原始行号"] = out.index + 2
            frames[project] = out[RESULT_COLUMNS]
        else:
            frames[project] = pd.DataFrame(columns=RESULT_COLUMNS)

    _FILE2_WARM_CACHE[cache_key] = frames
    return {project: frame.copy() for project, frame in frames.items()}


def fetch_file2_db_dataframe(project_id: str, current_datetime: datetime.datetime, provider=None) -> pd.DataFrame:
    project = str(project_id or "").strip()
    if not project:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return _fetch_file2_live_dataframe(project, current_datetime, provider)
    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    cached = _FILE2_WARM_CACHE.get(cache_key)
    if cached is not None and project in cached:
        return cached[project].copy()
    user_map = provider.get_user_map()

    int_path = provider.get_table_path("INTINTERFACEDOC")
    if not int_path:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    int_columns = parse_create_columns(int_path)
    project_tokens = [f"N'{project}'", f"'{project}'"]

    reply_by_ref: Dict[str, Dict[str, Any]] = {}
    candidates: List[Dict[str, Any]] = []
    candidate_source_ids: Set[str] = set()
    direct_related_ids: Set[str] = set()

    for row in iter_filtered_insert_dicts(int_path, int_columns, project_tokens):
        if not _is_current(row):
            continue

        ref_item = _clean(row.get("REF_ITEM_NUMBER"))
        if ref_item:
            prev = reply_by_ref.get(ref_item)
            if prev is None or _sort_key(row) >= _sort_key(prev):
                reply_by_ref[ref_item] = row

        if _clean(row.get("PROJ_NUM")) != project:
            continue

        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue

        dept_text = _pick_first_non_empty(row.get("PROPOSED_DEPT"), row.get("RECEIVE_DEPT"), row.get("RELEASE_PARTY"))
        if not _matches_internal_dept(dept_text):
            continue

        submit_date = _parse_dt(row.get("SUBMIT_DATE"))
        if submit_date is None:
            continue

        due_date = submit_date + datetime.timedelta(days=14)
        if not _in_file2_window(due_date, current_datetime, project):
            continue

        source_id = _clean(row.get("ID")).upper()
        if source_id:
            candidate_source_ids.add(source_id)
        direct_related_id = _clean(row.get("IDIACP1000")).upper()
        if direct_related_id:
            direct_related_ids.add(direct_related_id)

        candidates.append(
            {
                "row": row,
                "item_number": item_number,
                "dept_text": dept_text,
                "submit_date": submit_date,
                "due_date": due_date,
                "source_id": source_id,
                "direct_related_id": direct_related_id,
            }
        )

    if not candidates:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    link_map: Dict[str, List[str]] = {}
    bridge_path = provider.get_table_path("INTINTERFACEDOCIDIACP1000")
    if bridge_path and candidate_source_ids:
        bridge_columns = parse_create_columns(bridge_path)
        for row in iter_filtered_insert_dicts(bridge_path, bridge_columns, list(candidate_source_ids)):
            if not _is_current(row):
                continue
            source_id = _clean(row.get("SOURCE_ID")).upper()
            related_id = _clean(row.get("RELATED_ID")).upper()
            if source_id and related_id and source_id in candidate_source_ids:
                link_map.setdefault(source_id, []).append(related_id)

    related_ids: Set[str] = set(direct_related_ids)
    for values in link_map.values():
        related_ids.update(value for value in values if value)

    idi_by_id: Dict[str, str] = {}
    idi_path = provider.get_table_path("IDIACP1000")
    if idi_path and related_ids:
        idi_columns = parse_create_columns(idi_path)
        for row in iter_insert_dicts_by_first_id(idi_path, idi_columns, list(related_ids)):
            if not _is_current(row):
                continue
            row_id = _clean(row.get("ID")).upper()
            if row_id not in related_ids:
                continue
            item_number = _clean(row.get("ITEM_NUMBER"))
            if item_number:
                idi_by_id[row_id] = item_number

    rows: List[Dict[str, Any]] = []
    for candidate in candidates:
        item_number = candidate["item_number"]
        reply_row = reply_by_ref.get(item_number)
        reply_release = _parse_dt(reply_row.get("RELEASE_DATE")) if reply_row else None
        if reply_release is not None:
            continue

        row = candidate["row"]
        interface_id = ""
        if candidate["direct_related_id"]:
            interface_id = idi_by_id.get(candidate["direct_related_id"], "")
        if not interface_id:
            for related_id in link_map.get(candidate["source_id"], []):
                interface_id = idi_by_id.get(related_id, "")
                if interface_id:
                    break
        if not interface_id:
            interface_id = _clean(row.get("REF_ITEM_NUMBER"))
        if not interface_id:
            continue

        owner_name = (
            resolve_user_name(row.get("MODIFIED_BY_ID"), user_map)
            or resolve_user_name(row.get("CREATED_BY_ID"), user_map)
            or "无"
        )

        rows.append(
            {
                "接口号": interface_id,
                "接口时间": candidate["due_date"].strftime("%Y.%m.%d"),
                "责任人": owner_name,
                "科室": _normalize_department(candidate["dept_text"]),
                "项目号": project,
                "source_file": build_file2_virtual_source(project),
                "信息单编号": item_number,
                "提出日期": candidate["submit_date"].strftime("%Y.%m.%d"),
                "回文期限": candidate["due_date"].strftime("%Y.%m.%d"),
                "回文日期": "",
                "对方文号": _clean(row.get("REF_ITEM_NUMBER")),
            }
        )

    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号", "信息单编号"]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    return out[RESULT_COLUMNS]


def _fetch_file2_live_dataframe(project: str, current_datetime: datetime.datetime, provider) -> pd.DataFrame:
    user_map = provider.get_user_map()
    debug: Dict[str, Any] = {
        "backend": provider.source_label(),
        "project_id": project,
        "query_date": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "int_rows_total": 0,
        "reply_ref_rows": 0,
        "item_number_rows": 0,
        "dept_match_rows": 0,
        "submit_date_rows": 0,
        "due_window_rows": 0,
        "candidate_rows": 0,
        "candidate_source_ids": 0,
        "direct_related_ids": 0,
        "bridge_rows": 0,
        "bridge_source_hits": 0,
        "related_ids": 0,
        "idi_rows": 0,
        "idi_hits": 0,
        "reply_closed_skipped": 0,
        "missing_interface_id_skipped": 0,
        "final_rows": 0,
    }
    sql_template = """
SELECT
    [ID],
    [ITEM_NUMBER],
    [REF_ITEM_NUMBER],
    [PROPOSED_DEPT],
    [RECEIVE_DEPT],
    [RELEASE_PARTY],
    [SUBMIT_DATE],
    [RELEASE_DATE],
    [IDIACP1000],
    [MODIFIED_BY_ID],
    [CREATED_BY_ID],
    [MODIFIED_ON],
    [PROJ_NUM],
    [IS_CURRENT]
FROM [{schema}].[INTINTERFACEDOC]
WHERE [PROJ_NUM] = ?
  AND ([IS_CURRENT] = ? OR [IS_CURRENT] = 1 OR [IS_CURRENT] IS NULL)
"""
    int_rows = provider.fetch_rows(sql_template, params=(project, "1"))
    debug["int_rows_total"] = len(int_rows)

    reply_by_ref: Dict[str, Dict[str, Any]] = {}
    candidates: List[Dict[str, Any]] = []
    candidate_source_ids: Set[str] = set()
    direct_related_ids: Set[str] = set()

    for row in int_rows:
        ref_item = _clean(row.get("REF_ITEM_NUMBER"))
        if ref_item:
            debug["reply_ref_rows"] += 1
            prev = reply_by_ref.get(ref_item)
            if prev is None or _sort_key(row) >= _sort_key(prev):
                reply_by_ref[ref_item] = row

        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue
        debug["item_number_rows"] += 1

        dept_text = _pick_first_non_empty(row.get("PROPOSED_DEPT"), row.get("RECEIVE_DEPT"), row.get("RELEASE_PARTY"))
        if not _matches_internal_dept(dept_text):
            continue
        debug["dept_match_rows"] += 1

        submit_date = _parse_dt(row.get("SUBMIT_DATE"))
        if submit_date is None:
            continue
        debug["submit_date_rows"] += 1

        due_date = submit_date + datetime.timedelta(days=14)
        if not _in_file2_window(due_date, current_datetime, project):
            continue
        debug["due_window_rows"] += 1

        source_id = _clean(row.get("ID")).upper()
        if source_id:
            candidate_source_ids.add(source_id)
        direct_related_id = _clean(row.get("IDIACP1000")).upper()
        if direct_related_id:
            direct_related_ids.add(direct_related_id)

        candidates.append(
            {
                "row": row,
                "item_number": item_number,
                "dept_text": dept_text,
                "submit_date": submit_date,
                "due_date": due_date,
                "source_id": source_id,
                "direct_related_id": direct_related_id,
            }
        )
    debug["candidate_rows"] = len(candidates)
    debug["candidate_source_ids"] = len(candidate_source_ids)
    debug["direct_related_ids"] = len(direct_related_ids)

    link_map: Dict[str, List[str]] = {}
    if candidate_source_ids:
        bridge_sql = """
SELECT [SOURCE_ID], [RELATED_ID], [IS_CURRENT]
FROM [{schema}].[INTINTERFACEDOCIDIACP1000]
WHERE [SOURCE_ID] IN ({placeholders})
"""
        bridge_rows = provider.fetch_rows(
            bridge_sql.format(placeholders=_build_in_placeholders(candidate_source_ids)),
            params=tuple(candidate_source_ids),
        )
        debug["bridge_rows"] = len(bridge_rows)
        for row in bridge_rows:
            if not _is_current(row):
                continue
            source_id = _clean(row.get("SOURCE_ID")).upper()
            related_id = _clean(row.get("RELATED_ID")).upper()
            if source_id and related_id and source_id in candidate_source_ids:
                link_map.setdefault(source_id, []).append(related_id)
        debug["bridge_source_hits"] = len(link_map)

    related_ids: Set[str] = set(direct_related_ids)
    for values in link_map.values():
        related_ids.update(value for value in values if value)
    debug["related_ids"] = len(related_ids)

    idi_by_id: Dict[str, str] = {}
    if related_ids:
        idi_sql = """
SELECT [ID], [ITEM_NUMBER], [IS_CURRENT]
FROM [{schema}].[IDIACP1000]
WHERE [ID] IN ({placeholders})
"""
        idi_rows = provider.fetch_rows(
            idi_sql.format(placeholders=_build_in_placeholders(related_ids)),
            params=tuple(related_ids),
        )
        debug["idi_rows"] = len(idi_rows)
        for row in idi_rows:
            if not _is_current(row):
                continue
            row_id = _clean(row.get("ID")).upper()
            if row_id not in related_ids:
                continue
            item_number = _clean(row.get("ITEM_NUMBER"))
            if item_number:
                idi_by_id[row_id] = item_number
        debug["idi_hits"] = len(idi_by_id)

    rows: List[Dict[str, Any]] = []
    for candidate in candidates:
        item_number = candidate["item_number"]
        reply_row = reply_by_ref.get(item_number)
        reply_release = _parse_dt(reply_row.get("RELEASE_DATE")) if reply_row else None
        if reply_release is not None:
            debug["reply_closed_skipped"] += 1
            continue

        row = candidate["row"]
        interface_id = ""
        if candidate["direct_related_id"]:
            interface_id = idi_by_id.get(candidate["direct_related_id"], "")
        if not interface_id:
            for related_id in link_map.get(candidate["source_id"], []):
                interface_id = idi_by_id.get(related_id, "")
                if interface_id:
                    break
        if not interface_id:
            interface_id = _clean(row.get("REF_ITEM_NUMBER"))
        if not interface_id:
            debug["missing_interface_id_skipped"] += 1
            continue

        owner_name = (
            resolve_user_name(row.get("MODIFIED_BY_ID"), user_map)
            or resolve_user_name(row.get("CREATED_BY_ID"), user_map)
            or "无"
        )

        rows.append(
            {
                "接口号": interface_id,
                "接口时间": candidate["due_date"].strftime("%Y.%m.%d"),
                "责任人": owner_name,
                "科室": _normalize_department(candidate["dept_text"]),
                "项目号": project,
                "source_file": build_file2_virtual_source(project),
                "信息单编号": item_number,
                "提出日期": candidate["submit_date"].strftime("%Y.%m.%d"),
                "回文期限": candidate["due_date"].strftime("%Y.%m.%d"),
                "回文日期": "",
                "对方文号": _clean(row.get("REF_ITEM_NUMBER")),
            }
        )
    debug["final_rows"] = len(rows)
    debug["sample_interface_ids"] = [str(item.get("接口号", "")) for item in rows[:5]]
    _FILE2_DEBUG_SNAPSHOTS[project] = debug

    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号", "信息单编号"]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    return out[RESULT_COLUMNS]


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"", "none", "null", "nan", "nat"}:
        return ""
    return text


def _pick_first_non_empty(*values: Any) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _build_in_placeholders(values: Set[str]) -> str:
    return ", ".join("?" for _ in values)


def _is_current(row: Dict[str, Any]) -> bool:
    return _clean(row.get("IS_CURRENT")).upper() in {"", "1", "Y", "TRUE", "T"}


def _parse_dt(value: Any) -> Optional[datetime.datetime]:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime() if hasattr(parsed, "to_pydatetime") else parsed


def _sort_key(row: Dict[str, Any]) -> tuple:
    return (
        _parse_dt(row.get("RELEASE_DATE")) or datetime.datetime.min,
        _parse_dt(row.get("MODIFIED_ON")) or datetime.datetime.min,
        _clean(row.get("ITEM_NUMBER")),
    )


def _matches_internal_dept(value: Any) -> bool:
    text = _clean(value)
    if not text:
        return False
    return get_organization_filter() in text or contains_department_code(text)


def _normalize_department(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "请室主任确认"
    matched = match_department_name(text)
    return matched if matched and matched != text else "请室主任确认"


def _in_file2_window(target_date: datetime.datetime, current_datetime: datetime.datetime, project_id: str) -> bool:
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
    adjusted = adjust_date_for_project(target_date, project_id)
    return start_date <= adjusted <= end_date
