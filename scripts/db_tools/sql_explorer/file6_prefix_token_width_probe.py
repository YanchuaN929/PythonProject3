"""Probe token-width tuning on top of donor-selected shared-prefix pools."""

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
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from scripts.db_tools.sql_explorer.file4_ah_owner_chain_probe import _owner_match
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import _clean_text, _office_match, _org_match
from scripts.db_tools.sql_explorer.file6_prefix_donor_probe import _load_rows
from scripts.db_tools.sql_explorer.file6_shared_prefix_family_probe import _build_user_scope_maps


SEP_RE = re.compile(r"[,，;；/、]+")


def _split_multi(value: Any) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    return [token.strip() for token in SEP_RE.split(text) if token.strip()]


def _dedupe(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _predict_top_tokens(
    train_rows: Sequence[Dict[str, Any]],
    prefix_value: str,
    field_name: str,
    topn: int,
) -> List[str]:
    if not prefix_value or topn <= 0:
        return []
    counter: Counter[str] = Counter()
    for row in train_rows:
        if _clean_text(row.get("prefix")) != prefix_value:
            continue
        for token in _split_multi(row.get(field_name)):
            counter[token] += 1
    return [token for token, _ in counter.most_common(topn)]


def _predict_names(
    predicted_v: Sequence[str],
    predicted_w: Sequence[str],
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
) -> List[str]:
    result: List[str] = []
    for token in _dedupe(predicted_v):
        for name in org_to_names.get(token, []):
            if name not in result:
                result.append(name)
    for token in _dedupe(predicted_w):
        for name in office_to_names.get(token, []):
            if name not in result:
                result.append(name)
    return result


def _metric(hit: int, total: int) -> Dict[str, Any]:
    return {
        "hit": hit,
        "total": total,
        "rate": round(hit / total, 6) if total else 0.0,
    }


def _evaluate_pool(
    subset: Sequence[Dict[str, Any]],
    pool_rows: Sequence[Dict[str, Any]],
    v_topn: int,
    w_topn: int,
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    x_hit = x_total = 0
    v_hit = v_total = 0
    w_hit = w_total = 0
    predicted_name_sizes: List[int] = []

    for row in subset:
        train_rows = [candidate for candidate in pool_rows if candidate is not row]
        predicted_v = _predict_top_tokens(train_rows, _clean_text(row.get("prefix")), "v_raw", v_topn)
        predicted_w = _predict_top_tokens(train_rows, _clean_text(row.get("prefix")), "w_raw", w_topn)
        predicted_names = _predict_names(predicted_v, predicted_w, org_to_names, office_to_names)
        predicted_name_sizes.append(len(predicted_names))

        if _clean_text(row.get("x_raw")):
            x_total += 1
            if _owner_match(row["x_raw"], ",".join(predicted_names), user_map, roster_names):
                x_hit += 1
        if _clean_text(row.get("v_raw")):
            v_total += 1
            if _org_match(row["v_raw"], predicted_v):
                v_hit += 1
        if _clean_text(row.get("w_raw")):
            w_total += 1
            if _office_match(row["w_raw"], predicted_w):
                w_hit += 1

    return {
        "metrics": {
            "X": _metric(x_hit, x_total),
            "V": _metric(v_hit, v_total),
            "W": _metric(w_hit, w_total),
        },
        "predicted_name_scope": {
            "avg_count": round(sum(predicted_name_sizes) / len(predicted_name_sizes), 2) if predicted_name_sizes else 0.0,
            "max_count": max(predicted_name_sizes) if predicted_name_sizes else 0,
        },
    }


def build_report(
    detail_path: Path,
    donor_report_path: Path,
    sql35_dir: Path,
    max_topn: int,
    doc_types: Sequence[str] | None = None,
) -> Dict[str, Any]:
    by_type = _load_rows(detail_path)
    donor_report = json.loads(donor_report_path.read_text(encoding="utf-8"))
    org_to_names, office_to_names, user_map, roster_names = _build_user_scope_maps(sql35_dir)
    doc_type_filter = {_clean_text(item) for item in (doc_types or []) if _clean_text(item)}

    target_reports: Dict[str, Any] = {}
    for target_type, payload in donor_report.get("target_reports", {}).items():
        if doc_type_filter and _clean_text(target_type) not in doc_type_filter:
            continue
        top_combos = payload.get("top_combos") or []
        if not top_combos:
            continue
        donor_types = top_combos[0].get("donor_types") or []
        subset = by_type.get(target_type, [])
        if not subset:
            continue
        pool_rows = [row for doc_type in (target_type, *donor_types) for row in by_type.get(doc_type, [])]
        baseline = _evaluate_pool(
            subset,
            pool_rows,
            3,
            3,
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )

        base_metrics = baseline["metrics"]
        best_report = {
            "v_topn": 3,
            "w_topn": 3,
            **baseline,
            "delta_sum_vs_3_3": 0.0,
        }
        for v_topn in range(1, max_topn + 1):
            for w_topn in range(1, max_topn + 1):
                candidate = _evaluate_pool(
                    subset,
                    pool_rows,
                    v_topn,
                    w_topn,
                    org_to_names,
                    office_to_names,
                    user_map,
                    roster_names,
                )
                metrics = candidate["metrics"]
                delta_sum = round(
                    (metrics["X"]["rate"] - base_metrics["X"]["rate"])
                    + (metrics["V"]["rate"] - base_metrics["V"]["rate"])
                    + (metrics["W"]["rate"] - base_metrics["W"]["rate"]),
                    6,
                )
                candidate_report = {
                    "v_topn": v_topn,
                    "w_topn": w_topn,
                    **candidate,
                    "delta_sum_vs_3_3": delta_sum,
                }
                score = (
                    delta_sum,
                    metrics["V"]["rate"],
                    metrics["W"]["rate"],
                    metrics["X"]["rate"],
                    -candidate["predicted_name_scope"]["avg_count"],
                )
                best_score = (
                    best_report["delta_sum_vs_3_3"],
                    best_report["metrics"]["V"]["rate"],
                    best_report["metrics"]["W"]["rate"],
                    best_report["metrics"]["X"]["rate"],
                    -best_report["predicted_name_scope"]["avg_count"],
                )
                if score > best_score:
                    best_report = candidate_report

        target_reports[target_type] = {
            "donor_types": donor_types,
            "baseline_combo_3_3": baseline,
            "best_token_width": best_report,
        }

    return {
        "input": str(detail_path),
        "donor_report": str(donor_report_path),
        "sql35_dir": str(sql35_dir),
        "max_topn": max_topn,
        "doc_type_filter": sorted(doc_type_filter),
        "target_reports": target_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe token-width tuning on top of donor-selected pools.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--donor-report", type=Path, required=True, help="JSON from file6_prefix_donor_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-topn", type=int, default=5)
    parser.add_argument("--doc-types", nargs="*", help="Optional A-column doc types. Supports comma-separated values.")
    args = parser.parse_args()

    doc_types: List[str] = []
    for raw_value in args.doc_types or []:
        doc_types.extend([item.strip() for item in raw_value.split(",") if item.strip()])

    report = build_report(
        args.input,
        args.donor_report,
        args.sql35_dir,
        max_topn=args.max_topn,
        doc_types=doc_types or None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "target_count": len(report["target_reports"]),
                "max_topn": args.max_topn,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
