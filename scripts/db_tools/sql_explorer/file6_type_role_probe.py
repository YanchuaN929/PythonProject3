"""Score file6 type-specific responsibility candidates from detail JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .file4_ah_owner_chain_probe import _owner_match
from .file6_distribution_chain_probe import (
    _clean_text,
    _office_match,
    _org_match,
    _resolve_distribution_entities,
    parse_department_tree,
    resolve_sql35_table_path,
)
from .roster import load_all_roster_names
from .validate_cims_sql_dump import parse_user_map


def _dedupe(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _metric_rows(
    rows: Sequence[Dict[str, Any]],
    field_name: str,
    values_getter,
    user_map: Dict[str, Dict[str, Any]],
    department_map: Dict[str, Dict[str, str]],
    roster_names,
) -> Dict[str, Any]:
    total = 0
    x_hit = 0
    v_hit = 0
    w_hit = 0
    x_total = 0
    v_total = 0
    w_total = 0
    cache: Dict[Tuple[str, ...], Dict[str, List[str]]] = {}

    for row in rows:
        values = _dedupe(values_getter(row))
        cache_key = tuple(values)
        resolved = cache.get(cache_key)
        if resolved is None:
            resolved = _resolve_distribution_entities(values, user_map, department_map)
            cache[cache_key] = resolved

        if _clean_text(row.get("x_raw")):
            x_total += 1
            if _owner_match(row["x_raw"], ",".join(values), user_map, roster_names):
                x_hit += 1
        if _clean_text(row.get("v_raw")):
            v_total += 1
            if _org_match(row["v_raw"], resolved["org_values"]):
                v_hit += 1
        if _clean_text(row.get("w_raw")):
            w_total += 1
            if _office_match(row["w_raw"], resolved["office_values"]):
                w_hit += 1
        total += 1

    return {
        "row_count": total,
        "X_all": {"total": x_total, "hit": x_hit, "rate": round(x_hit / x_total, 6) if x_total else 0.0},
        "V_all": {"total": v_total, "hit": v_hit, "rate": round(v_hit / v_total, 6) if v_total else 0.0},
        "W_all": {"total": w_total, "hit": w_hit, "rate": round(w_hit / w_total, 6) if w_total else 0.0},
    }


def build_report(detail_path: Path, sql35_dir: Path, top_n: int) -> Dict[str, Any]:
    payload = json.loads(detail_path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    department_map = parse_department_tree(resolve_sql35_table_path(sql35_dir, "DEPARTMENT"))
    user_map = parse_user_map(resolve_sql35_table_path(sql35_dir, "USER"), department_map)
    roster_names = load_all_roster_names()

    activity_names = sorted(
        {
            activity_name
            for row in rows
            for activity_name in (row.get("vote_activity_operators") or {}).keys()
        }
    )
    source_types = sorted(
        {
            source_type
            for row in rows
            for source_type in (row.get("vote_source_type_operators") or {}).keys()
        }
    )

    candidates: List[Dict[str, Any]] = []

    def add_candidate(name: str, getter) -> None:
        metrics = _metric_rows(rows, "x_raw", getter, user_map, department_map, roster_names)
        metrics["name"] = name
        candidates.append(metrics)

    add_candidate("workflow_all_actors", lambda row: row.get("workflow_all_actor_values", []))
    add_candidate("workflow_active_actors", lambda row: row.get("workflow_active_actor_values", []))
    add_candidate("vote_all_operators", lambda row: row.get("vote_all_operators", []))
    add_candidate("vote_valid_operators", lambda row: row.get("vote_valid_operators", []))

    for activity_name in activity_names:
        add_candidate(
            f"vote_activity:{activity_name}",
            lambda row, activity_name=activity_name: (row.get("vote_activity_operators") or {}).get(activity_name, []),
        )
        add_candidate(
            f"vote_valid_activity:{activity_name}",
            lambda row, activity_name=activity_name: (row.get("vote_valid_activity_operators") or {}).get(activity_name, []),
        )

    for source_type in source_types:
        add_candidate(
            f"workflow_source:{source_type}",
            lambda row, source_type=source_type: (row.get("workflow_source_type_actors") or {}).get(source_type, []),
        )
        add_candidate(
            f"workflow_active_source:{source_type}",
            lambda row, source_type=source_type: (row.get("workflow_source_type_active_actors") or {}).get(source_type, []),
        )
        add_candidate(
            f"vote_source:{source_type}",
            lambda row, source_type=source_type: (row.get("vote_source_type_operators") or {}).get(source_type, []),
        )
        for activity_name in activity_names:
            add_candidate(
                f"vote_source:{source_type}|activity:{activity_name}",
                lambda row, source_type=source_type, activity_name=activity_name: (
                    (row.get("vote_source_type_activity_operators") or {}).get(source_type, {}).get(activity_name, [])
                ),
            )
            add_candidate(
                f"vote_valid_source:{source_type}|activity:{activity_name}",
                lambda row, source_type=source_type, activity_name=activity_name: (
                    (row.get("vote_valid_source_type_activity_operators") or {}).get(source_type, {}).get(activity_name, [])
                ),
            )

    candidates.sort(
        key=lambda item: (
            item["X_all"]["rate"],
            item["V_all"]["rate"],
            item["W_all"]["rate"],
            item["X_all"]["hit"],
        ),
        reverse=True,
    )

    return {
        "input": str(detail_path),
        "sql35_dir": str(sql35_dir),
        "row_count": len(rows),
        "doc_types": sorted({_clean_text(row.get("a_raw")) for row in rows if _clean_text(row.get("a_raw"))}),
        "activity_names": activity_names,
        "source_types": source_types,
        "top_candidates": candidates[:top_n],
        "all_candidates": candidates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score file6 type-specific responsibility candidates.")
    parser.add_argument("--input", type=Path, required=True, help="Detail JSON from file6_send_workflow_probe.py")
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=40)
    args = parser.parse_args()

    report = build_report(args.input, args.sql35_dir, args.top_n)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "row_count": report["row_count"],
                "doc_types": report["doc_types"],
                "top_candidates": [item["name"] for item in report["top_candidates"][:10]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
