"""
测试项目号显示功能

验证：
1. 数据处理时项目号列被添加到DataFrame
2. GUI显示时项目号列在接口号列之前
3. 项目号和角色来源可以同时显示
"""

import pytest
import pandas as pd
from window import WindowManager
from unittest.mock import Mock


class TestProjectIdInDataFrame:
    """测试DataFrame中的项目号列"""
    
    def test_project_id_added_to_result(self):
        """测试项目号被添加到处理结果中"""
        # 创建模拟的处理结果
        result = pd.DataFrame({
            '原始行号': [2, 3, 4],
            '列A': ['INT-001', 'INT-002', 'INT-003'],
            '其他列': ['数据1', '数据2', '数据3']
        })
        
        # 添加项目号列（模拟base.py中的操作）
        project_id = "2016"
        result['项目号'] = project_id
        
        # 验证项目号列存在
        assert '项目号' in result.columns
        assert all(result['项目号'] == project_id)
        assert len(result) == 3


class TestProjectIdDisplay:
    """测试项目号在GUI中的显示"""
    
    @pytest.fixture
    def mock_root(self):
        """创建模拟的Tkinter root"""
        root = Mock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        return root
    
    @pytest.fixture
    def window_manager(self, mock_root):
        """创建WindowManager实例"""
        callbacks = {
            'on_select_path': Mock(),
            'on_refresh_files': Mock(),
            'on_start_processing': Mock(),
            'on_export_results': Mock(),
            'on_tab_changed': Mock()
        }
        return WindowManager(mock_root, callbacks)
    
    def test_display_with_project_id_only(self, window_manager):
        """测试只有项目号（无角色来源）的显示"""
        # 创建测试数据 - 注意列顺序：Excel列在前，添加的列在后
        df = pd.DataFrame({
            '列A': ['INT-001', 'INT-002', 'INT-003'],  # 索引0 - 内部需打开接口
            '列B': ['数据1', '数据2', '数据3'],
            '项目号': ['2016', '2016', '1818'],
            '原始行号': [2, 3, 4]
        })
        
        # 测试_create_optimized_display
        result = window_manager._create_optimized_display(df, "内部需打开接口")
        
        # 验证返回结果
        assert '项目号' in result.columns
        assert '接口号' in result.columns
        assert result.columns[0] == '项目号'  # 项目号在第一列
        assert result.columns[1] == '接口号'  # 接口号在第二列
        assert len(result) == 3
        assert list(result['项目号']) == ['2016', '2016', '1818']
        assert all(result['接口号'].notna())
    
    def test_display_with_project_id_and_role(self, window_manager):
        """测试同时有项目号和角色来源的显示"""
        # 创建测试数据 - 注意列顺序：先是Excel原始列，然后是添加的列
        df = pd.DataFrame({
            '列A': ['INT-001', 'INT-002', 'INT-003'],  # 索引0，接口号列
            '列B': ['数据1', '数据2', '数据3'],
            '角色来源': ['设计人员', '2016接口工程师', '设计人员、1818接口工程师'],
            '项目号': ['2016', '2016', '1818'],
            '原始行号': [2, 3, 4]
        })
        
        # 测试_create_optimized_display
        result = window_manager._create_optimized_display(df, "内部需打开接口")
        
        # 验证返回结果
        assert '项目号' in result.columns
        assert '接口号' in result.columns
        assert result.columns[0] == '项目号'  # 项目号在第一列
        assert result.columns[1] == '接口号'  # 接口号在第二列
        assert len(result) == 3
        
        # 验证接口号包含角色标注
        assert result.iloc[0]['接口号'] == 'INT-001(设计人员)'
        assert result.iloc[1]['接口号'] == 'INT-002(2016接口工程师)'
        assert result.iloc[2]['接口号'] == 'INT-003(设计人员、1818接口工程师)'
    
    def test_display_without_project_id(self, window_manager):
        """测试没有项目号列的情况（向后兼容性）"""
        # 创建测试数据（没有项目号列）
        df = pd.DataFrame({
            '列A': ['INT-001', 'INT-002', 'INT-003'],
            '列B': ['数据1', '数据2', '数据3'],
            '原始行号': [2, 3, 4]
        })
        
        # 测试_create_optimized_display
        result = window_manager._create_optimized_display(df, "内部需打开接口")
        
        # 验证返回结果 - 应该只有接口号列
        assert '项目号' not in result.columns
        assert '接口号' in result.columns
        assert len(result) == 3
    
    def test_display_different_file_types(self, window_manager):
        """测试不同文件类型的项目号显示"""
        # 创建测试数据 - 内部需回复接口（R列=索引17）
        df_file2 = pd.DataFrame({
            '项目号': ['2026', '2026'],
            **{f'列{i}': [f'数据{i}_1', f'数据{i}_2'] for i in range(20)},  # 创建20列
            '原始行号': [2, 3]
        })
        df_file2.iloc[:, 17] = ['INT-R-001', 'INT-R-002']  # 设置R列（索引17）
        
        result = window_manager._create_optimized_display(df_file2, "内部需回复接口")
        
        assert '项目号' in result.columns
        assert '接口号' in result.columns
        assert result.columns[0] == '项目号'
        assert all(result['项目号'] == '2026')
        
        # 创建测试数据 - 外部需打开接口（C列=索引2）
        df_file3 = pd.DataFrame({
            '项目号': ['1907', '1907'],
            '列A': ['A1', 'A2'],
            '列B': ['B1', 'B2'],
            '列C': ['INT-C-001', 'INT-C-002'],  # C列
            '原始行号': [2, 3]
        })
        
        result = window_manager._create_optimized_display(df_file3, "外部需打开接口")
        
        assert '项目号' in result.columns
        assert '接口号' in result.columns
        assert all(result['项目号'] == '1907')


class TestProjectIdColumnOrdering:
    """测试项目号列的顺序"""
    
    def test_project_id_before_interface_id(self):
        """测试项目号列在接口号列之前"""
        # 创建模拟的WindowManager
        root = Mock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        
        callbacks = {'on_select_path': Mock()}
        window_manager = WindowManager(root, callbacks)
        
        # 创建测试数据 - 注意列顺序
        df = pd.DataFrame({
            '列A': ['INT-001', 'INT-002', 'INT-003'],
            '列B': ['数据1', '数据2', '数据3'],
            '角色来源': ['设计人员', '设计人员', '2016接口工程师'],
            '项目号': ['2016', '2016', '2016'],
            '原始行号': [2, 3, 4]
        })
        
        # 获取显示数据
        result = window_manager._create_optimized_display(df, "内部需打开接口")
        
        # 验证列顺序
        columns = list(result.columns)
        assert columns.index('项目号') < columns.index('接口号'), "项目号应该在接口号之前"
        assert columns[0] == '项目号', "项目号应该是第一列"
        assert columns[1] == '接口号', "接口号应该是第二列"


class TestMultiProjectDisplay:
    """测试多项目混合显示"""
    
    def test_mixed_projects_display(self):
        """测试多个项目混合显示"""
        root = Mock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        
        callbacks = {'on_select_path': Mock()}
        window_manager = WindowManager(root, callbacks)
        
        # 创建包含多个项目的测试数据 - 注意列顺序
        df = pd.DataFrame({
            '列A': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005'],  # 索引0
            '列B': ['数据1', '数据2', '数据3', '数据4', '数据5'],
            '角色来源': ['设计人员', '2016接口工程师', '1818接口工程师', '设计人员', '2026接口工程师'],
            '项目号': ['2016', '2016', '1818', '2306', '2026'],
            '原始行号': [2, 3, 4, 5, 6]
        })
        
        # 获取显示数据
        result = window_manager._create_optimized_display(df, "内部需打开接口")
        
        # 验证所有项目号都正确显示
        assert len(result) == 5
        assert list(result['项目号']) == ['2016', '2016', '1818', '2306', '2026']
        
        # 验证接口号和角色标注都正确
        assert result.iloc[0]['接口号'] == 'INT-001(设计人员)'
        assert result.iloc[1]['接口号'] == 'INT-002(2016接口工程师)'
        assert result.iloc[2]['接口号'] == 'INT-003(1818接口工程师)'
        assert result.iloc[3]['接口号'] == 'INT-004(设计人员)'
        assert result.iloc[4]['接口号'] == 'INT-005(2026接口工程师)'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

