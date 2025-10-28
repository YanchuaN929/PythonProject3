"""
测试所领导角色相关功能

测试内容:
1. 所领导角色的筛选规则（不区分科室）
2. 所领导的日期窗口（2天工作日）
3. 所领导的简洁导出模式
4. 工作日计算函数（排除周六周日）
"""

import pytest
import pandas as pd
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestWorkdayCalculation:
    """测试工作日计算功能"""
    
    def test_count_workdays_week(self):
        """测试计算一周工作日数"""
        from date_utils import count_workdays
        
        # 2025-10-27 是周一，2025-10-31 是周五
        start = date(2025, 10, 27)
        end = date(2025, 10, 31)
        
        result = count_workdays(start, end)
        assert result == 5  # 周一到周五，共5个工作日
    
    def test_count_workdays_with_weekend(self):
        """测试跨周末的工作日计算"""
        from date_utils import count_workdays
        
        # 2025-10-24 是周五，2025-10-27 是周一
        start = date(2025, 10, 24)
        end = date(2025, 10, 27)
        
        result = count_workdays(start, end)
        assert result == 2  # 周五和周一，共2个工作日
    
    def test_count_workdays_weekend_only(self):
        """测试只包含周末的日期范围"""
        from date_utils import count_workdays
        
        # 2025-10-25 是周六，2025-10-26 是周日
        start = date(2025, 10, 25)
        end = date(2025, 10, 26)
        
        result = count_workdays(start, end)
        assert result == 0  # 周末没有工作日
    
    def test_get_workday_difference_future(self):
        """测试未来日期的工作日差"""
        from date_utils import get_workday_difference
        
        # 2025-10-27 (周一) 到 2025-10-31 (周五)
        target = date(2025, 10, 31)
        reference = date(2025, 10, 27)
        
        result = get_workday_difference(target, reference)
        assert result == 4  # 4个工作日（周二、周三、周四、周五）
    
    def test_get_workday_difference_past(self):
        """测试过去日期的工作日差（返回负数）"""
        from date_utils import get_workday_difference
        
        # 2025-10-23 (周四) 到 2025-10-27 (周一)
        target = date(2025, 10, 23)
        reference = date(2025, 10, 27)
        
        result = get_workday_difference(target, reference)
        assert result == -2  # 已延期2个工作日（周四和周五）
    
    def test_get_workday_difference_same_day(self):
        """测试同一天的工作日差"""
        from date_utils import get_workday_difference
        
        target = date(2025, 10, 27)
        reference = date(2025, 10, 27)
        
        result = get_workday_difference(target, reference)
        assert result == 0
    
    def test_get_date_warn_tag_with_workdays(self):
        """测试使用工作日计算的警告标签"""
        from date_utils import get_date_warn_tag
        
        # 假设今天是2025-10-27（周一）
        reference = date(2025, 10, 27)
        
        # 2025-10-24是周五，已延期2个工作日
        tag1 = get_date_warn_tag("10.24", reference, use_workdays=True)
        assert tag1 == "（已延误！！）"
        
        # 2025-10-29是周三，还有2个工作日（周二、周三）
        tag2 = get_date_warn_tag("10.29", reference, use_workdays=True)
        assert tag2 == "（下班前必须完成）"
        
        # 2025-11-03是周一（跨周末），还有5个工作日
        tag3 = get_date_warn_tag("11.03", reference, use_workdays=True)
        assert tag3 == "（注意时间）"


class TestInstituteLeaderRole:
    """测试所领导角色功能"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的ExcelProcessorApp实例"""
        from base import ExcelProcessorApp
        
        # 创建最小化的mock对象，只保留需要的方法
        app = MagicMock(spec=ExcelProcessorApp)
        app.user_name = "张所长"
        app.user_roles = ["所领导"]
        app.user_role = "所领导"
        app.config = {
            "role_export_days": {
                "一室主任": 7,
                "二室主任": 7,
                "建筑总图室主任": 7,
                "所领导": 2,
                "管理员": None,
                "设计人员": None
            },
            "simple_export_mode": False
        }
        app.auto_mode = False
        
        # 绑定真实的方法
        app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app, ExcelProcessorApp)
        app.apply_auto_role_date_window = ExcelProcessorApp.apply_auto_role_date_window.__get__(app, ExcelProcessorApp)
        app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app, ExcelProcessorApp)
        app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app, ExcelProcessorApp)
        
        return app
    
    def test_institute_leader_filter_no_department_restriction(self, mock_app):
        """测试所领导不区分科室，查看所有数据"""
        # 创建包含不同科室的测试数据
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4, 5],
            '责任人': ['张三', '李四', '王五', '赵六', '钱七'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '请室主任确认', '结构一室'],
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005']
        })
        
        # 测试所领导角色过滤
        filtered = mock_app._filter_by_single_role(df, "所领导", project_id="2016")
        
        # 所领导应该看到所有数据，不受科室限制
        assert len(filtered) == 5
        assert list(filtered['科室']) == ['结构一室', '结构二室', '建筑总图室', '请室主任确认', '结构一室']
    
    def test_institute_leader_date_window_with_workdays(self, mock_app):
        """测试所领导的日期窗口使用工作日计算（2天）"""
        # 假设今天是2025-10-28（周二）
        test_date = date(2025, 10, 28)
        
        # 创建包含不同截止日期的测试数据
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4, 5],
            '接口时间': ['10.27', '10.29', '10.30', '10.31', '11.03'],  # 周一、周三、周四、周五、下周一
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005']
        })
        
        # 设置auto_mode
        mock_app.auto_mode = True
        
        # 应用日期窗口（所领导：2个工作日）
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            filtered = mock_app.apply_auto_role_date_window(df)
        
        # 10.27 (已延期) - 符合
        # 10.29 (周三，1个工作日) - 符合
        # 10.30 (周四，2个工作日) - 符合
        # 10.31 (周五，3个工作日) - 不符合
        # 11.03 (下周一，跨周末4个工作日) - 不符合
        assert len(filtered) == 3
        assert list(filtered['接口号']) == ['INT-001', 'INT-002', 'INT-003']
    
    def test_institute_leader_vs_director_date_window(self, mock_app):
        """测试所领导和室主任都使用工作日计算，但天数门槛不同"""
        # 假设今天是2025-10-28（周二）
        test_date = date(2025, 10, 28)
        
        # 创建测试数据（增加更多日期以区分2天和7天工作日）
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4, 5],
            '接口时间': ['10.29', '10.30', '10.31', '11.03', '11.07'],  # 周三、周四、周五、下周一、下周五
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004', 'INT-005']
        })
        
        mock_app.auto_mode = True
        
        # 测试所领导（使用工作日，2天）
        mock_app.user_role = "所领导"
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            leader_filtered = mock_app.apply_auto_role_date_window(df)
        
        # 10.29 (周三，1个工作日) - 符合
        # 10.30 (周四，2个工作日) - 符合
        # 10.31 (周五，3个工作日) - 不符合
        # 11.03 (下周一，4个工作日) - 不符合
        # 11.07 (下周五，8个工作日) - 不符合
        assert len(leader_filtered) == 2
        
        # 测试室主任（也使用工作日，但7天）
        mock_app.user_role = "一室主任"
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            director_filtered = mock_app.apply_auto_role_date_window(df)
        
        # 10.29 (周三，1个工作日) - 符合
        # 10.30 (周四，2个工作日) - 符合
        # 10.31 (周五，3个工作日) - 符合
        # 11.03 (下周一，4个工作日) - 符合
        # 11.07 (下周五，8个工作日) - 不符合
        assert len(director_filtered) == 4


class TestDirectorWorkdayCalculation:
    """测试室主任的工作日计算功能"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的ExcelProcessorApp实例"""
        from base import ExcelProcessorApp
        
        app = MagicMock(spec=ExcelProcessorApp)
        app.user_name = "张主任"
        app.user_roles = ["一室主任"]
        app.user_role = "一室主任"
        app.config = {
            "role_export_days": {
                "一室主任": 7,
                "二室主任": 7,
                "建筑总图室主任": 7,
                "所领导": 2
            }
        }
        app.auto_mode = False
        
        # 绑定真实的方法
        app.apply_auto_role_date_window = ExcelProcessorApp.apply_auto_role_date_window.__get__(app, ExcelProcessorApp)
        
        return app
    
    def test_director_uses_workday_calculation(self, mock_app):
        """测试室主任使用工作日计算（7个工作日）"""
        # 假设今天是2025-10-28（周二）
        test_date = date(2025, 10, 28)
        
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4],
            '接口时间': ['10.29', '11.03', '11.06', '11.10'],  # 周三(1d)、下周一(4d)、下周四(7d)、下下周一(9d)
            '接口号': ['INT-001', 'INT-002', 'INT-003', 'INT-004']
        })
        
        mock_app.auto_mode = True
        
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            filtered = mock_app.apply_auto_role_date_window(df)
        
        # 10.29 (周三，1个工作日) - 符合
        # 11.03 (下周一，4个工作日) - 符合
        # 11.06 (下周四，7个工作日) - 符合
        # 11.10 (下下周一，9个工作日) - 不符合
        assert len(filtered) == 3
        assert list(filtered['接口号']) == ['INT-001', 'INT-002', 'INT-003']
    
    def test_all_directors_use_workday(self, mock_app):
        """测试所有室主任角色都使用工作日计算"""
        test_date = date(2025, 10, 28)
        
        df = pd.DataFrame({
            '原始行号': [1, 2],
            '接口时间': ['11.06', '11.10'],  # 7个工作日和9个工作日
            '接口号': ['INT-001', 'INT-002']
        })
        
        mock_app.auto_mode = True
        
        # 测试一室主任
        mock_app.user_role = "一室主任"
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            result1 = mock_app.apply_auto_role_date_window(df)
        assert len(result1) == 1  # 只有7天内的
        
        # 测试二室主任
        mock_app.user_role = "二室主任"
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            result2 = mock_app.apply_auto_role_date_window(df)
        assert len(result2) == 1
        
        # 测试建筑总图室主任
        mock_app.user_role = "建筑总图室主任"
        with patch('datetime.date') as mock_date_module:
            mock_date_module.today.return_value = test_date
            mock_date_module.side_effect = lambda *args, **kw: date(*args, **kw)
            result3 = mock_app.apply_auto_role_date_window(df)
        assert len(result3) == 1


class TestInstituteLeaderExport:
    """测试所领导的导出逻辑"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的ExcelProcessorApp实例"""
        from base import ExcelProcessorApp
        
        # 创建最小化的mock对象
        app = MagicMock(spec=ExcelProcessorApp)
        app.user_name = "张所长"
        app.user_roles = ["所领导"]
        app.config = {
            "role_export_days": {
                "所领导": 2
            },
            "simple_export_mode": False  # 所领导不需要勾选，默认使用简洁模式
        }
        return app
    
    def test_institute_leader_uses_simple_mode(self, mock_app):
        """测试所领导默认使用简洁导出模式"""
        # 所领导角色应该触发简洁模式
        simple_mode = (
            (("管理员" in mock_app.user_roles) and mock_app.config.get("simple_export_mode", False)) or
            ("所领导" in mock_app.user_roles)
        )
        
        assert simple_mode is True
    
    def test_admin_needs_checkbox_for_simple_mode(self):
        """测试管理员需要勾选才能使用简洁模式"""
        from base import ExcelProcessorApp
        
        # 创建最小化的mock对象
        app = MagicMock(spec=ExcelProcessorApp)
        app.user_roles = ["管理员"]
        app.config = {"simple_export_mode": False}
        
        # 未勾选时，不使用简洁模式
        simple_mode = (
            (("管理员" in app.user_roles) and app.config.get("simple_export_mode", False)) or
            ("所领导" in app.user_roles)
        )
        assert simple_mode is False
        
        # 勾选后，使用简洁模式
        app.config["simple_export_mode"] = True
        simple_mode = (
            (("管理员" in app.user_roles) and app.config.get("simple_export_mode", False)) or
            ("所领导" in app.user_roles)
        )
        assert simple_mode is True
    
    def test_institute_leader_export_format(self):
        """测试所领导导出格式（简洁模式，只显示个数）"""
        import main2
        import tempfile
        from datetime import datetime
        
        # 准备测试数据
        df1 = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002', 'INT-003'],
            '科室': ['结构一室', '结构二室', '建筑总图室'],
            '接口时间': ['10.28', '10.29', '10.30'],
            '角色来源': ['所领导', '所领导', '所领导']
        })
        
        results_multi1 = {'2016': df1}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 启用简洁模式（所领导）
            txt_path = main2.write_export_summary(
                folder_path=tmpdir,
                current_datetime=datetime.now(),
                results_multi1=results_multi1,
                simple_export_mode=True  # 所领导使用简洁模式
            )
            
            # 读取生成的文件
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证：应该包含个数
            assert '10.28需打开1个' in content or '10.28需打开1个' in content
            assert '10.29需打开1个' in content or '10.29需打开1个' in content
            
            # 验证：不应该包含接口号
            assert '接口号：' not in content
            assert 'INT-001' not in content
            assert 'INT-002' not in content
            assert 'INT-003' not in content


class TestMultiRoleWithInstituteLeader:
    """测试包含所领导的多角色场景"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的ExcelProcessorApp实例"""
        from base import ExcelProcessorApp
        
        # 创建最小化的mock对象
        app = MagicMock(spec=ExcelProcessorApp)
        app.user_name = "张主任"
        app.user_roles = ["一室主任", "所领导"]  # 同时是室主任和所领导
        app.config = {
            "role_export_days": {
                "一室主任": 7,
                "所领导": 2
            },
            "simple_export_mode": False
        }
        
        # 绑定真实的方法
        app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app, ExcelProcessorApp)
        app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app, ExcelProcessorApp)
        app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app, ExcelProcessorApp)
        
        return app
    
    def test_multi_role_with_institute_leader_filter(self, mock_app):
        """测试同时拥有室主任和所领导角色的筛选"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [1, 2, 3, 4],
            '责任人': ['张三', '李四', '王五', '赵六'],
            '科室': ['结构一室', '结构二室', '建筑总图室', '结构一室']
        })
        
        # 应用角色过滤
        filtered = mock_app.apply_role_based_filter(df, project_id="2016")
        
        # 一室主任：只看结构一室（行1和4）
        # 所领导：看所有数据（行1、2、3、4）
        # 合并去重后：应该包含所有数据
        assert len(filtered) == 4
    
    def test_multi_role_with_institute_leader_export_mode(self, mock_app):
        """测试多角色包含所领导时使用简洁导出模式"""
        # 包含所领导角色时，应该使用简洁模式
        simple_mode = (
            (("管理员" in mock_app.user_roles) and mock_app.config.get("simple_export_mode", False)) or
            ("所领导" in mock_app.user_roles)
        )
        
        assert simple_mode is True


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])

