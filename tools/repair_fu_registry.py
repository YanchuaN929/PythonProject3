#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safely restore current FU tasks wrongly archived as missing_from_source."""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime


def _discover_excel_files(data_folder):
    files = []
    for root, dir_names, file_names in os.walk(data_folder):
        dir_names[:] = [name for name in dir_names if name not in {".registry", "result_cache"}]
        for name in file_names:
            if name.startswith("~$"):
                continue
            if os.path.splitext(name)[1].lower() in {".xlsx", ".xlsm", ".xls"}:
                files.append(os.path.join(root, name))
    return files


def _status_counts(db_path):
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        rows = conn.execute(
            """
            SELECT status, COALESCE(archive_reason, ''),
                   CASE WHEN confirmed_at IS NULL THEN 'not_confirmed' ELSE 'confirmed' END,
                   COUNT(*)
            FROM tasks
            WHERE file_type = 7
            GROUP BY status, COALESCE(archive_reason, ''),
                     CASE WHEN confirmed_at IS NULL THEN 'not_confirmed' ELSE 'confirmed' END
            ORDER BY 1, 2, 3
            """
        ).fetchall()
        return [list(row) for row in rows]
    finally:
        conn.close()


def run(data_folder=None, apply_changes=False):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core import main
    from registry import hooks, service
    from utils.dept_config import get_default_folder_path

    data_folder = os.path.abspath(data_folder or get_default_folder_path())
    db_path = os.path.join(data_folder, ".registry", "registry.db")
    if not os.path.isfile(db_path):
        raise FileNotFoundError("Registry not found: " + db_path)

    hooks.set_data_folder(data_folder)
    excel_files = _discover_excel_files(data_folder)
    targets = main.find_all_target_files7(excel_files)
    now = datetime.now()
    tasks_data = []
    rows_by_project = {}

    main.begin_registry_read_snapshot()
    try:
        for source_file, project_id in targets:
            frame = main.process_target_file7(source_file, now)
            if frame is None:
                raise RuntimeError("FU parser returned None: " + source_file)
            raw_frame = frame.copy()
            raw_frame["项目号"] = project_id
            rows_by_project[str(project_id)] = len(raw_frame)
            tasks_data.extend(hooks._build_process_tasks_data(7, source_file, raw_frame))
    finally:
        main.end_registry_read_snapshot()

    before = _status_counts(db_path)
    result = {
        "mode": "apply" if apply_changes else "preview",
        "db_path": db_path,
        "fu_files": len(targets),
        "rows_by_project": rows_by_project,
        "current_rows": len(tasks_data),
        "before": before,
    }
    if not apply_changes:
        return result

    backup_path = service._ensure_verified_recovery_backup(db_path)
    backup_conn = sqlite3.connect(backup_path, timeout=30.0)
    try:
        backup_counts = tuple(
            backup_conn.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            for table in ("tasks", "events", "ignored_snapshots")
        )
    finally:
        backup_conn.close()
    stats = service.batch_touch_scanned_tasks(db_path, False, tasks_data, now)

    verify = sqlite3.connect(db_path, timeout=30.0)
    try:
        integrity = verify.execute("PRAGMA quick_check").fetchone()[0]
        confirmed_archives = verify.execute(
            """
            SELECT COUNT(*) FROM tasks
            WHERE file_type=7 AND status='archived' AND confirmed_at IS NOT NULL
            """
        ).fetchone()[0]
    finally:
        verify.close()
    if integrity != "ok":
        raise RuntimeError("Registry failed post-repair quick_check: " + str(integrity))

    result.update({
        "backup_path": backup_path,
        "backup_counts": list(backup_counts),
        "sync": stats,
        "after": _status_counts(db_path),
        "confirmed_archives_after": confirmed_archives,
        "integrity": integrity,
    })
    return result


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-folder")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.data_folder, args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main_cli()
