#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口管理器单元测试
测试window.py中的WindowManager类的各项功能
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk
import pandas as pd
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from window import WindowManager


class TestWindowManagerInitialization:
    """测试WindowManager初始化"""
    
    def test_init_without_callbacks(self, mock_root):
        """测试无回调初始化"""
        wm = WindowManager(mock_root)
        assert wm.root == mock_root
        assert wm.callbacks == {}
        assert len(wm.viewers) == 6
        assert all(v is None for v in wm.viewers.values())
    
    def test_init_with_callbacks(self, mock_root, mock_callbacks):
        """测试带回调初始化"""
        wm = WindowManager(mock_root, mock_callbacks)
        assert wm.callbacks == mock_callbacks
        assert 'on_browse_folder' in wm.callbacks
    
    def test_viewers_initialization(self, mock_root):
        """测试viewer字典初始化"""
        wm = WindowManager(mock_root)
        expected_tabs = ['tab1', 'tab2', 'tab3', 'tab4', 'tab5', 'tab6']
        assert list(wm.viewers.keys()) == expected_tabs


class TestWindowSizeAdaptation:
    """测试窗口大小自适应"""
    
    def test_window_size_1920x1080(self, mock_root):
        """测试1920x1080分辨率 - 应该全屏"""
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080
        
        wm = WindowManager(mock_root)
        wm.setup_window_size()
        
        # 验证调用了最大化窗口
        mock_root.state.assert_called_with('zoomed')
    
    def test_window_size_1600x900(self, mock_root):
        """测试1600x900分辨率 - 应该90%屏幕空间"""
        mock_root.winfo_screenwidth.return_value = 1600
        mock_root.winfo_screenheight.return_value = 900
        
        wm = WindowManager(mock_root)
        wm.setup_window_size()
        
        # 验证设置了窗口大小
        expected_width = int(1600 * 0.9)
        expected_height = int(900 * 0.9)
        mock_root.geometry.assert_called()
    
    def test_window_size_1366x768(self, mock_root):
        """测试1366x768分辨率 - 应该85%屏幕空间"""
        mock_root.winfo_screenwidth.return_value = 1366
        mock_root.winfo_screenheight.return_value = 768
        
        wm = WindowManager(mock_root)
        wm.setup_window_size()
        
        # 验证设置了窗口大小
        mock_root.geometry.assert_called()
    
    def test_window_size_small_screen(self, mock_root):
        """测试小屏幕分辨率 - 应该使用最小推荐尺寸"""
        mock_root.winfo_screenwidth.return_value = 1024
        mock_root.winfo_screenheight.return_value = 600
        
        wm = WindowManager(mock_root)
        wm.setup_window_size()
        
        # 验证设置了窗口大小且不超过屏幕
        mock_root.geometry.assert_called()


class TestColumnWidthCalculation:
    """测试列宽计算功能"""
    
    def test_calculate_column_widths_normal_data(self):
        """测试正常数据的列宽计算"""
        df = pd.DataFrame({
            '短列': ['A', 'B'],
            '中文列名测试': ['中文内容很长很长', '测试'],
            'EnglishColumn': ['Short', 'VeryLongContent'],
        })
        
        wm = WindowManager(Mock())
        widths = wm.calculate_column_widths(df, df.columns)
        
        # 验证宽度在合理范围
        assert len(widths) == 3
        assert all(60 <= w <= 300 for w in widths)
    
    def test_calculate_column_widths_chinese_wider(self):
        """测试中文列宽度应该比英文宽"""
        df = pd.DataFrame({
            '中文列名很长': ['中文内容非常非常非常长', '测试数据也很长'],
            'ShortEng': ['Short', 'Text'],
        })
        
        wm = WindowManager(Mock())
        widths = wm.calculate_column_widths(df, df.columns)
        
        # 中文列宽度应该大于英文列
        assert widths[0] > widths[1], f"中文列宽{widths[0]}应该>英文列宽{widths[1]}"
    
    def test_calculate_column_widths_empty_dataframe(self):
        """测试空DataFrame"""
        df = pd.DataFrame()
        
        wm = WindowManager(Mock())
        widths = wm.calculate_column_widths(df, [])
        
        # 空DataFrame应返回空列表
        assert widths == []
    
    def test_calculate_column_widths_single_row(self):
        """测试单行DataFrame"""
        df = pd.DataFrame({'列1': ['值1']})
        
        wm = WindowManager(Mock())
        widths = wm.calculate_column_widths(df, df.columns)
        
        assert len(widths) == 1
        assert 60 <= widths[0] <= 300


class TestDataDisplay:
    """测试数据显示功能"""
    
    def test_show_empty_message(self, mock_root):
        """测试显示空消息"""
        wm = WindowManager(mock_root)
        
        # Mock Treeview (使用MagicMock支持item assignment)
        mock_viewer = MagicMock(spec=ttk.Treeview)
        mock_viewer.get_children.return_value = []
        
        wm.show_empty_message(mock_viewer, "测试消息")
        
        # 验证调用了insert
        mock_viewer.insert.assert_called_once()
    
    @patch('window.pd.isna')
    def test_display_excel_data_basic(self, mock_isna, mock_root, sample_dataframe):
        """测试基本Excel数据显示"""
        mock_isna.return_value = False
        
        wm = WindowManager(mock_root)
        
        # Mock Treeview (使用MagicMock)
        mock_viewer = MagicMock(spec=ttk.Treeview)
        mock_viewer.get_children.return_value = []
        
        # 执行显示（不显示全部，仅前20行）
        wm.display_excel_data(mock_viewer, sample_dataframe, "测试", show_all=False)
        
        # 验证调用了insert（应该插入3行数据）
        assert mock_viewer.insert.call_count == 3
    
    @patch('window.pd.isna')
    def test_display_excel_data_show_all(self, mock_isna, mock_root, sample_dataframe):
        """测试显示全部数据功能"""
        mock_isna.return_value = False
        
        wm = WindowManager(mock_root)
        
        # Mock Treeview (使用MagicMock)
        mock_viewer = MagicMock(spec=ttk.Treeview)
        mock_viewer.get_children.return_value = []
        
        # 执行显示（显示全部）
        wm.display_excel_data(mock_viewer, sample_dataframe, "测试", show_all=True)
        
        # 验证显示了所有行
        assert mock_viewer.insert.call_count == 3
    
    def test_display_excel_data_with_original_row_numbers(self, mock_root):
        """测试使用原始行号显示"""
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': ['a', 'b', 'c']
        })
        
        wm = WindowManager(mock_root)
        
        # Mock Treeview (使用MagicMock)
        mock_viewer = MagicMock(spec=ttk.Treeview)
        mock_viewer.get_children.return_value = []
        
        # 原始行号
        original_rows = [5, 10, 15]
        
        # 执行显示
        with patch('window.pd.isna', return_value=False):
            wm.display_excel_data(mock_viewer, df, "测试", show_all=True, original_row_numbers=original_rows)
        
        # 验证使用了原始行号
        calls = mock_viewer.insert.call_args_list
        assert len(calls) == 3
        assert calls[0][1]['text'] == '5'
        assert calls[1][1]['text'] == '10'
        assert calls[2][1]['text'] == '15'


class TestCallbackTrigger:
    """测试回调触发功能"""
    
    def test_trigger_callback_success(self, mock_root, mock_callbacks):
        """测试成功触发回调"""
        wm = WindowManager(mock_root, mock_callbacks)
        
        wm._trigger_callback('on_browse_folder')
        
        mock_callbacks['on_browse_folder'].assert_called_once()
    
    def test_trigger_callback_not_exist(self, mock_root):
        """测试触发不存在的回调"""
        wm = WindowManager(mock_root)
        
        # 不应该抛出异常
        wm._trigger_callback('non_existent_callback')
    
    def test_trigger_callback_exception(self, mock_root):
        """测试回调抛出异常时的处理"""
        def failing_callback():
            raise ValueError("测试异常")
        
        wm = WindowManager(mock_root, {'test': failing_callback})
        
        # 不应该抛出异常
        wm._trigger_callback('test')


class TestPathMethods:
    """测试路径相关方法"""
    
    def test_get_set_path_value(self, mock_root):
        """测试获取和设置路径"""
        wm = WindowManager(mock_root)
        # 使用Mock代替真实的StringVar
        wm.path_var = Mock()
        wm.path_var.get.return_value = "初始路径"
        
        # 测试获取
        assert wm.get_path_value() == "初始路径"
        
        # 测试设置
        wm.set_path_value("新路径")
        wm.path_var.set.assert_called_with("新路径")
    
    def test_get_set_export_path_value(self, mock_root):
        """测试获取和设置导出路径"""
        wm = WindowManager(mock_root)
        # 使用Mock代替真实的StringVar
        wm.export_path_var = Mock()
        wm.export_path_var.get.return_value = "初始导出路径"
        
        # 测试获取
        assert wm.get_export_path_value() == "初始导出路径"
        
        # 测试设置
        wm.set_export_path_value("新导出路径")
        wm.export_path_var.set.assert_called_with("新导出路径")


class TestButtonControl:
    """测试按钮控制功能"""
    
    def test_enable_export_button(self, mock_root):
        """测试启用导出按钮"""
        wm = WindowManager(mock_root)
        
        # Mock按钮
        mock_button = Mock()
        wm.buttons['export'] = mock_button
        
        # 启用按钮
        wm.enable_export_button(True)
        mock_button.config.assert_called_with(state='normal')
        
        # 禁用按钮
        wm.enable_export_button(False)
        mock_button.config.assert_called_with(state='disabled')


class TestUpdateFileInfo:
    """测试文件信息更新"""
    
    def test_update_file_info(self, mock_root):
        """测试更新文件信息显示"""
        wm = WindowManager(mock_root)
        
        # Mock ScrolledText
        mock_text = Mock()
        wm.file_info_text = mock_text
        
        # 更新信息
        wm.update_file_info("测试文件信息")
        
        # 验证调用
        mock_text.config.assert_called()
        mock_text.delete.assert_called_once()
        mock_text.insert.assert_called_with('1.0', "测试文件信息")


class TestOptimizedDisplay:
    """测试优化显示功能"""
    
    def test_create_optimized_display_file1(self, mock_root):
        """测试文件1的优化显示（仅显示接口号列）"""
        # 创建足够列数的DataFrame
        columns = [f'Col{i}' for i in range(20)]
        df = pd.DataFrame([[i] * 20 for i in range(5)], columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "内部需打开接口")
        
        # 应该显示至少3列：状态 + 接口号 + 是否已完成
        assert len(result.columns) >= 3
        assert '接口号' in result.columns
        assert '状态' in result.columns
        assert '是否已完成' in result.columns
        # 当没有项目号列时，顺序应该是：状态、接口号、是否已完成
        assert result.columns[0] == "状态"
        # 验证数据来自第0列
        assert list(result["接口号"]) == [0, 1, 2, 3, 4]
    
    def test_create_optimized_display_unknown_type(self, mock_root):
        """测试未知类型返回原始数据"""
        df = pd.DataFrame({'A': [1, 2, 3]})
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "未知类型")
        
        # 应该返回原始DataFrame
        assert result.equals(df)


# 运行测试的主函数
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=window', '--cov-report=html'])

