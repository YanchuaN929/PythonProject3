"""
钩子API模块

提供供现有程序调用的统一钩子接口，所有钩子内部捕获异常，不向外抛出。
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import time
import random
import sqlite3
import os
import pandas as pd
from .config import load_config
from .service import write_event, mark_completed, mark_confirmed, batch_upsert_tasks
from .db import close_connection, close_connection_after_use, MaintenanceModeError
from .models import EventType
from .util import (
    build_task_key_from_row, 
    build_task_fields_from_row,
    get_source_basename,
    safe_now,
    normalize_project_id
)


def _retry_on_lock(operation_name: str, func, max_retries: int = 5):
    """
    带重试的数据库操作包装器（专门应对网络盘锁定问题）
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "locked" in error_msg or "busy" in error_msg:
                last_error = e
                if attempt < max_retries:
                    # 指数退避 + 随机抖动
                    delay = min(1.0 * (2 ** attempt) + random.uniform(0, 1), 15.0)
                    print(f"[Registry] {operation_name}锁定中，{delay:.1f}秒后重试 ({attempt + 1}/{max_retries})")
                    # 关闭当前连接，释放锁
                    close_connection()
                    time.sleep(delay)
                    continue
            raise
        except Exception:
            raise
    
    if last_error:
        raise last_error

# 【多用户协作】全局数据文件夹路径，用于确定共享数据库位置
_DATA_FOLDER = None
_DISABLED_NOTIFIED = False

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
    # 在“允许触网”的时机（用户刷新/选择目录后）主动校验一次 registry 目录可用性。
    # 若不可用：直接禁用并提示（不回退到本地 result_cache/registry.db）。
    try:
        cfg = load_config(data_folder=_DATA_FOLDER, ensure_registry_dir=True)
        if not _enabled(cfg):
            global _DISABLED_NOTIFIED
            if not _DISABLED_NOTIFIED:
                _DISABLED_NOTIFIED = True
                reason = (cfg.get("registry_disabled_reason") or "").strip()
                msg = reason or "公共盘数据库不可用，Registry已禁用（不会回退本地库）"
                try:
                    from services.db_status import notify_error
                    notify_error(msg, show_dialog=True)
                except Exception:
                    print(f"[Registry] {msg}")
    except Exception:
        # set_data_folder 不应影响主流程
        pass

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
        wal = bool(cfg.get('registry_wal', False))
        
        # 解析用户角色列表
        user_roles = []
        if current_user_roles_str:
            user_roles = [r.strip() for r in current_user_roles_str.split(',') if r.strip()]
        
        from .service import get_display_status as service_get_display_status
        return service_get_display_status(db_path, wal, task_keys, user_roles)
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return {}
    except Exception as e:
        print(f"[Registry] get_display_status 失败: {e}")
        import traceback
        traceback.print_exc()
        return {}
    finally:
        close_connection_after_use()

def _cfg():
    """加载配置（内部辅助函数）"""
    return load_config(data_folder=_DATA_FOLDER)

def _enabled(cfg: dict) -> bool:
    """检查registry是否启用（内部辅助函数）"""
    return bool(cfg.get('registry_enabled', True))


def _handle_maintenance_mode(error: Exception):
    """维护模式处理：释放连接、提示并退出。"""
    try:
        close_connection()
    except Exception:
        pass
    
    msg = "Registry 已进入维护模式，请稍后再试。\n程序将退出以释放占用。"
    try:
        from services.db_status import notify_error
        notify_error(msg, show_dialog=True)
    except Exception:
        try:
            from tkinter import messagebox
            messagebox.showwarning("Registry维护模式", msg)
        except Exception:
            print(f"[Registry] {msg}")
    
    try:
        os._exit(0)
    except Exception:
        pass

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
    带自动重试机制，应对网络盘锁定问题。
    
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
        wal = bool(cfg.get('registry_wal', False))
        
        # 批量构造任务数据
        tasks_data = []
        for _, row in result_df.iterrows():
            key = build_task_key_from_row(row, file_type, source_file)
            fields = build_task_fields_from_row(row, file_type)
            tasks_data.append({'key': key, 'fields': fields})
        
        # 【关键改进】使用重试机制执行批量upsert
        def do_batch_upsert():
            return batch_upsert_tasks(db_path, wal, tasks_data, now)
        
        count = _retry_on_lock("批量写入任务", do_batch_upsert)
        
        # 写入process_done事件（也使用重试）
        def do_write_event():
            write_event(db_path, wal, EventType.PROCESS_DONE, {
                'file_type': file_type,
                'project_id': normalize_project_id(project_id, file_type),
                'source_file': get_source_basename(source_file),
                'extra': {'count': count}
            }, now)
        
        _retry_on_lock("写入事件", do_write_event)
        
        if count == 0:
            print(f"[Registry] ⚠ 文件{file_type}项目{project_id}: 写入0条（数据库可能未正确初始化）")
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_process_done 失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 通知数据库状态显示器
        try:
            from services.db_status import notify_error
            if "database is locked" in str(e).lower() or "busy" in str(e).lower():
                notify_error("数据库被其他用户锁定，请稍后重试", show_dialog=True)
            else:
                notify_error(str(e), show_dialog=True)
        except ImportError:
            pass
    finally:
        close_connection_after_use()

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
        wal = bool(cfg.get('registry_wal', False))
        
        write_event(db_path, wal, EventType.EXPORT_DONE, {
            'file_type': file_type,
            'project_id': normalize_project_id(project_id, file_type),
            'source_file': get_source_basename(export_path),
            'extra': {'count': int(count), 'path': export_path}
        }, now)
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_export_done 失败: {e}")
    finally:
        close_connection_after_use()

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
        wal = bool(cfg.get('registry_wal', False))
        
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
            'responsible_person': assigned_to,
            # 明确：这是“指派动作”的显示状态更新，必须覆盖旧状态（不要被 upsert_task 的“默认值继承”逻辑回退）
            '_force_display_status': True,
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
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_assigned 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_connection_after_use()

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
    
    特殊处理：如果填写人是上级角色（室主任、所领导、接口工程师），则自动完成确认
    
    参数:
        file_type: 文件类型（1-6）
        file_path: 源文件路径
        row_index: Excel原始行号
        interface_id: 接口号（不含角色后缀）
        response_number: 回文单号
        user_name: 操作用户姓名
        project_id: 项目号
        source_column: 写入列名（可选）
        role: 角色信息（可选，如"设计人员"、"接口工程师"、"一室主任"、"所领导"）
        now: 当前时间（可选）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
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
        
        # 【关键】判断是否为上级角色（自动确认逻辑）
        superior_roles = ['一室主任', '二室主任', '建筑总图室主任', '所长', '所领导', '接口工程师']
        is_superior = role and any(sup_role in role for sup_role in superior_roles)
        
        # 【修复】如果是上级角色填写，直接设置display_status为"已审查"
        if is_superior:
            display_status = '已审查'  # 上级自己填写，已完成审查
            print(f"[Registry] 上级角色{role}填写回文单号，自动完成确认，设置状态为'已审查'")
        
        # 更新任务字段（包含completed_by和response_number）
        fields_to_update = {
            'display_status': display_status,  # 保持"待审查"或"待指派人审查"
            'interface_time': old_interface_time,  # 保持时间不变，避免误判为时间变化
            '_completed_col_value': '有值',  # 标记完成列已填充
            'response_number': response_number,  # 记录回文单号
            'completed_by': user_name  # 【新增】记录完成人姓名
        }
        if role:
            fields_to_update['role'] = role
        
        # 如果是上级自动确认，设置confirmed_by和confirmed_at
        if is_superior:
            fields_to_update['confirmed_by'] = user_name
            fields_to_update['confirmed_at'] = now.isoformat()  # 【新增】明确设置确认时间
        
        from .service import upsert_task
        upsert_task(db_path, wal, key, fields_to_update, now)
        
        print(f"[Registry] upsert_task完成，display_status={display_status}, completed_by={user_name}")
        
        # 更新状态为completed
        mark_completed(db_path, wal, key, now)
        
        # 如果是上级角色，同时更新状态为confirmed
        if is_superior:
            mark_confirmed(db_path, wal, key, now, confirmed_by=user_name)
            print(f"[Registry] 上级角色{role}自动确认完成")
        
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
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_response_written 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_connection_after_use()

def on_confirmed_by_superior(
    file_type: int,
    file_path: str,
    row_index: int,
    user_name: str,
    project_id: str,
    interface_id: Optional[str] = None,
    role: Optional[str] = None,
    now: Optional[datetime] = None
) -> None:
    """
    上级确认钩子
    
    当上级点击"已完成"勾选框确认任务时调用，将任务状态从 completed 更新为 confirmed
    
    参数:
        file_type: 文件类型（1-6）
        file_path: 源文件路径
        row_index: Excel原始行号
        user_name: 操作用户（上级）姓名
        project_id: 项目号
        interface_id: 接口号（可选，如果有则使用）
        role: 角色信息（可选，用于日志）
        now: 当前时间（可选）
    """
    try:
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
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
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_confirmed_by_superior 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_connection_after_use()

def on_unconfirmed_by_superior(
    key: Dict[str, Any],
    user_name: str = None
) -> None:
    """
    上级角色取消确认（取消勾选）
    
    参数:
        key: 任务key（必须包含: file_type, project_id, interface_id, source_file, row_index）
        user_name: 操作人姓名
    """
    try:
        from .service import mark_unconfirmed
        
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
        print(f"[Registry] 上级取消确认: 文件类型={key['file_type']}, 项目={key['project_id']}, 接口={key['interface_id']}, 用户={user_name}")
        
        mark_unconfirmed(db_path, wal, key, now)
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_unconfirmed_by_superior 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_connection_after_use()

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
        wal = bool(cfg.get('registry_wal', False))
        days = int(missing_keep_days if missing_keep_days is not None else int(cfg.get('registry_missing_keep_days', 7)))
        
        # 执行归档逻辑
        from .service import finalize_scan
        finalize_scan(db_path, wal, now, days)
        
        print(f"[Registry] scan_finalize: batch={batch_tag}, missing_keep_days={days}")
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_scan_finalize 失败: {e}")
    finally:
        close_connection_after_use()

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
        wal = bool(cfg.get('registry_wal', False))
        
        write_event(db_path, wal, event, payload, now)
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] write_event_only 失败: {e}")
    finally:
        close_connection_after_use()


# ============================================================
# 第二/第三阶段优化：缓存和队列支持
# ============================================================

def invalidate_cache():
    """
    使本地读缓存失效
    
    在执行写入操作后调用此函数，确保下次读取获取最新数据。
    如果本地缓存未启用，此函数无操作。
    """
    try:
        from .db import invalidate_read_cache
        invalidate_read_cache()
    except Exception as e:
        print(f"[Registry] invalidate_cache 失败: {e}")


def force_sync_cache() -> bool:
    """
    强制同步本地缓存
    
    用于用户手动刷新数据时调用。
    
    返回:
        True = 同步成功，False = 同步失败或未启用
    """
    try:
        from .db import force_sync_cache as db_force_sync
        return db_force_sync()
    except Exception as e:
        print(f"[Registry] force_sync_cache 失败: {e}")
        return False


def get_cache_status() -> dict:
    """
    获取缓存状态信息
    
    返回:
        包含缓存状态的字典，用于调试或状态显示
    """
    try:
        from .db import get_cache_info
        return get_cache_info()
    except Exception as e:
        return {'error': str(e)}


def get_write_queue_stats() -> dict:
    """
    获取写入队列统计信息
    
    返回:
        包含队列状态的字典
    """
    try:
        cfg = _cfg()
        if not cfg.get('registry_write_queue_enabled', False):
            return {'enabled': False}
        
        from .write_queue import get_write_queue
        queue = get_write_queue()
        stats = queue.get_stats()
        stats['queue_size'] = queue.get_queue_size()
        stats['enabled'] = queue.is_enabled()
        return stats
    except Exception as e:
        return {'error': str(e)}


def flush_write_queue(timeout: float = 10.0) -> bool:
    """
    刷新写入队列，等待所有待处理请求完成
    
    在程序退出前调用此函数，确保所有写入操作已完成。
    
    参数:
        timeout: 最大等待时间（秒）
        
    返回:
        True = 队列已清空，False = 超时或未启用
    """
    try:
        cfg = _cfg()
        if not cfg.get('registry_write_queue_enabled', False):
            return True  # 未启用队列，无需刷新
        
        from .write_queue import get_write_queue
        queue = get_write_queue()
        return queue.flush(timeout)
    except Exception as e:
        print(f"[Registry] flush_write_queue 失败: {e}")
        return False


def shutdown():
    """
    关闭 Registry 模块
    
    在程序退出前调用，确保：
    1. 写入队列中的请求已处理完成
    2. 数据库连接已关闭
    3. 本地缓存已清理
    """
    try:
        # 1. 刷新写入队列
        flush_write_queue(timeout=5.0)
        
        # 2. 关闭写入队列
        try:
            from .write_queue import shutdown_write_queue
            shutdown_write_queue()
        except ImportError:
            pass
        
        # 3. 清理本地缓存
        try:
            from .local_cache import cleanup_global_cache
            cleanup_global_cache()
        except ImportError:
            pass
        
        # 4. 关闭数据库连接
        close_connection()
        
        print("[Registry] 模块已关闭")
        
    except Exception as e:
        print(f"[Registry] shutdown 失败: {e}")

