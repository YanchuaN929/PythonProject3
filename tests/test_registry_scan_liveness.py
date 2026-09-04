#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registry scan-liveness and missing-from-source recovery regressions."""

from datetime import datetime, timedelta


def _task(interface_id, row_index, source_file="fu.xlsx", completed_value=""):
    return {
        "key": {
            "file_type": 7,
            "project_id": "2026",
            "interface_id": interface_id,
            "source_file": source_file,
            "row_index": row_index,
        },
        "fields": {
            "department": "请室主任确认",
            "interface_time": "2026-09-10",
            "role": "",
            "display_status": "待完成",
            "responsible_person": "张三",
            "_completed_col_value": completed_value,
            "_source_revision": "100:200",
        },
    }


def _query_one(db_path, sql, params=()):
    from registry.db import close_connection_after_use, get_connection

    conn = get_connection(str(db_path), False)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        close_connection_after_use()


def _execute(db_path, sql, params=()):
    from registry.db import close_connection_after_use, get_connection

    conn = get_connection(str(db_path), False)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        close_connection_after_use()


def test_batch_upsert_restores_unconfirmed_missing_archive_and_keeps_audit_fields(tmp_path):
    from registry import service

    db_path = tmp_path / "registry.db"
    now = datetime(2026, 9, 4, 10, 0, 0)
    item = _task("FU-RESTORE", 10, completed_value="2026-09-03")
    service.batch_upsert_tasks(str(db_path), False, [item], now - timedelta(days=10))
    _execute(
        db_path,
        """
        UPDATE tasks
        SET status='archived', display_status='待审查',
            completed_at=?, completed_by=?, assigned_by=?, assigned_at=?,
            archive_reason='missing_from_source', archived_at=?, missing_since=?
        WHERE interface_id='FU-RESTORE'
        """,
        (
            (now - timedelta(days=9)).isoformat(),
            "张三",
            "李四",
            (now - timedelta(days=20)).isoformat(),
            (now - timedelta(days=1)).isoformat(),
            (now - timedelta(days=8)).isoformat(),
        ),
    )

    assert service.batch_upsert_tasks(str(db_path), False, [item], now) == 1
    backup_files = list((tmp_path / "backups").glob("registry_before_missing_restore_*.db"))
    assert len(backup_files) == 1
    assert _query_one(backup_files[0], "PRAGMA quick_check")[0] == "ok"
    row = _query_one(
        db_path,
        """
        SELECT status, display_status, completed_by, assigned_by,
               missing_since, archive_reason, archived_at, confirmed_at
        FROM tasks WHERE interface_id='FU-RESTORE'
        """,
    )
    assert row == ("completed", "待审查", "张三", "李四", None, None, None, None)


def test_batch_upsert_does_not_reopen_confirmed_archive(tmp_path):
    from registry import service

    db_path = tmp_path / "registry.db"
    now = datetime(2026, 9, 4, 10, 0, 0)
    item = _task("FU-CONFIRMED", 11, completed_value="2026-09-03")
    service.batch_upsert_tasks(str(db_path), False, [item], now - timedelta(days=2))
    _execute(
        db_path,
        """
        UPDATE tasks
        SET status='archived', display_status='已审查', completed_at=?,
            confirmed_at=?, archive_reason='confirmed_by_superior', archived_at=?
        WHERE interface_id='FU-CONFIRMED'
        """,
        ((now - timedelta(days=2)).isoformat(),) * 3,
    )

    service.batch_upsert_tasks(str(db_path), False, [item], now)
    assert not (tmp_path / "backups").exists()
    row = _query_one(
        db_path,
        "SELECT status, display_status, archive_reason, confirmed_at FROM tasks WHERE interface_id='FU-CONFIRMED'",
    )
    assert row[0:3] == ("archived", "已审查", "confirmed_by_superior")
    assert row[3]


def test_cached_touch_refreshes_existing_restores_missing_archive_and_creates_gap(tmp_path):
    from registry import service

    db_path = tmp_path / "registry.db"
    old = datetime(2026, 8, 20, 8, 0, 0)
    now = datetime(2026, 9, 4, 10, 0, 0)
    active = _task("FU-ACTIVE", 12)
    recoverable = _task("FU-RECOVERABLE", 13)
    missing = _task("FU-NEW", 14)
    service.batch_upsert_tasks(str(db_path), False, [active, recoverable], old)
    _execute(
        db_path,
        "UPDATE tasks SET missing_since=? WHERE interface_id='FU-ACTIVE'",
        ((old + timedelta(days=1)).isoformat(),),
    )
    _execute(
        db_path,
        """
        UPDATE tasks
        SET status='archived', archive_reason='missing_from_source',
            archived_at=?, missing_since=?
        WHERE interface_id='FU-RECOVERABLE'
        """,
        ((old + timedelta(days=9)).isoformat(), (old + timedelta(days=1)).isoformat()),
    )

    stats = service.batch_touch_scanned_tasks(
        str(db_path), False, [active, recoverable, missing], now
    )
    assert stats == {"seen": 3, "touched": 2, "restored": 1, "created": 1}
    rows = _query_one(
        db_path,
        """
        SELECT
          SUM(CASE WHEN last_seen_at=? THEN 1 ELSE 0 END),
          SUM(CASE WHEN missing_since IS NULL THEN 1 ELSE 0 END),
          SUM(CASE WHEN status='open' THEN 1 ELSE 0 END),
          SUM(CASE WHEN archive_reason IS NULL THEN 1 ELSE 0 END)
        FROM tasks WHERE file_type=7
        """,
        (now.isoformat(),),
    )
    assert rows == (3, 3, 3, 3)


def test_finalize_scan_only_marks_and_archives_fully_scanned_source(tmp_path):
    from registry import service

    db_path = tmp_path / "registry.db"
    old = datetime(2026, 8, 20, 8, 0, 0)
    first_scan = datetime(2026, 8, 21, 8, 0, 0)
    archive_scan = datetime(2026, 8, 29, 8, 0, 0)
    a = _task("FU-SCOPE-A", 20, source_file="a.xlsx")
    b = _task("FU-SCOPE-B", 21, source_file="b.xlsx")
    service.batch_upsert_tasks(str(db_path), False, [a, b], old)
    scope = [{"file_type": 7, "project_id": "2026", "source_file": "a.xlsx"}]

    stats = service.finalize_scan(str(db_path), False, first_scan, 7, scanned_sources=scope)
    assert stats["marked_missing"] == 1
    assert _query_one(
        db_path,
        "SELECT missing_since FROM tasks WHERE interface_id='FU-SCOPE-B'",
    )[0] is None

    stats = service.finalize_scan(str(db_path), False, archive_scan, 7, scanned_sources=scope)
    assert stats["archived_missing"] == 1
    rows = _query_one(
        db_path,
        """
        SELECT
          MAX(CASE WHEN interface_id='FU-SCOPE-A' THEN status END),
          MAX(CASE WHEN interface_id='FU-SCOPE-B' THEN status END)
        FROM tasks
        """,
    )
    assert rows == ("archived", "open")


def test_pending_loader_includes_only_unconfirmed_recoverable_completed_archive(tmp_path):
    from core import main
    from registry import service

    db_path = tmp_path / "registry.db"
    now = datetime(2026, 9, 4, 10, 0, 0)
    recoverable = _task("FU-PENDING-RECOVER", 30, completed_value="2026-09-03")
    confirmed = _task("FU-PENDING-CLOSED", 31, completed_value="2026-09-03")
    service.batch_upsert_tasks(str(db_path), False, [recoverable, confirmed], now)
    _execute(
        db_path,
        """
        UPDATE tasks SET status='archived', display_status='待审查',
            completed_at=?, completed_by='张三', archive_reason='missing_from_source',
            missing_since=?, archived_at=?
        WHERE interface_id='FU-PENDING-RECOVER'
        """,
        (now.isoformat(), now.isoformat(), now.isoformat()),
    )
    _execute(
        db_path,
        """
        UPDATE tasks SET status='archived', display_status='已审查',
            completed_at=?, confirmed_at=?, archive_reason='confirmed_by_superior', archived_at=?
        WHERE interface_id='FU-PENDING-CLOSED'
        """,
        (now.isoformat(), now.isoformat(), now.isoformat()),
    )

    rows = main._load_latest_registry_pending_tasks_uncached(7, str(db_path), False)
    assert [(row[0], row[2], row[3]) for row in rows] == [
        ("FU-PENDING-RECOVER", "待审查", "completed")
    ]
