#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared SQL providers for runtime SQL-backed workflows."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scripts.db_tools.sql_explorer.validate_cims_sql_dump import (
    iter_insert_rows,
    parse_create_columns,
    parse_department_map,
    parse_user_map,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OFFLINE_ROOT = PROJECT_ROOT / "example" / "CIMS-SQL-3.5"


class BaseSqlProvider:
    def source_label(self) -> str:
        raise NotImplementedError

    def get_table_rows(self, table_name: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def iter_table_rows(self, table_name: str):
        for row in self.get_table_rows(table_name):
            yield row

    def get_department_map(self) -> Dict[str, Dict[str, str]]:
        raise NotImplementedError

    def get_user_map(self) -> Dict[str, Dict[str, str]]:
        raise NotImplementedError

    def get_table_path(self, table_name: str) -> Optional[Path]:
        raise NotImplementedError

    def is_live(self) -> bool:
        return False


class OfflineDumpProvider(BaseSqlProvider):
    def __init__(self, root: Optional[os.PathLike[str] | str] = None):
        self.root = Path(root or DEFAULT_OFFLINE_ROOT)
        self._table_path_cache: Dict[str, Optional[Path]] = {}
        self._columns_cache: Dict[str, List[str]] = {}
        self._rows_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._department_map: Optional[Dict[str, Dict[str, str]]] = None
        self._user_map: Optional[Dict[str, Dict[str, str]]] = None

    def source_label(self) -> str:
        return f"offline:{self.root}"

    def is_available(self) -> bool:
        return self.root.exists()

    def get_table_path(self, table_name: str) -> Optional[Path]:
        key = str(table_name or "").strip().upper()
        if not key:
            return None
        if key in self._table_path_cache:
            return self._table_path_cache[key]

        direct = self.root / f"{key}.sql"
        dated = sorted(self.root.glob(f"{key}_*.sql"), reverse=True)
        path = dated[0] if dated else (direct if direct.exists() else None)
        self._table_path_cache[key] = path
        return path

    def get_columns(self, table_name: str) -> List[str]:
        key = str(table_name or "").strip().upper()
        if key in self._columns_cache:
            return self._columns_cache[key]
        path = self.get_table_path(key)
        columns = parse_create_columns(path) if path else []
        self._columns_cache[key] = list(columns)
        return self._columns_cache[key]

    def get_table_rows(self, table_name: str) -> List[Dict[str, Any]]:
        key = str(table_name or "").strip().upper()
        if key in self._rows_cache:
            return self._rows_cache[key]

        path = self.get_table_path(key)
        if path is None:
            self._rows_cache[key] = []
            return self._rows_cache[key]

        columns = self.get_columns(key)
        rows: List[Dict[str, Any]] = []
        for row in iter_insert_rows(path):
            payload = {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
            rows.append(payload)
        self._rows_cache[key] = rows
        return self._rows_cache[key]

    def iter_table_rows(self, table_name: str):
        key = str(table_name or "").strip().upper()
        path = self.get_table_path(key)
        if path is None:
            return
        columns = self.get_columns(key)
        for row in iter_insert_rows(path):
            yield {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}

    def get_department_map(self) -> Dict[str, Dict[str, str]]:
        if self._department_map is not None:
            return self._department_map
        path = self.get_table_path("DEPARTMENT")
        self._department_map = parse_department_map(path) if path else {}
        return self._department_map

    def get_user_map(self) -> Dict[str, Dict[str, str]]:
        if self._user_map is not None:
            return self._user_map
        path = self.get_table_path("USER")
        if not path:
            self._user_map = {}
            return self._user_map
        self._user_map = parse_user_map(path, self.get_department_map())
        return self._user_map


class LiveSqlProvider(BaseSqlProvider):
    def __init__(self):
        self._connector_name = ""

    def source_label(self) -> str:
        return f"live:{self._connector_name or 'sqlserver'}"

    def is_live(self) -> bool:
        return True

    def get_table_path(self, table_name: str) -> Optional[Path]:
        return None

    def _connect(self) -> Tuple[Any, str]:
        from scripts.db_tools.sql_explorer.config_store import load_profile
        from scripts.db_tools.sql_explorer.connect import connect_sql_server

        profile = load_profile()
        if profile is None:
            raise RuntimeError("sql_explorer connection profile is missing")
        conn, connector = connect_sql_server(profile)
        self._connector_name = connector
        return conn, connector

    @staticmethod
    def _is_pymssql_connection(conn: Any) -> bool:
        text = f"{getattr(conn.__class__, '__module__', '')}.{getattr(conn.__class__, '__name__', '')}".lower()
        return ("pymssql" in text) or ("_mssql" in text)

    def _execute_with_params(self, conn: Any, cursor: Any, sql_qmark: str, params: Sequence[Any]) -> None:
        if self._is_pymssql_connection(conn):
            cursor.execute(sql_qmark.replace("?", "%s"), tuple(params))
        else:
            cursor.execute(sql_qmark, tuple(params))

    def _fetch_rows(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn, _ = self._connect()
            cursor = conn.cursor()
            if params:
                self._execute_with_params(conn, cursor, sql, params)
            else:
                cursor.execute(sql)
            columns = [str(item[0]) for item in (cursor.description or [])]
            result: List[Dict[str, Any]] = []
            for row in cursor.fetchall() or []:
                result.append({columns[idx]: row[idx] for idx in range(len(columns))})
            return result
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def fetch_rows(self, sql_template: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        errors: List[str] = []
        for schema in ("innovator", "dbo"):
            try:
                return self._fetch_rows(sql_template.format(schema=schema), params=params)
            except Exception as exc:
                errors.append(f"{schema}: {exc}")
        raise RuntimeError(" ; ".join(errors))

    def can_connect(self) -> Tuple[bool, str]:
        conn = None
        try:
            conn, _ = self._connect()
            return True, ""
        except Exception as exc:
            return False, str(exc)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_table_rows(self, table_name: str) -> List[Dict[str, Any]]:
        table = str(table_name or "").strip()
        return self.fetch_rows(f"SELECT * FROM [{{schema}}].[{table}]")

    def iter_table_rows(self, table_name: str):
        for row in self.get_table_rows(table_name):
            yield row

    def get_department_map(self) -> Dict[str, Dict[str, str]]:
        result: Dict[str, Dict[str, str]] = {}
        for row in self.get_table_rows("DEPARTMENT"):
            dept_id = str(row.get("ID") or "").strip().upper()
            if not dept_id:
                continue
            result[dept_id] = {
                "dept_id": dept_id,
                "dept_name": str(row.get("NAME") or row.get("KEYED_NAME") or "").strip(),
                "dept_number": str(row.get("DEPT_NUMBER") or "").strip(),
            }
        return result

    def get_user_map(self) -> Dict[str, Dict[str, str]]:
        dept_map = self.get_department_map()
        result: Dict[str, Dict[str, str]] = {}
        for row in self.get_table_rows("USER"):
            user_id = str(row.get("ID") or "").strip().upper()
            if not user_id:
                continue
            dept_id = str(row.get("DEPARTMENT") or "").strip().upper()
            last_name = str(row.get("LAST_NAME") or "").strip()
            first_name = str(row.get("FIRST_NAME") or "").strip()
            keyed_name = str(row.get("KEYED_NAME") or "").strip()
            login_name = str(row.get("LOGIN_NAME") or "").strip()
            user_name = f"{last_name}{first_name}".strip() or keyed_name or login_name
            dept_info = dept_map.get(dept_id, {})
            result[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "login_name": login_name,
                "dept_id": dept_id,
                "dept_name": str(dept_info.get("dept_name", "") or "").strip(),
                "dept_number": str(dept_info.get("dept_number", "") or "").strip(),
            }
        return result


_OFFLINE_PROVIDER: Optional[OfflineDumpProvider] = None


def get_offline_provider(root: Optional[os.PathLike[str] | str] = None) -> OfflineDumpProvider:
    global _OFFLINE_PROVIDER
    if root is not None:
        return OfflineDumpProvider(root)
    if _OFFLINE_PROVIDER is None:
        _OFFLINE_PROVIDER = OfflineDumpProvider()
    return _OFFLINE_PROVIDER


def _try_live_provider() -> Optional[LiveSqlProvider]:
    provider = LiveSqlProvider()
    ok, _ = provider.can_connect()
    return provider if ok else None


def get_active_provider() -> BaseSqlProvider:
    live = _try_live_provider()
    if live is not None:
        return live
    return get_offline_provider()


def get_sql_backend_status() -> Dict[str, Any]:
    live = _try_live_provider()
    if live is not None:
        return {
            "mode": "live",
            "connected": "1",
            "message": f"实时SQL模式: {live.source_label()}",
            "offline_available": "0",
            "offline_root": "",
        }

    offline = get_offline_provider()
    offline_ok = offline.is_available()
    if offline_ok:
        return {
            "mode": "offline",
            "connected": "1",
            "message": f"离线快照模式: {offline.root}",
            "offline_available": "1",
            "offline_root": str(offline.root),
        }
    return {
        "mode": "unavailable",
        "connected": "0",
        "message": f"离线快照目录不存在: {offline.root}",
        "offline_available": "0",
        "offline_root": str(offline.root),
    }


def resolve_user_name(user_value: Any, user_map: Dict[str, Dict[str, str]]) -> str:
    text = str(user_value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if len(upper) == 32 and upper in user_map:
        return str(user_map.get(upper, {}).get("user_name", "") or "").strip()
    if len(text) > 32:
        for token in text.replace(",", " ").replace(";", " ").split():
            key = token.strip().upper()
            if len(key) == 32 and key in user_map:
                return str(user_map.get(key, {}).get("user_name", "") or "").strip()
    return text


def find_column(columns: Sequence[str], *names: str) -> int:
    mapping = {str(name).lower(): idx for idx, name in enumerate(columns)}
    for name in names:
        idx = mapping.get(str(name).lower())
        if idx is not None:
            return idx
    return -1
