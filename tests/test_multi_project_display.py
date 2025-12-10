"""
多项目显示修复测试
测试 _exclude_pending_confirmation_rows 函数正确处理多项目数据
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd


class TestGetProjectSourceFileMap:
    """测试 _get_project_source_file_map 方法"""
    
    def test_get_project_source_file_map_basic(self):
        """测试基本的项目号到源文件映射"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 设置测试数据
            app.target_files2 = [
                ('/path/to/1818file.xlsx', '1818'),
                ('/path/to/2306file.xlsx', '2306'),
            ]
            
            result = app._get_project_source_file_map("内部需回复接口")
            
            assert result == {
                '1818': '/path/to/1818file.xlsx',
                '2306': '/path/to/2306file.xlsx'
            }
    
    def test_get_project_source_file_map_empty(self):
        """测试空target_files返回空字典"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.target_files2 = []
            
            result = app._get_project_source_file_map("内部需回复接口")
            
            assert result == {}
    
    def test_get_project_source_file_map_unknown_tab(self):
        """测试未知tab名称返回空字典"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            result = app._get_project_source_file_map("未知选项卡")
            
            assert result == {}


class TestExcludePendingConfirmationRowsMultiProject:
    """测试 _exclude_pending_confirmation_rows 对多项目的支持"""
    
    def test_multi_project_uses_correct_source_file(self):
        """测试多项目数据使用各自正确的源文件"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.user_roles = ['管理员']
            app.user_role = '管理员'
            
            # 创建包含两个项目的测试数据
            df = pd.DataFrame({
                '原始行号': [10, 20, 30],
                '项目号': ['1818', '1818', '2306'],
                '接口号': ['A-001', 'A-002', 'B-001'],
            })
            
            # 项目号到源文件的映射
            project_source_map = {
                '1818': '/path/to/1818file.xlsx',
                '2306': '/path/to/2306file.xlsx'
            }
            
            # Mock registry hooks
            with patch('registry.hooks.get_display_status') as mock_get_status:
                # 返回所有任务的状态（假设都是待完成）
                mock_get_status.return_value = {
                    'task_1818_1': '📌 待完成',
                    'task_1818_2': '📌 待完成',
                    'task_2306_1': '📌 待完成'
                }
                
                with patch('registry.util.make_task_id') as mock_make_id:
                    # 验证make_task_id被调用时使用了正确的源文件
                    call_args_list = []
                    def track_make_id(file_type, proj_id, interface_id, source_file, row_index):
                        call_args_list.append({
                            'file_type': file_type,
                            'project_id': proj_id,
                            'source_file': source_file
                        })
                        return f"task_{proj_id}_{len(call_args_list)}"
                    
                    mock_make_id.side_effect = track_make_id
                    
                    with patch('registry.util.extract_interface_id', return_value='TEST'):
                        with patch('registry.util.extract_project_id') as mock_extract_proj:
                            # 返回每行的项目号
                            mock_extract_proj.side_effect = ['1818', '1818', '2306']
                            
                            # 调用函数
                            result = app._exclude_pending_confirmation_rows(
                                df, 
                                '/path/to/default.xlsx',  # 默认源文件
                                2,  # file_type
                                None,  # project_id
                                project_source_map  # 项目号到源文件的映射
                            )
                            
                            # 验证每个项目使用了正确的源文件
                            assert len(call_args_list) >= 3
                            
                            # 1818项目应该使用1818的源文件
                            calls_1818 = [c for c in call_args_list if c['project_id'] == '1818']
                            for call in calls_1818:
                                assert call['source_file'] == '/path/to/1818file.xlsx'
                            
                            # 2306项目应该使用2306的源文件
                            calls_2306 = [c for c in call_args_list if c['project_id'] == '2306']
                            for call in calls_2306:
                                assert call['source_file'] == '/path/to/2306file.xlsx'
    
    def test_fallback_to_default_source_file(self):
        """测试当项目号不在映射中时，使用默认源文件"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.user_roles = ['管理员']
            
            df = pd.DataFrame({
                '原始行号': [10],
                '项目号': ['9999'],  # 不在映射中的项目号
                '接口号': ['A-001'],
            })
            
            project_source_map = {
                '1818': '/path/to/1818file.xlsx'
            }
            
            with patch('registry.hooks.get_display_status', return_value={}):
                with patch('registry.util.make_task_id') as mock_make_id:
                    source_files_used = []
                    def track_source(file_type, proj_id, interface_id, source_file, row_index):
                        source_files_used.append(source_file)
                        return 'task_id'
                    mock_make_id.side_effect = track_source
                    
                    with patch('registry.util.extract_interface_id', return_value='TEST'):
                        with patch('registry.util.extract_project_id', return_value='9999'):
                            result = app._exclude_pending_confirmation_rows(
                                df,
                                '/path/to/default.xlsx',
                                1,
                                None,
                                project_source_map
                            )
                            
                            # 应该使用默认源文件
                            if source_files_used:
                                assert source_files_used[0] == '/path/to/default.xlsx'
    
    def test_none_project_source_map(self):
        """测试project_source_map为None时的兼容性"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.user_roles = ['管理员']
            
            df = pd.DataFrame({
                '原始行号': [10],
                '项目号': ['1818'],
                '接口号': ['A-001'],
            })
            
            with patch('registry.hooks.get_display_status', return_value={}):
                with patch('registry.util.make_task_id') as mock_make_id:
                    source_files_used = []
                    def track_source(file_type, proj_id, interface_id, source_file, row_index):
                        source_files_used.append(source_file)
                        return 'task_id'
                    mock_make_id.side_effect = track_source
                    
                    with patch('registry.util.extract_interface_id', return_value='TEST'):
                        with patch('registry.util.extract_project_id', return_value='1818'):
                            # project_source_map为None（旧调用方式）
                            result = app._exclude_pending_confirmation_rows(
                                df,
                                '/path/to/source.xlsx',
                                1,
                                '1818',
                                None  # 不传映射
                            )
                            
                            # 应该使用传入的source_file
                            if source_files_used:
                                assert source_files_used[0] == '/path/to/source.xlsx'


class TestIntegrationMultiProjectDisplay:
    """集成测试：多项目显示"""
    
    def test_display_preserves_all_projects(self):
        """测试显示时保留所有项目的数据"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.user_roles = ['管理员']
            
            # 设置多项目的源文件
            app.target_files2 = [
                ('/path/to/1818file.xlsx', '1818'),
                ('/path/to/2306file.xlsx', '2306'),
            ]
            
            # 验证映射正确
            project_map = app._get_project_source_file_map("内部需回复接口")
            
            assert '1818' in project_map
            assert '2306' in project_map
            assert project_map['1818'] == '/path/to/1818file.xlsx'
            assert project_map['2306'] == '/path/to/2306file.xlsx'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

