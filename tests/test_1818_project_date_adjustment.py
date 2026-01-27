#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试1818项目的日期减6天特殊逻辑

业务背景：1818项目的预期时间比实际流程提前6天，
因此在日期筛选时需要将Excel中的日期减6天后再与筛选范围比较。
"""

import datetime
import pandas as pd
import pytest


class TestAdjustDateForProject:
    """测试adjust.py中的adjust_date_for_project函数"""

    def test_1818_project_date_minus_6_days(self):
        """1818项目日期应减6天"""
        from utils.adjust import adjust_date_for_project
        
        original = datetime.datetime(2026, 1, 15)
        adjusted = adjust_date_for_project(original, '1818')
        
        expected = datetime.datetime(2026, 1, 9)
        assert adjusted == expected

    def test_non_1818_project_date_unchanged(self):
        """非1818项目日期不变"""
        from utils.adjust import adjust_date_for_project
        
        original = datetime.datetime(2026, 1, 15)
        
        # 测试其他项目
        for project_id in ['2016', '1907', '1915', '1916', '2026', '2306', None]:
            adjusted = adjust_date_for_project(original, project_id)
            assert adjusted == original, f"项目{project_id}的日期不应该改变"

    def test_1818_with_pandas_timestamp(self):
        """1818项目配合pandas.Timestamp也能正常工作"""
        from utils.adjust import adjust_date_for_project
        
        original = pd.Timestamp('2026-01-15')
        adjusted = adjust_date_for_project(original, '1818')
        
        # pandas Timestamp减去timedelta后仍是Timestamp
        expected = pd.Timestamp('2026-01-09')
        assert adjusted == expected

    def test_1818_with_none_date(self):
        """传入None日期时应返回None"""
        from utils.adjust import adjust_date_for_project
        
        adjusted = adjust_date_for_project(None, '1818')
        assert adjusted is None

    def test_get_project_date_offset(self):
        """测试get_project_date_offset函数"""
        from utils.adjust import get_project_date_offset
        
        assert get_project_date_offset('1818') == 6
        assert get_project_date_offset('2016') == 0
        assert get_project_date_offset(None) == 0


class TestExecuteProcess2With1818:
    """测试execute_process2对1818项目的日期筛选"""

    def test_1818_date_filter_boundary(self):
        """
        1818项目边界测试：
        - 当前日期：2026-01-15（1~19号范围内）
        - 筛选范围：2026-01-01 ~ 2026-01-31
        - Excel日期：2026-02-06（原本超出范围）
        - 减6天后：2026-01-31（刚好在范围内）
        """
        import core.main as main
        
        # 构造测试数据：K列(索引10)是日期列
        data = {i: ['header'] + [''] * 5 for i in range(11)}
        data[10] = ['header', '2026-02-06', '2026-02-07', '2026-01-15', '2026-01-01', '']
        df = pd.DataFrame(data)
        
        current_datetime = datetime.datetime(2026, 1, 15)
        
        # 1818项目：2026-02-06 减6天 = 2026-01-31，在范围内
        result_1818 = main.execute_process2(df, current_datetime, '1818')
        assert 1 in result_1818, "2026-02-06减6天后应在1月范围内"
        assert 2 not in result_1818, "2026-02-07减6天后是2026-02-01，超出1月范围"
        
        # 非1818项目：2026-02-06 超出范围
        result_2016 = main.execute_process2(df, current_datetime, '2016')
        assert 1 not in result_2016, "非1818项目：2026-02-06超出1月范围"

    def test_1818_date_filter_all_dates_shift(self):
        """验证1818项目所有日期都正确偏移"""
        import core.main as main
        
        # K列日期
        data = {i: ['header'] + [''] * 3 for i in range(11)}
        # 原日期：01-07, 01-08, 01-20
        # 减6天：01-01, 01-02, 01-14
        data[10] = ['header', '2026-01-07', '2026-01-08', '2026-01-20']
        df = pd.DataFrame(data)
        
        current_datetime = datetime.datetime(2026, 1, 15)
        
        # 1818项目
        result = main.execute_process2(df, current_datetime, '1818')
        # 01-07 - 6 = 01-01 (在范围内)
        # 01-08 - 6 = 01-02 (在范围内)
        # 01-20 - 6 = 01-14 (在范围内)
        assert 1 in result
        assert 2 in result
        assert 3 in result


class TestFile6DateFilterWith1818:
    """测试文件6的日期筛选（delta方式）对1818项目的处理"""

    def test_file6_1818_date_filter(self):
        """
        文件6使用delta计算：delta = (cell_date - today).days <= 14
        1818项目减6天后再计算delta
        """
        import core.main as main
        
        # I列(索引8)是日期列
        data = {i: ['header'] + [''] * 3 for i in range(9)}
        # 原日期：today+20天（原本超出14天限制）
        # 减6天后：today+14天（刚好在限制内）
        today = datetime.datetime(2026, 1, 15)
        date_plus_20 = (today + datetime.timedelta(days=20)).strftime('%Y-%m-%d')
        date_plus_21 = (today + datetime.timedelta(days=21)).strftime('%Y-%m-%d')
        data[8] = ['header', date_plus_20, date_plus_21, '2026-01-10']
        df = pd.DataFrame(data)
        
        # 1818项目
        result_1818 = main.execute6_process3(df, today, '1818')
        # date_plus_20 - 6 = today+14 (delta=14, 在范围内)
        assert 1 in result_1818, "today+20减6天后delta=14，应在范围内"
        # date_plus_21 - 6 = today+15 (delta=15, 超出范围)
        assert 2 not in result_1818, "today+21减6天后delta=15，应超出范围"
        
        # 非1818项目
        result_2016 = main.execute6_process3(df, today, '2016')
        assert 1 not in result_2016, "非1818项目：today+20超出14天限制"
