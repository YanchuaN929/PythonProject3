"""Table sampling utilities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def parse_table_ref(table_ref: str) -> Tuple[str, str]:
    """Parse table reference into schema/table."""

    if "." in table_ref:
        schema_name, table_name = table_ref.split(".", 1)
        return schema_name.strip("[] "), table_name.strip("[] ")
    return "dbo", table_ref.strip("[] ")


def qname(schema_name: str, table_name: str) -> str:
    """Quote schema.table safely."""

    return f"[{schema_name}].[{table_name}]"


def fetch_row_count(conn: Any, table_ref: str) -> int:
    """Fetch row count for a table."""

    schema_name, table_name = parse_table_ref(table_ref)
    sql = f"SELECT COUNT(1) FROM {qname(schema_name, table_name)}"
    cursor = conn.cursor()
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def sample_table(
    conn: Any,
    table_ref: str,
    top_n: int = 200,
    where_clause: Optional[str] = None,
) -> Dict[str, Any]:
    """Sample rows from a table."""

    schema_name, table_name = parse_table_ref(table_ref)
    where_sql = f" WHERE {where_clause}" if where_clause else ""
    sql = f"SELECT TOP {int(top_n)} * FROM {qname(schema_name, table_name)}{where_sql}"

    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    columns = [item[0] for item in cursor.description] if cursor.description else []

    records: List[Dict[str, Any]] = []
    for row in rows:
        rec = {columns[idx]: row[idx] for idx in range(len(columns))}
        records.append(rec)

    return {
        "table_ref": f"{schema_name}.{table_name}",
        "columns": columns,
        "row_count_sampled": len(records),
        "records": records,
    }
