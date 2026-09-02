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
        monkeypatch.setattr(registry_hooks, "on_response_written", MagicMock(return_value=True))

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


def test_assignment_registry_failure_uses_compensation_without_rewriting_excel(tmp_path, monkeypatch):
    """指派Excel成功、Registry失败时，后续补偿不得再次执行批量Excel写入。"""
    from services import distribution

    excel_batch_count = {"value": 0}
    registry_count = {"value": 0}

    def fake_save_assignments_batch(assignments):
        excel_batch_count["value"] += 1
        assignment = assignments[0]
        return {
            "success_count": 1,
            "failed_tasks": [],
            "registry_updates": 0,
            "registry_failures": [{
                "registry_payload": {
                    "file_type": assignment["file_type"],
                    "file_path": assignment["file_path"],
                    "row_index": assignment["row_index"],
                    "interface_id": assignment["interface_id"],
                    "project_id": assignment["project_id"],
                    "assigned_by": assignment["assigned_by"],
                    "assigned_to": assignment["assigned_name"],
                },
                "origin_error": "模拟Registry失败",
            }],
        }

    def fake_on_assigned(**_kwargs):
        registry_count["value"] += 1
        return True

    monkeypatch.setattr(distribution, "save_assignments_batch", fake_save_assignments_batch)
    monkeypatch.setattr(registry_hooks, "on_assigned", fake_on_assigned)

    manager = WriteTaskManager(state_path=tmp_path / "tasks.json")
    try:
        manager._sync_to_shared_log = MagicMock()
        task = manager.submit_assignment_task(
            assignments=[{
                "file_type": 7,
                "file_path": str(tmp_path / "fu.xlsx"),
                "row_index": 2,
                "interface_id": "FU-ASSIGN-01",
                "project_id": "1916",
                "assigned_by": "一室主任",
                "assigned_name": "张三",
            }],
            submitted_by="一室主任",
            description="测试指派补偿",
        )
        assert _wait_for_task_done(manager, task.task_id) == "completed"

        deadline = time.time() + 3.0
        compensation = None
        while time.time() < deadline:
            matches = [
                candidate for candidate in manager.tasks.values()
                if candidate.task_type == "registry_sync"
                and candidate.payload.get("origin_task_id") == task.task_id
            ]
            if matches and matches[0].status == "completed":
                compensation = matches[0]
                break
            time.sleep(0.05)

        assert compensation is not None
        assert compensation.payload["operation"] == "assigned"
        assert excel_batch_count["value"] == 1
        assert registry_count["value"] == 1
    finally:
        manager.shutdown()


def test_assignment_batch_reports_registry_failure_after_excel_success(monkeypatch):
    """实际指派服务必须把Registry失败返回给执行器，不能只打印后隐藏。"""
    from services import distribution

    assignment = {
        "file_type": 1,
        "file_path": "assignment.xlsx",
        "row_index": 6,
        "interface_id": "S-ASSIGN-FAIL",
        "project_id": "2026",
        "assigned_by": "2026接口工程师",
        "assigned_name": "张三",
    }
    monkeypatch.setattr(
        distribution,
        "_write_assignment_group",
        lambda _file_path, assignments: (list(assignments), []),
    )
    monkeypatch.setattr(registry_hooks, "on_assigned", lambda **_kwargs: False)

    result = distribution.save_assignments_batch([assignment])

    assert result["success_count"] == 1
    assert result["failed_tasks"] == []
    assert result["registry_updates"] == 0
    assert len(result["registry_failures"]) == 1
    assert result["registry_failures"][0]["registry_payload"]["interface_id"] == "S-ASSIGN-FAIL"


def test_fu_excel_success_creates_registry_only_compensation(tmp_path, monkeypatch):
    """FU的Excel写入成功后，Registry失败转独立补偿且不再次写Excel。"""
    data_folder = tmp_path / "data"
    data_folder.mkdir(parents=True, exist_ok=True)

    import ui.input_handler as input_handler

    excel_write_count = {"value": 0}
    registry_attempts = {"value": 0}

    def fake_excel_write(*_args, **_kwargs):
        excel_write_count["value"] += 1
        return True

    def fake_registry_write(**_kwargs):
        registry_attempts["value"] += 1
        return registry_attempts["value"] >= 2

    monkeypatch.setattr(input_handler, "write_fu_completion_to_excel", fake_excel_write)
    monkeypatch.setattr(registry_hooks, "on_fu_completed", fake_registry_write)

    manager = WriteTaskManager(state_path=tmp_path / "tasks.json")
    try:
        manager._sync_to_shared_log = MagicMock()
        task = manager.submit_fu_completion_task(
            file_path=str(tmp_path / "fu.xlsx"),
            row_index=2,
            interface_id="FU-001",
            user_name="测试用户",
            project_id="2026",
            completion_date="2026-07-27",
            data_folder=str(data_folder),
            description="测试FU完成",
        )

        status = _wait_for_task_done(manager, task.task_id)
        assert status == "completed"
        assert "Registry同步已转补偿队列" in manager.tasks[task.task_id].error

        deadline = time.time() + 3.0
        compensation = None
        while time.time() < deadline:
            matches = [
                candidate for candidate in manager.tasks.values()
                if candidate.task_type == "registry_sync"
                and candidate.payload.get("origin_task_id") == task.task_id
            ]
            if matches and matches[0].status == "completed":
                compensation = matches[0]
                break
            time.sleep(0.05)

        assert compensation is not None
        assert compensation.payload["operation"] == "fu_completed"
        assert excel_write_count["value"] == 1
        assert registry_attempts["value"] == 2
    finally:
        manager.shutdown()


def test_response_executor_registry_compensation_never_calls_excel(monkeypatch):
    """回文补偿执行器只调用Registry；原Excel写入器只执行一次。"""
    from write_tasks import executors
    import ui.input_handler as input_handler

    excel_write_count = {"value": 0}

    def fake_excel_write(**_kwargs):
        excel_write_count["value"] += 1
        return True

    monkeypatch.setattr(input_handler, "write_response_to_excel", fake_excel_write)
    monkeypatch.setattr(registry_hooks, "on_response_written", lambda **_kwargs: False)
    payload = {
        "file_path": "response.xlsx",
        "file_type": 2,
        "row_index": 10,
        "interface_id": "S-TEST-01(设计人员)",
        "response_number": "HFMR001",
        "user_name": "测试用户",
        "project_id": "2026",
        "source_column": "P",
        "role": "设计人员",
        "data_folder": "data",
    }

    result = executors.execute_response_task(payload)
    compensation = result["registry_compensation"]
    assert compensation["operation"] == "response_written"
    assert compensation["registry_payload"]["interface_id"] == "S-TEST-01"
    assert excel_write_count["value"] == 1

    monkeypatch.setattr(
        input_handler,
        "write_response_to_excel",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("补偿不得写Excel")),
    )
    monkeypatch.setattr(registry_hooks, "on_response_written", lambda **_kwargs: True)
    assert executors.execute_registry_sync_task(compensation) is True
    assert excel_write_count["value"] == 1


def test_registry_compensation_retry_does_not_block_excel_pending_check(tmp_path, monkeypatch):
    """仅有Registry补偿任务时，不阻塞用户开始下一轮Excel处理。"""
    import threading
    from write_tasks import executors

    release = threading.Event()
    monkeypatch.setitem(
        executors.EXECUTOR_MAP,
        "registry_sync",
        lambda _payload: release.wait(timeout=1.0) or True,
    )
    manager = WriteTaskManager(state_path=tmp_path / "tasks.json")
    try:
        manager._sync_to_shared_log = MagicMock()
        task = manager.submit_registry_sync_task(
            {
                "operation": "fu_completed",
                "registry_payload": {"interface_id": "FU-RETRY"},
            },
            submitted_by="测试用户",
            origin_task_id="origin-task",
        )
        # 任务可能已被工作线程取走；pending/running两种状态都不应阻塞Excel处理。
        assert task.task_type == "registry_sync"
        assert manager.has_pending_tasks() is False
        assert manager.has_pending_tasks(include_registry_sync=True) is True
    finally:
        release.set()
        manager.shutdown()


def test_registry_compensation_automatically_retries_registry_only(tmp_path, monkeypatch):
    """补偿失败后延迟重试同一Registry任务，直至成功。"""
    from write_tasks import executors
    import write_tasks.manager as manager_module

    attempts = {"value": 0}

    def flaky_registry_only(_payload):
        attempts["value"] += 1
        return attempts["value"] >= 2

    monkeypatch.setitem(executors.EXECUTOR_MAP, "registry_sync", flaky_registry_only)
    monkeypatch.setattr(manager_module, "REGISTRY_RETRY_DELAYS", (0.01,))
    manager = WriteTaskManager(state_path=tmp_path / "tasks.json")
    try:
        manager._sync_to_shared_log = MagicMock()
        task = manager.submit_registry_sync_task(
            {
                "operation": "response_written",
                "registry_payload": {"interface_id": "S-RETRY-01"},
            },
            submitted_by="测试用户",
            origin_task_id="origin-retry",
        )

        assert _wait_for_task_done(manager, task.task_id) == "completed"
        assert attempts["value"] == 2
        assert task.payload["_retry_count"] == 1
        assert task.error is None
    finally:
        manager.shutdown()
