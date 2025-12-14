import tkinter as tk

from write_tasks.models import WriteTask
from write_tasks.task_panel import TaskRecordPanel


class DummyManager:
    def __init__(self, tasks):
        self._tasks = tasks

    def get_tasks(self):
        return list(self._tasks)


def make_task(task_id, user, task_type="assignment", status="pending", submitted_at="2025-01-01T10:00:00"):
    return WriteTask(
        task_id=task_id,
        task_type=task_type,
        payload={},
        submitted_by=user,
        description=f"{task_type}-{task_id}",
        submitted_at=submitted_at,
        status=status,
    )


def _patch_shared_registry_cfg(monkeypatch, tmp_path):
    """
    模拟“共享盘 registry.db”环境：
    - 使用 tmp_path 下的 registry.db 作为共享库，避免污染工作区的 result_cache/registry.db
    - 强制网络模式，模拟类似 \\10.102.2.102\\... 的网络盘锁策略
    - 通过 monkeypatch 覆盖 registry.hooks._cfg，让 TaskRecordPanel 读取该共享库
    """
    try:
        from registry import db as registry_db
        from registry import hooks as registry_hooks
    except Exception:
        return

    try:
        registry_db.set_force_network_mode(True)
    except Exception:
        pass

    shared_db_path = str(tmp_path / "registry.db")

    def _fake_cfg():
        return {
            "registry_enabled": True,
            "registry_db_path": shared_db_path,
            "registry_wal": False,
            "registry_force_network_mode": True,
        }

    monkeypatch.setattr(registry_hooks, "_cfg", _fake_cfg, raising=True)


def test_task_panel_filters_only_mine(tmp_path, monkeypatch):
    _patch_shared_registry_cfg(monkeypatch, tmp_path)
    root = tk.Tk()
    root.withdraw()
    tasks = [
        make_task("t1", "Alice", submitted_at="2025-01-02T09:00:00"),
        make_task("t2", "Bob", submitted_at="2025-01-03T09:00:00"),
    ]
    panel = TaskRecordPanel(root, get_current_user=lambda: "Alice", auto_refresh=False)
    panel.bind_manager(DummyManager(tasks))

    # 默认显示全部
    all_items = panel.tree.get_children()
    assert len(all_items) == 2

    # 只看自己的任务
    panel.only_mine_var.set(True)
    panel.refresh_tasks()
    mine_items = panel.tree.get_children()
    assert len(mine_items) == 1
    first_values = panel.tree.item(mine_items[0], "values")
    assert first_values[1] == "Alice"

    panel.destroy()
    root.destroy()


def test_task_panel_shows_status_text(tmp_path, monkeypatch):
    _patch_shared_registry_cfg(monkeypatch, tmp_path)
    root = tk.Tk()
    root.withdraw()
    tasks = [
        make_task("a1", "Alice", status="completed", submitted_at="2025-03-01T08:00:00"),
        make_task("a2", "Alice", status="failed", submitted_at="2025-03-02T08:30:00"),
    ]
    panel = TaskRecordPanel(root, get_current_user=lambda: "Alice", auto_refresh=False)
    panel.bind_manager(DummyManager(tasks))
    panel.refresh_tasks()

    rows = panel.tree.get_children()
    assert len(rows) == 2
    first_status = panel.tree.item(rows[0], "values")[4]
    assert first_status in {"完成", "失败"}

    panel.destroy()
    root.destroy()



