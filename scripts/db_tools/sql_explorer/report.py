"""Report writers for SQL explorer results."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON payload."""

    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], headers: List[str]) -> None:
    """Write generic CSV rows."""

    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def flatten_candidates_for_csv(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten candidate data for CSV export."""

    rows: List[Dict[str, Any]] = []
    for file_type, scoped in (report.get("file_type_candidates") or {}).items():
        for item in scoped.get("time_candidates", []):
            rows.append(
                {
                    "file_type": file_type,
                    "category": "time",
                    "table_ref": item.get("table_ref", ""),
                    "column": item.get("column", ""),
                    "score": item.get("score", 0.0),
                    "evidence": json.dumps(item.get("evidence", {}), ensure_ascii=False),
                }
            )
        for item in scoped.get("owner_candidates", []):
            rows.append(
                {
                    "file_type": file_type,
                    "category": "owner",
                    "table_ref": item.get("table_ref", ""),
                    "column": item.get("column", ""),
                    "score": item.get("score", 0.0),
                    "evidence": json.dumps(item.get("evidence", {}), ensure_ascii=False),
                }
            )
    return rows


def build_markdown_report(
    schema_snapshot: Dict[str, Any],
    discovery_result: Dict[str, Any],
    quality_rows: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    template_spec: Dict[str, Any],
) -> str:
    """Build markdown summary report."""

    lines: List[str] = []
    lines.append("# SQL 探索报告")
    lines.append("")
    lines.append(f"- 生成时间: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    lines.append(f"- 连接器: `{metadata.get('connector', 'unknown')}`")
    lines.append(f"- 数据库: `{metadata.get('database', '')}`")
    lines.append(f"- 表数量: `{schema_snapshot.get('table_count', 0)}`")
    if template_spec:
        lines.append(f"- 模板规范版本: `{template_spec.get('version', 'unknown')}`")
    lines.append("")
    lines.append("## 全局候选（Top）")
    lines.append("")
    lines.append("### 时间列候选")
    for idx, item in enumerate(discovery_result.get("global_time_candidates", []), start=1):
        lines.append(
            f"{idx}. `{item.get('table_ref')}.{item.get('column')}` "
            f"(score={item.get('score')})"
        )
    lines.append("")
    lines.append("### 责任人列候选")
    for idx, item in enumerate(discovery_result.get("global_owner_candidates", []), start=1):
        lines.append(
            f"{idx}. `{item.get('table_ref')}.{item.get('column')}` "
            f"(score={item.get('score')})"
        )
    lines.append("")
    lines.append("## 文件类型 1/2/3/4/6 推荐")
    for file_type in ("1", "2", "3", "4", "6"):
        scoped = (discovery_result.get("file_type_candidates") or {}).get(file_type, {})
        lines.append("")
        lines.append(f"### 文件 {file_type}")
        lines.append("- 时间列候选:")
        for item in scoped.get("time_candidates", [])[:3]:
            lines.append(
                f"  - `{item.get('table_ref')}.{item.get('column')}` "
                f"(score={item.get('score')})"
            )
    if template_spec:
        lines.append("")
        lines.append("## 模板基线")
        for file_type in ("1", "2", "3", "4", "6"):
            spec = (template_spec.get("file_types") or {}).get(file_type, {})
            if not spec:
                continue
            lines.append(
                f"- 文件{file_type} `{spec.get('name', '')}` "
                f"模板: `{spec.get('template_file', '')}`"
            )
        lines.append("- 责任人列候选:")
        for item in scoped.get("owner_candidates", [])[:3]:
            lines.append(
                f"  - `{item.get('table_ref')}.{item.get('column')}` "
                f"(score={item.get('score')})"
            )
    lines.append("")
    lines.append("## 责任人质量检查")
    if not quality_rows:
        lines.append("- 未检测到可用于责任人质量校验的列。")
    else:
        for row in quality_rows:
            lines.append(
                "- "
                f"`{row.get('table_ref')}.{row.get('column')}` "
                f"匹配率 `{row.get('name_in_roster_rate')}`，"
                f"多人率 `{row.get('multi_owner_rate')}`"
            )

    lines.append("")
    lines.append("## 下一步建议")
    lines.append("- 先人工确认每个文件类型的时间/责任人候选列前两名。")
    lines.append("- 再定义 SQL -> 程序标准 DataFrame 映射：")
    lines.append("  `接口号`、`项目号`、`科室`、`接口时间`、`责任人`、`原始行号`、`source_file`。")
    return "\n".join(lines) + "\n"
