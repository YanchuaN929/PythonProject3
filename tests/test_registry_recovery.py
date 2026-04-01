#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

import pytest


pytestmark = pytest.mark.allow_empty_name


def test_rebuild_database_from_legacy_schema_preserves_core_rows(tmp_path):
    from registry.recovery import rebuild_database_from_compatible_source

    source_db = tmp_path / "legacy.db"
    target_db = tmp_path / "rebuilt.db"

    conn = sqlite3.connect(str(source_db))
    try:
        conn.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                file_type INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                interface_id TEXT NOT NULL,
                source_file TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                department TEXT DEFAULT '',
                interface_time TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                completed_at TEXT NULL,
                confirmed_at TEXT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event TEXT NOT NULL,
                file_type INTEGER,
                project_id TEXT,
                interface_id TEXT,
                source_file TEXT,
                row_index INTEGER,
                extra TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tasks (
                id, file_type, project_id, interface_id, source_file, row_index,
                department, interface_time, status, completed_at, confirmed_at,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "task-1",
                1,
                "2026",
                "IF-001",
                "source.xlsx",
                2,
                "建筑",
                "2026-03-01",
                "open",
                None,
                None,
                "2026-03-01T08:00:00",
                "2026-03-01T09:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO events (
                ts, event, file_type, project_id, interface_id, source_file, row_index, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-03-01T09:00:00",
                "process_done",
                1,
                "2026",
                "IF-001",
                "source.xlsx",
                2,
                '{"count":1}',
            ),
        )
        conn.commit()
    finally:
        conn.close()

    stats = rebuild_database_from_compatible_source(str(source_db), str(target_db))

    assert stats["tasks"] == 1
    assert stats["events"] == 1

    rebuilt_conn = sqlite3.connect(str(target_db))
    try:
        task_row = rebuilt_conn.execute(
            "SELECT business_id, display_status, status, first_seen_at, last_seen_at "
            "FROM tasks WHERE id = ?",
            ("task-1",),
        ).fetchone()
        assert task_row[0] == "1|2026|IF-001"
        assert task_row[1] is None
        assert task_row[2] == "open"
        assert task_row[3] == "2026-03-01T08:00:00"
        assert task_row[4] == "2026-03-01T09:00:00"

        event_row = rebuilt_conn.execute(
            "SELECT event, project_id FROM events WHERE interface_id = ?",
            ("IF-001",),
        ).fetchone()
        assert event_row == ("process_done", "2026")
    finally:
        rebuilt_conn.close()


def test_get_connection_runs_compatibility_guard(monkeypatch, tmp_path):
    from registry import db as registry_db

    db_path = tmp_path / "data" / ".registry" / "registry.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    called = []

    def fake_ensure_database_compatible(path):
        called.append(path)
        return {"status": "healthy", "healthy": True}

    monkeypatch.setattr(
        "registry.recovery.ensure_database_compatible",
        fake_ensure_database_compatible,
    )

    conn = registry_db.get_connection(str(db_path), wal=False)
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        registry_db.close_connection()

    assert called == [str(db_path)]


def test_find_task_by_business_id_supports_legacy_schema(tmp_path):
    from registry.service import find_task_by_business_id

    db_path = tmp_path / "legacy_find.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                file_type INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                interface_id TEXT NOT NULL,
                source_file TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                department TEXT DEFAULT '',
                interface_time TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                completed_at TEXT NULL,
                confirmed_at TEXT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tasks (
                id, file_type, project_id, interface_id, source_file, row_index,
                department, interface_time, status, completed_at, confirmed_at,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-task",
                1,
                "2026",
                "IF-LEGACY",
                "legacy.xlsx",
                3,
                "建筑",
                "2026-03-05",
                "open",
                None,
                None,
                "2026-03-05T08:00:00",
                "2026-03-05T09:00:00",
            ),
        )
        conn.commit()

        task = find_task_by_business_id(
            str(db_path),
            wal=False,
            file_type=1,
            project_id="2026",
            interface_id="IF-LEGACY",
            conn=conn,
        )
    finally:
        conn.close()

    assert task is not None
    assert task["id"] == "legacy-task"
    assert task["display_status"] is None
    assert task["responsible_person"] is None
    assert task["ignored"] == 0


def test_query_task_history_supports_legacy_schema(tmp_path):
    from registry.service import query_task_history

    db_path = tmp_path / "legacy_history.db"
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                file_type INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                interface_id TEXT NOT NULL,
                source_file TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                department TEXT DEFAULT '',
                interface_time TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                completed_at TEXT NULL,
                confirmed_at TEXT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO tasks (
                id, file_type, project_id, interface_id, source_file, row_index,
                department, interface_time, status, completed_at, confirmed_at,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-history",
                6,
                "1818",
                "IF-HISTORY",
                "legacy.xlsx",
                8,
                "总图",
                "2026-03-06",
                "completed",
                None,
                None,
                "2026-03-06T08:00:00",
                "2026-03-06T09:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    rows = query_task_history(
        str(db_path),
        wal=False,
        project_id="1818",
        interface_id="IF-HISTORY",
        file_type=6,
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "legacy-history"
    assert rows[0]["status"] == "completed"
    assert "display_status" not in rows[0] or rows[0]["display_status"] is None
