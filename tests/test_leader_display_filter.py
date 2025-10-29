"""
测试所领导与管理员在主显示窗的显示差异
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from datetime import date
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base import ExcelProcessorApp


class TestInstituteLeaderDisplayFilter:
    """测试所领导主显示窗的2个工作日过滤"""
    
    @pytest.fixture
    def mock_app(self):
        """创建ExcelProcessorApp的模拟实例"""
        with patch('tkinter.Tk'), \
             patch('base.WindowManager'):
            app = MagicMock(spec=ExcelProcessorApp)
            
            # 绑定真实方法
            app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app)
            app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app)
            
            # 设置用户信息
            app.user_name = "测试所领导"
            app.user_role = "所领导"
            app.config = {"role_export_days": {"所领导": 2}}
            
            return app
    
    def test_institute_leader_filters_by_2_workdays(self, mock_app):
        """测试所领导只显示2个工作日内的数据"""
        # 假设今天是2025-10-28（周二）
        test_date = date(2025, 10, 28)
        
        # 创建测试数据（包含不同到期日期）
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4, 5, 6, 7],
            '接口时间': ['10.27', '10.28', '10.29', '10.30', '10.31', '11.03', '-'],
            # 周一(已延期), 周二(今天), 周三(1工作日), 周四(2工作日), 周五(3工作日), 下周一(4工作日), 空值
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005', 'INT-006', 'INT-007'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '结构一室', '结构二室', '建筑总图室', '结构一室'],
            '责任人': ['张三', '李四', '王五', '赵六', '孙七', '周八', '吴九']
        })
        
        # 应用过滤
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            
            filtered = mock_app._filter_by_single_role(df, '所领导', '2016')
        
        # 验证：应该只保留已延期 + 0-2个工作日内的数据
        # 10.27 (已延期) - 保留
        # 10.28 (今天, 0工作日) - 保留
        # 10.29 (周三, 1工作日) - 保留
        # 10.30 (周四, 2工作日) - 保留
        # 10.31 (周五, 3工作日) - 不保留
        # 11.03 (下周一, 4工作日) - 不保留
        # '-' (空值) - 不保留
        assert len(filtered) == 4, f"应该保留4行数据，实际保留{len(filtered)}行"
        assert list(filtered['接口号']) == ['INT-001', 'INT-002', 'INT-003', 'INT-004']
    
    def test_institute_leader_includes_all_departments(self, mock_app):
        """测试所领导查看所有科室的数据（不受科室限制）"""
        test_date = date(2025, 10, 28)
        
        # 创建包含不同科室的测试数据
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4],
            '接口时间': ['10.28', '10.28', '10.28', '10.28'],  # 都在2天内
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '请室主任确认'],
            '责任人': ['张三', '李四', '王五', '赵六']
        })
        
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            
            filtered = mock_app._filter_by_single_role(df, '所领导', '2016')
        
        # 验证：所有科室的数据都应该保留
        assert len(filtered) == 4
        assert set(filtered['科室']) == {'结构一室', '结构二室', '建筑总图室', '请室主任确认'}
    
    def test_institute_leader_excludes_empty_time(self, mock_app):
        """测试所领导过滤掉空时间的数据"""
        test_date = date(2025, 10, 28)
        
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4],
            '接口时间': ['10.28', '-', '', None],
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '结构一室'],
            '责任人': ['张三', '李四', '王五', '赵六']
        })
        
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            
            filtered = mock_app._filter_by_single_role(df, '所领导', '2016')
        
        # 验证：只保留有效时间的数据
        assert len(filtered) == 1
        assert list(filtered['接口号']) == ['INT-001']
    
    def test_institute_leader_includes_overdue(self, mock_app):
        """测试所领导包含已延期的数据"""
        test_date = date(2025, 10, 28)
        
        df = pd.DataFrame({
            '原始行号': [1, 2, 3],
            '接口时间': ['10.20', '10.25', '10.27'],  # 都是已延期
            '接口号': ['INT-001', 'INT-002', 'INT-003'],
            '科室': ['结构一室', '结构二室', '建筑总图室'],
            '责任人': ['张三', '李四', '王五']
        })
        
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            
            filtered = mock_app._filter_by_single_role(df, '所领导', '2016')
        
        # 验证：所有已延期数据都应该保留
        assert len(filtered) == 3


class TestAdminNoTimeFilter:
    """测试管理员不受时间限制"""
    
    @pytest.fixture
    def mock_admin_app(self):
        """创建管理员角色的模拟实例"""
        with patch('tkinter.Tk'), \
             patch('base.WindowManager'):
            app = MagicMock(spec=ExcelProcessorApp)
            
            # 绑定真实方法
            app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app)
            app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app)
            
            # 设置用户信息
            app.user_name = "测试管理员"
            app.user_role = "管理员"
            app.config = {}
            
            return app
    
    def test_admin_sees_all_data_regardless_of_time(self, mock_admin_app):
        """测试管理员查看所有数据，不受时间限制"""
        test_date = date(2025, 10, 28)
        
        # 创建测试数据（包含各种到期日期）
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4, 5, 6],
            '接口时间': ['10.20', '10.28', '10.30', '11.05', '12.25', '-'],
            # 已延期、今天、2工作日、8工作日、很远的未来、空值
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005', 'INT-006'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '结构一室', '结构二室', '建筑总图室'],
            '责任人': ['张三', '李四', '王五', '赵六', '孙七', '周八']
        })
        
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            
            filtered = mock_admin_app._filter_by_single_role(df, '管理员', '2016')
        
        # 验证：管理员应该看到所有数据（包括空值）
        assert len(filtered) == 6
        assert list(filtered['接口号']) == ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005', 'INT-006']


class TestLeaderVsAdminComparison:
    """对比测试：所领导 vs 管理员"""
    
    @pytest.fixture
    def test_data(self):
        """创建共同的测试数据"""
        return pd.DataFrame({
            '原始行号': [1, 2, 3, 4, 5, 6],
            '接口时间': ['10.25', '10.28', '10.29', '10.31', '11.10', '-'],
            # 已延期、今天、1工作日、3工作日、很远未来、空值
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005', 'INT-006'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '结构一室', '结构二室', '建筑总图室'],
            '责任人': ['张三', '李四', '王五', '赵六', '孙七', '周八']
        })
    
    def test_leader_sees_subset_of_admin_data(self, test_data):
        """测试所领导看到的数据是管理员的子集"""
        test_date = date(2025, 10, 28)
        
        # 创建所领导实例
        with patch('tkinter.Tk'), patch('base.WindowManager'):
            leader_app = MagicMock(spec=ExcelProcessorApp)
            leader_app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(leader_app)
            leader_app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(leader_app)
            leader_app.user_name = "所领导"
            leader_app.user_role = "所领导"
            leader_app.config = {}
            
            # 创建管理员实例
            admin_app = MagicMock(spec=ExcelProcessorApp)
            admin_app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(admin_app)
            admin_app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(admin_app)
            admin_app.user_name = "管理员"
            admin_app.user_role = "管理员"
            admin_app.config = {}
        
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            
            leader_filtered = leader_app._filter_by_single_role(test_data, '所领导', '2016')
            admin_filtered = admin_app._filter_by_single_role(test_data, '管理员', '2016')
        
        # 验证
        assert len(leader_filtered) < len(admin_filtered), "所领导应该看到更少的数据"
        assert len(leader_filtered) == 3, "所领导应该看到3行数据（已延期+今天+1工作日）"
        assert len(admin_filtered) == 6, "管理员应该看到所有6行数据"
        
        # 验证所领导的数据是管理员的子集
        leader_ids = set(leader_filtered['接口号'])
        admin_ids = set(admin_filtered['接口号'])
        assert leader_ids.issubset(admin_ids), "所领导的数据应该是管理员的子集"
        
        # 验证具体的差异
        assert '10.25' in list(leader_filtered['接口时间']), "所领导应该看到已延期数据"
        assert '10.31' not in list(leader_filtered['接口时间']), "所领导不应该看到3工作日后的数据"
        assert '11.10' not in list(leader_filtered['接口时间']), "所领导不应该看到远期数据"
        assert '-' not in list(leader_filtered['接口时间']), "所领导不应该看到空时间数据"
        
        assert '10.31' in list(admin_filtered['接口时间']), "管理员应该看到所有时间的数据"
        assert '11.10' in list(admin_filtered['接口时间']), "管理员应该看到远期数据"
        assert '-' in list(admin_filtered['接口时间']), "管理员应该看到空时间数据"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

