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
from .util import make_task_id, make_business_id

def find_task_by_business_id(db_path: str, wal: bool, file_type: int, project_id: str, interface_id: str) -> Optional[Dict[str, Any]]:
    """
    根据业务ID查找任务（用于状态继承）
    
    返回最近一次见到的该接口的任务记录
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        file_type: 文件类型
        project_id: 项目号
        interface_id: 接口号
        
    返回:
        任务字典或None
    """
    conn = get_connection(db_path, wal)
    business_id = make_business_id(file_type, project_id, interface_id)
    
    cursor = conn.execute("""
        SELECT id, source_file, row_index, interface_time, 
               status, display_status, responsible_person,
               assigned_by, assigned_at, confirmed_by, completed_at, confirmed_at
        FROM tasks
        WHERE business_id = ?
        ORDER BY last_seen_at DESC
        LIMIT 1
    """, (business_id,))
    
    row = cursor.fetchone()
    if row:
        return {
            'id': row[0],
            'source_file': row[1],
            'row_index': row[2],
            'interface_time': row[3],
            'status': row[4],
            'display_status': row[5],
            'responsible_person': row[6],
            'assigned_by': row[7],
            'assigned_at': row[8],
            'confirmed_by': row[9],
            'completed_at': row[10],
            'confirmed_at': row[11]
        }
    return None

def should_reset_task_status(old_interface_time: str, new_interface_time: str, 
                             old_completed_val: str, new_completed_val: str) -> bool:
    """
    判断是否需要重置任务状态
    
    重置条件：
    1. 时间列（答复期限）发生变化
    2. 完成列（实际答复时间）从有值变为空
    
    不重置：
    1. 完成列从空变为有值（设计人员正常填写）
    2. 时间列和完成列都不变
    
    参数:
        old_interface_time: 旧的接口时间
        new_interface_time: 新的接口时间  
        old_completed_val: 旧的完成列值
        new_completed_val: 新的完成列值
        
    返回:
        True=需要重置，False=不需要重置
    """
    # 规范化为字符串
    old_time = str(old_interface_time).strip() if old_interface_time else ""
    new_time = str(new_interface_time).strip() if new_interface_time else ""
    old_comp = str(old_completed_val).strip() if old_completed_val else ""
    new_comp = str(new_completed_val).strip() if new_completed_val else ""
    
    # 条件1：时间列变化
    if old_time != new_time:
        return True
    
    # 条件2：完成列从有值变为空
    if old_comp and not new_comp:
        return True
    
    # 其他情况：不重置
    return False

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
    
    # 【新增】生成business_id并查询旧任务（状态继承逻辑）
    business_id = make_business_id(key['file_type'], key['project_id'], key['interface_id'])
    old_task = find_task_by_business_id(db_path, wal, key['file_type'], key['project_id'], key['interface_id'])
    
    if old_task:
        # 检查是否需要重置状态
        # 【修复】判断完成列变化的逻辑：
        # 如果Excel中完成列为空，但数据库中completed_at不为空
        # 说明完成列被删除了，需要重置状态
        new_completed_val = fields.get('_completed_col_value', '')
        old_completed_val = '有值' if old_task['completed_at'] else ''
        
        # 特殊情况：如果新完成列为空，但旧任务有completed_at
        # 说明Excel中的M列被删除了，需要重置并清除completed_at
        if not new_completed_val and old_task['completed_at']:
            # M列被删除，强制重置
            need_reset = True
            print(f"[Registry] {key['interface_id']} 完成列被删除（completed_at存在但Excel中M列为空），强制重置")
        else:
            need_reset = should_reset_task_status(
                old_task['interface_time'],
                fields.get('interface_time', ''),
                old_completed_val,
                new_completed_val
            )
        
        if need_reset:
            # 重置状态，但保留指派信息
            fields['status'] = Status.OPEN
            fields['display_status'] = '待完成' if old_task['responsible_person'] else '请指派'
            fields['completed_at'] = None
            fields['confirmed_at'] = None
            fields['confirmed_by'] = None
            
            if old_task['assigned_by'] and not fields.get('assigned_by'):
                fields['assigned_by'] = old_task['assigned_by']
                fields['assigned_at'] = old_task['assigned_at']
                fields['responsible_person'] = old_task['responsible_person']
            
            print(f"[Registry继承] {key['interface_id']} 时间变化，重置状态")
        else:
            # 继承状态（智能判断）
            # 如果新状态是默认值'待完成'且旧任务有其他状态，则继承旧状态
            # 但如果新状态是明确设置的其他值（如'待审查'），则使用新值
            current_display_status = fields.get('display_status')
            
            if current_display_status == '待完成' and old_task['display_status'] and old_task['display_status'] != '待完成':
                # 默认值'待完成'，继承旧状态
                fields['display_status'] = old_task['display_status']
                print(f"[Registry继承] {key['interface_id']} 未变化，继承状态: {old_task['display_status']}")
            elif current_display_status and current_display_status != '待完成':
                # 明确设置的其他状态（如'待审查'），使用新值，不继承
                print(f"[Registry] {key['interface_id']} 状态明确设置为: {current_display_status}，不继承")
            elif not current_display_status and old_task['display_status']:
                # 没有设置display_status，继承旧值
                fields['display_status'] = old_task['display_status']
                print(f"[Registry继承] {key['interface_id']} 继承旧状态: {old_task['display_status']}")
            
            # 继承其他状态字段
            if not fields.get('status'):
                fields['status'] = old_task['status']
            if not fields.get('completed_at'):
                fields['completed_at'] = old_task['completed_at']
            if not fields.get('confirmed_at'):
                fields['confirmed_at'] = old_task['confirmed_at']
            if not fields.get('confirmed_by'):
                fields['confirmed_by'] = old_task['confirmed_by']
            
            # 继承指派信息
            if old_task['assigned_by'] and not fields.get('assigned_by'):
                fields['assigned_by'] = old_task['assigned_by']
                fields['assigned_at'] = old_task['assigned_at']
            if old_task['responsible_person'] and not fields.get('responsible_person'):
                fields['responsible_person'] = old_task['responsible_person']
    
    status = fields.get('status', Status.OPEN)
    department = fields.get('department', '')
    interface_time = fields.get('interface_time', '')
    display_status = fields.get('display_status', '待完成')  # 【修复】确保总是有默认值
    now_str = now.isoformat()
    
    # 使用 INSERT ... ON CONFLICT 实现 upsert
    conn.execute(
        """
        INSERT INTO tasks (
            id, file_type, project_id, interface_id, source_file, row_index,
            business_id,
            department, interface_time, role, status, 
            assigned_by, assigned_at, display_status, confirmed_by, responsible_person,
            response_number, completed_at, confirmed_at,
            first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            business_id = excluded.business_id,
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
            response_number = COALESCE(excluded.response_number, response_number),
            completed_at = COALESCE(excluded.completed_at, completed_at),
            confirmed_at = COALESCE(excluded.confirmed_at, confirmed_at),
            last_seen_at = excluded.last_seen_at
        """,
        (
            tid,
            key['file_type'], 
            key['project_id'], 
            key['interface_id'], 
            key['source_file'], 
            key['row_index'],
            business_id,
            department,
            interface_time,
            fields.get('role', ''),
            status,
            fields.get('assigned_by'),
            fields.get('assigned_at'),
            display_status,
            fields.get('confirmed_by'),
            fields.get('responsible_person'),
            fields.get('response_number'),
            fields.get('completed_at'),
            fields.get('confirmed_at'),
            now_str,
            now_str
        )
    )
    conn.commit()
    
    # 【调试】验证display_status是否正确写入
    if fields.get('display_status'):
        cursor = conn.execute("SELECT display_status FROM tasks WHERE id=?", (tid,))
        row = cursor.fetchone()
        if row:
            # 【修复】不截断接口号，避免误导（之前[:20]会截断长接口号）
            print(f"[Registry调试] 任务{key.get('interface_id', '?')}写入后的display_status={row[0]}")

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
            
            # 如果已确认，返回空字符串（标记为已确认）
            if confirmed_at:
                result[tid] = ''  # 空字符串标记已确认
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
    - 遍历所有 status='open' 或 'completed' 的任务
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
    try:
        conn = get_connection(db_path, wal)
        now_str = now.isoformat()
        now_date_only = now.strftime('%Y-%m-%d')  # 只比较日期，忽略时间
        
        # 阶段1：标记消失的任务
        cursor = conn.execute("""
            SELECT id, interface_id FROM tasks
            WHERE status IN ('open', 'completed')
              AND DATE(last_seen_at) < DATE(?)
              AND missing_since IS NULL
        """, (now_str,))
        
        missing_tasks = cursor.fetchall()
        
        if missing_tasks:
            for task_id, interface_id in missing_tasks:
                conn.execute("""
                    UPDATE tasks
                    SET missing_since = ?
                    WHERE id = ?
                """, (now_str, task_id))
            
            conn.commit()
            print(f"[Registry归档] 标记{len(missing_tasks)}个消失的任务")
        
        # 阶段2：归档超期任务
        from datetime import timedelta
        cutoff_date = (now - timedelta(days=missing_keep_days)).isoformat()
        
        cursor = conn.execute("""
            SELECT id, interface_id, missing_since FROM tasks
            WHERE missing_since IS NOT NULL
              AND missing_since < ?
              AND status != 'archived'
        """, (cutoff_date,))
        
        archive_tasks = cursor.fetchall()
        
        if archive_tasks:
            for task_id, interface_id, missing_since in archive_tasks:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'archived',
                        archive_reason = 'missing_from_source'
                    WHERE id = ?
                """, (task_id,))
                
                # 写入归档事件
                write_event(db_path, wal, EventType.ARCHIVED, {
                    'task_id': task_id,
                    'interface_id': interface_id,
                    'extra': {
                        'reason': 'missing_from_source',
                        'missing_since': missing_since
                    }
                }, now)
            
            conn.commit()
            print(f"[Registry归档] 归档{len(archive_tasks)}个超过{missing_keep_days}天未见的任务")
        
    except Exception as e:
        print(f"[Registry] finalize_scan失败: {e}")
        import traceback
        traceback.print_exc()

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
            
            # 【新增】生成business_id并查询旧任务（接口号继承逻辑）
            business_id = make_business_id(key['file_type'], key['project_id'], key['interface_id'])
            old_task = find_task_by_business_id(db_path, wal, key['file_type'], key['project_id'], key['interface_id'])
            
            # 【修复】检查是否需要重置或继承
            if old_task:
                new_completed_val = fields.get('_completed_col_value', '')
                old_completed_val = '有值' if old_task['completed_at'] else ''
                
                # 【关键】优先检查完成列是否被清空（包括已确认的任务）
                if not new_completed_val and old_task['completed_at']:
                    # 完成列被删除，强制重置（即使是已确认的任务也要重置）
                    print(f"[Registry] 接口{key['interface_id']}: 完成列被清空，重置状态（old_status={old_task['status']}）")
                    fields['display_status'] = '待完成' if old_task['responsible_person'] else '请指派'
                    fields['status'] = Status.OPEN
                    # 清除完成相关字段
                    fields['completed_at'] = None
                    fields['confirmed_at'] = None
                    fields['confirmed_by'] = None
                    # 保留指派信息
                    if old_task['assigned_by']:
                        fields['assigned_by'] = old_task['assigned_by']
                        fields['assigned_at'] = old_task['assigned_at']
                        fields['responsible_person'] = old_task['responsible_person']
                
                # 【新增】如果已确认且完成列仍有值，保持确认状态
                elif old_task['status'] == Status.CONFIRMED and old_task['confirmed_at'] and new_completed_val:
                    # 已确认且完成列未被清空，保持确认状态
                    print(f"[Registry] 接口{key['interface_id']}: 已确认且完成列有值，保持确认状态")
                    fields['status'] = Status.CONFIRMED
                    fields['display_status'] = None  # 保持不显示
                    fields['confirmed_at'] = old_task['confirmed_at']
                    fields['confirmed_by'] = old_task['confirmed_by']
                    fields['completed_at'] = old_task['completed_at']
                    if old_task['assigned_by']:
                        fields['assigned_by'] = old_task['assigned_by']
                        fields['assigned_at'] = old_task['assigned_at']
                        fields['responsible_person'] = old_task['responsible_person']
                
                # 检查接口时间变化是否需要重置
                elif should_reset_task_status(old_task['interface_time'], fields.get('interface_time', ''), 
                                             old_completed_val, new_completed_val):
                    # 时间列变化，重置
                    print(f"[Registry] 接口{key['interface_id']}: 接口时间变化，重置状态")
                    fields['display_status'] = '待完成' if old_task['responsible_person'] else '请指派'
                    fields['status'] = Status.OPEN
                    if old_task['assigned_by']:
                        fields['assigned_by'] = old_task['assigned_by']
                        fields['assigned_at'] = old_task['assigned_at']
                        fields['responsible_person'] = old_task['responsible_person']
                
                # 其他情况：继承状态
                else:
                    # 继承状态
                    if fields.get('display_status') == '待完成' and old_task['display_status'] and old_task['display_status'] != '待完成':
                        fields['display_status'] = old_task['display_status']
                    if old_task['status']:
                        fields['status'] = old_task['status']
                    if old_task['completed_at']:
                        fields['completed_at'] = old_task['completed_at']
                    if old_task['confirmed_at']:
                        fields['confirmed_at'] = old_task['confirmed_at']
                        fields['confirmed_by'] = old_task['confirmed_by']
                    if old_task['assigned_by']:
                        fields['assigned_by'] = old_task['assigned_by']
                        fields['assigned_at'] = old_task['assigned_at']
                        fields['responsible_person'] = old_task['responsible_person']
            
            status = fields.get('status', Status.OPEN)
            department = fields.get('department', '')
            interface_time = fields.get('interface_time', '')
            role = fields.get('role', '')
            display_status = fields.get('display_status', '待完成')  # 【修复】提供默认值
            responsible_person = fields.get('responsible_person')  # 从Excel中读取
            
            # 【修复】从fields获取confirmed相关字段
            confirmed_at = fields.get('confirmed_at')
            confirmed_by = fields.get('confirmed_by')
            assigned_by = fields.get('assigned_by')
            assigned_at = fields.get('assigned_at')
            completed_at = fields.get('completed_at')
            
            conn.execute(
                """
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file, row_index,
                    business_id,
                    department, interface_time, role, status, display_status,
                    first_seen_at, last_seen_at,
                    assigned_by, assigned_at, responsible_person, confirmed_by,
                    completed_at, confirmed_at, response_number
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    business_id = excluded.business_id,
                    department = excluded.department,
                    interface_time = excluded.interface_time,
                    role = excluded.role,
                    status = excluded.status,
                    display_status = excluded.display_status,
                    last_seen_at = excluded.last_seen_at,
                    assigned_by = COALESCE(excluded.assigned_by, assigned_by),
                    assigned_at = COALESCE(excluded.assigned_at, assigned_at),
                    responsible_person = CASE
                        WHEN assigned_by IS NOT NULL THEN responsible_person
                        ELSE COALESCE(excluded.responsible_person, responsible_person)
                    END,
                    confirmed_by = excluded.confirmed_by,
                    completed_at = excluded.completed_at,
                    confirmed_at = excluded.confirmed_at,
                    response_number = COALESCE(excluded.response_number, response_number)
                """,
                (
                    tid,
                    key['file_type'], 
                    key['project_id'], 
                    key['interface_id'], 
                    key['source_file'], 
                    key['row_index'],
                    business_id,
                    department,
                    interface_time,
                    role,
                    status,
                    display_status,
                    now_str,
                    now_str,
                    assigned_by,
                    assigned_at,
                    responsible_person,
                    confirmed_by,
                    completed_at,
                    confirmed_at,
                    fields.get('response_number')
                )
            )
            count += 1
        
        conn.commit()
        return count
        
    except Exception as e:
        conn.rollback()
        print(f"[Registry] 批量upsert失败: {e}")
        raise


def query_task_history(db_path: str, wal: bool, project_id: str, interface_id: str, file_type: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    查询任务历史记录
    
    根据项目号和接口号查询所有历史记录（支持文件类型过滤）
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        project_id: 项目号
        interface_id: 接口号
        file_type: 文件类型（可选，None表示查询所有类型）
        
    返回:
        历史记录列表（按创建时间倒序）
    """
    conn = get_connection(db_path, wal)
    
    try:
        if file_type:
            # 精确查询特定文件类型
            business_id = f"{file_type}|{project_id}|{interface_id}"
            sql = """
                SELECT * FROM tasks 
                WHERE business_id = ? 
                ORDER BY first_seen_at DESC
            """
            params = (business_id,)
        else:
            # 查询所有文件类型
            business_id_pattern = f"%|{project_id}|{interface_id}"
            sql = """
                SELECT * FROM tasks 
                WHERE business_id LIKE ? 
                ORDER BY first_seen_at DESC
            """
            params = (business_id_pattern,)
        
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        
        # 转换为字典列表
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in rows:
            task = dict(zip(columns, row))
            results.append(task)
        
        return results
        
    except Exception as e:
        print(f"[Registry] 查询历史失败: {e}")
        import traceback
        traceback.print_exc()
        return []

