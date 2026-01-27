#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动隐藏超期任务功能测试
"""

import pytest
import sys
import os
from datetime import date, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkdayCalculation:
    """工作日计算测试"""
    
    def test_get_workday_difference_overdue(self):
        """测试超期工作日计算"""
        from utils.date_utils import get_workday_difference
        
        # 假设今天是2025-12-09（周二）
        today = date(2025, 12, 9)
        
        # 超期1个工作日（昨天周一）
        due_date = date(2025, 12, 8)
        diff = get_workday_difference(due_date, today)
        assert diff == -1
        
        # 超期5个工作日（上周一到周五）
        due_date = date(2025, 12, 2)  # 周二
        diff = get_workday_difference(due_date, today)
        assert diff < 0
        
    def test_get_workday_difference_future(self):
        """测试未来日期的工作日计算"""
        from utils.date_utils import get_workday_difference
        
        today = date(2025, 12, 9)  # 周二
        
        # 明天（周三）
        due_date = date(2025, 12, 10)
        diff = get_workday_difference(due_date, today)
        assert diff > 0
        
    def test_count_workdays_excludes_weekends(self):
        """测试工作日计算排除周末"""
        from utils.date_utils import count_workdays
        
        # 周一到周五 = 5个工作日
        start = date(2025, 12, 8)  # 周一
        end = date(2025, 12, 12)   # 周五
        assert count_workdays(start, end) == 5
        
        # 周六到周日 = 0个工作日
        start = date(2025, 12, 13)  # 周六
        end = date(2025, 12, 14)    # 周日
        assert count_workdays(start, end) == 0


class TestOverdueFilter:
    """超期过滤测试"""
    
    def test_should_hide_overdue_task(self):
        """测试超过阈值的任务应该被隐藏"""
        from utils.date_utils import parse_mmdd_to_date, get_workday_difference
        
        today = date(2025, 12, 9)
        threshold_days = 30
        
        # 超过30个工作日的日期
        old_date_str = "10.01"  # 2025年10月1日，距今超过30个工作日
        due_date = parse_mmdd_to_date(old_date_str, today)
        
        if due_date:
            diff = get_workday_difference(due_date, today)
            should_hide = diff < 0 and abs(diff) > threshold_days
            assert should_hide == True
            
    def test_should_not_hide_recent_overdue(self):
        """测试最近超期的任务不应该被隐藏"""
        from utils.date_utils import parse_mmdd_to_date, get_workday_difference
        
        today = date(2025, 12, 9)
        threshold_days = 30
        
        # 超期5个工作日的日期（约1周前）
        recent_date_str = "12.02"  # 2025年12月2日
        due_date = parse_mmdd_to_date(recent_date_str, today)
        
        if due_date:
            diff = get_workday_difference(due_date, today)
            should_hide = diff < 0 and abs(diff) > threshold_days
            assert should_hide == False
            
    def test_should_not_hide_future_task(self):
        """测试未来的任务不应该被隐藏"""
        from utils.date_utils import parse_mmdd_to_date, get_workday_difference
        
        today = date(2025, 12, 9)
        threshold_days = 30
        
        # 未来日期
        future_date_str = "12.15"
        due_date = parse_mmdd_to_date(future_date_str, today)
        
        if due_date:
            diff = get_workday_difference(due_date, today)
            should_hide = diff < 0 and abs(diff) > threshold_days
            assert should_hide == False


class TestDistributionOverdueFilter:
    """任务指派超期过滤测试"""
    
    def test_check_unassigned_filters_overdue(self):
        """测试指派检查过滤超期任务"""
        import pandas as pd
        from services.distribution import check_unassigned
        
        # 创建测试数据
        today = date.today()
        old_date = today - timedelta(days=60)  # 约60天前，超过30工作日
        recent_date = today - timedelta(days=5)  # 5天前
        
        df = pd.DataFrame({
            '项目号': ['P001', 'P002'],
            '接口号': ['I001', 'I002'],
            '责任人': ['', ''],  # 都没有责任人
            '科室': ['结构一室', '结构一室'],
            'source_file': ['/test/file.xlsx', '/test/file.xlsx'],
            '原始行号': [2, 3],
            '接口时间': [old_date.strftime('%Y.%m.%d'), recent_date.strftime('%Y.%m.%d')]
        })
        
        processed_results = {1: df}
        user_roles = ['所领导']
        
        # 开启自动过滤
        config = {
            'auto_hide_overdue_enabled': True,
            'auto_hide_overdue_days': 30
        }
        
        unassigned = check_unassigned(processed_results, user_roles, config=config)
        
        # 应该只有1个任务（最近超期的，老的被过滤掉）
        assert len(unassigned) == 1
        assert unassigned[0]['interface_id'] == 'I002'
        
    def test_check_unassigned_no_filter_when_disabled(self):
        """测试禁用过滤时不过滤超期任务"""
        import pandas as pd
        from services.distribution import check_unassigned
        
        today = date.today()
        old_date = today - timedelta(days=60)
        
        df = pd.DataFrame({
            '项目号': ['P001'],
            '接口号': ['I001'],
            '责任人': [''],
            '科室': ['结构一室'],
            'source_file': ['/test/file.xlsx'],
            '原始行号': [2],
            '接口时间': [old_date.strftime('%Y.%m.%d')]
        })
        
        processed_results = {1: df}
        user_roles = ['所领导']
        
        # 禁用自动过滤
        config = {
            'auto_hide_overdue_enabled': False,
            'auto_hide_overdue_days': 30
        }
        
        unassigned = check_unassigned(processed_results, user_roles, config=config)
        
        # 应该有1个任务（不过滤）
        assert len(unassigned) == 1


class TestConfigDefaults:
    """配置默认值测试"""
    
    def test_default_auto_hide_enabled(self):
        """测试默认开启自动隐藏"""
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert config.get('auto_hide_overdue_enabled') == True
        
    def test_default_threshold_days(self):
        """测试默认阈值为30天"""
        import json
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        assert config.get('auto_hide_overdue_days') == 30


class TestVersionUpdate:
    """版本更新测试"""
    
    def test_version_updated(self):
        """测试版本号已更新"""
        import json
        version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'version.json')
        
        with open(version_path, 'r', encoding='utf-8') as f:
            version_data = json.load(f)
        
        # 版本号应该是 2025.12.09.x 格式
        version = version_data.get('version', '')
        assert version.startswith('2025.12.09')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

