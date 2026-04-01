"""Probe cross-type shared-prefix families for file6 SEND-side rows."""

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
from collections import Counter, defaultdict, deque
from itertools import combinations
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence

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
from scripts.db_tools.sql_explorer.file6_type_author_route_probe import _metric, _prefix
from scripts.db_tools.sql_explorer.roster import load_all_roster_names
from scripts.db_tools.sql_explorer.validate_cims_sql_dump import parse_user_map


SEP_CHARS = [",", "，", ";", "；", "/", "、"]


def _split_multi(value: Any) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    for sep in SEP_CHARS:
        text = text.replace(sep, ",")
    return [token.strip() for token in text.split(",") if token.strip()]


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
    if not prefix_value:
        return []
    counter: Counter[str] = Counter()
    for row in train_rows:
        if _clean_text(row.get("prefix")) != prefix_value:
            continue
        for token in _split_multi(row.get(field_name)):
            counter[token] += 1
    return [token for token, _ in counter.most_common(topn)]


def _build_user_scope_maps(sql35_dir: Path) -> tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, Dict[str, Any]], set[str]]:
    department_map = parse_department_tree(resolve_sql35_table_path(sql35_dir, "DEPARTMENT"))
    user_map = parse_user_map(resolve_sql35_table_path(sql35_dir, "USER"), department_map)
    roster_names = load_all_roster_names()
    org_to_names: DefaultDict[str, set[str]] = defaultdict(set)
    office_to_names: DefaultDict[str, set[str]] = defaultdict(set)
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
        user_map,
        roster_names,
    )


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


def _evaluate_pool(
    subset: Sequence[Dict[str, Any]],
    pool_rows: Sequence[Dict[str, Any]],
    org_to_names: Dict[str, List[str]],
    office_to_names: Dict[str, List[str]],
    user_map: Dict[str, Dict[str, Any]],
    roster_names: set[str],
) -> Dict[str, Any]:
    x_hit = x_total = 0
    v_hit = v_total = 0
    w_hit = w_total = 0
    predicted_name_sizes: List[int] = []
    recovered_rows: List[Dict[str, Any]] = []

    for row in subset:
        train_rows = [candidate for candidate in pool_rows if candidate is not row]
        predicted_v = _predict_top_tokens(train_rows, _clean_text(row.get("prefix")), "v_raw", 3)
        predicted_w = _predict_top_tokens(train_rows, _clean_text(row.get("prefix")), "w_raw", 3)
        predicted_names = _predict_names(predicted_v, predicted_w, org_to_names, office_to_names)
        predicted_name_sizes.append(len(predicted_names))

        x_match = v_match = w_match = False
        if _clean_text(row.get("x_raw")):
            x_total += 1
            x_match = _owner_match(row["x_raw"], ",".join(predicted_names), user_map, roster_names)
            if x_match:
                x_hit += 1
        if _clean_text(row.get("v_raw")):
            v_total += 1
            v_match = _org_match(row["v_raw"], predicted_v)
            if v_match:
                v_hit += 1
        if _clean_text(row.get("w_raw")):
            w_total += 1
            w_match = _office_match(row["w_raw"], predicted_w)
            if w_match:
                w_hit += 1

        if len(recovered_rows) < 20 and (x_match or v_match or w_match):
            recovered_rows.append(
                {
                    "doc_type": row.get("a_raw"),
                    "e_raw": row.get("e_raw"),
                    "prefix": row.get("prefix"),
                    "predicted_v": predicted_v,
                    "predicted_w": predicted_w,
                }
            )

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
        "samples": recovered_rows,
    }


def build_report(detail_path: Path, sql35_dir: Path, min_shared_prefixes: int) -> Dict[str, Any]:
    payload = json.loads(detail_path.read_text(encoding="utf-8"))
    all_rows = []
    for row in payload.get("rows", []):
        doc_type = _clean_text(row.get("a_raw"))
        if not doc_type:
            continue
        item = dict(row)
        item["prefix"] = _prefix(row.get("e_raw"))
        all_rows.append(item)

    by_type: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        by_type[_clean_text(row.get("a_raw"))].append(row)

    prefix_sets = {
        doc_type: {_clean_text(row.get("prefix")) for row in rows if _clean_text(row.get("prefix"))}
        for doc_type, rows in by_type.items()
    }

    graph: DefaultDict[str, set[str]] = defaultdict(set)
    shared_edges: List[Dict[str, Any]] = []
    for left, right in combinations(sorted(prefix_sets), 2):
        shared = sorted(prefix_sets[left] & prefix_sets[right])
        if len(shared) < min_shared_prefixes:
            continue
        graph[left].add(right)
        graph[right].add(left)
        shared_edges.append(
            {
                "left": left,
                "right": right,
                "shared_prefix_count": len(shared),
                "sample_prefixes": shared[:12],
            }
        )

    components: List[List[str]] = []
    seen: set[str] = set()
    for doc_type in sorted(prefix_sets):
        if doc_type in seen:
            continue
        queue = deque([doc_type])
        seen.add(doc_type)
        component: List[str] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            for neighbor in sorted(graph[current]):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)
        components.append(component)

    components.sort(key=lambda component: sum(len(by_type[doc_type]) for doc_type in component), reverse=True)

    org_to_names, office_to_names, user_map, roster_names = _build_user_scope_maps(sql35_dir)

    component_reports: List[Dict[str, Any]] = []
    for component in components:
        component_rows = [row for doc_type in component for row in by_type[doc_type]]
        component_reports.append(
            {
                "doc_types": component,
                "row_count": len(component_rows),
                "type_reports": {
                    doc_type: {
                        "row_count": len(by_type[doc_type]),
                        "same_type_prefix_token_top3": _evaluate_pool(
                            by_type[doc_type],
                            by_type[doc_type],
                            org_to_names,
                            office_to_names,
                            user_map,
                            roster_names,
                        ),
                        "cross_type_prefix_token_top3": _evaluate_pool(
                            by_type[doc_type],
                            component_rows,
                            org_to_names,
                            office_to_names,
                            user_map,
                            roster_names,
                        ),
                    }
                    for doc_type in component
                },
            }
        )

    return {
        "input": str(detail_path),
        "sql35_dir": str(sql35_dir),
        "min_shared_prefixes": min_shared_prefixes,
        "shared_edges": shared_edges,
        "components": component_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file6 shared-prefix families across document types.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-shared-prefixes", type=int, default=6)
    args = parser.parse_args()

    report = build_report(args.input, args.sql35_dir, args.min_shared_prefixes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "component_count": len(report["components"]),
                "largest_component_rows": report["components"][0]["row_count"] if report["components"] else 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
