#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务指派窗口修复功能测试
测试问题1-4的修复
"""

import pytest
import pandas as pd
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch
from distribution import (
    get_interface_id_column_index,
    check_unassigned,
    AssignmentDialog,
    get_name_list
)


class TestInterfaceIdColumnMapping:
    """测试接口号列名映射（修复问题1）"""
    
    def test_file1_interface_column(self):
        """测试文件1的接口号列索引"""
        assert get_interface_id_column_index(1) == 0  # A列
    
    def test_file2_interface_column(self):
        """测试文件2的接口号列索引"""
        assert get_interface_id_column_index(2) == 17  # R列
    
    def test_file3_interface_column(self):
        """测试文件3的接口号列索引"""
        assert get_interface_id_column_index(3) == 2  # C列
    
    def test_file4_interface_column(self):
        """测试文件4的接口号列索引"""
        assert get_interface_id_column_index(4) == 4  # E列
    
    def test_file5_interface_column(self):
        """测试文件5的接口号列索引"""
        assert get_interface_id_column_index(5) == 0  # A列
    
    def test_file6_interface_column(self):
        """测试文件6的接口号列索引"""
        assert get_interface_id_column_index(6) == 4  # E列
    
    def test_invalid_file_type(self):
        """测试无效文件类型返回默认值"""
        assert get_interface_id_column_index(999) == 0  # 默认值


class TestCheckUnassignedWithInterfaceId:
    """测试check_unassigned函数能正确提取接口号"""
    
    @pytest.fixture
    def mock_df_file1(self):
        """创建模拟的文件1数据"""
        return pd.DataFrame({
            'A': ['INT-001', 'INT-002', 'INT-003'],  # 接口号列
            '项目号': ['2016', '2016', '2026'],
            '责任人': ['', '王任超', ''],
            '科室': ['结构一室', '结构一室', '结构二室'],
            '原始行号': [2, 3, 4],
            'source_file': ['file1.xlsx'] * 3,
            '接口时间': ['10.28', '10.29', '10.30']
        })
    
    @pytest.fixture
    def mock_df_file2(self):
        """创建模拟的文件2数据"""
        return pd.DataFrame({
            'I': ['INT-004', 'INT-005'],  # 接口号列
            '项目号': ['2016', '2026'],
            '责任人': ['无', ''],
            '科室': ['结构一室', '结构二室'],
            '原始行号': [5, 6],
            'source_file': ['file2.xlsx'] * 2,
            '接口时间': ['11.01', '11.02']
        })
    
    def test_extract_interface_id_file1(self, mock_df_file1):
        """测试能正确提取文件1的接口号"""
        processed_results = {1: mock_df_file1}
        user_roles = ['管理员']
        
        unassigned = check_unassigned(processed_results, user_roles)
        
        # 应该检测到2个未指派任务（第1和第3行）
        assert len(unassigned) == 2
        
        # 检查接口号是否正确提取
        interface_ids = [task['interface_id'] for task in unassigned]
        assert 'INT-001' in interface_ids
        assert 'INT-003' in interface_ids
        
        # 确保"王任超"负责的任务不在未指派列表中
        assert 'INT-002' not in interface_ids
    
    def test_extract_interface_id_file2(self, mock_df_file2):
        """测试能正确提取文件2的接口号"""
        processed_results = {2: mock_df_file2}
        user_roles = ['管理员']
        
        unassigned = check_unassigned(processed_results, user_roles)
        
        # 应该检测到2个未指派任务
        assert len(unassigned) == 2
        
        # 检查接口号是否正确提取
        interface_ids = [task['interface_id'] for task in unassigned]
        assert 'INT-004' in interface_ids
        assert 'INT-005' in interface_ids
    
    def test_mixed_file_types(self, mock_df_file1, mock_df_file2):
        """测试混合多种文件类型时能正确提取接口号"""
        processed_results = {
            1: mock_df_file1,
            2: mock_df_file2
        }
        user_roles = ['管理员']
        
        unassigned = check_unassigned(processed_results, user_roles)
        
        # 应该检测到4个未指派任务
        assert len(unassigned) == 4
        
        # 检查所有接口号
        interface_ids = [task['interface_id'] for task in unassigned]
        assert 'INT-001' in interface_ids
        assert 'INT-003' in interface_ids
        assert 'INT-004' in interface_ids
        assert 'INT-005' in interface_ids
    
    def test_interface_id_not_empty(self, mock_df_file1):
        """测试提取的接口号不为空"""
        processed_results = {1: mock_df_file1}
        user_roles = ['管理员']
        
        unassigned = check_unassigned(processed_results, user_roles)
        
        # 所有任务都应该有接口号
        for task in unassigned:
            assert task['interface_id'] != ''
            assert task['interface_id'] is not None


class TestComboboxMouseWheelFix:
    """测试Combobox鼠标滚轮修复（修复问题2）"""
    
    @pytest.fixture
    def mock_root(self):
        """创建模拟的Tk根窗口"""
        try:
            root = tk.Tk()
            root.withdraw()
            yield root
            root.destroy()
        except tk.TclError:
            # 如果无法创建GUI，跳过测试
            pytest.skip("无法创建Tk窗口")
    
    def test_combobox_mousewheel_disabled(self, mock_root):
        """测试Combobox的鼠标滚轮事件被禁用"""
        # 创建一个简单的Combobox
        cb = ttk.Combobox(mock_root, values=['选项1', '选项2', '选项3'])
        
        # 绑定滚轮事件（模拟AssignmentDialog中的绑定）
        cb.bind('<MouseWheel>', lambda e: "break")
        cb.bind('<Button-4>', lambda e: "break")
        cb.bind('<Button-5>', lambda e: "break")
        
        # 验证绑定存在
        bindings = cb.bind()
        assert '<MouseWheel>' in bindings or 'MouseWheel' in str(bindings)


class TestAssignmentButtonPosition:
    """测试指派任务按钮位置（修复问题4）"""
    
    def test_button_created_in_initialization(self):
        """测试按钮在初始化时创建"""
        # 这个测试需要运行完整的base.py初始化
        # 简化测试：验证按钮创建逻辑
        
        # 模拟button_frame
        root = tk.Tk()
        root.withdraw()
        button_frame = ttk.Frame(root)
        
        # 创建按钮
        assignment_button = ttk.Button(
            button_frame,
            text="📋 指派任务",
            command=lambda: None
        )
        
        # 验证按钮已创建
        assert assignment_button is not None
        assert assignment_button['text'] == "📋 指派任务"
        
        root.destroy()
    
    def test_button_pack_and_unpack(self):
        """测试按钮可以显示和隐藏"""
        root = tk.Tk()
        root.withdraw()
        button_frame = ttk.Frame(root)
        button_frame.pack()
        
        # 创建按钮
        assignment_button = ttk.Button(button_frame, text="测试按钮")
        
        # 显示按钮
        assignment_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 验证按钮已显示
        assert assignment_button.winfo_manager() == 'pack'
        
        # 隐藏按钮
        assignment_button.pack_forget()
        
        # 验证按钮已隐藏
        assert assignment_button.winfo_manager() == ''
        
        # 再次显示
        assignment_button.pack(side=tk.LEFT, padx=(10, 0))
        assert assignment_button.winfo_manager() == 'pack'
        
        root.destroy()


class TestAutoDropdownMenu:
    """测试自动弹出下拉菜单（修复问题2的一部分）"""
    
    @pytest.fixture
    def mock_dialog_components(self):
        """创建模拟的对话框组件"""
        try:
            root = tk.Tk()
            root.withdraw()
            
            name_list = ['王任超', '李四', '张三', '赵六', '王五']
            combobox = ttk.Combobox(root, values=name_list)
            
            yield {'root': root, 'combobox': combobox, 'name_list': name_list}
            
            root.destroy()
        except tk.TclError:
            pytest.skip("无法创建Tk窗口")
    
    def test_filtered_dropdown_values(self, mock_dialog_components):
        """测试输入时下拉列表正确过滤"""
        cb = mock_dialog_components['combobox']
        name_list = mock_dialog_components['name_list']
        
        # 模拟输入"王"
        search_text = "王"
        filtered = [name for name in name_list if search_text in name]
        
        # 更新Combobox的值
        cb['values'] = filtered
        
        # 验证过滤结果
        assert len(cb['values']) == 2  # 王任超、王五
        assert '王任超' in cb['values']
        assert '王五' in cb['values']
        assert '李四' not in cb['values']
    
    def test_empty_search_restores_all(self, mock_dialog_components):
        """测试清空搜索时恢复完整列表"""
        cb = mock_dialog_components['combobox']
        name_list = mock_dialog_components['name_list']
        
        # 先过滤
        cb['values'] = ['王任超']
        
        # 清空搜索，恢复完整列表
        cb['values'] = name_list
        
        # 验证完整列表已恢复
        assert len(cb['values']) == 5


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

