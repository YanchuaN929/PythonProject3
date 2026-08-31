#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry 数据库兼容探测与恢复。

目标：
1. 预探测数据库是否可稳定读取
2. 对缺列旧库保持兼容
3. 对部分损坏库尽量抢救可读核心数据，重建新库后原子替换
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple


_PROBE_CACHE: Dict[str, Dict[str, Any]] = {}

_TASK_TARGET_COLUMNS = [
    "id",
    "file_type",
    "project_id",
    "interface_id",
    "source_file",
    "source_revision",
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
]

_EVENT_TARGET_COLUMNS = [
    "ts",
    "event",
    "file_type",
    "project_id",
    "interface_id",
    "source_file",
    "row_index",
    "extra",
]

_IGNORED_SNAPSHOT_TARGET_COLUMNS = [
    "file_type",
    "project_id",
    "interface_id",
    "source_file",
    "row_index",
    "snapshot_interface_time",
    "snapshot_completed_col",
    "ignored_at",
    "ignored_by",
    "ignored_reason",
]


def _log(message: str) -> None:
    try:
        log_dir = os.path.expanduser("~/.excel_processor")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "registry_recovery.log")
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        with open(log_path, "a", encoding="utf-8") as file_obj:
            file_obj.write(f"{ts} {message}\n")
    except Exception:
        pass


def _signature_for_path(db_path: str) -> Tuple[int, int]:
    stat = os.stat(db_path)
    return int(stat.st_mtime), int(stat.st_size)


def _quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _is_malformed_error(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "database disk image is malformed" in text
        or "file is not a database" in text
        or "malformed" in text
    )


def _connect_probe(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, check_same_thread=False, timeout=5.0)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cursor = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})")
    return [str(row[1]) for row in cursor.fetchall()]


def get_existing_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    try:
        return _get_table_columns(conn, table)
    except Exception:
        return []


def select_available_columns(
    conn: sqlite3.Connection,
    table: str,
    preferred_columns: Iterable[str],
) -> List[str]:
    existing = set(get_existing_columns(conn, table))
    return [column for column in preferred_columns if column in existing]


def row_to_dict(
    row: Optional[tuple],
    columns: Iterable[str],
    *,
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    result = dict(defaults or {})
    if row is None:
        return result
    result.update(dict(zip(columns, row)))
    return result


def probe_database_compatibility(db_path: str) -> Dict[str, Any]:
    if not db_path or not os.path.exists(db_path):
        return {
            "status": "missing",
            "healthy": True,
            "recoverable": False,
            "tables": {},
        }

    signature = _signature_for_path(db_path)
    cached = _PROBE_CACHE.get(db_path)
    if cached and cached.get("signature") == signature:
        return dict(cached)

    result: Dict[str, Any] = {
        "status": "healthy",
        "healthy": True,
        "recoverable": False,
        "tables": {},
        "signature": signature,
    }

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _connect_probe(db_path)
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        try:
            quick_check = conn.execute("PRAGMA quick_check").fetchone()
            if quick_check and str(quick_check[0]).lower() != "ok":
                result["status"] = "integrity_failed"
                result["healthy"] = False
                result["recoverable"] = True
                result["error"] = str(quick_check[0])
        except Exception as exc:
            if _is_malformed_error(exc):
                result["status"] = "malformed"
                result["healthy"] = False
                result["recoverable"] = True
                result["error"] = str(exc)
            else:
                raise

        for table in ("tasks", "events", "ignored_snapshots"):
            try:
                if _table_exists(conn, table):
                    result["tables"][table] = _get_table_columns(conn, table)
            except Exception as exc:
                result["tables"][table] = {"error": str(exc)}
                if _is_malformed_error(exc):
                    result["status"] = "malformed"
                    result["healthy"] = False
                    result["recoverable"] = True
                    result["error"] = str(exc)
    except Exception as exc:
        result["status"] = "malformed" if _is_malformed_error(exc) else "error"
        result["healthy"] = False
        result["recoverable"] = _is_malformed_error(exc)
        result["error"] = str(exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    _PROBE_CACHE[db_path] = dict(result)
    return result


def _fetch_rows_in_rowid_range(
    conn: sqlite3.Connection,
    table: str,
    columns: Iterable[str],
    rowid_start: int,
    rowid_end: int,
) -> List[Dict[str, Any]]:
    selected_columns = list(columns)
    if not selected_columns or rowid_end < rowid_start:
        return []

    sql = (
        f"SELECT rowid, {', '.join(_quote_identifier(col) for col in selected_columns)} "
        f"FROM {_quote_identifier(table)} "
        "WHERE rowid >= ? AND rowid <= ? "
        "ORDER BY rowid"
    )
    cursor = conn.execute(sql, (rowid_start, rowid_end))
    rows = cursor.fetchall()
    results = []
    for row in rows:
        item = {"rowid": row[0]}
        for idx, col in enumerate(selected_columns, start=1):
            item[col] = row[idx]
        results.append(item)
    return results


def _read_table_rows_lenient(
    conn: sqlite3.Connection,
    table: str,
    columns: Iterable[str],
) -> List[Dict[str, Any]]:
    selected_columns = list(columns)
    if not selected_columns:
        return []

    try:
        max_rowid_row = conn.execute(
            f"SELECT MAX(rowid) FROM {_quote_identifier(table)}"
        ).fetchone()
    except Exception as exc:
        _log(f"lenient-read max-rowid failed table={table} error={exc}")
        return []

    max_rowid = int(max_rowid_row[0] or 0)
    if max_rowid <= 0:
        return []

    recovered: List[Dict[str, Any]] = []

    def scan_range(left: int, right: int) -> None:
        if left > right:
            return
        try:
            recovered.extend(
                _fetch_rows_in_rowid_range(conn, table, selected_columns, left, right)
            )
            return
        except Exception as exc:
            if not _is_malformed_error(exc):
                raise
            if left == right:
                _log(f"lenient-read skip row table={table} rowid={left} error={exc}")
                return
            mid = (left + right) // 2
            scan_range(left, mid)
            scan_range(mid + 1, right)

    batch_size = 200
    start = 1
    while start <= max_rowid:
        end = min(start + batch_size - 1, max_rowid)
        scan_range(start, end)
        start = end + 1

    return recovered


def _normalize_task_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    file_type = int(row.get("file_type") or 0)
    project_id = str(row.get("project_id") or "").strip()
    interface_id = str(row.get("interface_id") or "").strip()
    source_file = str(row.get("source_file") or "").strip()
    row_index = int(row.get("row_index") or 0)
    if not (file_type and project_id and interface_id and source_file and row_index):
        return None

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
    task_id = str(row.get("id") or f"{file_type}|{project_id}|{interface_id}|{source_file}|{row_index}")
    business_id = str(row.get("business_id") or f"{file_type}|{project_id}|{interface_id}")

    normalized = {
        "id": task_id,
        "file_type": file_type,
        "project_id": project_id,
        "interface_id": interface_id,
        "source_file": source_file,
        "row_index": row_index,
        "business_id": business_id,
        "department": str(row.get("department") or ""),
        "interface_time": str(row.get("interface_time") or ""),
        "role": str(row.get("role") or ""),
        "status": str(row.get("status") or "open"),
        "completed_at": row.get("completed_at"),
        "completed_by": row.get("completed_by"),
        "confirmed_at": row.get("confirmed_at"),
        "confirmed_by": row.get("confirmed_by"),
        "assigned_by": row.get("assigned_by"),
        "assigned_at": row.get("assigned_at"),
        "display_status": row.get("display_status"),
        "responsible_person": row.get("responsible_person"),
        "response_number": row.get("response_number"),
        "ignored": int(row.get("ignored") or 0),
        "ignored_at": row.get("ignored_at"),
        "ignored_by": row.get("ignored_by"),
        "interface_time_when_ignored": row.get("interface_time_when_ignored"),
        "ignored_reason": row.get("ignored_reason"),
        "first_seen_at": row.get("first_seen_at") or now_iso,
        "last_seen_at": row.get("last_seen_at") or row.get("first_seen_at") or now_iso,
        "missing_since": row.get("missing_since"),
        "archive_reason": row.get("archive_reason"),
        "archived_at": row.get("archived_at"),
    }
    return normalized


def _normalize_event_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    event = str(row.get("event") or "").strip()
    ts = str(row.get("ts") or "").strip()
    if not event or not ts:
        return None
    return {
        "ts": ts,
        "event": event,
        "file_type": row.get("file_type"),
        "project_id": row.get("project_id"),
        "interface_id": row.get("interface_id"),
        "source_file": row.get("source_file"),
        "row_index": row.get("row_index"),
        "extra": row.get("extra"),
    }


def _normalize_ignored_snapshot_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    file_type = int(row.get("file_type") or 0)
    project_id = str(row.get("project_id") or "").strip()
    interface_id = str(row.get("interface_id") or "").strip()
    source_file = str(row.get("source_file") or "").strip()
    row_index = int(row.get("row_index") or 0)
    ignored_at = str(row.get("ignored_at") or "").strip()
    if not (file_type and project_id and interface_id and source_file and row_index and ignored_at):
        return None
    return {
        "file_type": file_type,
        "project_id": project_id,
        "interface_id": interface_id,
        "source_file": source_file,
        "row_index": row_index,
        "snapshot_interface_time": row.get("snapshot_interface_time"),
        "snapshot_completed_col": row.get("snapshot_completed_col"),
        "ignored_at": ignored_at,
        "ignored_by": row.get("ignored_by"),
        "ignored_reason": row.get("ignored_reason"),
    }


def rebuild_database_from_compatible_source(
    source_db_path: str,
    target_db_path: str,
) -> Dict[str, Any]:
    if not os.path.exists(source_db_path):
        raise FileNotFoundError(source_db_path)

    source_conn = _connect_probe(source_db_path)
    try:
        tasks_columns = (
            _get_table_columns(source_conn, "tasks") if _table_exists(source_conn, "tasks") else []
        )
        events_columns = (
            _get_table_columns(source_conn, "events") if _table_exists(source_conn, "events") else []
        )
        ignored_columns = (
            _get_table_columns(source_conn, "ignored_snapshots")
            if _table_exists(source_conn, "ignored_snapshots")
            else []
        )

        tasks_rows = [
            item
            for raw in _read_table_rows_lenient(
                source_conn,
                "tasks",
                [col for col in _TASK_TARGET_COLUMNS if col in tasks_columns],
            )
            if (item := _normalize_task_row(raw)) is not None
        ]
        event_rows = [
            item
            for raw in _read_table_rows_lenient(
                source_conn,
                "events",
                [col for col in _EVENT_TARGET_COLUMNS if col in events_columns],
            )
            if (item := _normalize_event_row(raw)) is not None
        ]
        ignored_rows = [
            item
            for raw in _read_table_rows_lenient(
                source_conn,
                "ignored_snapshots",
                [col for col in _IGNORED_SNAPSHOT_TARGET_COLUMNS if col in ignored_columns],
            )
            if (item := _normalize_ignored_snapshot_row(raw)) is not None
        ]
    finally:
        try:
            source_conn.close()
        except Exception:
            pass

    if not tasks_columns and not events_columns and not ignored_columns:
        raise RuntimeError("source database has no readable registry tables")

    target_dir = os.path.dirname(target_db_path)
    if target_dir:
        os.makedirs(target_dir, exist_ok=True)

    if os.path.exists(target_db_path):
        os.remove(target_db_path)

    target_conn = sqlite3.connect(target_db_path, timeout=30.0)
    try:
        from .db import init_db

        init_db(target_conn)

        if tasks_rows:
            sql = (
                f"INSERT OR REPLACE INTO tasks ({', '.join(_quote_identifier(col) for col in _TASK_TARGET_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in _TASK_TARGET_COLUMNS)})"
            )
            target_conn.executemany(
                sql,
                [[row.get(col) for col in _TASK_TARGET_COLUMNS] for row in tasks_rows],
            )

        if event_rows:
            sql = (
                f"INSERT INTO events ({', '.join(_quote_identifier(col) for col in _EVENT_TARGET_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in _EVENT_TARGET_COLUMNS)})"
            )
            target_conn.executemany(
                sql,
                [[row.get(col) for col in _EVENT_TARGET_COLUMNS] for row in event_rows],
            )

        if ignored_rows:
            sql = (
                "INSERT OR REPLACE INTO ignored_snapshots "
                f"({', '.join(_quote_identifier(col) for col in _IGNORED_SNAPSHOT_TARGET_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in _IGNORED_SNAPSHOT_TARGET_COLUMNS)})"
            )
            target_conn.executemany(
                sql,
                [[row.get(col) for col in _IGNORED_SNAPSHOT_TARGET_COLUMNS] for row in ignored_rows],
            )

        target_conn.commit()
    finally:
        try:
            target_conn.close()
        except Exception:
            pass

    return {
        "tasks": len(tasks_rows),
        "events": len(event_rows),
        "ignored_snapshots": len(ignored_rows),
        "readable_tables": sum(
            1 for columns in (tasks_columns, events_columns, ignored_columns) if columns
        ),
    }


def recover_database_in_place(db_path: str) -> Dict[str, Any]:
    if not db_path or not os.path.exists(db_path):
        return {"status": "missing"}

    db_dir = os.path.dirname(db_path) or os.getcwd()
    fd, temp_path = tempfile.mkstemp(prefix=".__registry_rebuild_", suffix=".db", dir=db_dir)
    os.close(fd)

    try:
        stats = rebuild_database_from_compatible_source(db_path, temp_path)
        if stats.get("readable_tables", 0) <= 0:
            raise RuntimeError("no readable tables recovered")

        backup_path = (
            f"{db_path}.corrupt.{time.strftime('%Y%m%d_%H%M%S', time.localtime())}.bak"
        )
        shutil.copy2(db_path, backup_path)
        os.replace(temp_path, db_path)
        _PROBE_CACHE.pop(db_path, None)
        _log(
            f"recover success db={db_path} backup={backup_path} "
            f"tasks={stats['tasks']} events={stats['events']} ignored_snapshots={stats['ignored_snapshots']}"
        )
        return {
            "status": "recovered",
            "backup_path": backup_path,
            **stats,
        }
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def ensure_database_compatible(db_path: str) -> Dict[str, Any]:
    probe = probe_database_compatibility(db_path)
    if probe.get("healthy", False) or not probe.get("recoverable", False):
        return probe

    _log(
        f"recover start db={db_path} status={probe.get('status')} error={probe.get('error', '')}"
    )
    try:
        return recover_database_in_place(db_path)
    except Exception as exc:
        _log(f"recover failed db={db_path} error={exc}")
        failed = dict(probe)
        failed["status"] = "recover_failed"
        failed["recover_error"] = str(exc)
        return failed
