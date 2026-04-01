"""Probe donor document types for shared-prefix routing."""

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
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Sequence, Tuple

from scripts.db_tools.sql_explorer.file6_shared_prefix_family_probe import (
    _build_user_scope_maps,
    _evaluate_pool,
    _prefix,
)
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import _clean_text


def _load_rows(detail_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    payload = json.loads(detail_path.read_text(encoding="utf-8"))
    by_type: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in payload.get("rows", []):
        doc_type = _clean_text(row.get("a_raw"))
        if not doc_type:
            continue
        item = dict(row)
        item["prefix"] = _prefix(row.get("e_raw"))
        by_type[doc_type].append(item)
    return by_type


def _shared_prefix_count(left_rows: Sequence[Dict[str, Any]], right_rows: Sequence[Dict[str, Any]]) -> int:
    left = {_clean_text(row.get("prefix")) for row in left_rows if _clean_text(row.get("prefix"))}
    right = {_clean_text(row.get("prefix")) for row in right_rows if _clean_text(row.get("prefix"))}
    return len(left & right)


def _combo_report(
    target_type: str,
    donor_types: Tuple[str, ...],
    by_type: Dict[str, List[Dict[str, Any]]],
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    subset = by_type[target_type]
    pool_rows = [row for doc_type in (target_type, *donor_types) for row in by_type.get(doc_type, [])]
    payload = _evaluate_pool(
        subset,
        pool_rows,
        org_to_names,
        office_to_names,
        user_map,
        roster_names,
    )
    return {
        "target_type": target_type,
        "donor_types": list(donor_types),
        "pool_row_count": len(pool_rows),
        **payload,
    }


def build_report(
    detail_path: Path,
    sql35_dir: Path,
    max_combo_size: int,
    min_shared_prefixes: int,
) -> Dict[str, Any]:
    by_type = _load_rows(detail_path)
    org_to_names, office_to_names, user_map, roster_names = _build_user_scope_maps(sql35_dir)

    target_reports: Dict[str, Any] = {}
    for target_type, target_rows in sorted(by_type.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        baseline = _combo_report(
            target_type,
            (),
            by_type,
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )
        donor_candidates = [
            donor_type
            for donor_type, donor_rows in by_type.items()
            if donor_type != target_type and _shared_prefix_count(target_rows, donor_rows) >= min_shared_prefixes
        ]

        combo_reports: List[Dict[str, Any]] = []
        max_size = min(max_combo_size, len(donor_candidates))
        for combo_size in range(1, max_size + 1):
            for donor_types in combinations(sorted(donor_candidates), combo_size):
                combo_reports.append(
                    _combo_report(
                        target_type,
                        donor_types,
                        by_type,
                        org_to_names,
                        office_to_names,
                        user_map,
                        roster_names,
                    )
                )

        base_metrics = baseline["metrics"]
        for report in combo_reports:
            metrics = report["metrics"]
            report["delta_sum"] = round(
                (metrics["X"]["rate"] - base_metrics["X"]["rate"])
                + (metrics["V"]["rate"] - base_metrics["V"]["rate"])
                + (metrics["W"]["rate"] - base_metrics["W"]["rate"]),
                6,
            )

        combo_reports.sort(key=lambda item: (item["delta_sum"], -item["predicted_name_scope"]["avg_count"]), reverse=True)
        target_reports[target_type] = {
            "row_count": len(target_rows),
            "baseline": baseline,
            "donor_candidates": donor_candidates,
            "top_combos": combo_reports[:12],
        }

    return {
        "input": str(detail_path),
        "sql35_dir": str(sql35_dir),
        "max_combo_size": max_combo_size,
        "min_shared_prefixes": min_shared_prefixes,
        "target_reports": target_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe donor document types for shared-prefix routing.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-combo-size", type=int, default=2)
    parser.add_argument("--min-shared-prefixes", type=int, default=3)
    args = parser.parse_args()

    report = build_report(
        args.input,
        args.sql35_dir,
        max_combo_size=args.max_combo_size,
        min_shared_prefixes=args.min_shared_prefixes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "target_count": len(report["target_reports"]),
                "max_combo_size": args.max_combo_size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
