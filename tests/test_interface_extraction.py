#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试接口号提取逻辑
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os


class TestInterfaceNumberExtraction:
    """测试接口号从DataFrame中提取"""
    
    def test_extract_interface_from_column_a(self):
        """测试从A列（索引0）提取接口号"""
        # 创建模拟DataFrame（A列包含接口号）
        data = {
            'Col0': ['INT-001', 'INT-002', 'INT-003'],  # A列
            'Col1': ['Data1', 'Data2', 'Data3'],
            'Col2': ['Data1', 'Data2', 'Data3'],
        }
        df = pd.DataFrame(data)
        
        # 模拟提取逻辑
        col_idx = 0  # A列
        interface_series = [
            (str(v).strip() if v is not None and str(v).strip() and str(v) != 'nan' else "")
            for v in df.iloc[:, col_idx].tolist()
        ]
        
        assert len(interface_series) == 3
        assert interface_series[0] == 'INT-001'
        assert interface_series[1] == 'INT-002'
        assert interface_series[2] == 'INT-003'
    
    def test_extract_interface_from_column_r(self):
        """测试从R列（索引17）提取接口号"""
        # 创建有18列的DataFrame
        columns = [f'Col{i}' for i in range(20)]
        data = [[f'val{i}' for i in range(17)] + ['INT-R001', 'val18', 'val19'] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        # 模拟提取逻辑
        col_idx = 17  # R列
        interface_series = [
            (str(v).strip() if v is not None and str(v).strip() and str(v) != 'nan' else "")
            for v in df.iloc[:, col_idx].tolist()
        ]
        
        assert len(interface_series) == 3
        assert all(v == 'INT-R001' for v in interface_series)
    
    def test_extract_interface_from_column_e(self):
        """测试从E列（索引4）提取接口号"""
        # 创建DataFrame
        columns = [f'Col{i}' for i in range(10)]
        data = [[f'val{i}' for i in range(4)] + ['INT-E001'] + [f'val{i}' for i in range(5, 10)] for _ in range(3)]
        df = pd.DataFrame(data, columns=columns)
        
        # 模拟提取逻辑
        col_idx = 4  # E列
        interface_series = [
            (str(v).strip() if v is not None and str(v).strip() and str(v) != 'nan' else "")
            for v in df.iloc[:, col_idx].tolist()
        ]
        
        assert len(interface_series) == 3
        assert all(v == 'INT-E001' for v in interface_series)
    
    def test_handle_empty_values(self):
        """测试处理空值"""
        data = {
            'Col0': ['INT-001', None, '', 'INT-004'],
            'Col1': ['Data1', 'Data2', 'Data3', 'Data4'],
        }
        df = pd.DataFrame(data)
        
        col_idx = 0
        interface_series = [
            (str(v).strip() if v is not None and str(v).strip() and str(v) != 'nan' else "")
            for v in df.iloc[:, col_idx].tolist()
        ]
        
        assert interface_series[0] == 'INT-001'
        assert interface_series[1] == ''  # None应该变成空字符串
        assert interface_series[2] == ''  # 空字符串保持空
        assert interface_series[3] == 'INT-004'
    
    def test_column_index_mapping(self):
        """测试列字母到索引的映射"""
        col_index_map = {
            "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5,
            "G": 6, "H": 7, "I": 8, "J": 9, "K": 10, "L": 11,
            "M": 12, "N": 13, "O": 14, "P": 15, "Q": 16, "R": 17
        }
        
        assert col_index_map["A"] == 0
        assert col_index_map["C"] == 2
        assert col_index_map["E"] == 4
        assert col_index_map["R"] == 17
    
    def test_interface_series_with_real_data_structure(self):
        """测试使用真实数据结构提取接口号"""
        # 模拟真实Excel数据（第一行是表头，后面是数据）
        df = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002', 'INT-003'],  # 实际可能在A列
            '专业': ['结构', '建筑', '暖通'],
            '科室': ['结构一室', '建筑室', '暖通室'],
        })
        
        # 通过索引获取第一列（无论列名是什么）
        col_idx = 0
        interface_series = [
            (str(v).strip() if v is not None and str(v).strip() and str(v) != 'nan' else "")
            for v in df.iloc[:, col_idx].tolist()
        ]
        
        assert interface_series == ['INT-001', 'INT-002', 'INT-003']


class TestWriteExportSummaryIntegration:
    """测试write_export_summary函数的集成"""
    
    def test_interface_ids_in_summary(self):
        """测试接口号是否包含在导出摘要中"""
        from main2 import write_export_summary
        from datetime import datetime
        
        # 创建测试数据（使用新的函数签名）
        df1 = pd.DataFrame({
            0: ['INT-A001', 'INT-A002'],  # A列（索引0）
        })
        df1['科室'] = ['结构一室', '结构二室']
        df1['接口时间'] = ['01.06', '01.08']
        
        results_multi1 = {'1818': df1}
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = write_export_summary(
                folder_path=tmpdir,
                current_datetime=datetime.now(),
                results_multi1=results_multi1
            )
            
            # 读取生成的文件
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证接口号存在
            assert '接口号' in content, "输出应该包含'接口号'标签"
            assert 'INT-A001' in content or 'INT-A002' in content, "输出应该包含具体的接口号"
    
    def test_multiple_interface_types(self):
        """测试多种接口类型的接口号提取"""
        from main2 import write_export_summary
        from datetime import datetime
        
        # 内部需打开接口（A列）
        df1 = pd.DataFrame([[f'Col{i}' for i in range(20)] for _ in range(2)])
        df1.iloc[0, 0] = 'INT-A001'
        df1.iloc[1, 0] = 'INT-A002'
        df1['科室'] = ['结构一室', '结构一室']
        df1['接口时间'] = ['01.06', '01.07']
        
        # 三维提资接口（A列）
        df2 = pd.DataFrame([[f'Col{i}' for i in range(20)] for _ in range(2)])
        df2.iloc[0, 0] = 'INT-3D001'
        df2.iloc[1, 0] = 'INT-3D002'
        df2['科室'] = ['结构二室', '结构二室']
        df2['接口时间'] = ['01.08', '01.09']
        
        # 外部需回复接口（E列）
        df3 = pd.DataFrame([[f'Col{i}' for i in range(20)] for _ in range(2)])
        df3.iloc[0, 4] = 'INT-E001'
        df3.iloc[1, 4] = 'INT-E002'
        df3['科室'] = ['建筑总图室', '建筑总图室']
        df3['接口时间'] = ['01.10', '01.11']
        
        # 使用新的函数签名
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = write_export_summary(
                folder_path=tmpdir,
                current_datetime=datetime.now(),
                results_multi1={'1818': df1},
                results_multi5={'1818': df2},
                results_multi4={'2016': df3}
            )
            
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证各种接口号都存在
            assert '接口号' in content
            # 至少应该包含一些接口号
            interface_count = content.count('INT-')
            assert interface_count > 0, f"应该包含接口号，但只找到{interface_count}个"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

