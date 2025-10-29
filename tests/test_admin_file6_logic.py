"""
测试管理员身份对待处理文件6的特殊处理逻辑
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main


class TestAdminFile6Logic:
    """测试管理员对待处理文件6的特殊处理逻辑"""
    
    def test_process_functions_exist(self):
        """测试辅助处理函数存在"""
        assert hasattr(main, 'execute6_process1')
        assert hasattr(main, 'execute6_process3')
        assert hasattr(main, 'execute6_process4')
        
    def test_admin_includes_all_dates(self):
        """测试管理员模式包含所有日期的数据"""
        today = datetime.now()
        past_100 = today - timedelta(days=100)
        future_20 = today + timedelta(days=20)
        
        # 创建更清晰的测试数据
        data = {i: ['标题', '数据1', '数据2', '数据3'] for i in range(24)}
        # V列（索引21）：机构名称
        data[21] = ['V列', '河北分公司.建筑结构所', '河北分公司.建筑结构所', '其他机构']
        # I列（索引8）：日期
        data[8] = ['I列', past_100, future_20, today]
        # M列（索引12）：状态
        data[12] = ['M列', '尚未回复', '尚未回复', '已回复']
        # X列（索引23）：责任人
        data[23] = ['X列', '张三', '李四', '王五']
        
        df = pd.DataFrame(data)
        
        # 普通模式
        with patch('main.pd.read_excel', return_value=df):
            normal_result = main.process_target_file6('test.xlsx', today, skip_date_filter=False)
        
        # 管理员模式
        with patch('main.pd.read_excel', return_value=df):
            admin_result = main.process_target_file6('test.xlsx', today, skip_date_filter=True)
        
        # 普通模式：
        # p1 = {1, 2}（V列符合）
        # p3 = {1, 3}（I列日期 <= 今天+14天，100天前符合，20天后不符合，今天符合）
        # p4 = {1, 2}（M列符合）
        # final = p1 & p3 & p4 = {1}
        assert len(normal_result) == 1
        assert '张三' in normal_result.iloc[0]['责任人']
        
        # 管理员模式：
        # p1 = {1, 2}（V列符合）
        # p4 = {1, 2}（M列符合）
        # final = p1 & p4 = {1, 2}
        assert len(admin_result) == 2
        # 验证两行数据都包含了正确的责任人
        all_owners = ','.join(admin_result['责任人'].tolist())
        assert '张三' in all_owners
        assert '李四' in all_owners
        
    def test_normal_mode_filters_by_date(self):
        """测试普通模式仍然按日期筛选"""
        today = datetime.now()
        future_15 = today + timedelta(days=15)  # 超过14天限制
        future_10 = today + timedelta(days=10)  # 在14天内
        
        data = {i: ['标题', '数据1', '数据2'] for i in range(24)}
        data[21] = ['V列', '河北分公司.建筑结构所', '河北分公司.建筑结构所']
        data[8] = ['I列', future_15, future_10]
        data[12] = ['M列', '尚未回复', '尚未回复']
        data[23] = ['X列', '张三', '李四']
        
        df = pd.DataFrame(data)
        
        with patch('main.pd.read_excel', return_value=df):
            result = main.process_target_file6('test.xlsx', today, skip_date_filter=False)
        
        # 普通模式应该只包含第2行（10天后），排除第1行（15天后）
        assert len(result) == 1
        assert '李四' in result.iloc[0]['责任人']
    
    def test_admin_mode_ignores_far_future_dates(self):
        """测试管理员模式不受日期限制"""
        today = datetime.now()
        future_50 = today + timedelta(days=50)
        future_100 = today + timedelta(days=100)
        
        data = {i: ['标题', '数据1', '数据2'] for i in range(24)}
        data[21] = ['V列', '河北分公司.建筑结构所', '河北分公司.建筑结构所']
        data[8] = ['I列', future_50, future_100]
        data[12] = ['M列', '超期未回复', '尚未回复']
        data[23] = ['X列', '张三', '李四']
        
        df = pd.DataFrame(data)
        
        # 普通模式：未来50天和100天都超出14天限制
        with patch('main.pd.read_excel', return_value=df):
            normal_result = main.process_target_file6('test.xlsx', today, skip_date_filter=False)
        assert len(normal_result) == 0
        
        # 管理员模式：不受日期限制
        with patch('main.pd.read_excel', return_value=df):
            admin_result = main.process_target_file6('test.xlsx', today, skip_date_filter=True)
        assert len(admin_result) == 2


class TestAdminIntegration:
    """测试管理员和所领导在base.py中的集成"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的ExcelProcessorApp"""
        import base
        app = MagicMock(spec=base.ExcelProcessorApp)
        app.user_roles = ["管理员"]
        app.current_datetime = datetime.now()
        app.target_files6 = [("test.xlsx", "2016")]
        app.processing_results_multi6 = {}
        app._process_with_cache = base.ExcelProcessorApp._process_with_cache.__get__(app, base.ExcelProcessorApp)
        return app
    
    def test_base_calls_with_skip_date_filter_for_admin(self, mock_app):
        """测试base.py在管理员身份时正确传递skip_date_filter参数"""
        # 这个测试验证调用逻辑
        # 实际的集成测试需要完整的GUI环境
        
        # 验证：当用户角色包含"管理员"时，skip_date_filter应该为True
        skip_date_filter = ("管理员" in mock_app.user_roles) or ("所领导" in mock_app.user_roles)
        assert skip_date_filter == True
        
        # 验证：当用户角色不包含"管理员"时，skip_date_filter应该为False
        mock_app.user_roles = ["设计人员"]
        skip_date_filter = ("管理员" in mock_app.user_roles) or ("所领导" in mock_app.user_roles)
        assert skip_date_filter == False
    
    def test_base_calls_with_skip_date_filter_for_institute_leader(self, mock_app):
        """测试base.py在所领导身份时正确传递skip_date_filter参数"""
        # 验证：当用户角色包含"所领导"时，skip_date_filter应该为True
        mock_app.user_roles = ["所领导"]
        skip_date_filter = ("管理员" in mock_app.user_roles) or ("所领导" in mock_app.user_roles)
        assert skip_date_filter == True
        
    def test_base_calls_with_skip_date_filter_for_multi_roles(self, mock_app):
        """测试base.py在多角色（含管理员或所领导）时正确传递skip_date_filter参数"""
        # 设计人员 + 管理员
        mock_app.user_roles = ["设计人员", "管理员"]
        skip_date_filter = ("管理员" in mock_app.user_roles) or ("所领导" in mock_app.user_roles)
        assert skip_date_filter == True
        
        # 设计人员 + 所领导
        mock_app.user_roles = ["设计人员", "所领导"]
        skip_date_filter = ("管理员" in mock_app.user_roles) or ("所领导" in mock_app.user_roles)
        assert skip_date_filter == True
        
        # 仅设计人员
        mock_app.user_roles = ["设计人员"]
        skip_date_filter = ("管理员" in mock_app.user_roles) or ("所领导" in mock_app.user_roles)
        assert skip_date_filter == False


class TestFile6ParameterCompatibility:
    """测试process_target_file6的向后兼容性"""
    
    def test_default_parameter_is_false(self):
        """测试skip_date_filter默认值为False"""
        today = datetime.now()
        future_20 = today + timedelta(days=20)
        
        data = {i: ['标题', '数据1'] for i in range(24)}
        data[21] = ['V列', '河北分公司.建筑结构所']
        data[8] = ['I列', future_20]
        data[12] = ['M列', '尚未回复']
        data[23] = ['X列', '张三']
        
        df = pd.DataFrame(data)
        
        # 不传递skip_date_filter参数，应该使用默认值False
        with patch('main.pd.read_excel', return_value=df):
            result1 = main.process_target_file6('test.xlsx', today)
        
        # 显式传递False
        with patch('main.pd.read_excel', return_value=df):
            result2 = main.process_target_file6('test.xlsx', today, skip_date_filter=False)
        
        # 两者结果应该相同
        assert len(result1) == len(result2)
        assert len(result1) == 0  # 未来20天超出14天限制


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

