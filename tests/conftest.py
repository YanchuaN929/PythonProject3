#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest配置文件和共享fixtures
"""

import pytest
from unittest.mock import Mock, MagicMock
import tkinter as tk
from tkinter import ttk
import pandas as pd


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

