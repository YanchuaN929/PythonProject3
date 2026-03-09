#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import threading

import pytest
from openpyxl import Workbook


pytestmark = pytest.mark.allow_empty_name


def test_local_cache_get_read_connection_does_not_deadlock(tmp_path):
    from registry.local_cache import LocalCacheManager

    network_db_path = tmp_path / "network" / "registry.db"
    network_db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(network_db_path))
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO demo(name) VALUES ('ok')")
        conn.commit()
    finally:
        conn.close()

    manager = LocalCacheManager(
        str(network_db_path),
        local_cache_dir=str(tmp_path / "cache"),
        sync_interval=300,
    )

    result = {"done": False, "conn": None, "error": None}

    def worker():
        try:
            result["conn"] = manager.get_read_connection()
        except Exception as exc:  # pragma: no cover
            result["error"] = str(exc)
        finally:
            result["done"] = True

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=2.0)

    try:
        assert result["done"] is True, "get_read_connection 出现死锁"
        assert result["error"] is None
        assert result["conn"] is not None
        assert result["conn"].execute("SELECT name FROM demo").fetchone()[0] == "ok"
    finally:
        manager.cleanup()


def test_get_display_status_uses_read_connection(monkeypatch):
    from registry import service as registry_service

    class FakeCursor:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class FakeConn:
        def execute(self, _sql, _params):
            return FakeCursor(("open", "待完成", None, None, None, "张三", 0))

    monkeypatch.setattr(registry_service, "get_read_connection", lambda _db_path: FakeConn())
    monkeypatch.setattr(
        registry_service,
        "get_connection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不应走写连接")),
    )
    monkeypatch.setattr(registry_service, "close_connection_after_use", lambda: None)

    result = registry_service.get_display_status(
        "E:/dummy/.registry/registry.db",
        False,
        [
            {
                "file_type": 1,
                "project_id": "2016",
                "interface_id": "S-TEST-01",
                "source_file": "source.xlsx",
                "row_index": 2,
                "interface_time": "2026-02-10",
            }
        ],
    )

    assert len(result) == 1
    assert next(iter(result.values())).startswith("📌")


def test_atomic_save_workbook_keeps_file_openable(tmp_path):
    from utils.excel_io import atomic_save_workbook, open_workbook_for_edit

    file_path = tmp_path / "sample.xlsx"

    wb = Workbook()
    ws = wb.active
    ws["A1"] = "before"
    wb.save(str(file_path))
    wb.close()

    wb = open_workbook_for_edit(str(file_path))
    try:
        wb.active["A1"] = "after"
        atomic_save_workbook(wb, str(file_path))
    finally:
        wb.close()

    verify_wb = open_workbook_for_edit(str(file_path))
    try:
        assert verify_wb.active["A1"].value == "after"
    finally:
        verify_wb.close()

    leftover = [p.name for p in tmp_path.iterdir() if p.name.startswith(".__excel_write_")]
    assert leftover == []


def test_write_response_to_excel_keeps_workbook_valid(tmp_path, monkeypatch):
    from ui.input_handler import write_response_to_excel
    from utils.excel_io import open_workbook_for_edit

    file_path = tmp_path / "response.xlsx"

    wb = Workbook()
    ws = wb.active
    ws["A1"] = "标题"
    ws["L2"] = ""
    ws["J2"] = ""
    ws["N2"] = ""
    wb.save(str(file_path))
    wb.close()

    monkeypatch.setattr("tkinter.messagebox.showerror", lambda *_args, **_kwargs: None)

    ok = write_response_to_excel(
        str(file_path),
        file_type=6,
        row_index=2,
        response_number="HF-001",
        user_name="测试用户",
        project_id="2026",
        source_column=None,
    )

    assert ok is True

    verify_wb = open_workbook_for_edit(str(file_path))
    try:
        verify_ws = verify_wb.active
        assert verify_ws["L2"].value == "HF-001"
        assert verify_ws["N2"].value == "测试用户"
    finally:
        verify_wb.close()


def test_save_assignments_batch_keeps_workbook_valid(tmp_path, monkeypatch):
    from services.distribution import save_assignments_batch
    from utils.excel_io import open_workbook_for_edit

    file_path = tmp_path / "assignment.xlsx"

    wb = Workbook()
    ws = wb.active
    ws["A1"] = "标题"
    ws["R2"] = ""
    wb.save(str(file_path))
    wb.close()

    monkeypatch.setattr("services.distribution.log_info", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.distribution.log_success", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("services.distribution.log_error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("registry.hooks.on_assigned", lambda *_args, **_kwargs: None)

    result = save_assignments_batch(
        [
            {
                "file_type": 1,
                "file_path": str(file_path),
                "row_index": 2,
                "assigned_name": "张三",
                "interface_id": "S-TEST-01",
                "project_id": "2016",
                "assigned_by": "测试接口工程师",
            }
        ]
    )

    assert result["success_count"] == 1

    verify_wb = open_workbook_for_edit(str(file_path))
    try:
        assert verify_wb.active["R2"].value == "张三"
    finally:
        verify_wb.close()
