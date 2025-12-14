import time

import pytest

from write_tasks import manager as manager_module
from write_tasks import executors


@pytest.fixture
def isolated_manager(monkeypatch, tmp_path):
    manager_module.reset_write_task_manager_for_tests()
    state_path = tmp_path / "tasks_state.json"
    monkeypatch.setattr(manager_module, "DEFAULT_STATE_PATH", state_path)
    mgr = manager_module.get_write_task_manager()
    yield mgr
    manager_module.reset_write_task_manager_for_tests()


def _wait_for_completion(mgr, timeout=2.0):
    deadline = time.time() + timeout
    while mgr.has_pending_tasks() and time.time() < deadline:
        time.sleep(0.05)
    assert not mgr.has_pending_tasks(), "写任务队列未在预期时间内完成"


def test_assignment_task_executes(monkeypatch, isolated_manager):
    called_payloads = []

    def fake_executor(payload):
        called_payloads.append(payload)

    monkeypatch.setattr(executors, "get_executor", lambda task_type: fake_executor)

    task = isolated_manager.submit_assignment_task(
        assignments=[{"file_path": "a.xlsx", "assigned_name": "张三"}],
        submitted_by="测试用户",
        description="测试任务",
    )
    assert task.status == "pending"

    _wait_for_completion(isolated_manager)

    tasks = isolated_manager.get_tasks()
    assert tasks[0].status == "completed"
    assert called_payloads == [{"assignments": [{"file_path": "a.xlsx", "assigned_name": "张三"}]}]


def test_failed_task_sets_error(monkeypatch, isolated_manager):
    def failing_executor(payload):
        raise RuntimeError("boom")

    monkeypatch.setattr(executors, "get_executor", lambda task_type: failing_executor)

    isolated_manager.submit_response_task(
        file_path="b.xlsx",
        file_type=1,
        row_index=10,
        interface_id="S-GT---TEST",
        response_number="HW-001",
        user_name="测试用户",
        project_id="1818",
        source_column=None,
        role="设计人员",
        description="回文单号任务",
    )

    _wait_for_completion(isolated_manager)

    tasks = isolated_manager.get_tasks()
    matched = [t for t in tasks if t.description == "回文单号任务"]
    assert matched, "未找到目标任务"
    task = matched[0]
    assert task.status == "failed"
    assert "boom" in (task.error or "")

