# -*- coding: utf-8 -*-
"""
测试主界面显示时的角色筛选功能

测试场景：
1. 单角色筛选（设计人员、接口工程师、主任、管理员）
2. 多角色筛选（合并结果）
3. 没有角色来源列的数据
4. 空角色列表
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestRoleFilterDisplay:
    """测试显示时的角色筛选功能"""
    
    @pytest.fixture
    def sample_df_with_roles(self):
        """创建带有角色来源的测试数据"""
        return pd.DataFrame({
            '项目号': ['2016', '2016', '1818', '2026', '2016', '1818'],
            'A': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005', 'INT-006'],
            '角色来源': ['设计人员', '2016接口工程师', '设计人员', '设计人员、2026接口工程师', '管理员', None],
            '原始行号': [10, 11, 12, 13, 14, 15]
        })
    
    @pytest.fixture
    def window_manager(self):
        """创建WindowManager实例"""
        with patch('window.tk.Tk'):
            from window import WindowManager
            callbacks = {}
            root = MagicMock()
            wm = WindowManager(root, callbacks)
            # 初始化必要的属性
            wm.project_vars = {}
            return wm
    
    def test_filter_by_single_role_designer(self, window_manager, sample_df_with_roles):
        """测试单角色筛选 - 设计人员"""
        viewer = MagicMock()
        viewer.get_children.return_value = []  # 模拟空的viewer
        current_user_roles = ['设计人员']
        
        # 调用显示方法
        window_manager.display_excel_data(
            viewer=viewer,
            df=sample_df_with_roles,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 由于筛选后应该只显示"设计人员"和多角色包含"设计人员"的行
        # 预期：INT-001(设计人员), INT-003(设计人员), INT-004(含设计人员), INT-006(None宽松筛选) (4行)
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 4
    
    def test_filter_by_single_role_engineer(self, window_manager, sample_df_with_roles):
        """测试单角色筛选 - 接口工程师"""
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = ['2016接口工程师']
        
        window_manager.display_excel_data(
            viewer=viewer,
            df=sample_df_with_roles,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 预期：INT-002(2016接口工程师), INT-006(None宽松筛选) (2行)
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 2
    
    def test_filter_by_multiple_roles(self, window_manager, sample_df_with_roles):
        """测试多角色筛选"""
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = ['设计人员', '2016接口工程师']
        
        window_manager.display_excel_data(
            viewer=viewer,
            df=sample_df_with_roles,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 预期：INT-001(设计人员), INT-002(2016接口工程师), INT-003(设计人员), INT-004(含设计人员), INT-006(None宽松筛选) (5行)
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 5
    
    def test_filter_with_director_role(self, window_manager):
        """测试主任角色筛选"""
        df = pd.DataFrame({
            '项目号': ['2016', '2016', '1818'],
            'A': ['INT-001', 'INT-002', 'INT-003'],
            '角色来源': ['一室主任', '二室主任', '建筑总图室主任'],
            '原始行号': [10, 11, 12]
        })
        
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = ['一室主任']
        
        window_manager.display_excel_data(
            viewer=viewer,
            df=df,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 预期：只显示INT-001 (1行)
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 1
    
    def test_filter_with_admin_role(self, window_manager, sample_df_with_roles):
        """测试管理员角色筛选（应该显示所有数据）"""
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = ['管理员']
        
        window_manager.display_excel_data(
            viewer=viewer,
            df=sample_df_with_roles,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 管理员应该能看到标记为"管理员"的行，加上None的行（宽松筛选）
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 2  # INT-005(管理员) + INT-006(None宽松筛选)
    
    def test_filter_no_role_column(self, window_manager):
        """测试没有角色来源列的数据（不应报错）"""
        df = pd.DataFrame({
            '项目号': ['2016', '2016'],
            'A': ['INT-001', 'INT-002'],
            '原始行号': [10, 11]
        })
        
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = ['设计人员']
        
        # 不应该抛出异常
        window_manager.display_excel_data(
            viewer=viewer,
            df=df,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 没有角色来源列，应该显示所有数据
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 2
    
    def test_filter_empty_roles_list(self, window_manager, sample_df_with_roles):
        """测试空角色列表（应显示全部数据）"""
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = []
        
        window_manager.display_excel_data(
            viewer=viewer,
            df=sample_df_with_roles,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 空角色列表，应该显示所有数据
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 6
    
    def test_filter_with_nan_role_source(self, window_manager):
        """测试角色来源为NaN的数据（宽松筛选，应该显示）"""
        df = pd.DataFrame({
            '项目号': ['2016', '2016', '1818'],
            'A': ['INT-001', 'INT-002', 'INT-003'],
            '角色来源': ['设计人员', np.nan, ''],
            '原始行号': [10, 11, 12]
        })
        
        viewer = MagicMock()
        viewer.get_children.return_value = []
        current_user_roles = ['设计人员']
        
        window_manager.display_excel_data(
            viewer=viewer,
            df=df,
            tab_name="内部需打开接口",
            show_all=True,
            current_user_roles=current_user_roles
        )
        
        # 预期：3行都应该显示（宽松筛选）
        insert_calls = [call for call in viewer.insert.call_args_list]
        assert len(insert_calls) == 3


class TestCopyInterfaceNumber:
    """测试复制接口号功能"""
    
    @pytest.fixture
    def window_manager(self):
        """创建WindowManager实例"""
        with patch('window.tk.Tk'):
            from window import WindowManager
            callbacks = {}
            root = MagicMock()
            wm = WindowManager(root, callbacks)
            # 初始化必要的属性
            wm.project_vars = {}
            return wm
    
    def test_copy_single_interface_with_role(self, window_manager):
        """测试复制单个接口号（带角色标注）"""
        viewer = MagicMock()
        viewer.selection.return_value = ['item1']
        viewer.item.return_value = {'values': ['2016', 'INT-001(设计人员)', '☐']}
        viewer.__getitem__.return_value = ['项目号', '接口号', '是否已完成']
        
        root = MagicMock()
        window_manager.root = root
        
        # 调用复制方法
        window_manager._copy_selected_rows(viewer)
        
        # 验证剪贴板
        root.clipboard_clear.assert_called_once()
        root.clipboard_append.assert_called_once_with('INT-001')
    
    def test_copy_multiple_interfaces(self, window_manager):
        """测试复制多个接口号"""
        viewer = MagicMock()
        viewer.selection.return_value = ['item1', 'item2', 'item3']
        viewer.item.side_effect = [
            {'values': ['2016', 'INT-001(设计人员)', '☐']},
            {'values': ['2016', 'INT-002(2016接口工程师)', '☑']},
            {'values': ['1818', 'INT-003(设计人员、1818接口工程师)', '☐']}
        ]
        viewer.__getitem__.return_value = ['项目号', '接口号', '是否已完成']
        
        root = MagicMock()
        window_manager.root = root
        
        window_manager._copy_selected_rows(viewer)
        
        # 验证剪贴板内容（换行分隔）
        expected_text = 'INT-001\nINT-002\nINT-003'
        root.clipboard_append.assert_called_once_with(expected_text)
    
    def test_copy_interface_without_role(self, window_manager):
        """测试复制不带角色标注的接口号"""
        viewer = MagicMock()
        viewer.selection.return_value = ['item1']
        viewer.item.return_value = {'values': ['2016', 'INT-001', '☐']}
        viewer.__getitem__.return_value = ['项目号', '接口号', '是否已完成']
        
        root = MagicMock()
        window_manager.root = root
        
        window_manager._copy_selected_rows(viewer)
        
        # 应该直接复制接口号
        root.clipboard_append.assert_called_once_with('INT-001')
    
    def test_copy_without_project_column(self, window_manager):
        """测试没有项目号列时的复制"""
        viewer = MagicMock()
        viewer.selection.return_value = ['item1']
        viewer.item.return_value = {'values': ['INT-001(设计人员)', '☐']}
        viewer.__getitem__.return_value = ['接口号', '是否已完成']
        
        root = MagicMock()
        window_manager.root = root
        
        window_manager._copy_selected_rows(viewer)
        
        # 接口号在第一列(索引0)
        root.clipboard_append.assert_called_once_with('INT-001')
    
    def test_copy_empty_selection(self, window_manager):
        """测试没有选择时的复制"""
        viewer = MagicMock()
        viewer.selection.return_value = []
        
        root = MagicMock()
        window_manager.root = root
        
        window_manager._copy_selected_rows(viewer)
        
        # 不应该调用剪贴板
        root.clipboard_clear.assert_not_called()
        root.clipboard_append.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

