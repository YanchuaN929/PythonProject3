"""
项目号筛选功能测试
测试项目号筛选UI和业务逻辑
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk


class TestProjectFilterVariables:
    """测试项目号筛选变量初始化"""
    
    def test_project_vars_initialization(self):
        """测试项目号变量默认全选"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 验证6个项目号变量都被初始化
            assert hasattr(app, 'project_1818_var')
            assert hasattr(app, 'project_1907_var')
            assert hasattr(app, 'project_1916_var')
            assert hasattr(app, 'project_2016_var')
            assert hasattr(app, 'project_2026_var')
            assert hasattr(app, 'project_2306_var')
            
            # 验证默认都是选中状态
            assert app.project_1818_var.get() == True
            assert app.project_1907_var.get() == True
            assert app.project_1916_var.get() == True
            assert app.project_2016_var.get() == True
            assert app.project_2026_var.get() == True
            assert app.project_2306_var.get() == True


class TestGetEnabledProjects:
    """测试get_enabled_projects方法"""
    
    def test_all_projects_enabled(self):
        """测试全选情况"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            enabled = app.get_enabled_projects()
            
            assert len(enabled) == 6
            assert '1818' in enabled
            assert '1907' in enabled
            assert '1916' in enabled
            assert '2016' in enabled
            assert '2026' in enabled
            assert '2306' in enabled
    
    def test_partial_projects_enabled(self):
        """测试部分选择情况"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 取消勾选部分项目
            app.project_1907_var.set(False)
            app.project_2016_var.set(False)
            app.project_2306_var.set(False)
            
            enabled = app.get_enabled_projects()
            
            assert len(enabled) == 3
            assert '1818' in enabled
            assert '1916' in enabled
            assert '2026' in enabled
            assert '1907' not in enabled
            assert '2016' not in enabled
            assert '2306' not in enabled
    
    def test_no_projects_enabled(self):
        """测试全不选情况"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 取消勾选所有项目
            app.project_1818_var.set(False)
            app.project_1907_var.set(False)
            app.project_1916_var.set(False)
            app.project_2016_var.set(False)
            app.project_2026_var.set(False)
            app.project_2306_var.set(False)
            
            enabled = app.get_enabled_projects()
            
            assert len(enabled) == 0


class TestFilterFilesByProject:
    """测试_filter_files_by_project方法"""
    
    def test_filter_all_enabled(self):
        """测试全选时不过滤"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            file_list = [
                ('/path/file1.xlsx', '1818'),
                ('/path/file2.xlsx', '1907'),
                ('/path/file3.xlsx', '2016'),
            ]
            enabled_projects = ['1818', '1907', '2016']
            
            filtered, ignored = app._filter_files_by_project(file_list, enabled_projects, "测试文件")
            
            assert len(filtered) == 3
            assert len(ignored) == 0
            assert filtered == file_list
    
    def test_filter_partial_enabled(self):
        """测试部分项目勾选时的过滤"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            file_list = [
                ('/path/file1.xlsx', '1818'),
                ('/path/file2.xlsx', '1907'),
                ('/path/file3.xlsx', '2016'),
                ('/path/file4.xlsx', '1818'),
            ]
            enabled_projects = ['1818', '2016']  # 只勾选1818和2016
            
            filtered, ignored = app._filter_files_by_project(file_list, enabled_projects, "测试文件")
            
            # 验证过滤结果
            assert len(filtered) == 3
            assert len(ignored) == 1
            
            # 验证过滤后的文件
            assert ('/path/file1.xlsx', '1818') in filtered
            assert ('/path/file3.xlsx', '2016') in filtered
            assert ('/path/file4.xlsx', '1818') in filtered
            
            # 验证被忽略的文件
            assert len(ignored) == 1
            assert ignored[0][0] == '/path/file2.xlsx'
            assert ignored[0][1] == '1907'
            assert ignored[0][2] == "测试文件"
    
    def test_filter_none_enabled(self):
        """测试全不选时全部过滤"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            file_list = [
                ('/path/file1.xlsx', '1818'),
                ('/path/file2.xlsx', '1907'),
                ('/path/file3.xlsx', '2016'),
            ]
            enabled_projects = []  # 全不选
            
            filtered, ignored = app._filter_files_by_project(file_list, enabled_projects, "测试文件")
            
            assert len(filtered) == 0
            assert len(ignored) == 3
    
    def test_filter_empty_list(self):
        """测试空文件列表"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            file_list = []
            enabled_projects = ['1818', '1907']
            
            filtered, ignored = app._filter_files_by_project(file_list, enabled_projects, "测试文件")
            
            assert len(filtered) == 0
            assert len(ignored) == 0


class TestProjectFilterIntegration:
    """测试项目号筛选的集成功能"""
    
    def test_project_vars_passed_to_window_manager(self):
        """测试项目号变量被正确传递给WindowManager"""
        with patch('base.WindowManager') as MockWindowManager:
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 验证WindowManager.setup被调用，且传入了project_vars
            MockWindowManager.return_value.setup.assert_called_once()
            call_args = MockWindowManager.return_value.setup.call_args
            
            # 检查project_vars参数
            assert len(call_args[0]) == 3  # config_data, process_vars, project_vars
            project_vars = call_args[0][2]
            
            assert '1818' in project_vars
            assert '1907' in project_vars
            assert '1916' in project_vars
            assert '2016' in project_vars
            assert '2026' in project_vars
            assert '2306' in project_vars
    
    def test_ignored_files_stored(self):
        """测试被忽略的文件被正确记录"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 模拟ignored_files的初始化
            app.ignored_files = []
            
            file_list = [
                ('/path/file1.xlsx', '1818'),
                ('/path/file2.xlsx', '1907'),
            ]
            enabled_projects = ['1818']  # 只勾选1818
            
            filtered, ignored = app._filter_files_by_project(file_list, enabled_projects, "待处理文件1")
            app.ignored_files.extend(ignored)
            
            # 验证ignored_files被正确记录
            assert len(app.ignored_files) == 1
            assert app.ignored_files[0][0] == '/path/file2.xlsx'
            assert app.ignored_files[0][1] == '1907'
            assert app.ignored_files[0][2] == "待处理文件1"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

