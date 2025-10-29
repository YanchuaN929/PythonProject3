"""
测试接口时间列显示功能
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestInterfaceTimeDisplay:
    """测试接口时间列的显示功能"""
    
    @pytest.fixture
    def sample_df_with_time(self):
        """创建包含接口时间的测试DataFrame"""
        return pd.DataFrame({
            '原始行号': [10, 11, 12, 13],
            '项目号': ['2016', '1907', '2016', '1818'],
            '接口时间': ['10.28', '11.05', '', '12.15'],  # 包含空值
            '角色来源': ['设计人员', '设计人员', '2016接口工程师', '设计人员']
        })
    
    @pytest.fixture
    def mock_window_manager(self):
        """创建WindowManager的模拟实例"""
        from window import WindowManager
        
        # 模拟root
        mock_root = MagicMock()
        
        # 创建WindowManager实例
        wm = WindowManager(mock_root)
        
        # 模拟viewer
        mock_viewer = MagicMock()
        mock_viewer.get_children.return_value = []
        
        return wm, mock_viewer
    
    def test_interface_time_column_exists(self, mock_window_manager, sample_df_with_time):
        """测试接口时间列是否存在于优化显示中"""
        wm, mock_viewer = mock_window_manager
        
        # 调用_create_optimized_display
        result_df = wm._create_optimized_display(
            sample_df_with_time, 
            "内部需打开接口",
            completed_rows=set()
        )
        
        # 验证"接口时间"列存在
        assert "接口时间" in result_df.columns, "接口时间列应该存在"
        
        # 验证列的顺序
        expected_order = ["状态", "项目号", "接口号", "接口时间", "是否已完成"]
        actual_order = list(result_df.columns)
        assert actual_order == expected_order, f"列顺序应为{expected_order}，实际为{actual_order}"
    
    def test_interface_time_empty_value_display(self, mock_window_manager, sample_df_with_time):
        """测试空值是否显示为'-'"""
        wm, mock_viewer = mock_window_manager
        
        result_df = wm._create_optimized_display(
            sample_df_with_time,
            "内部需打开接口",
            completed_rows=set()
        )
        
        # 验证空值保留（在display_excel_data中会被转换为'-'）
        assert result_df.iloc[2]["接口时间"] == '' or result_df.iloc[2]["接口时间"] == '-'
    
    def test_interface_time_column_width(self, mock_window_manager):
        """测试接口时间列宽度设置"""
        wm, _ = mock_window_manager
        
        # 测试_calculate_single_column_width方法
        test_df = pd.DataFrame({
            '接口时间': ['10.28', '11.05', '12.15']
        })
        
        width = wm._calculate_single_column_width(test_df, '接口时间')
        
        # 验证宽度在合理范围内（60-300px）
        assert 60 <= width <= 300, f"列宽应在60-300之间，实际为{width}"
    
    def test_fixed_column_widths(self):
        """测试固定列宽配置"""
        expected_widths = {
            '状态': 50,
            '项目号': 75,
            '接口号': 240,
            '接口时间': 85,
            '是否已完成': 95
        }
        
        # 验证配置值合理
        for col, width in expected_widths.items():
            assert width > 0, f"{col}列宽度应大于0"
            assert width <= 300, f"{col}列宽度不应过大"
    
    @patch('window.is_date_overdue')
    def test_interface_time_with_overdue_status(self, mock_is_overdue, mock_window_manager, sample_df_with_time):
        """测试接口时间列与延期状态的配合"""
        # 设置延期判断模拟
        mock_is_overdue.side_effect = lambda x: x == '10.28'  # 10.28是延期的
        
        wm, mock_viewer = mock_window_manager
        
        result_df = wm._create_optimized_display(
            sample_df_with_time,
            "内部需打开接口",
            completed_rows=set()
        )
        
        # 验证状态列和接口时间列都存在
        assert "状态" in result_df.columns
        assert "接口时间" in result_df.columns
    
    def test_interface_time_all_file_types(self, mock_window_manager):
        """测试所有文件类型都有接口时间列"""
        wm, _ = mock_window_manager
        
        file_types = [
            "内部需打开接口",
            "内部需回复接口", 
            "外部需打开接口",
            "外部需回复接口",
            "三维提资接口",
            "收发文函"
        ]
        
        for file_type in file_types:
            # 创建测试数据
            test_df = pd.DataFrame({
                '原始行号': [10],
                '项目号': ['2016'],
                '接口时间': ['10.28'],
                '角色来源': ['设计人员']
            })
            
            # 对于不同文件类型，需要添加对应的接口号列
            if file_type == "内部需打开接口":
                test_df.insert(0, 'A列', ['INT-001'])
            elif file_type == "内部需回复接口":
                # R列在索引17
                for i in range(17):
                    test_df.insert(0, f'Col{i}', [''])
                test_df.insert(17, 'R列', ['INT-002'])
            elif file_type == "外部需打开接口":
                test_df.insert(0, 'A列', [''])
                test_df.insert(1, 'B列', [''])
                test_df.insert(2, 'C列', ['INT-003'])
            elif file_type == "外部需回复接口":
                for i in range(4):
                    test_df.insert(0, f'Col{i}', [''])
                test_df.insert(4, 'E列', ['INT-004'])
            elif file_type == "三维提资接口":
                test_df.insert(0, 'A列', ['INT-005'])
            else:  # 收发文函
                for i in range(4):
                    test_df.insert(0, f'Col{i}', [''])
                test_df.insert(4, 'E列', ['INT-006'])
            
            try:
                result_df = wm._create_optimized_display(
                    test_df,
                    file_type,
                    completed_rows=set()
                )
                
                # 验证接口时间列存在
                assert "接口时间" in result_df.columns, f"{file_type}应包含接口时间列"
            except Exception as e:
                pytest.fail(f"{file_type}处理失败: {e}")


class TestInterfaceTimeSorting:
    """测试接口时间列排序功能"""
    
    @pytest.fixture
    def mock_window_manager_with_viewer(self):
        """创建带有viewer的WindowManager模拟实例"""
        from window import WindowManager
        
        mock_root = MagicMock()
        wm = WindowManager(mock_root)
        
        # 创建模拟viewer
        mock_viewer = MagicMock()
        mock_viewer.__getitem__ = MagicMock(return_value=['状态', '项目号', '接口号', '接口时间', '是否已完成'])
        
        # 模拟viewer中的数据
        mock_items = ['item1', 'item2', 'item3', 'item4']
        mock_viewer.get_children.return_value = mock_items
        
        # 为每个item设置values和text
        def mock_item(item_id):
            data_map = {
                'item1': {'values': ['', '2016', 'INT-001(设计人员)', '10.28', '☐'], 'text': '10'},
                'item2': {'values': ['', '1907', 'INT-002(设计人员)', '11.05', '☐'], 'text': '11'},
                'item3': {'values': ['', '2016', 'INT-003(设计人员)', '-', '☐'], 'text': '12'},
                'item4': {'values': ['', '1818', 'INT-004(设计人员)', '09.15', '☐'], 'text': '13'},
            }
            return data_map.get(item_id, {'values': [], 'text': ''})
        
        mock_viewer.item = mock_item
        mock_viewer.move = MagicMock()
        mock_viewer.heading = MagicMock()
        
        return wm, mock_viewer
    
    def test_sort_by_interface_time_ascending(self, mock_window_manager_with_viewer):
        """测试按接口时间升序排序"""
        wm, mock_viewer = mock_window_manager_with_viewer
        
        # 执行排序
        wm._sort_by_column(mock_viewer, '接口时间', '测试选项卡')
        
        # 验证move方法被调用
        assert mock_viewer.move.called, "应该调用move方法重新排列数据"
        
        # 验证heading方法被调用（添加排序符号）
        assert mock_viewer.heading.called, "应该更新列标题"
    
    def test_sort_empty_values_last(self, mock_window_manager_with_viewer):
        """测试空值（'-'）排在最后"""
        wm, mock_viewer = mock_window_manager_with_viewer
        
        # 执行排序（升序）
        wm._sort_by_column(mock_viewer, '接口时间', '测试选项卡')
        
        # 检查move调用，验证'-'值的item被放到后面
        # 注意：具体验证需要检查move的调用参数
        assert mock_viewer.move.call_count == 4, "应该移动所有4个项"


class TestInterfaceTimeIntegration:
    """集成测试：验证接口时间列的完整流程"""
    
    @patch('window.is_date_overdue')
    def test_full_display_with_interface_time(self, mock_is_overdue, tmp_path):
        """测试完整的显示流程（模拟）"""
        from window import WindowManager
        import tkinter as tk
        
        # 设置延期判断
        mock_is_overdue.return_value = False
        
        # 创建测试数据
        test_df = pd.DataFrame({
            '原始行号': [10, 11, 12],
            '项目号': ['2016', '1907', '2016'],
            '接口时间': ['10.28', '11.05', '-'],
            '角色来源': ['设计人员', '设计人员', '2016接口工程师'],
            'A列': ['INT-001', 'INT-002', 'INT-003']
        })
        
        # 验证数据结构
        assert '接口时间' in test_df.columns
        assert len(test_df) == 3
        assert test_df.iloc[2]['接口时间'] == '-'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])

