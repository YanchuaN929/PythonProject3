"""Route-based leaf-owner probe for file4 AH."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, Iterator, List, Sequence, Tuple

import pandas as pd

from .composite_excel_sql_recheck import collect_workbooks
from .file4_ah_owner_chain_probe import _owner_match
from .real_distribution_chain_probe import _clean_text
from .roster import load_all_roster_names
from .validate_cims_sql_dump import parse_department_map, parse_user_map, normalize_hex32


PROJECTS = {"1818", "1907", "1915", "1916", "2016", "2026", "2306"}
DIST_PREFIX = "INSERT INTO [DISTRIBUTERECORD]"
DIST_END = "); GO"
DIST_COLS = [
    "id",
    "source_id",
    "classification",
    "keyed_name",
    "created_on",
    "created_by_id",
    "owned_by_id",
    "managed_by_id",
    "modified_on",
    "modified_by_id",
    "current_state",
    "state",
    "locked_by_id",
    "is_current",
    "major_rev",
    "minor_rev",
    "is_released",
    "not_lockable",
    "css",
    "generation",
    "new_version",
    "config_id",
    "permission_id",
    "team_id",
    "source_type",
    "sender",
    "bo_title",
    "distribute_type",
    "completed",
    "operator",
    "operation_time",
    "memo",
    "source_object_id",
    "bo_type",
    "proj_num",
    "due_time",
    "work_desc",
    "sync_status",
    "sync_date",
]
DIST_IDX = {name: idx for idx, name in enumerate(DIST_COLS)}


def _norm_route(text: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", _clean_text(text).upper())


def _parse_time(value: Any) -> pd.Timestamp:
    parsed = pd.to_datetime(str(value or "").strip(), errors="coerce")
    return parsed if parsed is not pd.NaT else pd.Timestamp.min


def _decode_sql_token(token: str) -> str:
    text = token.strip()
    if not text or text.upper() == "NULL":
        return ""
    if text.startswith("N'") and text.endswith("'"):
        return text[2:-1].replace("''", "'")
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1].replace("''", "'")
    return text


def _split_sql_values(values_blob: str) -> List[str]:
    items: List[str] = []
    buf: List[str] = []
    in_quote = False
    idx = 0
    total = len(values_blob)

    while idx < total:
        ch = values_blob[idx]
        if ch == "'":
            buf.append(ch)
            if in_quote and idx + 1 < total and values_blob[idx + 1] == "'":
                buf.append("'")
                idx += 2
                continue
            in_quote = not in_quote
            idx += 1
            continue
        if ch == "," and not in_quote:
            items.append(_decode_sql_token("".join(buf)))
            buf = []
        else:
            buf.append(ch)
        idx += 1
    items.append(_decode_sql_token("".join(buf)))
    return items


def _iter_insert_statements(path: Path) -> Iterator[str]:
    buffer: List[str] = []
    collecting = False
    with path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            if not collecting:
                if line.startswith(DIST_PREFIX):
                    buffer = [line]
                    collecting = True
                    if DIST_END in line:
                        yield "".join(buffer)
                        buffer = []
                        collecting = False
                continue
            buffer.append(line)
            if DIST_END in line:
                yield "".join(buffer)
                buffer = []
                collecting = False


def _extract_values_blob(statement: str) -> str:
    pos = statement.find("VALUES (")
    if pos < 0:
        return ""
    start = pos + len("VALUES (")
    end = statement.rfind(DIST_END)
    if end < 0:
        return ""
    return statement[start:end]


def _extract_route_from_bo_title(bo_title: str) -> Tuple[str, str]:
    text = _clean_text(bo_title)
    match = re.search(r"/(IITF|IICS)-(.+?)--", text, re.IGNORECASE)
    if not match:
        return "", ""
    source_type = match.group(1).upper()
    route = match.group(2).strip()
    parts = route.split("-")
    if len(parts) >= 2 and re.fullmatch(r"[A-Z0-9]{1,3}", parts[-1], re.IGNORECASE):
        route = "-".join(parts[:-1])
    return source_type, _norm_route(route)


def load_file4_rows(excel_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for workbook in collect_workbooks(excel_dir)["file4"]:
        df = pd.read_excel(workbook["path"], sheet_name=0, engine="openpyxl", usecols=[0, 22, 33])
        for idx, series in df.iterrows():
            owner = _clean_text(series.iloc[2])
            route = _norm_route(series.iloc[1])
            if not owner or not route:
                continue
            rows.append(
                {
                    "project": workbook["project"],
                    "a_type": _clean_text(series.iloc[0]).upper(),
                    "route": route,
                    "owner_raw": owner,
                    "workbook": workbook["name"],
                    "excel_row": idx + 2,
                }
            )
    return rows


def parse_dist_leafs(
    path: Path,
    projects: Iterable[str],
    route_keys: Iterable[str],
    *,
    progress_every: int = 200000,
) -> Dict[str, Any]:
    project_set = set(projects)
    route_set = set(route_keys)
    project_markers = {project: f"N'{project}'" for project in project_set}
    object_groups: DefaultDict[Tuple[str, str, str, str], Dict[str, Any]] = defaultdict(
        lambda: {"sender_ids": set(), "ops": [], "latest": pd.Timestamp.min}
    )
    statement_count = 0
    matched_statement_count = 0
    started = time.time()

    for statement in _iter_insert_statements(path):
        statement_count += 1
        if statement_count % progress_every == 0:
            print(
                json.dumps(
                    {
                        "stage": "scan_dist",
                        "statements": statement_count,
                        "matched": matched_statement_count,
                        "elapsed_sec": round(time.time() - started, 1),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

        if "extra.cnpe.entity.externalInterface.ExtII" not in statement:
            continue
        proj = next((item for item, marker in project_markers.items() if marker in statement), "")
        if not proj:
            continue

        route_type_hint, route_hint = _extract_route_from_bo_title(statement)
        if not route_hint or route_hint not in route_set:
            continue

        values_blob = _extract_values_blob(statement)
        if not values_blob:
            continue
        row = _split_sql_values(values_blob)
        if len(row) < len(DIST_COLS):
            continue
        is_current = str(row[DIST_IDX["is_current"]] or "").strip().upper()
        if is_current not in {"", "1", "Y", "TRUE", "T"}:
            continue

        source_type = _clean_text(row[DIST_IDX["source_type"]]).upper()
        if "EXTIITF" in source_type:
            source_type = "IITF"
        elif "EXTIICS" in source_type:
            source_type = "IICS"
        else:
            continue
        if route_type_hint and route_type_hint != source_type:
            source_type = route_type_hint

        source_object_id = normalize_hex32(row[DIST_IDX["source_object_id"]])
        if not source_object_id:
            continue
        sender = normalize_hex32(row[DIST_IDX["sender"]]) or _clean_text(row[DIST_IDX["sender"]])
        operator = _clean_text(row[DIST_IDX["operator"]])
        operation_time = _parse_time(row[DIST_IDX["operation_time"]])
        group = object_groups[(proj, source_type, route_hint, source_object_id)]
        if sender:
            group["sender_ids"].add(sender)
        if operator:
            group["ops"].append((operator, operation_time))
        if operation_time > group["latest"]:
            group["latest"] = operation_time
        matched_statement_count += 1

    route_latest: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    route_union: DefaultDict[Tuple[str, str, str], List[str]] = defaultdict(list)
    for (proj, source_type, route, source_object_id), payload in object_groups.items():
        leafs: List[str] = []
        for operator, _ in payload["ops"]:
            operator_id = normalize_hex32(operator)
            compare_key = operator_id or operator
            if compare_key in payload["sender_ids"]:
                continue
            if operator not in leafs:
                leafs.append(operator)
        route_key = (proj, source_type, route)
        for item in leafs:
            if item not in route_union[route_key]:
                route_union[route_key].append(item)
        candidate = {
            "source_object_id": source_object_id,
            "latest_time": None if payload["latest"] is pd.Timestamp.min else str(payload["latest"]),
            "leafs": leafs,
        }
        current = route_latest.get(route_key)
        if current is None or (candidate["latest_time"] or "") > (current["latest_time"] or ""):
            route_latest[route_key] = candidate

    return {
        "statement_count": statement_count,
        "matched_statement_count": matched_statement_count,
        "object_group_count": len(object_groups),
        "route_key_count": len(route_latest),
        "route_latest": route_latest,
        "route_union": route_union,
    }


def _metric(
    rows: Sequence[Dict[str, Any]],
    getter,
    user_map: Dict[str, Dict[str, Any]],
    roster_names,
) -> Dict[str, Any]:
    total = len(rows)
    hit = 0
    missing = 0
    by_project: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "hit": 0})
    samples: List[Dict[str, Any]] = []
    for row in rows:
        by_project[row["project"]]["total"] += 1
        tokens = getter(row)
        if not tokens:
            missing += 1
            continue
        ok = _owner_match(row["owner_raw"], ",".join(tokens), user_map, roster_names)
        if ok:
            hit += 1
            by_project[row["project"]]["hit"] += 1
            if len(samples) < 15:
                samples.append(
                    {
                        "project": row["project"],
                        "a_type": row["a_type"],
                        "route": row["route"],
                        "owner": row["owner_raw"],
                        "tokens": tokens,
                    }
                )
    return {
        "total": total,
        "hit": hit,
        "rate": round(hit / total, 6) if total else 0.0,
        "missing_route_count": missing,
        "by_project": {
            project: {
                "total": payload["total"],
                "hit": payload["hit"],
                "rate": round(payload["hit"] / payload["total"], 6) if payload["total"] else 0.0,
            }
            for project, payload in sorted(by_project.items())
        },
        "samples": samples,
    }


def run(excel_dir: Path, dist_path: Path, user_path: Path, dept_path: Path, output_path: Path) -> Dict[str, Any]:
    started = time.time()
    rows = load_file4_rows(excel_dir)
    route_keys = {row["route"] for row in rows}
    projects = {row["project"] for row in rows}
    print(json.dumps({"stage": "load_excel", "rows": len(rows), "elapsed_sec": round(time.time() - started, 1)}, ensure_ascii=False), flush=True)

    dist_data = parse_dist_leafs(dist_path, projects, route_keys)
    print(
        json.dumps(
            {
                "stage": "parsed_dist",
                "statements": dist_data["statement_count"],
                "matched": dist_data["matched_statement_count"],
                "object_groups": dist_data["object_group_count"],
                "route_keys": dist_data["route_key_count"],
                "elapsed_sec": round(time.time() - started, 1),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    dept_map = parse_department_map(dept_path)
    user_map = parse_user_map(user_path, dept_map)
    roster_names = load_all_roster_names()

    route_latest = dist_data["route_latest"]
    route_union = dist_data["route_union"]
    metrics = {
        "by_a_type_latest_leaf_any": _metric(
            rows,
            lambda row: route_latest.get((row["project"], row["a_type"], row["route"]), {}).get("leafs", []),
            user_map,
            roster_names,
        ),
        "by_a_type_union_leaf_any": _metric(
            rows,
            lambda row: route_union.get((row["project"], row["a_type"], row["route"]), []),
            user_map,
            roster_names,
        ),
        "iitf_latest_leaf_any": _metric(
            rows,
            lambda row: route_latest.get((row["project"], "IITF", row["route"]), {}).get("leafs", []),
            user_map,
            roster_names,
        ),
        "iitf_union_leaf_any": _metric(
            rows,
            lambda row: route_union.get((row["project"], "IITF", row["route"]), []),
            user_map,
            roster_names,
        ),
        "either_union_leaf_any": _metric(
            rows,
            lambda row: list(
                dict.fromkeys(
                    route_union.get((row["project"], "IITF", row["route"]), [])
                    + route_union.get((row["project"], "IICS", row["route"]), [])
                )
            ),
            user_map,
            roster_names,
        ),
    }
    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "dist_path": str(dist_path),
            "user_path": str(user_path),
            "dept_path": str(dept_path),
        },
        "row_counts": {
            "excel_owner_rows": len(rows),
            "dist_statement_count": dist_data["statement_count"],
            "dist_matched_statement_count": dist_data["matched_statement_count"],
            "dist_object_group_count": dist_data["object_group_count"],
            "dist_route_key_count": dist_data["route_key_count"],
        },
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file4 AH via route-based DISTRIBUTERECORD leaf operators.")
    parser.add_argument(
        "--excel-dir",
        type=Path,
        default=Path("example/CIMS-SQL-3.5/EXCEL导出数据"),
    )
    parser.add_argument(
        "--dist-path",
        type=Path,
        default=Path("example/CIMS-SQL-3.5/DISTRIBUTERECORD_20260305.sql"),
    )
    parser.add_argument(
        "--user-path",
        type=Path,
        default=Path("example/CIMS-SQL-3.5/USER_20260305.sql"),
    )
    parser.add_argument(
        "--dept-path",
        type=Path,
        default=Path("example/CIMS-SQL-3.5/DEPARTMENT_20260305.sql"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tmp/file4_dist_route_probe_20260310.json"),
    )
    args = parser.parse_args()
    payload = run(args.excel_dir, args.dist_path, args.user_path, args.dept_path, args.output)
    print(json.dumps(payload["row_counts"], ensure_ascii=False), flush=True)
    for name, metric in payload["metrics"].items():
        print(f"{name}: {metric['hit']}/{metric['total']} = {metric['rate']:.6f}", flush=True)


if __name__ == "__main__":
    main()
