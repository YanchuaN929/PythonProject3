#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用PAGE生成的GUI代码示例
这个文件展示了如何将PAGE生成的GUI代码整合到现有项目中
"""

import tkinter as tk
from tkinter import filedialog


def set_Tk_var():
    """初始化tkinter变量"""
    global path_var, export_path_var
    path_var = tk.StringVar()
    export_path_var = tk.StringVar()


def init(top, gui, *args, **kwargs):
    """初始化GUI"""
    global w, top_level, root
    w = gui
    top_level = top
    root = top


def destroy_window():
    """销毁窗口"""
    global top_level
    top_level.destroy()
    top_level = None


def browse_folder():
    """浏览文件夹回调函数"""
    folder_path = filedialog.askdirectory()
    if folder_path:
        path_var.set(folder_path)


def browse_export_folder():
    """浏览导出文件夹回调函数"""
    folder_path = filedialog.askdirectory()
    if folder_path:
        export_path_var.set(folder_path)


if __name__ == '__main__':
    """测试运行GUI"""
    import importlib
    interface_gui = importlib.import_module("interface_gui")
    
    # 创建根窗口
    root = tk.Tk()
    
    # 设置tkinter变量
    set_Tk_var()
    
    # 初始化GUI
    top = interface_gui.Toplevel1(root)
    
    # 运行主循环
    root.mainloop()