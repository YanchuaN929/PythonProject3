#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest配置文件和共享fixtures
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk
import pandas as pd


# 自动为所有ExcelProcessorApp实例设置默认姓名并禁止弹窗
@pytest.fixture(autouse=True)
def setup_default_user_name(monkeypatch, request):
    """自动为ExcelProcessorApp设置默认姓名并禁止测试时弹窗"""
    allow_empty = request.node.get_closest_marker("allow_empty_name") is not None
    
    # 1. Mock所有messagebox调用，避免测试时弹窗
    try:
        from unittest.mock import Mock
        import tkinter.messagebox
        monkeypatch.setattr(tkinter.messagebox, 'showinfo', Mock())
        monkeypatch.setattr(tkinter.messagebox, 'showwarning', Mock())
        monkeypatch.setattr(tkinter.messagebox, 'showerror', Mock())
        monkeypatch.setattr(tkinter.messagebox, 'askyesno', Mock(return_value=True))
    except ImportError:
        pass
    
    # 跳过真实的开机自启动注册
    monkeypatch.setenv("EXCEL_PROCESSOR_SKIP_AUTO_STARTUP", "1")
    
    # 2. Patch ExcelProcessorApp的初始化，提前设置姓名
    if allow_empty:
        yield
        return
    
    try:
        from base import ExcelProcessorApp
    except ImportError:
        yield
        return
    
    original_init = ExcelProcessorApp.__init__
    
    def patched_init(self, auto_mode=False, resume_action=""):
        # 在调用原始__init__之前，先设置一个临时config
        self.config = {"user_name": "王丹丹"}
        # 调用原始初始化
        original_init(self, auto_mode, resume_action)
        # 确保姓名被设置（以防被覆盖）
        self.config["user_name"] = "王丹丹"
    
    monkeypatch.setattr(ExcelProcessorApp, '__init__', patched_init)
    
    yield


@pytest.fixture
def mock_root():
    """Mock Tkinter根窗口"""
    root = MagicMock(spec=tk.Tk)
    root.winfo_screenwidth.return_value = 1920
    root.winfo_screenheight.return_value = 1080
    root.winfo_width.return_value = 1920
    root.winfo_height.return_value = 1080
    return root


@pytest.fixture
def sample_dataframe():
    """测试用DataFrame"""
    return pd.DataFrame({
        'A列': ['数据1', '数据2', '数据3'],
        'B列': ['测试1', '测试2', '测试3'],
        'H列': ['25C1', '25C2', '25C3'],
        'K列': ['2025-10-15', '2025-10-16', '2025-10-17'],
        'M列': ['', '', ''],
    })


@pytest.fixture
def mock_callbacks():
    """Mock回调函数"""
    return {
        'on_browse_folder': Mock(),
        'on_browse_export_folder': Mock(),
        'on_refresh_files': Mock(),
        'on_start_processing': Mock(),
        'on_export_results': Mock(),
        'on_open_folder': Mock(),
        'on_open_monitor': Mock(),
        'on_settings_menu': Mock(),
        'on_tab_changed': Mock(),
    }


@pytest.fixture
def process_vars():
    """Mock处理勾选框变量"""
    return {
        'tab1': tk.BooleanVar(value=True),
        'tab2': tk.BooleanVar(value=True),
        'tab3': tk.BooleanVar(value=True),
        'tab4': tk.BooleanVar(value=True),
        'tab5': tk.BooleanVar(value=True),
        'tab6': tk.BooleanVar(value=True),
    }


@pytest.fixture
def config_data():
    """Mock配置数据"""
    return {
        'folder_path': 'D:/test/path',
        'export_folder_path': 'D:/test/export',
    }


@pytest.fixture
def base_app(monkeypatch):
    """创建ExcelProcessorApp实例用于测试"""
    from unittest.mock import MagicMock
    import tkinter as tk
    
    # Mock所有messagebox
    monkeypatch.setattr('tkinter.messagebox.showinfo', MagicMock())
    monkeypatch.setattr('tkinter.messagebox.showwarning', MagicMock())
    monkeypatch.setattr('tkinter.messagebox.showerror', MagicMock())
    monkeypatch.setattr('tkinter.messagebox.askyesno', MagicMock(return_value=False))
    
    # Mock load_user_role to prevent file loading errors
    from base import ExcelProcessorApp
    original_load_user_role = ExcelProcessorApp.load_user_role
    
    def mock_load_user_role(self):
        """Mock的load_user_role，避免文件读取错误"""
        self.user_name = self.config.get("user_name", "").strip()
        self.user_role = ""
        self.user_roles = []
    
    monkeypatch.setattr(ExcelProcessorApp, 'load_user_role', mock_load_user_role)
    
    # 创建app实例
    app = ExcelProcessorApp(auto_mode=True)
    app.user_roles = []  # 默认空角色
    
    yield app
    
    # 清理
    try:
        app.root.destroy()
    except:
        pass

