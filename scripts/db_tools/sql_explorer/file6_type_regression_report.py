"""Summarize file6 SEND-side regression status by document type."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


STATUS_PRIORITY = {
    "semantic_gap": 0,
    "chain_and_semantics": 1,
    "chain_gap": 2,
    "workflow_missing": 3,
    "no_excel_baseline": 4,
    "near_closed": 5,
    "closed": 6,
}


def _metric_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
    total = int(payload.get("total", 0) or 0)
    hit = int(payload.get("hit", 0) or 0)
    rate = float(payload.get("rate", 0) or 0)
    return {
        "total": total,
        "hit": hit,
        "rate": rate,
        "closed": bool(total and hit == total),
        "has_baseline": bool(total),
    }


def _classify_type(doc_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    row_count = int(payload.get("row_count", 0) or 0)
    workflow_hits = int(payload.get("rows_with_workflow_hits", 0) or 0)
    workflow_hit_rate = round(workflow_hits / row_count, 6) if row_count else 0.0

    metrics = {
        "X": _metric_summary(payload.get("X_all", {})),
        "V": _metric_summary(payload.get("V_all", {})),
        "W": _metric_summary(payload.get("W_all", {})),
    }
    baselined_metrics = [name for name, item in metrics.items() if item["has_baseline"]]
    closed_metrics = [name for name, item in metrics.items() if item["closed"]]
    all_closed = bool(baselined_metrics) and len(closed_metrics) == len(baselined_metrics)

    near_closed = bool(baselined_metrics) and all(metrics[name]["rate"] >= 0.95 for name in baselined_metrics)

    if all_closed:
        status = "closed"
        next_step = "转抽样复核"
    elif near_closed:
        status = "near_closed"
        next_step = "转抽样复核"
    elif workflow_hits == 0:
        status = "workflow_missing"
        next_step = "先追对象桥"
    elif not baselined_metrics:
        status = "no_excel_baseline"
        next_step = "仅保留链路验证，等待更多 Excel 真值"
    elif workflow_hits < row_count:
        status = "chain_and_semantics"
        next_step = "先补对象桥，再拆责任人口径"
    else:
        status = "semantic_gap"
        next_step = "对象桥已通，优先拆责任人口径"

    return {
        "doc_type": doc_type,
        "status": status,
        "next_step": next_step,
        "row_count": row_count,
        "rows_with_workflow_hits": workflow_hits,
        "workflow_hit_rate": workflow_hit_rate,
        "metrics": metrics,
        "baselined_metrics": baselined_metrics,
        "closed_metrics": closed_metrics,
        "all_metrics_closed": all_closed,
        "near_closed": near_closed,
    }


def build_report(input_path: Path, include_closed: bool) -> Dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    by_type = payload.get("workflow_metrics", {}).get("by_type", {})

    entries = [_classify_type(doc_type, item) for doc_type, item in sorted(by_type.items())]
    entries.sort(key=lambda item: (STATUS_PRIORITY[item["status"]], -item["row_count"], item["doc_type"]))

    stabilized_statuses = {"closed", "near_closed"}
    focus_types = [item for item in entries if include_closed or item["status"] not in stabilized_statuses]
    closed_types = [item for item in entries if item["status"] in stabilized_statuses]

    return {
        "input": str(input_path),
        "summary": {
            "type_count": len(entries),
            "focus_type_count": len(focus_types),
            "closed_type_count": len(closed_types),
        },
        "focus_types": focus_types,
        "closed_types": closed_types,
        "all_types": {item["doc_type"]: item for item in entries},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build file6 regression summary by document type.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("document/file6_send_workflow_probe_20260313_rel2.json"),
        help="Input JSON produced by file6_send_workflow_probe.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("document/file6_type_regression_report_20260313.json"),
        help="Output JSON summary path",
    )
    parser.add_argument("--include-closed", action="store_true", help="Include closed types in focus_types output.")
    args = parser.parse_args()

    report = build_report(args.input, include_closed=args.include_closed)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "focus_type_count": report["summary"]["focus_type_count"],
                "closed_type_count": report["summary"]["closed_type_count"],
                "top_focus_types": [item["doc_type"] for item in report["focus_types"][:8]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
