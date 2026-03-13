#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""File4 SQL-backed data source."""

from __future__ import annotations

import copy
import datetime
import re
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set, Tuple

import pandas as pd

from core.sql.offline_dump_utils import iter_filtered_insert_dicts, iter_insert_dicts_by_first_id
from core.sql.provider import get_active_provider, resolve_user_name
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import parse_create_columns
from utils.adjust import adjust_date_for_project
from utils.dept_config import get_organization_filter, match_department_name


FILE4_DB_SOURCE_PREFIX = "db://file4/"

RESULT_COLUMNS = [
    "接口号",
    "接口时间",
    "责任人",
    "科室",
    "项目号",
    "原始行号",
    "source_file",
    "对象类型",
    "接口时间F",
    "回文期限S",
    "回文日期V",
    "处理方P",
]

_FILE4_WARM_CACHE: Dict[Tuple[str, str], Dict[str, pd.DataFrame]] = {}
_FILE4_DEBUG_SNAPSHOTS: Dict[str, Dict[str, Any]] = {}

ROUTE_RE = re.compile(r"/(IITF|IICS)-(.+?)--", re.IGNORECASE)
NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
TAIL_DIGITS_RE = re.compile(r"\d+$")


def build_file4_virtual_source(project_id: str) -> str:
    return f"{FILE4_DB_SOURCE_PREFIX}{str(project_id or '').strip()}"


def is_file4_db_virtual_source(path: str) -> bool:
    return str(path or "").strip().lower().startswith(FILE4_DB_SOURCE_PREFIX)


def extract_project_id_from_virtual_source(path: str) -> str:
    text = str(path or "").strip()
    if not is_file4_db_virtual_source(text):
        return ""
    return text[len(FILE4_DB_SOURCE_PREFIX) :].strip()


def get_file4_debug_snapshots() -> Dict[str, Dict[str, Any]]:
    return copy.deepcopy(_FILE4_DEBUG_SNAPSHOTS)


def prime_file4_db_cache(project_ids, current_datetime: datetime.datetime, provider=None) -> Dict[str, pd.DataFrame]:
    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return {}
    projects = sorted({str(item or "").strip() for item in (project_ids or []) if str(item or "").strip()})
    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    if not projects:
        _FILE4_WARM_CACHE[cache_key] = {}
        return {}

    project_set = set(projects)
    user_map = provider.get_user_map()
    org_filter = get_organization_filter()

    iics_by_project = _collect_branch_rows_multi(provider, "IICS", project_set, current_datetime, org_filter)
    iitf_by_project = _collect_branch_rows_multi(provider, "IITF", project_set, current_datetime, org_filter)

    selected_by_project: Dict[str, Dict[str, Dict[str, Any]]] = {}
    all_send_ids: Set[str] = set()
    for project in projects:
        selected: Dict[str, Dict[str, Any]] = {}
        for send_id, row in iitf_by_project.get(project, {}).items():
            selected[send_id] = row
        for send_id, row in iics_by_project.get(project, {}).items():
            selected[send_id] = row
        selected_by_project[project] = selected
        all_send_ids.update(selected.keys())

    send_rows = _collect_send_rows(provider, all_send_ids)
    direct_map_by_project, route_map_by_project = _load_distribution_maps_multi(provider, project_set, selected_by_project, user_map)

    frames: Dict[str, pd.DataFrame] = {}
    for project in projects:
        rows: List[Dict[str, Any]] = []
        for send_id, branch in selected_by_project.get(project, {}).items():
            send = send_rows.get(send_id)
            if not send:
                continue
            if _parse_dt(send.get("ANSWER_DATE")) is not None:
                continue

            interface_id = _clean(send.get("LETTER_SEND_NO")) or _clean(send.get("CORRESP_LETTER_REC_NO"))
            if not interface_id:
                continue

            branch_type = _clean(branch.get("_BRANCH_TYPE"))
            org_value = _clean(branch.get("_ORG_VALUE"))
            p_value = _clean(branch.get("_P_VALUE"))
            f_date = _parse_dt(branch.get("MODIFIED_ON"))
            if f_date is None:
                continue
            due_date = f_date + datetime.timedelta(days=20)

            owner_name = (
                _resolve_owner(
                    branch,
                    direct_map_by_project.get(project, {}),
                    route_map_by_project.get(project, {}),
                    user_map,
                )
                or resolve_user_name(branch.get("CREATED_BY_ID"), user_map)
                or "无"
            )
            dept_name = _normalize_department(org_value)

            rows.append(
                {
                    "接口号": interface_id,
                    "接口时间": due_date.strftime("%Y.%m.%d"),
                    "责任人": owner_name,
                    "科室": dept_name,
                    "项目号": project,
                    "source_file": build_file4_virtual_source(project),
                    "对象类型": branch_type,
                    "接口时间F": f_date.strftime("%Y.%m.%d"),
                    "回文期限S": due_date.strftime("%Y.%m.%d"),
                    "回文日期V": "",
                    "处理方P": p_value,
                }
            )

        if rows:
            out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号"]).reset_index(drop=True)
            out["原始行号"] = out.index + 2
            frames[project] = out[RESULT_COLUMNS]
        else:
            frames[project] = pd.DataFrame(columns=RESULT_COLUMNS)

    _FILE4_WARM_CACHE[cache_key] = frames
    return {project: frame.copy() for project, frame in frames.items()}


def fetch_file4_db_dataframe(project_id: str, current_datetime: datetime.datetime, provider=None) -> pd.DataFrame:
    project = str(project_id or "").strip()
    if not project:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    provider = provider or get_active_provider()
    if getattr(provider, "is_live", lambda: False)():
        return _fetch_file4_live_dataframe(project, current_datetime, provider)
    cache_key = (provider.source_label(), current_datetime.strftime("%Y-%m-%d"))
    cached = _FILE4_WARM_CACHE.get(cache_key)
    if cached is not None and project in cached:
        return cached[project].copy()
    user_map = provider.get_user_map()
    org_filter = get_organization_filter()

    iics_by_send = _collect_branch_rows(provider, "IICS", project, current_datetime, org_filter)
    iitf_by_send = _collect_branch_rows(provider, "IITF", project, current_datetime, org_filter)

    selected_by_send: Dict[str, Dict[str, Any]] = {}
    for send_id, row in iitf_by_send.items():
        selected_by_send[send_id] = row
    for send_id, row in iics_by_send.items():
        selected_by_send[send_id] = row
    if not selected_by_send:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    send_rows = _collect_send_rows(provider, set(selected_by_send.keys()))
    if not send_rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)

    direct_map, route_map = _load_distribution_maps(provider, project, selected_by_send, user_map)

    rows: List[Dict[str, Any]] = []
    for send_id, branch in selected_by_send.items():
        send = send_rows.get(send_id)
        if not send:
            continue
        if _parse_dt(send.get("ANSWER_DATE")) is not None:
            continue

        interface_id = _clean(send.get("LETTER_SEND_NO")) or _clean(send.get("CORRESP_LETTER_REC_NO"))
        if not interface_id:
            continue

        branch_type = _clean(branch.get("_BRANCH_TYPE"))
        org_value = _clean(branch.get("_ORG_VALUE"))
        p_value = _clean(branch.get("_P_VALUE"))
        f_date = _parse_dt(branch.get("MODIFIED_ON"))
        if f_date is None:
            continue
        due_date = f_date + datetime.timedelta(days=20)

        owner_name = _resolve_owner(branch, direct_map, route_map, user_map) or resolve_user_name(branch.get("CREATED_BY_ID"), user_map) or "无"
        dept_name = _normalize_department(org_value)

        rows.append(
            {
                "接口号": interface_id,
                "接口时间": due_date.strftime("%Y.%m.%d"),
                "责任人": owner_name,
                "科室": dept_name,
                "项目号": project,
                "source_file": build_file4_virtual_source(project),
                "对象类型": branch_type,
                "接口时间F": f_date.strftime("%Y.%m.%d"),
                "回文期限S": due_date.strftime("%Y.%m.%d"),
                "回文日期V": "",
                "处理方P": p_value,
            }
        )

    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号"]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    return out[RESULT_COLUMNS]


def _fetch_file4_live_dataframe(project: str, current_datetime: datetime.datetime, provider) -> pd.DataFrame:
    user_map = provider.get_user_map()
    org_filter = get_organization_filter()
    debug: Dict[str, Any] = {
        "backend": provider.source_label(),
        "project_id": project,
        "query_date": current_datetime.strftime("%Y-%m-%d %H:%M:%S"),
        "iics_query_rows": 0,
        "iics_selected_rows": 0,
        "iitf_query_rows": 0,
        "iitf_selected_rows": 0,
        "selected_send_rows": 0,
        "send_rows": 0,
        "distribution_query_rows": 0,
        "distribution_direct_groups": 0,
        "distribution_route_groups": 0,
        "answered_skipped": 0,
        "missing_interface_id_skipped": 0,
        "missing_f_date_skipped": 0,
        "final_rows": 0,
    }

    iics_by_send = _collect_branch_rows_live(provider, "IICS", project, current_datetime, org_filter, debug)
    iitf_by_send = _collect_branch_rows_live(provider, "IITF", project, current_datetime, org_filter, debug)

    selected_by_send: Dict[str, Dict[str, Any]] = {}
    for send_id, row in iitf_by_send.items():
        selected_by_send[send_id] = row
    for send_id, row in iics_by_send.items():
        selected_by_send[send_id] = row
    debug["selected_send_rows"] = len(selected_by_send)
    if not selected_by_send:
        _FILE4_DEBUG_SNAPSHOTS[project] = debug
        return pd.DataFrame(columns=RESULT_COLUMNS)

    send_rows = _collect_send_rows_live(provider, set(selected_by_send.keys()))
    debug["send_rows"] = len(send_rows)
    if not send_rows:
        _FILE4_DEBUG_SNAPSHOTS[project] = debug
        return pd.DataFrame(columns=RESULT_COLUMNS)

    direct_map, route_map = _load_distribution_maps_live(provider, project, selected_by_send, user_map, debug)

    rows: List[Dict[str, Any]] = []
    for send_id, branch in selected_by_send.items():
        send = send_rows.get(send_id)
        if not send:
            continue
        if _parse_dt(send.get("ANSWER_DATE")) is not None:
            debug["answered_skipped"] += 1
            continue

        interface_id = _clean(send.get("LETTER_SEND_NO")) or _clean(send.get("CORRESP_LETTER_REC_NO"))
        if not interface_id:
            debug["missing_interface_id_skipped"] += 1
            continue

        branch_type = _clean(branch.get("_BRANCH_TYPE"))
        org_value = _clean(branch.get("_ORG_VALUE"))
        p_value = _clean(branch.get("_P_VALUE"))
        f_date = _parse_dt(branch.get("MODIFIED_ON"))
        if f_date is None:
            debug["missing_f_date_skipped"] += 1
            continue
        due_date = f_date + datetime.timedelta(days=20)

        owner_name = _resolve_owner(branch, direct_map, route_map, user_map) or resolve_user_name(branch.get("CREATED_BY_ID"), user_map) or "无"
        dept_name = _normalize_department(org_value)

        rows.append(
            {
                "接口号": interface_id,
                "接口时间": due_date.strftime("%Y.%m.%d"),
                "责任人": owner_name,
                "科室": dept_name,
                "项目号": project,
                "source_file": build_file4_virtual_source(project),
                "对象类型": branch_type,
                "接口时间F": f_date.strftime("%Y.%m.%d"),
                "回文期限S": due_date.strftime("%Y.%m.%d"),
                "回文日期V": "",
                "处理方P": p_value,
            }
        )

    debug["final_rows"] = len(rows)
    debug["sample_interface_ids"] = [str(item.get("接口号", "")) for item in rows[:5]]
    _FILE4_DEBUG_SNAPSHOTS[project] = debug
    if not rows:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    out = pd.DataFrame(rows).sort_values(by=["接口时间", "接口号"]).reset_index(drop=True)
    out["原始行号"] = out.index + 2
    return out[RESULT_COLUMNS]


def _collect_branch_rows(provider, table_name: str, project: str, current_datetime: datetime.datetime, org_filter: str) -> Dict[str, Dict[str, Any]]:
    path = provider.get_table_path(table_name)
    if not path:
        return {}
    columns = parse_create_columns(path)
    project_tokens = [f"N'{project}'", f"'{project}'"]
    result: Dict[str, Dict[str, Any]] = {}

    for row in iter_filtered_insert_dicts(path, columns, project_tokens):
        if not _is_current(row):
            continue
        if _clean(row.get("PROJ_NUM")) != project:
            continue

        send_id = _clean(row.get("SEND_RECEIVE_DATA")).upper()
        if not send_id:
            continue

        if table_name == "IICS":
            p_value = _clean(row.get("RELEASE_PARTY"))
            org_value = _select_org_value(org_filter, row.get("RECEIVE_PARTY"), row.get("RELEASE_PARTY"))
        else:
            p_value = _clean(row.get("RECEIVE_PARTY"))
            org_value = _select_org_value(org_filter, row.get("RELEASE_PARTY"), row.get("RECEIVE_PARTY"))
        if p_value != "B":
            continue

        f_date = _parse_dt(row.get("MODIFIED_ON"))
        if f_date is None:
            continue
        due_date = f_date + datetime.timedelta(days=20)
        if not _in_time_window(due_date, current_datetime, project):
            continue

        candidate = dict(row)
        candidate["_BRANCH_TYPE"] = table_name
        candidate["_ORG_VALUE"] = org_value
        candidate["_P_VALUE"] = p_value
        prev = result.get(send_id)
        if prev is None or _branch_sort_key(candidate) >= _branch_sort_key(prev):
            result[send_id] = candidate
    return result


def _collect_branch_rows_live(provider, table_name: str, project: str, current_datetime: datetime.datetime, org_filter: str, debug: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    sql_template = f"""
SELECT
    [ID],
    [ITEM_NUMBER],
    [INTERFACE_INFO],
    [SEND_RECEIVE_DATA],
    [RELEASE_PARTY],
    [RECEIVE_PARTY],
    [MODIFIED_ON],
    [RELEASE_DATE],
    [CREATED_BY_ID],
    [PROJ_NUM],
    [IS_CURRENT]
FROM [{{schema}}].[{table_name}]
WHERE [PROJ_NUM] = ?
  AND ([IS_CURRENT] = ? OR [IS_CURRENT] = 1 OR [IS_CURRENT] IS NULL)
"""
    live_rows = provider.fetch_rows(sql_template, params=(project, "1"))
    if debug is not None:
        debug[f"{table_name.lower()}_query_rows"] = len(live_rows)
    result: Dict[str, Dict[str, Any]] = {}
    for row in live_rows:
        send_id = _clean(row.get("SEND_RECEIVE_DATA")).upper()
        if not send_id:
            continue

        if table_name == "IICS":
            p_value = _clean(row.get("RELEASE_PARTY"))
            org_value = _select_org_value(org_filter, row.get("RECEIVE_PARTY"), row.get("RELEASE_PARTY"))
        else:
            p_value = _clean(row.get("RECEIVE_PARTY"))
            org_value = _select_org_value(org_filter, row.get("RELEASE_PARTY"), row.get("RECEIVE_PARTY"))
        if p_value != "B":
            continue

        f_date = _parse_dt(row.get("MODIFIED_ON"))
        if f_date is None:
            continue
        due_date = f_date + datetime.timedelta(days=20)
        if not _in_time_window(due_date, current_datetime, project):
            continue

        candidate = dict(row)
        candidate["_BRANCH_TYPE"] = table_name
        candidate["_ORG_VALUE"] = org_value
        candidate["_P_VALUE"] = p_value
        prev = result.get(send_id)
        if prev is None or _branch_sort_key(candidate) >= _branch_sort_key(prev):
            result[send_id] = candidate
    if debug is not None:
        debug[f"{table_name.lower()}_selected_rows"] = len(result)
    return result


def _collect_branch_rows_multi(
    provider,
    table_name: str,
    projects: Set[str],
    current_datetime: datetime.datetime,
    org_filter: str,
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    path = provider.get_table_path(table_name)
    if not path or not projects:
        return {}
    columns = parse_create_columns(path)
    project_tokens: List[str] = []
    for project in sorted(projects):
        project_tokens.extend([f"N'{project}'", f"'{project}'"])

    result: Dict[str, Dict[str, Dict[str, Any]]] = {project: {} for project in projects}
    for row in iter_filtered_insert_dicts(path, columns, project_tokens):
        if not _is_current(row):
            continue
        project = _clean(row.get("PROJ_NUM"))
        if project not in projects:
            continue

        send_id = _clean(row.get("SEND_RECEIVE_DATA")).upper()
        if not send_id:
            continue

        if table_name == "IICS":
            p_value = _clean(row.get("RELEASE_PARTY"))
            org_value = _select_org_value(org_filter, row.get("RECEIVE_PARTY"), row.get("RELEASE_PARTY"))
        else:
            p_value = _clean(row.get("RECEIVE_PARTY"))
            org_value = _select_org_value(org_filter, row.get("RELEASE_PARTY"), row.get("RECEIVE_PARTY"))
        if p_value != "B":
            continue

        f_date = _parse_dt(row.get("MODIFIED_ON"))
        if f_date is None:
            continue
        due_date = f_date + datetime.timedelta(days=20)
        if not _in_time_window(due_date, current_datetime, project):
            continue

        candidate = dict(row)
        candidate["_BRANCH_TYPE"] = table_name
        candidate["_ORG_VALUE"] = org_value
        candidate["_P_VALUE"] = p_value
        prev = result[project].get(send_id)
        if prev is None or _branch_sort_key(candidate) >= _branch_sort_key(prev):
            result[project][send_id] = candidate
    return result


def _collect_send_rows(provider, send_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    if not send_ids:
        return {}
    path = provider.get_table_path("SENDRECEIVEDATA")
    if not path:
        return {}
    columns = parse_create_columns(path)
    result: Dict[str, Dict[str, Any]] = {}
    for row in iter_insert_dicts_by_first_id(path, columns, list(send_ids)):
        if not _is_current(row):
            continue
        row_id = _clean(row.get("ID")).upper()
        if row_id in send_ids:
            result[row_id] = row
    return result


def _collect_send_rows_live(provider, send_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    if not send_ids:
        return {}
    sql_template = """
SELECT [ID], [LETTER_SEND_NO], [CORRESP_LETTER_REC_NO], [ANSWER_DATE], [IS_CURRENT]
FROM [{schema}].[SENDRECEIVEDATA]
WHERE [ID] IN ({placeholders})
"""
    live_rows = provider.fetch_rows(
        sql_template.format(placeholders=", ".join("?" for _ in send_ids)),
        params=tuple(send_ids),
    )
    result: Dict[str, Dict[str, Any]] = {}
    for row in live_rows:
        if not _is_current(row):
            continue
        row_id = _clean(row.get("ID")).upper()
        if row_id in send_ids:
            result[row_id] = row
    return result


def _load_distribution_maps(
    provider,
    project: str,
    selected_by_send: Dict[str, Dict[str, Any]],
    user_map: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]:
    path = provider.get_table_path("DISTRIBUTERECORD")
    if not path:
        return {}, {}
    columns = parse_create_columns(path)
    project_tokens = [f"N'{project}'", f"'{project}'"]

    branch_ids = {_clean(row.get("ID")).upper() for row in selected_by_send.values() if _clean(row.get("ID"))}
    route_keys: Set[Tuple[str, str]] = set()
    for row in selected_by_send.values():
        branch_type = _clean(row.get("_BRANCH_TYPE")).upper()
        route_keys.add((branch_type, _normalize_route(row.get("ITEM_NUMBER"))))
        route_keys.add((branch_type, _normalize_route_tail(row.get("ITEM_NUMBER"))))
        route_keys.add((branch_type, _normalize_route(row.get("INTERFACE_INFO"))))
        route_keys.add((branch_type, _normalize_route_tail(row.get("INTERFACE_INFO"))))
    route_keys.discard(("IICS", ""))
    route_keys.discard(("IITF", ""))

    direct_groups: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {"senders": set(), "ops": []})
    route_groups: DefaultDict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"senders": set(), "ops": []})

    for row in iter_filtered_insert_dicts(path, columns, project_tokens):
        if not _is_current(row):
            continue
        if _clean(row.get("PROJ_NUM")) != project:
            continue

        source_object_id = _clean(row.get("SOURCE_OBJECT_ID")).upper()
        source_type = _normalize_dist_source_type(row.get("SOURCE_TYPE"))
        route_type, route_key = _extract_route_from_bo_title(row.get("BO_TITLE"))
        if route_type:
            source_type = route_type

        sender_tokens = _sender_tokens(row.get("SENDER"), user_map)
        operator = _clean(row.get("OPERATOR"))
        operation_time = _parse_dt(row.get("OPERATION_TIME")) or datetime.datetime.min
        created_on = _parse_dt(row.get("CREATED_ON")) or datetime.datetime.min

        if source_object_id and source_object_id in branch_ids:
            group = direct_groups[source_object_id]
            group["senders"].update(sender_tokens)
            if operator:
                group["ops"].append((operator, operation_time, created_on))

        route_pair = (source_type, route_key)
        if route_pair in route_keys:
            group = route_groups[route_pair]
            group["senders"].update(sender_tokens)
            if operator:
                group["ops"].append((operator, operation_time, created_on))

    return _build_distribution_payload(direct_groups), _build_distribution_payload(route_groups)


def _load_distribution_maps_live(
    provider,
    project: str,
    selected_by_send: Dict[str, Dict[str, Any]],
    user_map: Dict[str, Dict[str, str]],
    debug: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[Tuple[str, str], Dict[str, Any]]]:
    branch_ids = {_clean(row.get("ID")).upper() for row in selected_by_send.values() if _clean(row.get("ID"))}
    route_keys: Set[Tuple[str, str]] = set()
    for row in selected_by_send.values():
        branch_type = _clean(row.get("_BRANCH_TYPE")).upper()
        route_keys.add((branch_type, _normalize_route(row.get("ITEM_NUMBER"))))
        route_keys.add((branch_type, _normalize_route_tail(row.get("ITEM_NUMBER"))))
        route_keys.add((branch_type, _normalize_route(row.get("INTERFACE_INFO"))))
        route_keys.add((branch_type, _normalize_route_tail(row.get("INTERFACE_INFO"))))
    route_keys.discard(("IICS", ""))
    route_keys.discard(("IITF", ""))

    sql_template = """
SELECT
    [SOURCE_OBJECT_ID],
    [SOURCE_TYPE],
    [BO_TITLE],
    [SENDER],
    [OPERATOR],
    [OPERATION_TIME],
    [CREATED_ON],
    [PROJ_NUM],
    [IS_CURRENT]
FROM [{schema}].[DISTRIBUTERECORD]
WHERE [PROJ_NUM] = ?
  AND ([IS_CURRENT] = ? OR [IS_CURRENT] = 1 OR [IS_CURRENT] IS NULL)
"""
    live_rows = provider.fetch_rows(sql_template, params=(project, "1"))
    if debug is not None:
        debug["distribution_query_rows"] = len(live_rows)

    direct_groups: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {"senders": set(), "ops": []})
    route_groups: DefaultDict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"senders": set(), "ops": []})

    for row in live_rows:
        source_object_id = _clean(row.get("SOURCE_OBJECT_ID")).upper()
        source_type = _normalize_dist_source_type(row.get("SOURCE_TYPE"))
        route_type, route_key = _extract_route_from_bo_title(row.get("BO_TITLE"))
        if route_type:
            source_type = route_type

        sender_tokens = _sender_tokens(row.get("SENDER"), user_map)
        operator = _clean(row.get("OPERATOR"))
        operation_time = _parse_dt(row.get("OPERATION_TIME")) or datetime.datetime.min
        created_on = _parse_dt(row.get("CREATED_ON")) or datetime.datetime.min

        if source_object_id and source_object_id in branch_ids:
            group = direct_groups[source_object_id]
            group["senders"].update(sender_tokens)
            if operator:
                group["ops"].append((operator, operation_time, created_on))

        route_pair = (source_type, route_key)
        if route_pair in route_keys:
            group = route_groups[route_pair]
            group["senders"].update(sender_tokens)
            if operator:
                group["ops"].append((operator, operation_time, created_on))

    direct_payload = _build_distribution_payload(direct_groups)
    route_payload = _build_distribution_payload(route_groups)
    if debug is not None:
        debug["distribution_direct_groups"] = len(direct_payload)
        debug["distribution_route_groups"] = len(route_payload)
    return direct_payload, route_payload


def _load_distribution_maps_multi(
    provider,
    projects: Set[str],
    selected_by_project: Dict[str, Dict[str, Dict[str, Any]]],
    user_map: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Dict[Tuple[str, str], Dict[str, Any]]]]:
    path = provider.get_table_path("DISTRIBUTERECORD")
    if not path or not projects:
        return {}, {}
    columns = parse_create_columns(path)
    project_tokens: List[str] = []
    for project in sorted(projects):
        project_tokens.extend([f"N'{project}'", f"'{project}'"])

    branch_ids_by_project: Dict[str, Set[str]] = {}
    route_keys_by_project: Dict[str, Set[Tuple[str, str]]] = {}
    for project in projects:
        selected = selected_by_project.get(project, {})
        branch_ids = {_clean(row.get("ID")).upper() for row in selected.values() if _clean(row.get("ID"))}
        route_keys: Set[Tuple[str, str]] = set()
        for row in selected.values():
            branch_type = _clean(row.get("_BRANCH_TYPE")).upper()
            route_keys.add((branch_type, _normalize_route(row.get("ITEM_NUMBER"))))
            route_keys.add((branch_type, _normalize_route_tail(row.get("ITEM_NUMBER"))))
            route_keys.add((branch_type, _normalize_route(row.get("INTERFACE_INFO"))))
            route_keys.add((branch_type, _normalize_route_tail(row.get("INTERFACE_INFO"))))
        route_keys.discard(("IICS", ""))
        route_keys.discard(("IITF", ""))
        branch_ids_by_project[project] = branch_ids
        route_keys_by_project[project] = route_keys

    direct_groups_by_project: Dict[str, DefaultDict[str, Dict[str, Any]]] = {
        project: defaultdict(lambda: {"senders": set(), "ops": []}) for project in projects
    }
    route_groups_by_project: Dict[str, DefaultDict[Tuple[str, str], Dict[str, Any]]] = {
        project: defaultdict(lambda: {"senders": set(), "ops": []}) for project in projects
    }

    for row in iter_filtered_insert_dicts(path, columns, project_tokens):
        if not _is_current(row):
            continue
        project = _clean(row.get("PROJ_NUM"))
        if project not in projects:
            continue

        source_object_id = _clean(row.get("SOURCE_OBJECT_ID")).upper()
        source_type = _normalize_dist_source_type(row.get("SOURCE_TYPE"))
        route_type, route_key = _extract_route_from_bo_title(row.get("BO_TITLE"))
        if route_type:
            source_type = route_type

        sender_tokens = _sender_tokens(row.get("SENDER"), user_map)
        operator = _clean(row.get("OPERATOR"))
        operation_time = _parse_dt(row.get("OPERATION_TIME")) or datetime.datetime.min
        created_on = _parse_dt(row.get("CREATED_ON")) or datetime.datetime.min

        if source_object_id and source_object_id in branch_ids_by_project.get(project, set()):
            group = direct_groups_by_project[project][source_object_id]
            group["senders"].update(sender_tokens)
            if operator:
                group["ops"].append((operator, operation_time, created_on))

        route_pair = (source_type, route_key)
        if route_pair in route_keys_by_project.get(project, set()):
            group = route_groups_by_project[project][route_pair]
            group["senders"].update(sender_tokens)
            if operator:
                group["ops"].append((operator, operation_time, created_on))

    direct_payload = {project: _build_distribution_payload(groups) for project, groups in direct_groups_by_project.items()}
    route_payload = {project: _build_distribution_payload(groups) for project, groups in route_groups_by_project.items()}
    return direct_payload, route_payload


def _build_distribution_payload(groups):
    payload = {}
    for key, group in groups.items():
        sender_tokens = {str(item).strip() for item in group["senders"] if str(item).strip()}
        leafs: List[str] = []
        latest_operator = ""
        latest_score = (datetime.datetime.min, datetime.datetime.min)
        for operator, operation_time, created_on in group["ops"]:
            if operator in sender_tokens:
                continue
            if operator not in leafs:
                leafs.append(operator)
            if (operation_time, created_on) >= latest_score:
                latest_score = (operation_time, created_on)
                latest_operator = operator
        payload[key] = {"leaf_operators": leafs, "latest_operator": latest_operator}
    return payload


def _resolve_owner(
    branch: Dict[str, Any],
    direct_map: Dict[str, Dict[str, Any]],
    route_map: Dict[Tuple[str, str], Dict[str, Any]],
    user_map: Dict[str, Dict[str, str]],
) -> str:
    source_id = _clean(branch.get("ID")).upper()
    direct = direct_map.get(source_id, {})
    leafs = direct.get("leaf_operators") or []
    if leafs:
        return ",".join(leafs)
    if direct.get("latest_operator"):
        return _clean(direct.get("latest_operator"))

    branch_type = _clean(branch.get("_BRANCH_TYPE")).upper()
    route_candidates = [
        _normalize_route(branch.get("ITEM_NUMBER")),
        _normalize_route_tail(branch.get("ITEM_NUMBER")),
        _normalize_route(branch.get("INTERFACE_INFO")),
        _normalize_route_tail(branch.get("INTERFACE_INFO")),
    ]
    for route in route_candidates:
        if not route:
            continue
        payload = route_map.get((branch_type, route), {})
        leafs = payload.get("leaf_operators") or []
        if leafs:
            return ",".join(leafs)
        if payload.get("latest_operator"):
            return _clean(payload.get("latest_operator"))

    return resolve_user_name(branch.get("CREATED_BY_ID"), user_map)


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


def _branch_sort_key(row: Dict[str, Any]) -> tuple:
    return (
        _parse_dt(row.get("MODIFIED_ON")) or datetime.datetime.min,
        _parse_dt(row.get("RELEASE_DATE")) or datetime.datetime.min,
        _clean(row.get("ITEM_NUMBER")),
    )


def _normalize_department(value: Any) -> str:
    text = _clean(value)
    if not text:
        return "请室主任确认"
    matched = match_department_name(text)
    return matched if matched and matched != text else "请室主任确认"


def _select_org_value(org_filter: str, primary: Any, secondary: Any) -> str:
    first = _clean(primary)
    second = _clean(secondary)
    for text in (first, second):
        if org_filter and text.startswith(org_filter):
            return text
    for text in (first, second):
        if text and text != "B":
            return text
    return first or second


def _normalize_route(value: Any) -> str:
    return NON_ALNUM_RE.sub("", _clean(value).upper())


def _normalize_route_tail(value: Any) -> str:
    return TAIL_DIGITS_RE.sub("", _normalize_route(value))


def _extract_route_from_bo_title(bo_title: Any) -> Tuple[str, str]:
    text = _clean(bo_title)
    match = ROUTE_RE.search(text)
    if not match:
        return "", ""
    source_type = match.group(1).upper()
    route = match.group(2).strip()
    parts = route.split("-")
    if len(parts) >= 2 and re.fullmatch(r"[A-Z0-9]{1,3}", parts[-1], re.IGNORECASE):
        route = "-".join(parts[:-1])
    return source_type, _normalize_route(route)


def _normalize_dist_source_type(value: Any) -> str:
    text = _clean(value).upper()
    if "EXTIICS" in text or text.endswith("IICS"):
        return "IICS"
    if "EXTIITF" in text or text.endswith("IITF"):
        return "IITF"
    return text


def _sender_tokens(sender: Any, user_map: Dict[str, Dict[str, str]]) -> List[str]:
    cleaned = _clean(sender)
    if not cleaned:
        return []
    upper = cleaned.upper()
    if len(upper) == 32:
        name = resolve_user_name(upper, user_map)
        return [upper] + ([name] if name else [])
    return [cleaned]


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
