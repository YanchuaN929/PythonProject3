"""Composite probe for file4 AH using route-leaf owners plus SQL fallback."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence

import pandas as pd

from .composite_excel_sql_recheck import (
    best_child_id,
    collect_workbooks,
    parse_child_rows,
    parse_send_rows,
    prefilter_sql,
)
from .file4_ah_owner_chain_probe import _owner_match
from .file4_dist_route_probe import _norm_route, parse_dist_leafs
from .real_distribution_chain_probe import _clean_text, _excel_col_index, _norm_drop_tail_digits, _norm_key, _safe_get
from .roster import load_all_roster_names
from .validate_cims_sql_dump import parse_department_map, parse_user_map


def load_file4_rows(excel_dir: Path) -> List[Dict[str, Any]]:
    idx_a = _excel_col_index("A")
    idx_e = _excel_col_index("E")
    idx_w = _excel_col_index("W")
    idx_ah = _excel_col_index("AH")
    rows: List[Dict[str, Any]] = []

    for workbook in collect_workbooks(excel_dir)["file4"]:
        df = pd.read_excel(workbook["path"], sheet_name=0, engine="openpyxl", usecols=[idx_a, idx_e, idx_w, idx_ah])
        for row_no, series in df.iterrows():
            e_raw = _safe_get(series.tolist(), 1)
            owner = _clean_text(_safe_get(series.tolist(), 3))
            route = _norm_route(_safe_get(series.tolist(), 2))
            if not owner or not route:
                continue
            rows.append(
                {
                    "project": workbook["project"],
                    "workbook": workbook["name"],
                    "excel_row": row_no + 2,
                    "a_type": _clean_text(_safe_get(series.tolist(), 0)).upper(),
                    "e_token": _clean_text(e_raw),
                    "e_key": _norm_key(e_raw),
                    "e_key_tail": _norm_drop_tail_digits(e_raw),
                    "route": route,
                    "owner_raw": owner,
                }
            )
    return rows


def _rate(hit: int, total: int) -> float:
    return round(hit / total, 6) if total else 0.0


def _metric(rows: Sequence[Dict[str, Any]], flag: str) -> Dict[str, Any]:
    by_project: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "hit": 0})
    hit = 0
    for row in rows:
        by_project[row["project"]]["total"] += 1
        if row.get(flag):
            hit += 1
            by_project[row["project"]]["hit"] += 1
    return {
        "total": len(rows),
        "hit": hit,
        "rate": _rate(hit, len(rows)),
        "by_project": {
            project: {
                "total": payload["total"],
                "hit": payload["hit"],
                "rate": _rate(payload["hit"], payload["total"]),
            }
            for project, payload in sorted(by_project.items())
        },
    }


def _coverage(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Any]:
    by_project: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "covered": 0})
    covered = 0
    for row in rows:
        by_project[row["project"]]["total"] += 1
        if row.get(key):
            covered += 1
            by_project[row["project"]]["covered"] += 1
    return {
        "total": len(rows),
        "covered": covered,
        "rate": _rate(covered, len(rows)),
        "by_project": {
            project: {
                "total": payload["total"],
                "covered": payload["covered"],
                "rate": _rate(payload["covered"], payload["total"]),
            }
            for project, payload in sorted(by_project.items())
        },
    }


def _summarize_mode(rows: Sequence[Dict[str, Any]], key: str) -> Dict[str, Any]:
    counts: DefaultDict[str, int] = defaultdict(int)
    by_project: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        mode = row.get(key) or "miss"
        counts[mode] += 1
        by_project[row["project"]][mode] += 1
    return {
        "overall": dict(sorted(counts.items())),
        "by_project": {project: dict(sorted(modes.items())) for project, modes in sorted(by_project.items())},
    }


def _interesting_samples(rows: Sequence[Dict[str, Any]], key: str, *, limit: int = 20) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    preferred_routes = {"TGOCI1201TE", "WODWE0201TJABB", "ZGTCO1201ZDHSB", "ETUDCS1202BEFCS", "WSCGF1205GLDQB"}
    for row in rows:
        if row.get("route") in preferred_routes and len(selected) < limit:
            selected.append(
                {
                    "project": row["project"],
                    "route": row["route"],
                    "a_type": row["a_type"],
                    "owner": row["owner_raw"],
                    "iitf_leafs": row["iitf_leafs"],
                    "iics_leafs": row["iics_leafs"],
                    "iics_created_by": row["iics_created_by"],
                    "iitf_created_by": row["iitf_created_by"],
                    "composite_mode": row.get(key) or "miss",
                }
            )
    for row in rows:
        if row.get(key) != "miss":
            continue
        if len(selected) >= limit:
            break
        selected.append(
            {
                "project": row["project"],
                "route": row["route"],
                "a_type": row["a_type"],
                "owner": row["owner_raw"],
                "iitf_leafs": row["iitf_leafs"],
                "iics_leafs": row["iics_leafs"],
                "iics_created_by": row["iics_created_by"],
                "iitf_created_by": row["iitf_created_by"],
                "composite_mode": "miss",
            }
        )
    return selected[:limit]


def _ensure_prefilter(sql_path: Path, tokens: Iterable[str], out_path: Path) -> None:
    if out_path.exists() and out_path.stat().st_size > 0:
        return
    prefilter_sql(sql_path, set(tokens), out_path)


def run(excel_dir: Path, sql35_dir: Path, output_path: Path, temp_dir: Path) -> Dict[str, Any]:
    rows = load_file4_rows(excel_dir)
    dept_map = parse_department_map(sql35_dir / "DEPARTMENT_20260305.sql")
    user_map = parse_user_map(sql35_dir / "USER_20260305.sql", dept_map)
    roster_names = load_all_roster_names()

    needed_e = {row["e_key"] for row in rows if row["e_key"]}
    needed_tail = {row["e_key_tail"] for row in rows if row["e_key_tail"]}
    temp_dir.mkdir(parents=True, exist_ok=True)

    send_path = temp_dir / "SENDRECEIVEDATA.sql"
    iics_path = temp_dir / "IICS.sql"
    iitf_path = temp_dir / "IITF.sql"
    dist_path = temp_dir / "DISTRIBUTERECORD.sql"
    _ensure_prefilter(sql35_dir / "SENDRECEIVEDATA_20260305.sql", {row["e_token"] for row in rows if row["e_token"]}, send_path)
    send_data = parse_send_rows(send_path, needed_e, needed_tail)
    needed_send_ids = {item for ids in send_data["send_exact"].values() for item in ids} | {
        item for ids in send_data["send_tail"].values() for item in ids
    }
    _ensure_prefilter(sql35_dir / "IICS_20260305.sql", needed_send_ids, iics_path)
    _ensure_prefilter(sql35_dir / "IITF_20260305.sql", needed_send_ids, iitf_path)
    _ensure_prefilter(sql35_dir / "DISTRIBUTERECORD_20260305.sql", {row["route"] for row in rows}, dist_path)
    iics = parse_child_rows(iics_path, needed_send_ids)
    iitf = parse_child_rows(iitf_path, needed_send_ids)

    dist = parse_dist_leafs(
        dist_path,
        {row["project"] for row in rows},
        {row["route"] for row in rows},
    )
    route_union = dist["route_union"]

    for row in rows:
        exact_ids = send_data["send_exact"].get(row["e_key"], set())
        send_ids = exact_ids or send_data["send_tail"].get(row["e_key_tail"], set())
        iics_ids = set()
        iitf_ids = set()
        for send_id in send_ids:
            iics_ids.update(iics["send_to_ids"].get(send_id, set()))
            iitf_ids.update(iitf["send_to_ids"].get(send_id, set()))
        row["iics_id"] = best_child_id(iics_ids, iics["by_id"])
        row["iitf_id"] = best_child_id(iitf_ids, iitf["by_id"])
        row["iics_created_by"] = _clean_text(iics["by_id"].get(row["iics_id"], {}).get("CREATED_BY_ID"))
        row["iitf_created_by"] = _clean_text(iitf["by_id"].get(row["iitf_id"], {}).get("CREATED_BY_ID"))

        row["iitf_leafs"] = list(route_union.get((row["project"], "IITF", row["route"]), []))
        row["iics_leafs"] = list(route_union.get((row["project"], "IICS", row["route"]), []))
        row["either_leafs"] = row["iitf_leafs"] + [item for item in row["iics_leafs"] if item not in row["iitf_leafs"]]

        row["has_iitf_route"] = bool(row["iitf_leafs"])
        row["has_iics_route"] = bool(row["iics_leafs"])
        row["has_either_route"] = bool(row["either_leafs"])

        row["hit_iitf_leaf"] = _owner_match(row["owner_raw"], ",".join(row["iitf_leafs"]), user_map, roster_names)
        row["hit_iics_leaf"] = _owner_match(row["owner_raw"], ",".join(row["iics_leafs"]), user_map, roster_names)
        row["hit_either_leaf"] = _owner_match(row["owner_raw"], ",".join(row["either_leafs"]), user_map, roster_names)
        row["hit_iics_created_by"] = _owner_match(row["owner_raw"], row["iics_created_by"], user_map, roster_names)
        row["hit_iitf_created_by"] = _owner_match(row["owner_raw"], row["iitf_created_by"], user_map, roster_names)

        row["rule_iitf_then_iics_created_by"] = row["hit_iitf_leaf"] or (not row["has_iitf_route"] and row["hit_iics_created_by"])
        row["rule_iitf_or_iics_then_iics_created_by"] = (
            row["hit_iitf_leaf"]
            or (not row["has_iitf_route"] and row["hit_iics_leaf"])
            or (not row["has_iitf_route"] and not row["has_iics_route"] and row["hit_iics_created_by"])
        )

        if row["hit_iitf_leaf"]:
            row["composite_mode"] = "iitf_leaf"
        elif (not row["has_iitf_route"]) and row["hit_iics_leaf"]:
            row["composite_mode"] = "iics_leaf"
        elif (not row["has_iitf_route"]) and (not row["has_iics_route"]) and row["hit_iics_created_by"]:
            row["composite_mode"] = "iics_created_by"
        else:
            row["composite_mode"] = "miss"

    no_iitf_rows = [row for row in rows if not row["has_iitf_route"]]
    no_either_rows = [row for row in rows if not row["has_either_route"]]

    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
        },
        "rows": len(rows),
        "distribution_scan": {
            "statement_count": dist["statement_count"],
            "matched_statement_count": dist["matched_statement_count"],
            "object_group_count": dist["object_group_count"],
            "route_key_count": dist["route_key_count"],
        },
        "coverage": {
            "iitf_route": _coverage(rows, "has_iitf_route"),
            "iics_route": _coverage(rows, "has_iics_route"),
            "either_route": _coverage(rows, "has_either_route"),
        },
        "strict_business_candidates": {
            "iitf_union_leaf_any": _metric(rows, "hit_iitf_leaf"),
            "iics_union_leaf_any": _metric(rows, "hit_iics_leaf"),
            "either_union_leaf_any": _metric(rows, "hit_either_leaf"),
        },
        "fallback_candidates": {
            "iics_created_by": _metric(rows, "hit_iics_created_by"),
            "iitf_created_by": _metric(rows, "hit_iitf_created_by"),
            "iics_created_by_on_no_iitf_route": _metric(no_iitf_rows, "hit_iics_created_by"),
            "iics_created_by_on_no_either_route": _metric(no_either_rows, "hit_iics_created_by"),
        },
        "composite_rules": {
            "iitf_leaf_else_iics_created_by": _metric(rows, "rule_iitf_then_iics_created_by"),
            "iitf_leaf_else_iics_leaf_else_iics_created_by": _metric(rows, "rule_iitf_or_iics_then_iics_created_by"),
            "mode_breakdown": _summarize_mode(rows, "composite_mode"),
        },
        "samples": _interesting_samples(rows, "composite_mode"),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe composite file4 AH owner rule")
    parser.add_argument("--excel-dir", required=True)
    parser.add_argument("--sql35-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--temp-dir", required=True)
    args = parser.parse_args()
    run(Path(args.excel_dir), Path(args.sql35_dir), Path(args.output), Path(args.temp_dir))


if __name__ == "__main__":
    main()
