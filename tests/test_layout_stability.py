"""Real Tk checks; no production workbook or Registry access."""
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture(scope="module")
def root():
    import tkinter as tk
    window = tk.Tk()
    window.geometry("1200x500")
    yield window
    window.destroy()


def test_task_status_does_not_change_geometry(root):
    from write_tasks.task_panel import TaskRecordPanel
    panel = TaskRecordPanel(root, lambda: "tester", auto_refresh=False)
    panel.pack(fill="both", expand=True)
    try:
        measurements = []
        for text in ("暂无写入任务", "显示 100 条任务（共享）", "共享查询失败: " + "locked " * 80):
            panel.status_var.set(text)
            root.update_idletasks()
            measurements.append((panel.winfo_reqwidth(), panel.winfo_reqheight(),
                                 panel.tree.winfo_width(), panel.tree.winfo_height()))
        assert len(set(measurements)) == 1
    finally:
        panel.destroy()


def test_task_refresh_retains_selection_scroll_and_unchanged_rows(root, monkeypatch):
    from write_tasks.task_panel import TaskRecordPanel
    panel = TaskRecordPanel(root, lambda: "tester", auto_refresh=False)
    panel.pack(fill="both", expand=True)
    tasks = [SimpleNamespace(task_id=str(i), task_type="response", payload={},
                             submitted_at="2026-09-07", submitted_by="tester",
                             description="test", status="pending") for i in range(100)]
    try:
        panel._populate_tree(tasks)
        root.update_idletasks()
        panel.tree.selection_set("50")
        panel.tree.focus("50")
        panel.tree.yview_moveto(.4)
        before = panel.tree.yview()
        delete = Mock(wraps=panel.tree.delete)
        insert = Mock(wraps=panel.tree.insert)
        monkeypatch.setattr(panel.tree, "delete", delete)
        monkeypatch.setattr(panel.tree, "insert", insert)
        tasks[50].status = "completed"
        panel._populate_tree(tasks)
        assert not delete.called and not insert.called
        assert panel.tree.selection() == ("50",)
        assert panel.tree.focus() == "50"
        assert panel.tree.yview() == before
        assert panel.tree.item("50", "values")[-1] == "完成"
        panel._populate_tree(tasks[1:] + [tasks[0]])
        assert panel.tree.get_children()[-1] == "0"
        panel._populate_tree(tasks[1:])
        assert not panel.tree.exists("0")
    finally:
        panel.destroy()


@pytest.mark.parametrize("existing", [None, "TEST-RESPONSE"])
def test_response_dialog_keeps_loading_size(root, monkeypatch, existing):
    from ui.input_handler import InterfaceInputDialog as ResponseInputDialog
    from registry import hooks
    monkeypatch.setattr(hooks, "_ensure_data_folder_from_path", lambda *a: None)
    monkeypatch.setattr(ResponseInputDialog, "_load_existing_response",
                        lambda self: setattr(self, "existing_response", existing))
    dialog = ResponseInputDialog(root, "TEST-ID", 2, "test.xlsx", 10, "tester", "2026")
    try:
        root.update_idletasks()
        before = (dialog.winfo_width(), dialog.winfo_height())
        deadline = time.monotonic() + 2
        while dialog.title() == "回文单号" and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert dialog.title() != "回文单号"
        assert (dialog.winfo_width(), dialog.winfo_height()) == before == (450, 280)
    finally:
        dialog.destroy()
