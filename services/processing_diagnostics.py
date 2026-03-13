#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processing diagnostics written to the configured export directory."""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd

from core.sql.file2_db_source import get_file2_debug_snapshots
from core.sql.file3_db_source import get_file3_debug_snapshots
from core.sql.file4_db_source import get_file4_debug_snapshots
from core.sql.provider import get_sql_backend_status


def _row_count(df: Any) -> int:
    return int(len(df)) if isinstance(df, pd.DataFrame) else 0


def _resolve_output_dir(config: Dict[str, Any]) -> Path:
    config = config or {}
    candidate_paths = [
        str(config.get("export_folder_path", "")).strip(),
        str((config.get("defaults", {}) or {}).get("export_path", "")).strip(),
    ]
    for export_path in candidate_paths:
        if not export_path:
            continue
        try:
            output_dir = Path(export_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir
        except Exception:
            continue

    if getattr(sys, "frozen", False):
        output_dir = Path(sys.executable).resolve().parent / "diagnostics"
    else:
        output_dir = Path.cwd() / "diagnostics"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _sorted_projects(projects: Iterable[Any]) -> list[str]:
    return sorted(str(item).strip() for item in (projects or []) if str(item).strip())


def build_processing_diagnostic_report(app: Any, total_projects=None, error_message: str = "") -> str:
    now = datetime.datetime.now()
    backend_status = get_sql_backend_status()
    total_projects = _sorted_projects(total_projects or set())
    config = getattr(app, "config", {}) or {}

    lines = [
        "=== Processing Diagnostic Report ===",
        f"time: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"app_version: {getattr(app, 'current_version', '')}",
        f"python_executable: {sys.executable}",
        f"cwd: {os.getcwd()}",
        "",
        "[Config]",
        f"folder_path: {str(config.get('folder_path', '')).strip()}",
        f"export_folder_path: {str(config.get('export_folder_path', '')).strip()}",
        f"user_name: {str(config.get('user_name', '')).strip()}",
        f"current_datetime: {getattr(app, 'current_datetime', now)}",
        "",
        "[SQL Backend]",
        f"mode: {backend_status.get('mode', '')}",
        f"connected: {backend_status.get('connected', '')}",
        f"message: {backend_status.get('message', '')}",
        f"offline_root: {backend_status.get('offline_root', '')}",
        "",
        "[Selection]",
        f"selected_projects: {', '.join(total_projects)}",
        f"process_file1: {bool(getattr(app, 'process_file1_var', None).get() if getattr(app, 'process_file1_var', None) else False)}",
        f"process_file2: {bool(getattr(app, 'process_file2_var', None).get() if getattr(app, 'process_file2_var', None) else False)}",
        f"process_file3: {bool(getattr(app, 'process_file3_var', None).get() if getattr(app, 'process_file3_var', None) else False)}",
        f"process_file4: {bool(getattr(app, 'process_file4_var', None).get() if getattr(app, 'process_file4_var', None) else False)}",
        f"target_files1: {len(getattr(app, 'target_files1', []) or [])}",
        f"target_files2: {len(getattr(app, 'target_files2', []) or [])}",
        f"target_files3: {len(getattr(app, 'target_files3', []) or [])}",
        f"target_files4: {len(getattr(app, 'target_files4', []) or [])}",
        "",
        "[Results]",
    ]

    result_specs = [
        ("待处理文件1", getattr(app, "processing_results", None), getattr(app, "processing_results_multi1", {})),
        ("待处理文件2", getattr(app, "processing_results2", None), getattr(app, "processing_results_multi2", {})),
        ("待处理文件3", getattr(app, "processing_results3", None), getattr(app, "processing_results_multi3", {})),
        ("待处理文件4", getattr(app, "processing_results4", None), getattr(app, "processing_results_multi4", {})),
    ]
    for label, df, multi in result_specs:
        lines.append(f"{label}: rows={_row_count(df)} projects={len(multi or {})}")
        if isinstance(multi, dict) and multi:
            for project_id in sorted(multi.keys(), key=lambda item: str(item)):
                lines.append(f"  - {project_id}: rows={_row_count(multi.get(project_id))}")
    lines.append("")

    lines.append("[Live Query Debug]")
    live_debug = {
        "file2": get_file2_debug_snapshots(),
        "file3": get_file3_debug_snapshots(),
        "file4": get_file4_debug_snapshots(),
    }
    for label, payload in live_debug.items():
        lines.append(f"{label}:")
        if payload:
            lines.append(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            lines.append("  {}")
    lines.append("")

    if error_message:
        lines.extend(["[Error]", error_message, ""])

    total_rows = sum(_row_count(item[1]) for item in result_specs)
    if str(backend_status.get("connected", "0")) == "1" and total_rows == 0:
        lines.extend(
            [
                "[Hint]",
                "SQL 已连接，但本轮 1~4 结果均为 0。优先检查项目号、组织过滤、时间窗口和桥接链。",
                "",
            ]
        )

    return "\n".join(lines)


def write_processing_diagnostic_log(app: Any, total_projects=None, error_message: str = "") -> str:
    output_dir = _resolve_output_dir(getattr(app, "config", {}) or {})
    filename = f"processing_diagnostic_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path_obj = output_dir / filename
    report_text = build_processing_diagnostic_report(app, total_projects=total_projects, error_message=error_message)
    path_obj.write_text(report_text, encoding="utf-8")
    return str(path_obj)
