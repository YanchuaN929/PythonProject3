#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回文单号提交路径测试
"""

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_response_submit_passes_data_folder(monkeypatch):
    from ui import input_handler

    dialog = input_handler.InterfaceInputDialog.__new__(input_handler.InterfaceInputDialog)

    app = SimpleNamespace(config={"folder_path": "E:/program/接口筛选/测试文件"})
    dialog.master = SimpleNamespace(app=app)

    dialog.entry = MagicMock()
    dialog.entry.get.return_value = "HFMR001"
    dialog.file_path = "E:/program/接口筛选/测试文件/待处理文件1/test.xlsx"
    dialog.file_type = 1
    dialog.row_index = 10
    dialog.interface_id = "S-TEST-01"
    dialog.user_name = "测试用户"
    dialog.project_id = "2024"
    dialog.source_column = None
    dialog.user_roles = []
    dialog.on_success = None
    dialog.has_assignor = False
    dialog.destroy = lambda: None

    captured = {}

    class DummyManager:
        def submit_response_task(self, **kwargs):
            captured["data_folder"] = kwargs.get("data_folder")
            return SimpleNamespace(task_id="task-1")

    class DummyCache:
        def add_response_entry(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(input_handler, "get_write_task_manager", lambda: DummyManager())
    monkeypatch.setattr(input_handler, "get_pending_cache", lambda: DummyCache())

    dialog.on_confirm()

    assert captured["data_folder"] == "E:/program/接口筛选/测试文件"
