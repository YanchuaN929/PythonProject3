from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Optional

from ui_copy import copy_text, normalize_interface_id

try:
    from registry import hooks as registry_hooks
except Exception:
    registry_hooks = None

try:
    from .shared_log import list_tasks as shared_list_tasks
except Exception:
    shared_list_tasks = None


class TaskRecordPanel(ttk.LabelFrame):
    """显示写入任务的记录面板。"""

    def __init__(
        self,
        parent,
        get_current_user: Callable[[], str],
        auto_refresh: bool = True,
        refresh_interval: int = 5000,
    ):
        super().__init__(parent, text="写入任务记录", padding="6")
        self.get_current_user = get_current_user
        self.manager = None
        self.auto_refresh = auto_refresh
        self.refresh_interval = refresh_interval
        self._refresh_job: Optional[str] = None

        self.only_mine_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="暂无写入任务")
        self._task_by_iid = {}

        self._build_ui()

    def _build_ui(self):
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=2, pady=(0, 4))

        only_mine_cb = ttk.Checkbutton(
            control_frame,
            text="只看我的任务",
            variable=self.only_mine_var,
            command=self.refresh_tasks,
        )
        only_mine_cb.pack(side=tk.LEFT)

        refresh_btn = ttk.Button(control_frame, text="刷新", width=8, command=self.refresh_tasks)
        refresh_btn.pack(side=tk.RIGHT)

        self.tree = ttk.Treeview(
            self,
            columns=("time", "user", "type", "description", "status"),
            show="headings",
            height=12,
            selectmode="extended",
        )
        self.tree.heading("time", text="提交时间")
        self.tree.heading("user", text="提交人")
        self.tree.heading("type", text="类型")
        self.tree.heading("description", text="描述")
        self.tree.heading("status", text="状态")

        # 按截图调整列宽：描述更宽，状态更窄
        self.tree.column("time", width=175, anchor="w")
        self.tree.column("user", width=90, anchor="w")
        self.tree.column("type", width=90, anchor="w")
        self.tree.column("description", width=520, anchor="w")
        self.tree.column("status", width=70, anchor="center")

        tree_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=x_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # 复制：Ctrl+C / 右键菜单
        self.tree.bind("<Control-c>", self._on_copy)
        self.tree.bind("<Control-C>", self._on_copy)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_context_menu)
        self._menu = tk.Menu(self, tearoff=False)
        self._menu.add_command(label="复制接口号", command=self.copy_selected_interface_ids)
        self._menu.add_command(label="查看指派明细", command=self.open_selected_assignment_detail)
        self._menu.add_command(label="查看回文单号明细", command=self.open_selected_response_detail)

        self.status_label = ttk.Label(self, textvariable=self.status_var, anchor="w", foreground="gray")
        self.status_label.pack(fill=tk.X, pady=(4, 0))

    def _on_context_menu(self, event):
        # 右键时自动选中鼠标所在行（否则用户未先左键选中时，菜单动作会因 selection 为空而“无反应”）
        try:
            row_iid = self.tree.identify_row(getattr(event, "y", 0))
            if row_iid:
                # 聚焦并选中当前行
                try:
                    self.tree.focus(row_iid)
                except Exception:
                    pass
                sel = set(self.tree.selection() or ())
                if row_iid not in sel:
                    self.tree.selection_set((row_iid,))
        except Exception:
            pass
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._menu.grab_release()
            except Exception:
                pass

    def _on_copy(self, event=None):
        self.copy_selected_interface_ids()
        return "break"

    @staticmethod
    def _extract_interface_ids_from_task(task) -> list:
        ids = []
        try:
            if getattr(task, "task_type", "") == "assignment":
                for a in (task.payload or {}).get("assignments") or []:
                    interface_id = normalize_interface_id((a or {}).get("interface_id", ""))
                    if interface_id:
                        ids.append(interface_id)
            elif getattr(task, "task_type", "") == "response":
                interface_id = normalize_interface_id((task.payload or {}).get("interface_id", ""))
                if interface_id:
                    ids.append(interface_id)
        except Exception:
            pass
        # 去重但保序
        seen = set()
        out = []
        for x in ids:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    @staticmethod
    def _extract_response_numbers_from_task(task) -> list:
        nums = []
        try:
            if getattr(task, "task_type", "") == "response":
                rn = str((task.payload or {}).get("response_number", "") or "").strip()
                if rn:
                    nums.append(rn)
        except Exception:
            pass
        # 去重保序
        seen = set()
        out = []
        for x in nums:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    def copy_selected_interface_ids(self):
        interface_ids = []
        for iid in self.tree.selection():
            task = self._task_by_iid.get(iid)
            if not task:
                continue
            interface_ids.extend(self._extract_interface_ids_from_task(task))
        # 去重保序
        seen = set()
        uniq = []
        for x in interface_ids:
            if x in seen:
                continue
            seen.add(x)
            uniq.append(x)
        if not uniq:
            return
        copy_text(self, "\n".join(uniq).strip())

    def _on_double_click(self, event=None):
        # 仅对指派类任务：双击弹窗展示明细
        self.open_selected_assignment_detail()

    def open_selected_assignment_detail(self):
        sel = list(self.tree.selection())
        if not sel:
            return
        # 若多选，取第一条
        task = self._task_by_iid.get(sel[0])
        if not task or getattr(task, "task_type", "") != "assignment":
            return
        self._open_assignment_detail_dialog(task)

    def open_selected_response_detail(self):
        sel = list(self.tree.selection())
        if not sel:
            return
        task = self._task_by_iid.get(sel[0])
        if not task or getattr(task, "task_type", "") != "response":
            return
        self._open_response_detail_dialog(task)

    def _open_response_detail_dialog(self, task):
        win = tk.Toplevel(self)
        win.title("回文单号明细")
        win.geometry("900x420")
        win.transient(self.winfo_toplevel())
        win.grab_set()

        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text=task.description or "回文单号明细", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        def _copy_response_number():
            nums = self._extract_response_numbers_from_task(task)
            if nums:
                copy_text(win, "\n".join(nums).strip())

        ttk.Button(top, text="复制回文单号", command=_copy_response_number).pack(side=tk.RIGHT)

        columns = ("response_number", "interface_id", "project_id", "file_type", "row_index", "file_path")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=14, selectmode="extended")
        tree.heading("response_number", text="回文单号")
        tree.heading("interface_id", text="接口号")
        tree.heading("project_id", text="项目号")
        tree.heading("file_type", text="文件类型")
        tree.heading("row_index", text="行号")
        tree.heading("file_path", text="文件")

        tree.column("response_number", width=140, anchor="w")
        tree.column("interface_id", width=260, anchor="w")
        tree.column("project_id", width=90, anchor="w")
        tree.column("file_type", width=80, anchor="center")
        tree.column("row_index", width=70, anchor="center")
        tree.column("file_path", width=320, anchor="w")

        y_scroll = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(win, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        p = task.payload or {}
        tree.insert(
            "",
            tk.END,
            values=(
                str(p.get("response_number", "") or ""),
                normalize_interface_id(p.get("interface_id", "")),
                str(p.get("project_id", "") or ""),
                str(p.get("file_type", "") or ""),
                str(p.get("row_index", "") or ""),
                str(p.get("file_path", "") or ""),
            ),
        )

        def on_copy(event=None):
            nums = []
            for iid in tree.selection():
                vals = tree.item(iid, "values") or ()
                if vals and vals[0]:
                    nums.append(str(vals[0]).strip())
            if not nums:
                nums = self._extract_response_numbers_from_task(task)
            # 去重保序
            seen = set()
            uniq = []
            for x in nums:
                if x in seen:
                    continue
                seen.add(x)
                uniq.append(x)
            if uniq:
                copy_text(win, "\n".join(uniq).strip())
            return "break"

        tree.bind("<Control-c>", on_copy)
        tree.bind("<Control-C>", on_copy)

    def _open_assignment_detail_dialog(self, task):
        win = tk.Toplevel(self)
        win.title("指派明细（接口号列表）")
        win.geometry("900x520")
        win.transient(self.winfo_toplevel())
        win.grab_set()

        top = ttk.Frame(win, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text=task.description or "指派明细", anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(top, text="复制接口号", command=lambda: self._copy_assignment_detail(win, task)).pack(side=tk.RIGHT)

        columns = ("interface_id", "project_id", "assigned_to", "file_type", "row_index")
        tree = ttk.Treeview(win, columns=columns, show="headings", height=18, selectmode="extended")
        tree.heading("interface_id", text="接口号")
        tree.heading("project_id", text="项目号")
        tree.heading("assigned_to", text="指派给")
        tree.heading("file_type", text="文件类型")
        tree.heading("row_index", text="行号")

        tree.column("interface_id", width=380, anchor="w")
        tree.column("project_id", width=90, anchor="w")
        tree.column("assigned_to", width=120, anchor="w")
        tree.column("file_type", width=80, anchor="center")
        tree.column("row_index", width=70, anchor="center")

        y_scroll = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(win, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        assignments = (task.payload or {}).get("assignments") or []
        for a in assignments:
            a = a or {}
            tree.insert(
                "",
                tk.END,
                values=(
                    normalize_interface_id(a.get("interface_id", "")),
                    str(a.get("project_id", "") or ""),
                    str(a.get("assigned_name", "") or ""),
                    str(a.get("file_type", "") or ""),
                    str(a.get("row_index", "") or ""),
                ),
            )

        def on_copy(event=None):
            ids = []
            for iid in tree.selection():
                vals = tree.item(iid, "values") or ()
                if vals and vals[0]:
                    ids.append(normalize_interface_id(vals[0]))
            if not ids:
                ids = [normalize_interface_id((a or {}).get("interface_id", "")) for a in assignments if (a or {}).get("interface_id")]
            # 去重保序
            seen = set()
            uniq = []
            for x in ids:
                if x in seen:
                    continue
                seen.add(x)
                uniq.append(x)
            copy_text(win, "\n".join(uniq).strip())
            return "break"

        tree.bind("<Control-c>", on_copy)
        tree.bind("<Control-C>", on_copy)

    def _copy_assignment_detail(self, win, task):
        ids = self._extract_interface_ids_from_task(task)
        copy_text(win, "\n".join(ids).strip())

    def bind_manager(self, manager):
        self.manager = manager
        try:
            # 事件驱动刷新：写入任务状态变化时立刻刷新（比 5s 轮询更“实时”）
            def _listener(task):
                try:
                    # manager 的回调在后台线程触发，Tk 更新必须回到主线程
                    self.after(0, self.refresh_tasks)
                except Exception:
                    pass

            manager.register_listener(_listener)
        except Exception:
            pass
        self.refresh_tasks()
        if self.auto_refresh:
            self._schedule_refresh()

    def _schedule_refresh(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(self.refresh_interval, self.refresh_tasks)

    def refresh_tasks(self):
        tasks = self._collect_tasks()
        self._populate_tree(tasks)
        if self.auto_refresh and self.manager:
            self._schedule_refresh()

    def _collect_tasks(self) -> Iterable:
        # 优先从共享 registry.db 的 write_tasks_log 读取（可看到所有用户）
        shared_tasks = self._collect_shared_tasks()
        # 共享读取成功且有数据：直接使用共享数据
        if isinstance(shared_tasks, list) and len(shared_tasks) > 0:
            return shared_tasks
        # 共享读取成功但为空：如果本机队列存在，则回退显示本机（避免首次运行空窗）
        if isinstance(shared_tasks, list) and len(shared_tasks) == 0 and self.manager:
            pass
        elif shared_tasks is not None and self.manager is None:
            # 没有本机manager时，哪怕为空也返回共享结果
            return shared_tasks

        # 兜底：只显示本机任务（旧模式）
        if not self.manager:
            self.status_var.set("写入队列未初始化")
            return []

        try:
            tasks = list(self.manager.get_tasks())
        except Exception as exc:
            self.status_var.set(f"获取任务失败: {exc}")
            return []

        tasks.sort(key=lambda t: (t.submitted_at or ""), reverse=True)

        if self.only_mine_var.get():
            current_user = (self.get_current_user() or "").strip()
            if current_user:
                tasks = [task for task in tasks if (task.submitted_by or "").strip() == current_user]

        return tasks[:100]

    def _collect_shared_tasks(self):
        if not shared_list_tasks or not registry_hooks:
            return None
        try:
            cfg = registry_hooks._cfg()
            if not cfg.get("registry_enabled", True):
                return None
            db_path = cfg.get("registry_db_path")
            if not db_path:
                return None
            wal = bool(cfg.get("registry_wal", False))
            from registry.db import get_connection

            conn = get_connection(db_path, wal)
            if self.only_mine_var.get():
                current_user = (self.get_current_user() or "").strip()
                tasks = shared_list_tasks(conn, limit=100, only_user=current_user)
            else:
                tasks = shared_list_tasks(conn, limit=100, only_user=None)
            # 仅当共享有数据时才显示“共享”状态；为空时交给上层决定是否回退
            if tasks:
                self.status_var.set(f"显示 {len(tasks)} 条任务（共享）")
            return tasks
        except Exception as exc:
            # 共享读取失败时不阻塞，回退到本机显示
            self.status_var.set(f"共享任务读取失败，已回退本机: {exc}")
            return None
    def _populate_tree(self, tasks: Iterable):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._task_by_iid = {}

        type_map = {
            "assignment": "任务指派",
            "response": "回文填报",
        }
        status_map = {
            "pending": "待执行",
            "running": "执行中",
            "completed": "完成",
            "failed": "失败",
        }

        count = 0
        for task in tasks:
            count += 1
            display_type = type_map.get(task.task_type, task.task_type)
            status = status_map.get(task.status, task.status)
            submitted_time = task.submitted_at or ""
            iid = str(getattr(task, "task_id", "")) or None
            inserted = self.tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    submitted_time,
                    task.submitted_by or "",
                    display_type,
                    task.description or "",
                    status,
                ),
            )
            self._task_by_iid[inserted] = task

        if count == 0:
            self.status_var.set("暂无写入任务")
        else:
            self.status_var.set(f"显示 {count} 条任务")

    def destroy(self):
        if self._refresh_job:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:
                pass
        super().destroy()



