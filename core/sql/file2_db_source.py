#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File2 SQL-backed data source."""

from __future__ import annotations

import copy
import datetime
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from core.sql.offline_dump_utils import iter_filtered_insert_dicts, iter_insert_dicts_by_first_id
from core.sql.provider import get_active_provider, resolve_user_name
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import parse_create_columns
from utils.adjust import adjust_date_for_project
from utils.dept_config import contains_department_code, get_organization_filter, match_department_name


FILE2_DB_SOURCE_PREFIX = "db://file2/"
FILE2_STANDARD_PROJECTS = {"1907", "2016"}

COL_INTERFACE = "\u63a5\u53e3\u53f7"
COL_TIME = "\u63a5\u53e3\u65f6\u95f4"
COL_OWNER = "\u8d23\u4efb\u4eba"
COL_DEPT = "\u79d1\u5ba4"
COL_PROJECT = "\u9879\u76ee\u53f7"
COL_ROW = "\u539f\u59cb\u884c\u53f7"
COL_INFO_NO = "\u4fe1\u606f\u5355\u7f16\u53f7"
COL_SUBMIT = "\u63d0\u51fa\u65e5\u671f"
COL_DUE = "\u56de\u6587\u671f\u9650"
COL_REPLY = "\u56de\u6587\u65e5\u671f"
COL_OTHER_NO = "\u5bf9\u65b9\u6587\u53f7"
UNKNOWN_OWNER = "\u672a\u77e5"
UNKNOWN_DEPT = "\u672a\u8bc6\u522b\u90e8\u95e8"

RESULT_COLUMNS = [
    COL_INTERFACE,
    COL_TIME,
    COL_OWNER,
    COL_DEPT,
    COL_PROJECT,
    COL_ROW,
    "source_file",
    COL_INFO_NO,
    COL_SUBMIT,
    COL_DUE,
    COL_REPLY,
    COL_OTHER_NO,
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
    return text[len(FILE2_DB_SOURCE_PREFIX):].strip()


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

    int_path = provider.get_table_path("INTINTERFACEDOC")
    if not int_path:
        frames = {project: _empty_result_df() for project in projects}
        _FILE2_WARM_CACHE[cache_key] = frames
        return {project: frame.copy() for project, frame in frames.items()}

    entries_by_project, _, _ = _load_offline_entries(provider, set(projects))
    user_map = provider.get_user_map()
    frames: Dict[str, pd.DataFrame] = {}
    for project in projects:
        rows = _build_project_rows(entries_by_project.get(project, []), project, current_datetime, user_map)
        frames[project] = _rows_to_dataframe(rows)

    _FILE2_WARM_CACHE[cache_key] = frames
    return {project: frame.copy() for project, frame in frames.items()}


def fetch_file2_db_dataframe(project_id: str, current_datetime: datetime.datetime, provider=None) -> pd.DataFrame:
    project = str(project_id or "").strip()
    if not project:
        return _empty_result_df()

    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return _fetch_file2_live_dataframe(project, current_datetime, provider)

    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    cached = _FILE2_WARM_CACHE.get(cache_key)
    if cached is not None and project in cached:
        return cached[project].copy()

    entries_by_project, _, _ = _load_offline_entries(provider, {project})
    rows = _build_project_rows(entries_by_project.get(project, []), project, current_datetime, provider.get_user_map())
    return _rows_to_dataframe(rows)


def _fetch_file2_live_dataframe(project: str, current_datetime: datetime.datetime, provider) -> pd.DataFrame:
    user_map = provider.get_user_map()
    debug: Dict[str, Any] = {
        "backend": provider.source_label(),
        "project_id": project,
        "query_date": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "stage": "init",
        "int_rows_total": 0,
        "reply_ref_rows": 0,
        "item_number_rows": 0,
        "all_entry_rows": 0,
        "candidate_source_ids": 0,
        "direct_related_ids": 0,
        "bridge_rows": 0,
        "bridge_source_hits": 0,
        "related_ids": 0,
        "idi_rows": 0,
        "idi_hits": 0,
        "resolved_interface_rows": 0,
        "version_allowed_rows": 0,
        "p1_dept_match_rows": 0,
        "submit_date_rows": 0,
        "p2_due_window_rows": 0,
        "p3_excluded_rows": 0,
        "p4_open_rows": 0,
        "reply_closed_skipped": 0,
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
    [CLOSE_DATE],
    [REV],
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
    debug["stage"] = "load_intinterface"
    try:
        int_rows = provider.fetch_rows(sql_template, params=(project, "1"))
    except Exception as exc:
        debug["error"] = str(exc)
        _FILE2_DEBUG_SNAPSHOTS[project] = debug
        return _empty_result_df()
    debug["int_rows_total"] = len(int_rows)

    entries_by_project, reply_by_ref, id_sets = _collect_entries_from_rows(int_rows, {project}, debug)
    entries = entries_by_project.get(project, [])
    debug["all_entry_rows"] = len(entries)
    debug["candidate_source_ids"] = len(id_sets["source_ids"])
    debug["direct_related_ids"] = len(id_sets["direct_related_ids"])

    debug["stage"] = "load_bridge"
    try:
        link_map = _load_bridge_map_live(provider, id_sets["source_ids"])
    except Exception as exc:
        debug["error"] = str(exc)
        _FILE2_DEBUG_SNAPSHOTS[project] = debug
        return _empty_result_df()
    debug["bridge_rows"] = sum(len(values) for values in link_map.values())
    debug["bridge_source_hits"] = len(link_map)

    related_ids: Set[str] = set(id_sets["direct_related_ids"])
    for values in link_map.values():
        related_ids.update(value for value in values if value)
    debug["related_ids"] = len(related_ids)

    debug["stage"] = "load_idiacp1000"
    try:
        idi_by_id, idi_rows_count = _load_idi_map_live(provider, related_ids)
    except Exception as exc:
        debug["error"] = str(exc)
        _FILE2_DEBUG_SNAPSHOTS[project] = debug
        return _empty_result_df()
    debug["idi_rows"] = idi_rows_count
    debug["idi_hits"] = len(idi_by_id)

    _resolve_entry_links(entries, reply_by_ref, link_map, idi_by_id)
    debug["resolved_interface_rows"] = sum(1 for entry in entries if entry.get("interface_id"))

    version_allowed_entries = _select_file2_highest_version_entries(entries)
    debug["version_allowed_rows"] = len(version_allowed_entries)

    debug["stage"] = "build_rows"
    rows = _build_project_rows(version_allowed_entries, project, current_datetime, user_map, debug=debug)
    debug["final_rows"] = len(rows)
    debug["sample_interface_ids"] = [str(item.get(COL_INTERFACE, "")) for item in rows[:5]]
    _FILE2_DEBUG_SNAPSHOTS[project] = debug
    return _rows_to_dataframe(rows)


def _empty_result_df() -> pd.DataFrame:
    return pd.DataFrame(columns=RESULT_COLUMNS)


def _rows_to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return _empty_result_df()
    out = pd.DataFrame(rows).sort_values(by=[COL_TIME, COL_INTERFACE, COL_INFO_NO]).reset_index(drop=True)
    out[COL_ROW] = out.index + 2
    return out[RESULT_COLUMNS]


def _load_offline_entries(provider, project_set: Set[str]):
    int_path = provider.get_table_path("INTINTERFACEDOC")
    if not int_path:
        return {}, {}, {"source_ids": set(), "direct_related_ids": set()}
    int_columns = parse_create_columns(int_path)
    project_tokens: List[str] = []
    for project in sorted(project_set):
        project_tokens.extend([f"N'{project}'", f"'{project}'"])
    rows = list(iter_filtered_insert_dicts(int_path, int_columns, project_tokens))
    entries_by_project, reply_by_ref, id_sets = _collect_entries_from_rows(rows, project_set)
    link_map = _load_bridge_map_offline(provider, id_sets["source_ids"])
    idi_by_id = _load_idi_map_offline(provider, id_sets["direct_related_ids"], link_map)
    for project in project_set:
        _resolve_entry_links(entries_by_project.get(project, []), reply_by_ref, link_map, idi_by_id)
        entries_by_project[project] = _select_file2_highest_version_entries(entries_by_project.get(project, []))
    return entries_by_project, reply_by_ref, id_sets


def _collect_entries_from_rows(int_rows: List[Dict[str, Any]], allowed_projects: Set[str], debug: Optional[Dict[str, Any]] = None):
    reply_by_ref: Dict[Tuple[str, str], Dict[str, Any]] = {}
    entries_by_project: Dict[str, List[Dict[str, Any]]] = {project: [] for project in allowed_projects}
    source_ids: Set[str] = set()
    direct_related_ids: Set[str] = set()

    for row in int_rows:
        if not _is_current(row):
            continue
        project = _clean(row.get("PROJ_NUM"))
        if allowed_projects and project not in allowed_projects:
            continue

        ref_item = _clean(row.get("REF_ITEM_NUMBER"))
        if ref_item:
            if debug is not None:
                debug["reply_ref_rows"] += 1
            reply_key = (project, ref_item)
            prev = reply_by_ref.get(reply_key)
            if prev is None or _sort_key(row) >= _sort_key(prev):
                reply_by_ref[reply_key] = row

        item_number = _clean(row.get("ITEM_NUMBER"))
        if not item_number:
            continue
        if debug is not None:
            debug["item_number_rows"] += 1

        submit_date = _parse_dt(row.get("SUBMIT_DATE"))
        source_id = _clean(row.get("ID")).upper()
        if source_id:
            source_ids.add(source_id)
        direct_related_id = _clean(row.get("IDIACP1000")).upper()
        if direct_related_id:
            direct_related_ids.add(direct_related_id)

        entries_by_project.setdefault(project, []).append(
            {
                "project_id": project,
                "row": row,
                "item_number": item_number,
                "dept_text": _pick_first_non_empty(row.get("PROPOSED_DEPT"), row.get("RECEIVE_DEPT"), row.get("RELEASE_PARTY")),
                "submit_date": submit_date,
                "due_date": submit_date + datetime.timedelta(days=14) if submit_date is not None else None,
                "source_id": source_id,
                "direct_related_id": direct_related_id,
                "version_rank": _get_file2_version_rank(row.get("REV")),
                "interface_id": "",
                "reply_release": None,
            }
        )
    return entries_by_project, reply_by_ref, {"source_ids": source_ids, "direct_related_ids": direct_related_ids}


def _load_bridge_map_offline(provider, source_ids: Set[str]) -> Dict[str, List[str]]:
    link_map: Dict[str, List[str]] = {}
    if not source_ids:
        return link_map
    bridge_path = provider.get_table_path("INTINTERFACEDOCIDIACP1000")
    if not bridge_path:
        return link_map
    bridge_columns = parse_create_columns(bridge_path)
    for row in iter_filtered_insert_dicts(bridge_path, bridge_columns, list(source_ids)):
        if not _is_current(row):
            continue
        source_id = _clean(row.get("SOURCE_ID")).upper()
        related_id = _clean(row.get("RELATED_ID")).upper()
        if source_id and related_id and source_id in source_ids:
            link_map.setdefault(source_id, []).append(related_id)
    return link_map


def _load_bridge_map_live(provider, source_ids: Set[str]) -> Dict[str, List[str]]:
    link_map: Dict[str, List[str]] = {}
    if not source_ids:
        return link_map
    bridge_sql = """
SELECT [SOURCE_ID], [RELATED_ID], [IS_CURRENT]
FROM [{schema}].[INTINTERFACEDOCIDIACP1000]
WHERE [SOURCE_ID] IN ({placeholders})
"""
    bridge_rows = _fetch_rows_in_chunks(provider, bridge_sql, source_ids)
    for row in bridge_rows:
        if not _is_current(row):
            continue
        source_id = _clean(row.get("SOURCE_ID")).upper()
        related_id = _clean(row.get("RELATED_ID")).upper()
        if source_id and related_id and source_id in source_ids:
            link_map.setdefault(source_id, []).append(related_id)
    return link_map


def _load_idi_map_offline(provider, direct_related_ids: Set[str], link_map: Dict[str, List[str]]) -> Dict[str, str]:
    related_ids: Set[str] = set(direct_related_ids)
    for values in link_map.values():
        related_ids.update(value for value in values if value)
    if not related_ids:
        return {}
    idi_path = provider.get_table_path("IDIACP1000")
    if not idi_path:
        return {}
    idi_columns = parse_create_columns(idi_path)
    idi_by_id: Dict[str, str] = {}
    for row in iter_insert_dicts_by_first_id(idi_path, idi_columns, list(related_ids)):
        if not _is_current(row):
            continue
        row_id = _clean(row.get("ID")).upper()
        if row_id not in related_ids:
            continue
        item_number = _clean(row.get("ITEM_NUMBER"))
        if item_number:
            idi_by_id[row_id] = item_number
    return idi_by_id


def _load_idi_map_live(provider, related_ids: Set[str]) -> Tuple[Dict[str, str], int]:
    if not related_ids:
        return {}, 0
    idi_sql = """
SELECT [ID], [ITEM_NUMBER], [IS_CURRENT]
FROM [{schema}].[IDIACP1000]
WHERE [ID] IN ({placeholders})
"""
    idi_rows = _fetch_rows_in_chunks(provider, idi_sql, related_ids)
    idi_by_id: Dict[str, str] = {}
    for row in idi_rows:
        if not _is_current(row):
            continue
        row_id = _clean(row.get("ID")).upper()
        if row_id not in related_ids:
            continue
        item_number = _clean(row.get("ITEM_NUMBER"))
        if item_number:
            idi_by_id[row_id] = item_number
    return idi_by_id, len(idi_rows)


def _resolve_entry_links(entries: List[Dict[str, Any]], reply_by_ref: Dict[Tuple[str, str], Dict[str, Any]], link_map: Dict[str, List[str]], idi_by_id: Dict[str, str]) -> None:
    for entry in entries:
        entry["interface_id"] = _resolve_file2_interface_id(entry, link_map, idi_by_id)
        reply_row = reply_by_ref.get((entry.get("project_id", ""), entry.get("item_number", "")))
        entry["reply_release"] = _parse_dt(reply_row.get("RELEASE_DATE")) if reply_row else None


def _build_project_rows(entries: List[Dict[str, Any]], project: str, current_datetime: datetime.datetime, user_map: Dict[str, str], debug: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        if not _matches_internal_dept(entry.get("dept_text")):
            continue
        if debug is not None:
            debug["p1_dept_match_rows"] += 1

        if entry.get("submit_date") is None:
            continue
        if debug is not None:
            debug["submit_date_rows"] += 1

        due_date = entry.get("due_date")
        if due_date is None or not _in_file2_window(due_date, current_datetime, project):
            continue
        if debug is not None:
            debug["p2_due_window_rows"] += 1

        if entry.get("reply_release") is not None:
            if debug is not None:
                debug["reply_closed_skipped"] += 1
            continue
        if debug is not None:
            debug["p4_open_rows"] += 1

        if _is_file2_process3_excluded(entry.get("row", {}), project):
            if debug is not None:
                debug["p3_excluded_rows"] += 1
            continue

        rows.append(_build_file2_result_row(entry, project, user_map))
    return rows


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


def _fetch_rows_in_chunks(provider, sql_template: str, values: Set[str], chunk_size: int = 500) -> List[Dict[str, Any]]:
    items = [item for item in values if item]
    if not items:
        return []
    rows: List[Dict[str, Any]] = []
    for start in range(0, len(items), chunk_size):
        chunk = items[start:start + chunk_size]
        chunk_sql = sql_template.replace("{placeholders}", ", ".join("?" for _ in chunk))
        rows.extend(provider.fetch_rows(chunk_sql, params=tuple(chunk)))
    return rows


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
        return UNKNOWN_DEPT
    matched = match_department_name(text)
    return matched if matched and matched != text else UNKNOWN_DEPT


def _get_file2_version_rank(version_value: Any) -> int:
    version_text = _clean(version_value)
    if not version_text:
        return 0
    match = re.search(r"[A-Za-z]", version_text)
    if not match:
        return 0
    return ord(match.group(0).upper()) - ord("A") + 1


def _resolve_file2_interface_id(entry: Dict[str, Any], link_map: Dict[str, List[str]], idi_by_id: Dict[str, str]) -> str:
    direct_related_id = _clean(entry.get("direct_related_id")).upper()
    if direct_related_id:
        interface_id = idi_by_id.get(direct_related_id, "")
        if interface_id:
            return interface_id
    source_id = _clean(entry.get("source_id")).upper()
    for related_id in link_map.get(source_id, []):
        interface_id = idi_by_id.get(related_id, "")
        if interface_id:
            return interface_id
    return ""


def _select_file2_highest_version_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_rank_by_interface: Dict[str, int] = {}
    for entry in entries:
        interface_id = _clean(entry.get("interface_id"))
        if not interface_id:
            continue
        version_rank = int(entry.get("version_rank") or 0)
        current_rank = best_rank_by_interface.get(interface_id)
        if current_rank is None or version_rank > current_rank:
            best_rank_by_interface[interface_id] = version_rank

    kept_entries: List[Dict[str, Any]] = []
    for entry in entries:
        interface_id = _clean(entry.get("interface_id"))
        if not interface_id:
            kept_entries.append(entry)
            continue
        version_rank = int(entry.get("version_rank") or 0)
        if version_rank == best_rank_by_interface.get(interface_id, version_rank):
            kept_entries.append(entry)
    return kept_entries


def _build_file2_result_row(entry: Dict[str, Any], project: str, user_map: Dict[str, str]) -> Dict[str, Any]:
    row = entry.get("row", {})
    owner_name = (
        resolve_user_name(row.get("MODIFIED_BY_ID"), user_map)
        or resolve_user_name(row.get("CREATED_BY_ID"), user_map)
        or UNKNOWN_OWNER
    )
    submit_date = entry.get("submit_date")
    due_date = entry.get("due_date")
    reply_release = entry.get("reply_release")
    return {
        COL_INTERFACE: _clean(entry.get("interface_id")),
        COL_TIME: due_date.strftime("%Y.%m.%d") if due_date else "",
        COL_OWNER: owner_name,
        COL_DEPT: _normalize_department(entry.get("dept_text")),
        COL_PROJECT: project,
        COL_ROW: 0,
        "source_file": build_file2_virtual_source(project),
        COL_INFO_NO: _clean(entry.get("item_number")),
        COL_SUBMIT: submit_date.strftime("%Y.%m.%d") if submit_date else "",
        COL_DUE: due_date.strftime("%Y.%m.%d") if due_date else "",
        COL_REPLY: reply_release.strftime("%Y.%m.%d") if reply_release else "",
        COL_OTHER_NO: _clean(row.get("REF_ITEM_NUMBER")),
    }


def _is_file2_process3_excluded(row: Dict[str, Any], project_id: str) -> bool:
    if str(project_id or "").strip() in FILE2_STANDARD_PROJECTS:
        return False
    close_text = _clean(row.get("CLOSE_DATE"))
    return close_text.startswith("4444")


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
