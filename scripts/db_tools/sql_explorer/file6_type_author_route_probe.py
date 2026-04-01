"""Probe file6 routing via author-unit / letter-prefix patterns.

This script stays separate from workflow-based probes on purpose.
It is used to validate document types whose Excel X/V/W look more like:

    external sender or prefix -> internal org/office routing -> personnel scope

than direct workflow actors.
"""

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
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Sequence, Set, Tuple

from scripts.db_tools.sql_explorer.file4_ah_owner_chain_probe import _owner_match
from scripts.db_tools.sql_explorer.file6_distribution_chain_probe import (
    _clean_text,
    _department_chain_names,
    _department_tokens_from_chain,
    _office_match,
    _org_match,
    parse_department_tree,
    resolve_sql35_table_path,
)
from scripts.db_tools.sql_explorer.roster import load_all_roster_names
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import (
    iter_insert_rows,
    normalize_hex32,
    parse_create_columns,
    parse_user_map,
)


SEP_RE = re.compile(r"[,，;；/、\n]+")


@dataclass(frozen=True)
class StrategySpec:
    name: str
    mode: str
    v_chain: Tuple[Tuple[str, int], ...]
    w_chain: Tuple[Tuple[str, int], ...]
    pool_mode: str = "doc_type"
    workflow_fallback: bool = False
    experimental: bool = False
    description: str = ""


def _dedupe(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _split_multi(value: Any) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    return [token.strip() for token in SEP_RE.split(text) if token.strip()]


def _prefix(letter_no: Any) -> str:
    text = _clean_text(letter_no)
    if not text:
        return ""
    return text.split("-", 1)[0]


def _load_send_map(path: Path, detail_rows: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    needed_ids: Set[str] = set()
    for row in detail_rows:
        needed_ids.update(row.get("candidate_object_ids") or [])

    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    result: Dict[str, Dict[str, str]] = {}
    for row in iter_insert_rows(path):
        row_id = normalize_hex32(row[mapping["id"]])
        if not row_id or row_id not in needed_ids:
            continue
        result[row_id] = {
            "author_unit": _clean_text(row[mapping.get("author_unit", -1)]),
            "receive_unit": _clean_text(row[mapping.get("receive_unit", -1)]),
            "letter_send_no": _clean_text(row[mapping.get("letter_send_no", -1)]),
            "corresp_letter_rec_no": _clean_text(row[mapping.get("corresp_letter_rec_no", -1)]),
            "classification": _clean_text(row[mapping.get("classification", -1)]),
        }
        if len(result) == len(needed_ids):
            break
    return result


def _resolve_send_payload(row: Dict[str, Any], send_map: Mapping[str, Mapping[str, str]]) -> Dict[str, str]:
    letter_no = _clean_text(row.get("e_raw"))
    for obj_id in row.get("candidate_object_ids") or []:
        payload = send_map.get(obj_id)
        if not payload:
            continue
        if payload.get("letter_send_no") == letter_no or payload.get("corresp_letter_rec_no") == letter_no:
            return dict(payload)
    return {}


def _build_user_scope_maps(
    user_map: Dict[str, Dict[str, Any]],
    department_map: Dict[str, Dict[str, str]],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    org_to_names: DefaultDict[str, Set[str]] = defaultdict(set)
    office_to_names: DefaultDict[str, Set[str]] = defaultdict(set)
    for payload in user_map.values():
        user_name = _clean_text(payload.get("user_name"))
        if not user_name:
            continue
        chain = _department_chain_names(payload.get("dept_id"), department_map)
        tokens = _department_tokens_from_chain(chain)
        for token in tokens["org_values"]:
            org_to_names[token].add(user_name)
        for token in tokens["office_values"]:
            office_to_names[token].add(user_name)
    return (
        {key: sorted(values) for key, values in org_to_names.items()},
        {key: sorted(values) for key, values in office_to_names.items()},
    )


def _predict_majority_value(
    train_rows: Sequence[Dict[str, Any]],
    key_name: str,
    key_value: str,
    field_name: str,
) -> str:
    if not key_value:
        return ""
    counter = Counter(
        _clean_text(row.get(field_name))
        for row in train_rows
        if _clean_text(row.get(key_name)) == key_value and _clean_text(row.get(field_name))
    )
    return counter.most_common(1)[0][0] if counter else ""


def _predict_top_tokens(
    train_rows: Sequence[Dict[str, Any]],
    key_name: str,
    key_value: str,
    field_name: str,
    topn: int,
) -> List[str]:
    if not key_value or topn <= 0:
        return []
    counter: Counter[str] = Counter()
    for row in train_rows:
        if _clean_text(row.get(key_name)) != key_value:
            continue
        for token in _split_multi(row.get(field_name)):
            counter[token] += 1
    return [token for token, _ in counter.most_common(topn)]


def _predict_values_for_field(
    train_rows: Sequence[Dict[str, Any]],
    row: Dict[str, Any],
    field_name: str,
    chain: Sequence[Tuple[str, int]],
    mode: str,
) -> Tuple[List[str], str]:
    for key_name, strength in chain:
        key_value = _clean_text(row.get(key_name))
        if not key_value:
            continue
        if mode == "majority":
            predicted = _predict_majority_value(train_rows, key_name, key_value, field_name)
            values = [predicted] if predicted else []
        elif mode == "token":
            values = _predict_top_tokens(train_rows, key_name, key_value, field_name, topn=strength)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        if values:
            return values, key_name
    return [], ""


def _predict_names_from_scope(
    predicted_v: Sequence[str],
    predicted_w: Sequence[str],
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
) -> List[str]:
    result: List[str] = []
    for token in _dedupe(
        token
        for value in predicted_v
        for token in (_split_multi(value) or [_clean_text(value)])
    ):
        for name in org_to_names.get(token, []):
            if name not in result:
                result.append(name)
    for token in _dedupe(
        token
        for value in predicted_w
        for token in (_split_multi(value) or [_clean_text(value)])
    ):
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


def _evaluate_strategy(
    subset: Sequence[Dict[str, Any]],
    pool_rows: Sequence[Dict[str, Any]],
    strategy: StrategySpec,
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: Set[str],
) -> Dict[str, Any]:
    x_hit = x_total = 0
    v_hit = v_total = 0
    w_hit = w_total = 0
    predicted_name_sizes: List[int] = []
    source_usage: Counter[Tuple[str, str]] = Counter()
    samples: List[Dict[str, Any]] = []

    for row in subset:
        train_rows = [candidate for candidate in pool_rows if candidate is not row]
        predicted_v, v_source = _predict_values_for_field(train_rows, row, "v_raw", strategy.v_chain, strategy.mode)
        predicted_w, w_source = _predict_values_for_field(train_rows, row, "w_raw", strategy.w_chain, strategy.mode)

        if strategy.workflow_fallback:
            if not predicted_v:
                predicted_v = _dedupe(row.get("workflow_org_values") or [])
                if predicted_v:
                    v_source = "workflow_org_values"
            if not predicted_w:
                predicted_w = _dedupe(row.get("workflow_office_values") or [])
                if predicted_w:
                    w_source = "workflow_office_values"

        predicted_names = _predict_names_from_scope(predicted_v, predicted_w, org_to_names, office_to_names)
        predicted_name_sizes.append(len(predicted_names))
        source_usage[(v_source or "-", w_source or "-")] += 1

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

        if len(samples) < 20:
            samples.append(
                {
                    "e_raw": row.get("e_raw"),
                    "author_unit": row.get("author_unit"),
                    "letter_prefix": row.get("letter_prefix"),
                    "excel_v": row.get("v_raw"),
                    "excel_w": row.get("w_raw"),
                    "excel_x": row.get("x_raw"),
                    "predicted_v": predicted_v,
                    "predicted_w": predicted_w,
                    "predicted_x_count": len(predicted_names),
                    "prediction_v_source": v_source,
                    "prediction_w_source": w_source,
                }
            )

    return {
        "description": strategy.description,
        "experimental": strategy.experimental,
        "metrics": {
            "X": _metric(x_hit, x_total),
            "V": _metric(v_hit, v_total),
            "W": _metric(w_hit, w_total),
        },
        "predicted_name_scope": {
            "avg_count": round(sum(predicted_name_sizes) / len(predicted_name_sizes), 2) if predicted_name_sizes else 0.0,
            "max_count": max(predicted_name_sizes) if predicted_name_sizes else 0,
        },
        "source_usage": [
            {
                "v_source": v_source,
                "w_source": w_source,
                "row_count": count,
            }
            for (v_source, w_source), count in source_usage.most_common()
        ],
        "prediction_samples": samples,
    }


def _summarize_groups(subset: Sequence[Dict[str, Any]], key_name: str) -> Dict[str, Any]:
    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in subset:
        grouped[_clean_text(row.get(key_name))].append(row)

    result: Dict[str, Any] = {}
    for key_value, items in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if not key_value:
            continue
        v_counter = Counter(_clean_text(item.get("v_raw")) for item in items if _clean_text(item.get("v_raw")))
        w_counter = Counter(_clean_text(item.get("w_raw")) for item in items if _clean_text(item.get("w_raw")))
        result[key_value] = {
            "row_count": len(items),
            "x_nonempty": sum(1 for item in items if _clean_text(item.get("x_raw"))),
            "top_v": v_counter.most_common(5),
            "top_w": w_counter.most_common(5),
        }
    return result


def _recommended_strategy(strategy_results: Mapping[str, Dict[str, Any]]) -> str:
    stable_items = [
        (name, payload)
        for name, payload in strategy_results.items()
        if not payload.get("experimental")
    ]
    if not stable_items:
        return ""
    best_name = ""
    best_score: Tuple[float, float, float, float] = (-1.0, -1.0, -1.0, -1.0)
    for name, payload in stable_items:
        metrics = payload["metrics"]
        score = (
            metrics["V"]["rate"],
            metrics["W"]["rate"],
            metrics["X"]["rate"],
            -payload["predicted_name_scope"]["avg_count"],
        )
        if score > best_score:
            best_name = name
            best_score = score
    return best_name


def build_report(
    detail_path: Path,
    sql35_dir: Path,
    doc_types: Sequence[str] | None = None,
) -> Dict[str, Any]:
    payload = json.loads(detail_path.read_text(encoding="utf-8"))
    all_rows = payload.get("rows", [])
    doc_type_filter = {_clean_text(item) for item in (doc_types or []) if _clean_text(item)}
    rows = [
        row
        for row in all_rows
        if not doc_type_filter or _clean_text(row.get("a_raw")) in doc_type_filter
    ]

    department_map = parse_department_tree(resolve_sql35_table_path(sql35_dir, "DEPARTMENT"))
    user_map = parse_user_map(resolve_sql35_table_path(sql35_dir, "USER"), department_map)
    roster_names = load_all_roster_names()
    org_to_names, office_to_names = _build_user_scope_maps(user_map, department_map)
    send_map = _load_send_map(resolve_sql35_table_path(sql35_dir, "SENDRECEIVEDATA"), rows)

    enriched_rows: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        send_payload = _resolve_send_payload(row, send_map)
        item["author_unit"] = _clean_text(send_payload.get("author_unit"))
        item["receive_unit"] = _clean_text(send_payload.get("receive_unit"))
        item["classification"] = _clean_text(send_payload.get("classification"))
        item["letter_prefix"] = _prefix(row.get("e_raw"))
        item["author_prefix"] = "|".join(
            token for token in (item["author_unit"], item["letter_prefix"]) if token
        )
        enriched_rows.append(item)

    strategies = [
        StrategySpec(
            name="legacy_author_prefix_majority",
            mode="majority",
            v_chain=(("author_unit", 1), ("letter_prefix", 1)),
            w_chain=(("author_unit", 1), ("letter_prefix", 1)),
            description="Legacy full-string majority with author-unit first, prefix fallback.",
        ),
        StrategySpec(
            name="author_token_top3",
            mode="token",
            v_chain=(("author_unit", 3),),
            w_chain=(("author_unit", 3),),
            description="Token majority by author-unit only.",
        ),
        StrategySpec(
            name="prefix_token_top3",
            mode="token",
            v_chain=(("letter_prefix", 3),),
            w_chain=(("letter_prefix", 3),),
            description="Token majority by letter prefix only.",
        ),
        StrategySpec(
            name="author3_then_prefix3",
            mode="token",
            v_chain=(("author_unit", 3), ("letter_prefix", 3)),
            w_chain=(("author_unit", 3), ("letter_prefix", 3)),
            description="Stable token strategy: author-unit first, prefix fallback.",
        ),
        StrategySpec(
            name="prefix3_then_author3",
            mode="token",
            v_chain=(("letter_prefix", 3), ("author_unit", 3)),
            w_chain=(("letter_prefix", 3), ("author_unit", 3)),
            description="Stable token strategy: prefix first, author-unit fallback.",
        ),
        StrategySpec(
            name="prefix3_then_workflow_org_experimental",
            mode="token",
            v_chain=(("letter_prefix", 3),),
            w_chain=(("letter_prefix", 3),),
            workflow_fallback=True,
            experimental=True,
            description="Experimental only: workflow org/office fallback when author-route has no peers.",
        ),
        StrategySpec(
            name="cross_type_prefix_token_top3",
            mode="token",
            v_chain=(("letter_prefix", 3),),
            w_chain=(("letter_prefix", 3),),
            pool_mode="global",
            description="Stable route for sibling types: share prefix token evidence across all filtered doc types.",
        ),
    ]

    doc_type_reports: Dict[str, Any] = {}
    for doc_type in sorted({_clean_text(row.get("a_raw")) for row in enriched_rows if _clean_text(row.get("a_raw"))}):
        subset = [row for row in enriched_rows if _clean_text(row.get("a_raw")) == doc_type]
        strategy_results = {
            strategy.name: _evaluate_strategy(
                subset,
                enriched_rows if strategy.pool_mode == "global" else subset,
                strategy,
                org_to_names,
                office_to_names,
                user_map,
                roster_names,
            )
            for strategy in strategies
        }
        recommended = _recommended_strategy(strategy_results)
        doc_type_reports[doc_type] = {
            "row_count": len(subset),
            "recommended_stable_strategy": recommended,
            "strategy_results": strategy_results,
            "author_groups": _summarize_groups(subset, "author_unit"),
            "prefix_groups": _summarize_groups(subset, "letter_prefix"),
            "recommended_prediction_samples": strategy_results.get(recommended, {}).get("prediction_samples", []),
        }

    return {
        "input": str(detail_path),
        "sql35_dir": str(sql35_dir),
        "doc_type_filter": sorted(doc_type_filter),
        "doc_type_reports": doc_type_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file6 routing via author-unit / letter-prefix patterns.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--doc-types", nargs="*", help="Optional A-column doc types. Supports comma-separated values.")
    args = parser.parse_args()

    doc_types: List[str] = []
    for raw_value in args.doc_types or []:
        doc_types.extend([item.strip() for item in raw_value.split(",") if item.strip()])

    report = build_report(args.input, args.sql35_dir, doc_types=doc_types or None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "doc_types": sorted(report["doc_type_reports"].keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
