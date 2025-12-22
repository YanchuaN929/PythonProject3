import time

import pytest

from write_tasks import manager as manager_module
from write_tasks import executors


@pytest.fixture
def isolated_manager(monkeypatch, tmp_path):
    """
    复用 write_tasks.manager 的单例，但把 state_path 指到临时目录，避免污染本机 result_cache。
    """
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


def test_assignment_task_should_fail_if_success_count_is_zero(monkeypatch, isolated_manager):
    """
    现象复现：
    - 指派写入实际失败（success_count=0，failed_tasks 非空）
    - 但队列把任务标记为 completed（当前实现的缺陷）

    这个用例用“期望失败”来锁定缺陷：修复前应当 FAIL，修复后应当 PASS。
    """

    def fake_executor(payload):
        return {
            "success_count": 0,
            "failed_tasks": [{"interface_id": "S-TEST-001", "reason": "文件不存在"}],
            "registry_updates": 0,
        }

    monkeypatch.setattr(executors, "get_executor", lambda task_type: fake_executor)

    task = isolated_manager.submit_assignment_task(
        assignments=[
            {
                "file_type": 1,
                "file_path": r"\\10.102.2.7\文件服务器\建筑结构所\接口文件\X.xlsx",
                "row_index": 2,
                "assigned_name": "张三",
                "assigned_by": "李经理（所领导）",
                "interface_id": "S-TEST-001",
                "project_id": "2016",
                "status_text": "待完成",
            }
        ],
        submitted_by="测试用户",
        description="测试：指派失败不应显示完成",
    )
    assert task.status == "pending"

    _wait_for_completion(isolated_manager)

    # 期望：失败应当体现在队列任务状态里（修复后满足）
    tasks = isolated_manager.get_tasks()
    matched = [t for t in tasks if t.task_id == task.task_id]
    assert matched, "未找到目标任务"
    assert matched[0].status == "failed"


