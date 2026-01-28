"""
工具函数模块

提供task_id生成、字段提取等辅助功能。
"""
import hashlib
import os
import pandas as pd
from datetime import datetime
from typing import Dict, Any

def make_task_id(file_type: int, project_id: str, interface_id: str, source_file: str, row_index: int) -> str:
    """
    生成任务唯一ID
    
    使用SHA1哈希确保唯一性，避免主键冲突
    
    参数:
        file_type: 文件类型（1-6）
        project_id: 项目号
        interface_id: 接口号
        source_file: 源文件basename
        row_index: 原始行号
        
    返回:
        40字符的SHA1哈希字符串
    """
    # 确保source_file只取basename
    source_basename = os.path.basename(source_file) if source_file else ""
    
    # 构造唯一标识字符串
    key_str = f"{file_type}|{project_id}|{interface_id}|{source_basename}|{row_index}"
    
    # 生成SHA1哈希
    return hashlib.sha1(key_str.encode('utf-8')).hexdigest()

def make_business_id(file_type: int, project_id: str, interface_id: str) -> str:
    """
    生成业务ID（用于跨文件匹配接口）
    
    业务ID不包含source_file和row_index，只基于业务含义：
    - file_type: 文件类型
    - project_id: 项目号
    - interface_id: 接口号
    
    参数:
        file_type: 文件类型（1-6）
        project_id: 项目号
        interface_id: 接口号
        
    返回:
        业务ID字符串，格式：file_type|project_id|interface_id
    """
    return f"{file_type}|{project_id}|{interface_id}"

def extract_interface_id(df_row: pd.Series, file_type: int) -> str:
    """
    从DataFrame行中提取接口号
    
    根据文件类型映射对应的列：
    - 文件1: A列(0)
    - 文件2: R列(17)
    - 文件3: C列(2)
    - 文件4: E列(4)
    - 文件5: A列(0)
    - 文件6: E列(4)
    
    参数:
        df_row: DataFrame的一行（pd.Series）
        file_type: 文件类型（1-6）
        
    返回:
        接口号字符串（去除前后空格）
    """
    # 接口号列映射（列索引）
    interface_col_map = {
        1: 0,   # A列
        2: 17,  # R列
        3: 2,   # C列
        4: 4,   # E列
        5: 0,   # A列
        6: 4,   # E列
    }
    
    # 首先尝试使用"接口号"列名（如果DataFrame已经处理过）
    if "接口号" in df_row.index:
        interface_id = str(df_row["接口号"]).strip()
        # 【修复】去除角色后缀，例如"S-SA---1JT-01-25C1-25E6(设计人员)" -> "S-SA---1JT-01-25C1-25E6"
        import re
        interface_id = re.sub(r'\([^)]*\)$', '', interface_id).strip()
        return interface_id
    
    # 否则使用列索引
    col_idx = interface_col_map.get(file_type)
    if col_idx is not None and col_idx < len(df_row):
        interface_id = str(df_row.iloc[col_idx]).strip()
        # 【修复】去除角色后缀
        import re
        interface_id = re.sub(r'\([^)]*\)$', '', interface_id).strip()
        return interface_id
    
    # 兜底：返回空字符串
    return ""

def extract_project_id(df_row: pd.Series, file_type: int) -> str:
    """
    从DataFrame行中提取项目号
    
    对于文件1-6，项目号通常从文件名中提取，存储在DataFrame的"项目号"列中
    
    参数:
        df_row: DataFrame的一行（pd.Series）
        file_type: 文件类型（1-6）
        
    返回:
        项目号字符串（去除前后空格）
    """
    # 首先尝试使用"项目号"列名
    if "项目号" in df_row.index:
        project_id = str(df_row["项目号"]).strip()
    elif "source_file" in df_row.index:
        # 尝试从source_file列提取项目号
        source_file = str(df_row["source_file"])
        import re
        match = re.search(r'(\d{4})', source_file)
        project_id = match.group(1) if match else ""
    else:
        # 【修复】对于原始Excel行（使用iloc获取的），项目号信息不在行数据中
        # 需要从外部传入，这里返回空由调用方处理
        project_id = ""
    
    # 【修复】删除文件6的"未知项目"特殊处理，保持与normalize_project_id一致
    # 避免business_id不一致导致重复记录
    return project_id

def extract_department(df_row: pd.Series) -> str:
    """
    从DataFrame行中提取部门/科室信息
    
    参数:
        df_row: DataFrame的一行（pd.Series）
        
    返回:
        部门/科室字符串（去除前后空格）
    """
    # 优先查找"科室"列（常用）
    if "科室" in df_row.index:
        dept = str(df_row["科室"]).strip()
        if dept and dept.lower() not in ['nan', 'none', '']:
            return dept
    
    # 其次查找"部门"列
    if "部门" in df_row.index:
        dept = str(df_row["部门"]).strip()
        if dept and dept.lower() not in ['nan', 'none', '']:
            return dept
    
    return ""

def extract_completed_column_value(df_row: pd.Series, file_type: int) -> str:
    """
    从DataFrame行中提取完成列的值（用于判断是否已填写回文单号）
    
    根据文件类型映射对应的列：
    - 文件1: M列（索引12）
    - 文件2: N列（索引13）
    - 文件3: Q列（索引16）或T列（索引19）
    - 文件4: V列（索引21）
    - 文件5: N列（索引13）
    - 文件6: J列（索引9）
    
    参数:
        df_row: DataFrame的一行
        file_type: 文件类型（1-6）
        
    返回:
        列值字符串（去除前后空格），如果为空返回空字符串
    """
    col_map = {
        1: 12,   # M列
        2: 13,   # N列
        3: (16, 19),  # Q列或T列（返回两者中任一有值的）
        4: 21,   # V列
        5: 13,   # N列
        6: 9,    # J列
    }
    
    col_idx = col_map.get(file_type)
    if col_idx is None:
        return ""
    
    # 文件3特殊处理（Q列或T列）
    if file_type == 3 and isinstance(col_idx, tuple):
        q_val = df_row.iloc[col_idx[0]] if col_idx[0] < len(df_row) else None
        t_val = df_row.iloc[col_idx[1]] if col_idx[1] < len(df_row) else None
        
        q_str = str(q_val).strip() if pd.notna(q_val) else ""
        t_str = str(t_val).strip() if pd.notna(t_val) else ""
        
        # 返回非空的那个，都非空则返回Q列
        return q_str if q_str else t_str
    
    # 其他文件类型
    if col_idx < len(df_row):
        val = df_row.iloc[col_idx]
        return str(val).strip() if pd.notna(val) else ""
    
    return ""

def extract_interface_time(df_row: pd.Series) -> str:
    """
    从DataFrame行中提取接口时间
    
    参数:
        df_row: DataFrame的一行（pd.Series）
        
    返回:
        接口时间字符串（mm.dd 或 yyyy.mm.dd 格式）
    """
    if "接口时间" in df_row.index:
        time_val = df_row["接口时间"]
        if pd.notna(time_val):
            return str(time_val).strip()
    return ""

def normalize_project_id(pid: str, file_type: int) -> str:
    """
    规范化项目号
    
    参数:
        pid: 原始项目号
        file_type: 文件类型
        
    返回:
        规范化后的项目号
    """
    pid = str(pid).strip() if pid else ""
    return pid

def get_source_basename(path: str) -> str:
    """
    获取文件路径的basename
    
    参数:
        path: 文件路径
        
    返回:
        文件名（不含路径）
    """
    if not path:
        return ""
    return os.path.basename(path)

def safe_now() -> datetime:
    """
    获取当前时间（封装以便测试）
    
    返回:
        当前datetime对象
    """
    return datetime.now()

def build_task_key_from_row(df_row: pd.Series, file_type: int, source_file: str) -> Dict[str, Any]:
    """
    从DataFrame行构建任务关键字段字典
    
    参数:
        df_row: DataFrame的一行
        file_type: 文件类型
        source_file: 源文件路径
        
    返回:
        包含file_type, project_id, interface_id, source_file, row_index的字典
    """
    # 提取行号
    row_index = int(df_row.get("原始行号", 0)) if "原始行号" in df_row.index else 0
    
    return {
        'file_type': file_type,
        'project_id': normalize_project_id(extract_project_id(df_row, file_type), file_type),
        'interface_id': extract_interface_id(df_row, file_type),
        'source_file': get_source_basename(source_file),
        'row_index': row_index,
    }

def extract_role(value: str) -> str:
    """
    从字符串中提取括号内的角色信息
    
    例如：
    - "S-SA---1JT-01-25C1-25E6(设计人员)" -> "设计人员"
    - "S-SA---1JT-01-25C1-25E6(接口工程师)" -> "接口工程师"
    - "S-SA---1JT-01-25C1-25E6" -> ""
    
    参数:
        value: 可能包含角色后缀的字符串
        
    返回:
        括号内的角色信息，如果没有则返回空字符串
    """
    import re
    match = re.search(r'\(([^)]+)\)$', value)
    return match.group(1) if match else ""

def build_task_fields_from_row(df_row: pd.Series, file_type: int = None) -> Dict[str, Any]:
    """
    从DataFrame行提取任务附加字段
    
    参数:
        df_row: DataFrame的一行
        file_type: 文件类型（1-6），用于提取完成列值
        
    返回:
        包含department, interface_time, role等字段的字典
    """
    # 提取角色信息（从接口号或角色来源列）
    role = ""
    if "角色来源" in df_row.index:
        role = str(df_row["角色来源"]).strip()
    elif "接口号" in df_row.index:
        # 如果接口号包含角色后缀，提取它
        role = extract_role(str(df_row["接口号"]))
    
    # 【新增】提取Excel中的责任人列（如果存在）
    # 这样即使不通过指派功能，Excel中手动填写的责任人也会被同步到数据库
    responsible_person = None
    if "责任人" in df_row.index:
        resp = str(df_row["责任人"]).strip()
        # 过滤无效值
        if resp and resp.lower() not in ['nan', 'none', '无', '']:
            responsible_person = resp
    
    fields = {
        'department': extract_department(df_row),
        'interface_time': extract_interface_time(df_row),
        'role': role,
        'display_status': '待完成',
    }
    
    # 只有当Excel中有责任人时才添加此字段
    if responsible_person:
        fields['responsible_person'] = responsible_person
    
    # 【新增】提取完成列的值（用于状态重置判断）
    if file_type:
        completed_val = extract_completed_column_value(df_row, file_type)
        fields['_completed_col_value'] = completed_val
    
    return fields

