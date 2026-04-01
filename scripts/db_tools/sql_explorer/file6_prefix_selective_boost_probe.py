"""Probe prefix-selective token-width boosts on top of donor-selected pools."""

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
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence

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


def _evaluate_row(
    row: Dict[str, Any],
    pool_rows: Sequence[Dict[str, Any]],
    v_topn: int,
    w_topn: int,
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    train_rows = [candidate for candidate in pool_rows if candidate is not row]
    prefix_value = _clean_text(row.get("prefix"))
    predicted_v = _predict_top_tokens(train_rows, prefix_value, "v_raw", v_topn)
    predicted_w = _predict_top_tokens(train_rows, prefix_value, "w_raw", w_topn)
    predicted_names = _predict_names(predicted_v, predicted_w, org_to_names, office_to_names)
    return {
        "x_hit": bool(_clean_text(row.get("x_raw"))) and _owner_match(row["x_raw"], ",".join(predicted_names), user_map, roster_names),
        "v_hit": bool(_clean_text(row.get("v_raw"))) and _org_match(row["v_raw"], predicted_v),
        "w_hit": bool(_clean_text(row.get("w_raw"))) and _office_match(row["w_raw"], predicted_w),
        "scope_count": len(predicted_names),
    }


def _metric(hit: int, total: int) -> Dict[str, Any]:
    return {
        "hit": hit,
        "total": total,
        "rate": round(hit / total, 6) if total else 0.0,
    }


def _evaluate_pool(
    subset: Sequence[Dict[str, Any]],
    pool_rows: Sequence[Dict[str, Any]],
    base_v_topn: int,
    base_w_topn: int,
    extra_v_topn: int,
    extra_w_topn: int,
    boosted_prefixes: set[str],
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
        prefix_value = _clean_text(row.get("prefix"))
        use_extra = prefix_value in boosted_prefixes
        row_report = _evaluate_row(
            row,
            pool_rows,
            extra_v_topn if use_extra else base_v_topn,
            extra_w_topn if use_extra else base_w_topn,
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )
        predicted_name_sizes.append(row_report["scope_count"])
        if _clean_text(row.get("x_raw")):
            x_total += 1
            x_hit += int(row_report["x_hit"])
        if _clean_text(row.get("v_raw")):
            v_total += 1
            v_hit += int(row_report["v_hit"])
        if _clean_text(row.get("w_raw")):
            w_total += 1
            w_hit += int(row_report["w_hit"])

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


def _candidate_prefixes(
    subset: Sequence[Dict[str, Any]],
    pool_rows: Sequence[Dict[str, Any]],
    base_v_topn: int,
    base_w_topn: int,
    extra_v_topn: int,
    extra_w_topn: int,
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> List[Dict[str, Any]]:
    prefix_payloads: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "row_count": 0,
            "delta_sum": 0,
            "base": {"x": 0, "v": 0, "w": 0},
            "extra": {"x": 0, "v": 0, "w": 0},
            "scope_base": [],
            "scope_extra": [],
        }
    )
    for row in subset:
        prefix_value = _clean_text(row.get("prefix"))
        if not prefix_value:
            continue
        base_report = _evaluate_row(
            row,
            pool_rows,
            base_v_topn,
            base_w_topn,
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )
        extra_report = _evaluate_row(
            row,
            pool_rows,
            extra_v_topn,
            extra_w_topn,
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )
        payload = prefix_payloads[prefix_value]
        payload["row_count"] += 1
        for key, field in [("x_hit", "x"), ("v_hit", "v"), ("w_hit", "w")]:
            payload["base"][field] += int(base_report[key])
            payload["extra"][field] += int(extra_report[key])
        payload["scope_base"].append(base_report["scope_count"])
        payload["scope_extra"].append(extra_report["scope_count"])

    result: List[Dict[str, Any]] = []
    for prefix_value, payload in prefix_payloads.items():
        delta_sum = (
            (payload["extra"]["x"] - payload["base"]["x"])
            + (payload["extra"]["v"] - payload["base"]["v"])
            + (payload["extra"]["w"] - payload["base"]["w"])
        )
        if delta_sum <= 0:
            continue
        payload["delta_sum"] = delta_sum
        payload["prefix"] = prefix_value
        payload["avg_scope_base"] = round(sum(payload["scope_base"]) / len(payload["scope_base"]), 2)
        payload["avg_scope_extra"] = round(sum(payload["scope_extra"]) / len(payload["scope_extra"]), 2)
        result.append(payload)
    result.sort(key=lambda item: (item["delta_sum"], item["row_count"], -item["avg_scope_extra"]), reverse=True)
    return result


def build_report(
    detail_path: Path,
    width_report_path: Path,
    sql35_dir: Path,
    scope_growth_ratio: float,
    doc_types: Sequence[str] | None = None,
) -> Dict[str, Any]:
    by_type = _load_rows(detail_path)
    width_report = json.loads(width_report_path.read_text(encoding="utf-8"))
    org_to_names, office_to_names, user_map, roster_names = _build_user_scope_maps(sql35_dir)
    doc_type_filter = {_clean_text(item) for item in (doc_types or []) if _clean_text(item)}

    target_reports: Dict[str, Any] = {}
    for target_type, payload in width_report.get("target_reports", {}).items():
        if doc_type_filter and _clean_text(target_type) not in doc_type_filter:
            continue
        best_token_width = payload.get("best_token_width") or {}
        base_v_topn = 3
        base_w_topn = 3
        extra_v_topn = int(best_token_width.get("v_topn") or 3)
        extra_w_topn = int(best_token_width.get("w_topn") or 3)
        if extra_v_topn == base_v_topn and extra_w_topn == base_w_topn:
            continue

        donor_types = payload.get("donor_types") or []
        subset = by_type.get(target_type, [])
        if not subset:
            continue
        pool_rows = [row for doc_type in (target_type, *donor_types) for row in by_type.get(doc_type, [])]

        base_report = _evaluate_pool(
            subset,
            pool_rows,
            base_v_topn,
            base_w_topn,
            extra_v_topn,
            extra_w_topn,
            set(),
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )
        candidate_prefixes = _candidate_prefixes(
            subset,
            pool_rows,
            base_v_topn,
            base_w_topn,
            extra_v_topn,
            extra_w_topn,
            org_to_names,
            office_to_names,
            user_map,
            roster_names,
        )
        candidate_prefix_names = [item["prefix"] for item in candidate_prefixes]
        if len(candidate_prefix_names) > 12:
            continue

        best_unrestricted = {
            "boosted_prefixes": [],
            **base_report,
        }
        best_under_limit = None
        scope_limit = round(base_report["predicted_name_scope"]["avg_count"] * scope_growth_ratio, 2)

        for size in range(len(candidate_prefix_names) + 1):
            for combo in combinations(candidate_prefix_names, size):
                boosted_prefixes = set(combo)
                candidate_report = _evaluate_pool(
                    subset,
                    pool_rows,
                    base_v_topn,
                    base_w_topn,
                    extra_v_topn,
                    extra_w_topn,
                    boosted_prefixes,
                    org_to_names,
                    office_to_names,
                    user_map,
                    roster_names,
                )
                candidate_payload = {
                    "boosted_prefixes": list(combo),
                    **candidate_report,
                }
                score = (
                    candidate_report["metrics"]["V"]["hit"],
                    candidate_report["metrics"]["W"]["hit"],
                    candidate_report["metrics"]["X"]["hit"],
                    -candidate_report["predicted_name_scope"]["avg_count"],
                    -candidate_report["predicted_name_scope"]["max_count"],
                )
                best_score = (
                    best_unrestricted["metrics"]["V"]["hit"],
                    best_unrestricted["metrics"]["W"]["hit"],
                    best_unrestricted["metrics"]["X"]["hit"],
                    -best_unrestricted["predicted_name_scope"]["avg_count"],
                    -best_unrestricted["predicted_name_scope"]["max_count"],
                )
                if score > best_score:
                    best_unrestricted = candidate_payload

                if candidate_report["predicted_name_scope"]["avg_count"] <= scope_limit:
                    best_limit_score = None
                    if best_under_limit is not None:
                        best_limit_score = (
                            best_under_limit["metrics"]["V"]["hit"],
                            best_under_limit["metrics"]["W"]["hit"],
                            best_under_limit["metrics"]["X"]["hit"],
                            -best_under_limit["predicted_name_scope"]["avg_count"],
                            -best_under_limit["predicted_name_scope"]["max_count"],
                        )
                    if best_limit_score is None or score > best_limit_score:
                        best_under_limit = candidate_payload

        target_reports[target_type] = {
            "donor_types": donor_types,
            "base_token_width": {"v_topn": base_v_topn, "w_topn": base_w_topn},
            "extra_token_width": {"v_topn": extra_v_topn, "w_topn": extra_w_topn},
            "scope_growth_ratio": scope_growth_ratio,
            "scope_limit": scope_limit,
            "candidate_prefixes": candidate_prefixes,
            "best_unrestricted": best_unrestricted,
            "best_under_limit": best_under_limit,
        }

    return {
        "input": str(detail_path),
        "width_report": str(width_report_path),
        "sql35_dir": str(sql35_dir),
        "scope_growth_ratio": scope_growth_ratio,
        "doc_type_filter": sorted(doc_type_filter),
        "target_reports": target_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe prefix-selective token-width boosts.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--width-report", type=Path, required=True, help="JSON from file6_prefix_token_width_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope-growth-ratio", type=float, default=1.1)
    parser.add_argument("--doc-types", nargs="*", help="Optional A-column doc types. Supports comma-separated values.")
    args = parser.parse_args()

    doc_types: List[str] = []
    for raw_value in args.doc_types or []:
        doc_types.extend([item.strip() for item in raw_value.split(",") if item.strip()])

    report = build_report(
        args.input,
        args.width_report,
        args.sql35_dir,
        scope_growth_ratio=args.scope_growth_ratio,
        doc_types=doc_types or None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "target_count": len(report["target_reports"]),
                "scope_growth_ratio": args.scope_growth_ratio,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
