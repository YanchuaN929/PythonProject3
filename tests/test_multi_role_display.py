"""
多角色叠加显示测试
测试设计人员 + 多个接口工程师角色的组合场景
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import tkinter as tk


class TestMultiRoleFilter:
    """测试多角色筛选逻辑"""
    
    def test_designer_plus_two_interface_engineers(self):
        """测试设计人员 + 两个接口工程师角色的叠加显示"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    # 设置用户信息：设计人员 + 1907接口工程师 + 2306接口工程师
                    app.user_name = '张三'
                    app.user_roles = ['设计人员', '1907接口工程师', '2306接口工程师']
                    
                    # 创建测试数据：包含1818、1907、2306三个项目
                    df = pd.DataFrame({
                        '原始行号': [10, 20, 30, 40, 50, 60],
                        '项目号': ['1818', '1818', '1907', '1907', '2306', '2306'],
                        '接口号': ['A-001', 'A-002', 'B-001', 'B-002', 'C-001', 'C-002'],
                        '责任人': ['张三', '李四', '王五', '赵六', '张三', '钱七'],
                        '科室': ['结构一室'] * 6,
                    })
                    
                    # 测试1818项目（只显示责任人=张三的任务）
                    result_1818 = app.apply_role_based_filter(df[df['项目号'] == '1818'].copy(), project_id='1818')
                    assert len(result_1818) == 1, f"1818项目应只显示1行（责任人=张三），实际{len(result_1818)}行"
                    assert result_1818.iloc[0]['接口号'] == 'A-001'
                    
                    # 测试1907项目（显示全部，因为是接口工程师）
                    result_1907 = app.apply_role_based_filter(df[df['项目号'] == '1907'].copy(), project_id='1907')
                    assert len(result_1907) == 2, f"1907项目应显示全部2行，实际{len(result_1907)}行"
                    
                    # 测试2306项目（显示全部，因为是接口工程师）
                    result_2306 = app.apply_role_based_filter(df[df['项目号'] == '2306'].copy(), project_id='2306')
                    assert len(result_2306) == 2, f"2306项目应显示全部2行，实际{len(result_2306)}行"
        finally:
            root.destroy()
    
    def test_only_designer_role(self):
        """测试只有设计人员角色时，只显示责任人为自己的任务"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    app.user_name = '张三'
                    app.user_roles = ['设计人员']
                    
                    df = pd.DataFrame({
                        '原始行号': [10, 20, 30],
                        '项目号': ['1907', '1907', '1907'],
                        '接口号': ['A-001', 'A-002', 'A-003'],
                        '责任人': ['张三', '李四', '张三'],
                        '科室': ['结构一室'] * 3,
                    })
                    
                    result = app.apply_role_based_filter(df.copy(), project_id='1907')
                    
                    # 应该只显示责任人=张三的2行
                    assert len(result) == 2
                    assert all(result['责任人'] == '张三')
        finally:
            root.destroy()
    
    def test_only_interface_engineer_role(self):
        """测试只有接口工程师角色时，只显示对应项目的全部数据"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    app.user_name = '张三'
                    app.user_roles = ['1907接口工程师']
                    
                    df = pd.DataFrame({
                        '原始行号': [10, 20, 30],
                        '项目号': ['1907', '1907', '1907'],
                        '接口号': ['A-001', 'A-002', 'A-003'],
                        '责任人': ['李四', '王五', '赵六'],  # 责任人都不是张三
                        '科室': ['结构一室'] * 3,
                    })
                    
                    # 1907项目：作为接口工程师，应显示全部
                    result_1907 = app.apply_role_based_filter(df.copy(), project_id='1907')
                    assert len(result_1907) == 3, f"1907项目应显示全部3行，实际{len(result_1907)}行"
                    
                    # 1818项目：不是该项目的接口工程师，应显示空
                    result_1818 = app.apply_role_based_filter(df.copy(), project_id='1818')
                    assert len(result_1818) == 0, f"1818项目应显示0行，实际{len(result_1818)}行"
        finally:
            root.destroy()
    
    def test_interface_engineer_plus_designer_combined(self):
        """测试接口工程师+设计人员角色的合并结果（去重）"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    app.user_name = '张三'
                    app.user_roles = ['设计人员', '1907接口工程师']
                    
                    df = pd.DataFrame({
                        '原始行号': [10, 20, 30],
                        '项目号': ['1907', '1907', '1907'],
                        '接口号': ['A-001', 'A-002', 'A-003'],
                        '责任人': ['张三', '李四', '张三'],  # 张三负责2个
                        '科室': ['结构一室'] * 3,
                    })
                    
                    result = app.apply_role_based_filter(df.copy(), project_id='1907')
                    
                    # 接口工程师返回全部3行，设计人员返回2行，合并去重后应该是3行
                    assert len(result) == 3, f"应显示3行（去重后），实际{len(result)}行"
        finally:
            root.destroy()
    
    def test_multiple_projects_combined_display(self):
        """测试多个项目的数据合并显示"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    app.user_name = '张三'
                    app.user_roles = ['设计人员', '1907接口工程师', '2306接口工程师']
                    
                    # 模拟合并后的DataFrame（包含多个项目）
                    all_results = []
                    
                    # 1818项目数据
                    df_1818 = pd.DataFrame({
                        '原始行号': [10, 20],
                        '项目号': ['1818', '1818'],
                        '接口号': ['A-001', 'A-002'],
                        '责任人': ['张三', '李四'],
                    })
                    result_1818 = app.apply_role_based_filter(df_1818.copy(), project_id='1818')
                    if not result_1818.empty:
                        all_results.append(result_1818)
                    
                    # 1907项目数据
                    df_1907 = pd.DataFrame({
                        '原始行号': [30, 40],
                        '项目号': ['1907', '1907'],
                        '接口号': ['B-001', 'B-002'],
                        '责任人': ['王五', '赵六'],
                    })
                    result_1907 = app.apply_role_based_filter(df_1907.copy(), project_id='1907')
                    if not result_1907.empty:
                        all_results.append(result_1907)
                    
                    # 2306项目数据
                    df_2306 = pd.DataFrame({
                        '原始行号': [50, 60],
                        '项目号': ['2306', '2306'],
                        '接口号': ['C-001', 'C-002'],
                        '责任人': ['孙七', '周八'],
                    })
                    result_2306 = app.apply_role_based_filter(df_2306.copy(), project_id='2306')
                    if not result_2306.empty:
                        all_results.append(result_2306)
                    
                    # 合并结果
                    if all_results:
                        combined = pd.concat(all_results, ignore_index=True)
                    else:
                        combined = pd.DataFrame()
                    
                    # 验证结果：
                    # - 1818: 1行（只有张三负责的）
                    # - 1907: 2行（接口工程师看全部）
                    # - 2306: 2行（接口工程师看全部）
                    # 总计: 5行
                    assert len(combined) == 5, f"应显示5行，实际{len(combined)}行"
                    
                    # 验证各项目的行数
                    assert len(combined[combined['项目号'] == '1818']) == 1
                    assert len(combined[combined['项目号'] == '1907']) == 2
                    assert len(combined[combined['项目号'] == '2306']) == 2
        finally:
            root.destroy()
    
    def test_parse_interface_engineer_role(self):
        """测试接口工程师角色解析"""
        with patch('base.tk.Tk'), patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 测试有效的接口工程师角色
            assert app._parse_interface_engineer_role('1907接口工程师') == '1907'
            assert app._parse_interface_engineer_role('2306接口工程师') == '2306'
            assert app._parse_interface_engineer_role('2016接口工程师') == '2016'
            
            # 测试无效的角色
            assert app._parse_interface_engineer_role('设计人员') is None
            assert app._parse_interface_engineer_role('一室主任') is None
            assert app._parse_interface_engineer_role('管理员') is None
    
    def test_role_source_column_added(self):
        """测试角色来源列被正确添加"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    app.user_name = '张三'
                    app.user_roles = ['设计人员']
                    
                    df = pd.DataFrame({
                        '原始行号': [10],
                        '项目号': ['1907'],
                        '接口号': ['A-001'],
                        '责任人': ['张三'],
                    })
                    
                    result = app.apply_role_based_filter(df.copy(), project_id='1907')
                    
                    # 验证角色来源列存在
                    assert '角色来源' in result.columns
                    assert result.iloc[0]['角色来源'] == '设计人员'
        finally:
            root.destroy()


class TestAdminRole:
    """测试管理员角色"""
    
    def test_admin_sees_all_data(self):
        """测试管理员角色能看到所有数据"""
        root = tk.Tk()
        root.withdraw()
        
        try:
            with patch('base.WindowManager'):
                from base import ExcelProcessorApp
                
                with patch('base.tk.Tk', return_value=root):
                    app = ExcelProcessorApp(auto_mode=False)
                    
                    app.user_name = '管理员A'
                    app.user_roles = ['管理员']
                    
                    df = pd.DataFrame({
                        '原始行号': [10, 20, 30],
                        '项目号': ['1818', '1907', '2306'],
                        '接口号': ['A-001', 'B-001', 'C-001'],
                        '责任人': ['张三', '李四', '王五'],
                    })
                    
                    result = app.apply_role_based_filter(df.copy(), project_id='1818')
                    
                    # 管理员应该看到全部数据
                    assert len(result) == 3
        finally:
            root.destroy()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

