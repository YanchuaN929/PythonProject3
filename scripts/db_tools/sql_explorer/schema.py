"""Schema scanning helpers for SQL Server."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def list_tables(
    conn: Any,
    include_views: bool = False,
    schema_whitelist: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    """List table/view names from INFORMATION_SCHEMA."""

    types = ["BASE TABLE"]
    if include_views:
        types.append("VIEW")

    params: List[Any] = list(types)
    clauses = ["TABLE_TYPE IN ({})".format(",".join("?" for _ in types))]
    if schema_whitelist:
        clauses.append("TABLE_SCHEMA IN ({})".format(",".join("?" for _ in schema_whitelist)))
        params.extend(schema_whitelist)

    sql = (
        "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
        "FROM INFORMATION_SCHEMA.TABLES "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY TABLE_SCHEMA, TABLE_NAME"
    )

    cursor = conn.cursor()
    cursor.execute(sql, tuple(params))
    return [
        {"schema": row[0], "table": row[1], "table_type": row[2]}
        for row in cursor.fetchall()
    ]


def list_columns(conn: Any, schema_name: str, table_name: str) -> List[Dict[str, Any]]:
    """List columns for a table."""

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            ORDINAL_POSITION,
            COALESCE(CHARACTER_MAXIMUM_LENGTH, -1) AS max_length
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """,
        (schema_name, table_name),
    )
    return [
        {
            "name": row[0],
            "data_type": row[1],
            "nullable": row[2] == "YES",
            "ordinal": int(row[3]),
            "max_length": int(row[4]),
        }
        for row in cursor.fetchall()
    ]


def list_primary_keys(conn: Any, schema_name: str, table_name: str) -> List[str]:
    """List primary key columns for a table."""

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT kcu.COLUMN_NAME
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
          ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
         AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
         AND tc.TABLE_NAME = kcu.TABLE_NAME
        WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
          AND tc.TABLE_SCHEMA = ?
          AND tc.TABLE_NAME = ?
        ORDER BY kcu.ORDINAL_POSITION
        """,
        (schema_name, table_name),
    )
    return [row[0] for row in cursor.fetchall()]


def list_indexes(conn: Any, schema_name: str, table_name: str) -> List[Dict[str, Any]]:
    """List indexes for a table from sys views."""

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            i.name AS index_name,
            i.is_unique,
            i.is_primary_key
        FROM sys.indexes i
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name = ? AND t.name = ? AND i.name IS NOT NULL
        ORDER BY i.name
        """,
        (schema_name, table_name),
    )
    return [
        {
            "index_name": row[0],
            "is_unique": bool(row[1]),
            "is_primary_key": bool(row[2]),
        }
        for row in cursor.fetchall()
    ]


def scan_schema_snapshot(
    conn: Any,
    include_views: bool = False,
    schema_whitelist: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Collect full schema snapshot."""

    tables = list_tables(conn, include_views=include_views, schema_whitelist=schema_whitelist)
    table_entries: List[Dict[str, Any]] = []

    for item in tables:
        schema_name = item["schema"]
        table_name = item["table"]
        table_entries.append(
            {
                **item,
                "columns": list_columns(conn, schema_name, table_name),
                "primary_keys": list_primary_keys(conn, schema_name, table_name),
                "indexes": list_indexes(conn, schema_name, table_name),
            }
        )

    return {"table_count": len(table_entries), "tables": table_entries}
