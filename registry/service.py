"""
核心业务逻辑模块

提供任务创建更新、状态流转、事件记录等核心功能。
"""
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List
from .db import get_connection
from .models import Status, EventType
from .util import make_task_id

def upsert_task(db_path: str, wal: bool, key: Dict[str, Any], fields: Dict[str, Any], now: datetime) -> None:
    """
    创建或更新任务
    
    按唯一键(file_type, project_id, interface_id, source_file, row_index) upsert 任务。
    - 首次见到：创建任务，记录 first_seen_at 和 last_seen_at
    - 再次见到：更新 last_seen_at、department、interface_time
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        key: 任务关键字段 {'file_type', 'project_id', 'interface_id', 'source_file', 'row_index'}
        fields: 任务附加字段 {'department', 'interface_time', 'status'(可选)}
        now: 当前时间
    """
    conn = get_connection(db_path, wal)
    tid = make_task_id(
        key['file_type'], 
        key['project_id'], 
        key['interface_id'], 
        key['source_file'], 
        key['row_index']
    )
    
    status = fields.get('status', Status.OPEN)
    department = fields.get('department', '')
    interface_time = fields.get('interface_time', '')
    now_str = now.isoformat()
    
    # 使用 INSERT ... ON CONFLICT 实现 upsert
    conn.execute(
        """
        INSERT INTO tasks (
            id, file_type, project_id, interface_id, source_file, row_index,
            department, interface_time, role, status, 
            assigned_by, assigned_at, display_status, confirmed_by, responsible_person,
            first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            department = excluded.department,
            interface_time = excluded.interface_time,
            role = excluded.role,
            assigned_by = COALESCE(excluded.assigned_by, assigned_by),
            assigned_at = COALESCE(excluded.assigned_at, assigned_at),
            display_status = CASE 
                WHEN excluded.display_status IS NOT NULL THEN excluded.display_status
                WHEN display_status IS NULL THEN excluded.display_status
                ELSE display_status
            END,
            confirmed_by = COALESCE(excluded.confirmed_by, confirmed_by),
            responsible_person = COALESCE(excluded.responsible_person, responsible_person),
            last_seen_at = excluded.last_seen_at
        """,
        (
            tid,
            key['file_type'], 
            key['project_id'], 
            key['interface_id'], 
            key['source_file'], 
            key['row_index'],
            department,
            interface_time,
            fields.get('role', ''),  # 角色信息
            status,
            fields.get('assigned_by'),  # 指派人
            fields.get('assigned_at'),  # 指派时间
            fields.get('display_status'),  # 显示状态
            fields.get('confirmed_by'),  # 确认人
            fields.get('responsible_person'),  # 责任人
            now_str,  # first_seen_at (只在INSERT时设置)
            now_str   # last_seen_at (INSERT和UPDATE都会更新)
        )
    )
    conn.commit()

def write_event(db_path: str, wal: bool, event_type: str, payload: Dict[str, Any], now: datetime) -> None:
    """
    写入事件记录
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        event_type: 事件类型（EventType枚举）
        payload: 事件数据 {'file_type', 'project_id', 'interface_id'(可选), 'source_file'(可选), 'row_index'(可选), 'extra'(可选)}
        now: 当前时间
    """
    conn = get_connection(db_path, wal)
    
    # 提取字段
    file_type = payload.get('file_type')
    project_id = payload.get('project_id')
    interface_id = payload.get('interface_id', '')
    source_file = payload.get('source_file', '')
    row_index = payload.get('row_index')
    extra = payload.get('extra')
    
    # extra转为JSON字符串
    extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
    
    conn.execute(
        """
        INSERT INTO events (ts, event, file_type, project_id, interface_id, source_file, row_index, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now.isoformat(),
            event_type,
            file_type,
            project_id,
            interface_id,
            source_file,
            row_index,
            extra_json
        )
    )
    conn.commit()

def mark_completed(db_path: str, wal: bool, key: Dict[str, Any], now: datetime) -> None:
    """
    标记任务为已完成
    
    将任务状态从 open 更新为 completed，并记录 completed_at
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        key: 任务关键字段
        now: 当前时间
    """
    conn = get_connection(db_path, wal)
    tid = make_task_id(
        key['file_type'], 
        key['project_id'], 
        key['interface_id'], 
        key['source_file'], 
        key['row_index']
    )
    
    conn.execute(
        "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
        (Status.COMPLETED, now.isoformat(), tid)
    )
    conn.commit()

def mark_confirmed(db_path: str, wal: bool, key: Dict[str, Any], now: datetime, confirmed_by: str = None) -> None:
    """
    标记任务为已确认
    
    将任务状态从 completed 更新为 confirmed，并记录 confirmed_at
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        key: 任务关键字段
        now: 当前时间
        confirmed_by: 确认人姓名（可选）
    """
    conn = get_connection(db_path, wal)
    tid = make_task_id(
        key['file_type'], 
        key['project_id'], 
        key['interface_id'], 
        key['source_file'], 
        key['row_index']
    )
    
    # 【状态提醒】确认时清除display_status和设置confirmed_by
    conn.execute(
        "UPDATE tasks SET status = ?, confirmed_at = ?, display_status = NULL, confirmed_by = ? WHERE id = ?",
        (Status.CONFIRMED, now.isoformat(), confirmed_by, tid)
    )
    conn.commit()

def get_display_status(db_path: str, wal: bool, task_keys: List[Dict[str, Any]], current_user_roles: List[str] = None) -> Dict[str, str]:
    """
    批量查询任务的显示状态（用于UI显示）
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        task_keys: 任务key列表，每个key包含 file_type, project_id, interface_id, source_file, row_index, interface_time
        current_user_roles: 当前用户角色列表（如["设计人员", "1818接口工程师"]）
    
    返回:
        Dict[task_id, display_status_text]: 任务ID到显示文本的映射
        例如: {"task_abc123": "📌 待完成", "task_def456": "⏳ 待审查"}
    """
    if not task_keys:
        return {}
    
    conn = get_connection(db_path, wal)
    result = {}
    
    # 判断用户角色类型
    is_designer = False
    is_superior = False
    if current_user_roles:
        for role in current_user_roles:
            if "设计人员" in role:
                is_designer = True
            if any(keyword in role for keyword in ['所领导', '室主任', '接口工程师']):
                is_superior = True
    
    # 导入延期判断函数
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from date_utils import is_date_overdue
    except:
        # 如果导入失败，使用简单判断
        def is_date_overdue(date_str):
            return False
    
    try:
        for key in task_keys:
            tid = make_task_id(
                key['file_type'],
                key['project_id'],
                key['interface_id'],
                key['source_file'],
                key['row_index']
            )
            
            # 获取接口时间（用于判断是否延期）
            interface_time = key.get('interface_time', '')
            is_overdue = is_date_overdue(interface_time) if interface_time and interface_time != '-' else False
            
            # 查询任务信息
            cursor = conn.execute(
                """
                SELECT status, display_status, assigned_by, role, confirmed_at, responsible_person
                FROM tasks
                WHERE id = ?
                """,
                (tid,)
            )
            row = cursor.fetchone()
            
            if not row:
                # 任务不存在，不显示状态
                continue
            
            status, display_status, assigned_by, role, confirmed_at, responsible_person = row
            
            # 如果已确认，不显示状态
            if confirmed_at:
                continue
            
            # 如果有预设的display_status，根据用户角色调整显示
            if display_status:
                if display_status == '待完成':
                    # 【新增】判断是否需要指派（没有责任人且是未完成状态）
                    if not responsible_person and is_superior:
                        # 上级角色看到未指派的待完成任务：显示"请指派"
                        display_text = '请指派'
                    # 【需求2】上级角色看到"待设计人员完成"，设计人员看到"待完成"
                    elif is_superior and not is_designer:
                        # 纯上级角色
                        display_text = '待设计人员完成'
                    elif is_designer and is_superior:
                        # 【需求3】重叠角色：显示"待完成"
                        display_text = '待完成'
                    else:
                        # 设计人员或其他角色
                        display_text = '待完成'
                else:
                    # 待确认状态保持不变（不受责任人影响）
                    display_text = display_status
                
                # 【新增】如果任务延期，在状态前加"（已延期）"
                if is_overdue:
                    display_text = f"（已延期）{display_text}"
                
                # 添加Emoji前缀
                emoji_map = {
                    '待完成': '📌',
                    '待设计人员完成': '📌',
                    '请指派': '❗',
                    '待审查': '⏳',
                    '待指派人审查': '⏳',
                    '待确认（可自行确认）': '⏳'
                }
                
                # 如果有"（已延期）"前缀，去掉前缀后查找emoji
                emoji_key = display_text.replace('（已延期）', '')
                emoji = emoji_map.get(emoji_key, '')
                if emoji:
                    result[tid] = f"{emoji} {display_text}"
                else:
                    result[tid] = display_text
        
        return result
        
    except Exception as e:
        print(f"[Registry] get_display_status内部错误: {e}")
        return {}

def finalize_scan(db_path: str, wal: bool, now: datetime, missing_keep_days: int) -> None:
    """
    完成扫描，标记缺失任务并归档超期项
    
    阶段1：标记消失
    - 遍历所有 status='open' 的任务
    - 如果 last_seen_at 不是本次扫描时间，且 missing_since 为空
    - 则标记 missing_since = 当前时间
    
    阶段2：自动归档
    - 遍历所有已标记 missing_since 的任务
    - 如果距离现在超过 missing_keep_days 天
    - 则归档：status='archived', archive_reason='missing_from_source'
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        now: 当前扫描时间
        missing_keep_days: 消失后保持天数（超过则归档）
    """
    # 注意：这是阶段1的简化实现
    # 完整的归档逻辑将在阶段2实现
    # 当前仅提供接口骨架，不执行实际操作
    pass

def batch_upsert_tasks(db_path: str, wal: bool, tasks_data: list, now: datetime) -> int:
    """
    批量创建或更新任务（带事务优化）
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        tasks_data: 任务数据列表，每项包含 {'key': {...}, 'fields': {...}}
        now: 当前时间
        
    返回:
        成功upsert的任务数量
    """
    if not tasks_data:
        return 0
    
    conn = get_connection(db_path, wal)
    now_str = now.isoformat()
    count = 0
    
    try:
        # 开启事务
        conn.execute("BEGIN TRANSACTION")
        
        for task_data in tasks_data:
            key = task_data['key']
            fields = task_data['fields']
            
            tid = make_task_id(
                key['file_type'], 
                key['project_id'], 
                key['interface_id'], 
                key['source_file'], 
                key['row_index']
            )
            
            status = fields.get('status', Status.OPEN)
            department = fields.get('department', '')
            interface_time = fields.get('interface_time', '')
            role = fields.get('role', '')
            display_status = fields.get('display_status')
            responsible_person = fields.get('responsible_person')  # 从Excel中读取
            
            conn.execute(
                """
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file, row_index,
                    department, interface_time, role, status, display_status,
                    first_seen_at, last_seen_at,
                    assigned_by, assigned_at, responsible_person, confirmed_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    department = excluded.department,
                    interface_time = excluded.interface_time,
                    role = excluded.role,
                    display_status = COALESCE(display_status, excluded.display_status),
                    last_seen_at = excluded.last_seen_at,
                    assigned_by = COALESCE(excluded.assigned_by, assigned_by),
                    assigned_at = COALESCE(excluded.assigned_at, assigned_at),
                    responsible_person = CASE
                        WHEN assigned_by IS NOT NULL THEN responsible_person
                        ELSE COALESCE(excluded.responsible_person, responsible_person)
                    END,
                    confirmed_by = COALESCE(excluded.confirmed_by, confirmed_by)
                """,
                (
                    tid,
                    key['file_type'], 
                    key['project_id'], 
                    key['interface_id'], 
                    key['source_file'], 
                    key['row_index'],
                    department,
                    interface_time,
                    role,
                    status,
                    display_status,
                    now_str,
                    now_str,
                    None,  # assigned_by (INSERT时为NULL，除非通过指派)
                    None,  # assigned_at (INSERT时为NULL，除非通过指派)
                    responsible_person,  # 从Excel中读取的责任人
                    None   # confirmed_by (INSERT时为NULL)
                )
            )
            count += 1
        
        conn.commit()
        return count
        
    except Exception as e:
        conn.rollback()
        print(f"[Registry] 批量upsert失败: {e}")
        raise

