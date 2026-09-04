#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帮助窗口样式与内容回归测试。"""

from pathlib import Path
import subprocess
import sys


def test_help_toc_style_does_not_mutate_global_treeview():
    # 本项目的Windows/Tcl运行时在同一pytest进程内反复销毁默认Tk根窗口时
    # 偶尔会污染后续GUI fixture，因此放到子进程做真实Tk样式验证。
    project_root = Path(__file__).resolve().parents[1]
    script = r'''
import tkinter as tk
from tkinter import ttk
from ui.help_viewer import HelpViewer

root = tk.Tk()
root.withdraw()
style = ttk.Style(root)
rowheight_before = style.lookup("Treeview", "rowheight")
font_before = style.lookup("Treeview", "font")
viewer = HelpViewer(root)
viewer.window = root
viewer._create_toc_panel(ttk.Frame(root))
assert viewer.toc_tree.cget("style") == "Help.TOC.Treeview"
assert style.lookup("Help.TOC.Treeview", "rowheight") == 28
assert style.lookup("Treeview", "rowheight") == rowheight_before
assert style.lookup("Treeview", "font") == font_before
root.destroy()
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_help_document_contains_current_fu_and_registry_workflow():
    help_path = Path(__file__).resolve().parents[1] / "document" / "4_使用说明.md"
    content = help_path.read_text(encoding="utf-8")

    assert "版本**: 以程序右下角显示为准" in content
    assert "### 1.1 三分钟快速上手" in content
    assert "刷新文件列表 → 开始处理 → 完成/指派/审查 → 导出结果" in content
    assert "点击该行 **是否已完成** 方框" in content
    assert "只重试状态同步，不会重复写Excel" in content
    assert "`.registry/registry.db`" in content
