"""
钩子API模块

提供供现有程序调用的统一钩子接口，所有钩子内部捕获异常，不向外抛出。
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
from .config import load_config
from .service import upsert_task, write_event, mark_completed, mark_confirmed, finalize_scan, batch_upsert_tasks
from .models import EventType, Status
from .util import (
    build_task_key_from_row, 
    build_task_fields_from_row,
    get_source_basename,
    safe_now,
    normalize_project_id
)

# 【多用户协作】全局数据文件夹路径，用于确定共享数据库位置
_DATA_FOLDER = None

def set_data_folder(folder_path: str):
    """
    设置数据文件夹路径（用于多用户协作）
    
    应该在程序启动时调用，传入公共盘的数据文件夹路径。
    数据库将自动创建在该文件夹下的.registry子目录中。
    
    参数:
        folder_path: 数据文件夹的绝对路径
    """
    global _DATA_FOLDER
    _DATA_FOLDER = folder_path
    print(f"[Registry] 数据文件夹已设置: {folder_path}")

def get_display_status(task_keys: List[Dict[str, Any]], current_user_roles_str: str = None) -> Dict[str, str]:
    """
    批量查询任务的显示状态（用于UI显示）
    
    参数:
        task_keys: 任务key列表，每个key包含 file_type, project_id, interface_id, source_file, row_index, interface_time
        current_user_roles_str: 当前用户角色列表（逗号分隔，如"设计人员,1818接口工程师"）
    
    返回:
        Dict[task_id, display_status_text]: 任务ID到显示文本的映射
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return {}
        
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        # 解析用户角色列表
        user_roles = []
        if current_user_roles_str:
            user_roles = [r.strip() for r in current_user_roles_str.split(',') if r.strip()]
        
        from .service import get_display_status as service_get_display_status
        return service_get_display_status(db_path, wal, task_keys, user_roles)
        
    except Exception as e:
        print(f"[Registry] get_display_status 失败: {e}")
        import traceback
        traceback.print_exc()
        return {}

def _cfg():
    """加载配置（内部辅助函数）"""
    return load_config(data_folder=_DATA_FOLDER)

def _enabled(cfg: dict) -> bool:
    """检查registry是否启用（内部辅助函数）"""
    return bool(cfg.get('registry_enabled', True))

def on_process_done(
    file_type: int, 
    project_id: str, 
    source_file: str, 
    result_df: pd.DataFrame, 
    now: Optional[datetime] = None
) -> None:
    """
    处理完成钩子
    
    当某类文件处理完成后调用，逐行upsert任务到数据库
    
    参数:
        file_type: 文件类型（1-6）
        project_id: 项目号
        source_file: 源文件路径
        result_df: 处理结果DataFrame
        now: 当前时间（可选，默认为当前系统时间）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        if result_df is None or result_df.empty:
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        # 批量构造任务数据
        tasks_data = []
        for _, row in result_df.iterrows():
            key = build_task_key_from_row(row, file_type, source_file)
            fields = build_task_fields_from_row(row, file_type)  # 【修改】传递file_type
            tasks_data.append({'key': key, 'fields': fields})
        
        # 批量upsert
        count = batch_upsert_tasks(db_path, wal, tasks_data, now)
        
        # 写入process_done事件
        write_event(db_path, wal, EventType.PROCESS_DONE, {
            'file_type': file_type,
            'project_id': normalize_project_id(project_id, file_type),
            'source_file': get_source_basename(source_file),
            'extra': {'count': count}
        }, now)
        
        print(f"[Registry] process_done: file_type={file_type}, project_id={project_id}, tasks={count}")
        
    except Exception as e:
        print(f"[Registry] on_process_done 失败: {e}")
        import traceback
        traceback.print_exc()

def on_export_done(
    file_type: int, 
    project_id: str, 
    export_path: str, 
    count: int, 
    now: Optional[datetime] = None
) -> None:
    """
    导出完成钩子
    
    当导出操作完成后调用，记录导出事件
    
    参数:
        file_type: 文件类型（1-6）
        project_id: 项目号
        export_path: 导出文件路径
        count: 导出行数
        now: 当前时间（可选）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        write_event(db_path, wal, EventType.EXPORT_DONE, {
            'file_type': file_type,
            'project_id': normalize_project_id(project_id, file_type),
            'source_file': get_source_basename(export_path),
            'extra': {'count': int(count), 'path': export_path}
        }, now)
        
        print(f"[Registry] export_done: file_type={file_type}, count={count}")
        
    except Exception as e:
        print(f"[Registry] on_export_done 失败: {e}")

def on_assigned(
    file_type: int,
    file_path: str,
    row_index: int,
    interface_id: str,
    project_id: str,
    assigned_by: str,
    assigned_to: str,
    now: Optional[datetime] = None
) -> None:
    """
    任务指派钩子
    
    当接口工程师/室主任指派任务时调用
    
    参数:
        file_type: 文件类型（1-6）
        file_path: 源文件路径
        row_index: Excel原始行号
        interface_id: 接口号
        project_id: 项目号
        assigned_by: 指派人（含角色，如"王工（1818接口工程师）"）
        assigned_to: 责任人姓名
        now: 当前时间（可选）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        # 构造任务key
        key = {
            'file_type': file_type,
            'project_id': normalize_project_id(project_id, file_type),
            'interface_id': (interface_id or "").strip(),
            'source_file': get_source_basename(file_path),
            'row_index': int(row_index or 0),
        }
        
        # 更新任务：设置指派信息和显示状态
        fields = {
            'assigned_by': assigned_by,
            'assigned_at': now.isoformat(),
            'display_status': '待完成',
            'responsible_person': assigned_to
        }
        
        from .service import upsert_task
        upsert_task(db_path, wal, key, fields, now)
        
        # 写入ASSIGNED事件
        write_event(db_path, wal, EventType.ASSIGNED, {
            'file_type': file_type,
            'project_id': key['project_id'],
            'interface_id': key['interface_id'],
            'source_file': key['source_file'],
            'row_index': key['row_index'],
            'extra': {
                'assigned_by': assigned_by,
                'assigned_to': assigned_to
            }
        }, now)
        
        print(f"[Registry] assigned: interface_id={interface_id}, by={assigned_by}, to={assigned_to}")
        
    except Exception as e:
        print(f"[Registry] on_assigned 失败: {e}")
        import traceback
        traceback.print_exc()

def on_response_written(
    file_type: int,
    file_path: str,
    row_index: int,
    interface_id: str,
    response_number: str,
    user_name: str,
    project_id: str,
    source_column: Optional[str] = None,
    role: Optional[str] = None,
    now: Optional[datetime] = None
) -> None:
    """
    回文单号写入钩子
    
    当设计人员写入回文单号后调用，将任务状态从 open 更新为 completed
    
    参数:
        file_type: 文件类型（1-6）
        file_path: 源文件路径
        row_index: Excel原始行号
        interface_id: 接口号（不含角色后缀）
        response_number: 回文单号
        user_name: 操作用户
        project_id: 项目号
        source_column: 写入列名（可选）
        role: 角色信息（可选，如"设计人员"、"接口工程师"）
        now: 当前时间（可选）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        # 构造任务key
        key = {
            'file_type': file_type,
            'project_id': normalize_project_id(project_id, file_type),
            'interface_id': (interface_id or "").strip(),
            'source_file': get_source_basename(file_path),
            'row_index': int(row_index or 0),
        }
        
        # 【状态提醒】查询任务是否有指派人
        from .util import make_task_id
        from .db import get_connection
        
        tid = make_task_id(
            key['file_type'],
            key['project_id'],
            key['interface_id'],
            key['source_file'],
            key['row_index']
        )
        
        # 连接数据库查询
        conn = get_connection(db_path, wal)
        try:
            cursor = conn.execute("SELECT assigned_by FROM tasks WHERE id=?", (tid,))
            task_row = cursor.fetchone()
            has_assignor = task_row and task_row[0]  # 是否有指派人
        except Exception as e:
            # 如果表结构不存在或查询失败，假设没有指派人
            print(f"[Registry] 查询指派人失败（可能是旧数据库）: {e}")
            has_assignor = False
        
        # 确定display_status
        if has_assignor:
            display_status = '待指派人审查'
        else:
            display_status = '待审查'
        
        print(f"[Registry] 回文单号写入 - 设置display_status={display_status}, has_assignor={has_assignor}")
        
        # 【修复】查询旧任务的interface_time，避免误判为时间变化
        # 使用business_id查询，确保能找到同一接口的历史任务（即使row_index变化）
        old_interface_time = ''
        try:
            from .util import make_business_id
            business_id = make_business_id(key['file_type'], key['project_id'], key['interface_id'])
            cursor = conn.execute("SELECT interface_time FROM tasks WHERE business_id=? ORDER BY last_seen_at DESC LIMIT 1", (business_id,))
            row = cursor.fetchone()
            if row and row[0]:
                old_interface_time = row[0]
        except Exception as e:
            print(f"[Registry] 查询旧interface_time失败: {e}")
        
        # 如果提供了角色信息，先更新任务的role字段和display_status
        fields_to_update = {
            'display_status': display_status,
            'interface_time': old_interface_time,  # 【新增】保持时间不变，避免误判为时间变化
            '_completed_col_value': '有值',  # 【新增】标记完成列已填充
            'response_number': response_number  # 【新增】记录回文单号
        }
        if role:
            fields_to_update['role'] = role
        
        from .service import upsert_task
        upsert_task(db_path, wal, key, fields_to_update, now)
        
        print(f"[Registry] upsert_task完成，应该已设置display_status={display_status}")
        
        # 更新状态为completed
        mark_completed(db_path, wal, key, now)
        
        # 写入response_written事件
        write_event(db_path, wal, EventType.RESPONSE_WRITTEN, {
            'file_type': file_type,
            'project_id': key['project_id'],
            'interface_id': key['interface_id'],
            'source_file': key['source_file'],
            'row_index': key['row_index'],
            'extra': {
                'response_number': response_number,
                'user_name': user_name,
                'source_column': source_column
            }
        }, now)
        
        print(f"[Registry] response_written: interface_id={interface_id}, user={user_name}")
        
    except Exception as e:
        print(f"[Registry] on_response_written 失败: {e}")
        import traceback
        traceback.print_exc()

def on_confirmed_by_superior(
    file_type: int,
    file_path: str,
    row_index: int,
    user_name: str,
    project_id: str,
    interface_id: Optional[str] = None,
    now: Optional[datetime] = None
) -> None:
    """
    上级确认钩子
    
    当上级点击"已完成"勾选框确认任务时调用，将任务状态从 completed 更新为 confirmed
    
    参数:
        file_type: 文件类型（1-6）
        file_path: 源文件路径
        row_index: Excel原始行号
        user_name: 操作用户（上级）
        project_id: 项目号
        interface_id: 接口号（可选，如果有则使用）
        now: 当前时间（可选）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        # 构造任务key
        key = {
            'file_type': file_type,
            'project_id': normalize_project_id(project_id, file_type),
            'interface_id': (interface_id or "").strip(),
            'source_file': get_source_basename(file_path),
            'row_index': int(row_index or 0),
        }
        
        # 【修复】更新状态为confirmed，传递确认人姓名
        mark_confirmed(db_path, wal, key, now, confirmed_by=user_name)
        
        # 写入confirmed事件
        write_event(db_path, wal, EventType.CONFIRMED, {
            'file_type': file_type,
            'project_id': key['project_id'],
            'interface_id': key['interface_id'],
            'source_file': key['source_file'],
            'row_index': key['row_index'],
            'extra': {'user_name': user_name}
        }, now)
        
        print(f"[Registry] confirmed: file_type={file_type}, row={row_index}, user={user_name}")
        
    except Exception as e:
        print(f"[Registry] on_confirmed_by_superior 失败: {e}")
        import traceback
        traceback.print_exc()

def on_scan_finalize(
    batch_tag: str,
    now: Optional[datetime] = None,
    missing_keep_days: Optional[int] = None
) -> None:
    """
    扫描完成钩子
    
    当一次完整扫描结束后调用，标记消失任务并归档超期项
    
    注意：阶段1暂不实现完整逻辑，留待阶段2完善
    
    参数:
        batch_tag: 批次标识（如时间戳）
        now: 当前时间（可选）
        missing_keep_days: 消失后保持天数（可选，不指定则使用配置）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        days = int(missing_keep_days if missing_keep_days is not None else int(cfg.get('registry_missing_keep_days', 7)))
        
        # 执行归档逻辑
        from .service import finalize_scan
        finalize_scan(db_path, wal, now, days)
        
        print(f"[Registry] scan_finalize: batch={batch_tag}, missing_keep_days={days}")
        
    except Exception as e:
        print(f"[Registry] on_scan_finalize 失败: {e}")

def write_event_only(event: str, payload: dict) -> None:
    """
    仅写入事件（不更新任务状态）
    
    用于记录assign等辅助事件
    
    参数:
        event: 事件类型
        payload: 事件数据
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        write_event(db_path, wal, event, payload, now)
        
    except Exception as e:
        print(f"[Registry] write_event_only 失败: {e}")

