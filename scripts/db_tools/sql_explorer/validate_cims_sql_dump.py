"""Offline validator for CIMS SQL dump files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence

from .roster import load_roster_names, validate_owner_values

HEX32_RE = re.compile(r"^[0-9a-fA-F]{32}$")
ZH_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")
OWNER_KEYWORDS = (
    "owner",
    "responsible",
    "assignee",
    "person",
    "principal",
    "created_by_id",
    "owned_by_id",
    "managed_by_id",
    "modified_by_id",
    "locked_by_id",
    "dept_user",
    "department",
    "shezong",
    "relevant_person",
    "compile_user",
    "delay_open_person",
    "reopen_person",
    "责任人",
    "负责人",
    "经办",
    "主办",
    "办理人",
    "设计人",
)
DEFAULT_TABLE_FILES = (
    "TA.sql",
    "IDIACP1000.sql",
    "ICMACP1000.sql",
    "INTINTERFACEDOC.sql",
    "SENDRECEIVEDATA.sql",
)
INVALID_OWNER_VALUES = {"", "none", "null", "nan", "无"}


def normalize_hex32(value: Any) -> str:
    text = str(value or "").strip().strip("\"'[]{}()")
    if HEX32_RE.fullmatch(text):
        return text.upper()
    return ""


def _is_current_flag(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip().upper()
    if text == "":
        return True
    return text in {"1", "Y", "TRUE", "T"}


def _decode_sql_token(token: str) -> Optional[str]:
    text = token.strip()
    if not text:
        return ""
    if text.upper() == "NULL":
        return None

    if text.upper().startswith("N'") and text.endswith("'"):
        value = text[2:-1]
        return value.replace("''", "'")
    if text.startswith("'") and text.endswith("'"):
        value = text[1:-1]
        return value.replace("''", "'")
    return text


def _split_sql_values(values_blob: str) -> List[Optional[str]]:
    items: List[str] = []
    buf: List[str] = []
    in_quote = False
    idx = 0
    total = len(values_blob)

    while idx < total:
        ch = values_blob[idx]
        if ch == "'":
            buf.append(ch)
            if in_quote and idx + 1 < total and values_blob[idx + 1] == "'":
                buf.append("'")
                idx += 2
                continue
            in_quote = not in_quote
            idx += 1
            continue

        if ch == "," and not in_quote:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        idx += 1

    items.append("".join(buf).strip())
    return [_decode_sql_token(item) for item in items]


def _extract_values_blob(sql_text: str) -> Optional[str]:
    upper = sql_text.upper()
    pos = upper.find("VALUES")
    if pos < 0:
        return None
    start = sql_text.find("(", pos)
    if start < 0:
        return None

    in_quote = False
    depth = 0
    idx = start
    total = len(sql_text)
    while idx < total:
        ch = sql_text[idx]
        if ch == "'":
            if in_quote and idx + 1 < total and sql_text[idx + 1] == "'":
                idx += 2
                continue
            in_quote = not in_quote
            idx += 1
            continue

        if not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return sql_text[start + 1 : idx]
        idx += 1
    return None


def iter_insert_rows(path: Path) -> Iterator[List[Optional[str]]]:
    buffer = ""
    collecting = False
    with path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            stripped = line.lstrip()
            upper = stripped.upper()
            if not collecting:
                if upper.startswith("INSERT INTO"):
                    buffer = line
                    collecting = True
                else:
                    continue
            else:
                buffer += line

            blob = _extract_values_blob(buffer)
            if blob is None:
                continue
            yield _split_sql_values(blob)
            buffer = ""
            collecting = False


def count_insert_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            if line.lstrip().upper().startswith("INSERT INTO"):
                count += 1
    return count


def parse_create_columns(path: Path) -> List[str]:
    columns: List[str] = []
    in_create = False
    with path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            raw = line.strip()
            upper = raw.upper()
            if not in_create and upper.startswith("CREATE TABLE"):
                in_create = True
                continue
            if not in_create:
                continue
            if raw.startswith(")"):
                break
            match = re.match(r"^\[([^\]]+)\]\s+", raw)
            if match:
                columns.append(match.group(1))
    return columns


def _best_name(first_name: Any, last_name: Any, keyed_name: Any, login_name: Any) -> str:
    first = str(first_name or "").strip()
    last = str(last_name or "").strip()
    full = f"{last}{first}".strip()
    if full:
        zh = ZH_NAME_RE.search(full)
        if zh:
            return zh.group(0)
        return full

    keyed = str(keyed_name or "").strip()
    if keyed and not normalize_hex32(keyed):
        zh = ZH_NAME_RE.search(keyed)
        if zh:
            return zh.group(0)
        return keyed.split()[0].strip()

    return str(login_name or "").strip()


def _find_col(columns: Sequence[str], *names: str) -> int:
    mapping = {item.lower(): idx for idx, item in enumerate(columns)}
    for name in names:
        if name.lower() in mapping:
            return mapping[name.lower()]
    return -1


def _safe_get(row: Sequence[Optional[str]], idx: int) -> Optional[str]:
    if idx < 0 or idx >= len(row):
        return None
    return row[idx]


def parse_department_map(path: Path) -> Dict[str, Dict[str, str]]:
    columns = parse_create_columns(path)
    id_idx = _find_col(columns, "id")
    is_current_idx = _find_col(columns, "is_current")
    name_idx = _find_col(columns, "name", "name_memo", "keyed_name")
    dept_no_idx = _find_col(columns, "dept_number")

    result: Dict[str, Dict[str, str]] = {}
    for row in iter_insert_rows(path):
        dept_id = normalize_hex32(_safe_get(row, id_idx))
        if not dept_id:
            continue
        if is_current_idx >= 0 and not _is_current_flag(_safe_get(row, is_current_idx)):
            continue
        dept_name = str(_safe_get(row, name_idx) or "").strip()
        dept_no = str(_safe_get(row, dept_no_idx) or "").strip()
        result[dept_id] = {
            "dept_id": dept_id,
            "dept_name": dept_name,
            "dept_number": dept_no,
        }
    return result


def parse_user_map(
    path: Path,
    department_map: Dict[str, Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    columns = parse_create_columns(path)
    id_idx = _find_col(columns, "id")
    is_current_idx = _find_col(columns, "is_current")
    keyed_name_idx = _find_col(columns, "keyed_name")
    first_name_idx = _find_col(columns, "first_name")
    last_name_idx = _find_col(columns, "last_name")
    login_name_idx = _find_col(columns, "login_name")
    department_idx = _find_col(columns, "department")

    result: Dict[str, Dict[str, str]] = {}
    for row in iter_insert_rows(path):
        user_id = normalize_hex32(_safe_get(row, id_idx))
        if not user_id:
            continue
        if is_current_idx >= 0 and not _is_current_flag(_safe_get(row, is_current_idx)):
            continue

        dept_id = normalize_hex32(_safe_get(row, department_idx))
        dept_info = department_map.get(dept_id, {})
        user_name = _best_name(
            _safe_get(row, first_name_idx),
            _safe_get(row, last_name_idx),
            _safe_get(row, keyed_name_idx),
            _safe_get(row, login_name_idx),
        )
        item = {
            "user_id": user_id,
            "user_name": user_name,
            "login_name": str(_safe_get(row, login_name_idx) or "").strip(),
            "dept_id": dept_id,
            "dept_name": str(dept_info.get("dept_name", "") or "").strip(),
            "dept_number": str(dept_info.get("dept_number", "") or "").strip(),
        }
        prev = result.get(user_id)
        if prev is None:
            result[user_id] = item
            continue
        prev_score = (1 if prev.get("user_name") else 0) + (1 if prev.get("dept_name") else 0)
        curr_score = (1 if item.get("user_name") else 0) + (1 if item.get("dept_name") else 0)
        if curr_score >= prev_score:
            result[user_id] = item
    return result


def _owner_column_names(columns: Sequence[str]) -> List[str]:
    result: List[str] = []
    for column in columns:
        lowered = column.lower()
        if any(keyword in lowered for keyword in OWNER_KEYWORDS):
            result.append(column)
    return result


def _hex_token_row_rate(values: Iterable[Any]) -> float:
    total = 0
    hit = 0
    token_re = re.compile(r"(?i)\b[0-9a-f]{32}\b")
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        total += 1
        if token_re.search(text):
            hit += 1
    if total == 0:
        return 0.0
    return round(hit / total, 6)


def _non_empty_count(values: Iterable[Any]) -> int:
    count = 0
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in INVALID_OWNER_VALUES:
            count += 1
    return count


def validate_owner_columns_for_table(
    path: Path,
    roster_names: set[str],
    user_map: Dict[str, Dict[str, str]],
    sample_target: int,
) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    owner_cols = _owner_column_names(columns)
    total_inserts = count_insert_rows(path)
    if total_inserts <= 0:
        return {
            "table": path.stem,
            "file": str(path),
            "columns": columns,
            "owner_columns": [],
            "owner_results": [],
            "total_inserts": 0,
            "sample_rows": 0,
            "sample_stride": 1,
            "warnings": ["未发现 INSERT 记录"],
        }
    if not owner_cols:
        return {
            "table": path.stem,
            "file": str(path),
            "columns": columns,
            "owner_columns": [],
            "owner_results": [],
            "total_inserts": total_inserts,
            "sample_rows": 0,
            "sample_stride": 1,
            "warnings": ["未发现责任人相关列（按关键词）"],
        }

    sample_stride = max(1, total_inserts // max(1, sample_target))
    col_idx = {name: columns.index(name) for name in owner_cols}
    values_by_col: Dict[str, List[Optional[str]]] = {name: [] for name in owner_cols}
    parse_error_rows = 0
    sample_rows = 0

    for idx, row in enumerate(iter_insert_rows(path), start=1):
        if (idx - 1) % sample_stride != 0:
            continue
        sample_rows += 1
        for col_name, col_pos in col_idx.items():
            if col_pos >= len(row):
                parse_error_rows += 1
                continue
            values_by_col[col_name].append(row[col_pos])

    results: List[Dict[str, Any]] = []
    for col_name in owner_cols:
        values = values_by_col[col_name]
        quality = validate_owner_values(values, roster_names, user_id_map=user_map)
        metric_score = (
            0.45 * float(quality.get("id_resolved_rate", 0.0))
            + 0.35 * float(quality.get("name_in_roster_rate", 0.0))
            + 0.20 * float(quality.get("resolved_dept_rate", 0.0))
        )
        results.append(
            {
                "column": col_name,
                "sample_values": len(values),
                "non_empty_values": _non_empty_count(values),
                "hex_token_row_rate": _hex_token_row_rate(values),
                "score": round(metric_score, 6),
                **quality,
            }
        )

    results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return {
        "table": path.stem,
        "file": str(path),
        "columns": columns,
        "owner_columns": owner_cols,
        "owner_results": results,
        "total_inserts": total_inserts,
        "sample_rows": sample_rows,
        "sample_stride": sample_stride,
        "warnings": [f"解析列索引越界计数: {parse_error_rows}"] if parse_error_rows else [],
    }


def build_markdown(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# CIMS SQL 离线解析验证报告")
    lines.append("")
    lines.append(f"- 生成时间: `{payload.get('generated_at', '')}`")
    lines.append(f"- dump目录: `{payload.get('dump_dir', '')}`")
    lines.append(f"- 名单人数: `{payload.get('roster_count', 0)}`")
    lines.append("")

    identity = payload.get("identity_summary", {})
    lines.append("## USER / DEPARTMENT 映射")
    lines.append(f"- USER有效ID数: `{identity.get('user_count', 0)}`")
    lines.append(f"- DEPARTMENT有效ID数: `{identity.get('department_count', 0)}`")
    lines.append(f"- USER带部门占比: `{identity.get('user_with_dept_rate', 0.0)}`")
    lines.append(f"- USER姓名命中名单占比: `{identity.get('user_name_in_roster_rate', 0.0)}`")
    lines.append("")

    lines.append("## 关键表责任人列验证")
    for table in payload.get("tables", []):
        lines.append("")
        lines.append(f"### {table.get('table', '')}")
        lines.append(
            f"- 总行数 `{table.get('total_inserts', 0)}`，抽样 `{table.get('sample_rows', 0)}`，"
            f"步长 `{table.get('sample_stride', 1)}`"
        )
        if table.get("warnings"):
            for item in table.get("warnings", []):
                lines.append(f"- 警告: {item}")
        owner_results = table.get("owner_results", [])
        if not owner_results:
            lines.append("- 未得到责任人候选列结果。")
            continue
        for row in owner_results[:5]:
            lines.append(
                "- "
                f"`{row.get('column')}` score=`{row.get('score')}` "
                f"id解析率=`{row.get('id_resolved_rate')}` "
                f"部门解析率=`{row.get('resolved_dept_rate')}` "
                f"名单匹配率=`{row.get('name_in_roster_rate')}`"
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="离线验证 CIMS-sql 导出数据")
    parser.add_argument(
        "--dump-dir",
        default="sql_explorer_output/CIMS-sql",
        help="CIMS-sql 导出目录",
    )
    parser.add_argument(
        "--sample-target",
        type=int,
        default=60000,
        help="每张大表目标抽样行数（按步长采样）",
    )
    parser.add_argument(
        "--roster-file",
        default=None,
        help="姓名角色表（可选，不传则用默认 excel_bin/姓名角色表.xlsx）",
    )
    args = parser.parse_args()

    dump_dir = Path(args.dump_dir)
    if not dump_dir.exists():
        print(f"[ERROR] dump目录不存在: {dump_dir}")
        return 2

    user_sql = dump_dir / "USER.sql"
    dept_sql = dump_dir / "DEPARTMENT.sql"
    if not user_sql.exists() or not dept_sql.exists():
        print("[ERROR] USER.sql 或 DEPARTMENT.sql 不存在，无法做ID映射验证。")
        return 2

    roster_names = load_roster_names(args.roster_file)
    department_map = parse_department_map(dept_sql)
    user_map = parse_user_map(user_sql, department_map)

    user_with_dept = sum(1 for item in user_map.values() if item.get("dept_id"))
    user_with_name = sum(1 for item in user_map.values() if item.get("user_name"))
    user_name_in_roster = sum(
        1 for item in user_map.values() if item.get("user_name") in roster_names
    )
    identity_summary = {
        "user_count": len(user_map),
        "department_count": len(department_map),
        "user_with_dept_count": user_with_dept,
        "user_with_name_count": user_with_name,
        "user_with_dept_rate": round(user_with_dept / len(user_map), 6) if user_map else 0.0,
        "user_name_in_roster_count": user_name_in_roster,
        "user_name_in_roster_rate": (
            round(user_name_in_roster / user_with_name, 6) if user_with_name else 0.0
        ),
    }

    table_results: List[Dict[str, Any]] = []
    for file_name in DEFAULT_TABLE_FILES:
        file_path = dump_dir / file_name
        if not file_path.exists():
            table_results.append(
                {
                    "table": file_name.replace(".sql", ""),
                    "file": str(file_path),
                    "owner_results": [],
                    "warnings": ["文件不存在，跳过"],
                    "total_inserts": 0,
                    "sample_rows": 0,
                    "sample_stride": 1,
                }
            )
            continue
        print(f"[INFO] 正在验证: {file_name}")
        table_results.append(
            validate_owner_columns_for_table(
                file_path,
                roster_names=roster_names,
                user_map=user_map,
                sample_target=max(1000, int(args.sample_target)),
            )
        )

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dump_dir": str(dump_dir.resolve()),
        "sample_target": int(args.sample_target),
        "roster_count": len(roster_names),
        "identity_summary": identity_summary,
        "tables": table_results,
    }

    out_dir = dump_dir / "validation_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"offline_validation_{ts}.json"
    md_path = out_dir / f"offline_validation_{ts}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown(payload), encoding="utf-8")

    print(f"[SUCCESS] JSON报告: {json_path}")
    print(f"[SUCCESS] Markdown报告: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
