#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日期工具模块测试用例
"""

import pytest
from datetime import date, timedelta
from date_utils import is_date_overdue, get_date_warn_tag


class TestIsDateOverdue:
    """测试is_date_overdue函数"""
    
    def test_overdue_date(self):
        """测试已过期的日期"""
        # 假设今天是2025-01-15
        test_date = date(2025, 1, 15)
        # 01.10已过期
        assert is_date_overdue("01.10", test_date) is True
    
    def test_future_date(self):
        """测试未来的日期"""
        test_date = date(2025, 1, 15)
        # 01.20未过期
        assert is_date_overdue("01.20", test_date) is False
    
    def test_today_date(self):
        """测试今天的日期"""
        test_date = date(2025, 1, 15)
        # 01.15今天，不算过期
        assert is_date_overdue("01.15", test_date) is False
    
    def test_unknown_date(self):
        """测试未知日期"""
        test_date = date(2025, 1, 15)
        assert is_date_overdue("未知", test_date) is False
    
    def test_empty_date(self):
        """测试空日期"""
        test_date = date(2025, 1, 15)
        assert is_date_overdue("", test_date) is False
        assert is_date_overdue(None, test_date) is False
    
    def test_invalid_format(self):
        """测试无效格式"""
        test_date = date(2025, 1, 15)
        assert is_date_overdue("2025-01-15", test_date) is False
        assert is_date_overdue("01/15", test_date) is False
        assert is_date_overdue("invalid", test_date) is False
    
    def test_default_reference_date(self):
        """测试默认参考日期（今天）"""
        yesterday = date.today() - timedelta(days=1)
        yesterday_str = f"{yesterday.month:02d}.{yesterday.day:02d}"
        # 昨天应该是过期的
        assert is_date_overdue(yesterday_str) is True
        
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_str = f"{tomorrow.month:02d}.{tomorrow.day:02d}"
        # 明天不应该是过期的
        assert is_date_overdue(tomorrow_str) is False


class TestGetDateWarnTag:
    """测试get_date_warn_tag函数"""
    
    def test_overdue_tag(self):
        """测试已延误标签"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("01.10", test_date) == "（已延误！！）"
        assert get_date_warn_tag("01.14", test_date) == "（已延误！！）"
    
    def test_urgent_tag(self):
        """测试紧急标签（3天内）"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("01.16", test_date) == "（下班前必须完成）"
        assert get_date_warn_tag("01.17", test_date) == "（下班前必须完成）"
        assert get_date_warn_tag("01.18", test_date) == "（下班前必须完成）"
    
    def test_warning_tag(self):
        """测试警告标签（7天内）"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("01.19", test_date) == "（注意时间）"
        assert get_date_warn_tag("01.20", test_date) == "（注意时间）"
        assert get_date_warn_tag("01.22", test_date) == "（注意时间）"
    
    def test_no_tag(self):
        """测试无标签（7天后）"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("01.23", test_date) == ""
        assert get_date_warn_tag("01.30", test_date) == ""
    
    def test_unknown_date_tag(self):
        """测试未知日期标签"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("未知", test_date) == ""
    
    def test_empty_date_tag(self):
        """测试空日期标签"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("", test_date) == ""
        assert get_date_warn_tag(None, test_date) == ""
    
    def test_invalid_format_tag(self):
        """测试无效格式标签"""
        test_date = date(2025, 1, 15)
        assert get_date_warn_tag("2025-01-15", test_date) == ""
        assert get_date_warn_tag("invalid", test_date) == ""
    
    def test_today_tag(self):
        """测试今天的标签"""
        test_date = date(2025, 1, 15)
        # 今天delta=0，应该返回已延误
        assert get_date_warn_tag("01.15", test_date) == "（已延误！！）"
    
    def test_default_reference_date_tag(self):
        """测试默认参考日期（今天）的标签"""
        yesterday = date.today() - timedelta(days=1)
        yesterday_str = f"{yesterday.month:02d}.{yesterday.day:02d}"
        # 昨天应该显示已延误
        assert get_date_warn_tag(yesterday_str) == "（已延误！！）"


class TestEdgeCases:
    """测试边界情况"""
    
    def test_year_boundary(self):
        """测试跨年边界"""
        # 假设今天是2025-12-30
        test_date = date(2025, 12, 30)
        # 12.25已过期
        assert is_date_overdue("12.25", test_date) is True
        # 12.31未过期
        assert is_date_overdue("12.31", test_date) is False
    
    def test_month_boundary(self):
        """测试月份边界"""
        # 假设今天是2025-01-31
        test_date = date(2025, 1, 31)
        # 01.30已过期
        assert is_date_overdue("01.30", test_date) is True
        # 02.01未过期
        assert is_date_overdue("02.01", test_date) is False
    
    def test_leading_zeros(self):
        """测试前导零"""
        test_date = date(2025, 1, 15)
        # 带前导零
        assert is_date_overdue("01.10", test_date) is True
        # 不带前导零（如果输入允许）
        # 注意：我们的实现假设总是有前导零


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

