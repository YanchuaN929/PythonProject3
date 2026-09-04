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
import threading
import pandas as pd
from .config import load_config, set_config

try:
    from utils.dept_config import get_superior_keywords
except ImportError:
    def get_superior_keywords():
        return ['一室主任', '二室主任', '建筑总图室主任', '所长', '所领导', '接口工程师', '管理员']
from .service import (
    write_event,
    mark_completed,
    mark_confirmed,
    batch_upsert_tasks,
    batch_touch_scanned_tasks,
    resolve_task_record,
    resolve_task_records,
)
from .db import close_connection, close_connection_after_use, MaintenanceModeError, _diag_log
from .models import EventType
from .util import (
    build_task_key_from_row, 
    build_task_fields_from_row,
    get_source_basename,
    get_source_revision,
    safe_now,
    normalize_project_id
)


def _is_lock_error(error: Exception) -> bool:
    """判断是否为数据库锁/忙相关错误。"""
    text = str(error).lower()
    keywords = (
        "locked",
        "busy",
        "database is locked",
        "database table is locked",
        "database schema is locked",
    )
    return any(k in text for k in keywords)


def _retry_on_lock(operation_name: str, func, max_retries: int = 8):
    """
    带重试的数据库操作包装器（专门应对网络盘锁定问题）
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = func()
            # 若曾发生锁等待但最终成功，恢复状态栏为“已连接”。
            if attempt > 0:
                try:
                    from services.db_status import notify_connected
                    cfg = _cfg()
                    notify_connected(db_path=cfg.get("registry_db_path"))
                except Exception:
                    pass
            return result
        except sqlite3.OperationalError as e:
            if _is_lock_error(e):
                last_error = e
                if attempt < max_retries:
                    try:
                        from services.db_status import notify_waiting
                        notify_waiting()
                    except Exception:
                        pass
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
_RUNTIME_DISABLED_REASON = ""
_RUNTIME_DISABLE_NOTIFIED = False


def _is_malformed_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "database disk image is malformed" in text
        or "file is not a database" in text
        or "malformed" in text
    )


def _disable_registry_runtime(message: str, *, show_dialog: bool = True) -> None:
    global _RUNTIME_DISABLED_REASON, _RUNTIME_DISABLE_NOTIFIED
    _RUNTIME_DISABLED_REASON = message
    if _RUNTIME_DISABLE_NOTIFIED:
        return
    _RUNTIME_DISABLE_NOTIFIED = True
    try:
        from services.db_status import notify_error
        notify_error(message, show_dialog=show_dialog)
    except Exception:
        print(f"[Registry] {message}")


def _handle_runtime_registry_error(error: Exception) -> None:
    if _is_malformed_error(error):
        _disable_registry_runtime(
            "共享 Registry 数据库已损坏（database disk image is malformed），本次运行已暂停 Registry 功能，请联系管理员修复共享盘 .registry/registry.db。",
            show_dialog=True,
        )
        return

    try:
        from services.db_status import notify_error
        if _is_lock_error(error):
            notify_error("数据库被其他用户锁定，系统已自动重试，请稍后再试", show_dialog=False)
        else:
            notify_error(str(error), show_dialog=True)
    except Exception:
        pass

def _normalize_folder_path(path: str) -> str:
    if not path:
        return ""
    normalized = str(path).strip().replace("/", "\\")
    while normalized.endswith("\\"):
        normalized = normalized[:-1]
    return normalized.lower()

def _ensure_data_folder_from_path(source_path: Optional[str]) -> None:
    """
    尝试从源文件路径推导并设置数据目录。
    
    【重要】此函数仅在 _DATA_FOLDER 尚未设置时才会尝试推导。
    正常情况下，_DATA_FOLDER 应该由主程序在启动时/用户选择路径时通过 set_data_folder() 设置。
    此函数是一个后备机制，用于处理某些边缘情况。
    """
    # 【关键】如果 _DATA_FOLDER 已经设置，不再尝试推导（避免覆盖用户选择的路径）
    if _DATA_FOLDER:
        return
    
    if not source_path:
        return
    try:
        source_path = str(source_path)
        if not (os.path.isabs(source_path) or source_path.startswith("\\\\") or source_path.startswith("//")):
            return
        folder = source_path
        if not os.path.isdir(folder):
            folder = os.path.dirname(source_path)
        if not folder:
            return

        # 向上寻找包含 .registry 的目录（数据根目录的标志）
        search_dir = folder
        for _ in range(5):
            try:
                registry_dir_candidate = os.path.join(search_dir, ".registry")
                if os.path.isdir(registry_dir_candidate):
                    set_data_folder(search_dir)
                    return
            except Exception:
                pass
            parent = os.path.dirname(search_dir)
            if not parent or parent == search_dir:
                break
            search_dir = parent

        # 如果没找到 .registry 目录，使用文件所在目录
        set_data_folder(folder)
    except Exception:
        pass

def _ensure_data_folder_from_task_keys(task_keys: List[Dict[str, Any]]) -> None:
    """从 task_keys 中尽力推导数据目录（优先使用绝对 source_file）。"""
    if not task_keys:
        return
    for tk in task_keys:
        try:
            source_file = tk.get("source_file")
            if source_file and (os.path.isabs(source_file) or str(source_file).startswith("\\\\") or str(source_file).startswith("//")):
                _ensure_data_folder_from_path(source_file)
                return
        except Exception:
            continue

def set_data_folder(folder_path: str):
    """
    设置数据文件夹路径（用于多用户协作）
    
    应该在程序启动时调用，传入公共盘的数据文件夹路径。
    数据库将自动创建在该文件夹下的.registry子目录中。
    
    参数:
        folder_path: 数据文件夹的绝对路径
    """
    global _DATA_FOLDER, _RUNTIME_DISABLED_REASON, _RUNTIME_DISABLE_NOTIFIED
    _DATA_FOLDER = folder_path
    _RUNTIME_DISABLED_REASON = ""
    _RUNTIME_DISABLE_NOTIFIED = False
    # 在“允许触网”的时机（用户刷新/选择目录后）主动校验一次 registry 目录可用性。
    # 若不可用：直接禁用并提示（不回退到本地 result_cache/registry.db）。
    try:
        cfg = load_config(data_folder=_DATA_FOLDER, ensure_registry_dir=True)
        try:
            # 同步更新全局配置缓存，避免后续 get_config 读到旧的 db_path
            set_config(cfg)
        except Exception:
            pass
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

def get_data_folder() -> Optional[str]:
    """
    获取当前设置的数据文件夹路径
    
    返回:
        当前的 _DATA_FOLDER 值，如果未设置则返回 None
    """
    return _DATA_FOLDER

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
        _ensure_data_folder_from_task_keys(task_keys)
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


def get_display_state(
    task_keys: List[Dict[str, Any]],
    current_user_roles_str: str = None,
) -> tuple:
    """一次批量查询同时返回显示状态和实时任务快照。"""
    try:
        _ensure_data_folder_from_task_keys(task_keys)
        cfg = _cfg()
        if not _enabled(cfg):
            return {}, {}

        db_path = cfg["registry_db_path"]
        wal = bool(cfg.get("registry_wal", False))
        user_roles = []
        if current_user_roles_str:
            user_roles = [
                role.strip()
                for role in current_user_roles_str.split(",")
                if role.strip()
            ]

        snapshots = resolve_task_records(db_path, wal, task_keys)
        from .service import get_display_status as service_get_display_status
        statuses = service_get_display_status(
            db_path,
            wal,
            task_keys,
            user_roles,
            task_snapshots=snapshots,
        )
        return statuses, snapshots
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] get_display_state 失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_connection_after_use()
    return {}, {}


def get_task_snapshot(key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """统一读取任务快照，先查精确 task_id，再回退到最新 business 记录。"""
    try:
        _ensure_data_folder_from_path(key.get("source_file"))
        cfg = _cfg()
        if not _enabled(cfg):
            return None

        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        return resolve_task_record(db_path, wal, key)
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] get_task_snapshot 澶辫触: {e}")
        import traceback
        traceback.print_exc()
    finally:
        close_connection_after_use()
    return None


def _cfg():
    """加载配置（内部辅助函数）"""
    return load_config(data_folder=_DATA_FOLDER)

def _enabled(cfg: dict) -> bool:
    """检查registry是否启用（内部辅助函数）"""
    return bool(cfg.get('registry_enabled', True)) and not bool(_RUNTIME_DISABLED_REASON)


def _handle_maintenance_mode(error: Exception):
    """维护模式处理：释放连接、提示并退出。"""
    flag_path = None
    is_main_thread = threading.current_thread() is threading.main_thread()
    try:
        from .db import get_maintenance_flag_path
        if _DATA_FOLDER:
            flag_path = get_maintenance_flag_path(data_folder=_DATA_FOLDER)
    except Exception:
        flag_path = None
    _diag_log(
        "maintenance_handle_start",
        data_folder=_DATA_FOLDER or "",
        flag_path=flag_path or "",
        error=str(error),
        is_main_thread=is_main_thread,
    )
    print(f"[Registry] 维护模式触发退出: {error}, flag_path={flag_path}")
    
    try:
        close_connection()
    except Exception:
        pass
    
    msg = "Registry 已进入维护模式，请稍后再试。\n程序将退出以释放占用。"
    try:
        from services.db_status import notify_maintenance
        flag_path = None
        try:
            from .db import get_maintenance_flag_path
            if _DATA_FOLDER:
                flag_path = get_maintenance_flag_path(data_folder=_DATA_FOLDER)
        except Exception:
            flag_path = None
        notify_maintenance(flag_path=flag_path)
    except Exception:
        pass
    
    if is_main_thread:
        try:
            from tkinter import messagebox
            messagebox.showwarning("Registry维护模式", msg)
        except Exception:
            print(f"[Registry] {msg}")
    else:
        # 后台线程禁止直接触发Tk对话框，避免跨线程UI调用导致卡顿
        print(f"[Registry] {msg}（后台线程触发，跳过弹窗）")
    
    try:
        try:
            log_dir = os.path.expanduser("~/.excel_processor")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "exit_reason.log")
            ts = safe_now().isoformat()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} maintenance_exit flag_path={flag_path} error={error}\n")
        except Exception:
            pass
        import sys
        _diag_log(
            "maintenance_exit",
            data_folder=_DATA_FOLDER or "",
            flag_path=flag_path or "",
            error=str(error),
            is_main_thread=is_main_thread,
        )
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(0)
    except Exception:
        pass

def _build_process_tasks_data(file_type, source_file, result_df):
    source_revision = get_source_revision(source_file)
    tasks_data = []
    for _, row in result_df.iterrows():
        key = build_task_key_from_row(row, file_type, source_file)
        fields = build_task_fields_from_row(row, file_type)
        fields['_source_revision'] = source_revision
        tasks_data.append({'key': key, 'fields': fields})
    return tasks_data


def on_process_done(
    file_type: int, 
    project_id: str, 
    source_file: str, 
    result_df: pd.DataFrame, 
    now: Optional[datetime] = None
) -> bool:
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
        _ensure_data_folder_from_path(source_file)
        cfg = _cfg()
        if not _enabled(cfg):
            return False
        
        if result_df is None or result_df.empty:
            return True
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
        tasks_data = _build_process_tasks_data(file_type, source_file, result_df)
        
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

        # 扫描可能新增任务或自动归档旧任务，后续显示必须重新同步本地只读缓存。
        invalidate_cache()
        
        if count == 0:
            print(f"[Registry] ⚠ 文件{file_type}项目{project_id}: 写入0条（数据库可能未正确初始化）")
        return True
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_process_done 失败: {e}")
        import traceback
        tb_text = traceback.format_exc()
        print(tb_text)
        _diag_log(
            "process_done_error",
            file_type=file_type,
            project_id=normalize_project_id(project_id, file_type),
            source_file=get_source_basename(source_file),
            error=str(e),
            traceback=tb_text,
        )
        
        _handle_runtime_registry_error(e)
        return False
    finally:
        close_connection_after_use()


def on_cached_process_done(
    file_type: int,
    project_id: str,
    source_file: str,
    result_df: pd.DataFrame,
    now: Optional[datetime] = None,
) -> bool:
    """缓存命中时批量刷新任务存活状态，不重读 Excel。"""
    try:
        _ensure_data_folder_from_path(source_file)
        cfg = _cfg()
        if not _enabled(cfg):
            return False
        if result_df is None or result_df.empty:
            return True

        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        tasks_data = _build_process_tasks_data(file_type, source_file, result_df)
        stats = _retry_on_lock(
            "刷新缓存任务存活状态",
            lambda: batch_touch_scanned_tasks(db_path, wal, tasks_data, now),
        )

        if stats.get("restored", 0) or stats.get("created", 0):
            _retry_on_lock(
                "记录缓存任务恢复",
                lambda: write_event(db_path, wal, EventType.PROCESS_DONE, {
                    'file_type': file_type,
                    'project_id': normalize_project_id(project_id, file_type),
                    'source_file': get_source_basename(source_file),
                    'extra': {
                        'count': stats.get("seen", 0),
                        'cache_hit': True,
                        'restored': stats.get("restored", 0),
                        'created': stats.get("created", 0),
                    }
                }, now),
            )
            invalidate_cache()
        return True
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_cached_process_done 失败: {e}")
        import traceback
        tb_text = traceback.format_exc()
        print(tb_text)
        _diag_log(
            "cached_process_done_error",
            file_type=file_type,
            project_id=normalize_project_id(project_id, file_type),
            source_file=get_source_basename(source_file),
            error=str(e),
            traceback=tb_text,
        )
        _handle_runtime_registry_error(e)
        return False
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
        _ensure_data_folder_from_path(export_path)
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
        _retry_on_lock(
            "导出事件写入",
            lambda: write_event(
                db_path,
                wal,
                EventType.EXPORT_DONE,
                {
                    'file_type': file_type,
                    'project_id': normalize_project_id(project_id, file_type),
                    'source_file': get_source_basename(export_path),
                    'extra': {'count': int(count), 'path': export_path}
                },
                now
            )
        )
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] on_export_done 失败: {e}")
        _handle_runtime_registry_error(e)
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
) -> bool:
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
        _ensure_data_folder_from_path(file_path)
        cfg = _cfg()
        if not _enabled(cfg):
            return False
        
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
        
        def _do_assigned_write():
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

        _retry_on_lock("指派写入", _do_assigned_write)
        invalidate_cache()
        return True
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_assigned 失败: {e}")
        import traceback
        traceback.print_exc()
        _handle_runtime_registry_error(e)
        return False
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
) -> bool:
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
        _ensure_data_folder_from_path(file_path)
        cfg = _cfg()
        if not _enabled(cfg):
            return True
        
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
        
        def _do_response_write():
            from .db import get_connection
            from .service import upsert_task

            conn = get_connection(db_path, wal)
            try:
                # 【统一解析】先查精确 task_id，再回退到最新 business 记录
                task_snapshot = resolve_task_record(db_path, wal, key, conn=conn)
                has_assignor = bool(task_snapshot and task_snapshot.get('assigned_by'))

                # 确定display_status
                if has_assignor:
                    display_status = '待指派人审查'
                else:
                    display_status = '待审查'

                print(f"[Registry] 回文单号写入 - 设置display_status={display_status}, has_assignor={has_assignor}")

                # 【修复】查询旧任务的interface_time，避免误判为时间变化
                # 使用business_id查询，确保能找到同一接口的历史任务（即使row_index变化）
                old_interface_time = ''
                if task_snapshot and task_snapshot.get('interface_time'):
                    old_interface_time = task_snapshot['interface_time']

                # 【关键】判断是否为上级角色（自动确认逻辑）
                superior_roles = get_superior_keywords()
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
                fields_to_update['_source_revision'] = get_source_revision(file_path)
                if role:
                    fields_to_update['role'] = role

                # 如果是上级自动确认，设置confirmed_by和confirmed_at
                if is_superior:
                    fields_to_update['confirmed_by'] = user_name
                    fields_to_update['confirmed_at'] = now.isoformat()  # 【新增】明确设置确认时间

                upsert_task(db_path, wal, key, fields_to_update, now, conn=conn)

                print(f"[Registry] upsert_task完成，display_status={display_status}, completed_by={user_name}")

                # 更新状态为completed
                mark_completed(db_path, wal, key, now, conn=conn)

                # 如果是上级角色，同时完成确认并归档
                if is_superior:
                    archive_info = mark_confirmed(db_path, wal, key, now, confirmed_by=user_name, conn=conn)
                    if not archive_info:
                        raise RuntimeError(f"上级自动确认失败，未找到任务: {key['interface_id']}")
                    write_event(db_path, wal, EventType.ARCHIVED, {
                        'file_type': file_type,
                        'project_id': key['project_id'],
                        'interface_id': key['interface_id'],
                        'source_file': key['source_file'],
                        'row_index': key['row_index'],
                        'extra': {
                            'reason': archive_info.get('archive_reason'),
                            'confirmed_by': user_name,
                            'archived_task_id': archive_info.get('archived_id'),
                            'original_task_id': archive_info.get('original_id'),
                            'archived_row_index': archive_info.get('archived_row_index'),
                        }
                    }, now, conn=conn)
                    print(f"[Registry] 上级角色{role}自动确认并归档完成")

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
                }, now, conn=conn)
            finally:
                close_connection_after_use()

        _retry_on_lock("回文单号写入", _do_response_write)
        invalidate_cache()
        
        # 控制台输出优化：已验证逻辑，默认不输出
        return True
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_response_written 失败: {e}")
        import traceback
        traceback.print_exc()
        _handle_runtime_registry_error(e)
        return False
    finally:
        close_connection_after_use()


def on_fu_completed(
    file_path: str,
    row_index: int,
    interface_id: str,
    actual_date: str,
    user_name: str,
    project_id: str,
    role: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """Record a type-7 FU date write and move the task to review."""
    try:
        _ensure_data_folder_from_path(file_path)
        cfg = _cfg()
        if not _enabled(cfg):
            return True

        now = now or safe_now()
        db_path = cfg["registry_db_path"]
        wal = bool(cfg.get("registry_wal", False))
        key = {
            "file_type": 7,
            "project_id": normalize_project_id(project_id, 7),
            "interface_id": (interface_id or "").strip(),
            "source_file": get_source_basename(file_path),
            "row_index": int(row_index or 0),
        }

        def _do_fu_write():
            from .db import get_connection
            from .service import upsert_task

            conn = get_connection(db_path, wal)
            try:
                snapshot = resolve_task_record(db_path, wal, key, conn=conn)
                display_status = "待指派人审查" if snapshot and snapshot.get("assigned_by") else "待审查"
                interface_time = snapshot.get("interface_time", "") if snapshot else ""
                superior_keywords = get_superior_keywords()
                is_superior = bool(
                    role and any(keyword in role for keyword in superior_keywords)
                )
                if is_superior:
                    display_status = "已审查"

                fields = {
                    "display_status": display_status,
                    "interface_time": interface_time,
                    "_completed_col_value": actual_date or "有值",
                    "completed_by": user_name,
                    "_source_revision": get_source_revision(file_path),
                }
                if role:
                    fields["role"] = role
                if is_superior:
                    fields["confirmed_by"] = user_name
                    fields["confirmed_at"] = now.isoformat()

                upsert_task(db_path, wal, key, fields, now, conn=conn)
                mark_completed(db_path, wal, key, now, conn=conn)

                if is_superior:
                    archive_info = mark_confirmed(
                        db_path, wal, key, now, confirmed_by=user_name, conn=conn
                    )
                    if not archive_info:
                        raise RuntimeError(f"FU自动确认失败，未找到任务: {key['interface_id']}")
                    write_event(db_path, wal, EventType.ARCHIVED, {
                        **key,
                        "extra": {
                            "reason": archive_info.get("archive_reason"),
                            "confirmed_by": user_name,
                            "archived_task_id": archive_info.get("archived_id"),
                            "original_task_id": archive_info.get("original_id"),
                            "archived_row_index": archive_info.get("archived_row_index"),
                        },
                    }, now, conn=conn)

                write_event(db_path, wal, EventType.FU_COMPLETED, {
                    **key,
                    "extra": {
                        "actual_date": actual_date,
                        "user_name": user_name,
                    },
                }, now, conn=conn)
            finally:
                close_connection_after_use()

        _retry_on_lock("FU日期写入", _do_fu_write)
        invalidate_cache()
        return True
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_fu_completed 失败: {e}")
        import traceback
        traceback.print_exc()
        _handle_runtime_registry_error(e)
        return False
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
) -> bool:
    """
    上级确认钩子
    
    当上级点击"已完成"勾选框确认任务时调用，将任务状态从 completed 直接归档
    
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
        _ensure_data_folder_from_path(file_path)
        cfg = _cfg()
        if not _enabled(cfg):
            return False
        
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
        
        def _do_confirm_write():
            archive_info = mark_confirmed(db_path, wal, key, now, confirmed_by=user_name)
            if not archive_info:
                raise RuntimeError(f"确认失败，未找到任务: {key['interface_id']}")

            # 写入confirmed事件
            write_event(db_path, wal, EventType.CONFIRMED, {
                'file_type': file_type,
                'project_id': key['project_id'],
                'interface_id': key['interface_id'],
                'source_file': key['source_file'],
                'row_index': key['row_index'],
                'extra': {'user_name': user_name}
            }, now)

            # 确认即归档，记录归档事件，便于后续审计。
            write_event(db_path, wal, EventType.ARCHIVED, {
                'file_type': file_type,
                'project_id': key['project_id'],
                'interface_id': key['interface_id'],
                'source_file': key['source_file'],
                'row_index': key['row_index'],
                'extra': {
                    'reason': archive_info.get('archive_reason'),
                    'confirmed_by': user_name,
                    'archived_task_id': archive_info.get('archived_id'),
                    'original_task_id': archive_info.get('original_id'),
                    'archived_row_index': archive_info.get('archived_row_index'),
                }
            }, now)

        _retry_on_lock("上级确认写入", _do_confirm_write)
        invalidate_cache()
        return True
        
        # 控制台输出优化：已验证逻辑，默认不输出
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_confirmed_by_superior 失败: {e}")
        import traceback
        traceback.print_exc()
        _handle_runtime_registry_error(e)
        return False
    finally:
        close_connection_after_use()

def on_unconfirmed_by_superior(
    key: Dict[str, Any],
    user_name: str = None
) -> bool:
    """
    上级角色取消确认（取消勾选）
    
    参数:
        key: 任务key（必须包含: file_type, project_id, interface_id, source_file, row_index）
        user_name: 操作人姓名
    """
    try:
        try:
            _ensure_data_folder_from_path(key.get("source_file"))
        except Exception:
            pass
        from .service import mark_unconfirmed
        
        cfg = _cfg()
        if not _enabled(cfg):
            return False
        
        now = safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
        print(f"[Registry] 上级取消确认: 文件类型={key['file_type']}, 项目={key['project_id']}, 接口={key['interface_id']}, 用户={user_name}")
        
        _retry_on_lock("上级取消确认写入", lambda: mark_unconfirmed(db_path, wal, key, now))
        invalidate_cache()
        return True
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_unconfirmed_by_superior 失败: {e}")
        import traceback
        traceback.print_exc()
        _handle_runtime_registry_error(e)
        return False
    finally:
        close_connection_after_use()

def on_scan_finalize(
    batch_tag: str,
    now: Optional[datetime] = None,
    missing_keep_days: Optional[int] = None,
    scanned_sources=None,
) -> bool:
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
            return False
        
        now = now or safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        days = int(missing_keep_days if missing_keep_days is not None else int(cfg.get('registry_missing_keep_days', 7)))
        
        # 执行归档逻辑
        from .service import finalize_scan
        finalize_scan(
            db_path,
            wal,
            now,
            days,
            scanned_sources=scanned_sources,
        )
        invalidate_cache()
        
        print(f"[Registry] scan_finalize: batch={batch_tag}, missing_keep_days={days}")
        return True
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
        return False
    except Exception as e:
        print(f"[Registry] on_scan_finalize 失败: {e}")
        _handle_runtime_registry_error(e)
        return False
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
        try:
            _ensure_data_folder_from_path(payload.get("source_file") or payload.get("file_path"))
        except Exception:
            pass
        cfg = _cfg()
        if not _enabled(cfg):
            return
        
        now = safe_now()
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', False))
        
        _retry_on_lock("事件写入", lambda: write_event(db_path, wal, event, payload, now))
        
    except MaintenanceModeError as e:
        _handle_maintenance_mode(e)
    except Exception as e:
        print(f"[Registry] write_event_only 失败: {e}")
        _handle_runtime_registry_error(e)
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
    """兼容旧诊断入口；Registry 当前固定使用直接事务写入。"""
    return {'enabled': False, 'mode': 'direct', 'queue_size': 0}


def flush_write_queue(timeout: float = 10.0) -> bool:
    """兼容旧退出入口；直接写入模式没有待刷新的 Registry 队列。"""
    return True


def shutdown():
    """
    关闭 Registry 模块
    
    在程序退出前调用，确保：
    1. 写入队列中的请求已处理完成
    2. 数据库连接已关闭
    3. 本地缓存已清理
    """
    try:
        # 1. 清理本地缓存
        try:
            from .local_cache import cleanup_global_cache
            cleanup_global_cache()
        except ImportError:
            pass
        
        # 2. 关闭数据库连接
        close_connection()
        
        print("[Registry] 模块已关闭")
        
    except Exception as e:
        print(f"[Registry] shutdown 失败: {e}")
