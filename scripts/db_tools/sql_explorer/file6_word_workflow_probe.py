"""Strict Word-style workflow candidate probe for file6 SEND rows."""

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
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from scripts.db_tools.sql_explorer.file4_ah_owner_chain_probe import _owner_match
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import (
    _metric,
    _office_match,
    _org_match,
    _resolve_distribution_entities,
    parse_department_tree,
)
from scripts.db_tools.sql_explorer.roster import load_all_roster_names
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import parse_user_map


CandidateGetter = Callable[[Dict[str, Any]], List[str]]


def _build_candidate_getters(rows: Sequence[Dict[str, Any]]) -> Dict[str, CandidateGetter]:
    candidates: Dict[str, CandidateGetter] = {
        "workflow_all": lambda row: list(row.get("workflow_all_actor_values", [])),
        "workflow_active": lambda row: list(row.get("workflow_active_actor_values", [])),
        "vote_all": lambda row: list(row.get("vote_all_operators", [])),
        "vote_valid": lambda row: list(row.get("vote_valid_operators", [])),
        "active_plus_valid": lambda row: list(
            dict.fromkeys(list(row.get("workflow_active_actor_values", [])) + list(row.get("vote_valid_operators", [])))
        ),
    }

    activity_names = sorted(
        {name for row in rows for name in row.get("vote_valid_activity_operators", {}).keys()}
        | {name for row in rows for name in row.get("vote_activity_operators", {}).keys()}
    )
    for activity_name in activity_names:
        candidates[f"activity:{activity_name}"] = (
            lambda row, activity_name=activity_name: list(row.get("vote_valid_activity_operators", {}).get(activity_name, []))
            or list(row.get("vote_activity_operators", {}).get(activity_name, []))
        )

    return candidates


def _resolve_candidate_fields(
    rows: Sequence[Dict[str, Any]],
    candidate_getters: Dict[str, CandidateGetter],
    user_map: Dict[str, Dict[str, Any]],
    department_map: Dict[str, Dict[str, Any]],
) -> None:
    cache: Dict[tuple[str, ...], Dict[str, List[str]]] = {}
    for row in rows:
        for candidate_name, getter in candidate_getters.items():
            raw_values = getter(row)
            key = tuple(raw_values)
            if key not in cache:
                cache[key] = _resolve_distribution_entities(raw_values, user_map, department_map)
            resolved = cache[key]
            row[f"__{candidate_name}_names"] = resolved["names"]
            row[f"__{candidate_name}_orgs"] = resolved["org_values"]
            row[f"__{candidate_name}_offices"] = resolved["office_values"]


def _candidate_metric_bundle(
    rows: Sequence[Dict[str, Any]],
    candidate_name: str,
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    return {
        "X": _metric(
            rows,
            "x_raw",
            lambda row, candidate_name=candidate_name: ",".join(row[f"__{candidate_name}_names"]),
            lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
        ),
        "V": _metric(rows, "v_raw", lambda row, candidate_name=candidate_name: row[f"__{candidate_name}_orgs"], _org_match),
        "W": _metric(rows, "w_raw", lambda row, candidate_name=candidate_name: row[f"__{candidate_name}_offices"], _office_match),
    }


def _best_type_candidate(
    rows: Sequence[Dict[str, Any]],
    candidate_getters: Dict[str, CandidateGetter],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    best_name = ""
    best_metrics: Dict[str, Any] = {}
    best_rank: tuple[float, float, float, int, int, int] | None = None
    for candidate_name in candidate_getters:
        metrics = _candidate_metric_bundle(rows, candidate_name, user_map, roster_names)
        rank = (
            float(metrics["X"]["rate"]),
            float(metrics["V"]["rate"]),
            float(metrics["W"]["rate"]),
            int(metrics["X"]["hit"]),
            int(metrics["V"]["hit"]),
            int(metrics["W"]["hit"]),
        )
        if best_rank is None or rank > best_rank:
            best_name = candidate_name
            best_metrics = metrics
            best_rank = rank
    return {"candidate": best_name, "metrics": best_metrics}


def run(detail_input: Path, sql35_dir: Path, output_path: Path) -> Dict[str, Any]:
    payload = json.loads(detail_input.read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = payload["rows"]

    department_map = parse_department_tree(sql35_dir / "DEPARTMENT_20260305.sql")
    user_map = parse_user_map(sql35_dir / "USER_20260305.sql", department_map)
    roster_names = load_all_roster_names()

    candidate_getters = _build_candidate_getters(rows)
    _resolve_candidate_fields(rows, candidate_getters, user_map, department_map)

    base_candidates = ["workflow_all", "workflow_active", "vote_all", "vote_valid", "active_plus_valid"]
    base_candidate_metrics = {
        name: _candidate_metric_bundle(rows, name, user_map, roster_names) for name in base_candidates
    }

    type_best_candidates: Dict[str, Any] = {}
    for doc_type in sorted({str(row.get("a_raw") or "") for row in rows}):
        doc_rows = [row for row in rows if str(row.get("a_raw") or "") == doc_type]
        best = _best_type_candidate(doc_rows, candidate_getters, user_map, roster_names)
        type_best_candidates[doc_type] = {
            "row_count": len(doc_rows),
            "candidate": best["candidate"],
            "metrics": best["metrics"],
        }

    for row in rows:
        selected = type_best_candidates[str(row.get("a_raw") or "")]["candidate"]
        row["__selected_names"] = row[f"__{selected}_names"]
        row["__selected_orgs"] = row[f"__{selected}_orgs"]
        row["__selected_offices"] = row[f"__{selected}_offices"]

    selected_overall_metrics = {
        "X": _metric(
            rows,
            "x_raw",
            lambda row: ",".join(row["__selected_names"]),
            lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
        ),
        "V": _metric(rows, "v_raw", lambda row: row["__selected_orgs"], _org_match),
        "W": _metric(rows, "w_raw", lambda row: row["__selected_offices"], _office_match),
    }

    result = {
        "inputs": {
            "detail_input": str(detail_input),
            "sql35_dir": str(sql35_dir),
            "logic_mode": "word_strict_workflow_candidates",
        },
        "candidate_space": {
            "base_candidates": base_candidates,
            "activity_candidate_count": len(candidate_getters) - len(base_candidates),
            "activity_candidates": sorted(name for name in candidate_getters if name.startswith("activity:")),
        },
        "base_candidate_metrics": base_candidate_metrics,
        "type_best_candidates": type_best_candidates,
        "selected_overall_metrics": selected_overall_metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe strict Word-style workflow candidates for file6 SEND rows.")
    parser.add_argument(
        "--detail-input",
        type=Path,
        default=Path("document/file6_send_workflow_probe_20260313_rel4_detail_rows.json"),
    )
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, default=Path("document/file6_word_workflow_probe_20260321.json"))
    args = parser.parse_args()

    result = run(args.detail_input, args.sql35_dir, args.output)
    selected = result["selected_overall_metrics"]
    print(
        json.dumps(
            {
                "output": str(args.output),
                "x_rate": selected["X"]["rate"],
                "v_rate": selected["V"]["rate"],
                "w_rate": selected["W"]["rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
