"""
测试待处理文件6（收发文函）的处理逻辑
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import core.main as main


class TestFile6ProcessLogic:
    """测试待处理文件6的处理逻辑"""
    
    def test_execute6_process4_accepts_both_statuses(self):
        """测试execute6_process4接受'尚未回复'和'超期未回复'"""
        # 创建测试数据（M列是第13列，索引12）- 需要至少13列
        data = {i: [f'col{i}'] * 6 for i in range(13)}
        data[12] = ['M列标题', '尚未回复', '超期未回复', '已回复', '尚未回复', '其他状态']
        df = pd.DataFrame(data)
        
        result = main.execute6_process4(df)
        
        # 应该包含行1、2、4（索引1、2、4）
        assert len(result) == 3
        assert 1 in result  # '尚未回复'
        assert 2 in result  # '超期未回复'
        assert 4 in result  # '尚未回复'
        assert 3 not in result  # '已回复' 不应该包含
        assert 5 not in result  # '其他状态' 不应该包含
    
    def test_execute6_process4_handles_empty_column(self):
        """测试execute6_process4处理空列"""
        # M列不存在（列数不足）
        df = pd.DataFrame({
            0: ['标题', '1', '2'],
            1: ['A', 'B', 'C']
        })
        
        result = main.execute6_process4(df)
        
        assert len(result) == 0
    
    def test_execute6_process4_ignores_header(self):
        """测试execute6_process4忽略标题行"""
        data = {i: ['标题'] for i in range(13)}
        data[12] = ['尚未回复']  # 第0行是标题，应该被忽略
        df = pd.DataFrame(data)
        
        result = main.execute6_process4(df)
        
        assert len(result) == 0  # 标题行不应该被包含
    
    def test_process_target_file6_does_not_use_h_column(self):
        """测试process_target_file6不再使用H列筛选"""
        # 创建包含所有必要列的测试数据
        today = datetime.now()
        future_date = today + timedelta(days=7)
        
        # 创建测试DataFrame（需要至少24列以包含X列）- 所有列长度必须一致
        data = {i: [f'col{i}', 'data1', 'data2', 'data3', 'data4', 'data5'] for i in range(25)}
        
        # 设置关键列
        # H列（索引7）- 不应该影响结果
        data[7] = ['H列', '否', '否', '否', '否', '否']
        
        # V列（索引21）- 包含机构名
        data[21] = ['V列', '河北分公司.建筑结构所', '河北分公司.建筑结构所', '其他', '河北分公司.建筑结构所', '河北分公司.建筑结构所']
        
        # I列（索引8）- 日期列
        data[8] = ['I列', future_date, future_date, future_date, future_date, future_date]
        
        # M列（索引12）- 回复状态
        data[12] = ['M列', '尚未回复', '超期未回复', '已回复', '尚未回复', '尚未回复']
        
        # X列（索引23）- 责任人
        data[23] = ['X列', '张三', '李四', '王五', '赵六', '孙七']
        
        df = pd.DataFrame(data)
        
        # 模拟文件读取
        with patch('main.pd.read_excel', return_value=df):
            result = main.process_target_file6('test.xlsx', today)
        
        # 即使H列都是"否"，只要满足其他3个条件，仍应该有结果
        # 预期：行1、2、4、5符合（V列+I列+M列条件），行3不符合（M列='已回复'）
        assert len(result) == 4
    
    def test_final_rows_calculation_excludes_h_column(self):
        """测试final_rows计算不包含p2(H列筛选)"""
        # 创建简单的测试数据 - 需要至少22列以包含V列
        data = {i: ['标题'] * 4 for i in range(22)}
        data[7] = ['H列', '否', '是', '否']  # H列
        data[21] = ['V列', '河北分公司.建筑结构所', '河北分公司.建筑结构所', '其他']  # V列
        data[8] = ['I列', datetime.now(), datetime.now(), datetime.now()]  # I列
        data[12] = ['M列', '尚未回复', '尚未回复', '尚未回复']  # M列
        df = pd.DataFrame(data)
        
        p1 = main.execute6_process1(df)  # V列匹配
        p3 = main.execute6_process3(df, datetime.now())  # I列日期范围
        p4 = main.execute6_process4(df)  # M列状态
        
        # 验证p1包含行1、2（V列符合），不包含行3
        assert 1 in p1
        assert 2 in p1
        assert 3 not in p1
        
        # 验证p4包含所有3行（M列都是'尚未回复'）
        assert len(p4) == 3
        
        # final_rows应该是p1 & p3 & p4（不包含p2）
        final_rows = p1 & p3 & p4
        
        # 即使行1的H列是"否"，它仍应该在final_rows中
        assert 1 in final_rows


class TestFile6DateLogic:
    """测试I列日期筛选逻辑"""
    
    def test_process3_includes_past_dates(self):
        """测试execute6_process3包含过去的日期"""
        today = datetime.now()
        past_date = today - timedelta(days=30)  # 30天前
        
        data = {i: ['标题', '数据1', '数据2'] for i in range(9)}
        data[8] = ['I列', past_date, today]
        df = pd.DataFrame(data)
        
        result = main.execute6_process3(df, today)
        
        # 应该包含行1（过去30天）和行2（今天）
        assert len(result) == 2
        assert 1 in result  # 过去的日期
        assert 2 in result  # 今天
    
    def test_process3_includes_today(self):
        """测试execute6_process3包含今天"""
        today = datetime.now()
        
        data = {i: ['标题', '数据'] for i in range(9)}
        data[8] = ['I列', today]
        df = pd.DataFrame(data)
        
        result = main.execute6_process3(df, today)
        
        assert len(result) == 1
        assert 1 in result
    
    def test_process3_includes_future_14_days(self):
        """测试execute6_process3包含未来14天"""
        today = datetime.now()
        future_14 = today + timedelta(days=14)
        
        data = {i: ['标题', '数据'] for i in range(9)}
        data[8] = ['I列', future_14]
        df = pd.DataFrame(data)
        
        result = main.execute6_process3(df, today)
        
        assert len(result) == 1
        assert 1 in result
    
    def test_process3_excludes_future_15_days(self):
        """测试execute6_process3排除未来15天及以后"""
        today = datetime.now()
        future_15 = today + timedelta(days=15)
        future_20 = today + timedelta(days=20)
        
        data = {i: ['标题', '数据1', '数据2'] for i in range(9)}
        data[8] = ['I列', future_15, future_20]
        df = pd.DataFrame(data)
        
        result = main.execute6_process3(df, today)
        
        # 不应该包含任何数据（15天和20天都超出范围）
        assert len(result) == 0
    
    def test_process3_mixed_dates(self):
        """测试execute6_process3混合日期（过去、今天、未来14天内、未来15天外）"""
        today = datetime.now()
        past = today - timedelta(days=100)
        future_7 = today + timedelta(days=7)
        future_14 = today + timedelta(days=14)
        future_15 = today + timedelta(days=15)
        
        data = {i: ['标题', '数据1', '数据2', '数据3', '数据4', '数据5'] for i in range(9)}
        data[8] = ['I列', past, today, future_7, future_14, future_15]
        df = pd.DataFrame(data)
        
        result = main.execute6_process3(df, today)
        
        # 应该包含前4行（过去、今天、未来7天、未来14天），排除第5行（未来15天）
        assert len(result) == 4
        assert 1 in result  # 过去
        assert 2 in result  # 今天
        assert 3 in result  # 未来7天
        assert 4 in result  # 未来14天
        assert 5 not in result  # 未来15天（超出范围）


class TestFile6MColumnExpansion:
    """测试M列接受多种状态"""
    
    def test_m_column_accepts_standard_reply(self):
        """测试M列接受'尚未回复'"""
        data = {i: ['标题', '数据'] for i in range(13)}
        data[12] = ['M列', '尚未回复']
        df = pd.DataFrame(data)
        
        result = main.execute6_process4(df)
        assert 1 in result
    
    def test_m_column_accepts_overdue_reply(self):
        """测试M列接受'超期未回复'"""
        data = {i: ['标题', '数据'] for i in range(13)}
        data[12] = ['M列', '超期未回复']
        df = pd.DataFrame(data)
        
        result = main.execute6_process4(df)
        assert 1 in result
    
    def test_m_column_rejects_other_statuses(self):
        """测试M列拒绝其他状态"""
        df = pd.DataFrame({
            12: ['M列', '已回复', '部分回复', '无需回复', '']
        })
        
        result = main.execute6_process4(df)
        assert len(result) == 0
    
    def test_m_column_handles_whitespace(self):
        """测试M列正确处理空白字符"""
        data = {i: ['标题', '数据1', '数据2', '数据3'] for i in range(13)}
        data[12] = ['M列', '  尚未回复  ', '\t超期未回复\n', '已回复  ']
        df = pd.DataFrame(data)
        
        result = main.execute6_process4(df)
        
        # 应该识别出前两个（尚未回复和超期未回复）
        assert len(result) == 2
        assert 1 in result
        assert 2 in result
        assert 3 not in result  # '已回复' 不应该包含


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

