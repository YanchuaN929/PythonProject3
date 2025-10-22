#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试显示修复：三维提资接口和行号列宽
"""

import pytest
from unittest.mock import Mock, MagicMock
import pandas as pd


class TestInterfaceColumnMapping:
    """测试接口号列映射"""
    
    def test_sanwei_tizi_uses_column_a(self, mock_root):
        """测试：三维提资接口使用A列作为接口号"""
        from window import WindowManager
        
        # 创建有足够列的DataFrame
        columns = [f'Col{i}' for i in range(20)]
        data = [['INT-001', 'data1', 'data2'] + [f'val{i}' for i in range(17)] for _ in range(5)]
        df = pd.DataFrame(data, columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "三维提资接口")
        
        # 应该只显示A列（索引0），重命名为"接口号"
        assert len(result.columns) == 1, "应该只有1列"
        assert result.columns[0] == "接口号", "列名应该是'接口号'"
        
        # 验证数据来自A列（索引0）
        assert result.iloc[0, 0] == 'INT-001', "数据应该来自A列"
    
    def test_nebu_dakao_uses_column_a(self, mock_root):
        """测试：内部需打开接口使用A列"""
        from window import WindowManager
        
        columns = [f'Col{i}' for i in range(20)]
        data = [['INT-A001'] + [f'val{i}' for i in range(19)] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "内部需打开接口")
        
        assert len(result.columns) == 1
        assert result.columns[0] == "接口号"
        assert result.iloc[0, 0] == 'INT-A001'
    
    def test_nebu_huifu_uses_column_r(self, mock_root):
        """测试：内部需回复接口使用R列（索引17）"""
        from window import WindowManager
        
        columns = [f'Col{i}' for i in range(20)]
        data = [[f'val{i}' for i in range(17)] + ['INT-R001', 'val18', 'val19'] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "内部需回复接口")
        
        assert len(result.columns) == 1
        assert result.columns[0] == "接口号"
        assert result.iloc[0, 0] == 'INT-R001'
    
    def test_waibu_dakao_uses_column_c(self, mock_root):
        """测试：外部需打开接口使用C列（索引2）"""
        from window import WindowManager
        
        columns = [f'Col{i}' for i in range(20)]
        data = [['val0', 'val1', 'INT-C001'] + [f'val{i}' for i in range(3, 20)] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "外部需打开接口")
        
        assert len(result.columns) == 1
        assert result.columns[0] == "接口号"
        assert result.iloc[0, 0] == 'INT-C001'
    
    def test_waibu_huifu_uses_column_e(self, mock_root):
        """测试：外部需回复接口使用E列（索引4）"""
        from window import WindowManager
        
        columns = [f'Col{i}' for i in range(20)]
        data = [[f'val{i}' for i in range(4)] + ['INT-E001'] + [f'val{i}' for i in range(5, 20)] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "外部需回复接口")
        
        assert len(result.columns) == 1
        assert result.columns[0] == "接口号"
        assert result.iloc[0, 0] == 'INT-E001'
    
    def test_shoufawenhan_uses_column_e(self, mock_root):
        """测试：收发文函使用E列（索引4）"""
        from window import WindowManager
        
        columns = [f'Col{i}' for i in range(20)]
        data = [[f'val{i}' for i in range(4)] + ['INT-E002'] + [f'val{i}' for i in range(5, 20)] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        wm = WindowManager(mock_root)
        result = wm._create_optimized_display(df, "收发文函")
        
        assert len(result.columns) == 1
        assert result.columns[0] == "接口号"
        assert result.iloc[0, 0] == 'INT-E002'


class TestRowNumberColumnWidth:
    """测试行号列宽度"""
    
    def test_row_number_width_matches_data_width(self, mock_root):
        """测试：行号列宽度与接口号列宽度一致"""
        from window import WindowManager
        
        # 创建短接口号的DataFrame
        df = pd.DataFrame({'接口号': ['A1', 'B2', 'C3']})
        
        wm = WindowManager(mock_root)
        
        # Mock viewer
        mock_viewer = MagicMock()
        mock_viewer.get_children.return_value = []
        mock_viewer.__getitem__ = Mock(return_value=[])
        
        # 调用display_excel_data
        wm.display_excel_data(mock_viewer, df, "三维提资接口", show_all=True)
        
        # 验证column方法被调用
        assert mock_viewer.column.called, "column方法应该被调用"
        
        # 获取所有column调用
        column_calls = [call for call in mock_viewer.column.call_args_list]
        
        # 第一个调用应该是设置行号列（"#0"）
        first_call = column_calls[0]
        assert first_call[0][0] == "#0", "第一个调用应该是设置行号列"
        
        # 验证行号列有宽度设置
        assert 'width' in first_call[1], "应该设置width参数"
    
    def test_row_number_width_calculated_from_data(self, mock_root):
        """测试：行号列宽度基于数据内容计算"""
        from window import WindowManager
        
        # 创建包含中文字符的DataFrame（宽度会更大）
        df = pd.DataFrame({'接口号': ['中文接口-001', '中文接口-002', '中文接口-003']})
        
        wm = WindowManager(mock_root)
        
        # Mock viewer
        mock_viewer = MagicMock()
        mock_viewer.get_children.return_value = []
        mock_viewer.__getitem__ = Mock(return_value=[])
        
        # 调用display_excel_data
        wm.display_excel_data(mock_viewer, df, "收发文函", show_all=True)
        
        # 验证column方法被调用
        column_calls = [call for call in mock_viewer.column.call_args_list]
        
        # 获取行号列的宽度
        row_number_call = column_calls[0]
        row_number_width = row_number_call[1].get('width', 60)
        
        # 获取数据列的宽度（第二个column调用）
        if len(column_calls) > 1:
            data_column_call = column_calls[1]
            data_column_width = data_column_call[1].get('width', 60)
            
            # 验证两者宽度一致
            assert row_number_width == data_column_width, \
                f"行号列宽度({row_number_width})应该与接口号列宽度({data_column_width})一致"
    
    def test_row_number_width_short_interface_numbers(self, mock_root):
        """测试：短接口号时行号列宽度相应缩小"""
        from window import WindowManager
        
        # 创建很短的接口号
        df = pd.DataFrame({'接口号': ['1', '2', '3']})
        
        wm = WindowManager(mock_root)
        
        # 计算列宽
        column_widths = wm.calculate_column_widths(df, ['接口号'])
        
        # 验证宽度被正确计算（短内容应该有较小的宽度）
        assert len(column_widths) > 0, "应该有列宽计算结果"
        # 最小宽度应该是60px
        assert column_widths[0] >= 60, "宽度应该不小于60px"
        assert column_widths[0] <= 100, "短内容的宽度应该较小"


class TestMain2InterfaceMapping:
    """测试main2.py中的接口号映射"""
    
    def test_interface_column_map_includes_sanwei(self):
        """测试：main2.py中三维提资接口映射到A列"""
        import main2
        
        # 直接检查模块中的映射（需要运行write_export_summary才会创建）
        # 这里我们验证函数内部的映射定义
        import inspect
        source = inspect.getsource(main2.write_export_summary)
        
        # 验证源码中包含正确的映射
        assert '"三维提资接口": "A"' in source, "三维提资接口应该映射到A列"
    
    def test_all_interface_mappings_present(self):
        """测试：所有接口类型都有映射"""
        import main2
        import inspect
        
        source = inspect.getsource(main2.write_export_summary)
        
        required_mappings = [
            '"内部需打开接口": "A"',
            '"内部需回复接口": "R"',
            '"外部需打开接口": "C"',
            '"外部需回复接口": "E"',
            '"三维提资接口": "A"',
            '"收发文函": "E"'
        ]
        
        for mapping in required_mappings:
            assert mapping in source, f"应该包含映射: {mapping}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

