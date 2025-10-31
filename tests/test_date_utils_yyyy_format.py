#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 parse_mmdd_to_date 函数对 yyyy.mm.dd 格式的支持
"""

import pytest
from datetime import date
from date_utils import parse_mmdd_to_date, get_workday_difference


class TestYyyyMmDdFormatSupport:
    """测试 yyyy.mm.dd 格式支持"""
    
    def test_parse_full_date_format(self):
        """测试解析完整日期格式 yyyy.mm.dd"""
        # 测试已延期的日期
        result = parse_mmdd_to_date("2024.12.20", date(2025, 10, 31))
        assert result == date(2024, 12, 20)
        
        # 测试今年的日期
        result = parse_mmdd_to_date("2025.10.28", date(2025, 10, 31))
        assert result == date(2025, 10, 28)
        
        # 测试未来的日期
        result = parse_mmdd_to_date("2025.11.05", date(2025, 10, 31))
        assert result == date(2025, 11, 5)
    
    def test_parse_old_mmdd_format_still_works(self):
        """测试旧的 mm.dd 格式仍然正常工作"""
        # 测试今年的日期
        result = parse_mmdd_to_date("10.28", date(2025, 10, 31))
        assert result == date(2025, 10, 28)
        
        # 测试跨年判断（1月份会被判断为明年）
        result = parse_mmdd_to_date("01.20", date(2025, 10, 31))
        assert result == date(2026, 1, 20)  # 明年1月
        
        # 测试最近已延期的日期
        result = parse_mmdd_to_date("09.15", date(2025, 10, 31))
        assert result == date(2025, 9, 15)  # 今年9月（已延期）
    
    def test_workday_difference_with_full_date(self):
        """测试使用完整日期格式计算工作日差"""
        # 2024.12.20（去年）到 2025.10.31（今天）
        due_date = parse_mmdd_to_date("2024.12.20", date(2025, 10, 31))
        workday_diff = get_workday_difference(due_date, date(2025, 10, 31))
        
        # 应该是负数（已延期）
        assert workday_diff < 0
        print(f"2024.12.20 到 2025.10.31 的工作日差: {workday_diff}")
    
    def test_workday_difference_with_recent_past(self):
        """测试最近已延期的日期"""
        # 2025.10.25（上周五）到 2025.10.31（本周五）
        due_date = parse_mmdd_to_date("2025.10.25", date(2025, 10, 31))
        workday_diff = get_workday_difference(due_date, date(2025, 10, 31))
        
        # 应该是 -4 个工作日（周五到下周五，跨过周末）
        assert workday_diff < 0
        print(f"2025.10.25 到 2025.10.31 的工作日差: {workday_diff}")
    
    def test_workday_difference_with_future(self):
        """测试未来日期"""
        # 2025.11.04（下周一）到 2025.10.31（本周五）
        due_date = parse_mmdd_to_date("2025.11.04", date(2025, 10, 31))
        workday_diff = get_workday_difference(due_date, date(2025, 10, 31))
        
        # 应该是 2 个工作日（周五到下周一）
        assert workday_diff == 2
        print(f"2025.11.04 到 2025.10.31 的工作日差: {workday_diff}")
    
    def test_leader_role_filter_logic(self):
        """测试所领导角色的过滤逻辑（2个工作日窗口）"""
        today = date(2025, 10, 31)  # 周五
        max_workdays = 2
        
        test_cases = [
            ("2024.12.20", True, "去年已延期，应保留"),
            ("2025.10.25", True, "上周已延期，应保留"),
            ("2025.10.31", True, "今天到期，应保留"),
            ("2025.11.01", True, "明天（算作下周一，1个工作日），应保留"),
            ("2025.11.04", True, "下周一（2个工作日），应保留"),
            ("2025.11.05", False, "下周二（3个工作日），不保留"),
        ]
        
        for date_str, should_keep, description in test_cases:
            due_date = parse_mmdd_to_date(date_str, today)
            assert due_date is not None, f"日期解析失败: {date_str}"
            
            workday_diff = get_workday_difference(due_date, today)
            kept = (workday_diff <= max_workdays)
            
            assert kept == should_keep, f"{description} - 日期:{date_str}, 工作日差:{workday_diff}, 预期:{should_keep}, 实际:{kept}"
            print(f"[PASS] {description} - {date_str} (工作日差={workday_diff})")


class TestEdgeCases:
    """边界情况测试"""
    
    def test_invalid_full_date(self):
        """测试无效的完整日期"""
        # 无效的月份
        result = parse_mmdd_to_date("2025.13.01", date(2025, 10, 31))
        assert result is None
        
        # 无效的日期
        result = parse_mmdd_to_date("2025.02.30", date(2025, 10, 31))
        assert result is None
    
    def test_empty_and_none_dates(self):
        """测试空值和None"""
        assert parse_mmdd_to_date("", date(2025, 10, 31)) is None
        assert parse_mmdd_to_date("未知", date(2025, 10, 31)) is None
    
    def test_single_part_date(self):
        """测试单部分日期（应该失败）"""
        result = parse_mmdd_to_date("2025", date(2025, 10, 31))
        assert result is None
    
    def test_four_part_date(self):
        """测试四部分日期（应该失败）"""
        result = parse_mmdd_to_date("2025.10.31.00", date(2025, 10, 31))
        assert result is None


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])

