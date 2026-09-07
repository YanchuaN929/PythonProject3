import json
import threading
import time
from unittest.mock import Mock

import pandas as pd
import pytest

from write_tasks.manager import WriteTaskManager
from write_tasks.models import WriteTask


@pytest.fixture(scope="module")
def business_tk_root():
    """The application owns one Tcl interpreter; share it across GUI scenarios."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def submit(manager, interface="A", row=10):
    return manager.submit_response_task(
        file_path="source.xlsx", file_type=2, row_index=row, interface_id=interface,
        response_number="R-1", user_name="designer", project_id="2026",
        source_column=None, description="test")


def test_slow_persistence_never_blocks_submission_or_executes_before_saved(tmp_path, monkeypatch):
    from write_tasks import executors
    entered, release, executed = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(executors, "get_executor", lambda _: lambda p: executed.set())
    manager = WriteTaskManager(tmp_path / "tasks.json")
    original_save = manager.cache.save
    def slow_save(tasks):
        entered.set()
        assert release.wait(4)
        original_save(tasks)
    manager.cache.save = slow_save
    manager._sync_to_shared_log = Mock()
    try:
        start = time.monotonic()
        task = submit(manager)
        assert time.monotonic() - start < 0.3
        assert entered.wait(1)
        assert task.status == "submitting"
        assert not executed.is_set()
        release.set()
        wait_for(lambda: task.status == "completed")
        assert executed.is_set()
    finally:
        release.set()
        manager.shutdown()


def test_shared_log_wait_does_not_block_business_execution(tmp_path, monkeypatch):
    from write_tasks import executors
    release, entered = threading.Event(), threading.Event()
    monkeypatch.setattr(executors, "get_executor", lambda _: lambda p: True)
    manager = WriteTaskManager(tmp_path / "tasks.json")
    def slow_log(task):
        entered.set()
        release.wait(4)
        return True
    manager._write_shared_log = slow_log
    try:
        task = submit(manager)
        assert entered.wait(1)
        wait_for(lambda: task.status == "completed")
        assert not release.is_set()
    finally:
        release.set()
        manager.shutdown()


def test_failed_persistence_rejects_execution_and_worker_survives(tmp_path, monkeypatch):
    from write_tasks import executors
    executor = Mock(return_value=True)
    monkeypatch.setattr(executors, "get_executor", lambda _: executor)
    manager = WriteTaskManager(tmp_path / "tasks.json")
    manager._sync_to_shared_log = Mock()
    original_save = manager.cache.save
    manager.cache.save = Mock(side_effect=OSError("disk unavailable"))
    try:
        task = submit(manager)
        wait_for(lambda: task.status == "failed")
        assert "业务未执行" in task.error
        executor.assert_not_called()
        manager.cache.save = original_save
        second = submit(manager, "B", 11)
        wait_for(lambda: second.status == "completed")
        assert executor.call_count == 1
    finally:
        manager.shutdown()


def test_conflicting_actions_are_rejected_during_execution(tmp_path, monkeypatch):
    from write_tasks import executors
    release = threading.Event()
    monkeypatch.setattr(executors, "get_executor", lambda _: lambda p: release.wait(4))
    manager = WriteTaskManager(tmp_path / "tasks.json")
    manager._sync_to_shared_log = Mock()
    try:
        task = submit(manager)
        wait_for(lambda: task.status == "running")
        with pytest.raises(ValueError, match="已有"):
            manager.submit_registry_action("confirmation", [{
                "file_type": 2, "project_id": "2026", "interface_id": "A",
                "file_path": "source.xlsx", "row_index": 10,
            }], "reviewer", "所领导")
        release.set()
        wait_for(lambda: task.status == "completed")
    finally:
        release.set()
        manager.shutdown()


def test_interrupted_excel_execution_is_not_blindly_replayed(tmp_path):
    task = WriteTask("old", "response", {}, "user", "old", status="running")
    state = tmp_path / "tasks.json"
    state.write_text(json.dumps({"tasks": [task.to_dict()]}), encoding="utf-8")
    manager = WriteTaskManager(state)
    try:
        assert manager.tasks["old"].status == "failed"
        assert "可能已写入" in manager.tasks["old"].error
        assert not manager.has_pending_tasks()
    finally:
        manager.shutdown()


def test_pending_response_does_not_hide_or_complete_business_row():
    from write_tasks.pending_cache import PendingCache
    cache = PendingCache()
    cache.add_response_entry("task", dict(file_path="source.xlsx", file_type=2,
        row_index=10, response_number="R-1", user_name="designer", project_id="2026"))
    frame = pd.DataFrame([{"source_file": "source.xlsx", "原始行号": 10,
                           "回文单号": "", "是否已完成": "☐", "状态": "待完成"}])
    pending = cache.apply_overrides_to_dataframe(frame, 2, ["设计人员"], "designer")
    assert len(pending) == 1
    assert pending.iloc[0]["是否已完成"] == "☐"
    assert pending.iloc[0]["回文单号"] == ""
    assert pending.iloc[0]["状态"] == "排队中"
    cache.on_task_status_changed(WriteTask("task", "response", {}, "designer", "", status="failed"))
    restored = cache.apply_overrides_to_dataframe(frame, 2, ["设计人员"], "designer")
    assert restored.iloc[0]["状态"] == "待完成"


def test_queued_confirmation_rechecks_current_state_and_retains_partial_results(monkeypatch):
    from registry import hooks
    from write_tasks.registry_actions import execute_registry_action
    monkeypatch.setattr(hooks, "get_task_snapshot",
                        lambda key: {"status": "completed" if key["interface_id"] == "A" else "open"})
    confirm = Mock(return_value=True)
    monkeypatch.setattr(hooks, "on_confirmed_by_superior", confirm)
    payload = {"role": "所领导", "user_name": "leader", "items": [
        {"file_type": 7, "project_id": "2026", "interface_id": name,
         "source_file": "fu.xlsx", "row_index": index + 1}
        for index, name in enumerate(["A", "B"])]}
    with pytest.raises(RuntimeError, match="成功 1 条，失败 1 条"):
        execute_registry_action(payload, "confirmation")
    assert confirm.call_count == 1
    assert payload["succeeded_items"] == [payload["items"][0]]


def test_designer_cannot_queue_superior_confirmation(monkeypatch):
    from write_tasks.registry_actions import execute_registry_action
    with pytest.raises(PermissionError):
        execute_registry_action({"role": "设计人员", "items": []}, "confirmation")


def test_partial_assignment_failure_keeps_registry_only_compensation(tmp_path, monkeypatch):
    from write_tasks import executors
    executed = []
    def get_executor(kind):
        def run(payload):
            executed.append(kind)
            if kind == "assignment":
                return {"success_count": 1, "failed_tasks": [{"reason": "locked"}],
                        "registry_compensations": [{"operation": "assigned", "registry_payload": {}}]}
            return True
        return run
    monkeypatch.setattr(executors, "get_executor", get_executor)
    manager = WriteTaskManager(tmp_path / "tasks.json")
    manager._sync_to_shared_log = Mock()
    try:
        task = manager.submit_assignment_task(
            [{"interface_id": "A", "row_index": 1}, {"interface_id": "B", "row_index": 2}], "user", "batch")
        wait_for(lambda: task.status == "failed")
        wait_for(lambda: "registry_sync" in executed)
        assert executed.count("assignment") == 1
        assert any(t.task_type == "registry_sync" for t in manager.get_tasks())
    finally:
        manager.shutdown()


def test_tk_heartbeat_continues_while_background_read_is_blocked(business_tk_root):
    from ui.background_io import run_background
    root = business_tk_root
    entered, release = threading.Event(), threading.Event()
    results, ticks, timers = [], [], []
    def read():
        entered.set()
        assert release.wait(4)
        return "ready"
    def heartbeat():
        ticks.append(time.monotonic())
        timers.append(root.after(10, heartbeat))
    try:
        run_background(root, read, results.append)
        heartbeat()
        assert entered.wait(1)
        deadline = time.monotonic() + 0.35
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.003)
        assert len(ticks) >= 12
        assert not results
        release.set()
        deadline = time.monotonic() + 2
        while not results and time.monotonic() < deadline:
            root.update()
            time.sleep(0.005)
        assert results == ["ready"]
    finally:
        release.set()
        for timer in timers:
            root.after_cancel(timer)


def test_fu_async_render_preserves_rows_and_reloads_stale_snapshot(monkeypatch, business_tk_root):
    import tkinter as tk
    from tkinter import ttk
    from types import SimpleNamespace
    from registry import hooks, util
    from ui.window import WindowManager
    root = business_tk_root
    entered, release = threading.Event(), threading.Event()
    calls = []
    def read(keys, roles):
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(4)
        return {}, {}
    monkeypatch.setattr(hooks, "get_display_state", read)
    monkeypatch.setattr(util, "extract_interface_id", lambda row, ft: str(row["内部编码"]))
    monkeypatch.setattr(util, "extract_project_id", lambda row, ft: str(row["项目号"]))
    manager = WindowManager(root, {})
    manager.app = SimpleNamespace(user_name="designer", user_roles=["设计人员"])
    viewer = ttk.Treeview(root)
    frame = pd.DataFrame([{"原始行号": 42, "项目号": "2026", "内部编码": "FU-42",
                           "中文标题": "test", "FU计划": "2026.09.20", "实际FU日期": "",
                           "责任人": "designer", "是否已完成": "☐", "状态": "待完成",
                           "source_file": "fu.xlsx"}])
    monkeypatch.setattr(manager, "_create_optimized_display",
                        lambda df, *a, **kw: df.drop(columns=["source_file", "原始行号"]))
    try:
        start = time.monotonic()
        manager.display_excel_data(viewer, frame, "FU", True, [42], ["fu.xlsx"],
                                   current_user_roles=["设计人员"])
        assert time.monotonic() - start < 0.3
        assert entered.wait(1)
        manager._business_epoch = 1
        release.set()
        deadline = time.monotonic() + 3
        while not viewer.get_children() and time.monotonic() < deadline:
            root.update()
            time.sleep(0.005)
        assert len(viewer.get_children()) == 1
        iid = viewer.get_children()[0]
        assert str(manager._item_metadata[(viewer, iid)]["original_row"]) == "42"
        assert manager._item_metadata[(viewer, iid)]["source_file"] == "fu.xlsx"
        assert len(calls) == 2
        assert all(tid != threading.get_ident() for tid in calls)
    finally:
        release.set()
        viewer.destroy()


def test_registry_review_cannot_confirm_or_unconfirm_open_task(tmp_path):
    from datetime import datetime
    from registry import service
    from registry.db import close_connection_after_use
    db_path = str(tmp_path / "review.db")
    key = dict(file_type=7, project_id="2026", interface_id="FU-1",
               source_file="fu.xlsx", row_index=10)
    try:
        service.upsert_task(db_path, False, key, {"display_status": "待完成"}, datetime.now())
        assert service.mark_confirmed(db_path, False, key, datetime.now(), "leader") is None
        with pytest.raises(RuntimeError, match="状态已变化"):
            service.mark_unconfirmed(db_path, False, key, datetime.now())
        assert service.resolve_task_record(db_path, False, key)["status"] == "open"
    finally:
        close_connection_after_use()


def test_task_folder_context_does_not_change_other_threads(monkeypatch):
    from registry import hooks
    monkeypatch.setattr(hooks, "_DATA_FOLDER", "ui-folder")
    entered, release = threading.Event(), threading.Event()
    observed = []
    def worker():
        with hooks.task_data_folder("queued-folder"):
            hooks.set_data_folder("queued-folder")
            entered.set()
            release.wait(2)
            observed.append(hooks.get_data_folder())
    thread = threading.Thread(target=worker)
    thread.start()
    try:
        assert entered.wait(1)
        assert hooks.get_data_folder() == "ui-folder"
    finally:
        release.set()
        thread.join(2)
    assert observed == ["queued-folder"]
    assert hooks.get_data_folder() == "ui-folder"
