#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry maintenance mode and connection lifecycle tests.
"""

import os

import pytest

from registry import db as registry_db
from registry import service as registry_service
from registry.util import make_task_id, make_business_id
from registry.write_queue import WriteQueue, WriteRequest, WriteOperation


pytestmark = pytest.mark.allow_empty_name


def _create_db_with_task(tmp_path, file_type=1, project_id="P1", interface_id="I1"):
    data_folder = tmp_path / "data"
    db_path = data_folder / ".registry" / "registry.db"
    conn = registry_db.get_connection(str(db_path), wal=False)
    try:
        tid = make_task_id(file_type, project_id, interface_id, "source.xlsx", 1)
        business_id = make_business_id(file_type, project_id, interface_id)
        now = "2025-01-01T00:00:00"
        conn.execute(
            """
            INSERT INTO tasks (
                id, file_type, project_id, interface_id, source_file, row_index,
                business_id, status, display_status, responsible_person,
                first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                file_type,
                project_id,
                interface_id,
                "source.xlsx",
                1,
                business_id,
                "open",
                "待完成",
                "张三",
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        registry_db.close_connection()
    return data_folder, db_path


def test_maintenance_flag_lifecycle(tmp_path):
    data_folder = tmp_path / "data"
    flag_path = registry_db.get_maintenance_flag_path(data_folder=str(data_folder))

    assert not registry_db.is_maintenance_mode(data_folder=str(data_folder))

    created_path = registry_db.enable_maintenance_mode(str(data_folder))
    assert created_path == flag_path
    assert os.path.exists(flag_path)
    assert registry_db.is_maintenance_mode(data_folder=str(data_folder))

    assert registry_db.disable_maintenance_mode(str(data_folder)) is True
    assert not os.path.exists(flag_path)
    assert registry_db.is_maintenance_mode(data_folder=str(data_folder)) is False

    assert registry_db.disable_maintenance_mode(str(data_folder)) is False


def test_maintenance_flag_path_from_db_path(tmp_path):
    data_folder, db_path = _create_db_with_task(tmp_path)
    flag_by_data = registry_db.get_maintenance_flag_path(data_folder=str(data_folder))
    flag_by_db = registry_db.get_maintenance_flag_path(db_path=str(db_path))
    assert flag_by_data == flag_by_db


def test_ensure_not_in_maintenance_raises(tmp_path):
    data_folder, db_path = _create_db_with_task(tmp_path)
    registry_db.enable_maintenance_mode(str(data_folder))
    with pytest.raises(registry_db.MaintenanceModeError):
        registry_db.ensure_not_in_maintenance(db_path=str(db_path))


def test_get_connection_blocked_by_maintenance(tmp_path):
    data_folder, db_path = _create_db_with_task(tmp_path)
    registry_db.enable_maintenance_mode(str(data_folder))
    with pytest.raises(registry_db.MaintenanceModeError):
        registry_db.get_connection(str(db_path), wal=False)


def test_query_task_history_closes_connection(tmp_path):
    _, db_path = _create_db_with_task(tmp_path)
    results = registry_service.query_task_history(
        str(db_path),
        wal=False,
        project_id="P1",
        interface_id="I1",
    )
    assert len(results) == 1
    assert registry_db._CONN is None


def test_find_tasks_for_force_assign_closes_connection(tmp_path):
    _, db_path = _create_db_with_task(tmp_path)
    results = registry_service.find_tasks_for_force_assign(
        str(db_path),
        wal=False,
        file_type=1,
        project_id="P1",
        interface_id="I1",
    )
    assert len(results) == 1
    assert registry_db._CONN is None


def test_write_queue_blocks_in_maintenance(monkeypatch):
    queue = WriteQueue(db_path="dummy.db", enabled=True)
    callback_result = {}

    def callback(success, error_message):
        callback_result["success"] = success
        callback_result["error"] = error_message

    request = WriteRequest(
        WriteOperation.WRITE_EVENT,
        {"db_path": "dummy.db"},
        callback=callback,
    )

    def raise_maintenance(*_args, **_kwargs):
        raise registry_db.MaintenanceModeError("maintenance")

    def should_not_connect(*_args, **_kwargs):
        raise AssertionError("should not connect during maintenance")

    monkeypatch.setattr(registry_db, "ensure_not_in_maintenance", raise_maintenance)
    monkeypatch.setattr(registry_db, "get_write_connection", should_not_connect)

    queue._process_batch([request])

    assert request.result is False
    assert "maintenance" in (request.error or "")
    assert callback_result.get("success") is False
