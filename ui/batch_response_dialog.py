"""Dialogs and pure parsing helpers for batch response/FU operations."""

from __future__ import annotations

from datetime import date
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Iterable, List


FILE_TYPE_NAMES = {
    1: "内部需打开",
    2: "内部需回复",
    3: "外部需打开",
    4: "外部需回复",
    5: "三维提资",
    6: "收发文函",
    7: "FU",
}


def normalize_interface_key(value) -> str:
    text = "" if value is None else str(value).strip()
    text = re.sub(r"\([^)]*\)$", "", text).strip()
    return re.sub(r"\s+", "", text).upper()


def _nonempty_paste_lines(text: str) -> List[str]:
    return [line.rstrip("\r") for line in str(text or "").splitlines() if line.strip()]


def parse_response_paste(text: str, items: Iterable[dict], mode: str = "mapping") -> Dict[int, str]:
    """Parse Excel clipboard text and return item-index -> response-number updates."""
    item_list = list(items or [])
    active_indices = [index for index, item in enumerate(item_list) if item.get("enabled", True)]
    lines = _nonempty_paste_lines(text)
    if not lines:
        raise ValueError("剪贴板内容为空。")

    if mode == "sequential":
        values = []
        for line in lines:
            cells = line.split("\t")
            if len(cells) != 1:
                raise ValueError("按选择顺序粘贴时只能包含一列回文单号。")
            value = cells[0].strip()
            if not value:
                raise ValueError("回文单号不能为空。")
            values.append(value)
        if len(values) != len(active_indices):
            raise ValueError(
                f"粘贴了{len(values)}条回文，但当前启用了{len(active_indices)}个接口；数量必须完全一致。"
            )
        return dict(zip(active_indices, values))

    parsed_rows = []
    for line_number, line in enumerate(lines, start=1):
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) != 2:
            raise ValueError(f"第{line_number}行不是“接口号 + 回文单号”两列。")
        if line_number == 1 and "接口" in cells[0] and "回文" in cells[1]:
            continue
        interface_key = normalize_interface_key(cells[0])
        response_number = cells[1]
        if not interface_key or not response_number:
            raise ValueError(f"第{line_number}行的接口号或回文单号为空。")
        parsed_rows.append((interface_key, response_number, line_number))
    if not parsed_rows:
        raise ValueError("没有可应用的回文数据。")

    selected_by_interface: Dict[str, List[int]] = {}
    for index in active_indices:
        interface_key = normalize_interface_key(item_list[index].get("interface_id"))
        if interface_key:
            selected_by_interface.setdefault(interface_key, []).append(index)

    input_values: Dict[str, str] = {}
    for interface_key, response_number, line_number in parsed_rows:
        if interface_key not in selected_by_interface:
            raise ValueError(f"第{line_number}行接口号不在当前选中任务中：{interface_key}")
        previous = input_values.get(interface_key)
        if previous is not None and previous != response_number:
            raise ValueError(f"接口号{interface_key}在粘贴内容中对应了两个不同回文单号。")
        input_values[interface_key] = response_number

    updates: Dict[int, str] = {}
    for interface_key, response_number in input_values.items():
        # 文件3同一接口可能因不同来源列形成两条任务；相同映射安全地应用到全部匹配项。
        for index in selected_by_interface[interface_key]:
            updates[index] = response_number
    return updates


class BatchResponseDialog(tk.Toplevel):
    """Preview, paste and submit responses for selected file type 1-6 rows."""

    def __init__(self, parent, items: Iterable[dict], on_submit):
        super().__init__(parent)
        self.items = [dict(item, enabled=True, response_number=str(item.get("response_number", "") or "")) for item in items]
        self.on_submit = on_submit
        self.title(f"批量填写回文（共{len(self.items)}个接口）")
        self.geometry("1060x680")
        self.minsize(900, 560)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.common_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="mapping")
        self.status_var = tk.StringVar(value="请填写统一回文，或从Excel粘贴两列数据。")
        self._item_index_by_iid: Dict[str, int] = {}
        self._build_ui()
        self._refresh_tree()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        common = ttk.LabelFrame(outer, text="统一回文单号", padding=8)
        common.pack(fill=tk.X)
        ttk.Label(common, text="回文单号：").pack(side=tk.LEFT)
        entry = ttk.Entry(common, textvariable=self.common_var, width=42)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(common, text="应用到蓝色选中项", command=self._apply_common_to_selection).pack(side=tk.LEFT)
        ttk.Label(common, text="未选择预览行时应用到全部启用项", foreground="gray").pack(side=tk.LEFT, padx=(10, 0))

        paste_frame = ttk.LabelFrame(outer, text="从Excel粘贴", padding=8)
        paste_frame.pack(fill=tk.X, pady=(10, 8))
        modes = ttk.Frame(paste_frame)
        modes.pack(fill=tk.X, pady=(0, 5))
        ttk.Radiobutton(
            modes,
            text="接口号 + 回文单号（推荐，不受界面排序影响）",
            variable=self.mode_var,
            value="mapping",
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            modes,
            text="仅回文单号（严格按当前预览顺序）",
            variable=self.mode_var,
            value="sequential",
        ).pack(side=tk.LEFT, padx=(20, 0))
        paste_body = ttk.Frame(paste_frame)
        paste_body.pack(fill=tk.X)
        self.paste_text = tk.Text(paste_body, height=5, wrap="none", undo=True)
        self.paste_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(paste_body, text="解析并应用", command=self._apply_paste).pack(side=tk.LEFT, padx=(8, 0))

        preview = ttk.LabelFrame(outer, text="提交预览", padding=6)
        preview.pack(fill=tk.BOTH, expand=True)
        columns = ("enabled", "file_type", "project_id", "interface_id", "response_number", "file_name")
        self.tree = ttk.Treeview(preview, columns=columns, show="headings", selectmode="extended")
        headings = {
            "enabled": "选择",
            "file_type": "文件类型",
            "project_id": "项目号",
            "interface_id": "接口号",
            "response_number": "回文单号",
            "file_name": "源文件",
        }
        widths = {"enabled": 55, "file_type": 90, "project_id": 70, "interface_id": 300, "response_number": 180, "file_name": 260}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="center" if column in {"enabled", "file_type", "project_id"} else "w")
        y_scroll = ttk.Scrollbar(preview, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(preview, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        preview.rowconfigure(0, weight=1)
        preview.columnconfigure(0, weight=1)
        self.tree.bind("<Button-1>", self._toggle_enabled)
        self.tree.bind("<Double-1>", self._edit_response_cell)

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var, foreground="#555555").pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(footer, text="取消", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="确认提交", command=self._submit, style="Accent.TButton").pack(side=tk.RIGHT, padx=(0, 8))
        entry.focus_set()

    def _refresh_tree(self):
        selected_indices = {
            self._item_index_by_iid[iid]
            for iid in self.tree.selection()
            if iid in self._item_index_by_iid
        }
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._item_index_by_iid = {}
        for index, item in enumerate(self.items):
            iid = self.tree.insert(
                "",
                tk.END,
                values=(
                    "☑" if item.get("enabled", True) else "☐",
                    FILE_TYPE_NAMES.get(int(item.get("file_type", 0) or 0), item.get("file_type", "")),
                    item.get("project_id", ""),
                    item.get("interface_id", ""),
                    item.get("response_number", ""),
                    os.path.basename(str(item.get("file_path", "") or "")),
                ),
            )
            self._item_index_by_iid[iid] = index
            if index in selected_indices:
                self.tree.selection_add(iid)
        self._update_status()

    def _update_status(self, prefix: str = ""):
        enabled = [item for item in self.items if item.get("enabled", True)]
        filled = [item for item in enabled if str(item.get("response_number", "") or "").strip()]
        summary = f"已启用{len(enabled)}项，已填写{len(filled)}项"
        self.status_var.set(f"{prefix}；{summary}" if prefix else summary)

    def _selected_indices(self) -> List[int]:
        indices = [self._item_index_by_iid[iid] for iid in self.tree.selection() if iid in self._item_index_by_iid]
        return indices or [index for index, item in enumerate(self.items) if item.get("enabled", True)]

    def _apply_common_to_selection(self):
        response_number = self.common_var.get().strip()
        if not response_number:
            messagebox.showwarning("提示", "请输入统一回文单号。", parent=self)
            return
        indices = self._selected_indices()
        applied = 0
        for index in indices:
            if self.items[index].get("enabled", True):
                self.items[index]["response_number"] = response_number
                applied += 1
        self._refresh_tree()
        self._update_status(f"已将“{response_number}”应用到{applied}个接口")

    def _apply_paste(self):
        try:
            updates = parse_response_paste(self.paste_text.get("1.0", tk.END), self.items, self.mode_var.get())
            for index, response_number in updates.items():
                self.items[index]["response_number"] = response_number
            self._refresh_tree()
            self._update_status(f"粘贴内容已应用到{len(updates)}个接口")
        except Exception as exc:
            messagebox.showerror("粘贴内容无法应用", str(exc), parent=self)

    def _toggle_enabled(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell" or self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        index = self._item_index_by_iid.get(iid)
        if index is None:
            return
        self.items[index]["enabled"] = not self.items[index].get("enabled", True)
        self.after_idle(self._refresh_tree)
        return "break"

    def _edit_response_cell(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell" or self.tree.identify_column(event.x) != "#5":
            return
        iid = self.tree.identify_row(event.y)
        index = self._item_index_by_iid.get(iid)
        bbox = self.tree.bbox(iid, "response_number")
        if index is None or not bbox:
            return
        x, y, width, height = bbox
        editor = ttk.Entry(self.tree)
        editor.insert(0, str(self.items[index].get("response_number", "") or ""))
        editor.select_range(0, tk.END)
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()

        def commit(_event=None):
            self.items[index]["response_number"] = editor.get().strip()
            editor.destroy()
            self._refresh_tree()

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda _event: editor.destroy())

    def _submit(self):
        active = [dict(item) for item in self.items if item.get("enabled", True)]
        if not active:
            messagebox.showwarning("提示", "没有启用的接口。", parent=self)
            return
        missing = [str(item.get("interface_id", "") or "") for item in active if not str(item.get("response_number", "") or "").strip()]
        if missing:
            detail = "、".join(missing[:5])
            messagebox.showwarning("仍有未填写项", f"以下接口尚未填写回文单号：{detail}", parent=self)
            return
        seen = set()
        for item in active:
            key = (
                os.path.normcase(os.path.abspath(str(item.get("file_path", "") or ""))),
                int(item.get("file_type", 0) or 0),
                int(item.get("row_index", 0) or 0),
                normalize_interface_key(item.get("interface_id")),
                str(item.get("source_column", "") or "").upper(),
            )
            if key in seen:
                messagebox.showerror("重复任务", f"同一目标接口被重复选择：{item.get('interface_id', '')}", parent=self)
                return
            seen.add(key)
        try:
            self.on_submit(active)
        except Exception as exc:
            messagebox.showerror("提交失败", str(exc), parent=self)
            return
        self.destroy()


class BatchFuCompletionDialog(tk.Toplevel):
    """Confirm one completion date for selected FU rows."""

    def __init__(self, parent, items: Iterable[dict], on_submit):
        super().__init__(parent)
        self.items = [dict(item) for item in items]
        self.on_submit = on_submit
        self.title(f"批量标记FU完成（共{len(self.items)}项）")
        self.geometry("880x520")
        self.minsize(760, 440)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.date_var = tk.StringVar(value=date.today().isoformat())
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        controls = ttk.LabelFrame(outer, text="完成信息", padding=8)
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="实际FU日期：").pack(side=tk.LEFT)
        entry = ttk.Entry(controls, textvariable=self.date_var, width=18)
        entry.pack(side=tk.LEFT)
        ttk.Label(controls, text="格式：YYYY-MM-DD；将统一应用到以下FU", foreground="gray").pack(side=tk.LEFT, padx=(12, 0))

        preview = ttk.LabelFrame(outer, text="提交预览", padding=6)
        preview.pack(fill=tk.BOTH, expand=True, pady=(10, 8))
        columns = ("project_id", "interface_id", "file_name")
        tree = ttk.Treeview(preview, columns=columns, show="headings")
        tree.heading("project_id", text="项目号")
        tree.heading("interface_id", text="内部编码")
        tree.heading("file_name", text="源文件")
        tree.column("project_id", width=90, anchor="center")
        tree.column("interface_id", width=320, anchor="w")
        tree.column("file_name", width=360, anchor="w")
        scroll = ttk.Scrollbar(preview, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        for item in self.items:
            tree.insert("", tk.END, values=(
                item.get("project_id", ""),
                item.get("interface_id", ""),
                os.path.basename(str(item.get("file_path", "") or "")),
            ))

        footer = ttk.Frame(outer)
        footer.pack(fill=tk.X)
        ttk.Label(footer, text=f"共{len(self.items)}项；提交后按源工作簿分组写入", foreground="#555555").pack(side=tk.LEFT)
        ttk.Button(footer, text="取消", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="确认提交", command=self._submit, style="Accent.TButton").pack(side=tk.RIGHT, padx=(0, 8))
        entry.focus_set()

    def _submit(self):
        try:
            target_date = date.fromisoformat(self.date_var.get().strip()).isoformat()
        except Exception:
            messagebox.showerror("日期格式错误", "请输入YYYY-MM-DD格式的有效日期。", parent=self)
            return
        payload = [dict(item, completion_date=target_date) for item in self.items]
        try:
            self.on_submit(payload)
        except Exception as exc:
            messagebox.showerror("提交失败", str(exc), parent=self)
            return
        self.destroy()
