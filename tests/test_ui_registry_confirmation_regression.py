#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI/Registry confirmation regression tests."""

from unittest.mock import patch

import pandas as pd
import os
import pytest
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


def test_realtime_archived_snapshot_overrides_stale_display_status():
    from ui.window import _terminal_registry_status_from_snapshot

    assert _terminal_registry_status_from_snapshot({
        "status": "archived",
        "display_status": "待审查",
        "confirmed_at": "2026-07-23T08:00:00+00:00",
    }) == "已审查"
    assert _terminal_registry_status_from_snapshot({
        "status": "confirmed",
        "display_status": "待审查",
    }) == "已审查"
    assert _terminal_registry_status_from_snapshot({
        "status": "completed",
        "display_status": "待审查",
    }) is None


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


def test_batch_task_resolution_matches_single_resolution_for_active_and_archive():
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use
    from registry.util import make_task_id

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    active_key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-BATCH-ACTIVE",
        "source_file": "source.xlsx",
        "row_index": 10,
        "interface_time": "2026.07.25",
    }
    archived_key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-BATCH-ARCHIVED",
        "source_file": "source.xlsx",
        "row_index": 11,
        "interface_time": "2026.07.25",
    }
    try:
        for key in (active_key, archived_key):
            service.upsert_task(
                db_path,
                False,
                key,
                {"display_status": "待审查", "interface_time": key["interface_time"]},
                datetime(2026, 7, 23, 8, 0, key["row_index"]),
            )
        service.mark_completed(
            db_path,
            False,
            archived_key,
            datetime(2026, 7, 23, 8, 1, 0),
        )
        service.mark_confirmed(
            db_path,
            False,
            archived_key,
            datetime(2026, 7, 23, 8, 2, 0),
            confirmed_by="一室主任",
        )

        task_keys = [active_key, archived_key]
        batch = service.resolve_task_records(db_path, False, task_keys)
        singles = {
            make_task_id(
                key["file_type"],
                key["project_id"],
                key["interface_id"],
                key["source_file"],
                key["row_index"],
            ): service.resolve_task_record(db_path, False, key)
            for key in task_keys
        }

        assert set(batch) == set(singles)
        for task_id in batch:
            assert batch[task_id]["status"] == singles[task_id]["status"]
            assert batch[task_id]["display_status"] == singles[task_id]["display_status"]

        statuses = service.get_display_status(
            db_path,
            False,
            task_keys,
            ["管理员"],
            task_snapshots=batch,
        )
        archived_id = make_task_id(
            archived_key["file_type"],
            archived_key["project_id"],
            archived_key["interface_id"],
            archived_key["source_file"],
            archived_key["row_index"],
        )
        # 本用例验证批量/单条解析一致性；是否增加延期前缀取决于运行日期。
        assert statuses[archived_id].endswith("已审查")
    finally:
        close_connection_after_use()
        try:
            os.remove(db_path)
        except OSError:
            pass


def test_mark_confirmed_archives_all_active_rows_for_same_business(tmp_path):
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use

    db_path = str(tmp_path / "registry.db")
    common = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-TEST-DUPLICATE-ACTIVE",
    }
    old_key = {**common, "source_file": "old-source.xlsx", "row_index": 10}
    current_key = {**common, "source_file": "current-source.xlsx", "row_index": 20}

    for key, minute in ((old_key, 0), (current_key, 1)):
        now = datetime(2026, 7, 22, 10, minute, 0)
        service.upsert_task(
            db_path,
            False,
            key,
            {
                "display_status": "待审查",
                "status": "completed",
                "completed_at": now.isoformat(),
                "interface_time": "2026.07.22",
                "_completed_col_value": "2026.07.22",
            },
            now,
        )

    archive_info = service.mark_confirmed(
        db_path,
        False,
        current_key,
        datetime(2026, 7, 22, 10, 2, 0),
        confirmed_by="管理员",
    )
    close_connection_after_use()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT status, display_status, confirmed_by, archive_reason
            FROM tasks
            WHERE business_id = ?
            """,
            ("1|2026|S-TEST-DUPLICATE-ACTIVE",),
        ).fetchall()
    finally:
        conn.close()

    assert archive_info["archived_count"] == 2
    assert len(rows) == 2
    assert all(row == ("archived", "已审查", "管理员", "confirmed_by_superior") for row in rows)


def test_newer_confirmed_archive_supersedes_legacy_active_duplicate(tmp_path):
    from datetime import datetime
    from core.main import _load_latest_registry_pending_tasks
    from registry import service
    from registry.db import close_connection_after_use

    db_path = str(tmp_path / "registry.db")
    common = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-TEST-LEGACY-DUPLICATE",
    }
    current_key = {**common, "source_file": "current-source.xlsx", "row_index": 20}
    stale_key = {**common, "source_file": "old-source.xlsx", "row_index": 10}

    service.upsert_task(
        db_path,
        False,
        current_key,
        {
            "display_status": "待审查",
            "status": "completed",
            "completed_at": "2026-07-22T10:00:00",
            "interface_time": "2026.07.22",
            "_completed_col_value": "2026.07.22",
        },
        datetime(2026, 7, 22, 10, 0, 0),
    )
    service.mark_confirmed(
        db_path,
        False,
        current_key,
        datetime(2026, 7, 22, 10, 2, 0),
        confirmed_by="管理员",
    )

    # Simulate an old Registry left behind by the previous one-row confirmation logic.
    service.upsert_task(
        db_path,
        False,
        stale_key,
        {
            "display_status": "待审查",
            "status": "completed",
            "completed_at": "2026-07-14T08:00:00",
            "interface_time": "2026.07.22",
            "_completed_col_value": "2026.07.22",
        },
        datetime(2026, 7, 14, 8, 0, 0),
    )
    close_connection_after_use()

    snapshot = service.resolve_task_record(db_path, False, stale_key)
    pending = _load_latest_registry_pending_tasks(1, db_path, False)
    close_connection_after_use()

    assert snapshot is not None
    assert snapshot["status"] == "archived"
    assert snapshot["display_status"] == "已审查"
    assert pending == []


@pytest.mark.parametrize("file_type", range(1, 8))
def test_completed_value_in_new_source_auto_confirms_pending_review(tmp_path, file_type):
    from datetime import datetime
    from core.main import _load_latest_registry_pending_tasks
    from registry import service
    from registry.db import close_connection_after_use

    db_path = str(tmp_path / f"registry-{file_type}.db")
    common = {
        "file_type": file_type,
        "project_id": "2026",
        "interface_id": f"AUTO-CLOSE-{file_type}",
    }
    old_key = {**common, "source_file": "source-v1.xlsx", "row_index": 10}
    new_key = {**common, "source_file": "source-v2.xlsx", "row_index": 20}

    service.upsert_task(
        db_path,
        False,
        old_key,
        {
            "display_status": "待审查",
            "status": "completed",
            "completed_at": "2026-07-20T08:00:00",
            "interface_time": "2026.07.25",
            "_completed_col_value": "2026.07.20",
        },
        datetime(2026, 7, 20, 8, 0, 0),
    )

    count = service.batch_upsert_tasks(
        db_path,
        False,
        [{
            "key": new_key,
            "fields": {
                "display_status": "待完成",
                "interface_time": "2026.07.25",
                "_completed_col_value": "2026.07.21",
            },
        }],
        datetime(2026, 7, 22, 9, 0, 0),
    )
    close_connection_after_use()

    conn = sqlite3.connect(db_path)
    try:
        task_rows = conn.execute(
            """
            SELECT status, display_status, confirmed_by, archive_reason
            FROM tasks WHERE business_id = ?
            """,
            (f"{file_type}|2026|AUTO-CLOSE-{file_type}",),
        ).fetchall()
        events = conn.execute(
            """
            SELECT event FROM events
            WHERE interface_id = ? AND source_file = ?
            ORDER BY id
            """,
            (f"AUTO-CLOSE-{file_type}", "source-v2.xlsx"),
        ).fetchall()
    finally:
        conn.close()

    snapshot = service.resolve_task_record(db_path, False, new_key)
    pending = _load_latest_registry_pending_tasks(file_type, db_path, False)
    close_connection_after_use()

    assert count == 1
    assert task_rows == [(
        "archived",
        "已审查",
        "源文件更新自动确认",
        "completed_in_new_source",
    )]
    assert events == [("confirmed",), ("archived",)]
    assert snapshot is not None
    assert snapshot["status"] == "archived"
    assert snapshot["display_status"] == "已审查"
    assert pending == []


def test_completed_value_in_same_source_remains_pending_review(tmp_path):
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use

    db_path = str(tmp_path / "registry.db")
    key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "SAME-SOURCE-PENDING",
        "source_file": "source.xlsx",
        "row_index": 10,
    }
    service.upsert_task(
        db_path,
        False,
        key,
        {
            "display_status": "待审查",
            "status": "completed",
            "completed_at": "2026-07-20T08:00:00",
            "interface_time": "2026.07.25",
            "_completed_col_value": "2026.07.20",
            "_source_revision": "1000:1000000000",
        },
        datetime(2026, 7, 20, 8, 0, 0),
    )
    service.batch_upsert_tasks(
        db_path,
        False,
        [{
            "key": key,
            "fields": {
                "display_status": "待完成",
                "interface_time": "2026.07.25",
                "_completed_col_value": "2026.07.20",
                "_source_revision": "1000:1000000000",
            },
        }],
        datetime(2026, 7, 20, 8, 1, 0),
    )
    close_connection_after_use()

    snapshot = service.resolve_task_record(db_path, False, key)
    close_connection_after_use()

    assert snapshot is not None
    assert snapshot["status"] == "completed"
    assert snapshot["display_status"] == "待审查"


def test_completed_value_in_revised_same_source_auto_confirms_pending_review(tmp_path):
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use

    db_path = str(tmp_path / "registry.db")
    key = {
        "file_type": 7,
        "project_id": "1916",
        "interface_id": "FU-SAME-NAME",
        "source_file": "1916项目标准表格.xlsx",
        "row_index": 10,
    }
    service.upsert_task(
        db_path,
        False,
        key,
        {
            "display_status": "待审查",
            "status": "completed",
            "completed_at": "2026-07-20T08:00:00",
            "interface_time": "2026.07.25",
            "_completed_col_value": "2026.07.20",
            "_source_revision": "1000:1000000000",
        },
        datetime(2026, 7, 20, 8, 0, 0),
    )
    count = service.batch_upsert_tasks(
        db_path,
        False,
        [{
            "key": key,
            "fields": {
                "display_status": "待完成",
                "interface_time": "2026.07.25",
                "_completed_col_value": "2026.07.21",
                "_source_revision": "1200:2000000000",
            },
        }],
        datetime(2026, 7, 22, 9, 0, 0),
    )
    close_connection_after_use()

    snapshot = service.resolve_task_record(db_path, False, key)
    close_connection_after_use()

    assert count == 1
    assert snapshot is not None
    assert snapshot["status"] == "archived"
    assert snapshot["display_status"] == "已审查"
    assert snapshot["archive_reason"] == "completed_in_new_source"


def test_rescan_same_completed_row_does_not_recreate_confirmed_archived_task(tmp_path):
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use

    db_path = str(tmp_path / "registry.db")
    key = {
        "file_type": 2,
        "project_id": "2416",
        "interface_id": "S-PE---1HJ-01-25E5-25C3",
        "source_file": "内部接口信息单报表241620260616.xlsx",
        "row_index": 20,
    }
    base_fields = {
        "department": "结构一室",
        "interface_time": "2026.06.16",
        "role": "设计人员",
        "display_status": "待完成",
        "responsible_person": "张三",
        "assigned_by": "李子香（2416接口工程师）",
    }

    service.upsert_task(db_path, False, key, dict(base_fields), datetime(2026, 6, 16, 10, 0, 0))
    service.mark_completed(db_path, False, key, datetime(2026, 6, 16, 10, 1, 0))
    service.mark_confirmed(
        db_path,
        False,
        key,
        datetime(2026, 6, 16, 10, 2, 0),
        confirmed_by="李子香",
    )
    close_connection_after_use()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE tasks SET interface_time = '' WHERE business_id = ? AND status = 'archived'",
            ("2|2416|S-PE---1HJ-01-25E5-25C3",),
        )
        conn.commit()
    finally:
        conn.close()

    unchanged_completed_fields = dict(base_fields)
    unchanged_completed_fields["_completed_col_value"] = "2026.06.16"
    count = service.batch_upsert_tasks(
        db_path,
        False,
        [{"key": key, "fields": unchanged_completed_fields}],
        datetime(2026, 6, 16, 10, 3, 0),
    )
    close_connection_after_use()

    conn = sqlite3.connect(db_path)
    try:
        active_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE business_id = ? AND status != 'archived'",
            ("2|2416|S-PE---1HJ-01-25E5-25C3",),
        ).fetchone()[0]
        archived_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE business_id = ? AND status = 'archived'",
            ("2|2416|S-PE---1HJ-01-25E5-25C3",),
        ).fetchone()[0]
    finally:
        conn.close()

    assert count == 0
    assert active_count == 0
    assert archived_count == 1

    reset_fields = dict(base_fields)
    reset_fields["_completed_col_value"] = ""
    count = service.batch_upsert_tasks(
        db_path,
        False,
        [{"key": key, "fields": reset_fields}],
        datetime(2026, 6, 16, 10, 4, 0),
    )
    close_connection_after_use()

    conn = sqlite3.connect(db_path)
    try:
        active_rows = conn.execute(
            "SELECT status, display_status FROM tasks WHERE business_id = ? AND status != 'archived'",
            ("2|2416|S-PE---1HJ-01-25E5-25C3",),
        ).fetchall()
    finally:
        conn.close()

    assert count == 1
    assert active_rows == [("open", "待完成")]


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


def test_process_done_invalidates_registry_read_cache():
    from registry import hooks

    cfg = {
        "registry_enabled": True,
        "registry_db_path": "E:/tmp/registry.db",
        "registry_wal": False,
    }
    result_df = pd.DataFrame({"接口号": ["S-TEST-01"]})
    task_key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "S-TEST-01",
        "source_file": "source.xlsx",
        "row_index": 10,
    }

    with patch.object(hooks, "_cfg", return_value=cfg), \
            patch.object(hooks, "_ensure_data_folder_from_path"), \
            patch.object(hooks, "get_source_revision", return_value="revision"), \
            patch.object(hooks, "build_task_key_from_row", return_value=task_key), \
            patch.object(hooks, "build_task_fields_from_row", return_value={}), \
            patch.object(hooks, "batch_upsert_tasks", return_value=1), \
            patch.object(hooks, "write_event"), \
            patch.object(hooks, "invalidate_cache") as invalidate_cache:
        hooks.on_process_done(
            file_type=1,
            project_id="2026",
            source_file="E:/tmp/source.xlsx",
            result_df=result_df,
        )

    invalidate_cache.assert_called_once()


def test_assignment_invalidates_registry_read_cache():
    from registry import hooks

    cfg = {
        "registry_enabled": True,
        "registry_db_path": "E:/tmp/registry.db",
        "registry_wal": False,
    }
    with patch.object(hooks, "_cfg", return_value=cfg), \
            patch.object(hooks, "_retry_on_lock", return_value=None), \
            patch.object(hooks, "invalidate_cache") as invalidate_cache:
        result = hooks.on_assigned(
            file_type=1,
            file_path="E:/tmp/source.xlsx",
            row_index=10,
            interface_id="S-TEST-01",
            project_id="2026",
            assigned_by="接口工程师",
            assigned_to="张三",
        )

    assert result is True
    invalidate_cache.assert_called_once()


def test_scan_finalize_invalidates_registry_read_cache():
    from registry import hooks

    cfg = {
        "registry_enabled": True,
        "registry_db_path": "E:/tmp/registry.db",
        "registry_wal": False,
        "registry_missing_keep_days": 7,
    }
    scopes = [{"file_type": 7, "project_id": "2026", "source_file": "fu.xlsx"}]
    with patch.object(hooks, "_cfg", return_value=cfg), \
            patch("registry.service.finalize_scan") as finalize_scan, \
            patch.object(hooks, "invalidate_cache") as invalidate_cache:
        assert hooks.on_scan_finalize(
            batch_tag="20260723_120000",
            scanned_sources=scopes,
        ) is True

    invalidate_cache.assert_called_once()
    assert finalize_scan.call_args.kwargs["scanned_sources"] == scopes


def test_clear_viewer_metadata_only_removes_target_viewer_rows():
    from ui.window import WindowManager

    manager = WindowManager.__new__(WindowManager)
    viewer = object()
    other_viewer = object()
    manager._item_metadata = {
        (viewer, "row-1"): {"interface_id": "A"},
        (viewer, "row-2"): {"interface_id": "B"},
        (other_viewer, "row-3"): {"interface_id": "C"},
    }

    manager._clear_viewer_metadata(viewer)

    assert list(manager._item_metadata) == [(other_viewer, "row-3")]


def test_partial_registry_status_map_only_hides_explicit_terminal_tasks(monkeypatch):
    from base import ExcelProcessorApp
    from registry import hooks
    from registry.util import make_task_id

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.config = {"auto_hide_overdue_enabled": False}
    app.user_roles = ["管理员"]
    source_file = "E:/tmp/2026按项目导出IDI手册2026-07-23.xlsx"
    data = pd.DataFrame([
        {"项目号": "2026", "接口号": "S-A", "原始行号": 2},
        {"项目号": "2026", "接口号": "S-B", "原始行号": 3},
        {"项目号": "2026", "接口号": "S-C", "原始行号": 4},
    ])

    def partial_state(task_keys, *_args, **_kwargs):
        key = task_keys[0]
        task_id = make_task_id(
            key["file_type"], key["project_id"], key["interface_id"],
            key["source_file"], key["row_index"],
        )
        snapshots = {}
        for candidate in task_keys:
            if candidate.get("interface_id") != "S-B":
                continue
            candidate_id = make_task_id(
                candidate["file_type"],
                candidate["project_id"],
                candidate["interface_id"],
                candidate["source_file"],
                candidate["row_index"],
            )
            snapshots[candidate_id] = {
                "status": "archived",
                "display_status": "待审查",
            }
        return {task_id: "待审查"}, snapshots

    monkeypatch.setattr(hooks, "get_display_state", partial_state)

    result = app._exclude_pending_confirmation_rows(
        data,
        source_file=source_file,
        file_type=1,
        project_id="2026",
    )

    assert result["接口号"].tolist() == ["S-A", "S-C"]


def test_user_tab_switch_reuses_rendered_tree_until_forced_refresh():
    from base import ExcelProcessorApp

    class FakeNotebook:
        @staticmethod
        def select():
            return "tab2"

        @staticmethod
        def index(_selection):
            return 1

    class FakeViewer:
        @staticmethod
        def get_children():
            return ("existing-row",)

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.notebook = FakeNotebook()
    app.tab2_viewer = FakeViewer()
    app.processing_results2 = pd.DataFrame([{"原始行号": 2}])
    app.user_roles = ["管理员"]
    app.target_file2 = "source.xlsx"
    app.has_processed_results2 = True
    app._suppress_tab_change_render = False
    signature = (
        id(app.processing_results2),
        len(app.processing_results2),
        tuple(app.user_roles),
        True,
    )
    app._tab_render_signatures = {1: signature}
    render_calls = []
    app.display_results2 = lambda *_args, **_kwargs: render_calls.append("rendered")

    ExcelProcessorApp.on_tab_changed(app, "user_tab_switch")
    assert render_calls == []

    ExcelProcessorApp.on_tab_changed(app, None)
    assert render_calls == ["rendered"]


def test_processed_tabs_are_preloaded_in_separate_ui_slices():
    from base import ExcelProcessorApp

    class FakeRoot:
        def __init__(self):
            self.callbacks = []

        def after_idle(self, callback):
            self.callbacks.append(callback)

        def after(self, _delay, callback):
            self.callbacks.append(callback)

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.root = FakeRoot()
    app._tab_preload_generation = 0
    app._tab_render_signatures = {}
    for index in range(1, 8):
        setattr(app, f"has_processed_results{index}", index in (1, 2, 4))

    render_calls = []
    app._render_tab_by_index = (
        lambda tab_index, reuse_rendered=False:
        render_calls.append((tab_index, reuse_rendered))
    )

    ExcelProcessorApp._schedule_processed_tab_preload(app, active_tab=1)

    # 首次只登记一个 idle 回调；每个回调只渲染一个选项卡。
    assert len(app.root.callbacks) == 1
    first_callback = app.root.callbacks.pop(0)
    first_callback()
    assert render_calls == [(0, True)]
    assert len(app.root.callbacks) == 1

    second_callback = app.root.callbacks.pop(0)
    second_callback()
    assert render_calls == [(0, True), (3, True)]
    assert app.root.callbacks == []


def test_new_processing_generation_cancels_stale_tab_preload():
    from base import ExcelProcessorApp

    class FakeRoot:
        def __init__(self):
            self.callbacks = []

        def after_idle(self, callback):
            self.callbacks.append(callback)

        def after(self, _delay, callback):
            self.callbacks.append(callback)

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.root = FakeRoot()
    app._tab_preload_generation = 0
    app._tab_render_signatures = {1: ("old",)}
    for index in range(1, 8):
        setattr(app, f"has_processed_results{index}", index == 2)

    render_calls = []
    app._render_tab_by_index = (
        lambda tab_index, reuse_rendered=False:
        render_calls.append((tab_index, reuse_rendered))
    )

    ExcelProcessorApp._schedule_processed_tab_preload(app, active_tab=0)
    stale_callback = app.root.callbacks.pop(0)
    ExcelProcessorApp._cancel_tab_preload(app, clear_signatures=True)
    stale_callback()

    assert render_calls == []
    assert app._tab_render_signatures == {}


def test_post_processing_renders_active_tab_then_schedules_preload():
    from base import ExcelProcessorApp

    class FakeNotebook:
        def __init__(self):
            self.selected = None

        def select(self, tab_index):
            self.selected = tab_index

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.notebook = FakeNotebook()
    app._tab_preload_generation = 2
    app._tab_render_signatures = {0: ("stale",)}
    events = []
    app.on_tab_changed = lambda event: events.append(("render", event))
    app._schedule_processed_tab_preload = (
        lambda active_tab: events.append(("preload", active_tab))
    )

    ExcelProcessorApp._post_processing_select_and_render_active_tab(app, active_tab=3)

    assert app.notebook.selected == 3
    assert app._suppress_tab_change_render is False
    assert app._tab_render_signatures == {}
    assert events == [("render", None), ("preload", 3)]
