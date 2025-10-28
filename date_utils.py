#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日期工具模块 - 提供日期相关的公共函数
"""

from datetime import date, timedelta
from typing import Optional


def is_date_overdue(date_str: str, reference_date: Optional[date] = None) -> bool:
    """
    判断日期是否已延期
    
    Args:
        date_str: 日期字符串，格式 mm.dd（如：01.15）
        reference_date: 参考日期，默认为今天
    
    Returns:
        bool: True表示已延期，False表示未延期或无法判断
    
    Examples:
        >>> is_date_overdue("01.10")  # 如果今天是01.15，返回True
        >>> is_date_overdue("01.20")  # 如果今天是01.15，返回False
        >>> is_date_overdue("未知")   # 返回False
    """
    try:
        # 处理空值或"未知"
        if not date_str or date_str == "未知":
            return False
        
        # 解析日期字符串
        date_str = str(date_str).strip()
        parts = date_str.split('.')
        if len(parts) != 2:
            return False
        
        month = int(parts[0])
        day = int(parts[1])
        
        # 确定参考日期
        if reference_date is None:
            reference_date = date.today()
        
        # 构建截止日期（假设为当前年份）
        due_date = date(reference_date.year, month, day)
        
        # 判断是否延期（截止日期 < 参考日期）
        return due_date < reference_date
        
    except (ValueError, AttributeError, IndexError) as e:
        # 解析失败，默认不标红
        return False


def count_workdays(start_date: date, end_date: date) -> int:
    """
    计算两个日期之间的工作日天数（排除周六和周日）
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        int: 工作日天数
    
    Examples:
        >>> count_workdays(date(2025, 10, 27), date(2025, 10, 31))  # 周一到周五
        5
        >>> count_workdays(date(2025, 10, 25), date(2025, 10, 27))  # 周六到周一
        1
    """
    if start_date > end_date:
        return 0
    
    workdays = 0
    current = start_date
    
    while current <= end_date:
        # weekday(): 0=周一, 1=周二, ..., 5=周六, 6=周日
        if current.weekday() < 5:  # 周一到周五
            workdays += 1
        current += timedelta(days=1)
    
    return workdays


def get_workday_difference(target_date: date, reference_date: Optional[date] = None) -> int:
    """
    计算目标日期与参考日期之间的工作日天数差（排除周六周日）
    
    Args:
        target_date: 目标日期（截止日期）
        reference_date: 参考日期，默认为今天
    
    Returns:
        int: 工作日天数差
            - 正数：目标日期在参考日期之后（还有N个工作日）
            - 负数：目标日期在参考日期之前（已延期N个工作日）
            - 0：同一天或目标日期是参考日期后的非工作日
    
    Examples:
        >>> get_workday_difference(date(2025, 10, 31), date(2025, 10, 27))  # 周一到周五
        5
        >>> get_workday_difference(date(2025, 10, 25), date(2025, 10, 27))  # 周六到周一
        -1
    """
    if reference_date is None:
        reference_date = date.today()
    
    if target_date < reference_date:
        # 已过期：计算逾期的工作日数（返回负值）
        return -count_workdays(target_date, reference_date - timedelta(days=1))
    elif target_date == reference_date:
        return 0
    else:
        # 未来：计算剩余工作日数（返回正值）
        return count_workdays(reference_date + timedelta(days=1), target_date)


def get_date_warn_tag(date_str: str, reference_date: Optional[date] = None, use_workdays: bool = True) -> str:
    """
    根据日期与当前日期的天数差生成提醒标签
    
    Args:
        date_str: 日期字符串，格式 mm.dd（如：01.15）
        reference_date: 参考日期，默认为今天
        use_workdays: 是否使用工作日计算（排除周六周日），默认True
    
    Returns:
        str: 提醒标签，可能的值：
            - "（已延误！！）" - 已过期
            - "（下班前必须完成）" - 3天内到期
            - "（注意时间）" - 7天内到期
            - "" - 无需提醒
    
    Examples:
        >>> get_date_warn_tag("01.10")  # 如果今天是01.15，返回"（已延误！！）"
        >>> get_date_warn_tag("01.17")  # 如果今天是01.15，返回"（下班前必须完成）"
        >>> get_date_warn_tag("01.20")  # 如果今天是01.15，返回"（注意时间）"
    """
    try:
        # 处理空值或"未知"
        if not date_str or date_str == "未知":
            return ""
        
        # 解析日期字符串
        date_str = str(date_str).strip()
        parts = date_str.split('.')
        if len(parts) != 2:
            return ""
        
        month = int(parts[0])
        day = int(parts[1])
        
        # 确定参考日期
        if reference_date is None:
            reference_date = date.today()
        
        # 构建截止日期（假设为当前年份）
        due_date = date(reference_date.year, month, day)
        
        # 计算天数差
        if use_workdays:
            # 使用工作日计算（排除周六周日）
            delta = get_workday_difference(due_date, reference_date)
        else:
            # 使用自然日计算
            delta = (due_date - reference_date).days
        
        # 根据天数差返回提醒标签
        if delta <= 0:
            return "（已延误！！）"
        elif delta <= 3:
            return "（下班前必须完成）"
        elif delta <= 7:
            return "（注意时间）"
        else:
            return ""
        
    except (ValueError, AttributeError, IndexError) as e:
        # 解析失败，返回空字符串
        return ""


if __name__ == "__main__":
    # 简单测试
    from datetime import date
    
    # 假设今天是2025-01-15
    test_date = date(2025, 1, 15)
    
    print("测试 is_date_overdue:")
    print(f"  01.10 (已过期): {is_date_overdue('01.10', test_date)}")  # True
    print(f"  01.15 (今天): {is_date_overdue('01.15', test_date)}")    # False
    print(f"  01.20 (未来): {is_date_overdue('01.20', test_date)}")    # False
    print(f"  未知: {is_date_overdue('未知', test_date)}")              # False
    
    print("\n测试 get_date_warn_tag:")
    print(f"  01.10: {get_date_warn_tag('01.10', test_date)}")  # （已延误！！）
    print(f"  01.17: {get_date_warn_tag('01.17', test_date)}")  # （下班前必须完成）
    print(f"  01.20: {get_date_warn_tag('01.20', test_date)}")  # （注意时间）
    print(f"  01.30: {get_date_warn_tag('01.30', test_date)}")  # （空）

