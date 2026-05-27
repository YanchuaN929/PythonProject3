# -*- coding: utf-8 -*-
"""
科室参数化配置模块

通过 config.json 中的 department_profile / department_profiles 实现多科室支持。
所有科室相关的硬编码参数统一从此模块获取。

使用示例::

    from utils.dept_config import get_department_codes, get_organization_filter

    codes = get_department_codes()          # ["25C1", "25C2", "25C3"]
    org   = get_organization_filter()       # "河北分公司-建筑结构所"
"""

import json
import os
import sys

_profile_cache = None


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _get_config_path():
    """获取项目根目录 config.json 的路径（兼容 PyInstaller 打包环境）"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, "config.json")
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.json",
    )


def _default_profile():
    """默认参数族（建筑结构所）— 当 config.json 无 department_profiles 时的后备值"""
    return {
        "organization_filter": "河北分公司-建筑结构所",
        "organization_filter_file6": "河北分公司.建筑结构所",
        "department_codes": ["25C1", "25C2", "25C3"],
        "department_code_mapping": {
            "25C1": "结构一室",
            "25C2": "结构二室",
            "25C3": "建筑总图室",
        },
        "director_role_mapping": {
            "一室主任": "结构一室",
            "二室主任": "结构二室",
            "建筑总图室主任": "建筑总图室",
        },
        "role_export_days": {
            "一室主任": 7,
            "二室主任": 7,
            "建筑总图室主任": 7,
            "所领导": 2,
            "管理员": None,
            "设计人员": None,
        },
        "projects": ["1818", "1907", "1915", "1916", "2016", "2026", "2306", "2416"],
        "projects_standard_filter": ["1907", "2016"],
        "role_table_file": "excel_bin/姓名角色表.xlsx",
        "default_folder_path": (
            r"//10.102.2.7/文件服务器/建筑结构所"
            r"/接口文件/各项目内外部接口手册"
        ),
        "watermark_text": "建筑结构所",
    }


# ---------------------------------------------------------------------------
# 核心加载
# ---------------------------------------------------------------------------

def get_active_profile():
    """获取当前激活的科室参数族（带缓存，首次调用时从 config.json 加载）"""
    global _profile_cache  # noqa: PLW0603
    if _profile_cache is not None:
        return _profile_cache

    config_path = _get_config_path()
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            profile_name = config.get("department_profile", "建筑结构所")
            profiles = config.get("department_profiles", {})
            if profile_name in profiles:
                profile = profiles[profile_name]
                # 用默认值补全缺失字段
                default = _default_profile()
                for k, v in default.items():
                    profile.setdefault(k, v)
                _profile_cache = profile
                return profile
    except Exception as e:
        print(f"[dept_config] 加载科室参数族失败: {e}")

    _profile_cache = _default_profile()
    return _profile_cache


def reload_profile():
    """强制重新加载（配置文件变更后调用）"""
    global _profile_cache  # noqa: PLW0603
    _profile_cache = None
    return get_active_profile()


# ---------------------------------------------------------------------------
# 便捷访问函数 —— 筛选参数
# ---------------------------------------------------------------------------

def get_department_codes():
    """获取科室编码列表，如 ``["25C1", "25C2", "25C3"]``"""
    return get_active_profile()["department_codes"]


def get_department_code_mapping():
    """获取编码→科室名称映射，如 ``{"25C1": "结构一室", ...}``"""
    return get_active_profile()["department_code_mapping"]


def get_department_names():
    """获取科室名称列表（从编码映射值去重保序）

    如 ``["结构一室", "结构二室", "建筑总图室"]``
    """
    return list(dict.fromkeys(get_active_profile()["department_code_mapping"].values()))


def get_organization_filter():
    """获取单位筛选关键词（横线版），如 ``"河北分公司-建筑结构所"``

    用于文件2（contains）、文件3（startswith）、文件4（startswith）。
    """
    return get_active_profile()["organization_filter"]


def get_organization_filter_file6():
    """获取单位筛选关键词（点号版），如 ``"河北分公司.建筑结构所"``

    仅用于文件6（contains）。
    """
    return get_active_profile()["organization_filter_file6"]


# ---------------------------------------------------------------------------
# 便捷访问函数 —— 角色参数
# ---------------------------------------------------------------------------

def get_director_role_mapping():
    """获取室主任角色→科室映射，如 ``{"一室主任": "结构一室", ...}``"""
    return get_active_profile()["director_role_mapping"]


def get_director_roles():
    """获取室主任角色名称列表，如 ``["一室主任", "二室主任", "建筑总图室主任"]``"""
    return list(get_active_profile()["director_role_mapping"].keys())


def get_superior_keywords():
    """获取上级角色关键词列表（室主任角色 + 通用上级角色）"""
    return get_director_roles() + ["所长", "所领导", "接口工程师", "管理员"]


def get_time_window_roles():
    """获取需要时间窗口过滤的角色集合（室主任 + 所领导）"""
    return set(get_director_roles() + ["所领导"])


def get_use_workdays_roles():
    """获取使用工作日计算的角色列表（室主任 + 所领导）"""
    return get_director_roles() + ["所领导"]


# ---------------------------------------------------------------------------
# 便捷访问函数 —— UI / 路径
# ---------------------------------------------------------------------------

def get_default_folder_path():
    """获取默认数据文件夹路径"""
    return get_active_profile().get("default_folder_path", "")


def get_watermark_text():
    """获取水印显示文本，如 ``"建筑结构所"``"""
    return get_active_profile().get("watermark_text", "")


def get_projects():
    """获取当前科室参数族的项目号列表

    返回示例::

        ["1818", "1907", "1915", "1916", "2016", "2026", "2306", "2416"]
    """
    return get_active_profile().get("projects", [])


def get_projects_standard_filter():
    """获取使用标准筛选逻辑（不排除 process3）的项目号列表

    用于 ``core/main.py`` 中文件2的筛选分支判断。
    返回示例::

        ["1907", "2016"]
    """
    return get_active_profile().get("projects_standard_filter", ["1907", "2016"])


def get_role_table_file():
    """获取当前科室参数族的姓名角色表文件路径

    返回示例::

        "excel_bin/姓名角色表.xlsx"
    """
    return get_active_profile().get("role_table_file", "excel_bin/姓名角色表.xlsx")


def get_role_export_days():
    """获取角色→导出天数映射

    从当前科室参数族的 ``role_export_days`` 字段读取。
    返回示例::

        {"一室主任": 7, "二室主任": 7, "建筑总图室主任": 7,
         "所领导": 2, "管理员": None, "设计人员": None}

    值为 ``None`` 表示该角色无天数限制。
    """
    return get_active_profile().get("role_export_days", {})


def get_help_section_map():
    """获取角色→帮助章节ID映射

    通用角色（设计人员、所领导、管理员）使用固定映射；
    所有室主任角色统一映射到 ``'3-室主任使用指南'``。
    """
    mapping = {
        "设计人员": "2-设计人员使用指南",
        "所领导": "4-所领导使用指南",
        "管理员": "5-管理员使用指南",
    }
    for role in get_director_roles():
        mapping[role] = "3-室主任使用指南"
    return mapping


# ---------------------------------------------------------------------------
# 辅助匹配函数 —— 供 core/main.py 使用
# ---------------------------------------------------------------------------

def map_code_to_department(cell_str):
    """根据单元格文本匹配科室编码并返回科室名称

    用于文件1（H列）、文件5（G列）的编码→科室映射。
    例如: ``"...25C1..."`` → ``"结构一室"``

    返回:
        匹配的科室名称；未匹配返回空字符串。
    """
    mapping = get_department_code_mapping()
    for code, dept_name in mapping.items():
        if code in cell_str:
            return dept_name
    return ""


def match_department_name(cell_str):
    """根据单元格文本匹配科室名称

    用于文件2（I列）、文件3（AO列）、文件4（AG列）的科室名称提取。
    例如: ``"河北分公司-建筑结构所-结构一室"`` → ``"结构一室"``

    返回:
        匹配的科室名称；未匹配返回原始文本。
    """
    for dept_name in get_department_names():
        if dept_name in cell_str:
            return dept_name
    return cell_str


def contains_department_code(cell_str):
    """检查单元格文本是否包含任一科室编码

    用于文件1（H列）、文件2（I列）、文件5（G列）的行筛选。
    """
    for code in get_department_codes():
        if code in cell_str:
            return True
    return False
