import tkinter as tk

from write_tasks.models import WriteTask
from write_tasks.task_panel import TaskRecordPanel


def test_right_click_selects_row_before_popup():
    root = tk.Tk()
    root.withdraw()
    try:
        panel = TaskRecordPanel(root, get_current_user=lambda: "Alice", auto_refresh=False)
        panel.pack()

        tasks = [
            WriteTask(
                task_id="t1",
                task_type="assignment",
                payload={"assignments": [{"interface_id": "A"}]},
                submitted_by="Alice",
                description="d1",
                status="completed",
                submitted_at="2025-01-01T10:00:00",
            )
        ]
        panel._populate_tree(tasks)

        # 让 Tk 完成一次布局/绘制，否则 Treeview 可能拿不到 bbox（返回空字符串）
        try:
            root.update_idletasks()
            root.update()
        except Exception:
            pass

        # 拿到第一行的 bbox，构造一个右键事件，模拟“未先左键选中就右键”的用户动作
        iid = panel.tree.get_children()[0]
        bbox = panel.tree.bbox(iid)
        if bbox:
            x, y, w, h = bbox
            click_y = y + max(1, h // 2)
        else:
            # 某些环境下 withdraw 的窗口仍可能拿不到 bbox；退化为点击第一行的近似坐标
            click_y = 5

        called = {"popup": False}

        def fake_popup(x_root, y_root):
            called["popup"] = True

        panel._menu.tk_popup = fake_popup  # type: ignore[attr-defined]

        class E:
            pass

        e = E()
        e.x_root = 10
        e.y_root = 10
        e.y = click_y

        # 确保起始时没有选择
        panel.tree.selection_remove(panel.tree.selection())
        assert panel.tree.selection() == ()

        panel._on_context_menu(e)

        assert called["popup"] is True
        assert panel.tree.selection() == (iid,)
    finally:
        root.destroy()


