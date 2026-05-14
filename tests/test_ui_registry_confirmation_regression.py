#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI/Registry confirmation regression tests."""

from unittest.mock import patch

import pandas as pd
import os
import sqlite3
import tempfile


def test_drop_display_rows_preserves_source_indices():
    from ui.window import _drop_display_rows_with_source_indices

    display_df = pd.DataFrame({"接口号": ["A", "B", "C", "D"]})
    filtered_display_df, source_indices = _drop_display_rows_with_source_indices(
        display_df,
        [0, 1, 2, 3],
        [0, 2],
    )

    assert list(filtered_display_df["接口号"]) == ["B", "D"]
    assert source_indices == [1, 3]


def test_selected_confirmation_items_uses_blue_selection_only_when_clicked_inside_selection():
    from ui.window import WindowManager

    class FakeViewer:
        def __init__(self, selected):
            self._selected = selected

        def selection(self):
            return self._selected

    manager = WindowManager.__new__(WindowManager)

    assert manager._selected_confirmation_items(FakeViewer(["a", "b"]), "a") == ["a", "b"]
    assert manager._selected_confirmation_items(FakeViewer(["a", "b"]), "c") == ["c"]


def test_mark_confirmed_archives_and_releases_original_task_id():
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use
    from registry.util import make_task_id

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-TEST-ARCHIVE",
        "source_file": "source.xlsx",
        "row_index": 10,
    }
    try:
        service.upsert_task(
            db_path,
            False,
            key,
            {"display_status": "待审查", "interface_time": "2026.05.14"},
            datetime(2026, 5, 14, 8, 0, 0),
        )
        service.mark_completed(db_path, False, key, datetime(2026, 5, 14, 8, 0, 30))

        archive_info = service.mark_confirmed(
            db_path,
            False,
            key,
            datetime(2026, 5, 14, 8, 1, 0),
            confirmed_by="一室主任",
        )
        close_connection_after_use()

        original_id = make_task_id(1, "2026", "S-TEST-ARCHIVE", "source.xlsx", 10)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        archived_rows = [dict(row) for row in conn.execute("SELECT * FROM tasks").fetchall()]
        exact_exists = conn.execute("SELECT 1 FROM tasks WHERE id = ?", (original_id,)).fetchone()
        conn.close()

        assert archive_info["original_id"] == original_id
        assert exact_exists is None
        assert len(archived_rows) == 1
        assert archived_rows[0]["status"] == "archived"
        assert archived_rows[0]["display_status"] == "已审查"
        assert archived_rows[0]["confirmed_by"] == "一室主任"
        assert archived_rows[0]["archive_reason"] == "confirmed_by_superior"

        service.upsert_task(
            db_path,
            False,
            key,
            {"display_status": "待完成", "interface_time": "2026.05.14"},
            datetime(2026, 5, 14, 8, 2, 0),
        )
        close_connection_after_use()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows_after_rescan = [dict(row) for row in conn.execute("SELECT id, status FROM tasks").fetchall()]
        conn.close()

        assert len(rows_after_rescan) == 2
        assert sum(1 for row in rows_after_rescan if row["status"] != "archived") == 1
        assert any(row["id"] == original_id and row["status"] == "open" for row in rows_after_rescan)
    finally:
        close_connection_after_use()
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_confirmation_task_log_is_visible_in_shared_tasks():
    from write_tasks.models import WriteTask
    from write_tasks.shared_log import list_tasks, upsert_task

    conn = sqlite3.connect(":memory:")
    try:
        task = WriteTask(
            task_id="confirm-1",
            task_type="confirmation",
            payload={
                "confirmations": [
                    {
                        "file_type": 1,
                        "file_path": "source.xlsx",
                        "row_index": 10,
                        "project_id": "2026",
                        "interface_id": "S-TEST-ARCHIVE",
                    }
                ]
            },
            submitted_by="一室主任",
            description="一室主任 审查确认 S-TEST-ARCHIVE",
            status="completed",
        )

        upsert_task(conn, task)
        tasks = list_tasks(conn)

        assert len(tasks) == 1
        assert tasks[0].task_type == "confirmation"
        assert tasks[0].submitted_by == "一室主任"
        assert tasks[0].description == "一室主任 审查确认 S-TEST-ARCHIVE"
        assert tasks[0].status == "completed"
    finally:
        conn.close()


def test_superior_confirm_invalidates_registry_read_cache():
    from registry import hooks

    cfg = {
        "registry_enabled": True,
        "registry_db_path": "E:/tmp/registry.db",
        "registry_wal": False,
    }
    with patch.object(hooks, "_cfg", return_value=cfg), \
            patch.object(hooks, "_retry_on_lock", return_value=None), \
            patch.object(hooks, "invalidate_cache") as invalidate_cache:
        result = hooks.on_confirmed_by_superior(
            file_type=1,
            file_path="E:/tmp/source.xlsx",
            row_index=10,
            user_name="一室主任",
            project_id="2026",
            interface_id="S-TEST-01",
        )

    assert result is True
    invalidate_cache.assert_called_once()


def test_superior_unconfirm_invalidates_registry_read_cache():
    from registry import hooks

    cfg = {
        "registry_enabled": True,
        "registry_db_path": "E:/tmp/registry.db",
        "registry_wal": False,
    }
    key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-TEST-01",
        "source_file": "source.xlsx",
        "row_index": 10,
    }
    with patch.object(hooks, "_cfg", return_value=cfg), \
            patch.object(hooks, "_retry_on_lock", return_value=None), \
            patch.object(hooks, "invalidate_cache") as invalidate_cache:
        result = hooks.on_unconfirmed_by_superior(key=key, user_name="一室主任")

    assert result is True
    invalidate_cache.assert_called_once()
