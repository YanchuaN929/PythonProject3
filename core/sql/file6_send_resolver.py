#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable SEND-side resolver for file6 document-type rules."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from scripts.db_tools.sql_explorer.composite_excel_sql_recheck import prefilter_sql
from scripts.db_tools.sql_explorer.file4_ah_owner_chain_probe import _owner_match, _remark_names
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import (
    PARENT_FIELD_BY_REPLY,
    PARENT_TABLE_BY_REPLY,
    SEND_SIDE_TABLES,
    _build_relation_map,
    _clean_text,
    _expand_relation_ids,
    _filter_highest_version,
    _metric,
    _office_match,
    _org_match,
    _resolve_distribution_entities,
    _safe_get,
    load_file6_rows,
    parse_department_tree,
    resolve_sql35_table_path,
    scan_child_table,
    scan_filetransmission_route,
    scan_objectreplylink,
    scan_send_table,
)
from scripts.db_tools.sql_explorer.roster import load_all_roster_names
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import (
    iter_insert_rows,
    normalize_hex32,
    parse_create_columns,
    parse_user_map,
)


@dataclass(frozen=True)
class File6SendTypeRule:
    doc_type: str
    actor_strategy: str = "workflow_union"
    object_actor_fields: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    status_hint: str = "unclassified"
    next_focus: str = "先验证 workflow/vote 主链，再判断是否需要对象字段补强"


_DEFAULT_RULE = File6SendTypeRule(doc_type="")

FILE6_SEND_TYPE_RULES: Dict[str, File6SendTypeRule] = {
    "图文传真": File6SendTypeRule(
        doc_type="图文传真",
        actor_strategy="workflow_union_plus_object_fields",
        object_actor_fields={"TELEFAX": ("CREATED_BY_ID", "MODIFIED_BY_ID")},
        status_hint="semantic_gap",
        next_focus="对象桥已通，优先拆责任人口径",
    ),
    "备忘录": File6SendTypeRule(
        doc_type="备忘录",
        actor_strategy="workflow_union_plus_object_fields",
        object_actor_fields={"MEMORANDUM": ("CREATED_BY_ID", "MODIFIED_BY_ID")},
        status_hint="chain_and_semantics",
        next_focus="先补对象桥，再拆责任人口径",
    ),
    "文件传递单": File6SendTypeRule(
        doc_type="文件传递单",
        actor_strategy="workflow_union_plus_object_fields",
        object_actor_fields={"FILETRANSMISSION": ("MODIFIED_BY_ID",)},
        status_hint="chain_and_semantics",
        next_focus="先补对象桥，再拆责任人口径",
    ),
    "审查意见单": File6SendTypeRule(
        doc_type="审查意见单",
        actor_strategy="workflow_union_plus_object_fields",
        object_actor_fields={
            "DESIGNREVIEWOPNION": ("MODIFIED_BY_ID",),
            "FILETRANSMISSION": ("MODIFIED_BY_ID",),
        },
        status_hint="semantic_gap",
        next_focus="对象桥已通，优先拆责任人口径",
    ),
    "审查意见答复单": File6SendTypeRule(
        doc_type="审查意见答复单",
        status_hint="near_closed",
        next_focus="转抽样复核",
    ),
    "TA": File6SendTypeRule(
        doc_type="TA",
        status_hint="semantic_gap",
        next_focus="对象桥已通，优先拆责任人口径",
    ),
    "CR": File6SendTypeRule(
        doc_type="CR",
        status_hint="semantic_gap",
        next_focus="对象桥已通，优先拆责任人口径",
    ),
    "NCR": File6SendTypeRule(
        doc_type="NCR",
        status_hint="semantic_gap",
        next_focus="对象桥已通，优先拆责任人口径",
    ),
    "外发纪要": File6SendTypeRule(
        doc_type="外发纪要",
        status_hint="semantic_gap",
        next_focus="对象桥已通，优先拆责任人口径",
    ),
    "FU通知单": File6SendTypeRule(
        doc_type="FU通知单",
        status_hint="chain_and_semantics",
        next_focus="先补对象桥，再拆责任人口径",
    ),
    "IITF": File6SendTypeRule(
        doc_type="IITF",
        status_hint="workflow_missing",
        next_focus="先追对象桥",
    ),
    "IICS": File6SendTypeRule(
        doc_type="IICS",
        status_hint="workflow_missing",
        next_focus="先追对象桥",
    ),
    "TA回复单": File6SendTypeRule(
        doc_type="TA回复单",
        status_hint="no_excel_baseline",
        next_focus="仅保留链路验证，等待更多 Excel 真值",
    ),
    "CR答复单": File6SendTypeRule(
        doc_type="CR答复单",
        status_hint="no_excel_baseline",
        next_focus="仅保留链路验证，等待更多 Excel 真值",
    ),
    "NCR回复单": File6SendTypeRule(
        doc_type="NCR回复单",
        status_hint="no_excel_baseline",
        next_focus="仅保留链路验证，等待更多 Excel 真值",
    ),
    "作废通知单": File6SendTypeRule(
        doc_type="作废通知单",
        status_hint="no_excel_baseline",
        next_focus="仅保留链路验证，等待更多 Excel 真值",
    ),
}


def get_file6_send_type_rule(doc_type: str) -> File6SendTypeRule:
    key = _clean_text(doc_type)
    if not key:
        return _DEFAULT_RULE
    return FILE6_SEND_TYPE_RULES.get(key, File6SendTypeRule(doc_type=key))


def get_file6_send_type_rulebook() -> Dict[str, File6SendTypeRule]:
    return dict(FILE6_SEND_TYPE_RULES)


def serialize_file6_send_rule(rule: File6SendTypeRule) -> Dict[str, Any]:
    return {
        "doc_type": rule.doc_type,
        "actor_strategy": rule.actor_strategy,
        "object_actor_fields": {table: list(fields) for table, fields in rule.object_actor_fields.items()},
        "status_hint": rule.status_hint,
        "next_focus": rule.next_focus,
    }


def _parse_time(value: Any) -> Tuple[str, str]:
    text = _clean_text(value)
    return (text, text)


def _add_unique(items: List[str], value: Any) -> None:
    text = _clean_text(value)
    if text and text not in items:
        items.append(text)


def _best_id(ids: Iterable[str], by_id: Dict[str, Dict[str, Any]]) -> str:
    choice = ""
    best_score: Tuple[str, ...] = ()
    for obj_id in sorted(set(ids)):
        score = tuple(str(item) for item in by_id.get(obj_id, {}).get("row_score", ()))
        if not choice or score >= best_score:
            choice = obj_id
            best_score = score
    return choice


def _resolve_union_table_path(primary_dir: Path, fallback_dir: Path, table_name: str) -> Path:
    candidates = [
        primary_dir / f"{table_name}_20260307.sql",
        primary_dir / f"{table_name}.sql",
        fallback_dir / f"{table_name}_20260307.sql",
        fallback_dir / f"{table_name}.sql",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def parse_workflow_union_rows(path: Path, source_ids: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_source = mapping.get("source_object_id", -1)
    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if current_idx >= 0 and str(_safe_get(row, current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_id = normalize_hex32(_safe_get(row, idx_source))
        if not source_id or source_id not in source_ids:
            continue
        matched += 1
        payload = {
            "created_on": _safe_get(row, mapping.get("created_on", -1)),
            "created_by_id": normalize_hex32(_safe_get(row, mapping.get("created_by_id", -1))),
            "modified_on": _safe_get(row, mapping.get("modified_on", -1)),
            "modified_by_id": normalize_hex32(_safe_get(row, mapping.get("modified_by_id", -1))),
            "remark": _safe_get(row, mapping.get("remark", -1)),
            "source_type": _clean_text(_safe_get(row, mapping.get("source_type", -1))),
            "is_active": _clean_text(_safe_get(row, mapping.get("is_active", -1))),
        }
        payload.update(_remark_names(payload.get("remark")))
        grouped[source_id].append(payload)

    result: Dict[str, Dict[str, Any]] = {}
    for source_id, items in grouped.items():
        actor_values: List[str] = []
        active_actor_values: List[str] = []
        source_types: List[str] = []
        source_type_actor_values: Dict[str, List[str]] = {}
        source_type_active_actor_values: Dict[str, List[str]] = {}
        for item in items:
            source_type = _clean_text(item.get("source_type")) or "[unknown]"
            if source_type not in source_types:
                source_types.append(source_type)
            for value in (
                item.get("created_by_id"),
                item.get("modified_by_id"),
                item.get("user_name"),
                item.get("transactor_name"),
            ):
                _add_unique(actor_values, value)
                _add_unique(source_type_actor_values.setdefault(source_type, []), value)
                if _clean_text(item.get("is_active")) == "1":
                    _add_unique(active_actor_values, value)
                    _add_unique(source_type_active_actor_values.setdefault(source_type, []), value)
        result[source_id] = {
            "actor_values": actor_values,
            "active_actor_values": active_actor_values,
            "source_types": source_types,
            "source_type_actor_values": source_type_actor_values,
            "source_type_active_actor_values": source_type_active_actor_values,
            "row_count": len(items),
        }
    return {"scanned": scanned, "matched": matched, "by_source": result}


def parse_vote_union_rows(path: Path, source_ids: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_source = mapping.get("source_object_id", -1)
    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    activity_counter: Counter[str] = Counter()
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if current_idx >= 0 and str(_safe_get(row, current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_id = normalize_hex32(_safe_get(row, idx_source))
        if not source_id or source_id not in source_ids:
            continue
        matched += 1
        payload = {
            "operator": normalize_hex32(_safe_get(row, mapping.get("operator", -1))) or _clean_text(_safe_get(row, mapping.get("operator", -1))),
            "operation_time": _safe_get(row, mapping.get("operation_time", -1)),
            "receive_time": _safe_get(row, mapping.get("receive_time", -1)),
            "activity_name": _clean_text(_safe_get(row, mapping.get("activity_name", -1))),
            "is_valid": _clean_text(_safe_get(row, mapping.get("is_valid", -1))),
        }
        grouped[source_id].append(payload)
        if payload["activity_name"]:
            activity_counter[payload["activity_name"]] += 1

    result: Dict[str, Dict[str, Any]] = {}
    for source_id, items in grouped.items():
        operator_values: List[str] = []
        valid_operator_values: List[str] = []
        activity_to_operator_values: Dict[str, List[str]] = {}
        valid_activity_to_operator_values: Dict[str, List[str]] = {}
        for item in items:
            operator = _clean_text(item.get("operator"))
            activity_name = _clean_text(item.get("activity_name")) or "[unknown]"
            _add_unique(operator_values, operator)
            _add_unique(activity_to_operator_values.setdefault(activity_name, []), operator)
            if _clean_text(item.get("is_valid")) in {"1", "Y", "TRUE", "T"}:
                _add_unique(valid_operator_values, operator)
                _add_unique(valid_activity_to_operator_values.setdefault(activity_name, []), operator)
        latest_item = max(items, key=lambda item: _parse_time(item.get("operation_time")))
        result[source_id] = {
            "operator_values": operator_values,
            "valid_operator_values": valid_operator_values,
            "activity_to_operator_values": activity_to_operator_values,
            "valid_activity_to_operator_values": valid_activity_to_operator_values,
            "latest_operator": _clean_text(latest_item.get("operator")),
            "row_count": len(items),
        }
    return {"scanned": scanned, "matched": matched, "by_source": result, "activity_counter": dict(activity_counter.most_common(30))}


def resolve_file6_send_rows(
    excel_dir: Path,
    sql35_dir: Path,
    sql37_dir: Path,
    temp_dir: Path,
    doc_types: Sequence[str] | None = None,
    include_detail_rows: bool = False,
) -> Dict[str, Any]:
    rows = load_file6_rows(excel_dir)
    version_best = _filter_highest_version(rows)
    department_map = parse_department_tree(resolve_sql35_table_path(sql35_dir, "DEPARTMENT"))
    user_map = parse_user_map(resolve_sql35_table_path(sql35_dir, "USER"), department_map)
    roster_names = load_all_roster_names()
    doc_type_filter = {_clean_text(item) for item in (doc_types or []) if _clean_text(item)}

    send_rows = [
        row
        for row in rows
        if row["key_type"] not in {"empty_key", "int_key"}
        and row["e_key"]
        and (not doc_type_filter or _clean_text(row["a_raw"]) in doc_type_filter)
    ]
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
        base = child_tables.get(parent_table)
        if not base:
            child_tables[parent_table] = rescan
        else:
            base["scanned"] += rescan.get("scanned", 0)
            base["matched"] += rescan.get("matched", 0)
            base["by_id"].update(rescan.get("by_id", {}))
            for key, ids in rescan.get("send_to_ids", {}).items():
                base["send_to_ids"][key].update(ids)
            for key, ids in rescan.get("item_to_ids", {}).items():
                base["item_to_ids"][key].update(ids)

    ft_direct = scan_filetransmission_route(resolve_sql35_table_path(sql35_dir, "FILETRANSMISSION"), {row["e_key"] for row in send_rows})
    obj_reply = scan_objectreplylink(resolve_sql35_table_path(sql35_dir, "OBJECTREPLYLINK"), {row["e_key"] for row in send_rows})
    relation_map = _build_relation_map(send_scan, ft_direct, *child_tables.values())

    for row in send_rows:
        row["version_best"] = (row["workbook"], row["excel_row"]) in version_best
        row["candidate_object_ids"] = []
        row["table_sources"] = []
        send_ids = set(send_scan["rec_to_ids"].get(row["e_key"], set())) | set(send_scan["send_to_ids"].get(row["e_key"], set()))
        send_id = _best_id(send_ids, send_scan["by_id"])
        ft_id = _best_id(ft_direct["key_to_ids"].get(row["e_key"], set()), ft_direct["by_id"])
        if not send_id and ft_id:
            linked_send = normalize_hex32(ft_direct["by_id"].get(ft_id, {}).get("SEND_RECEIVE_DATA"))
            if linked_send:
                send_id = linked_send
        row["send_id"] = send_id

        candidate_ids: Set[str] = set()
        if send_id:
            candidate_ids.add(send_id)
        if ft_id:
            candidate_ids.add(ft_id)
            row["table_sources"].append("FILETRANSMISSION_ROUTE")
        obj_reply_payload = obj_reply["by_key"].get(row["e_key"], {})
        if obj_reply_payload:
            candidate_ids.update(obj_reply_payload.get("relation_ids", []))
            row["table_sources"].append("OBJECTREPLYLINK")
        for table_name, scan in child_tables.items():
            child_ids: Set[str] = set(scan.get("item_to_ids", {}).get(row["e_key"], set()))
            if send_id:
                child_ids.update(scan["send_to_ids"].get(send_id, set()))
            if child_ids:
                row["table_sources"].append(table_name)
                candidate_ids.update(child_ids)
        row["candidate_object_ids"] = sorted(_expand_relation_ids(candidate_ids, relation_map))

    all_object_ids = {obj_id for row in send_rows for obj_id in row["candidate_object_ids"]}

    temp_dir.mkdir(parents=True, exist_ok=True)
    wf_path = temp_dir / "WORKFLOWPROCESSESBIND_file6_send.sql"
    vote_path = temp_dir / "USERVOTERECORD_file6_send.sql"
    workflow_source = _resolve_union_table_path(sql37_dir, sql35_dir, "WORKFLOWPROCESSESBIND")
    vote_source = _resolve_union_table_path(sql37_dir, sql35_dir, "USERVOTERECORD")
    prefilter_sql(workflow_source, all_object_ids, wf_path)
    prefilter_sql(vote_source, all_object_ids, vote_path)
    wf = parse_workflow_union_rows(wf_path, all_object_ids)
    vote = parse_vote_union_rows(vote_path, all_object_ids)

    matched_examples: List[Dict[str, Any]] = []
    unresolved_examples: List[Dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    row_source_counter: Counter[str] = Counter()
    detail_rows: List[Dict[str, Any]] = []

    for row in send_rows:
        rule = get_file6_send_type_rule(row.get("a_raw", ""))
        actor_values: List[str] = []
        source_types: List[str] = []
        object_actor_values: List[str] = []
        object_actor_sources: Dict[str, List[str]] = {}
        workflow_all_actor_values: List[str] = []
        workflow_active_actor_values: List[str] = []
        vote_all_operators: List[str] = []
        vote_valid_operators: List[str] = []
        workflow_source_type_actors: Dict[str, List[str]] = {}
        workflow_source_type_active_actors: Dict[str, List[str]] = {}
        vote_activity_operators: Dict[str, List[str]] = {}
        vote_valid_activity_operators: Dict[str, List[str]] = {}
        vote_source_type_operators: Dict[str, List[str]] = {}
        vote_source_type_activity_operators: Dict[str, Dict[str, List[str]]] = {}
        vote_valid_source_type_activity_operators: Dict[str, Dict[str, List[str]]] = {}
        for obj_id in row["candidate_object_ids"]:
            wf_payload = wf["by_source"].get(obj_id, {})
            vote_payload = vote["by_source"].get(obj_id, {})
            obj_source_types = wf_payload.get("source_types", []) or ["[unknown]"]
            for value in wf_payload.get("actor_values", []):
                _add_unique(actor_values, value)
                _add_unique(workflow_all_actor_values, value)
            for value in wf_payload.get("active_actor_values", []):
                _add_unique(workflow_active_actor_values, value)
            for source_type, values in wf_payload.get("source_type_actor_values", {}).items():
                bucket = workflow_source_type_actors.setdefault(source_type, [])
                for value in values:
                    _add_unique(bucket, value)
            for source_type, values in wf_payload.get("source_type_active_actor_values", {}).items():
                bucket = workflow_source_type_active_actors.setdefault(source_type, [])
                for value in values:
                    _add_unique(bucket, value)
            for value in vote_payload.get("operator_values", []):
                _add_unique(actor_values, value)
                _add_unique(vote_all_operators, value)
            for value in vote_payload.get("valid_operator_values", []):
                _add_unique(vote_valid_operators, value)
            for activity_name, values in vote_payload.get("activity_to_operator_values", {}).items():
                activity_bucket = vote_activity_operators.setdefault(activity_name, [])
                for value in values:
                    _add_unique(activity_bucket, value)
                for source_type in obj_source_types:
                    source_bucket = vote_source_type_operators.setdefault(source_type, [])
                    for value in values:
                        _add_unique(source_bucket, value)
                    activity_bucket_by_source = vote_source_type_activity_operators.setdefault(source_type, {}).setdefault(activity_name, [])
                    for value in values:
                        _add_unique(activity_bucket_by_source, value)
            for activity_name, values in vote_payload.get("valid_activity_to_operator_values", {}).items():
                activity_bucket = vote_valid_activity_operators.setdefault(activity_name, [])
                for value in values:
                    _add_unique(activity_bucket, value)
                for source_type in obj_source_types:
                    activity_bucket_by_source = vote_valid_source_type_activity_operators.setdefault(source_type, {}).setdefault(activity_name, [])
                    for value in values:
                        _add_unique(activity_bucket_by_source, value)
            for source_type in obj_source_types:
                if source_type and source_type not in source_types:
                    source_types.append(source_type)

        for table_name, field_names in rule.object_actor_fields.items():
            scan = child_tables.get(table_name)
            if not scan:
                continue
            for obj_id in row["candidate_object_ids"]:
                payload = scan["by_id"].get(obj_id, {})
                if not payload:
                    continue
                for field_name in field_names:
                    value = payload.get(field_name)
                    _add_unique(actor_values, value)
                    _add_unique(object_actor_values, value)
                    _add_unique(object_actor_sources.setdefault(f"{table_name}.{field_name}", []), value)

        resolved = _resolve_distribution_entities(actor_values, user_map, department_map)
        row["workflow_people_all"] = resolved["names"]
        row["workflow_org_values"] = resolved["org_values"]
        row["workflow_office_values"] = resolved["office_values"]
        row["workflow_source_types"] = source_types
        row["workflow_object_hit_count"] = sum(
            1 for obj_id in row["candidate_object_ids"] if obj_id in wf["by_source"] or obj_id in vote["by_source"]
        )
        row["rule"] = serialize_file6_send_rule(rule)

        for source in row["table_sources"]:
            row_source_counter[source] += 1
        for source_type in source_types:
            source_counter[source_type] += 1

        if row["version_best"] and row["workflow_object_hit_count"] and len(matched_examples) < 40:
            matched_examples.append(
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "table_sources": row["table_sources"],
                    "candidate_object_ids": row["candidate_object_ids"][:8],
                    "workflow_source_types": row["workflow_source_types"][:6],
                    "workflow_people_all": row["workflow_people_all"][:30],
                    "workflow_org_values": row["workflow_org_values"][:15],
                    "workflow_office_values": row["workflow_office_values"][:15],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
            )
        elif row["version_best"] and not row["workflow_object_hit_count"] and len(unresolved_examples) < 40:
            unresolved_examples.append(
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "table_sources": row["table_sources"],
                    "candidate_object_ids": row["candidate_object_ids"][:8],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
            )

        if include_detail_rows and row["version_best"]:
            detail_rows.append(
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                    "table_sources": row["table_sources"],
                    "candidate_object_ids": row["candidate_object_ids"],
                    "workflow_source_types": row["workflow_source_types"],
                    "workflow_object_hit_count": row["workflow_object_hit_count"],
                    "workflow_people_all": row["workflow_people_all"],
                    "workflow_org_values": row["workflow_org_values"],
                    "workflow_office_values": row["workflow_office_values"],
                    "object_actor_values": object_actor_values,
                    "object_actor_sources": object_actor_sources,
                    "workflow_all_actor_values": workflow_all_actor_values,
                    "workflow_active_actor_values": workflow_active_actor_values,
                    "workflow_source_type_actors": workflow_source_type_actors,
                    "workflow_source_type_active_actors": workflow_source_type_active_actors,
                    "vote_all_operators": vote_all_operators,
                    "vote_valid_operators": vote_valid_operators,
                    "vote_activity_operators": vote_activity_operators,
                    "vote_valid_activity_operators": vote_valid_activity_operators,
                    "vote_source_type_operators": vote_source_type_operators,
                    "vote_source_type_activity_operators": vote_source_type_activity_operators,
                    "vote_valid_source_type_activity_operators": vote_valid_source_type_activity_operators,
                    "rule": row["rule"],
                }
            )

    version_rows = [row for row in send_rows if row["version_best"]]
    present_doc_types = sorted({_clean_text(row["a_raw"]) for row in version_rows if _clean_text(row["a_raw"])})
    by_type_metrics = {}
    for doc_type in present_doc_types:
        doc_rows = [row for row in version_rows if _clean_text(row["a_raw"]) == doc_type]
        by_type_metrics[doc_type] = {
            "row_count": len(doc_rows),
            "rows_with_workflow_hits": sum(1 for row in doc_rows if row["workflow_object_hit_count"]),
            "X_all": _metric(
                doc_rows,
                "x_raw",
                lambda row: ",".join(row["workflow_people_all"]),
                lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
            ),
            "V_all": _metric(doc_rows, "v_raw", lambda row: row["workflow_org_values"], _org_match),
            "W_all": _metric(doc_rows, "w_raw", lambda row: row["workflow_office_values"], _office_match),
        }

    payload: Dict[str, Any] = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
            "sql37_dir": str(sql37_dir),
            "doc_types": sorted(doc_type_filter),
        },
        "row_counts": {
            "all_send_rows": len(send_rows),
            "version_best_send_rows": len(version_rows),
            "rows_with_candidate_objects": sum(1 for row in send_rows if row["candidate_object_ids"]),
            "rows_with_workflow_hits": sum(1 for row in send_rows if row["workflow_object_hit_count"]),
            "version_best_rows_with_workflow_hits": sum(1 for row in version_rows if row["workflow_object_hit_count"]),
        },
        "table_scans": {
            "SENDRECEIVEDATA": {"rows_scanned": send_scan["scanned"], "rows_matched": send_scan["matched"]},
            "FILETRANSMISSION_ROUTE": {"rows_scanned": ft_direct["scanned"], "rows_matched": ft_direct["matched"]},
            "OBJECTREPLYLINK": {"rows_scanned": obj_reply["scanned"], "rows_matched": obj_reply["matched"]},
            "send_aux_tables": {
                table_name: {
                    "rows_scanned": scan["scanned"],
                    "rows_matched": scan["matched"],
                    "send_link_rows": sum(len(ids) for ids in scan["send_to_ids"].values()),
                }
                for table_name, scan in sorted(child_tables.items())
            },
            "WORKFLOWPROCESSESBIND": {
                "rows_scanned": wf["scanned"],
                "rows_matched": wf["matched"],
                "matched_source_ids": len(wf["by_source"]),
                "source_path": str(workflow_source),
            },
            "USERVOTERECORD": {
                "rows_scanned": vote["scanned"],
                "rows_matched": vote["matched"],
                "matched_source_ids": len(vote["by_source"]),
                "activity_counter": vote["activity_counter"],
                "source_path": str(vote_source),
            },
        },
        "workflow_metrics": {
            "version_best": {
                "X_all": _metric(
                    version_rows,
                    "x_raw",
                    lambda row: ",".join(row["workflow_people_all"]),
                    lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
                ),
                "V_all": _metric(version_rows, "v_raw", lambda row: row["workflow_org_values"], _org_match),
                "W_all": _metric(version_rows, "w_raw", lambda row: row["workflow_office_values"], _office_match),
            },
            "by_type": by_type_metrics,
        },
        "type_rules": {doc_type: serialize_file6_send_rule(get_file6_send_type_rule(doc_type)) for doc_type in present_doc_types},
        "source_counters": {
            "workflow_source_types": dict(source_counter.most_common(20)),
            "row_table_sources": dict(row_source_counter.most_common(20)),
        },
        "samples": {
            "matched_examples": matched_examples,
            "unresolved_examples": unresolved_examples,
        },
    }
    if include_detail_rows:
        payload["detail_rows"] = detail_rows
    return payload
