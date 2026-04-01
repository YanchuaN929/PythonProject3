"""Probe file6 SEND-side handler chain through workflow tables."""

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
from pathlib import Path
from typing import List

from core.sql.file6_send_resolver import resolve_file6_send_rows


def run(
    excel_dir: Path,
    sql35_dir: Path,
    sql37_dir: Path,
    output_path: Path,
    temp_dir: Path,
    doc_types: List[str] | None = None,
    detail_output: Path | None = None,
):
    payload = resolve_file6_send_rows(
        excel_dir=excel_dir,
        sql35_dir=sql35_dir,
        sql37_dir=sql37_dir,
        temp_dir=temp_dir,
        doc_types=doc_types,
        include_detail_rows=detail_output is not None,
    )
    detail_rows = payload.pop("detail_rows", None)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if detail_output is not None:
        detail_output.parent.mkdir(parents=True, exist_ok=True)
        detail_output.write_text(
            json.dumps(
                {
                    "inputs": payload["inputs"],
                    "row_counts": payload["row_counts"],
                    "table_scans": {
                        "WORKFLOWPROCESSESBIND": payload["table_scans"]["WORKFLOWPROCESSESBIND"],
                        "USERVOTERECORD": payload["table_scans"]["USERVOTERECORD"],
                    },
                    "rows": detail_rows or [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file6 SEND-side workflow handlers.")
    parser.add_argument("--excel-dir", type=Path, default=Path("example/CIMS-SQL-3.5/EXCEL导出数据"))
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--sql37-dir", type=Path, default=Path("example/CIMS-sql-3.7"))
    parser.add_argument("--output", type=Path, default=Path("tmp/file6_send_workflow_probe_20260312.json"))
    parser.add_argument("--temp-dir", type=Path, default=Path("tmp/file6_send_workflow_probe"))
    parser.add_argument("--detail-output", type=Path, help="Optional row-level detail JSON for type-specific role probing.")
    parser.add_argument("--doc-types", nargs="*", help="Optional A-column doc types to probe. Supports comma-separated values.")
    args = parser.parse_args()

    doc_types: List[str] = []
    for raw_value in args.doc_types or []:
        doc_types.extend([item.strip() for item in raw_value.split(",") if item.strip()])

    payload = run(
        args.excel_dir,
        args.sql35_dir,
        args.sql37_dir,
        args.output,
        args.temp_dir,
        doc_types=doc_types or None,
        detail_output=args.detail_output,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "doc_types": payload["inputs"]["doc_types"],
                "version_best_rows": payload["row_counts"]["version_best_send_rows"],
                "rows_with_workflow_hits": payload["row_counts"]["version_best_rows_with_workflow_hits"],
                "x_rate": payload["workflow_metrics"]["version_best"]["X_all"]["rate"],
                "v_rate": payload["workflow_metrics"]["version_best"]["V_all"]["rate"],
                "w_rate": payload["workflow_metrics"]["version_best"]["W_all"]["rate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
