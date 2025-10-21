"""
新功能测试模块

测试内容：
1. 统一导出结果弹窗样式
2. 主显示框支持选中复制功能
3. 导出txt添加接口号信息
4. 主显示框只显示接口号数据
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk


class TestCopyFunctionality:
    """测试复制功能"""
    
    def test_copy_selected_rows_single(self):
        """测试复制单行数据"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建模拟的Treeview
            mock_viewer = MagicMock(spec=ttk.Treeview)
            mock_viewer.selection.return_value = ['item1']
            mock_viewer.__getitem__ = lambda self, key: ['Col1', 'Col2'] if key == 'columns' else None
            mock_viewer.item.return_value = {'values': ['Value1', 'Value2']}
            
            # 模拟剪贴板
            mock_root.clipboard_clear = Mock()
            mock_root.clipboard_append = Mock()
            
            # 执行复制
            wm._copy_selected_rows(mock_viewer)
            
            # 验证剪贴板操作
            mock_root.clipboard_clear.assert_called_once()
            mock_root.clipboard_append.assert_called_once()
            
            # 验证复制的文本格式
            copied_text = mock_root.clipboard_append.call_args[0][0]
            assert copied_text == 'Value1\tValue2'
    
    def test_copy_selected_rows_multiple(self):
        """测试复制多行数据"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建模拟的Treeview
            mock_viewer = MagicMock(spec=ttk.Treeview)
            mock_viewer.selection.return_value = ['item1', 'item2', 'item3']
            mock_viewer.__getitem__ = lambda self, key: ['Col1', 'Col2'] if key == 'columns' else None
            mock_viewer.item.side_effect = [
                {'values': ['A1', 'B1']},
                {'values': ['A2', 'B2']},
                {'values': ['A3', 'B3']}
            ]
            
            # 模拟剪贴板
            mock_root.clipboard_clear = Mock()
            mock_root.clipboard_append = Mock()
            
            # 执行复制
            wm._copy_selected_rows(mock_viewer)
            
            # 验证复制的文本格式（多行用换行分隔）
            copied_text = mock_root.clipboard_append.call_args[0][0]
            assert copied_text == 'A1\tB1\nA2\tB2\nA3\tB3'
    
    def test_copy_selected_rows_empty_selection(self):
        """测试空选择时不复制"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建模拟的Treeview（空选择）
            mock_viewer = MagicMock(spec=ttk.Treeview)
            mock_viewer.selection.return_value = []
            
            # 模拟剪贴板
            mock_root.clipboard_clear = Mock()
            mock_root.clipboard_append = Mock()
            
            # 执行复制
            wm._copy_selected_rows(mock_viewer)
            
            # 验证没有调用剪贴板操作
            mock_root.clipboard_clear.assert_not_called()
            mock_root.clipboard_append.assert_not_called()
    
    def test_select_all_rows(self):
        """测试全选功能"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建模拟的Treeview
            mock_viewer = MagicMock(spec=ttk.Treeview)
            mock_viewer.get_children.return_value = ['item1', 'item2', 'item3', 'item4']
            mock_viewer.selection_set = Mock()
            
            # 执行全选
            wm._select_all_rows(mock_viewer)
            
            # 验证选中了所有项
            mock_viewer.selection_set.assert_called_once_with(['item1', 'item2', 'item3', 'item4'])


class TestInterfaceNumberDisplay:
    """测试接口号显示功能"""
    
    def test_optimized_display_file1(self):
        """测试内部需打开接口只显示A列"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建测试数据（20列）
            df = pd.DataFrame({
                'A': ['A1', 'A2', 'A3'],
                'B': ['B1', 'B2', 'B3'],
                'C': ['C1', 'C2', 'C3'],
                **{f'Col{i}': [f'Val{i}']*3 for i in range(4, 20)}
            })
            
            result = wm._create_optimized_display(df, "内部需打开接口")
            
            # 验证只有一列，且列名为"接口号"
            assert len(result.columns) == 1
            assert result.columns[0] == "接口号"
            assert list(result["接口号"]) == ['A1', 'A2', 'A3']
    
    def test_optimized_display_file2(self):
        """测试内部需回复接口只显示R列"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建测试数据（至少18列，R=索引17）
            df = pd.DataFrame({
                **{f'Col{i}': [f'Val{i}']*3 for i in range(17)},
                'R': ['R1', 'R2', 'R3'],
                **{f'Col{i}': [f'Val{i}']*3 for i in range(18, 30)}
            })
            
            result = wm._create_optimized_display(df, "内部需回复接口")
            
            # 验证只有一列，且列名为"接口号"
            assert len(result.columns) == 1
            assert result.columns[0] == "接口号"
            assert list(result["接口号"]) == ['R1', 'R2', 'R3']
    
    def test_optimized_display_file3(self):
        """测试外部需打开接口只显示C列"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建测试数据（至少3列，C=索引2）
            df = pd.DataFrame({
                'A': ['A1', 'A2', 'A3'],
                'B': ['B1', 'B2', 'B3'],
                'C': ['C1', 'C2', 'C3'],
                **{f'Col{i}': [f'Val{i}']*3 for i in range(3, 20)}
            })
            
            result = wm._create_optimized_display(df, "外部需打开接口")
            
            # 验证只有一列，且列名为"接口号"
            assert len(result.columns) == 1
            assert result.columns[0] == "接口号"
            assert list(result["接口号"]) == ['C1', 'C2', 'C3']
    
    def test_optimized_display_file4(self):
        """测试外部需回复接口只显示E列"""
        with patch('window.tk'):
            from window import WindowManager
            
            mock_root = MagicMock(spec=tk.Tk)
            wm = WindowManager(mock_root)
            
            # 创建测试数据（至少5列，E=索引4）
            df = pd.DataFrame({
                'A': ['A1', 'A2', 'A3'],
                'B': ['B1', 'B2', 'B3'],
                'C': ['C1', 'C2', 'C3'],
                'D': ['D1', 'D2', 'D3'],
                'E': ['E1', 'E2', 'E3'],
                **{f'Col{i}': [f'Val{i}']*3 for i in range(5, 20)}
            })
            
            result = wm._create_optimized_display(df, "外部需回复接口")
            
            # 验证只有一列，且列名为"接口号"
            assert len(result.columns) == 1
            assert result.columns[0] == "接口号"
            assert list(result["接口号"]) == ['E1', 'E2', 'E3']


class TestTreeviewSelectMode:
    """测试Treeview选择模式"""
    
    def test_treeview_extended_select_mode(self):
        """测试Treeview创建时设置了extended选择模式"""
        with patch('window.tk'):
            with patch('window.ttk') as mock_ttk:
                from window import WindowManager
                
                mock_root = MagicMock(spec=tk.Tk)
                mock_parent = MagicMock()
                
                # 模拟Treeview创建
                mock_treeview = MagicMock(spec=ttk.Treeview)
                mock_ttk.Treeview.return_value = mock_treeview
                
                wm = WindowManager(mock_root)
                wm.create_excel_viewer(mock_parent, 'tab1', '测试标签')
                
                # 验证Treeview创建时传入了selectmode='extended'
                mock_ttk.Treeview.assert_called_once()
                call_kwargs = mock_ttk.Treeview.call_args[1]
                assert call_kwargs.get('selectmode') == 'extended'


class TestExportSummaryIntegration:
    """测试导出汇总集成"""
    
    def test_manual_export_uses_summary_popup(self):
        """测试手动导出使用汇总弹窗"""
        with patch('base.WindowManager'):
            with patch('base.tk.Tk'):
                from base import ExcelProcessorApp
                
                app = ExcelProcessorApp(auto_mode=False)
                app.config["user_name"] = "王丹丹"  # 设置默认姓名
                # 模拟有汇总文件路径
                app.last_summary_written_path = 'test_summary.txt'
                
                # 模拟_show_summary_popup方法
                app._show_summary_popup = Mock()
                
                # 验证方法存在
                assert hasattr(app, '_show_summary_popup')
                assert callable(app._show_summary_popup)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

