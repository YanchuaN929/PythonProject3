# -*- coding: utf-8 -*-
"""
测试主显示窗口是否显示角色筛选后的数据

测试场景：
1. 设计人员 - 只看到责任人是自己的数据
2. 接口工程师 - 看到对应项目的所有数据
3. 一室主任 - 看到对应科室的数据
4. 多角色 - 看到合并后的数据
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestDisplayFilteredResults:
    """测试主显示窗口显示角色筛选后的数据"""
    
    def test_designer_sees_only_own_data(self):
        """测试设计人员只看到自己负责的数据"""
        # 创建测试数据
        df = pd.DataFrame({
            'A': ['INT-001', 'INT-002', 'INT-003'],
            '责任人': ['刘义航', '梁卿达', '刘义航'],
            '科室': ['结构一室', '结构一室', '结构二室'],
            '原始行号': [10, 11, 12]
        })
        
        with patch('base.tk.Tk'):
            from base import ExcelProcessorApp
            
            # 模拟应用
            app = Mock(spec=ExcelProcessorApp)
            app.user_name = '刘义航'
            app.user_roles = ['设计人员']
            app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app)
            app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app)
            app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app)
            
            # 应用角色筛选
            filtered = app.apply_role_based_filter(df, project_id='2016')
            
            # 验证：只有刘义航负责的数据
            assert len(filtered) == 2
            assert set(filtered['A']) == {'INT-001', 'INT-003'}
    
    def test_engineer_sees_all_project_data(self):
        """测试接口工程师看到对应项目的所有数据"""
        # 创建测试数据（2016项目）
        df = pd.DataFrame({
            'A': ['INT-001', 'INT-002', 'INT-003'],
            '责任人': ['刘义航', '梁卿达', '王五'],
            '科室': ['结构一室', '结构一室', '结构二室'],
            '原始行号': [10, 11, 12]
        })
        
        with patch('base.tk.Tk'):
            from base import ExcelProcessorApp
            
            app = Mock(spec=ExcelProcessorApp)
            app.user_name = '刘义航'
            app.user_roles = ['2016接口工程师']
            app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app)
            app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app)
            app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app)
            
            # 应用角色筛选（项目号匹配）
            filtered = app.apply_role_based_filter(df, project_id='2016')
            
            # 验证：显示所有数据（因为项目号匹配）
            assert len(filtered) == 3
    
    def test_director_sees_department_data(self):
        """测试主任看到对应科室的数据"""
        df = pd.DataFrame({
            'A': ['INT-001', 'INT-002', 'INT-003'],
            '责任人': ['刘义航', '梁卿达', '王五'],
            '科室': ['结构一室', '结构一室', '结构二室'],
            '原始行号': [10, 11, 12]
        })
        
        with patch('base.tk.Tk'):
            from base import ExcelProcessorApp
            
            app = Mock(spec=ExcelProcessorApp)
            app.user_name = '梁卿达'
            app.user_roles = ['一室主任']
            app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app)
            app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app)
            app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app)
            
            # 应用角色筛选
            filtered = app.apply_role_based_filter(df, project_id='2016')
            
            # 验证：只有结构一室的数据
            assert len(filtered) == 2
            assert set(filtered['科室']) == {'结构一室'}
    
    def test_multi_role_sees_combined_data(self):
        """测试多角色用户看到合并后的数据"""
        df = pd.DataFrame({
            'A': ['INT-001', 'INT-002', 'INT-003', 'INT-004'],
            '责任人': ['刘义航', '梁卿达', '王五', '刘义航'],
            '科室': ['结构一室', '结构一室', '结构二室', '结构二室'],
            '原始行号': [10, 11, 12, 13]
        })
        
        with patch('base.tk.Tk'):
            from base import ExcelProcessorApp
            
            app = Mock(spec=ExcelProcessorApp)
            app.user_name = '刘义航'
            app.user_roles = ['设计人员', '2016接口工程师']
            app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app)
            app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app)
            app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app)
            
            # 应用角色筛选（项目号匹配）
            filtered = app.apply_role_based_filter(df, project_id='2016')
            
            # 验证：看到所有数据（设计人员看到2条 + 接口工程师看到全部）
            assert len(filtered) == 4  # 多角色合并后的结果
            # 验证角色来源列存在
            assert '角色来源' in filtered.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

