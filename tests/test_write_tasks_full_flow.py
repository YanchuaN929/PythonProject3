#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
写入任务完整流程测试

覆盖：
1) WriteTaskManager + execute_assignment_task 完整流程
2) WriteTaskManager + execute_response_task 完整流程
"""

import time
from unittest.mock import MagicMock

from registry import hooks as registry_hooks
from write_tasks.manager import WriteTaskManager


def _wait_for_task_done(manager: WriteTaskManager, task_id: str, timeout: float = 3.0) -> str:
    deadline = time.time() + timeout
    status = ""
    while time.time() < deadline:
        status = manager.tasks[task_id].status
        if status in ("completed", "failed"):
            return status
        time.sleep(0.05)
    return status


def test_assignment_write_task_full_flow(tmp_path, monkeypatch):
    """测试：指派任务完整流程可完成且不闪退"""
    data_folder = tmp_path / "data"
    data_folder.mkdir(parents=True, exist_ok=True)

    original = registry_hooks._DATA_FOLDER
    try:
        registry_hooks._DATA_FOLDER = str(data_folder)

        # mock 实际写入逻辑，避免依赖Excel文件
        from services import distribution

        def fake_save_assignments_batch(assignments):
            return {
                "success_count": len(assignments),
                "failed_tasks": [],
                "registry_updates": 0,
            }

        monkeypatch.setattr(distribution, "save_assignments_batch", fake_save_assignments_batch)

        manager = WriteTaskManager(state_path=tmp_path / "tasks.json")
        try:
            manager._sync_to_shared_log = MagicMock()
            task = manager.submit_assignment_task(
                assignments=[{"interface_id": "S-TEST-01", "assigned_name": "测试人员"}],
                submitted_by="测试用户",
                description="测试指派任务",
            )

            status = _wait_for_task_done(manager, task.task_id)
            assert status == "completed"
            assert manager.tasks[task.task_id].error is None
        finally:
            manager.shutdown()
    finally:
        registry_hooks._DATA_FOLDER = original


def test_response_write_task_full_flow(tmp_path, monkeypatch):
    """测试：回文单号写入任务完整流程可完成且不闪退"""
    data_folder = tmp_path / "data"
    data_folder.mkdir(parents=True, exist_ok=True)

    original = registry_hooks._DATA_FOLDER
    try:
        registry_hooks._DATA_FOLDER = str(data_folder)

        # mock Excel写入与 registry 写入
        import ui.input_handler as input_handler

        monkeypatch.setattr(input_handler, "write_response_to_excel", lambda **_kwargs: True)
        monkeypatch.setattr(registry_hooks, "on_response_written", MagicMock())

        manager = WriteTaskManager(state_path=tmp_path / "tasks.json")
        try:
            manager._sync_to_shared_log = MagicMock()
            task = manager.submit_response_task(
                file_path=str(tmp_path / "dummy.xlsx"),
                file_type=1,
                row_index=10,
                interface_id="S-TEST-01",
                response_number="HFMR001",
                user_name="测试用户",
                project_id="2024",
                source_column="回复列",
                description="测试回文单号",
            )

            status = _wait_for_task_done(manager, task.task_id)
            assert status == "completed"
            assert manager.tasks[task.task_id].error is None
        finally:
            manager.shutdown()
    finally:
        registry_hooks._DATA_FOLDER = original
