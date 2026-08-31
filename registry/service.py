"""
核心业务逻辑模块

提供任务创建更新、状态流转、事件记录等核心功能。
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from .db import get_connection, get_read_connection, close_connection_after_use
from .models import Status, EventType
from .recovery import row_to_dict, select_available_columns
from .util import make_task_id, make_business_id


CONFIRMED_ARCHIVE_REASONS = frozenset({
    "confirmed_by_superior",
    "completed_in_new_source",
})
AUTO_CONFIRMED_BY_SOURCE_UPDATE = "源文件更新自动确认"


def _task_activity_timestamp(task: Optional[Dict[str, Any]]) -> str:
    """Return the best comparable timestamp for an active task record."""
    if not task:
        return ""
    return str(task.get("last_seen_at") or task.get("first_seen_at") or "").strip()


def _confirmed_archive_timestamp(task: Optional[Dict[str, Any]]) -> str:
    """Return the lifecycle timestamp that closed a business task."""
    if not task:
        return ""
    return str(
        task.get("archived_at")
        or task.get("confirmed_at")
        or task.get("last_seen_at")
        or ""
    ).strip()


def _is_superseded_by_confirmed_archive(
    active_task: Optional[Dict[str, Any]],
    archived_task: Optional[Dict[str, Any]],
) -> bool:
    """Whether a confirmed archive is at least as new as an active duplicate."""
    if not active_task or not archived_task:
        return False
    archive_ts = _confirmed_archive_timestamp(archived_task)
    active_ts = _task_activity_timestamp(active_task)
    if not archive_ts:
        return False
    if not active_ts:
        return True
    return archive_ts >= active_ts

def find_task_by_business_id(
    db_path: str,
    wal: bool,
    file_type: int,
    project_id: str,
    interface_id: str,
    conn=None
) -> Optional[Dict[str, Any]]:
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
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    business_id = make_business_id(file_type, project_id, interface_id)
    
    try:
        preferred_columns = [
            "id",
            "business_id",
            "file_type",
            "project_id",
            "interface_id",
            "source_file",
            "source_revision",
            "row_index",
            "interface_time",
            "status",
            "display_status",
            "responsible_person",
            "assigned_by",
            "assigned_at",
            "confirmed_by",
            "completed_at",
            "completed_by",
            "confirmed_at",
            "first_seen_at",
            "last_seen_at",
            "ignored",
            "ignored_at",
            "ignored_by",
            "interface_time_when_ignored",
            "ignored_reason",
        ]
        selected_columns = select_available_columns(conn, "tasks", preferred_columns)
        if not selected_columns:
            return None

        where_sql = "business_id = ?" if "business_id" in select_available_columns(conn, "tasks", ["business_id"]) else "file_type = ? AND project_id = ? AND interface_id = ?"
        params = (business_id,) if "business_id" in where_sql else (file_type, project_id, interface_id)
        status_filter = " AND status != 'archived'" if "status" in selected_columns or "status" in select_available_columns(conn, "tasks", ["status"]) else ""
        order_by = "last_seen_at DESC" if "last_seen_at" in select_available_columns(conn, "tasks", ["last_seen_at"]) else "rowid DESC"
        cursor = conn.execute(
            f"""
            SELECT {", ".join(selected_columns)}
            FROM tasks
            WHERE {where_sql}{status_filter}
            ORDER BY {order_by}
            LIMIT 1
            """,
            params,
        )

        row = cursor.fetchone()
        if row:
            task = row_to_dict(
                row,
                selected_columns,
                defaults={
                    "display_status": None,
                    "responsible_person": None,
                    "assigned_by": None,
                    "assigned_at": None,
                    "role": "",
                    "confirmed_by": None,
                    "completed_at": None,
                    "completed_by": None,
                    "confirmed_at": None,
                    "first_seen_at": None,
                    "last_seen_at": None,
                    "source_revision": None,
                    "ignored": 0,
                    "ignored_at": None,
                    "ignored_by": None,
                    "interface_time_when_ignored": None,
                    "ignored_reason": None,
                },
            )
            archived_task = find_latest_confirmed_archive_by_business_id(
                db_path,
                wal,
                file_type,
                project_id,
                interface_id,
                conn=conn,
            )
            if _is_superseded_by_confirmed_archive(task, archived_task):
                return None
            return task
        return None
    finally:
        if owns_conn:
            close_connection_after_use()


def find_latest_confirmed_archive_by_business_id(
    db_path: str,
    wal: bool,
    file_type: int,
    project_id: str,
    interface_id: str,
    conn=None
) -> Optional[Dict[str, Any]]:
    """查找同一 business_id 最近一次由确认产生的归档记录。"""
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    business_id = make_business_id(file_type, project_id, interface_id)

    try:
        preferred_columns = [
            "id",
            "business_id",
            "file_type",
            "project_id",
            "interface_id",
            "source_file",
            "source_revision",
            "row_index",
            "interface_time",
            "status",
            "display_status",
            "responsible_person",
            "assigned_by",
            "assigned_at",
            "confirmed_by",
            "completed_at",
            "completed_by",
            "confirmed_at",
            "first_seen_at",
            "last_seen_at",
            "archive_reason",
            "archived_at",
            "ignored",
        ]
        selected_columns = select_available_columns(conn, "tasks", preferred_columns)
        if not selected_columns:
            return None

        available = set(selected_columns)
        if not {"business_id", "status"}.issubset(available):
            return None

        archive_filter = (
            " AND archive_reason IN ('confirmed_by_superior', 'completed_in_new_source')"
            if "archive_reason" in available
            else ""
        )
        confirmed_filter = " AND confirmed_at IS NOT NULL" if "confirmed_at" in available else ""
        order_parts = []
        if "archived_at" in available:
            order_parts.append("archived_at DESC")
        if "last_seen_at" in available:
            order_parts.append("last_seen_at DESC")
        order_parts.append("rowid DESC")

        cursor = conn.execute(
            f"""
            SELECT {", ".join(selected_columns)}
            FROM tasks
            WHERE business_id = ?
              AND status = 'archived'
              {archive_filter}
              {confirmed_filter}
            ORDER BY {", ".join(order_parts)}
            LIMIT 1
            """,
            (business_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return row_to_dict(
            row,
            selected_columns,
            defaults={
                "display_status": None,
                "responsible_person": None,
                "assigned_by": None,
                "assigned_at": None,
                "role": "",
                "confirmed_by": None,
                "completed_at": None,
                "completed_by": None,
                "confirmed_at": None,
                "first_seen_at": None,
                "last_seen_at": None,
                "source_revision": None,
                "archive_reason": None,
                "archived_at": None,
                "ignored": 0,
            },
        )
    finally:
        if owns_conn:
            close_connection_after_use()


def _should_suppress_rescan_after_confirmed_archive(
    archived_task: Optional[Dict[str, Any]],
    fields: Dict[str, Any],
    file_type: Optional[int] = None,
) -> bool:
    """同一轮任务已确认归档后，源 Excel 未重置时禁止重扫重新生成待审查任务。"""
    if not archived_task:
        return False
    if archived_task.get("status") != Status.ARCHIVED:
        return False
    if archived_task.get("archive_reason") not in CONFIRMED_ARCHIVE_REASONS:
        return False
    if not archived_task.get("completed_at") or not archived_task.get("confirmed_at"):
        return False

    new_completed_val = str(fields.get("_completed_col_value", "") or "").strip()
    old_interface_time = archived_task.get("interface_time") or ""
    new_interface_time = fields.get("interface_time", "")

    # FU starts a new cycle only when the plan changes and D is cleared. Merely
    # clearing D for an already confirmed plan must not recreate the task.
    if int(file_type or 0) == 7 and not new_completed_val:
        return not should_reset_task_status(
            old_interface_time,
            new_interface_time,
            "",
            "",
        )

    if not new_completed_val:
        return False

    old_completed_val = "有值"
    if not old_interface_time or not new_interface_time:
        return True
    return not should_reset_task_status(
        old_interface_time,
        new_interface_time,
        old_completed_val,
        new_completed_val,
    )


def _get_task_lookup_columns(conn) -> List[str]:
    preferred_columns = [
        "id",
        "business_id",
        "file_type",
        "project_id",
        "interface_id",
        "source_file",
        "source_revision",
        "row_index",
        "interface_time",
        "status",
        "display_status",
        "assigned_by",
        "assigned_at",
        "role",
        "confirmed_at",
        "confirmed_by",
        "responsible_person",
        "completed_at",
        "completed_by",
        "response_number",
        "first_seen_at",
        "last_seen_at",
        "archive_reason",
        "archived_at",
        "ignored",
    ]
    return select_available_columns(conn, "tasks", preferred_columns)


def _task_row_to_dict(row, selected_columns) -> Dict[str, Any]:
    return row_to_dict(
        row,
        selected_columns,
        defaults={
            "business_id": None,
            "file_type": None,
            "project_id": None,
            "interface_id": None,
            "source_file": None,
            "row_index": None,
            "interface_time": None,
            "status": "open",
            "display_status": None,
            "assigned_by": None,
            "assigned_at": None,
            "role": "",
            "confirmed_at": None,
            "confirmed_by": None,
            "responsible_person": None,
            "completed_at": None,
            "completed_by": None,
            "response_number": None,
            "first_seen_at": None,
            "last_seen_at": None,
            "archive_reason": None,
            "archived_at": None,
            "source_revision": None,
            "ignored": 0,
        },
    )


def _fetch_task_by_exact_id(conn, selected_columns: List[str], task_id: str) -> Optional[Dict[str, Any]]:
    if not selected_columns:
        return None
    row = conn.execute(
        f"""
        SELECT {", ".join(selected_columns)}
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()
    if not row:
        return None
    return _task_row_to_dict(row, selected_columns)


def resolve_task_record(
    db_path: str,
    wal: bool,
    key: Dict[str, Any],
    conn=None,
) -> Optional[Dict[str, Any]]:
    """
    统一解析当前任务记录。

    口径：
    1. 先查精确 task_id
    2. 若未命中，或命中的是旧/已归档记录，则回退到最新非归档 business_id
    """
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    try:
        selected_columns = _get_task_lookup_columns(conn)
        if not selected_columns:
            return None

        exact_task_id = make_task_id(
            key['file_type'],
            key['project_id'],
            key['interface_id'],
            key['source_file'],
            key['row_index'],
        )
        exact_task = _fetch_task_by_exact_id(conn, selected_columns, exact_task_id)
        latest_task = find_task_by_business_id(
            db_path,
            wal,
            key['file_type'],
            key['project_id'],
            key['interface_id'],
            conn=conn,
        )
        latest_archive = find_latest_confirmed_archive_by_business_id(
            db_path,
            wal,
            key['file_type'],
            key['project_id'],
            key['interface_id'],
            conn=conn,
        )

        exact_status = str((exact_task or {}).get("status") or "").strip().lower()
        exact_active = exact_task if exact_task and exact_status != Status.ARCHIVED else None
        if _is_superseded_by_confirmed_archive(exact_active, latest_archive):
            exact_active = None

        if latest_task is None:
            return latest_archive or exact_task
        if exact_active is None:
            return latest_task
        if exact_active.get("id") == latest_task.get("id"):
            return latest_task

        exact_last_seen = str(exact_active.get("last_seen_at") or "").strip()
        latest_last_seen = str(latest_task.get("last_seen_at") or "").strip()

        if latest_last_seen and not exact_last_seen:
            return latest_task
        if latest_last_seen and exact_last_seen and latest_last_seen > exact_last_seen:
            return latest_task

        return exact_active
    finally:
        if owns_conn:
            close_connection_after_use()


def resolve_task_records(
    db_path: str,
    wal: bool,
    task_keys: List[Dict[str, Any]],
    conn=None,
) -> Dict[str, Dict[str, Any]]:
    """批量解析任务记录，避免界面按行往返查询 Registry。"""
    if not task_keys:
        return {}

    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    try:
        selected_columns = _get_task_lookup_columns(conn)
        available = set(selected_columns)
        if not {"id", "business_id", "status"}.issubset(available):
            return {
                task_id: task
                for key in task_keys
                for task_id, task in [(
                    make_task_id(
                        key["file_type"],
                        key["project_id"],
                        key["interface_id"],
                        key["source_file"],
                        key["row_index"],
                    ),
                    resolve_task_record(db_path, wal, key, conn=conn),
                )]
                if task is not None
            }

        exact_ids = []
        business_ids = []
        keyed_ids = []
        for key in task_keys:
            task_id = make_task_id(
                key["file_type"],
                key["project_id"],
                key["interface_id"],
                key["source_file"],
                key["row_index"],
            )
            business_id = make_business_id(
                key["file_type"],
                key["project_id"],
                key["interface_id"],
            )
            exact_ids.append(task_id)
            business_ids.append(business_id)
            keyed_ids.append((task_id, business_id))

        candidate_rows = {}

        def fetch_candidates(column_name: str, values: List[str]) -> None:
            unique_values = list(dict.fromkeys(value for value in values if value))
            for start in range(0, len(unique_values), 400):
                chunk = unique_values[start:start + 400]
                placeholders = ", ".join("?" for _ in chunk)
                rows = conn.execute(
                    f"""
                    SELECT rowid, {", ".join(selected_columns)}
                    FROM tasks
                    WHERE {column_name} IN ({placeholders})
                    """,
                    chunk,
                ).fetchall()
                for row in rows:
                    rowid = row[0]
                    if rowid in candidate_rows:
                        continue
                    task = _task_row_to_dict(row[1:], selected_columns)
                    task["_registry_rowid"] = rowid
                    candidate_rows[rowid] = task

        # business_id 查询负责取最新业务记录；id 查询兜底历史库中 business_id 异常的精确行。
        fetch_candidates("business_id", business_ids)
        fetch_candidates("id", exact_ids)

        tasks_by_id = {}
        tasks_by_business_id = {}
        for task in candidate_rows.values():
            task_id = str(task.get("id") or "")
            business_id = str(task.get("business_id") or "")
            if task_id:
                tasks_by_id[task_id] = task
            if business_id:
                tasks_by_business_id.setdefault(business_id, []).append(task)

        has_archive_reason = "archive_reason" in available
        has_confirmed_at = "confirmed_at" in available
        resolved_by_business_id = {}

        for business_id, candidates in tasks_by_business_id.items():
            archive_candidates = [
                task
                for task in candidates
                if str(task.get("status") or "").strip().lower() == Status.ARCHIVED
                and (
                    not has_archive_reason
                    or task.get("archive_reason") in CONFIRMED_ARCHIVE_REASONS
                )
                and (not has_confirmed_at or task.get("confirmed_at"))
            ]
            latest_archive = max(
                archive_candidates,
                key=lambda task: (
                    str(task.get("archived_at") or ""),
                    str(task.get("last_seen_at") or ""),
                    int(task.get("_registry_rowid") or 0),
                ),
                default=None,
            )

            active_candidates = [
                task
                for task in candidates
                if str(task.get("status") or "").strip().lower() != Status.ARCHIVED
            ]
            latest_task = max(
                active_candidates,
                key=lambda task: (
                    str(task.get("last_seen_at") or ""),
                    int(task.get("_registry_rowid") or 0),
                ),
                default=None,
            )
            if _is_superseded_by_confirmed_archive(latest_task, latest_archive):
                latest_task = None
            resolved_by_business_id[business_id] = (latest_task, latest_archive)

        result = {}
        for exact_task_id, business_id in keyed_ids:
            exact_task = tasks_by_id.get(exact_task_id)
            latest_task, latest_archive = resolved_by_business_id.get(
                business_id,
                (None, None),
            )

            exact_status = str((exact_task or {}).get("status") or "").strip().lower()
            exact_active = exact_task if exact_task and exact_status != Status.ARCHIVED else None
            if _is_superseded_by_confirmed_archive(exact_active, latest_archive):
                exact_active = None

            if latest_task is None:
                resolved = latest_archive or exact_task
            elif exact_active is None or exact_active.get("id") == latest_task.get("id"):
                resolved = latest_task
            else:
                exact_last_seen = str(exact_active.get("last_seen_at") or "").strip()
                latest_last_seen = str(latest_task.get("last_seen_at") or "").strip()
                if latest_last_seen and (
                    not exact_last_seen or latest_last_seen > exact_last_seen
                ):
                    resolved = latest_task
                else:
                    resolved = exact_active

            if resolved is not None:
                resolved = dict(resolved)
                resolved.pop("_registry_rowid", None)
                result[exact_task_id] = resolved

        return result
    finally:
        if owns_conn:
            close_connection_after_use()


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
    
    # 【修复】标准化时间格式进行比较（避免格式差异导致误判）
    # - 支持 yyyy.mm.dd / yyyy-mm-dd / yyyy年m月d日
    # - 支持 mm.dd / mm-dd / mm/dd：若另一侧含年份，则补齐年份后再比较
    # - 避免把 "25C2" 等非日期字符串误识别为日期
    def _extract_year_if_any(time_str: str):
        import re
        nums = re.findall(r'\d+', time_str or "")
        if len(nums) >= 3:
            try:
                return int(nums[0])
            except Exception:
                return None
        return None

    ref_year_old = _extract_year_if_any(old_time)
    ref_year_new = _extract_year_if_any(new_time)

    def normalize_time(time_str: str, prefer_year=None) -> str:
        if not time_str:
            return ""
        import re
        s = str(time_str).strip()

        # 仅在“形如 mm.dd / mm-dd / mm/dd”时才把两段数字当作月日
        has_mmdd_delim = bool(re.match(r'^\s*\d{1,2}\s*[./-]\s*\d{1,2}\s*$', s))

        nums = re.findall(r'\d+', s)
        if len(nums) >= 3:
            y, m, d = nums[0], nums[1], nums[2]
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        if len(nums) == 2 and has_mmdd_delim and prefer_year:
            m, d = nums[0], nums[1]
            return f"{int(prefer_year):04d}-{int(m):02d}-{int(d):02d}"

        # 兜底：只做分隔符统一
        return s.replace('.', '-').replace('/', '-').strip()

    # 互相补齐年份：如果一侧只有 mm.dd，另一侧有 yyyy-mm-dd，则以对方年份为准
    old_time_norm = normalize_time(old_time, prefer_year=ref_year_new)
    new_time_norm = normalize_time(new_time, prefer_year=ref_year_old)
    
    # 条件1：时间列变化
    if old_time_norm != new_time_norm:
        return True
    
    # 条件2：完成列从有值变为空
    if old_comp and not new_comp:
        return True
    
    # 其他情况：不重置
    return False

def upsert_task(
    db_path: Optional[str] = None,
    wal: bool = False,
    key: Optional[Dict[str, Any]] = None,
    fields: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    conn=None
) -> None:
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
    if key is None or fields is None:
        raise ValueError("upsert_task 需要提供 key 和 fields")
    if now is None:
        now = datetime.now()
    owns_conn = conn is None
    if conn is None:
        if not db_path:
            raise ValueError("upsert_task 需要 db_path 或 conn")
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
    old_task = find_task_by_business_id(
        db_path or "",
        wal,
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        conn=conn
    )
    
    # 【新增】在更新任务前，检查是否需要自动取消忽略
    if old_task and old_task.get('ignored') == 1:
        old_interface_time = old_task.get('interface_time_when_ignored', '')
        current_interface_time = fields.get('interface_time', '')
        
        if current_interface_time != old_interface_time:
            # 自动取消忽略
            fields['ignored'] = 0
            fields['ignored_at'] = None
            fields['ignored_by'] = None
            fields['interface_time_when_ignored'] = None
            fields['ignored_reason'] = None
            
            print(f"[Registry自动取消忽略] ✓ {key['interface_id']}")
            print(f"  原预期时间: {old_interface_time}")
            print(f"  新预期时间: {current_interface_time}")
    
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
            # 关键：仅当本次 upsert 来自“Excel全量/增量扫描”（携带 interface_time 或完成列值）时，才允许触发重置判断。
            # 指派/回文等“局部写入”钩子通常只更新 assigned_by/response_number 等字段，
            # 若用 fields.get('interface_time','') 会把新时间视为空字符串，从而误判“时间变化”，导致状态回退为“请指派”。
            has_interface_time = 'interface_time' in fields
            has_completed_col = '_completed_col_value' in fields
            if not has_interface_time and not has_completed_col:
                need_reset = False
            else:
                need_reset = should_reset_task_status(
                    old_task['interface_time'],
                    fields.get('interface_time', ''),
                    old_completed_val,
                    new_completed_val
                )
        
        # 【历史记录版本化】检测是否需要创建新轮次记录
        # 条件：completed_at变空 且 interface_time变化 且 之前有完整数据链（completed_at和confirmed_at都存在）
        if need_reset and old_task.get('completed_at') and old_task.get('confirmed_at'):
            # 有完整数据链，创建新轮次记录
            # 策略：归档旧记录（修改row_index释放UNIQUE约束），新记录使用当前row_index
            print(f"[Registry版本化] {key['interface_id']} 检测到更新/重置，之前有完整数据链，归档旧记录并创建新轮次")
            
            # 1. 归档旧记录，修改row_index避免UNIQUE约束冲突
            # 使用负数row_index标记归档记录：-1000000 - 时间戳后6位 - 原row_index后3位
            import time
            old_tid = old_task['id']
            old_row_index = old_task['row_index']
            archived_row_index = -1000000 - int(time.time() % 1000000) - (old_row_index % 1000)
            now_str = now.isoformat()
            
            # 先修改row_index和id（释放UNIQUE约束和主键冲突），再修改status
            # 新的id基于归档后的row_index计算
            from .util import make_task_id as calc_tid
            archived_tid = calc_tid(
                key['file_type'],
                key['project_id'],
                key['interface_id'],
                old_task['source_file'],
                archived_row_index
            )
            conn.execute("""
                UPDATE tasks
                SET id = ?,
                    row_index = ?,
                    status = 'archived',
                    archive_reason = 'updated',
                    archived_at = ?
                WHERE id = ?
            """, (archived_tid, archived_row_index, now_str, old_tid))
            conn.commit()
            print(f"[Registry版本化] 已归档旧记录: {old_tid} -> {archived_tid}，row_index {old_row_index} -> {archived_row_index}")
            
            # 2. 设置新记录的first_seen_at为更新日期格式
            update_date = now.strftime('%Y-%m-%d')
            fields['_versioned_first_seen'] = f"(更新日期){update_date}"
            # 3. 强制清空继承字段，确保是全新记录
            fields['status'] = Status.OPEN
            fields['display_status'] = '待完成' if old_task.get('responsible_person') else '请指派'
            # 【关键】显式设置为None，而不是不设置（避免后续继承逻辑覆盖）
            fields['completed_at'] = None
            fields['completed_by'] = None
            fields['confirmed_at'] = None
            fields['confirmed_by'] = None
            fields['response_number'] = None
            # 4. 保留指派信息
            if old_task.get('assigned_by'):
                fields['assigned_by'] = old_task['assigned_by']
                fields['assigned_at'] = old_task['assigned_at']
                fields['responsible_person'] = old_task['responsible_person']
            # 5. 跳过后续的need_reset逻辑（已经处理完毕）
            need_reset = False
            # 6. 标记old_task为None，避免后续继承逻辑
            old_task = None
            print(f"[Registry版本化] 新轮次记录的首次发现时间标注为: {fields['_versioned_first_seen']}")
        
        if need_reset:
            # 重置状态，但保留指派信息
            fields['status'] = Status.OPEN
            # 重置时优先看本次写入是否携带责任人（例如指派刚写入），否则再看旧任务
            rp = fields.get('responsible_person') or (old_task.get('responsible_person') if old_task else None)
            fields['display_status'] = '待完成' if rp else '请指派'
            rp = fields.get('responsible_person') or (old_task.get('responsible_person') if old_task else None)
            fields['display_status'] = '待完成' if rp else '请指派'
            fields['completed_at'] = None
            fields['completed_by'] = None
            fields['confirmed_at'] = None
            fields['confirmed_by'] = None
            # 【新增】重置时也确保清空忽略标记（如果之前自动取消忽略没触发）
            if not fields.get('ignored'):  # 如果没有显式设置，确保为0
                fields['ignored'] = 0
                fields['ignored_at'] = None
                fields['ignored_by'] = None
                fields['interface_time_when_ignored'] = None
                fields['ignored_reason'] = None
            
            if old_task and old_task.get('assigned_by') and not fields.get('assigned_by'):
                fields['assigned_by'] = old_task['assigned_by']
                fields['assigned_at'] = old_task['assigned_at']
                fields['responsible_person'] = old_task['responsible_person']
            
            print(f"[Registry继承] {key['interface_id']} 时间变化，重置状态")
        else:
            # 继承状态（智能判断）
            # 如果新状态是默认值'待完成'且旧任务有其他状态，则继承旧状态
            # 但如果新状态是明确设置的其他值（如'待审查'），则使用新值
            current_display_status = fields.get('display_status')
            
            # 若调用方明确要求覆盖 display_status（例如 on_assigned），则跳过“默认值继承”逻辑
            if fields.get('_force_display_status'):
                pass
            elif old_task and current_display_status == '待完成' and old_task['display_status'] and old_task['display_status'] != '待完成':
                # 默认值'待完成'，继承旧状态
                fields['display_status'] = old_task['display_status']
                print(f"[Registry继承] {key['interface_id']} 未变化，继承状态: {old_task['display_status']}")
            elif current_display_status and current_display_status != '待完成':
                # 明确设置的其他状态（如'待审查'），使用新值，不继承
                print(f"[Registry] {key['interface_id']} 状态明确设置为: {current_display_status}，不继承")
            elif old_task and not current_display_status and old_task['display_status']:
                # 没有设置display_status，继承旧值
                fields['display_status'] = old_task['display_status']
                print(f"[Registry继承] {key['interface_id']} 继承旧状态: {old_task['display_status']}")
            
            # 继承其他状态字段（仅当old_task存在时）
            if old_task:
                if not fields.get('status'):
                    fields['status'] = old_task['status']
                if not fields.get('completed_at'):
                    fields['completed_at'] = old_task['completed_at']
                if not fields.get('completed_by'):
                    fields['completed_by'] = old_task['completed_by']
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
    # 【修复】如果department为空，设置为"请室主任确认"
    if not department or str(department).strip() == '':
        department = '请室主任确认'
    interface_time = fields.get('interface_time', '')
    display_status = fields.get('display_status', '待完成')  # 【修复】确保总是有默认值
    now_str = now.isoformat()
    
    # 【历史记录版本化】使用自定义的first_seen_at（如果是新轮次记录）
    first_seen_at = fields.get('_versioned_first_seen', now_str)
    
    # 使用 INSERT ... ON CONFLICT 实现 upsert
    conn.execute(
        """
        INSERT INTO tasks (
            id, file_type, project_id, interface_id, source_file, source_revision, row_index,
            business_id,
            department, interface_time, role, status, 
            assigned_by, assigned_at, display_status, confirmed_by, responsible_person,
            response_number, completed_at, completed_by, confirmed_at,
            ignored, ignored_at, ignored_by, interface_time_when_ignored, ignored_reason,
            first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            business_id = excluded.business_id,
            source_revision = COALESCE(excluded.source_revision, source_revision),
            department = excluded.department,
            interface_time = excluded.interface_time,
            role = excluded.role,
            status = excluded.status,
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
            completed_at = excluded.completed_at,
            completed_by = excluded.completed_by,
            confirmed_at = excluded.confirmed_at,
            ignored = CASE 
                WHEN excluded.ignored IS NOT NULL THEN excluded.ignored
                ELSE ignored
            END,
            ignored_at = CASE 
                WHEN excluded.ignored IS NOT NULL THEN excluded.ignored_at
                ELSE ignored_at
            END,
            ignored_by = CASE 
                WHEN excluded.ignored IS NOT NULL THEN excluded.ignored_by
                ELSE ignored_by
            END,
            interface_time_when_ignored = CASE 
                WHEN excluded.ignored IS NOT NULL THEN excluded.interface_time_when_ignored
                ELSE interface_time_when_ignored
            END,
            ignored_reason = CASE 
                WHEN excluded.ignored IS NOT NULL THEN excluded.ignored_reason
                ELSE ignored_reason
            END,
            last_seen_at = excluded.last_seen_at
        """,
        (
            tid,
            key['file_type'], 
            key['project_id'], 
            key['interface_id'], 
            key['source_file'], 
            fields.get('_source_revision'),
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
            fields.get('completed_by'),
            fields.get('confirmed_at'),
            fields.get('ignored', None),
            fields.get('ignored_at', None),
            fields.get('ignored_by', None),
            fields.get('interface_time_when_ignored', None),
            fields.get('ignored_reason', None),
            first_seen_at,
            now_str
        )
    )
    conn.commit()
    
    if owns_conn:
        close_connection_after_use()

def write_event(
    db_path: Optional[str],
    wal: bool,
    event_type: str,
    payload: Dict[str, Any],
    now: datetime,
    conn=None
) -> None:
    """
    写入事件记录
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        event_type: 事件类型（EventType枚举）
        payload: 事件数据 {'file_type', 'project_id', 'interface_id'(可选), 'source_file'(可选), 'row_index'(可选), 'extra'(可选)}
        now: 当前时间
    """
    owns_conn = conn is None
    if conn is None:
        if not db_path:
            raise ValueError("write_event 需要 db_path 或 conn")
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
    if owns_conn:
        close_connection_after_use()

def mark_completed(db_path: str, wal: bool, key: Dict[str, Any], now: datetime, conn=None) -> None:
    """
    标记任务为已完成
    
    将任务状态从 open 更新为 completed，并记录 completed_at
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        key: 任务关键字段
        now: 当前时间
    """
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    
    task = resolve_task_record(db_path, wal, key, conn=conn)
    if not task:
        print(f"[Registry] mark_completed警告: 找不到非归档任务 {key['interface_id']}")
        if owns_conn:
            close_connection_after_use()
        return

    tid = task["id"]
    
    conn.execute(
        "UPDATE tasks SET status = ?, completed_at = ? WHERE id = ?",
        (Status.COMPLETED, now.isoformat(), tid)
    )
    conn.commit()
    if owns_conn:
        close_connection_after_use()

def _build_archived_task_identity(conn, task: Dict[str, Any], now: datetime) -> tuple:
    """为归档记录生成新的 task_id/row_index，释放原精确行给下一轮新任务。"""
    old_id = str(task["id"])
    source_file = str(task.get("source_file") or "")
    file_type = int(task.get("file_type") or 0)
    project_id = str(task.get("project_id") or "")
    interface_id = str(task.get("interface_id") or "")
    seed = int(now.timestamp() * 1000000) % 1000000000
    stable_hash = abs(hash(old_id)) % 100000

    for attempt in range(1000):
        archived_row_index = -1000000000 - seed - stable_hash - attempt
        archived_id = make_task_id(
            file_type,
            project_id,
            interface_id,
            source_file,
            archived_row_index,
        )
        exists = conn.execute(
            "SELECT 1 FROM tasks WHERE id = ? AND id != ? LIMIT 1",
            (archived_id, old_id),
        ).fetchone()
        if not exists:
            return archived_id, archived_row_index

    raise RuntimeError(f"无法为归档任务生成唯一ID: {old_id}")


def _load_active_business_tasks(
    conn,
    key: Dict[str, Any],
    business_id: str,
    preferred_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Load every active row belonging to one business lifecycle."""
    lookup_columns = _get_task_lookup_columns(conn)
    rows = conn.execute(
        f"""
        SELECT {", ".join(lookup_columns)}
        FROM tasks
        WHERE status != ?
          AND (
              business_id = ?
              OR (
                  business_id IS NULL
                  AND file_type = ?
                  AND project_id = ?
                  AND interface_id = ?
              )
          )
        ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END, last_seen_at DESC, rowid DESC
        """,
        (
            Status.ARCHIVED,
            business_id,
            int(key['file_type']),
            str(key['project_id']),
            str(key['interface_id']),
            preferred_id or "",
        ),
    ).fetchall()
    return [_task_row_to_dict(row, lookup_columns) for row in rows]


def _archive_active_business_tasks(
    conn,
    active_tasks: List[Dict[str, Any]],
    now: datetime,
    confirmed_by: Optional[str],
    archive_reason: str,
) -> List[Dict[str, Any]]:
    """Archive active siblings without committing the caller's transaction."""
    now_str = now.isoformat()
    archived_records = []
    for active_task in active_tasks:
        old_id = active_task["id"]
        old_row_index = int(active_task.get("row_index") or 0)
        archived_id, archived_row_index = _build_archived_task_identity(conn, active_task, now)
        conn.execute(
            """
            UPDATE tasks
            SET id = ?,
                row_index = ?,
                status = ?,
                completed_at = COALESCE(completed_at, ?),
                confirmed_at = ?,
                confirmed_by = ?,
                display_status = ?,
                archive_reason = ?,
                archived_at = ?,
                missing_since = NULL
            WHERE id = ? AND status != ?
            """,
            (
                archived_id,
                archived_row_index,
                Status.ARCHIVED,
                now_str,
                now_str,
                confirmed_by,
                '已审查',
                archive_reason,
                now_str,
                old_id,
                Status.ARCHIVED,
            ),
        )
        archived_records.append(
            {
                "original_id": old_id,
                "archived_id": archived_id,
                "original_row_index": old_row_index,
                "archived_row_index": archived_row_index,
            }
        )
    return archived_records


def _should_auto_confirm_from_new_source(
    old_task: Optional[Dict[str, Any]],
    key: Dict[str, Any],
    fields: Dict[str, Any],
) -> bool:
    """Close pending review when a newer source file already records completion."""
    if not old_task:
        return False
    if str(old_task.get("status") or "").strip().lower() != Status.COMPLETED:
        return False
    if str(old_task.get("display_status") or "").strip() not in {
        "待审查",
        "待指派人审查",
    }:
        return False

    completed_value = str(fields.get("_completed_col_value") or "").strip()
    if not completed_value or completed_value.lower() in {"nan", "none"}:
        return False

    old_source = os.path.normcase(os.path.basename(str(old_task.get("source_file") or "").strip()))
    new_source = os.path.normcase(os.path.basename(str(key.get("source_file") or "").strip()))
    if old_source and new_source and old_source != new_source:
        return True

    old_revision = str(old_task.get("source_revision") or "").strip()
    new_revision = str(fields.get("_source_revision") or "").strip()
    if old_revision and new_revision:
        return old_revision != new_revision
    if not new_revision:
        return False

    # Existing Registry databases have no revision token until their first
    # scan. Use mtime versus last_seen_at once, then normal token comparison.
    try:
        revision_mtime = int(new_revision.rsplit(":", 1)[1]) / 1_000_000_000
        last_seen = datetime.fromisoformat(str(old_task.get("last_seen_at") or "")).timestamp()
        return revision_mtime > last_seen + 1.0
    except (IndexError, TypeError, ValueError, OSError):
        return False


def mark_confirmed(db_path: str, wal: bool, key: Dict[str, Any], now: datetime, confirmed_by: str = None, conn=None) -> Optional[Dict[str, Any]]:
    """
    标记任务为已确认并立即归档。
    
    上级确认代表本轮任务闭环完成：写入 confirmed_at/confirmed_by 后直接归档，
    同时移动归档记录的 row_index/id，确保下次源文件再次扫描到同一业务接口时创建新任务。
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        key: 任务关键字段
        now: 当前时间
        confirmed_by: 确认人姓名（可选）
    """
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    
    task = resolve_task_record(db_path, wal, key, conn=conn)
    if not task:
        print(f"[Registry] mark_confirmed警告: 找不到非归档任务 {key['interface_id']}")
        if owns_conn:
            close_connection_after_use()
        return None

    if str(task.get("status") or "").strip().lower() == Status.ARCHIVED:
        print(f"[Registry] mark_confirmed警告: 任务已经归档 {key['interface_id']}")
        if owns_conn:
            close_connection_after_use()
        return None

    business_id = str(task.get("business_id") or "").strip() or make_business_id(
        key['file_type'], key['project_id'], key['interface_id']
    )
    active_tasks = _load_active_business_tasks(
        conn,
        key,
        business_id,
        preferred_id=task['id'],
    )
    if not active_tasks:
        print(f"[Registry] mark_confirmed警告: 找不到活动任务 {key['interface_id']}")
        if owns_conn:
            close_connection_after_use()
        return None

    target_task = next((item for item in active_tasks if item.get("id") == task.get("id")), active_tasks[0])
    tid = target_task["id"]
    original_row_index = int(target_task.get("row_index") or key.get("row_index") or 0)
    try:
        # 同一 business_id 只代表一个业务任务。确认时一并关闭旧源文件残留，
        # 否则当前行归档后，旧的 completed/待审查记录会在刷新时再次加回。
        archived_records = _archive_active_business_tasks(
            conn,
            active_tasks,
            now,
            confirmed_by,
            "confirmed_by_superior",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        if owns_conn:
            close_connection_after_use()
        raise

    target_archive = next(
        (item for item in archived_records if item["original_id"] == tid),
        archived_records[0],
    )
    if owns_conn:
        close_connection_after_use()
    return {
        "original_id": tid,
        "archived_id": target_archive["archived_id"],
        "original_row_index": original_row_index,
        "archived_row_index": target_archive["archived_row_index"],
        "archive_reason": "confirmed_by_superior",
        "archived_count": len(archived_records),
        "archived_task_ids": [item["archived_id"] for item in archived_records],
    }

def mark_unconfirmed(db_path: str, wal: bool, key: Dict[str, Any], now: datetime, conn=None) -> None:
    """
    取消确认任务（上级角色取消勾选）
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        key: 任务key (file_type, project_id, interface_id, source_file, row_index)
        now: 当前时间
    """
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    
    task = resolve_task_record(db_path, wal, key, conn=conn)
    if not task:
        print(f"[Registry] mark_unconfirmed警告: 找不到非归档任务 {key['interface_id']}")
        if owns_conn:
            close_connection_after_use()
        return

    tid = task["id"]
    
    # 取消确认：清除confirmed_at和confirmed_by，status改回COMPLETED，display_status改回"待审查"
    conn.execute(
        "UPDATE tasks SET status = ?, confirmed_at = NULL, confirmed_by = NULL, display_status = ? WHERE id = ?",
        (Status.COMPLETED, '待审查', tid)
    )
    conn.commit()
    print(f"[Registry] 已取消确认任务: {key['interface_id']}")
    if owns_conn:
        close_connection_after_use()

def mark_ignored_batch(
    db_path: str, 
    wal: bool, 
    task_keys: List[Dict[str, Any]], 
    ignored_by: str,
    ignored_reason: str = "",
    now: datetime = None,
    conn=None
) -> Dict[str, Any]:
    """
    批量标记任务为"忽略"状态
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        task_keys: 任务key列表，每个key包含 file_type, project_id, interface_id, 
                   source_file, row_index, interface_time
        ignored_by: 忽略操作人
        ignored_reason: 忽略原因（可选）
        now: 当前时间
    
    返回:
        {
            'success_count': int,  # 成功标记的数量
            'failed_tasks': [...]  # 失败的任务列表
        }
    """
    if now is None:
        now = datetime.now()
    
    print(f"\n[标记忽略] 开始批量忽略 {len(task_keys)} 个任务")
    print(f"[标记忽略] 操作人: {ignored_by}")
    print(f"[标记忽略] 原因: {ignored_reason if ignored_reason else '(无)'}")
    
    owns_conn = conn is None
    conn = conn or get_connection(db_path, wal)
    success_count = 0
    failed_tasks = []
    
    for idx, key in enumerate(task_keys, 1):
        try:
            interface_id = key['interface_id']
            print(f"\n[标记忽略] [{idx}/{len(task_keys)}] 处理接口: {interface_id}")
            
            # 1. 查找任务（使用business_id查找最新非归档任务）
            business_id = make_business_id(
                key['file_type'], 
                key['project_id'], 
                key['interface_id']
            )
            print(f"[标记忽略]   business_id: {business_id}")
            
            cursor = conn.execute("""
                SELECT id, status, ignored, responsible_person, completed_by, interface_time
                FROM tasks
                WHERE business_id = ?
                  AND status != 'archived'
                ORDER BY last_seen_at DESC
                LIMIT 1
            """, (business_id,))
            
            row = cursor.fetchone()
            if not row:
                print("[标记忽略]   ✗ 任务不存在")
                failed_tasks.append({
                    'interface_id': interface_id,
                    'reason': '任务不存在'
                })
                continue
            
            tid, status, already_ignored, resp_person, completed_by, interface_time = row
            print(f"[标记忽略]   任务ID: {tid}")
            print(f"[标记忽略]   当前状态: {status}")
            print(f"[标记忽略]   已忽略: {already_ignored}")
            print(f"[标记忽略]   责任人: {resp_person if resp_person else '(无)'}")
            print(f"[标记忽略]   完成人: {completed_by if completed_by else '(无)'}")
            print(f"[标记忽略]   预期时间: {interface_time if interface_time else '(无)'}")
            
            # 2. 检查是否已经被忽略
            if already_ignored == 1:
                print("[标记忽略]   ✗ 已经被忽略")
                failed_tasks.append({
                    'interface_id': interface_id,
                    'reason': '已经被忽略'
                })
                continue
            
            # 3. 标记为忽略（使用从数据库查询到的interface_time）
            print("[标记忽略]   执行UPDATE...")
            
            conn.execute("""
                UPDATE tasks
                SET ignored = 1,
                    ignored_at = ?,
                    ignored_by = ?,
                    interface_time_when_ignored = ?,
                    ignored_reason = ?
                WHERE id = ?
            """, (
                now.isoformat(),
                ignored_by,
                interface_time,
                ignored_reason,
                tid
            ))
            
            # 4. 创建忽略快照（用于后续变化检测）
            print("[标记忽略]   创建快照记录...")
            conn.execute("""
                INSERT OR REPLACE INTO ignored_snapshots (
                    file_type, project_id, interface_id, source_file, row_index,
                    snapshot_interface_time, snapshot_completed_col,
                    ignored_at, ignored_by, ignored_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                key['file_type'],
                key['project_id'],
                key['interface_id'],
                key['source_file'],
                key['row_index'],
                interface_time,  # 快照：预期时间
                None,  # 快照：完成时间列（暂时为None，后续可扩展）
                now.isoformat(),
                ignored_by,
                ignored_reason
            ))
            
            success_count += 1
            print("[标记忽略]   ✓ 成功（已创建快照）")
            
        except Exception as e:
            print(f"[标记忽略]   ✗ 失败: {e}")
            import traceback
            traceback.print_exc()
            failed_tasks.append({
                'interface_id': key.get('interface_id', '未知'),
                'reason': str(e)
            })
    
    conn.commit()
    print(f"\n[标记忽略] 完成! 成功{success_count}个，失败{len(failed_tasks)}个\n")
    if owns_conn:
        close_connection_after_use()
    
    return {
        'success_count': success_count,
        'failed_tasks': failed_tasks
    }

def get_display_status(
    db_path: str,
    wal: bool,
    task_keys: List[Dict[str, Any]],
    current_user_roles: List[str] = None,
    task_snapshots: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, str]:
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
    
    # 已提供批量快照时不再重复查库；兼容旧调用时仍优先走本地缓存读。
    conn = None if task_snapshots is not None else get_read_connection(db_path)
    result = {}
    
    # 判断用户角色类型
    try:
        from utils.dept_config import get_superior_keywords
        _superior_kw = get_superior_keywords()
    except Exception:
        _superior_kw = ['所领导', '室主任', '接口工程师', '管理员']

    is_designer = False
    is_superior = False
    if current_user_roles:
        for role in current_user_roles:
            if "设计人员" in role:
                is_designer = True
            if any(keyword in role for keyword in _superior_kw):
                is_superior = True
    
    # 导入延期判断函数
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.date_utils import is_date_overdue
    except Exception:
        # 如果导入失败，使用简单判断
        def is_date_overdue(date_str):
            return False
    
    try:
        if task_snapshots is None:
            selected_columns = select_available_columns(
                conn,
                "tasks",
                [
                    "status",
                    "display_status",
                    "assigned_by",
                    "role",
                    "confirmed_at",
                    "responsible_person",
                    "ignored",
                    "confirmed_by",
                    "last_seen_at",
                ],
            )
            if not selected_columns:
                return {}

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
            
            task = (
                task_snapshots.get(tid)
                if task_snapshots is not None
                else resolve_task_record(db_path, wal, key, conn=conn)
            )
            if not task:
                # 任务不存在，不显示状态
                continue

            display_status = task.get("display_status")
            role = task.get("role", "")
            confirmed_at = task.get("confirmed_at")
            responsible_person = task.get("responsible_person")
            ignored = task.get("ignored", 0)
            
            # 【新增】如果任务被忽略，完全不返回（UI中会被过滤）
            if ignored == 1:
                continue
            
            # 【修复】如果已确认，直接使用display_status（应该已经是"已审查"）
            if confirmed_at:
                # 已确认的任务，display_status应该已经是"已审查"
                # 如果不是（旧数据），使用"已审查"作为默认值
                display_text = display_status if display_status == '已审查' else '已审查'
                # 如果任务延期，在状态前加"（已延期）"
                if is_overdue:
                    display_text = f"（已延期）{display_text}"
                result[tid] = display_text
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
    
    阶段3：确认后7天归档
    - 遍历所有 status='confirmed' 的任务
    - 如果确认时间超过7天
    - 则归档：status='archived', archive_reason='confirmed_expired'
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        now: 当前扫描时间
        missing_keep_days: 消失后保持天数（超过则归档）
    """
    try:
        conn = get_connection(db_path, wal)
        now_str = now.isoformat()
        
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
        
        # 阶段2：归档超期任务（消失任务）
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
                        archive_reason = 'missing_from_source',
                        archived_at = ?
                    WHERE id = ?
                """, (now_str, task_id))
                
                # 写入归档事件
                write_event(db_path, wal, EventType.ARCHIVED, {
                    'task_id': task_id,
                    'interface_id': interface_id,
                    'extra': {
                        'reason': 'missing_from_source',
                        'missing_since': missing_since
                    }
                }, now, conn=conn)
            
            conn.commit()
            print(f"[Registry归档] 归档{len(archive_tasks)}个超过{missing_keep_days}天未见的任务")
        
        # 阶段3：确认后7天归档
        confirmed_cutoff_date = (now - timedelta(days=7)).isoformat()
        
        cursor = conn.execute("""
            SELECT id, interface_id, confirmed_at FROM tasks
            WHERE status = 'confirmed'
              AND confirmed_at IS NOT NULL
              AND confirmed_at < ?
        """, (confirmed_cutoff_date,))
        
        confirmed_archive_tasks = cursor.fetchall()
        
        if confirmed_archive_tasks:
            for task_id, interface_id, confirmed_at in confirmed_archive_tasks:
                conn.execute("""
                    UPDATE tasks
                    SET status = 'archived',
                        archive_reason = 'confirmed_expired',
                        archived_at = ?
                    WHERE id = ?
                """, (now_str, task_id))
                
                # 写入归档事件
                write_event(db_path, wal, EventType.ARCHIVED, {
                    'task_id': task_id,
                    'interface_id': interface_id,
                    'extra': {
                        'reason': 'confirmed_expired',
                        'confirmed_at': confirmed_at
                    }
                }, now, conn=conn)
            
            conn.commit()
            print(f"[Registry归档] 归档{len(confirmed_archive_tasks)}个确认超过7天的任务")
        
        close_connection_after_use()
    except Exception as e:
        print(f"[Registry] finalize_scan失败: {e}")
        import traceback
        traceback.print_exc()
        close_connection_after_use()

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
    # Step6：日志去噪 —— 默认仅汇总输出重置/归档等关键统计（需要逐条排查时设置 REGISTRY_VERBOSE=1）
    import os as _os
    verbose = (_os.getenv("REGISTRY_VERBOSE", "").strip() == "1")
    reset_time_changed_count = 0
    reset_time_changed_samples: list[str] = []
    auto_confirmed_count = 0
    
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
            old_task = find_task_by_business_id(
                db_path,
                wal,
                key['file_type'],
                key['project_id'],
                key['interface_id'],
                conn=conn
            )

            if _should_auto_confirm_from_new_source(old_task, key, fields):
                active_tasks = _load_active_business_tasks(
                    conn,
                    key,
                    business_id,
                    preferred_id=old_task.get("id"),
                )
                archived_records = _archive_active_business_tasks(
                    conn,
                    active_tasks,
                    now,
                    AUTO_CONFIRMED_BY_SOURCE_UPDATE,
                    "completed_in_new_source",
                )
                event_extra = json.dumps(
                    {
                        "automatic": True,
                        "reason": "completed_in_new_source",
                        "confirmed_by": AUTO_CONFIRMED_BY_SOURCE_UPDATE,
                        "previous_source_file": old_task.get("source_file"),
                        "archived_count": len(archived_records),
                    },
                    ensure_ascii=False,
                )
                for event_type in (EventType.CONFIRMED, EventType.ARCHIVED):
                    conn.execute(
                        """
                        INSERT INTO events (
                            ts, event, file_type, project_id, interface_id,
                            source_file, row_index, extra
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            now_str,
                            event_type,
                            int(key['file_type']),
                            str(key['project_id']),
                            str(key['interface_id']),
                            str(key['source_file']),
                            int(key['row_index']),
                            event_extra,
                        ),
                    )
                auto_confirmed_count += 1
                count += 1
                continue

            if not old_task:
                archived_task = find_latest_confirmed_archive_by_business_id(
                    db_path,
                    wal,
                    key['file_type'],
                    key['project_id'],
                    key['interface_id'],
                    conn=conn
                )
                if _should_suppress_rescan_after_confirmed_archive(
                    archived_task, fields, key.get("file_type")
                ):
                    if verbose:
                        print(
                            f"[Registry闭环] {key['interface_id']}: 已确认归档且源Excel仍为同一轮已完成状态，跳过重建任务"
                        )
                    continue
            
            # 【修正】row_index不匹配时的智能判断
            # 如果row_index差距较小（±100行以内），可能是Excel文件编辑导致的行号偏移，应该继承状态
            # 如果差距很大，可能是真正的不同任务，但仍然继承状态（避免状态丢失）
            # 注意：只有当接口时间等关键字段变化时才会重置状态，row_index变化本身不重置
            if old_task and old_task['row_index'] != key['row_index']:
                row_diff = abs(old_task['row_index'] - key['row_index'])
                if verbose and key['file_type'] == 2 and row_diff > 100:  # 文件2特别容易出现重复接口号
                    print(f"[Registry调试] 接口{key['interface_id']}: 行号变化较大(旧行={old_task['row_index']}, 新行={key['row_index']}, 差距={row_diff})，但仍继承状态")
                # 不将old_task设为None，继续使用它来继承状态
            
            # 【新增】基于快照检测预期时间变化并自动取消忽略
            # 这个检查要在预期时间变化重置之前，确保忽略状态被正确取消
            time_changed_due_to_ignore = False
            if old_task and old_task.get('ignored') == 1:
                # 查询忽略快照
                cursor = conn.execute("""
                    SELECT snapshot_interface_time, ignored_at, ignored_by, ignored_reason, row_index
                    FROM ignored_snapshots
                    WHERE file_type = ? AND project_id = ? AND interface_id = ?
                    ORDER BY ignored_at DESC
                    LIMIT 1
                """, (
                    key['file_type'],
                    key['project_id'],
                    key['interface_id']
                ))
                snapshot = cursor.fetchone()
            
                if snapshot:
                    snapshot_time, _, _, _, snapshot_row = snapshot
                    current_interface_time = fields.get('interface_time', '')
                
                    def normalize_time_for_ignore(time_str):
                        if not time_str:
                            return ""
                        import re
                        numbers = re.findall(r'\d+', str(time_str))
                        if len(numbers) >= 3:
                            return '-'.join(numbers[:3])
                        return str(time_str).replace('.', '-').replace('/', '-').strip()
                
                    snapshot_time_norm = normalize_time_for_ignore(snapshot_time)
                    current_time_norm = normalize_time_for_ignore(current_interface_time)
                
                    if verbose:
                        print(f"[忽略快照检查] 接口{key['interface_id']}")
                        print(f"  快照时间: '{snapshot_time}' -> 标准化: '{snapshot_time_norm}'")
                        print(f"  当前时间: '{current_interface_time}' -> 标准化: '{current_time_norm}'")
                        print(f"  快照行号: {snapshot_row}, 当前行号: {key['row_index']}")
                
                    if snapshot_time_norm and current_time_norm and snapshot_time_norm != current_time_norm:
                        print(f"[Registry自动取消忽略] {key['interface_id']}: 预期时间变化 ({snapshot_time_norm} -> {current_time_norm})")
                        time_changed_due_to_ignore = True
                    
                        # 取消忽略标记
                        fields['ignored'] = 0
                        fields['ignored_at'] = None
                        fields['ignored_by'] = None
                        fields['interface_time_when_ignored'] = None
                        fields['ignored_reason'] = None
                    
                        # 删除快照记录
                        conn.execute("""
                            DELETE FROM ignored_snapshots
                            WHERE file_type = ? AND project_id = ? AND interface_id = ?
                        """, (
                            key['file_type'],
                            key['project_id'],
                            key['interface_id']
                        ))
                        if verbose:
                            print("[Registry] 已删除忽略快照记录")
                    else:
                        if verbose:
                            print("  时间未变化，保持忽略状态")
                else:
                    if verbose:
                        print(f"[Registry调试] 接口{key['interface_id']}: 已忽略但没有找到快照记录")
        
            # 【关键】处理任务状态继承和重置逻辑
            if old_task:
                new_completed_val = fields.get('_completed_col_value', '')
                old_completed_val = '有值' if old_task['completed_at'] else ''
            
                # 检查是否因为时间变化取消了忽略
                need_force_reset = time_changed_due_to_ignore
            
                # 【关键修复】优先检查接口时间是否变化（预期时间变化应该触发归档和重置）
                if should_reset_task_status(old_task['interface_time'], fields.get('interface_time', ''), 
                                           old_completed_val, new_completed_val):
                    # 【新增】如果有完整数据链（completed_at和confirmed_at都存在），归档旧记录
                    if old_task.get('completed_at') and old_task.get('confirmed_at'):
                        if verbose:
                            print(f"[Registry版本化-批量] {key['interface_id']} 检测到预期时间变化，之前有完整数据链，归档旧记录")
                    
                        # 归档旧记录
                        import time as time_module
                        old_tid = old_task['id']
                        old_row_index = old_task['row_index']
                        archived_row_index = -1000000 - int(time_module.time() % 1000000) - (old_row_index % 1000)
                        now_str = now.isoformat()
                    
                        from .util import make_task_id as calc_tid
                        archived_tid = calc_tid(
                            key['file_type'],
                            key['project_id'],
                            key['interface_id'],
                            old_task['source_file'],
                            archived_row_index
                        )
                    
                        # 更新旧记录：修改id、row_index、status、archived_at
                        conn.execute("""
                            UPDATE tasks
                            SET id = ?,
                                row_index = ?,
                                status = ?,
                                archived_at = ?,
                                archive_reason = ?
                            WHERE id = ?
                        """, (archived_tid, archived_row_index, Status.ARCHIVED, now_str, 'task_reset_time_changed', old_tid))
                    
                        if verbose:
                            print(f"[Registry版本化-批量] 旧记录已归档: {old_tid} -> {archived_tid}")
                
                    # 预期时间变化，重置状态
                    reset_time_changed_count += 1
                    if verbose:
                        print(f"[Registry] 接口{key['interface_id']}: 预期时间变化，重置状态")
                    else:
                        if len(reset_time_changed_samples) < 3:
                            reset_time_changed_samples.append(str(key['interface_id']))
                    fields['display_status'] = '待完成' if old_task['responsible_person'] else '请指派'
                    fields['status'] = Status.OPEN
                    # 清除完成和确认相关字段
                    fields['completed_at'] = None
                    fields['completed_by'] = None
                    fields['confirmed_at'] = None
                    fields['confirmed_by'] = None
                    # 保留指派信息
                    if old_task['assigned_by']:
                        fields['assigned_by'] = old_task['assigned_by']
                        fields['assigned_at'] = old_task['assigned_at']
                        fields['responsible_person'] = old_task['responsible_person']
            
                # 【次优先】检查完成列是否被清空（包括已确认的任务）
                elif not new_completed_val and old_task['completed_at']:
                    # 【修复】如果有完整数据链（completed_at和confirmed_at都存在），先归档旧记录
                    if old_task.get('completed_at') and old_task.get('confirmed_at'):
                        if verbose:
                            print(f"[Registry版本化-批量] {key['interface_id']} 完成列被清空，之前有完整数据链，归档旧记录")
                    
                        # 归档旧记录
                        import time as time_module
                        old_tid = old_task['id']
                        old_row_index = old_task['row_index']
                        archived_row_index = -1000000 - int(time_module.time() % 1000000) - (old_row_index % 1000)
                        now_str = now.isoformat()
                    
                        from .util import make_task_id as calc_tid
                        archived_tid = calc_tid(
                            key['file_type'],
                            key['project_id'],
                            key['interface_id'],
                            old_task['source_file'],
                            archived_row_index
                        )
                    
                        # 更新旧记录：修改id、row_index、status、archived_at
                        conn.execute("""
                            UPDATE tasks
                            SET id = ?,
                                row_index = ?,
                                status = ?,
                                archived_at = ?,
                                archive_reason = ?
                            WHERE id = ?
                        """, (archived_tid, archived_row_index, Status.ARCHIVED, now_str, 'task_reset_completed_cleared', old_tid))
                    
                        if verbose:
                            print(f"[Registry版本化-批量] 旧记录已归档: {old_tid} -> {archived_tid}")
                
                    # 完成列被删除，强制重置（即使是已确认的任务也要重置）
                    if verbose:
                        print(f"[Registry] 接口{key['interface_id']}: 完成列被清空，重置状态（old_status={old_task['status']}）")
                    fields['display_status'] = '待完成' if old_task['responsible_person'] else '请指派'
                    fields['status'] = Status.OPEN
                    # 清除完成相关字段
                    fields['completed_at'] = None
                    fields['completed_by'] = None
                    fields['confirmed_at'] = None
                    fields['confirmed_by'] = None
                    # 保留指派信息
                    if old_task['assigned_by']:
                        fields['assigned_by'] = old_task['assigned_by']
                        fields['assigned_at'] = old_task['assigned_at']
                        fields['responsible_person'] = old_task['responsible_person']
            
                # 【新增】如果已确认且完成列仍有值，且未被取消忽略，保持确认状态
                elif old_task['status'] == Status.CONFIRMED and old_task['confirmed_at'] and new_completed_val and not need_force_reset:
                    # 已确认且完成列未被清空，保持确认状态
                    if verbose:
                        print(f"[Registry] 接口{key['interface_id']}: 已确认且完成列有值，保持确认状态")
                    fields['status'] = Status.CONFIRMED
                    # 【修复】如果旧状态是"已审查"则保持，否则设置为"已审查"
                    # 因为已确认的任务，其display_status应该反映真实状态
                    old_display_status = old_task.get('display_status') or ''
                    if old_display_status == '已审查':
                        fields['display_status'] = '已审查'
                    else:
                        # 旧数据可能是"待审查"等，统一更正为"已审查"
                        fields['display_status'] = '已审查'
                    fields['confirmed_at'] = old_task['confirmed_at']
                    fields['confirmed_by'] = old_task['confirmed_by']
                    fields['completed_at'] = old_task['completed_at']
                    fields['completed_by'] = old_task['completed_by']
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
                    # 【修复】不继承ignored状态，如果已经明确设置了ignored=0（取消忽略），应该保持
                    # 如果fields中没有设置ignored，则继承旧值
                    if 'ignored' not in fields and old_task.get('ignored'):
                        fields['ignored'] = old_task['ignored']
                        fields['ignored_at'] = old_task.get('ignored_at')
                        fields['ignored_by'] = old_task.get('ignored_by')
                        fields['interface_time_when_ignored'] = old_task.get('interface_time_when_ignored')
                        fields['ignored_reason'] = old_task.get('ignored_reason')
            
            # 【关键】执行INSERT（不管old_task是否存在都要执行）
            status = fields.get('status', Status.OPEN)
            department = fields.get('department', '')
            # 【修复】如果department为空，设置为"请室主任确认"
            if not department or str(department).strip() == '':
                department = '请室主任确认'
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
            
            # 【新增】从fields获取ignored相关字段
            # 【修复】默认值改为None，避免覆盖已忽略的任务
            ignored = fields.get('ignored', None)
            ignored_at = fields.get('ignored_at')
            ignored_by = fields.get('ignored_by')
            interface_time_when_ignored = fields.get('interface_time_when_ignored')
            ignored_reason = fields.get('ignored_reason')
            
            conn.execute(
                """
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file, source_revision, row_index,
                    business_id,
                    department, interface_time, role, status, display_status,
                    first_seen_at, last_seen_at,
                    assigned_by, assigned_at, responsible_person, confirmed_by,
                    completed_at, completed_by, confirmed_at, response_number,
                    ignored, ignored_at, ignored_by, interface_time_when_ignored, ignored_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    business_id = excluded.business_id,
                    source_revision = COALESCE(excluded.source_revision, source_revision),
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
                    completed_by = COALESCE(excluded.completed_by, completed_by),
                    confirmed_at = excluded.confirmed_at,
                    response_number = COALESCE(excluded.response_number, response_number),
                    ignored = COALESCE(excluded.ignored, ignored),
                    ignored_at = COALESCE(excluded.ignored_at, ignored_at),
                    ignored_by = COALESCE(excluded.ignored_by, ignored_by),
                    interface_time_when_ignored = COALESCE(excluded.interface_time_when_ignored, interface_time_when_ignored),
                    ignored_reason = COALESCE(excluded.ignored_reason, ignored_reason)
                """,
                (
                    tid,
                    key['file_type'], 
                    key['project_id'], 
                    key['interface_id'], 
                    key['source_file'], 
                    fields.get('_source_revision'),
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
                    fields.get('completed_by'),
                    confirmed_at,
                    fields.get('response_number'),
                    ignored,
                    ignored_at,
                    ignored_by,
                    interface_time_when_ignored,
                    ignored_reason
                )
            )
            count += 1
        
        conn.commit()
        # 汇总输出（避免大量逐条重置打印）
        if reset_time_changed_count and not verbose:
            suffix = ""
            if reset_time_changed_samples:
                suffix = f" (示例: {', '.join(reset_time_changed_samples)})"
            print(f"[Registry] 本轮批量：预期时间变化→重置状态 {reset_time_changed_count} 条{suffix}")
        if auto_confirmed_count:
            print(f"[Registry] 本轮批量：新源文件已填写完成列，自动审查归档 {auto_confirmed_count} 条")
        close_connection_after_use()
        return count
        
    except Exception as e:
        conn.rollback()
        print(f"[Registry] 批量upsert失败: {e}")
        
        # 通知数据库状态显示器
        try:
            from services.db_status import notify_error
            if _is_lock_error(e):
                # 锁冲突由上层重试逻辑处理，这里不要把状态打成“连接失败”。
                pass
            else:
                notify_error(f"数据写入失败: {str(e)[:50]}", show_dialog=False)
        except ImportError:
            pass
        
        close_connection_after_use()
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
        selected_columns = select_available_columns(
            conn,
            "tasks",
            [
                "id",
                "file_type",
                "project_id",
                "interface_id",
                "source_file",
                "row_index",
                "business_id",
                "department",
                "interface_time",
                "role",
                "status",
                "completed_at",
                "completed_by",
                "confirmed_at",
                "confirmed_by",
                "assigned_by",
                "assigned_at",
                "display_status",
                "responsible_person",
                "response_number",
                "ignored",
                "ignored_at",
                "ignored_by",
                "interface_time_when_ignored",
                "ignored_reason",
                "first_seen_at",
                "last_seen_at",
                "missing_since",
                "archive_reason",
                "archived_at",
            ],
        )
        if not selected_columns:
            return []

        has_business_id = "business_id" in select_available_columns(conn, "tasks", ["business_id"])
        order_by = "first_seen_at DESC" if "first_seen_at" in selected_columns else "rowid DESC"
        if file_type:
            if has_business_id:
                business_id = f"{file_type}|{project_id}|{interface_id}"
                sql = f"""
                    SELECT {", ".join(selected_columns)}
                    FROM tasks
                    WHERE business_id = ?
                    ORDER BY {order_by}
                """
                params = (business_id,)
            else:
                sql = f"""
                    SELECT {", ".join(selected_columns)}
                    FROM tasks
                    WHERE file_type = ? AND project_id = ? AND interface_id = ?
                    ORDER BY {order_by}
                """
                params = (file_type, project_id, interface_id)
        else:
            if has_business_id:
                business_id_pattern = f"%|{project_id}|{interface_id}"
                sql = f"""
                    SELECT {", ".join(selected_columns)}
                    FROM tasks
                    WHERE business_id LIKE ?
                    ORDER BY {order_by}
                """
                params = (business_id_pattern,)
            else:
                sql = f"""
                    SELECT {", ".join(selected_columns)}
                    FROM tasks
                    WHERE project_id = ? AND interface_id = ?
                    ORDER BY {order_by}
                """
                params = (project_id, interface_id)
        
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        
        # 转换为字典列表
        results = []
        for row in rows:
            results.append(row_to_dict(row, selected_columns))
        
        return results
        
    except Exception as e:
        print(f"[Registry] 查询历史失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        close_connection_after_use()


def find_tasks_for_force_assign(
    db_path: str, wal: bool, file_type: int, project_id: str, interface_id: str
) -> List[Dict[str, Any]]:
    """
    根据业务标识查找任务（用于强制指派）
    
    返回所有匹配的非归档任务记录（同一接口可能出现在多个源文件中）
    
    参数:
        db_path: 数据库路径
        wal: 是否使用WAL模式
        file_type: 文件类型（1-6）
        project_id: 项目号
        interface_id: 接口号
        
    返回:
        匹配的任务列表，每项包含:
        - source_file: 源文件名
        - row_index: 行号
        - file_type: 文件类型
        - project_id: 项目号
        - interface_id: 接口号
        - responsible_person: 当前责任人
        - display_status: 当前显示状态
    """
    conn = get_connection(db_path, wal)
    business_id = make_business_id(file_type, project_id, interface_id)
    
    try:
        selected_columns = select_available_columns(
            conn,
            "tasks",
            [
                "source_file",
                "row_index",
                "file_type",
                "project_id",
                "interface_id",
                "responsible_person",
                "display_status",
                "status",
            ],
        )
        if not selected_columns:
            return []

        has_business_id = "business_id" in select_available_columns(conn, "tasks", ["business_id"])
        status_filter = " AND status != 'archived'" if "status" in selected_columns else ""
        order_by = "last_seen_at DESC" if "last_seen_at" in select_available_columns(conn, "tasks", ["last_seen_at"]) else "rowid DESC"
        if has_business_id:
            sql = f"""
                SELECT {", ".join(selected_columns)}
                FROM tasks
                WHERE business_id = ?{status_filter}
                ORDER BY {order_by}
            """
            params = (business_id,)
        else:
            sql = f"""
                SELECT {", ".join(selected_columns)}
                FROM tasks
                WHERE file_type = ? AND project_id = ? AND interface_id = ?{status_filter}
                ORDER BY {order_by}
            """
            params = (file_type, project_id, interface_id)

        cursor = conn.execute(sql, params)
        
        rows = cursor.fetchall()
        results = []
        for row in rows:
            task = row_to_dict(
                row,
                selected_columns,
                defaults={"responsible_person": None, "display_status": None, "status": "open"},
            )
            results.append({
                'source_file': task.get('source_file', ''),
                'row_index': task.get('row_index', 0),
                'file_type': task.get('file_type', file_type),
                'project_id': task.get('project_id', project_id),
                'interface_id': task.get('interface_id', interface_id),
                'responsible_person': task.get('responsible_person'),
                'display_status': task.get('display_status'),
                'status': task.get('status', 'open'),
            })
        return results
        
    except Exception as e:
        print(f"[Registry] find_tasks_for_force_assign失败: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        close_connection_after_use()
