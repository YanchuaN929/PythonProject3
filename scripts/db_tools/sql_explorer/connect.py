"""SQL Server connection helpers with pymssql/pyodbc fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .config_store import ConnectionProfile

DEFAULT_ODBC_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server Native Client 11.0",
    "SQL Server",
)


class SqlConnectionError(RuntimeError):
    """Raised when all SQL Server connectors failed."""


@dataclass
class ConnectTestResult:
    """Connection test payload."""

    success: bool
    connector: str
    message: str
    details: Dict[str, Any]


def _connect_with_pymssql(profile: ConnectionProfile) -> Any:
    import pymssql  # type: ignore

    return pymssql.connect(
        server=profile.host,
        port=int(profile.port),
        user=profile.username,
        password=profile.password,
        database=profile.database,
        login_timeout=8,
        timeout=15,
        charset="UTF-8",
    )


def _connect_with_pyodbc(profile: ConnectionProfile) -> Any:
    import pyodbc  # type: ignore

    candidate_drivers = list(DEFAULT_ODBC_DRIVERS)
    if profile.driver_preference.startswith("odbc:"):
        candidate_drivers.insert(0, profile.driver_preference.split(":", 1)[1])

    for driver in candidate_drivers:
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={profile.host},{profile.port};"
            f"DATABASE={profile.database};"
            f"UID={profile.username};"
            f"PWD={profile.password};"
            f"Encrypt={'yes' if profile.encrypt else 'no'};"
            f"TrustServerCertificate={'yes' if profile.trust_server_certificate else 'no'};"
        )
        try:
            return pyodbc.connect(conn_str, timeout=8)
        except Exception:
            continue

    raise SqlConnectionError("pyodbc 无可用 SQL Server 驱动或连接失败")


def connect_sql_server(
    profile: ConnectionProfile,
) -> Tuple[Any, str]:
    """Connect SQL Server with fallback strategy."""

    preference = (profile.driver_preference or "auto").lower()
    errors = []

    strategies = []
    if preference == "pymssql":
        strategies = [("pymssql", _connect_with_pymssql), ("pyodbc", _connect_with_pyodbc)]
    elif preference == "pyodbc":
        strategies = [("pyodbc", _connect_with_pyodbc), ("pymssql", _connect_with_pymssql)]
    else:
        strategies = [("pymssql", _connect_with_pymssql), ("pyodbc", _connect_with_pyodbc)]

    for name, func in strategies:
        try:
            conn = func(profile)
            return conn, name
        except Exception as exc:  # pragma: no cover - depends on environment
            errors.append(f"{name}: {exc}")

    raise SqlConnectionError(" ; ".join(errors))


def run_connect_test(profile: ConnectionProfile) -> ConnectTestResult:
    """Run connection test and return metadata."""

    try:
        conn, connector = connect_sql_server(profile)
    except Exception as exc:
        return ConnectTestResult(
            success=False,
            connector="none",
            message=f"连接失败: {exc}",
            details={},
        )

    try:
        cursor = conn.cursor()
        # 保守语法，兼容不同驱动执行器（避免关键字别名导致语法报错）
        cursor.execute("SELECT @@SERVERNAME, DB_NAME(), SYSTEM_USER, SUSER_SNAME(), @@VERSION")
        row = cursor.fetchone()
        details = {
            "server_name": row[0] if row else "",
            "database_name": row[1] if row else "",
            "system_user_name": row[2] if row else "",
            "login_name": row[3] if row else "",
            "version_text": row[4] if row else "",
        }
        return ConnectTestResult(
            success=True,
            connector=connector,
            message="连接成功",
            details=details,
        )
    except Exception as exc:
        return ConnectTestResult(
            success=False,
            connector=connector,
            message=f"连接成功，但测试查询失败: {exc}",
            details={},
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass
