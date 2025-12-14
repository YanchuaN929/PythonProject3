from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterable, List, Optional

from .models import WriteTask


def _safe_json_dumps(data) -> str:
    try:
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        try:
            return json.dumps(str(data), ensure_ascii=False)
        except Exception:
            return "{}"


def _extract_fields(task: WriteTask) -> dict:
    """
    从payload中抽取展示/查询用字段（便于跨用户列表快速筛选）。
    注意：这里不引入任何新状态词，只记录原始信息。
    """
    file_path = ""
    file_type = None
    project_id = ""
    row_index = None

    try:
        if task.task_type == "response":
            file_path = str(task.payload.get("file_path", "") or "")
            file_type = task.payload.get("file_type")
            project_id = str(task.payload.get("project_id", "") or "")
            row_index = task.payload.get("row_index")
        elif task.task_type == "assignment":
            # 指派任务可能涉及多条，记录第一条用于快速定位
            assignments = task.payload.get("assignments") or []
            if assignments:
                first = assignments[0] or {}
                file_path = str(first.get("file_path", "") or "")
                file_type = first.get("file_type")
                project_id = str(first.get("project_id", "") or "")
                row_index = first.get("row_index")
    except Exception:
        pass

    return {
        "file_path": file_path,
        "file_type": int(file_type) if file_type is not None and str(file_type).isdigit() else None,
        "project_id": project_id,
        "row_index": int(row_index) if row_index is not None and str(row_index).isdigit() else None,
    }


def ensure_schema(conn) -> None:
    """
    在共享 registry.db 上创建写入任务日志表（幂等）。
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS write_tasks_log (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            submitted_by TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL,
            started_at TEXT DEFAULT NULL,
            completed_at TEXT DEFAULT NULL,
            error TEXT DEFAULT NULL,
            payload_json TEXT DEFAULT '{}',
            file_path TEXT DEFAULT '',
            file_type INTEGER DEFAULT NULL,
            project_id TEXT DEFAULT '',
            row_index INTEGER DEFAULT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wtl_updated_at ON write_tasks_log(updated_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wtl_submitted_at ON write_tasks_log(submitted_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_wtl_submitted_by ON write_tasks_log(submitted_by);")
    conn.commit()


def upsert_task(conn, task: WriteTask) -> None:
    """
    写入/更新一条全局日志记录（提交/状态变化都会调用）。
    """
    ensure_schema(conn)
    extra = _extract_fields(task)
    payload_json = _safe_json_dumps(task.payload)
    updated_at = task.completed_at or task.started_at or task.submitted_at

    conn.execute(
        """
        INSERT INTO write_tasks_log (
            task_id, task_type, submitted_by, submitted_at, description,
            status, started_at, completed_at, error, payload_json,
            file_path, file_type, project_id, row_index, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        ON CONFLICT(task_id) DO UPDATE SET
            status=excluded.status,
            started_at=excluded.started_at,
            completed_at=excluded.completed_at,
            error=excluded.error,
            description=excluded.description,
            payload_json=excluded.payload_json,
            file_path=excluded.file_path,
            file_type=excluded.file_type,
            project_id=excluded.project_id,
            row_index=excluded.row_index,
            updated_at=excluded.updated_at
        """,
        (
            task.task_id,
            task.task_type,
            task.submitted_by or "未知用户",
            task.submitted_at or "",
            task.description or "",
            task.status or "pending",
            task.started_at,
            task.completed_at,
            task.error,
            payload_json,
            extra.get("file_path") or "",
            extra.get("file_type"),
            extra.get("project_id") or "",
            extra.get("row_index"),
            updated_at or (task.submitted_at or ""),
        ),
    )
    conn.commit()


def list_tasks(conn, limit: int = 100, only_user: Optional[str] = None) -> List[WriteTask]:
    """
    读取共享日志记录，返回 WriteTask 列表（用于 UI 直接复用现有渲染逻辑）。
    """
    ensure_schema(conn)
    only_user = (only_user or "").strip()
    params = []
    where = ""
    if only_user:
        where = "WHERE submitted_by = ?"
        params.append(only_user)
    params.append(int(limit))

    rows = conn.execute(
        f"""
        SELECT task_id, task_type, submitted_by, description, submitted_at,
               status, started_at, completed_at, error, payload_json
        FROM write_tasks_log
        {where}
        ORDER BY submitted_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    tasks: List[WriteTask] = []
    for row in rows:
        task_id, task_type, submitted_by, description, submitted_at, status, started_at, completed_at, error, payload_json = row
        try:
            payload = json.loads(payload_json or "{}")
        except Exception:
            payload = {}
        tasks.append(
            WriteTask(
                task_id=task_id,
                task_type=task_type,
                payload=payload,
                submitted_by=submitted_by,
                description=description or "",
                submitted_at=submitted_at,
                status=status or "pending",
                started_at=started_at,
                completed_at=completed_at,
                error=error,
            )
        )
    return tasks


