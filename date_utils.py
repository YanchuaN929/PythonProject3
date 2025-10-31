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
        date_str: 日期字符串，支持多种格式：
                  - mm.dd（如：01.15）
                  - yyyy.mm.dd（如：2024.12.20）
                  - yyyy-mm-dd（如：2024-12-20）
        reference_date: 参考日期，默认为今天
    
    Returns:
        bool: True表示已延期，False表示未延期或无法判断
    
    Examples:
        >>> is_date_overdue("01.10")  # 如果今天是01.15，返回True
        >>> is_date_overdue("2024.12.20")  # 如果今天是2025.10.31，返回True
        >>> is_date_overdue("未知")   # 返回False
    """
    try:
        # 处理空值或"未知"
        if not date_str or date_str == "未知":
            return False
        
        # 解析日期字符串
        date_str = str(date_str).strip()
        
        # 确定参考日期
        if reference_date is None:
            reference_date = date.today()
        
        # 尝试解析完整日期格式（yyyy.mm.dd 或 yyyy-mm-dd）
        if '.' in date_str or '-' in date_str:
            separator = '.' if '.' in date_str else '-'
            parts = date_str.split(separator)
            
            if len(parts) == 3:
                # 完整日期格式：yyyy.mm.dd
                try:
                    year = int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2])
                    due_date = date(year, month, day)
                    return due_date < reference_date
                except (ValueError, IndexError):
                    pass
            
            if len(parts) == 2:
                # mm.dd 格式：使用智能跨年判断
                parsed_date = parse_mmdd_to_date(date_str, reference_date)
                if parsed_date:
                    return parsed_date < reference_date
        
        # 兜底：按照旧逻辑处理（假设为当前年份）
        parts = date_str.replace('-', '.').split('.')
        if len(parts) == 2:
            month = int(parts[0])
            day = int(parts[1])
            due_date = date(reference_date.year, month, day)
            return due_date < reference_date
        
        return False
        
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


def parse_mmdd_to_date(date_str: str, reference_date: Optional[date] = None) -> Optional[date]:
    """
    将 mm.dd 格式的日期字符串解析为 date 对象
    
    智能处理跨年情况的核心逻辑:
    1. 先按今年解析日期
    2. 如果解析出的日期已经过去(< reference_date):
       - 判断是"最近刚过期"还是"很久以前"
       - 如果相差超过6个月,判断为"明年的日期,但还没到"(跨年未来)
       - 否则判断为"今年的已延期数据"
    3. 如果解析出的日期在未来(>= reference_date):
       - 直接返回今年的日期
    
    Args:
        date_str: mm.dd 格式的日期字符串(如 "09.15", "01.20")
        reference_date: 参考日期,默认为今天
    
    Returns:
        date对象,解析失败返回None
    
    Examples:
        # 假设今天是 2025-10-28
        >>> parse_mmdd_to_date("09.15")  # 今年9月(已延期)
        date(2025, 9, 15)
        >>> parse_mmdd_to_date("11.05")  # 今年11月(未来)
        date(2025, 11, 5)
        >>> parse_mmdd_to_date("01.20")  # 明年1月(未来,因为距离今天超过6个月)
        date(2026, 1, 20)
    """
    if reference_date is None:
        reference_date = date.today()
    
    try:
        # 解析 mm.dd
        parts = str(date_str).strip().split('.')
        if len(parts) != 2:
            return None
        
        month, day = int(parts[0]), int(parts[1])
        
        # 先尝试今年
        try:
            current_year_date = date(reference_date.year, month, day)
            
            # 计算距离参考日期的天数
            days_diff = (current_year_date - reference_date).days
            
            # 情况1: 日期在未来 (>= 0)
            if days_diff >= 0:
                return current_year_date
            
            # 情况2: 日期在过去 (< 0)
            # 需要判断是"今年的已延期"还是"实际上是明年但被解析成今年"
            # 阈值: 如果过去超过180天(约6个月),很可能是明年的日期
            # 例如: 今天是10月28日,1月10日距离今天约-291天,应该是明年1月
            #       今天是10月28日,9月15日距离今天约-43天,应该是今年9月(已延期)
            if days_diff < -180:
                # 距离太远,判断为明年
                next_year_date = date(reference_date.year + 1, month, day)
                return next_year_date
            else:
                # 距离较近,判断为今年已延期
                return current_year_date
                
        except ValueError:
            # 日期无效(如2月30日)
            return None
            
    except (ValueError, AttributeError, IndexError):
        return None

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

