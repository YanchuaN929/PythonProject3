"""Probe file6 strictly along the Word-described distribution workflow."""

from __future__ import annotations

import os
import sys

if __package__ in {None, ""}:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
    sys.path = [item for item in sys.path if os.path.abspath(item or ".") != _SCRIPT_DIR]
    sys.path.insert(0, _PROJECT_ROOT)

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Sequence, Set, Tuple

import pandas as pd

from scripts.db_tools.sql_explorer.file4_ah_owner_chain_probe import _owner_match
from scripts.db_tools.sql_explorer.file4_dist_route_probe import (
    DIST_COLS,
    DIST_IDX,
    _extract_values_blob,
    _iter_insert_statements,
    _split_sql_values,
)
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import (
    PARENT_FIELD_BY_REPLY,
    PARENT_TABLE_BY_REPLY,
    SEND_SIDE_TABLES,
    _best_id,
    _build_relation_map,
    _classify_key,
    _expand_relation_ids,
    _extract_candidate_keys,
    _filter_highest_version,
    _metric,
    _office_match,
    _org_match,
    _resolve_distribution_entities,
    _version_rank,
    merge_child_scans,
    merge_int_scans,
    parse_department_tree,
    resolve_sql35_table_path,
    scan_child_table,
    scan_filetransmission_route,
    scan_int_table,
    scan_objectreplylink,
    scan_send_table,
)
from scripts.db_tools.sql_explorer.real_distribution_chain_probe import _clean_text, _norm_key, _safe_get
from scripts.db_tools.sql_explorer.roster import load_all_roster_names
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import normalize_hex32, parse_user_map


FILE6_PATTERN = "收发文清单*.xlsx"


def _rate(hit: int, total: int) -> float:
    return round(hit / total, 6) if total else 0.0


def _add_unique(items: List[str], value: Any) -> None:
    text = _clean_text(value)
    if text and text not in items:
        items.append(text)


def load_file6_rows_full(excel_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(excel_dir.glob(FILE6_PATTERN)):
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
        project = ""
        stem = path.stem
        if stem.startswith("收发文清单") and len(stem) >= 8:
            maybe_project = stem[4:8]
            if maybe_project.isdigit():
                project = maybe_project
        for row_no in range(len(df)):
            values = df.iloc[row_no].tolist()
            e_raw = _safe_get(values, 4)
            rows.append(
                {
                    "project": project,
                    "workbook": path.name,
                    "excel_row": row_no + 2,
                    "a_raw": _clean_text(_safe_get(values, 0)),
                    "e_raw": _clean_text(e_raw),
                    "e_key": _norm_key(e_raw),
                    "key_type": _classify_key(e_raw),
                    "h_raw": _clean_text(_safe_get(values, 7)),
                    "i_raw": _safe_get(values, 8),
                    "j_raw": _safe_get(values, 9),
                    "m_raw": _clean_text(_safe_get(values, 12)),
                    "v_raw": _clean_text(_safe_get(values, 21)),
                    "w_raw": _clean_text(_safe_get(values, 22)),
                    "x_raw": _clean_text(_safe_get(values, 23)),
                    "ac_raw": _clean_text(_safe_get(values, 28)),
                    "version_rank": _version_rank(_safe_get(values, 28)),
                }
            )
    return rows


def scan_distribution_word_strict(path: Path, target_ids: Set[str], needed_title_keys: Set[str]) -> Dict[str, Any]:
    groups: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "sender_ids": set(),
            "ops": [],
            "latest": pd.Timestamp.min,
            "source_types": set(),
            "titles": [],
        }
    )
    statement_count = 0
    matched_count = 0
    matched_by_title_count = 0
    title_key_to_group_ids: DefaultDict[str, Set[str]] = defaultdict(set)

    for statement in _iter_insert_statements(path):
        statement_count += 1
        values_blob = _extract_values_blob(statement)
        if not values_blob:
            continue
        row = _split_sql_values(values_blob)
        if len(row) < len(DIST_COLS):
            continue
        if str(row[DIST_IDX["is_current"]] or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue

        source_object_id = normalize_hex32(row[DIST_IDX["source_object_id"]])
        row_id = normalize_hex32(row[DIST_IDX["id"]])
        title_keys = set(_extract_candidate_keys(_safe_get(row, DIST_IDX["bo_title"])))
        title_hits = title_keys & needed_title_keys
        if (not source_object_id or source_object_id not in target_ids) and not title_hits:
            continue

        group_id = source_object_id or row_id or f"ROW_{statement_count}"
        group = groups[group_id]

        sender = normalize_hex32(row[DIST_IDX["sender"]]) or _clean_text(row[DIST_IDX["sender"]])
        operator = _clean_text(row[DIST_IDX["operator"]])
        operator_norm = normalize_hex32(row[DIST_IDX["operator"]]) or operator
        operation_time = pd.to_datetime(str(row[DIST_IDX["operation_time"]] or "").strip(), errors="coerce")
        if operation_time is pd.NaT:
            operation_time = pd.Timestamp.min

        if sender:
            group["sender_ids"].add(sender)
        if operator:
            group["ops"].append((operator, operator_norm, operation_time))
        if operation_time > group["latest"]:
            group["latest"] = operation_time

        source_type = _clean_text(row[DIST_IDX["source_type"]])
        if source_type:
            group["source_types"].add(source_type)
        title = _clean_text(_safe_get(row, DIST_IDX["bo_title"]))
        if title and title not in group["titles"]:
            group["titles"].append(title)
        for key in title_hits:
            title_key_to_group_ids[key].add(group_id)

        matched_count += 1
        if title_hits:
            matched_by_title_count += 1

    leaves_by_group: Dict[str, List[str]] = {}
    latest_leaves_by_group: Dict[str, List[str]] = {}
    leaf_items_by_group: Dict[str, List[Dict[str, Any]]] = {}
    row_latest_time_by_group: Dict[str, str] = {}

    for group_id, payload in groups.items():
        union_leafs: List[str] = []
        latest_leafs: List[str] = []
        leaf_items: List[Dict[str, Any]] = []
        latest = payload["latest"]
        for operator, operator_norm, operation_time in payload["ops"]:
            compare_key = operator_norm or operator
            if compare_key in payload["sender_ids"]:
                continue
            if operator not in union_leafs:
                union_leafs.append(operator)
            leaf_items.append(
                {
                    "operator": operator,
                    "operation_time": operation_time.strftime("%Y-%m-%d %H:%M:%S") if operation_time is not pd.Timestamp.min else "",
                    "operation_ts": operation_time,
                }
            )
            if latest is not pd.Timestamp.min and operation_time == latest and operator not in latest_leafs:
                latest_leafs.append(operator)
        leaves_by_group[group_id] = union_leafs
        latest_leaves_by_group[group_id] = latest_leafs
        leaf_items_by_group[group_id] = leaf_items
        row_latest_time_by_group[group_id] = latest.strftime("%Y-%m-%d %H:%M:%S") if latest is not pd.Timestamp.min else ""

    return {
        "statement_count": statement_count,
        "matched_count": matched_count,
        "matched_by_title_count": matched_by_title_count,
        "group_count": len(groups),
        "leaves_by_group": leaves_by_group,
        "latest_leaves_by_group": latest_leaves_by_group,
        "leaf_items_by_group": leaf_items_by_group,
        "row_latest_time_by_group": row_latest_time_by_group,
        "source_types_by_group": {key: sorted(value["source_types"]) for key, value in groups.items()},
        "titles_by_group": {key: value["titles"] for key, value in groups.items()},
        "title_key_to_group_ids": {key: sorted(value) for key, value in title_key_to_group_ids.items()},
    }


def _row_latest_leafs(group_ids: Sequence[str], dist_scan: Dict[str, Any]) -> List[str]:
    latest_time = pd.Timestamp.min
    latest_leafs: List[str] = []
    for group_id in group_ids:
        for item in dist_scan["leaf_items_by_group"].get(group_id, []):
            operation_ts = item["operation_ts"]
            operator = item["operator"]
            if operation_ts is pd.Timestamp.min:
                continue
            if operation_ts > latest_time:
                latest_time = operation_ts
                latest_leafs = [operator]
            elif operation_ts == latest_time and operator not in latest_leafs:
                latest_leafs.append(operator)
    return latest_leafs


def _by_type_metric(rows: Sequence[Dict[str, Any]], getter) -> Dict[str, Dict[str, Any]]:
    stats: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"row_count": 0, "hit_rows": 0})
    for row in rows:
        doc_type = _clean_text(row.get("a_raw"))
        stats[doc_type]["row_count"] += 1
        if getter(row):
            stats[doc_type]["hit_rows"] += 1
    return {
        doc_type: {
            "row_count": payload["row_count"],
            "hit_rows": payload["hit_rows"],
            "rate": _rate(payload["hit_rows"], payload["row_count"]),
        }
        for doc_type, payload in sorted(stats.items())
    }


def run(
    excel_dir: Path,
    sql35_dir: Path,
    output_path: Path,
    doc_types: Sequence[str] | None = None,
) -> Dict[str, Any]:
    rows = load_file6_rows_full(excel_dir)
    if doc_types:
        wanted_types = {_clean_text(value) for value in doc_types if _clean_text(value)}
        rows = [row for row in rows if _clean_text(row["a_raw"]) in wanted_types]
    version_best = _filter_highest_version(rows)

    department_map = parse_department_tree(resolve_sql35_table_path(sql35_dir, "DEPARTMENT"))
    user_map = parse_user_map(resolve_sql35_table_path(sql35_dir, "USER"), department_map)
    roster_names = load_all_roster_names()

    int_rows = [row for row in rows if row["key_type"] == "int_key" and row["e_key"]]
    send_rows = [row for row in rows if row["key_type"] not in {"empty_key", "int_key"} and row["e_key"]]

    int_needed_keys = {row["e_key"] for row in int_rows}
    int_scan = scan_int_table(resolve_sql35_table_path(sql35_dir, "INTINTERFACEDOC"), int_needed_keys)
    needed_chain_ids = {
        payload.get("chain_id", "")
        for payload in int_scan["by_key"].values()
        if _clean_text(payload.get("chain_id"))
    }
    if needed_chain_ids:
        int_rescan = scan_int_table(resolve_sql35_table_path(sql35_dir, "INTINTERFACEDOC"), set(), needed_chain_ids=needed_chain_ids)
        int_scan = merge_int_scans(int_scan, int_rescan)

    send_scan = scan_send_table(resolve_sql35_table_path(sql35_dir, "SENDRECEIVEDATA"), {row["e_key"] for row in send_rows})

    needed_send_ids: Set[str] = set()
    for mapping_name in ("rec_to_ids", "send_to_ids"):
        for send_ids in send_scan[mapping_name].values():
            needed_send_ids.update(send_ids)

    child_tables: Dict[str, Dict[str, Any]] = {}
    child_item_keys = {row["e_key"] for row in send_rows}
    for table_name in SEND_SIDE_TABLES:
        sql_path = resolve_sql35_table_path(sql35_dir, table_name)
        if not sql_path.exists():
            continue
        child_tables[table_name] = scan_child_table(sql_path, table_name, needed_send_ids, child_item_keys)

    for reply_table, parent_table in PARENT_TABLE_BY_REPLY.items():
        scan = child_tables.get(reply_table)
        if not scan:
            continue
        parent_field = PARENT_FIELD_BY_REPLY.get(reply_table)
        if not parent_field:
            continue
        needed_parent_ids: Set[str] = set()
        for payload in scan["by_id"].values():
            rel_id = normalize_hex32(payload.get(parent_field))
            if rel_id:
                needed_parent_ids.add(rel_id)
        if not needed_parent_ids:
            continue
        sql_path = resolve_sql35_table_path(sql35_dir, parent_table)
        if not sql_path.exists():
            continue
        rescan = scan_child_table(sql_path, parent_table, needed_send_ids, child_item_keys, needed_ids=needed_parent_ids)
        child_tables[parent_table] = merge_child_scans(child_tables.get(parent_table), rescan)

    ft_direct = scan_filetransmission_route(resolve_sql35_table_path(sql35_dir, "FILETRANSMISSION"), {row["e_key"] for row in send_rows})
    obj_reply = scan_objectreplylink(resolve_sql35_table_path(sql35_dir, "OBJECTREPLYLINK"), {row["e_key"] for row in send_rows})
    relation_map = _build_relation_map(int_scan, send_scan, ft_direct, *child_tables.values())

    object_ids_for_dist: Set[str] = set(int_scan["by_id"].keys()) | set(send_scan["by_id"].keys()) | set(ft_direct["by_id"].keys())
    needed_title_keys: Set[str] = {row["e_key"] for row in rows if row["e_key"]}
    for payload in int_scan["by_key"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
        needed_title_keys.update(payload.get("candidate_keys", set()))
    for payload in send_scan["by_id"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
        needed_title_keys.update(payload.get("candidate_keys", set()))
    for payload in ft_direct["by_id"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
        needed_title_keys.update(payload.get("candidate_keys", set()))
    for payload in obj_reply["by_key"].values():
        object_ids_for_dist.update(payload.get("relation_ids", []))
        needed_title_keys.update(payload.get("candidate_keys", []))
    for scan in child_tables.values():
        object_ids_for_dist.update(scan["by_id"].keys())
        for payload in scan["by_id"].values():
            object_ids_for_dist.update(payload.get("relation_ids", set()))
            needed_title_keys.update(payload.get("candidate_keys", set()))
    object_ids_for_dist = _expand_relation_ids(object_ids_for_dist, relation_map)

    dist_scan = scan_distribution_word_strict(resolve_sql35_table_path(sql35_dir, "DISTRIBUTERECORD"), object_ids_for_dist, needed_title_keys)

    branch_counter = Counter()
    matched_rows: List[Dict[str, Any]] = []
    unresolved_samples: List[Dict[str, Any]] = []

    for row in rows:
        row["version_best"] = (row["workbook"], row["excel_row"]) in version_best
        row["branch"] = "UNRESOLVED"
        row["send_id"] = ""
        row["int_id"] = ""
        row["title_keys"] = [row["e_key"]] if row["e_key"] else []
        row["group_ids"] = []
        row["leaf_operators"] = []
        row["latest_leaf_operators"] = []
        row["row_latest_leaf_operators"] = []
        row["leaf_people"] = []
        row["latest_leaf_people"] = []
        row["row_latest_leaf_people"] = []
        row["leaf_org_values"] = []
        row["latest_leaf_org_values"] = []
        row["row_latest_leaf_org_values"] = []
        row["leaf_office_values"] = []
        row["latest_leaf_office_values"] = []
        row["row_latest_leaf_office_values"] = []
        row["dist_source_types"] = []
        row["doc_tables"] = []

        direct_ids: Set[str] = set()
        title_keys: Set[str] = set(row["title_keys"])

        if row["key_type"] == "int_key" and row["e_key"] in int_scan["by_key"]:
            payload = int_scan["by_key"][row["e_key"]]
            row["branch"] = "INT"
            row["int_id"] = normalize_hex32(payload.get("ID")) or ""
            direct_ids.update(payload.get("relation_ids", set()))
            title_keys.update(payload.get("candidate_keys", set()))
            related_ids = set(int_scan["ref_to_ids"].get(row["e_key"], set()))
            chain_id = normalize_hex32(payload.get("chain_id"))
            if chain_id:
                related_ids.update(int_scan["chain_to_ids"].get(chain_id, set()))
            if related_ids:
                row["doc_tables"].append("INT_CHAIN")
            for related_id in related_ids:
                related_payload = int_scan["by_id"].get(related_id, {})
                direct_ids.update(related_payload.get("relation_ids", set()))
                title_keys.update(related_payload.get("candidate_keys", set()))
        else:
            send_ids = set(send_scan["rec_to_ids"].get(row["e_key"], set())) | set(send_scan["send_to_ids"].get(row["e_key"], set()))
            send_id = _best_id(send_ids, send_scan["by_id"])
            ft_id = _best_id(ft_direct["key_to_ids"].get(row["e_key"], set()), ft_direct["by_id"])
            obj_reply_payload = obj_reply["by_key"].get(row["e_key"], {})
            if not send_id and ft_id:
                linked_send = normalize_hex32(ft_direct["by_id"].get(ft_id, {}).get("SEND_RECEIVE_DATA"))
                if linked_send:
                    send_id = linked_send
            matched_child_tables: List[Tuple[str, Set[str]]] = []
            for table_name, scan in child_tables.items():
                child_ids: Set[str] = set(scan.get("item_to_ids", {}).get(row["e_key"], set()))
                if send_id:
                    child_ids.update(scan["send_to_ids"].get(send_id, set()))
                if child_ids:
                    matched_child_tables.append((table_name, child_ids))

            if send_id or ft_id or obj_reply_payload or matched_child_tables:
                row["branch"] = "SEND"
                row["send_id"] = send_id
                if send_id:
                    send_payload = send_scan["by_id"].get(send_id, {})
                    direct_ids.update(send_payload.get("relation_ids", set()))
                    title_keys.update(send_payload.get("candidate_keys", set()))
                if ft_id:
                    row["doc_tables"].append("FILETRANSMISSION_ROUTE")
                    ft_payload = ft_direct["by_id"].get(ft_id, {})
                    direct_ids.update(ft_payload.get("relation_ids", set()))
                    title_keys.update(ft_payload.get("candidate_keys", set()))
                if obj_reply_payload:
                    row["doc_tables"].append("OBJECTREPLYLINK")
                    direct_ids.update(obj_reply_payload.get("relation_ids", []))
                    title_keys.update(obj_reply_payload.get("candidate_keys", []))
                for table_name, child_ids in matched_child_tables:
                    row["doc_tables"].append(table_name)
                    scan = child_tables[table_name]
                    for child_id in child_ids:
                        child_payload = scan["by_id"].get(child_id, {})
                        direct_ids.update(child_payload.get("relation_ids", set()))
                        title_keys.update(child_payload.get("candidate_keys", set()))
            elif row["e_key"] and len(unresolved_samples) < 60:
                unresolved_samples.append(
                    {
                        "project": row["project"],
                        "workbook": row["workbook"],
                        "excel_row": row["excel_row"],
                        "a_raw": row["a_raw"],
                        "e_raw": row["e_raw"],
                        "key_type": row["key_type"],
                    }
                )

        direct_ids = _expand_relation_ids(direct_ids, relation_map)

        group_ids: Set[str] = set()
        for obj_id in direct_ids:
            if obj_id in dist_scan["leaves_by_group"]:
                group_ids.add(obj_id)
        for key in title_keys:
            group_ids.update(dist_scan["title_key_to_group_ids"].get(key, []))

        leaf_operators: List[str] = []
        latest_leaf_operators: List[str] = []
        source_types: List[str] = []
        for group_id in sorted(group_ids):
            for operator in dist_scan["leaves_by_group"].get(group_id, []):
                _add_unique(leaf_operators, operator)
            for operator in dist_scan["latest_leaves_by_group"].get(group_id, []):
                _add_unique(latest_leaf_operators, operator)
            for source_type in dist_scan["source_types_by_group"].get(group_id, []):
                _add_unique(source_types, source_type)

        row_latest_leaf_operators = _row_latest_leafs(sorted(group_ids), dist_scan)
        row["title_keys"] = sorted(title_keys)
        row["group_ids"] = sorted(group_ids)
        row["leaf_operators"] = leaf_operators
        row["latest_leaf_operators"] = latest_leaf_operators
        row["row_latest_leaf_operators"] = row_latest_leaf_operators
        row["dist_source_types"] = source_types

        leaf_resolved = _resolve_distribution_entities(leaf_operators, user_map, department_map)
        latest_leaf_resolved = _resolve_distribution_entities(latest_leaf_operators, user_map, department_map)
        row_latest_leaf_resolved = _resolve_distribution_entities(row_latest_leaf_operators, user_map, department_map)

        row["leaf_people"] = leaf_resolved["names"]
        row["latest_leaf_people"] = latest_leaf_resolved["names"]
        row["row_latest_leaf_people"] = row_latest_leaf_resolved["names"]
        row["leaf_org_values"] = leaf_resolved["org_values"]
        row["latest_leaf_org_values"] = latest_leaf_resolved["org_values"]
        row["row_latest_leaf_org_values"] = row_latest_leaf_resolved["org_values"]
        row["leaf_office_values"] = leaf_resolved["office_values"]
        row["latest_leaf_office_values"] = latest_leaf_resolved["office_values"]
        row["row_latest_leaf_office_values"] = row_latest_leaf_resolved["office_values"]

        branch_counter[row["branch"]] += 1
        matched_rows.append(row)

    int_rows_matched = [row for row in matched_rows if row["branch"] == "INT"]
    send_rows_matched = [row for row in matched_rows if row["branch"] == "SEND"]
    version_rows = [row for row in matched_rows if row["version_best"] and row["branch"] in {"INT", "SEND"}]

    strict_metrics = {
        "INT": {
            "X_leaf_union": _metric(int_rows_matched, "x_raw", lambda row: ",".join(row["leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "X_latest_leaf_union": _metric(int_rows_matched, "x_raw", lambda row: ",".join(row["latest_leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "X_row_latest_leaf": _metric(int_rows_matched, "x_raw", lambda row: ",".join(row["row_latest_leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "V_leaf_union": _metric(int_rows_matched, "v_raw", lambda row: row["leaf_org_values"], _org_match),
            "V_latest_leaf_union": _metric(int_rows_matched, "v_raw", lambda row: row["latest_leaf_org_values"], _org_match),
            "V_row_latest_leaf": _metric(int_rows_matched, "v_raw", lambda row: row["row_latest_leaf_org_values"], _org_match),
            "W_leaf_union": _metric(int_rows_matched, "w_raw", lambda row: row["leaf_office_values"], _office_match),
            "W_latest_leaf_union": _metric(int_rows_matched, "w_raw", lambda row: row["latest_leaf_office_values"], _office_match),
            "W_row_latest_leaf": _metric(int_rows_matched, "w_raw", lambda row: row["row_latest_leaf_office_values"], _office_match),
        },
        "SEND": {
            "X_leaf_union": _metric(send_rows_matched, "x_raw", lambda row: ",".join(row["leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "X_latest_leaf_union": _metric(send_rows_matched, "x_raw", lambda row: ",".join(row["latest_leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "X_row_latest_leaf": _metric(send_rows_matched, "x_raw", lambda row: ",".join(row["row_latest_leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "V_leaf_union": _metric(send_rows_matched, "v_raw", lambda row: row["leaf_org_values"], _org_match),
            "V_latest_leaf_union": _metric(send_rows_matched, "v_raw", lambda row: row["latest_leaf_org_values"], _org_match),
            "V_row_latest_leaf": _metric(send_rows_matched, "v_raw", lambda row: row["row_latest_leaf_org_values"], _org_match),
            "W_leaf_union": _metric(send_rows_matched, "w_raw", lambda row: row["leaf_office_values"], _office_match),
            "W_latest_leaf_union": _metric(send_rows_matched, "w_raw", lambda row: row["latest_leaf_office_values"], _office_match),
            "W_row_latest_leaf": _metric(send_rows_matched, "w_raw", lambda row: row["row_latest_leaf_office_values"], _office_match),
        },
        "version_best_overall": {
            "X_leaf_union": _metric(version_rows, "x_raw", lambda row: ",".join(row["leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "X_latest_leaf_union": _metric(version_rows, "x_raw", lambda row: ",".join(row["latest_leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "X_row_latest_leaf": _metric(version_rows, "x_raw", lambda row: ",".join(row["row_latest_leaf_people"]), lambda excel, sql: _owner_match(excel, sql, user_map, roster_names)),
            "V_leaf_union": _metric(version_rows, "v_raw", lambda row: row["leaf_org_values"], _org_match),
            "V_latest_leaf_union": _metric(version_rows, "v_raw", lambda row: row["latest_leaf_org_values"], _org_match),
            "V_row_latest_leaf": _metric(version_rows, "v_raw", lambda row: row["row_latest_leaf_org_values"], _org_match),
            "W_leaf_union": _metric(version_rows, "w_raw", lambda row: row["leaf_office_values"], _office_match),
            "W_latest_leaf_union": _metric(version_rows, "w_raw", lambda row: row["latest_leaf_office_values"], _office_match),
            "W_row_latest_leaf": _metric(version_rows, "w_raw", lambda row: row["row_latest_leaf_office_values"], _office_match),
        },
    }

    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
            "doc_types": sorted({_clean_text(value) for value in (doc_types or []) if _clean_text(value)}),
            "logic_mode": "word_strict_distribution_leaf_only",
        },
        "word_constraints": {
            "workflow_tables_used_for_x": False,
            "prefix_routing_used": False,
            "x_source": "DISTRIBUTERECORD leaf/latest-leaf operators only",
            "vw_source": "department resolution derived from leaf/latest-leaf operators only",
            "completion_rule_note": "Word states reply date means completed; this probe focuses on X/V/W strict owner path.",
        },
        "row_counts": {
            "all_rows": len(rows),
            "version_best_rows": len(version_rows),
            "resolved_rows": sum(1 for row in matched_rows if row["branch"] in {"INT", "SEND"}),
            "version_best_rows_with_groups": sum(1 for row in version_rows if row["group_ids"]),
            "version_best_rows_with_leafs": sum(1 for row in version_rows if row["leaf_people"]),
            "version_best_rows_with_row_latest_leaf": sum(1 for row in version_rows if row["row_latest_leaf_people"]),
        },
        "route_summary": {
            "by_branch": dict(sorted(branch_counter.items())),
            "coverage": {
                "resolved": _rate(sum(1 for row in matched_rows if row["branch"] in {"INT", "SEND"}), len(matched_rows)),
                "version_best_with_groups": _rate(sum(1 for row in version_rows if row["group_ids"]), len(version_rows)),
                "version_best_with_leafs": _rate(sum(1 for row in version_rows if row["leaf_people"]), len(version_rows)),
                "version_best_with_row_latest_leaf": _rate(sum(1 for row in version_rows if row["row_latest_leaf_people"]), len(version_rows)),
            },
            "by_type_group_hits": _by_type_metric(version_rows, lambda row: bool(row["group_ids"])),
            "by_type_leaf_hits": _by_type_metric(version_rows, lambda row: bool(row["leaf_people"])),
            "unresolved_samples": unresolved_samples,
        },
        "table_scans": {
            "INTINTERFACEDOC": {"rows_scanned": int_scan["scanned"], "rows_matched": int_scan["matched"]},
            "SENDRECEIVEDATA": {"rows_scanned": send_scan["scanned"], "rows_matched": send_scan["matched"]},
            "FILETRANSMISSION_ROUTE": {"rows_scanned": ft_direct["scanned"], "rows_matched": ft_direct["matched"]},
            "OBJECTREPLYLINK": {"rows_scanned": obj_reply["scanned"], "rows_matched": obj_reply["matched"]},
            "DISTRIBUTERECORD": {
                "statement_count": dist_scan["statement_count"],
                "matched_count": dist_scan["matched_count"],
                "matched_by_title_count": dist_scan["matched_by_title_count"],
                "group_count": dist_scan["group_count"],
            },
            "send_aux_tables": {
                table_name: {
                    "rows_scanned": scan["scanned"],
                    "rows_matched": scan["matched"],
                    "send_link_rows": sum(len(ids) for ids in scan["send_to_ids"].values()),
                }
                for table_name, scan in sorted(child_tables.items())
            },
        },
        "strict_metrics": strict_metrics,
        "samples": {
            "strict_leaf_examples": [
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "branch": row["branch"],
                    "group_ids": row["group_ids"][:8],
                    "leaf_people": row["leaf_people"][:12],
                    "latest_leaf_people": row["latest_leaf_people"][:12],
                    "row_latest_leaf_people": row["row_latest_leaf_people"][:12],
                    "leaf_org_values": row["leaf_org_values"][:12],
                    "leaf_office_values": row["leaf_office_values"][:12],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
                for row in version_rows
                if row["leaf_people"] and (_clean_text(row["x_raw"]) or _clean_text(row["v_raw"]) or _clean_text(row["w_raw"]))
            ][:40],
            "group_without_leaf_examples": [
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "branch": row["branch"],
                    "group_ids": row["group_ids"][:8],
                    "dist_source_types": row["dist_source_types"][:8],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
                for row in version_rows
                if row["group_ids"] and not row["leaf_people"] and (_clean_text(row["x_raw"]) or _clean_text(row["v_raw"]) or _clean_text(row["w_raw"]))
            ][:40],
            "leaf_miss_examples": [
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "branch": row["branch"],
                    "leaf_people": row["leaf_people"][:10],
                    "row_latest_leaf_people": row["row_latest_leaf_people"][:10],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
                for row in version_rows
                if row["leaf_people"] and row["x_raw"] and not _owner_match(row["x_raw"], ",".join(row["leaf_people"]), user_map, roster_names)
            ][:40],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file6 strictly with Word-described distribution leaf handlers.")
    parser.add_argument("--excel-dir", type=Path, default=Path("example/CIMS-SQL-3.5/EXCEL导出数据"))
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, default=Path("document/file6_word_strict_probe_20260321.json"))
    parser.add_argument("--doc-types", nargs="*", help="Optional A-column doc types to probe. Supports comma-separated values.")
    args = parser.parse_args()

    doc_types: List[str] = []
    for raw_value in args.doc_types or []:
        doc_types.extend([item.strip() for item in raw_value.split(",") if item.strip()])

    payload = run(args.excel_dir, args.sql35_dir, args.output, doc_types=doc_types or None)
    summary = payload["strict_metrics"]["version_best_overall"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "doc_types": payload["inputs"]["doc_types"],
                "version_best_rows": payload["row_counts"]["version_best_rows"],
                "rows_with_groups": payload["row_counts"]["version_best_rows_with_groups"],
                "rows_with_leafs": payload["row_counts"]["version_best_rows_with_leafs"],
                "x_leaf_rate": summary["X_leaf_union"]["rate"],
                "x_row_latest_rate": summary["X_row_latest_leaf"]["rate"],
                "v_leaf_rate": summary["V_leaf_union"]["rate"],
                "w_leaf_rate": summary["W_leaf_union"]["rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
