"""Run full-file composite simulation for file6 SEND-side rows."""

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Sequence

from scripts.db_tools.sql_explorer.file4_ah_owner_chain_probe import _owner_match
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import _clean_text, _office_match, _org_match
from scripts.db_tools.sql_explorer.file6_prefix_donor_probe import _load_rows
from scripts.db_tools.sql_explorer.file6_shared_prefix_family_probe import _build_user_scope_maps


SEP_RE = re.compile(r"[,，;；/、]+")


@dataclass(frozen=True)
class PrefixCompositeRule:
    donor_types: tuple[str, ...] = ()
    default_v_topn: int = 0
    default_w_topn: int = 0
    boost_v_topn: int = 0
    boost_w_topn: int = 0
    boosted_prefixes: tuple[str, ...] = ()


STABLE_RULES: Dict[str, PrefixCompositeRule] = {
    "TA": PrefixCompositeRule(
        donor_types=("CR", "文件传递单"),
        default_v_topn=3,
        default_w_topn=1,
    ),
    "CR": PrefixCompositeRule(
        donor_types=("TA", "文件传递单"),
        default_v_topn=3,
        default_w_topn=1,
    ),
    "文件传递单": PrefixCompositeRule(
        donor_types=("TA", "审查意见答复单"),
        default_v_topn=3,
        default_w_topn=3,
        boost_v_topn=5,
        boost_w_topn=3,
        boosted_prefixes=("JAPDB", "FAPAK", "FAPBH", "SMPCJ"),
    ),
    "审查意见答复单": PrefixCompositeRule(
        donor_types=("文件传递单",),
        default_v_topn=3,
        default_w_topn=3,
        boost_v_topn=3,
        boost_w_topn=4,
        boosted_prefixes=("EDES",),
    ),
    "FU通知单": PrefixCompositeRule(
        donor_types=("文件传递单",),
        default_v_topn=2,
        default_w_topn=1,
    ),
    "外发纪要": PrefixCompositeRule(
        donor_types=("图文传真",),
        default_v_topn=1,
        default_w_topn=5,
    ),
    "NCR": PrefixCompositeRule(
        donor_types=("文件传递单",),
        default_v_topn=3,
        default_w_topn=1,
    ),
    "图文传真": PrefixCompositeRule(
        donor_types=("外发纪要", "审查意见单"),
        default_v_topn=3,
        default_w_topn=3,
        boost_v_topn=5,
        boost_w_topn=4,
        boosted_prefixes=("ECZB", "ECZS"),
    ),
}


EXPERIMENTAL_RULES: Dict[str, PrefixCompositeRule] = {
    **STABLE_RULES,
    "图文传真": PrefixCompositeRule(
        donor_types=("外发纪要", "审查意见单"),
        default_v_topn=3,
        default_w_topn=3,
        boost_v_topn=5,
        boost_w_topn=4,
        boosted_prefixes=("ECZB", "ECZS", "YBANY", "FADGB"),
    ),
}


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


def _get_rule(
    doc_type: str,
    profile: str,
) -> PrefixCompositeRule | None:
    key = _clean_text(doc_type)
    if profile == "stable":
        return STABLE_RULES.get(key)
    if profile == "experimental":
        return EXPERIMENTAL_RULES.get(key)
    return None


def _build_type_pools(rows_by_type: Mapping[str, List[Dict[str, Any]]], rules: Mapping[str, PrefixCompositeRule]) -> Dict[str, List[Dict[str, Any]]]:
    pools: Dict[str, List[Dict[str, Any]]] = {}
    for doc_type, rule in rules.items():
        pool_rows: List[Dict[str, Any]] = []
        for donor_type in (doc_type, *rule.donor_types):
            pool_rows.extend(rows_by_type.get(_clean_text(donor_type), []))
        pools[_clean_text(doc_type)] = pool_rows
    return pools


def _simulate_profile(
    rows: Sequence[Dict[str, Any]],
    rows_by_type: Mapping[str, List[Dict[str, Any]]],
    profile: str,
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    rules = STABLE_RULES if profile == "stable" else EXPERIMENTAL_RULES if profile == "experimental" else {}
    type_pools = _build_type_pools(rows_by_type, rules)

    x_hit = x_total = 0
    v_hit = v_total = 0
    w_hit = w_total = 0
    x_delta = v_delta = w_delta = 0
    changed_row_count = 0
    by_type_counts: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    samples: List[Dict[str, Any]] = []

    for row in rows:
        doc_type = _clean_text(row.get("a_raw"))
        rule = _get_rule(doc_type, profile)
        prefix_pred_v: List[str] = []
        prefix_pred_w: List[str] = []
        prefix_pred_names: List[str] = []
        prefix_applied = False
        if rule:
            pool_rows = type_pools.get(doc_type, [])
            prefix_value = _clean_text(row.get("prefix"))
            boosted_prefixes = set(rule.boosted_prefixes)
            use_boost = prefix_value in boosted_prefixes and rule.boost_v_topn > 0 and rule.boost_w_topn > 0
            v_topn = rule.boost_v_topn if use_boost else rule.default_v_topn
            w_topn = rule.boost_w_topn if use_boost else rule.default_w_topn
            train_rows = [candidate for candidate in pool_rows if candidate is not row]
            prefix_pred_v = _predict_top_tokens(train_rows, prefix_value, "v_raw", v_topn)
            prefix_pred_w = _predict_top_tokens(train_rows, prefix_value, "w_raw", w_topn)
            prefix_pred_names = _predict_names(prefix_pred_v, prefix_pred_w, org_to_names, office_to_names)
            prefix_applied = bool(prefix_pred_v or prefix_pred_w or prefix_pred_names)

        workflow_people = _dedupe(row.get("workflow_people_all") or [])
        workflow_orgs = _dedupe(row.get("workflow_org_values") or [])
        workflow_offices = _dedupe(row.get("workflow_office_values") or [])
        composite_people = _dedupe([*workflow_people, *prefix_pred_names])
        composite_orgs = _dedupe([*workflow_orgs, *prefix_pred_v])
        composite_offices = _dedupe([*workflow_offices, *prefix_pred_w])

        baseline_x = baseline_v = baseline_w = False
        composite_x = composite_v = composite_w = False
        if _clean_text(row.get("x_raw")):
            x_total += 1
            baseline_x = _owner_match(row["x_raw"], ",".join(workflow_people), user_map, roster_names)
            composite_x = _owner_match(row["x_raw"], ",".join(composite_people), user_map, roster_names)
            x_hit += int(composite_x)
            x_delta += int(composite_x) - int(baseline_x)
        if _clean_text(row.get("v_raw")):
            v_total += 1
            baseline_v = _org_match(row["v_raw"], workflow_orgs)
            composite_v = _org_match(row["v_raw"], composite_orgs)
            v_hit += int(composite_v)
            v_delta += int(composite_v) - int(baseline_v)
        if _clean_text(row.get("w_raw")):
            w_total += 1
            baseline_w = _office_match(row["w_raw"], workflow_offices)
            composite_w = _office_match(row["w_raw"], composite_offices)
            w_hit += int(composite_w)
            w_delta += int(composite_w) - int(baseline_w)

        if composite_x != baseline_x or composite_v != baseline_v or composite_w != baseline_w:
            changed_row_count += 1
            if len(samples) < 40:
                samples.append(
                    {
                        "a_raw": row.get("a_raw"),
                        "e_raw": row.get("e_raw"),
                        "excel_row": row.get("excel_row"),
                        "prefix": row.get("prefix"),
                        "profile": profile,
                        "workflow_org_values": workflow_orgs,
                        "workflow_office_values": workflow_offices,
                        "prefix_pred_v": prefix_pred_v,
                        "prefix_pred_w": prefix_pred_w,
                        "prefix_pred_names": prefix_pred_names[:30],
                        "baseline_hits": {"X": baseline_x, "V": baseline_v, "W": baseline_w},
                        "composite_hits": {"X": composite_x, "V": composite_v, "W": composite_w},
                    }
                )

        by_type = by_type_counts[doc_type]
        by_type["row_count"] += 1
        by_type["rows_with_prefix_rule"] += int(rule is not None)
        by_type["rows_with_prefix_prediction"] += int(prefix_applied)
        by_type["X_hit"] += int(composite_x)
        by_type["X_total"] += int(bool(_clean_text(row.get("x_raw"))))
        by_type["V_hit"] += int(composite_v)
        by_type["V_total"] += int(bool(_clean_text(row.get("v_raw"))))
        by_type["W_hit"] += int(composite_w)
        by_type["W_total"] += int(bool(_clean_text(row.get("w_raw"))))
        by_type["X_delta"] += int(composite_x) - int(baseline_x)
        by_type["V_delta"] += int(composite_v) - int(baseline_v)
        by_type["W_delta"] += int(composite_w) - int(baseline_w)

    by_type_payload: Dict[str, Any] = {}
    for doc_type, counts in sorted(by_type_counts.items()):
        by_type_payload[doc_type] = {
            "row_count": counts["row_count"],
            "rows_with_prefix_rule": counts["rows_with_prefix_rule"],
            "rows_with_prefix_prediction": counts["rows_with_prefix_prediction"],
            "metrics": {
                "X": _metric(counts["X_hit"], counts["X_total"]),
                "V": _metric(counts["V_hit"], counts["V_total"]),
                "W": _metric(counts["W_hit"], counts["W_total"]),
            },
            "delta_vs_workflow": {
                "X_hit_delta": counts["X_delta"],
                "V_hit_delta": counts["V_delta"],
                "W_hit_delta": counts["W_delta"],
            },
        }

    return {
        "metrics": {
            "X": _metric(x_hit, x_total),
            "V": _metric(v_hit, v_total),
            "W": _metric(w_hit, w_total),
        },
        "delta_vs_workflow": {
            "X_hit_delta": x_delta,
            "V_hit_delta": v_delta,
            "W_hit_delta": w_delta,
            "changed_row_count": changed_row_count,
        },
        "by_type": by_type_payload,
        "samples": samples,
    }


def _workflow_baseline(
    rows: Sequence[Dict[str, Any]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    x_hit = x_total = 0
    v_hit = v_total = 0
    w_hit = w_total = 0
    by_type_counts: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        doc_type = _clean_text(row.get("a_raw"))
        workflow_people = _dedupe(row.get("workflow_people_all") or [])
        workflow_orgs = _dedupe(row.get("workflow_org_values") or [])
        workflow_offices = _dedupe(row.get("workflow_office_values") or [])
        x_hit_flag = v_hit_flag = w_hit_flag = False
        if _clean_text(row.get("x_raw")):
            x_total += 1
            x_hit_flag = _owner_match(row["x_raw"], ",".join(workflow_people), user_map, roster_names)
            x_hit += int(x_hit_flag)
        if _clean_text(row.get("v_raw")):
            v_total += 1
            v_hit_flag = _org_match(row["v_raw"], workflow_orgs)
            v_hit += int(v_hit_flag)
        if _clean_text(row.get("w_raw")):
            w_total += 1
            w_hit_flag = _office_match(row["w_raw"], workflow_offices)
            w_hit += int(w_hit_flag)

        by_type = by_type_counts[doc_type]
        by_type["row_count"] += 1
        by_type["X_hit"] += int(x_hit_flag)
        by_type["X_total"] += int(bool(_clean_text(row.get("x_raw"))))
        by_type["V_hit"] += int(v_hit_flag)
        by_type["V_total"] += int(bool(_clean_text(row.get("v_raw"))))
        by_type["W_hit"] += int(w_hit_flag)
        by_type["W_total"] += int(bool(_clean_text(row.get("w_raw"))))

    by_type_payload: Dict[str, Any] = {}
    for doc_type, counts in sorted(by_type_counts.items()):
        by_type_payload[doc_type] = {
            "row_count": counts["row_count"],
            "metrics": {
                "X": _metric(counts["X_hit"], counts["X_total"]),
                "V": _metric(counts["V_hit"], counts["V_total"]),
                "W": _metric(counts["W_hit"], counts["W_total"]),
            },
        }
    return {
        "metrics": {
            "X": _metric(x_hit, x_total),
            "V": _metric(v_hit, v_total),
            "W": _metric(w_hit, w_total),
        },
        "by_type": by_type_payload,
    }


def build_report(detail_path: Path, sql35_dir: Path) -> Dict[str, Any]:
    by_type = _load_rows(detail_path)
    rows = [row for rows_for_type in by_type.values() for row in rows_for_type]
    org_to_names, office_to_names, user_map, roster_names = _build_user_scope_maps(sql35_dir)
    baseline = _workflow_baseline(rows, user_map, roster_names)
    stable = _simulate_profile(rows, by_type, "stable", org_to_names, office_to_names, user_map, roster_names)
    experimental = _simulate_profile(rows, by_type, "experimental", org_to_names, office_to_names, user_map, roster_names)
    return {
        "input": str(detail_path),
        "sql35_dir": str(sql35_dir),
        "row_count": len(rows),
        "profiles": {
            "workflow_only": baseline,
            "stable_composite": stable,
            "experimental_composite": experimental,
        },
        "rulebooks": {
            "stable": {
                doc_type: {
                    "donor_types": list(rule.donor_types),
                    "default_v_topn": rule.default_v_topn,
                    "default_w_topn": rule.default_w_topn,
                    "boost_v_topn": rule.boost_v_topn,
                    "boost_w_topn": rule.boost_w_topn,
                    "boosted_prefixes": list(rule.boosted_prefixes),
                }
                for doc_type, rule in STABLE_RULES.items()
            },
            "experimental": {
                doc_type: {
                    "donor_types": list(rule.donor_types),
                    "default_v_topn": rule.default_v_topn,
                    "default_w_topn": rule.default_w_topn,
                    "boost_v_topn": rule.boost_v_topn,
                    "boost_w_topn": rule.boost_w_topn,
                    "boosted_prefixes": list(rule.boosted_prefixes),
                }
                for doc_type, rule in EXPERIMENTAL_RULES.items()
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full-file composite simulation for file6 SEND-side rows.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(args.input, args.sql35_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "output": str(args.output),
        "row_count": report["row_count"],
        "workflow_only": report["profiles"]["workflow_only"]["metrics"],
        "stable_composite": report["profiles"]["stable_composite"]["metrics"],
        "experimental_composite": report["profiles"]["experimental_composite"]["metrics"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
