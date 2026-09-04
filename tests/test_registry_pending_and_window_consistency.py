#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

import pandas as pd
import pytest


pytestmark = pytest.mark.allow_empty_name


def test_window_resolve_response_source_column_prefers_metadata():
    from ui.window import _resolve_response_source_column

    original_df = pd.DataFrame({"_source_column": ["L"]})

    assert _resolve_response_source_column(3, "M", original_df=original_df, item_index=0) == "M"
    assert _resolve_response_source_column(3, None, original_df=original_df, item_index=0) == "L"
    assert _resolve_response_source_column(1, "M", original_df=original_df, item_index=0) is None


def test_window_confirmed_status_text_recognizes_yishencha():
    from ui.window import _is_confirmed_registry_status

    assert _is_confirmed_registry_status("已审查") is True
    assert _is_confirmed_registry_status("（已延期） 已审查") is True
    assert _is_confirmed_registry_status("⏳ 待审查") is False


def test_window_registry_visibility_rules_distinguish_designer_and_superior():
    from ui.window import _should_hide_registry_row_for_roles

    assert _should_hide_registry_row_for_roles("⏳ 待审查", ["设计人员"]) is True
    assert _should_hide_registry_row_for_roles("⏳ 待审查", ["一室主任"]) is False
    assert _should_hide_registry_row_for_roles("已审查", ["一室主任"]) is True
    assert _should_hide_registry_row_for_roles("", ["设计人员"]) is True


def test_merge_registry_pending_rows_readds_latest_pending_business_record(monkeypatch):
    from core import main

    df = pd.DataFrame(
        [
            ["", "", "", "", "表头"],
            ["", "", "", "", "IF-001"],
        ]
    )

    monkeypatch.setattr(
        main,
        "_load_latest_registry_pending_tasks",
        lambda *_args, **_kwargs: [("IF-001", "1818", "待审查", "completed", "2026-04-24T08:00:00")],
    )

    rows, pending = main._merge_registry_pending_rows(
        file_type=6,
        file_path="E:/tmp/收发文清单1818.xlsx",
        df=df,
        final_rows=set(),
        allowed_rows={1},
    )
    assert pending == {1}
    assert rows == {1}


def test_extract_project_id_prefers_source_file_basename_over_parent_path_digits():
    from registry.util import extract_project_id

    row = pd.Series(
        {
            "source_file": "E:/program/PythonProject3_20260226/example/1818按项目导出IDI手册2026-01-28.xlsx",
        }
    )

    assert extract_project_id(row, 1) == "1818"


def test_resolve_task_record_and_display_status_fall_back_to_latest_business_record(tmp_path):
    from registry.service import get_display_status, resolve_task_record
    from registry.util import make_business_id, make_task_id

    db_path = tmp_path / "registry.db"
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
                business_id TEXT,
                interface_time TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                display_status TEXT,
                assigned_by TEXT,
                role TEXT,
                confirmed_at TEXT,
                confirmed_by TEXT,
                responsible_person TEXT,
                ignored INTEGER DEFAULT 0,
                last_seen_at TEXT
            )
            """
        )

        business_id = make_business_id(1, "2026", "IF-001")
        exact_tid = make_task_id(1, "2026", "IF-001", "source.xlsx", 2)
        latest_tid = make_task_id(1, "2026", "IF-001", "source.xlsx", 9)

        conn.execute(
            """
            INSERT INTO tasks (
                id, file_type, project_id, interface_id, source_file, row_index,
                business_id, interface_time, status, display_status, assigned_by,
                role, confirmed_at, confirmed_by, responsible_person, ignored, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exact_tid,
                1,
                "2026",
                "IF-001",
                "source.xlsx",
                2,
                business_id,
                "2026-04-20",
                "completed",
                "待审查",
                None,
                "",
                None,
                None,
                "张三",
                0,
                "2026-04-20T08:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO tasks (
                id, file_type, project_id, interface_id, source_file, row_index,
                business_id, interface_time, status, display_status, assigned_by,
                role, confirmed_at, confirmed_by, responsible_person, ignored, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                latest_tid,
                1,
                "2026",
                "IF-001",
                "source.xlsx",
                9,
                business_id,
                "2026-04-20",
                "confirmed",
                "已审查",
                None,
                "",
                "2026-04-24T09:00:00",
                "一室主任",
                "张三",
                0,
                "2026-04-24T09:00:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    key = {
        "file_type": 1,
        "project_id": "2026",
        "interface_id": "IF-001",
        "source_file": "source.xlsx",
        "row_index": 2,
        "interface_time": "2026-04-20",
    }

    resolved = resolve_task_record(str(db_path), wal=False, key=key)
    assert resolved is not None
    assert resolved["id"] == latest_tid
    assert resolved["confirmed_by"] == "一室主任"

    status_map = get_display_status(str(db_path), False, [key], current_user_roles=["一室主任"])
    assert exact_tid in status_map
    assert status_map[exact_tid].endswith("已审查")
