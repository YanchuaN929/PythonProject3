#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目特殊调整逻辑模块

此模块用于处理特定项目的特殊业务规则，便于集中管理和维护。
当需要为某个项目添加特殊逻辑时，在此文件中添加即可，无需修改核心处理代码。
"""

import datetime

# ===================== 1818项目日期调整 =====================
# 业务背景：1818项目的预期时间比实际流程提前6天
# 影响范围：仅影响1818项目的6类待处理文件的日期筛选
# 修改时间：2026-01-15

PROJECT_1818_DATE_OFFSET_DAYS = 6  # 可配置的偏移天数


def adjust_date_for_project(cell_date, project_id):
    """
    根据项目号调整日期（目前仅1818项目需要减6天）
    
    业务说明：
        1818项目的预期时间字段比实际截止日期提前6天，
        因此在日期筛选时需要将Excel中的日期减6天后再与筛选范围比较。
        
        例如：Excel中日期为2026-01-15，对于1818项目，
        实际参与筛选的日期应为2026-01-09。
    
    参数:
        cell_date: datetime对象或pandas.Timestamp，Excel单元格解析出的日期
        project_id: 项目号字符串（如 '1818', '2016' 等）
    
    返回:
        datetime对象，调整后的日期（非1818项目返回原值）
    """
    if project_id == '1818' and cell_date is not None:
        try:
            # pandas Timestamp 或 datetime 都支持减法
            return cell_date - datetime.timedelta(days=PROJECT_1818_DATE_OFFSET_DAYS)
        except Exception:
            return cell_date
    return cell_date


def get_project_date_offset(project_id):
    """
    获取项目的日期偏移天数
    
    参数:
        project_id: 项目号字符串
    
    返回:
        int: 偏移天数（正数表示减去的天数，0表示不调整）
    """
    if project_id == '1818':
        return PROJECT_1818_DATE_OFFSET_DAYS
    return 0


def is_project_with_date_adjustment(project_id):
    """
    判断项目是否需要日期调整
    
    参数:
        project_id: 项目号字符串
    
    返回:
        bool: True表示需要调整，False表示不需要
    """
    return project_id == '1818'
