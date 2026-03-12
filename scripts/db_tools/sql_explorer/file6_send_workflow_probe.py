"""Probe file6 SEND-side handler chain through workflow tables."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence, Set, Tuple

from .composite_excel_sql_recheck import prefilter_sql
from .file4_ah_owner_chain_probe import _owner_match, _remark_names
from .file6_distribution_chain_probe import (
    PARENT_TABLE_BY_REPLY,
    SEND_SIDE_TABLES,
    _clean_text,
    _filter_highest_version,
    _metric,
    _office_match,
    _org_match,
    _resolve_distribution_entities,
    _safe_get,
    load_file6_rows,
    parse_department_tree,
    scan_child_table,
    scan_filetransmission_route,
    scan_objectreplylink,
    scan_send_table,
)
from .roster import load_all_roster_names
from .validate_cims_sql_dump import iter_insert_rows, normalize_hex32, parse_create_columns, parse_user_map


def _parse_time(value: Any) -> Tuple[str, str]:
    text = _clean_text(value)
    return (text, text)


def parse_workflow_union_rows(path: Path, source_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
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
        for item in items:
            for value in (
                item.get("created_by_id"),
                item.get("modified_by_id"),
                item.get("user_name"),
                item.get("transactor_name"),
            ):
                text = _clean_text(value)
                if text and text not in actor_values:
                    actor_values.append(text)
                if _clean_text(item.get("is_active")) == "1" and text and text not in active_actor_values:
                    active_actor_values.append(text)
            source_type = _clean_text(item.get("source_type"))
            if source_type and source_type not in source_types:
                source_types.append(source_type)
        result[source_id] = {
            "actor_values": actor_values,
            "active_actor_values": active_actor_values,
            "source_types": source_types,
            "row_count": len(items),
        }
    return {"scanned": scanned, "matched": matched, "by_source": result}


def parse_vote_union_rows(path: Path, source_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
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
        for item in items:
            operator = _clean_text(item.get("operator"))
            if operator and operator not in operator_values:
                operator_values.append(operator)
            if _clean_text(item.get("is_valid")) in {"1", "Y", "TRUE", "T"} and operator and operator not in valid_operator_values:
                valid_operator_values.append(operator)
        latest_item = max(items, key=lambda item: _parse_time(item.get("operation_time")))
        result[source_id] = {
            "operator_values": operator_values,
            "valid_operator_values": valid_operator_values,
            "latest_operator": _clean_text(latest_item.get("operator")),
            "row_count": len(items),
        }
    return {"scanned": scanned, "matched": matched, "by_source": result, "activity_counter": dict(activity_counter.most_common(30))}


def _best_id(ids: Iterable[str], by_id: Dict[str, Dict[str, Any]]) -> str:
    choice = ""
    best_score: Tuple[str, ...] = ()
    for obj_id in sorted(set(ids)):
        score = tuple(str(item) for item in by_id.get(obj_id, {}).get("row_score", ()))
        if not choice or score >= best_score:
            choice = obj_id
            best_score = score
    return choice


def run(excel_dir: Path, sql35_dir: Path, sql37_dir: Path, output_path: Path, temp_dir: Path) -> Dict[str, Any]:
    rows = load_file6_rows(excel_dir)
    version_best = _filter_highest_version(rows)
    department_map = parse_department_tree(sql35_dir / "DEPARTMENT_20260305.sql")
    user_map = parse_user_map(sql35_dir / "USER_20260305.sql", department_map)
    roster_names = load_all_roster_names()

    send_rows = [row for row in rows if row["key_type"] not in {"empty_key", "int_key"} and row["e_key"]]
    send_scan = scan_send_table(sql35_dir / "SENDRECEIVEDATA_20260305.sql", {row["e_key"] for row in send_rows})

    needed_send_ids: Set[str] = set()
    for mapping_name in ("rec_to_ids", "send_to_ids"):
        for send_ids in send_scan[mapping_name].values():
            needed_send_ids.update(send_ids)

    child_tables: Dict[str, Dict[str, Any]] = {}
    child_item_keys = {row["e_key"] for row in send_rows}
    for table_name in SEND_SIDE_TABLES:
        sql_path = sql35_dir / f"{table_name}_20260305.sql"
        if not sql_path.exists():
            continue
        child_tables[table_name] = scan_child_table(sql_path, table_name, needed_send_ids, child_item_keys)

    for reply_table, parent_table in PARENT_TABLE_BY_REPLY.items():
        scan = child_tables.get(reply_table)
        if not scan:
            continue
        needed_parent_ids: Set[str] = set()
        for payload in scan["by_id"].values():
            for field_name in ("CR", "TA", "NCR"):
                rel_id = normalize_hex32(payload.get(field_name))
                if rel_id:
                    needed_parent_ids.add(rel_id)
        if not needed_parent_ids:
            continue
        sql_path = sql35_dir / f"{parent_table}_20260305.sql"
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

    ft_direct = scan_filetransmission_route(sql35_dir / "FILETRANSMISSION_20260305.sql", {row["e_key"] for row in send_rows})
    obj_reply = scan_objectreplylink(sql35_dir / "OBJECTREPLYLINK_20260305.sql", {row["e_key"] for row in send_rows})

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
            child_ids = list(scan["send_to_ids"].get(send_id, set())) if send_id else []
            if child_ids:
                row["table_sources"].append(table_name)
                candidate_ids.update(child_ids)

        row["candidate_object_ids"] = sorted(candidate_ids)

    all_object_ids = {obj_id for row in send_rows for obj_id in row["candidate_object_ids"]}

    temp_dir.mkdir(parents=True, exist_ok=True)
    wf_path = temp_dir / "WORKFLOWPROCESSESBIND_file6_send.sql"
    vote_path = temp_dir / "USERVOTERECORD_file6_send.sql"
    prefilter_sql(sql37_dir / "WORKFLOWPROCESSESBIND_20260307.sql", all_object_ids, wf_path)
    prefilter_sql(sql37_dir / "USERVOTERECORD_20260307.sql", all_object_ids, vote_path)
    wf = parse_workflow_union_rows(wf_path, all_object_ids)
    vote = parse_vote_union_rows(vote_path, all_object_ids)

    matched_examples: List[Dict[str, Any]] = []
    unresolved_examples: List[Dict[str, Any]] = []
    source_counter: Counter[str] = Counter()
    row_source_counter: Counter[str] = Counter()

    for row in send_rows:
        actor_values: List[str] = []
        source_types: List[str] = []
        for obj_id in row["candidate_object_ids"]:
            wf_payload = wf["by_source"].get(obj_id, {})
            vote_payload = vote["by_source"].get(obj_id, {})
            for value in wf_payload.get("actor_values", []):
                if value and value not in actor_values:
                    actor_values.append(value)
            for value in vote_payload.get("operator_values", []):
                if value and value not in actor_values:
                    actor_values.append(value)
            for source_type in wf_payload.get("source_types", []):
                if source_type and source_type not in source_types:
                    source_types.append(source_type)
        resolved = _resolve_distribution_entities(actor_values, user_map, department_map)
        row["workflow_people_all"] = resolved["names"]
        row["workflow_org_values"] = resolved["org_values"]
        row["workflow_office_values"] = resolved["office_values"]
        row["workflow_source_types"] = source_types
        row["workflow_object_hit_count"] = sum(
            1 for obj_id in row["candidate_object_ids"] if obj_id in wf["by_source"] or obj_id in vote["by_source"]
        )

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

    version_rows = [row for row in send_rows if row["version_best"]]
    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
            "sql37_dir": str(sql37_dir),
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
            },
            "USERVOTERECORD": {
                "rows_scanned": vote["scanned"],
                "rows_matched": vote["matched"],
                "matched_source_ids": len(vote["by_source"]),
                "activity_counter": vote["activity_counter"],
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
            }
        },
        "source_counters": {
            "workflow_source_types": dict(source_counter.most_common(20)),
            "row_table_sources": dict(row_source_counter.most_common(20)),
        },
        "samples": {
            "matched_examples": matched_examples,
            "unresolved_examples": unresolved_examples,
        },
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file6 SEND-side workflow handlers.")
    parser.add_argument("--excel-dir", type=Path, default=Path("example/CIMS-SQL-3.5/EXCEL导出数据"))
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--sql37-dir", type=Path, default=Path("example/CIMS-sql-3.7"))
    parser.add_argument("--output", type=Path, default=Path("tmp/file6_send_workflow_probe_20260312.json"))
    parser.add_argument("--temp-dir", type=Path, default=Path("tmp/file6_send_workflow_probe"))
    args = parser.parse_args()

    payload = run(args.excel_dir, args.sql35_dir, args.sql37_dir, args.output, args.temp_dir)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "version_best_rows": payload["row_counts"]["version_best_send_rows"],
                "rows_with_workflow_hits": payload["row_counts"]["version_best_rows_with_workflow_hits"],
                "x_rate": payload["workflow_metrics"]["version_best"]["X_all"]["rate"],
                "v_rate": payload["workflow_metrics"]["version_best"]["V_all"]["rate"],
                "w_rate": payload["workflow_metrics"]["version_best"]["W_all"]["rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
