"""Focused probe for file4 AH owner chain."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set

import pandas as pd

from .composite_excel_sql_recheck import best_child_id, collect_workbooks, parse_child_rows, parse_send_rows, prefilter_sql
from .identity_resolver import resolve_owner_value
from .real_distribution_chain_probe import _clean_text, _excel_col_index, _norm_drop_tail_digits, _norm_key, _safe_get
from .roster import load_all_roster_names, normalize_owner_tokens
from .validate_cims_sql_dump import iter_insert_rows, parse_create_columns, parse_department_map, parse_user_map, normalize_hex32


def load_file4_rows(excel_dir: Path) -> List[Dict[str, Any]]:
    workbooks = collect_workbooks(excel_dir)["file4"]
    idx_a = _excel_col_index("A")
    idx_e = _excel_col_index("E")
    idx_ah = _excel_col_index("AH")
    rows: List[Dict[str, Any]] = []
    for wb in workbooks:
        df = pd.read_excel(wb["path"], sheet_name=0, engine="openpyxl")
        for row_no in range(len(df)):
            values = df.iloc[row_no].tolist()
            e_raw = _safe_get(values, idx_e)
            e_key = _norm_key(e_raw)
            if not e_key:
                continue
            rows.append(
                {
                    "project": wb["project"],
                    "workbook": wb["name"],
                    "excel_row": row_no + 2,
                    "a_type": _clean_text(_safe_get(values, idx_a)).upper(),
                    "e_token": _clean_text(e_raw),
                    "e_key": e_key,
                    "e_key_tail": _norm_drop_tail_digits(e_raw),
                    "owner_raw": _clean_text(_safe_get(values, idx_ah)),
                }
            )
    return rows


def _parse_time(value: Any) -> pd.Timestamp:
    parsed = pd.to_datetime(str(value or "").strip(), errors="coerce")
    return parsed if parsed is not pd.NaT else pd.Timestamp.min


def _owner_match(excel_value: Any, sql_value: Any, user_map: Dict[str, Dict[str, Any]], roster_names: Set[str]) -> bool:
    excel_tokens = normalize_owner_tokens(excel_value)
    if not excel_tokens:
        return False

    sql_tokens = normalize_owner_tokens(sql_value)
    resolved = resolve_owner_value(sql_value, user_map)
    for name in resolved.get("resolved_names", []) or []:
        text = _clean_text(name)
        if text and text not in sql_tokens:
            sql_tokens.append(text)

    if roster_names:
        sql_tokens = [token for token in sql_tokens if token in roster_names or token in excel_tokens] or sql_tokens
    return bool(set(excel_tokens) & set(sql_tokens))


def _metric(rows: Sequence[Dict[str, Any]], getter) -> Dict[str, Any]:
    total = len(rows)
    hit = 0
    by_project = defaultdict(lambda: {"total": 0, "hit": 0})
    for row in rows:
        by_project[row["project"]]["total"] += 1
        if getter(row):
            hit += 1
            by_project[row["project"]]["hit"] += 1
    return {
        "total": total,
        "hit": hit,
        "rate": round(hit / total, 6) if total else 0.0,
        "by_project": {
            project: {
                "total": payload["total"],
                "hit": payload["hit"],
                "rate": round(payload["hit"] / payload["total"], 6) if payload["total"] else 0.0,
            }
            for project, payload in sorted(by_project.items())
        },
    }


def _pick_first_non_empty(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _remark_names(remark: Any) -> Dict[str, str]:
    text = _clean_text(remark)
    if not text:
        return {"user_name": "", "transactor_name": "", "combined": ""}
    try:
        data = json.loads(text)
    except Exception:
        return {"user_name": "", "transactor_name": "", "combined": ""}
    flow_user = data.get("flowUser") or {}
    user_name = _clean_text(flow_user.get("userName"))
    transactor_name = _clean_text(flow_user.get("transactorName"))
    combined = ",".join([item for item in [user_name, transactor_name] if item])
    return {"user_name": user_name, "transactor_name": transactor_name, "combined": combined}


def parse_workflow_rows(path: Path, source_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_source = mapping.get("source_object_id", -1)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in iter_insert_rows(path):
        if current_idx >= 0 and str(_safe_get(row, current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_id = normalize_hex32(_safe_get(row, idx_source))
        if not source_id or source_id not in source_ids:
            continue
        payload = {
            "created_on": _safe_get(row, mapping.get("created_on", -1)),
            "created_by_id": _safe_get(row, mapping.get("created_by_id", -1)),
            "modified_on": _safe_get(row, mapping.get("modified_on", -1)),
            "modified_by_id": _safe_get(row, mapping.get("modified_by_id", -1)),
            "workflow_process_id": _safe_get(row, mapping.get("workflow_process_id", -1)),
            "remark": _safe_get(row, mapping.get("remark", -1)),
            "is_active": _safe_get(row, mapping.get("is_active", -1)),
        }
        payload.update(_remark_names(payload.get("remark")))
        grouped[source_id].append(payload)

    result: Dict[str, Dict[str, Any]] = {}
    for source_id, items in grouped.items():
        latest_modified = max(items, key=lambda item: _parse_time(item.get("modified_on")))
        latest_created = max(items, key=lambda item: _parse_time(item.get("created_on")))
        latest_active = max(items, key=lambda item: (_clean_text(item.get("is_active")) == "1", _parse_time(item.get("modified_on"))))
        result[source_id] = {
            "latest_modified_by_id": _clean_text(latest_modified.get("modified_by_id")),
            "latest_created_by_id": _clean_text(latest_created.get("created_by_id")),
            "latest_remark_user_name": _clean_text(latest_modified.get("user_name")),
            "latest_remark_transactor_name": _clean_text(latest_modified.get("transactor_name")),
            "latest_remark_user_or_transactor": _pick_first_non_empty(latest_modified.get("transactor_name"), latest_modified.get("user_name")),
            "active_remark_user_name": _clean_text(latest_active.get("user_name")),
            "active_remark_transactor_name": _clean_text(latest_active.get("transactor_name")),
            "active_remark_user_or_transactor": _pick_first_non_empty(latest_active.get("transactor_name"), latest_active.get("user_name")),
        }
    return result


def parse_vote_rows(path: Path, source_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_source = mapping.get("source_object_id", -1)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    activity_counter: Counter[str] = Counter()
    for row in iter_insert_rows(path):
        if current_idx >= 0 and str(_safe_get(row, current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_id = normalize_hex32(_safe_get(row, idx_source))
        if not source_id or source_id not in source_ids:
            continue
        payload = {
            "operator": _safe_get(row, mapping.get("operator", -1)),
            "operation_time": _safe_get(row, mapping.get("operation_time", -1)),
            "receive_time": _safe_get(row, mapping.get("receive_time", -1)),
            "is_valid": _safe_get(row, mapping.get("is_valid", -1)),
            "activity_name": _clean_text(_safe_get(row, mapping.get("activity_name", -1))),
        }
        grouped[source_id].append(payload)
        if payload["activity_name"]:
            activity_counter[payload["activity_name"]] += 1

    result: Dict[str, Dict[str, Any]] = {}
    for source_id, items in grouped.items():
        latest_op = max(items, key=lambda item: _parse_time(item.get("operation_time")))
        earliest_op = min(items, key=lambda item: _parse_time(item.get("operation_time")))
        latest_receive = max(items, key=lambda item: _parse_time(item.get("receive_time")))
        valid_items = [item for item in items if _clean_text(item.get("is_valid")) in {"1", "Y", "TRUE", "T"}]
        latest_valid = max(valid_items, key=lambda item: _parse_time(item.get("operation_time"))) if valid_items else {}
        result[source_id] = {
            "latest_operator": _clean_text(latest_op.get("operator")),
            "earliest_operator": _clean_text(earliest_op.get("operator")),
            "latest_receive_operator": _clean_text(latest_receive.get("operator")),
            "latest_valid_operator": _clean_text(latest_valid.get("operator")),
            "latest_activity_name": _clean_text(latest_op.get("activity_name")),
        }
    result["_activity_counter"] = dict(activity_counter.most_common(30))
    return result


def parse_distribution_rows(path: Path, source_ids: Set[str]) -> Dict[str, Dict[str, Any]]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_source = mapping.get("source_object_id", -1)
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in iter_insert_rows(path):
        if current_idx >= 0 and str(_safe_get(row, current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_id = normalize_hex32(_safe_get(row, idx_source))
        if not source_id or source_id not in source_ids:
            continue
        grouped[source_id].append(
            {
                "sender": _clean_text(_safe_get(row, mapping.get("sender", -1))),
                "operator": _clean_text(_safe_get(row, mapping.get("operator", -1))),
                "operation_time": _safe_get(row, mapping.get("operation_time", -1)),
                "created_on": _safe_get(row, mapping.get("created_on", -1)),
            }
        )

    result: Dict[str, Dict[str, Any]] = {}
    for source_id, items in grouped.items():
        sender_ids = {normalize_hex32(item.get("sender")) for item in items if normalize_hex32(item.get("sender"))}
        leaf_ops: List[str] = []
        for item in items:
            operator = _clean_text(item.get("operator"))
            operator_id = normalize_hex32(operator)
            if not operator:
                continue
            if operator_id and operator_id in sender_ids:
                continue
            if operator not in leaf_ops:
                leaf_ops.append(operator)
        latest_item = max(items, key=lambda item: _parse_time(item.get("operation_time") or item.get("created_on")))
        result[source_id] = {
            "leaf_operators": ",".join(leaf_ops),
            "leaf_count": len(leaf_ops),
            "latest_operator": _clean_text(latest_item.get("operator")),
        }
    return result


def run(excel_dir: Path, sql35_dir: Path, sql37_dir: Path, output_path: Path, temp_dir: Path) -> Dict[str, Any]:
    rows = load_file4_rows(excel_dir)
    dept_map = parse_department_map(sql35_dir / "DEPARTMENT_20260305.sql")
    user_map = parse_user_map(sql35_dir / "USER_20260305.sql", dept_map)
    roster_names = load_all_roster_names()

    temp_dir.mkdir(parents=True, exist_ok=True)
    send_path = temp_dir / "SENDRECEIVEDATA.sql"
    iics_path = temp_dir / "IICS.sql"
    iitf_path = temp_dir / "IITF.sql"
    prefilter_sql(
        sql35_dir / "SENDRECEIVEDATA_20260305.sql",
        {row["e_token"] for row in rows if row.get("e_token")},
        send_path,
    )
    send_data = parse_send_rows(send_path, {row["e_key"] for row in rows}, {row["e_key_tail"] for row in rows})
    needed_send_ids = {sid for ids in send_data["send_exact"].values() for sid in ids} | {sid for ids in send_data["send_tail"].values() for sid in ids}
    prefilter_sql(sql35_dir / "IICS_20260305.sql", needed_send_ids, iics_path)
    prefilter_sql(sql35_dir / "IITF_20260305.sql", needed_send_ids, iitf_path)
    iics = parse_child_rows(iics_path, needed_send_ids)
    iitf = parse_child_rows(iitf_path, needed_send_ids)

    for row in rows:
        exact_ids = send_data["send_exact"].get(row["e_key"], set())
        send_ids = exact_ids or send_data["send_tail"].get(row["e_key_tail"], set())
        row["send_id"] = sorted(send_ids)[0] if send_ids else ""
        iics_ids: Set[str] = set()
        iitf_ids: Set[str] = set()
        for send_id in send_ids:
            iics_ids.update(iics["send_to_ids"].get(send_id, set()))
            iitf_ids.update(iitf["send_to_ids"].get(send_id, set()))
        row["iics_id"] = best_child_id(iics_ids, iics["by_id"])
        row["iitf_id"] = best_child_id(iitf_ids, iitf["by_id"])

    branch_ids = {row["iics_id"] for row in rows if row["iics_id"]} | {row["iitf_id"] for row in rows if row["iitf_id"]}
    wf_path = temp_dir / "WORKFLOWPROCESSESBIND.sql"
    vote_path = temp_dir / "USERVOTERECORD.sql"
    dist_path = temp_dir / "DISTRIBUTERECORD.sql"
    prefilter_sql(sql37_dir / "WORKFLOWPROCESSESBIND_20260307.sql", branch_ids, wf_path)
    prefilter_sql(sql37_dir / "USERVOTERECORD_20260307.sql", branch_ids, vote_path)
    prefilter_sql(sql35_dir / "DISTRIBUTERECORD_20260305.sql", branch_ids, dist_path)
    wf = parse_workflow_rows(wf_path, branch_ids)
    vote = parse_vote_rows(vote_path, branch_ids)
    dist = parse_distribution_rows(dist_path, branch_ids)

    owner_rows = [row for row in rows if row.get("owner_raw")]

    def branch_value(row: Dict[str, Any], key_iics: str, key_iitf: str, *, prefer_iics: bool = False) -> Any:
        if row.get("a_type") == "IICS" and row.get("iics_id"):
            return (wf if key_iics.startswith("wf:") else vote if key_iics.startswith("vote:") else iics["by_id"]).get(row["iics_id"], {}).get(key_iics.split(":", 1)[-1], "")
        if row.get("a_type") == "IITF" and row.get("iitf_id"):
            return (wf if key_iitf.startswith("wf:") else vote if key_iitf.startswith("vote:") else iitf["by_id"]).get(row["iitf_id"], {}).get(key_iitf.split(":", 1)[-1], "")
        if prefer_iics and row.get("iics_id"):
            return (wf if key_iics.startswith("wf:") else vote if key_iics.startswith("vote:") else iics["by_id"]).get(row["iics_id"], {}).get(key_iics.split(":", 1)[-1], "")
        return ""

    candidates = {
        "branch_created_by": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "CREATED_BY_ID", "CREATED_BY_ID"), user_map, roster_names)),
        "branch_modified_by": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "MODIFIED_BY_ID", "MODIFIED_BY_ID"), user_map, roster_names)),
        "branch_wf_latest_modified_by": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "wf:latest_modified_by_id", "wf:latest_modified_by_id"), user_map, roster_names)),
        "branch_wf_latest_created_by": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "wf:latest_created_by_id", "wf:latest_created_by_id"), user_map, roster_names)),
        "branch_wf_latest_transactor_name": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "wf:latest_remark_transactor_name", "wf:latest_remark_transactor_name"), user_map, roster_names)),
        "branch_wf_latest_user_name": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "wf:latest_remark_user_name", "wf:latest_remark_user_name"), user_map, roster_names)),
        "branch_wf_latest_user_or_transactor": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "wf:latest_remark_user_or_transactor", "wf:latest_remark_user_or_transactor"), user_map, roster_names)),
        "branch_wf_active_user_or_transactor": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "wf:active_remark_user_or_transactor", "wf:active_remark_user_or_transactor"), user_map, roster_names)),
        "branch_vote_latest_operator": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "vote:latest_operator", "vote:latest_operator"), user_map, roster_names)),
        "branch_vote_latest_valid_operator": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "vote:latest_valid_operator", "vote:latest_valid_operator"), user_map, roster_names)),
        "branch_vote_earliest_operator": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "vote:earliest_operator", "vote:earliest_operator"), user_map, roster_names)),
        "branch_vote_latest_receive_operator": _metric(owner_rows, lambda row: _owner_match(row["owner_raw"], branch_value(row, "vote:latest_receive_operator", "vote:latest_receive_operator"), user_map, roster_names)),
        "branch_dist_latest_operator": _metric(
            owner_rows,
            lambda row: _owner_match(
                row["owner_raw"],
                (dist.get(row["iics_id"], {}) if row.get("a_type") == "IICS" else dist.get(row["iitf_id"], {}) if row.get("a_type") == "IITF" else {}).get("latest_operator", ""),
                user_map,
                roster_names,
            ),
        ),
        "branch_dist_leaf_operators_any_match": _metric(
            owner_rows,
            lambda row: _owner_match(
                row["owner_raw"],
                (dist.get(row["iics_id"], {}) if row.get("a_type") == "IICS" else dist.get(row["iitf_id"], {}) if row.get("a_type") == "IITF" else {}).get("leaf_operators", ""),
                user_map,
                roster_names,
            ),
        ),
        "branch_vote_latest_or_wf_transactor": _metric(
            owner_rows,
            lambda row: _owner_match(
                row["owner_raw"],
                _pick_first_non_empty(
                    branch_value(row, "vote:latest_operator", "vote:latest_operator"),
                    branch_value(row, "wf:latest_remark_user_or_transactor", "wf:latest_remark_user_or_transactor"),
                ),
                user_map,
                roster_names,
            ),
        ),
        "branch_vote_latest_valid_or_wf_transactor": _metric(
            owner_rows,
            lambda row: _owner_match(
                row["owner_raw"],
                _pick_first_non_empty(
                    branch_value(row, "vote:latest_valid_operator", "vote:latest_valid_operator"),
                    branch_value(row, "wf:latest_remark_user_or_transactor", "wf:latest_remark_user_or_transactor"),
                ),
                user_map,
                roster_names,
            ),
        ),
    }

    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
            "sql37_dir": str(sql37_dir),
        },
        "row_counts": {
            "file4_rows": len(rows),
            "ah_non_empty_rows": len(owner_rows),
            "send_matched_rows": sum(1 for row in rows if row.get("send_id")),
            "iics_branch_rows": sum(1 for row in rows if row.get("a_type") == "IICS" and row.get("iics_id")),
            "iitf_branch_rows": sum(1 for row in rows if row.get("a_type") == "IITF" and row.get("iitf_id")),
            "dist_iics_rows": sum(1 for row in rows if row.get("a_type") == "IICS" and row.get("iics_id") in dist),
            "dist_iitf_rows": sum(1 for row in rows if row.get("a_type") == "IITF" and row.get("iitf_id") in dist),
        },
        "top_vote_activities": vote.get("_activity_counter", {}),
        "candidates": dict(sorted(candidates.items(), key=lambda item: (-item[1]["rate"], item[0]))),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file4 AH owner chain")
    parser.add_argument("--excel-dir", required=True)
    parser.add_argument("--sql35-dir", required=True)
    parser.add_argument("--sql37-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--temp-dir", required=True)
    args = parser.parse_args()
    run(Path(args.excel_dir), Path(args.sql35_dir), Path(args.sql37_dir), Path(args.output), Path(args.temp_dir))


if __name__ == "__main__":
    main()
