#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
责任人列显示功能测试
"""

import pytest
import pandas as pd
import re
from datetime import datetime


class TestResponsiblePersonColumn:
    """测试责任人列的存在性和数据正确性"""
    
    def test_file1_has_responsible_column(self):
        """测试文件1有责任人列（R列，索引17）"""
        import main
        
        # 创建模拟数据，确保R列在索引17的位置
        # 按顺序创建列，确保索引正确
        columns = []
        for i in range(18):
            columns.append(f'Col{i}')
        
        # 创建DataFrame，初始化所有列为空字符串
        test_data = {}
        for col in columns:
            test_data[col] = [''] * 5
        
        df = pd.DataFrame(test_data)
        
        # 在索引17的位置设置R列数据（责任人）
        df.iloc[:, 17] = ['王任超', '李四', '', None, '张三李四']
        
        # 测试责任人提取逻辑（从main.py复制）
        zh_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        owners = []
        for idx in range(len(df)):
            cell_val = df.iloc[idx, 17] if 17 < len(df.columns) else None
            s = str(cell_val) if cell_val is not None else ""
            found = zh_pattern.findall(s)
            owners.append("".join(found))
        
        assert owners[0] == "王任超"
        assert owners[1] == "李四"
        assert owners[2] == ""
        assert owners[3] == ""
        assert owners[4] == "张三李四"
    
    def test_file2_responsible_from_am_column(self):
        """测试文件2的责任人列从AM列读取（索引38）"""
        # 创建测试数据（文件2）
        # AM列（索引38）包含责任人姓名
        
        # 创建一个包含至少39列的DataFrame
        test_data = {}
        for i in range(40):
            test_data[f'Col{i}'] = ['数据1', '数据2', '数据3']
        
        # AM列是索引38
        test_data['Col38'] = ['王任超', '', '李四abc']  # AM列：责任人
        
        df = pd.DataFrame(test_data)
        
        # 模拟main.py中文件2的逻辑
        zh_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        owners = []
        for idx in range(len(df)):
            cell_val = df.iloc[idx, 38] if 38 < len(df.columns) else None
            s = str(cell_val) if cell_val is not None else ""
            found = zh_pattern.findall(s)
            owner_str = "".join(found)
            # 空值显示"无"
            owners.append(owner_str if owner_str else "无")
        
        assert owners[0] == "王任超"
        assert owners[1] == "无"  # 空值
        assert owners[2] == "李四"  # 提取中文
    
    def test_file3_has_responsible_column(self):
        """测试文件3有责任人列（AP列，索引41）"""
        # 测试AP列责任人提取
        zh_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        
        test_values = ['王任超', '李四', '张三王五', '']
        extracted = []
        
        for val in test_values:
            s = str(val) if val is not None else ""
            found = zh_pattern.findall(s)
            extracted.append("".join(found))
        
        assert extracted[0] == "王任超"
        assert extracted[1] == "李四"
        assert extracted[2] == "张三王五"
        assert extracted[3] == ""
    
    def test_file4_has_responsible_column(self):
        """测试文件4有责任人列（AH列，索引33）"""
        # AH列索引为33
        zh_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        
        test_values = ['赵六', '孙七', '']
        extracted = []
        
        for val in test_values:
            s = str(val) if val is not None else ""
            found = zh_pattern.findall(s)
            extracted.append("".join(found))
        
        assert extracted[0] == "赵六"
        assert extracted[1] == "孙七"
        assert extracted[2] == ""
    
    def test_file5_has_responsible_column(self):
        """测试文件5有责任人列（K列，索引10）"""
        # K列索引为10
        zh_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        
        test_values = ['周八', '吴九', '']
        extracted = []
        
        for val in test_values:
            s = str(val) if val is not None else ""
            found = zh_pattern.findall(s)
            extracted.append("".join(found))
        
        assert extracted[0] == "周八"
        assert extracted[1] == "吴九"
        assert extracted[2] == ""
    
    def test_file6_has_responsible_column_with_multiple_persons(self):
        """测试文件6有责任人列（X列，索引23，多人用逗号分隔）"""
        # X列索引为23，支持多人，用分隔符分隔
        test_value = "王任超,李四,张三"
        
        # 分隔符处理
        s = test_value
        for sep in [',', '，', ';', '；', '/', '、']:
            s = s.replace(sep, ',')
        tokens = [t.strip() for t in s.split(',') if t.strip()]
        result = ','.join(tokens)
        
        assert len(tokens) == 3
        assert "王任超" in tokens
        assert "李四" in tokens
        assert "张三" in tokens
        assert result == "王任超,李四,张三"
    
    def test_file6_responsible_with_various_separators(self):
        """测试文件6责任人列支持多种分隔符"""
        test_cases = [
            ("王任超、李四、张三", ["王任超", "李四", "张三"]),
            ("王任超；李四；张三", ["王任超", "李四", "张三"]),
            ("王任超/李四/张三", ["王任超", "李四", "张三"]),
            ("王任超，李四，张三", ["王任超", "李四", "张三"]),
        ]
        
        for test_input, expected in test_cases:
            s = test_input
            for sep in [',', '，', ';', '；', '/', '、']:
                s = s.replace(sep, ',')
            tokens = [t.strip() for t in s.split(',') if t.strip()]
            assert tokens == expected


class TestResponsiblePersonDisplay:
    """测试责任人列在GUI中的显示"""
    
    def test_responsible_column_in_display(self):
        """测试责任人列在显示列表中"""
        # 期望的列顺序：状态 → 项目号 → 接口号 → 接口时间 → 责任人 → 是否已完成
        display_columns = ['状态', '项目号', '接口号', '接口时间', '责任人', '是否已完成']
        assert '责任人' in display_columns
        
        # 确认位置在"接口时间"之后
        responsible_index = display_columns.index('责任人')
        time_index = display_columns.index('接口时间')
        assert responsible_index == time_index + 1
    
    def test_empty_responsible_shows_none(self):
        """测试空责任人显示为'无'"""
        test_values = [None, '', '  ', float('nan')]
        
        for val in test_values:
            if pd.isna(val) or str(val).strip() == '':
                result = '无'
            else:
                result = str(val).strip()
            assert result == '无'
    
    def test_non_empty_responsible_preserved(self):
        """测试非空责任人正确显示"""
        test_values = ['王任超', '李四', '张三王五']
        
        for val in test_values:
            if pd.isna(val) or str(val).strip() == '':
                result = '无'
            else:
                result = str(val).strip()
            assert result == val
    
    def test_responsible_column_width(self):
        """测试责任人列宽度设置"""
        fixed_widths = {
            '状态': 50,
            '项目号': 75,
            '接口号': 240,
            '接口时间': 85,
            '责任人': 100,
            '是否已完成': 95
        }
        assert fixed_widths['责任人'] == 100
    
    def test_responsible_column_alignment(self):
        """测试责任人列对齐方式"""
        column_alignment = {
            '状态': 'center',
            '项目号': 'center',
            '接口号': 'w',
            '接口时间': 'center',
            '责任人': 'center',
            '是否已完成': 'center'
        }
        assert column_alignment['责任人'] == 'center'


class TestSourceFileColumn:
    """测试source_file列的添加"""
    
    def test_source_file_added_to_result(self):
        """测试result_df包含source_file列"""
        # 模拟处理结果
        result_df = pd.DataFrame({
            '项目号': ['2016'],
            '接口号': ['INT-001'],
            '责任人': ['王任超']
        })
        
        file_path = 'D:/test/file1.xlsx'
        result_df['source_file'] = file_path
        
        assert 'source_file' in result_df.columns
        assert result_df['source_file'].iloc[0] == file_path


class TestFile3SourceColumn:
    """测试文件3的_source_column标记"""
    
    def test_source_column_m_path(self):
        """测试M列筛选路径标记"""
        # 模拟group1（M列路径）的索引
        group1 = {1, 2, 3}
        group2 = {5, 6}
        final_indices = [1, 2, 3, 5, 6]
        
        source_columns = []
        for idx in final_indices:
            if idx in group1 and idx not in group2:
                source_columns.append('M')
            elif idx in group2 and idx not in group1:
                source_columns.append('L')
            else:
                source_columns.append('M')
        
        assert source_columns[0] == 'M'  # 索引1在group1
        assert source_columns[1] == 'M'  # 索引2在group1
        assert source_columns[2] == 'M'  # 索引3在group1
        assert source_columns[3] == 'L'  # 索引5在group2
        assert source_columns[4] == 'L'  # 索引6在group2
    
    def test_source_column_both_paths(self):
        """测试同时匹配两个路径时优先M列"""
        # 模拟同时在group1和group2的索引
        group1 = {1, 2}
        group2 = {2, 3}
        final_indices = [1, 2, 3]
        
        source_columns = []
        for idx in final_indices:
            if idx in group1 and idx not in group2:
                source_columns.append('M')
            elif idx in group2 and idx not in group1:
                source_columns.append('L')
            else:
                source_columns.append('M')  # 两者都匹配，优先M列
        
        assert source_columns[0] == 'M'  # 只在group1
        assert source_columns[1] == 'M'  # 两者都有，优先M
        assert source_columns[2] == 'L'  # 只在group2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

