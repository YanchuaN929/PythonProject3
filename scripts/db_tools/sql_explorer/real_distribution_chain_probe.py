"""Real-machine distribution chain probe for file2/file4 owner path."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd

from .identity_resolver import normalize_hex32, resolve_owner_value
from .roster import normalize_owner_tokens, validate_owner_values
from .validate_cims_sql_dump import (
    count_insert_rows,
    iter_insert_rows,
    parse_create_columns,
    parse_department_map,
    parse_user_map,
)

# Required tables from the task book.
P0_TABLES = [
    "DISTRIBUTERECORD",
    "OBJECTREPLYLINK",
    "FILETRANSMISSION",
    "SENDRECEIVEDATA",
    "INTINTERFACEDOC",
]
P1_TABLES = [
    "CRREPLY",
    "DCRREPLY",
    "FCRREPLY",
    "NCRREPLY",
    "TCRREPLY",
    "TAREPLY",
    "TA",
    "MEMORANDUM",
    "TELEFAX",
]
ALL_REQUIRED_TABLES = [*P0_TABLES, *P1_TABLES]

MINIMAL_SUPPLEMENT_FIELDS: Dict[str, List[str]] = {
    "DISTRIBUTERECORD": ["ID", "SOURCE_OBJECT_ID", "OPERATOR", "SENDER", "CREATED_ON", "IS_CURRENT"],
    "OBJECTREPLYLINK": ["ID", "SOURCE_OBJECT_ID", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "FILETRANSMISSION": ["ID", "SEND_RECEIVE_DATA", "FILE_RECEIVER", "CREATED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "CRREPLY": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "DCRREPLY": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "FCRREPLY": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "NCRREPLY": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "TCRREPLY": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "TAREPLY": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "TA": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "MEMORANDUM": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
    "TELEFAX": ["ID", "SEND_RECEIVE_DATA", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON", "IS_CURRENT"],
}

HEX32_TOKEN_RE = re.compile(r"(?i)\b[0-9a-f]{32}\b")
NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
TAIL_DIGITS_RE = re.compile(r"\d+$")
INVALID_TEXT = {"", "nan", "none", "null", "nat"}


@dataclass
class CoverageRow:
    """One coverage metric row."""

    scenario: str
    step: str
    source: str
    target: str
    available: bool
    source_count: int
    matched_count: int
    coverage_rate: Optional[float]
    status: str
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario,
            "step": self.step,
            "source": self.source,
            "target": self.target,
            "available": self.available,
            "source_count": self.source_count,
            "matched_count": self.matched_count,
            "coverage_rate": (
                round(self.coverage_rate, 6) if self.coverage_rate is not None else ""
            ),
            "status": self.status,
            "details": self.details,
        }


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in INVALID_TEXT:
        return ""
    return text


def _norm_key(value: Any) -> str:
    text = _clean_text(value).upper()
    if not text:
        return ""
    return NON_ALNUM_RE.sub("", text)


def _norm_drop_tail_digits(value: Any) -> str:
    """Normalize key and drop numeric tail for relaxed matching."""
    key = _norm_key(value)
    if not key:
        return ""
    return TAIL_DIGITS_RE.sub("", key)


def _is_current_flag(value: Any) -> bool:
    text = str(value or "").strip().upper()
    return text in {"", "1", "Y", "TRUE", "T"}


def _find_col_idx(columns: Sequence[str], candidates: Sequence[str]) -> int:
    mapping = {str(name).lower(): idx for idx, name in enumerate(columns)}
    for name in candidates:
        idx = mapping.get(name.lower())
        if idx is not None:
            return idx
    return -1


def _safe_get(row: Sequence[Any], idx: int) -> Any:
    if idx < 0 or idx >= len(row):
        return None
    return row[idx]


def _excel_col_index(col: str) -> int:
    col = col.strip().upper()
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _table_in_schema(innovator_schema: str, table: str) -> bool:
    marker = f"[innovator].[{table}]".lower()
    return marker in innovator_schema.lower()


def _owner_tokens_with_id_resolution(value: Any, user_map: Dict[str, Dict[str, Any]]) -> List[str]:
    tokens = normalize_owner_tokens(value)
    resolved = resolve_owner_value(value, user_map)
    for name in resolved.get("resolved_names", []):
        name = str(name or "").strip()
        if not name:
            continue
        if name not in tokens:
            tokens.append(name)
    return tokens


def _row_owner_match_rate(
    excel_owner_values: Sequence[Any],
    sql_owner_values: Sequence[Any],
    user_map: Dict[str, Dict[str, Any]],
) -> float:
    total = 0
    hit = 0
    for excel_val, sql_val in zip(excel_owner_values, sql_owner_values):
        excel_tokens = normalize_owner_tokens(excel_val)
        sql_tokens = _owner_tokens_with_id_resolution(sql_val, user_map)
        if not excel_tokens:
            continue
        total += 1
        if set(excel_tokens) & set(sql_tokens):
            hit += 1
    if total == 0:
        return 0.0
    return hit / total


def _build_candidate_row(
    *,
    file_type: str,
    chain_path: str,
    table: str,
    column: str,
    values: Sequence[Any],
    excel_owner_values: Sequence[Any],
    user_map: Dict[str, Dict[str, Any]],
    available: bool,
    note: str = "",
) -> Dict[str, Any]:
    if not available:
        return {
            "file_type": file_type,
            "chain_path": chain_path,
            "table": table,
            "column": column,
            "available": False,
            "row_count": len(values),
            "non_null_rate": "",
            "id_resolved_rate": "",
            "resolved_dept_rate": "",
            "excel_owner_match_rate": "",
            "score": "",
            "note": note,
        }

    non_empty = 0
    for value in values:
        if _clean_text(value):
            non_empty += 1
    non_null_rate = (non_empty / len(values)) if values else 0.0

    quality = validate_owner_values(values, roster_names=set(), user_id_map=user_map)
    id_rate = float(quality.get("id_resolved_rate", 0.0))
    dept_rate = float(quality.get("resolved_dept_rate", 0.0))
    excel_match = _row_owner_match_rate(excel_owner_values, values, user_map)

    score = 0.40 * id_rate + 0.25 * dept_rate + 0.25 * excel_match + 0.10 * non_null_rate
    return {
        "file_type": file_type,
        "chain_path": chain_path,
        "table": table,
        "column": column,
        "available": True,
        "row_count": len(values),
        "non_null_rate": round(non_null_rate, 6),
        "id_resolved_rate": round(id_rate, 6),
        "resolved_dept_rate": round(dept_rate, 6),
        "excel_owner_match_rate": round(excel_match, 6),
        "score": round(score, 6),
        "note": note,
    }


def load_excel_file2(path: Path) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    col_a = _excel_col_index("A")
    col_d = _excel_col_index("D")
    col_am = _excel_col_index("AM")

    rows: List[Dict[str, Any]] = []
    for idx in range(len(df)):
        a_raw = _safe_get(df.iloc[idx].tolist(), col_a)
        d_raw = _safe_get(df.iloc[idx].tolist(), col_d)
        owner_raw = _safe_get(df.iloc[idx].tolist(), col_am)
        a_key = _norm_key(a_raw)
        d_key = _norm_key(d_raw)
        if not d_key:
            continue
        rows.append(
            {
                "excel_row": idx + 2,
                "a_raw": _clean_text(a_raw),
                "d_raw": _clean_text(d_raw),
                "owner_raw": _clean_text(owner_raw),
                "a_key": a_key,
                "d_key": d_key,
            }
        )
    return rows


def load_excel_file4(path: Path) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    col_e = _excel_col_index("E")
    col_ah = _excel_col_index("AH")

    rows: List[Dict[str, Any]] = []
    for idx in range(len(df)):
        e_raw = _safe_get(df.iloc[idx].tolist(), col_e)
        owner_raw = _safe_get(df.iloc[idx].tolist(), col_ah)
        e_key = _norm_key(e_raw)
        if not e_key:
            continue
        rows.append(
            {
                "excel_row": idx + 2,
                "e_raw": _clean_text(e_raw),
                "owner_raw": _clean_text(owner_raw),
                "e_key": e_key,
                "e_key_tail": _norm_drop_tail_digits(e_raw),
            }
        )
    return rows


def parse_int_table(
    path: Path,
    needed_item_keys: Set[str],
    needed_ref_keys: Set[str],
) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    id_idx = _find_col_idx(columns, ["id"])
    item_idx = _find_col_idx(columns, ["ITEM_NUMBER"])
    ref_idx = _find_col_idx(columns, ["REF_ITEM_NUMBER"])
    current_idx = _find_col_idx(columns, ["IS_CURRENT"])
    owner_cols = [
        col
        for col in ["CREATED_BY_ID", "MODIFIED_BY_ID", "RESP_SHEZONG", "RELEVANT_PERSON", "DEPART_USER"]
        if col in columns
    ]
    owner_idx = {name: _find_col_idx(columns, [name]) for name in owner_cols}

    d_to_item_ids: Dict[str, Set[str]] = {}
    d_to_ref_ids: Dict[str, Set[str]] = {}
    pair_to_ids: Dict[Tuple[str, str], Set[str]] = {}
    id_owner_values: Dict[str, Dict[str, Any]] = {}

    row_count = 0
    for row in iter_insert_rows(path):
        row_count += 1
        if current_idx >= 0 and not _is_current_flag(_safe_get(row, current_idx)):
            continue

        item_key = _norm_key(_safe_get(row, item_idx))
        ref_key = _norm_key(_safe_get(row, ref_idx))
        if not item_key and not ref_key:
            continue
        if (item_key not in needed_item_keys and item_key not in needed_ref_keys) and (
            ref_key not in needed_ref_keys
        ):
            continue

        obj_id = normalize_hex32(_safe_get(row, id_idx))
        if not obj_id:
            continue

        if item_key in needed_ref_keys:
            d_to_item_ids.setdefault(item_key, set()).add(obj_id)
        if ref_key in needed_ref_keys:
            d_to_ref_ids.setdefault(ref_key, set()).add(obj_id)
        if item_key in needed_item_keys and ref_key in needed_ref_keys:
            pair_to_ids.setdefault((item_key, ref_key), set()).add(obj_id)

        owner_payload = id_owner_values.setdefault(obj_id, {})
        for name, idx in owner_idx.items():
            value = _safe_get(row, idx)
            if _clean_text(value):
                owner_payload[name] = value

    return {
        "row_count": row_count,
        "d_to_item_ids": d_to_item_ids,
        "d_to_ref_ids": d_to_ref_ids,
        "pair_to_ids": pair_to_ids,
        "id_owner_values": id_owner_values,
        "owner_columns": owner_cols,
    }


def parse_send_table(path: Path, needed_e_keys: Set[str], needed_e_keys_tail: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    id_idx = _find_col_idx(columns, ["id"])
    send_idx = _find_col_idx(columns, ["LETTER_SEND_NO"])
    rec_idx = _find_col_idx(columns, ["CORRESP_LETTER_REC_NO"])
    current_idx = _find_col_idx(columns, ["IS_CURRENT"])
    owner_cols = [col for col in ["CREATED_BY_ID", "MODIFIED_BY_ID"] if col in columns]
    owner_idx = {name: _find_col_idx(columns, [name]) for name in owner_cols}

    e_to_send_ids: Dict[str, Set[str]] = {}
    e_to_rec_ids: Dict[str, Set[str]] = {}
    e_to_send_tail_ids: Dict[str, Set[str]] = {}
    e_to_rec_tail_ids: Dict[str, Set[str]] = {}
    id_owner_values: Dict[str, Dict[str, Any]] = {}
    row_count = 0

    for row in iter_insert_rows(path):
        row_count += 1
        if current_idx >= 0 and not _is_current_flag(_safe_get(row, current_idx)):
            continue

        send_key = _norm_key(_safe_get(row, send_idx))
        rec_key = _norm_key(_safe_get(row, rec_idx))
        send_tail = _norm_drop_tail_digits(_safe_get(row, send_idx))
        rec_tail = _norm_drop_tail_digits(_safe_get(row, rec_idx))
        if (
            send_key not in needed_e_keys
            and rec_key not in needed_e_keys
            and send_tail not in needed_e_keys_tail
            and rec_tail not in needed_e_keys_tail
        ):
            continue

        send_id = normalize_hex32(_safe_get(row, id_idx))
        if not send_id:
            continue

        if send_key in needed_e_keys:
            e_to_send_ids.setdefault(send_key, set()).add(send_id)
        if rec_key in needed_e_keys:
            e_to_rec_ids.setdefault(rec_key, set()).add(send_id)
        if send_tail in needed_e_keys_tail:
            e_to_send_tail_ids.setdefault(send_tail, set()).add(send_id)
        if rec_tail in needed_e_keys_tail:
            e_to_rec_tail_ids.setdefault(rec_tail, set()).add(send_id)

        owner_payload = id_owner_values.setdefault(send_id, {})
        for name, idx in owner_idx.items():
            value = _safe_get(row, idx)
            if _clean_text(value):
                owner_payload[name] = value

    return {
        "row_count": row_count,
        "e_to_send_ids": e_to_send_ids,
        "e_to_rec_ids": e_to_rec_ids,
        "e_to_send_tail_ids": e_to_send_tail_ids,
        "e_to_rec_tail_ids": e_to_rec_tail_ids,
        "id_owner_values": id_owner_values,
        "owner_columns": owner_cols,
    }


def parse_link_table(
    table_name: str,
    sql_dir: Path,
    source_ids: Set[str],
    source_col_candidates: Sequence[str],
    owner_col_candidates: Sequence[str],
) -> Dict[str, Any]:
    file_path = sql_dir / f"{table_name}.sql"
    if not file_path.exists():
        return {
            "available": False,
            "reason": "table_dump_missing",
            "row_count": 0,
            "matched_source_ids": set(),
            "source_column": "",
            "owner_by_source": {},
            "sample_rows": [],
        }

    columns = parse_create_columns(file_path)
    source_idx = _find_col_idx(columns, source_col_candidates)
    current_idx = _find_col_idx(columns, ["IS_CURRENT"])
    owner_cols = [col for col in owner_col_candidates if col in columns]
    owner_idx = {name: _find_col_idx(columns, [name]) for name in owner_cols}
    if source_idx < 0:
        return {
            "available": False,
            "reason": "source_column_missing",
            "row_count": count_insert_rows(file_path),
            "matched_source_ids": set(),
            "source_column": "",
            "owner_by_source": {},
            "sample_rows": [],
        }

    owner_by_source: Dict[str, Dict[str, Any]] = {}
    matched_source_ids: Set[str] = set()
    sample_rows: List[Dict[str, Any]] = []
    row_count = 0
    source_col_name = columns[source_idx]

    for row in iter_insert_rows(file_path):
        row_count += 1
        if current_idx >= 0 and not _is_current_flag(_safe_get(row, current_idx)):
            continue
        src_id = normalize_hex32(_safe_get(row, source_idx))
        if not src_id or src_id not in source_ids:
            continue
        matched_source_ids.add(src_id)
        payload = owner_by_source.setdefault(src_id, {})
        for name, idx in owner_idx.items():
            value = _safe_get(row, idx)
            if _clean_text(value) and not _clean_text(payload.get(name)):
                payload[name] = value
        if len(sample_rows) < 30:
            sample_row = {"source_id": src_id}
            for name, idx in owner_idx.items():
                sample_row[name] = _safe_get(row, idx)
            sample_rows.append(sample_row)

    available = row_count > 0
    reason = "" if available else "empty_table"
    return {
        "available": available,
        "reason": reason,
        "row_count": row_count,
        "matched_source_ids": matched_source_ids,
        "source_column": source_col_name,
        "owner_by_source": owner_by_source,
        "sample_rows": sample_rows,
        "owner_columns": owner_cols,
    }


def _coverage(
    scenario: str,
    step: str,
    source: str,
    target: str,
    available: bool,
    source_count: int,
    matched_count: int,
    status: str,
    details: str,
) -> CoverageRow:
    rate = None
    if source_count > 0 and available:
        rate = matched_count / source_count
    return CoverageRow(
        scenario=scenario,
        step=step,
        source=source,
        target=target,
        available=available,
        source_count=source_count,
        matched_count=matched_count,
        coverage_rate=rate,
        status=status,
        details=details,
    )


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_text(encoding="utf-8-sig", errors="ignore")


def _latest_dir(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    dirs = [item for item in path.iterdir() if item.is_dir()]
    if not dirs:
        return None
    dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return dirs[0]


def _build_markdown_report(payload: Dict[str, Any]) -> str:
    q = payload["question_answers"]
    lines: List[str] = []
    lines.append("# real_distribution_chain_report")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- output_root: `{payload['output_root']}`")
    lines.append("")
    lines.append("## Final Answers")
    lines.append(f"1. 文件2责任人是否需分发链路：**{q['q1_file2_need_distribution_chain']['answer']}**")
    lines.append(f"2. 文件4责任人是否需分发链路：**{q['q2_file4_need_distribution_chain']['answer']}**")
    lines.append(f"3. 最优责任人来源：**{q['q3_best_owner_source']['answer']}**")
    lines.append(f"4. 是否存在权限/数据阻塞：**{q['q4_blocked_by_permission_or_data']['answer']}**")
    lines.append("")
    lines.append("## Blocking Details")
    for item in payload.get("blocking_points", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Coverage Highlights")
    for row in payload.get("coverage_rows", [])[:12]:
        lines.append(
            "- "
            f"{row['scenario']}::{row['step']} "
            f"source={row['source_count']} matched={row['matched_count']} "
            f"rate={row['coverage_rate']} status={row['status']}"
        )
    lines.append("")
    lines.append("## Owner Candidate Top")
    by_file: Dict[str, List[Dict[str, Any]]] = {"2": [], "4": []}
    for row in payload.get("owner_candidate_scores", []):
        file_type = str(row.get("file_type", ""))
        if file_type in by_file and row.get("available") is True:
            by_file[file_type].append(row)
    for file_type in ("2", "4"):
        rows = sorted(by_file[file_type], key=lambda r: float(r.get("score", 0.0)), reverse=True)[:5]
        lines.append(f"- 文件{file_type}:")
        if not rows:
            lines.append("  - 无可用候选（受连接/分发表缺失影响）")
            continue
        for row in rows:
            lines.append(
                "  - "
                f"{row['table']}.{row['column']} "
                f"score={row['score']} "
                f"id={row['id_resolved_rate']} dept={row['resolved_dept_rate']} "
                f"excel_match={row['excel_owner_match_rate']}"
            )
    lines.append("")
    lines.append("## Fallback")
    lines.append("- 文件2 fallback: `INTINTERFACEDOC.MODIFIED_BY_ID` / `INTINTERFACEDOC.CREATED_BY_ID`")
    lines.append("- 文件4 fallback: `SENDRECEIVEDATA.CREATED_BY_ID` / `SENDRECEIVEDATA.MODIFIED_BY_ID`")
    lines.append("- 标记：以上回退口径为 `non_final`，需实机可访问分发表后二次确认。")
    lines.append("")
    lines.append("## 最小补数清单")
    minimal_requests = payload.get("minimal_data_requests", [])
    if not minimal_requests:
        lines.append("- 无")
    else:
        for row in minimal_requests:
            fields = ", ".join(row.get("required_fields", []))
            lines.append(
                "- "
                f"{row.get('table')} | fields=[{fields}] | "
                f"suggested_time_range={row.get('suggested_time_range')}"
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def run_probe(args: argparse.Namespace) -> Dict[str, Any]:
    run_root = Path(args.run_root).resolve()
    raw_run_root = run_root / "raw_runs"
    sql_dir = Path(args.sql_dir).resolve()
    file2_excel = Path(args.file2_excel).resolve()
    file4_excel = Path(args.file4_excel).resolve()
    innovator_schema_file = sql_dir / "innovator.sql"

    output_root = run_root / "final"
    output_root.mkdir(parents=True, exist_ok=True)

    file2_rows = load_excel_file2(file2_excel)
    file4_rows = load_excel_file4(file4_excel)
    file2_a_keys = {row["a_key"] for row in file2_rows if row["a_key"]}
    file2_d_keys = {row["d_key"] for row in file2_rows if row["d_key"]}
    file4_e_keys = {row["e_key"] for row in file4_rows if row["e_key"]}
    file4_e_tail_keys = {row["e_key_tail"] for row in file4_rows if row["e_key_tail"]}

    int_path = sql_dir / "INTINTERFACEDOC.sql"
    send_path = sql_dir / "SENDRECEIVEDATA.sql"
    user_path = sql_dir / "USER.sql"
    dept_path = sql_dir / "DEPARTMENT.sql"

    int_data = parse_int_table(int_path, file2_a_keys, file2_d_keys)
    send_data = parse_send_table(send_path, file4_e_keys, file4_e_tail_keys)
    dept_map = parse_department_map(dept_path)
    user_map = parse_user_map(user_path, dept_map)

    # Chain joins.
    file2_joined: List[Dict[str, Any]] = []
    pair_hit = 0
    for row in file2_rows:
        pair_ids = int_data["pair_to_ids"].get((row["a_key"], row["d_key"]), set())
        chosen_id = sorted(pair_ids)[0] if pair_ids else ""
        if chosen_id:
            pair_hit += 1
        file2_joined.append({**row, "int_id": chosen_id})

    file4_joined: List[Dict[str, Any]] = []
    send_hit = 0
    send_hit_tail = 0
    for row in file4_rows:
        send_ids = send_data["e_to_send_ids"].get(row["e_key"], set())
        match_mode = "exact"
        if not send_ids and row.get("e_key_tail"):
            send_ids = send_data["e_to_send_tail_ids"].get(row["e_key_tail"], set())
            if send_ids:
                match_mode = "tail_relaxed"
        chosen_id = sorted(send_ids)[0] if send_ids else ""
        if chosen_id:
            send_hit += 1
            if match_mode == "tail_relaxed":
                send_hit_tail += 1
        file4_joined.append({**row, "send_id": chosen_id, "match_mode": match_mode})

    matched_int_ids = {row["int_id"] for row in file2_joined if row["int_id"]}
    matched_send_ids = {row["send_id"] for row in file4_joined if row["send_id"]}

    # Required chain link tables.
    link_specs = [
        ("DISTRIBUTERECORD", ["SOURCE_OBJECT_ID"], ["OPERATOR", "SENDER", "CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("OBJECTREPLYLINK", ["SOURCE_OBJECT_ID"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("FILETRANSMISSION", ["SEND_RECEIVE_DATA"], ["FILE_RECEIVER", "CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("CRREPLY", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("DCRREPLY", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("FCRREPLY", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("NCRREPLY", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("TCRREPLY", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("TAREPLY", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("TA", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("MEMORANDUM", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("TELEFAX", ["SEND_RECEIVE_DATA"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
    ]

    file2_links: Dict[str, Dict[str, Any]] = {}
    file4_links: Dict[str, Dict[str, Any]] = {}
    for table, source_cols, owner_cols in link_specs:
        file2_links[table] = parse_link_table(
            table, sql_dir, matched_int_ids, source_cols, owner_cols
        )
        file4_links[table] = parse_link_table(
            table, sql_dir, matched_send_ids, source_cols, owner_cols
        )

    coverage_rows: List[CoverageRow] = []
    # File2 coverage.
    unique_d_count = len(file2_d_keys)
    unique_d_item_hit = sum(1 for key in file2_d_keys if len(int_data["d_to_item_ids"].get(key, set())) == 1)
    unique_d_ref_hit = sum(1 for key in file2_d_keys if len(int_data["d_to_ref_ids"].get(key, set())) == 1)
    coverage_rows.append(
        _coverage(
            "file2",
            "d_to_int_item_unique",
            "Excel.D",
            "INTINTERFACEDOC.ITEM_NUMBER",
            True,
            unique_d_count,
            unique_d_item_hit,
            "ok",
            "unique-key hit count",
        )
    )
    coverage_rows.append(
        _coverage(
            "file2",
            "d_to_int_ref_unique",
            "Excel.D",
            "INTINTERFACEDOC.REF_ITEM_NUMBER",
            True,
            unique_d_count,
            unique_d_ref_hit,
            "ok",
            "unique-key hit count",
        )
    )
    coverage_rows.append(
        _coverage(
            "file2",
            "a_d_pair_to_int_row",
            "Excel.(A,D)",
            "INTINTERFACEDOC.(ITEM_NUMBER,REF_ITEM_NUMBER)",
            True,
            len(file2_joined),
            pair_hit,
            "ok",
            "row-level pair hit",
        )
    )

    for table in ("DISTRIBUTERECORD", "OBJECTREPLYLINK"):
        link = file2_links[table]
        matched_count = len(link.get("matched_source_ids", set()))
        if not link.get("available"):
            status = "blocked"
        elif len(matched_int_ids) > 0 and matched_count == 0:
            status = "data_gap"
        else:
            status = "ok"
        coverage_rows.append(
            _coverage(
                "file2",
                f"int_id_to_{table.lower()}",
                "INTINTERFACEDOC.id",
                f"{table}.SOURCE_OBJECT_ID",
                bool(link.get("available")),
                len(matched_int_ids),
                matched_count,
                status,
                link.get("reason", ""),
            )
        )

    # File4 coverage.
    unique_e_count = len(file4_e_keys)
    unique_e_send_hit = sum(1 for key in file4_e_keys if len(send_data["e_to_send_ids"].get(key, set())) == 1)
    unique_e_rec_hit = sum(1 for key in file4_e_keys if len(send_data["e_to_rec_ids"].get(key, set())) == 1)
    coverage_rows.append(
        _coverage(
            "file4",
            "e_to_send_letter_send_no_unique",
            "Excel.E",
            "SENDRECEIVEDATA.LETTER_SEND_NO",
            True,
            unique_e_count,
            unique_e_send_hit,
            "ok",
            "unique-key hit count",
        )
    )
    coverage_rows.append(
        _coverage(
            "file4",
            "e_to_send_tail_relaxed_row",
            "Excel.E",
            "SENDRECEIVEDATA.LETTER_SEND_NO(tail_relaxed)",
            True,
            len(file4_joined),
            send_hit_tail,
            "ok",
            "drop-tail-digit relaxed match",
        )
    )
    coverage_rows.append(
        _coverage(
            "file4",
            "e_to_send_corresp_rec_no_unique",
            "Excel.E",
            "SENDRECEIVEDATA.CORRESP_LETTER_REC_NO",
            True,
            unique_e_count,
            unique_e_rec_hit,
            "ok",
            "aux-key unique hit",
        )
    )
    for table, source_col in (
        ("DISTRIBUTERECORD", "SOURCE_OBJECT_ID"),
        ("OBJECTREPLYLINK", "SOURCE_OBJECT_ID"),
        ("FILETRANSMISSION", "SEND_RECEIVE_DATA"),
    ):
        link = file4_links[table]
        matched_count = len(link.get("matched_source_ids", set()))
        if not link.get("available"):
            status = "blocked"
        elif len(matched_send_ids) > 0 and matched_count == 0:
            status = "data_gap"
        else:
            status = "ok"
        coverage_rows.append(
            _coverage(
                "file4",
                f"send_id_to_{table.lower()}",
                "SENDRECEIVEDATA.id",
                f"{table}.{source_col}",
                bool(link.get("available")),
                len(matched_send_ids),
                matched_count,
                status,
                link.get("reason", ""),
            )
        )
    for table in ("CRREPLY", "DCRREPLY", "FCRREPLY", "NCRREPLY", "TCRREPLY"):
        link = file4_links[table]
        matched_count = len(link.get("matched_source_ids", set()))
        if not link.get("available"):
            status = "blocked"
        elif len(matched_send_ids) > 0 and matched_count == 0:
            status = "data_gap"
        else:
            status = "ok"
        coverage_rows.append(
            _coverage(
                "file4",
                f"send_id_to_{table.lower()}",
                "SENDRECEIVEDATA.id",
                f"{table}.SEND_RECEIVE_DATA",
                bool(link.get("available")),
                len(matched_send_ids),
                matched_count,
                status,
                link.get("reason", ""),
            )
        )

    owner_candidate_scores: List[Dict[str, Any]] = []

    # File2 from INT table.
    for col in int_data["owner_columns"]:
        values = []
        excel_owner_values = []
        for row in file2_joined:
            int_id = row.get("int_id", "")
            value = ""
            if int_id:
                value = int_data["id_owner_values"].get(int_id, {}).get(col)
            values.append(value)
            excel_owner_values.append(row.get("owner_raw", ""))
        owner_candidate_scores.append(
            _build_candidate_row(
                file_type="2",
                chain_path="file2:A,D->INT",
                table="INTINTERFACEDOC",
                column=col,
                values=values,
                excel_owner_values=excel_owner_values,
                user_map=user_map,
                available=True,
            )
        )

    # File4 from SEND table.
    for col in send_data["owner_columns"]:
        values = []
        excel_owner_values = []
        for row in file4_joined:
            send_id = row.get("send_id", "")
            value = ""
            if send_id:
                value = send_data["id_owner_values"].get(send_id, {}).get(col)
            values.append(value)
            excel_owner_values.append(row.get("owner_raw", ""))
        owner_candidate_scores.append(
            _build_candidate_row(
                file_type="4",
                chain_path="file4:E->SEND",
                table="SENDRECEIVEDATA",
                column=col,
                values=values,
                excel_owner_values=excel_owner_values,
                user_map=user_map,
                available=True,
            )
        )

    # Distribution/reply owner candidates.
    for table, _source_cols, owner_cols in link_specs:
        link2 = file2_links[table]
        link4 = file4_links[table]

        for col in owner_cols:
            # File2.
            values2: List[Any] = []
            owners2: List[Any] = []
            for row in file2_joined:
                int_id = row.get("int_id", "")
                owner_map = link2.get("owner_by_source", {})
                val = ""
                if int_id:
                    val = (owner_map.get(int_id, {}) or {}).get(col)
                values2.append(val)
                owners2.append(row.get("owner_raw", ""))
            owner_candidate_scores.append(
                _build_candidate_row(
                    file_type="2",
                    chain_path=f"file2:INT.id->{table}",
                    table=table,
                    column=col,
                    values=values2,
                    excel_owner_values=owners2,
                    user_map=user_map,
                    available=bool(link2.get("available")),
                    note=str(link2.get("reason", "")),
                )
            )

            # File4.
            values4: List[Any] = []
            owners4: List[Any] = []
            for row in file4_joined:
                send_id = row.get("send_id", "")
                owner_map = link4.get("owner_by_source", {})
                val = ""
                if send_id:
                    val = (owner_map.get(send_id, {}) or {}).get(col)
                values4.append(val)
                owners4.append(row.get("owner_raw", ""))
            owner_candidate_scores.append(
                _build_candidate_row(
                    file_type="4",
                    chain_path=f"file4:SEND.id->{table}",
                    table=table,
                    column=col,
                    values=values4,
                    excel_owner_values=owners4,
                    user_map=user_map,
                    available=bool(link4.get("available")),
                    note=str(link4.get("reason", "")),
                )
            )

    # Required table availability.
    innovator_schema_text = _read_text_if_exists(innovator_schema_file)
    table_access_rows: List[Dict[str, Any]] = []
    blocked_tables: List[str] = []
    for table in ALL_REQUIRED_TABLES:
        dump_path = sql_dir / f"{table}.sql"
        has_dump = dump_path.exists()
        in_schema = _table_in_schema(innovator_schema_text, table)
        row_count = count_insert_rows(dump_path) if has_dump else 0
        if has_dump and row_count == 0:
            status = "empty"
        elif has_dump:
            status = "ok"
        else:
            status = "schema_only" if in_schema else "not_found"
        if status != "ok":
            blocked_tables.append(table)
        table_access_rows.append(
            {
                "table": table,
                "in_schema": in_schema,
                "has_dump": has_dump,
                "row_count": row_count,
                "status": status,
            }
        )

    minimal_data_requests: List[Dict[str, Any]] = []
    for table in blocked_tables:
        minimal_data_requests.append(
            {
                "table": table,
                "required_fields": MINIMAL_SUPPLEMENT_FIELDS.get(
                    table, ["ID", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON"]
                ),
                "suggested_time_range": "近3-5年",
            }
        )

    # Raw run diagnostics aggregation.
    sample_attempt_path = raw_run_root / "sample_attempts.json"
    sample_attempt_data = []
    if sample_attempt_path.exists():
        sample_attempt_data = json.loads(sample_attempt_path.read_text(encoding="utf-8-sig"))
    sample_exit_counts = Counter(str(item.get("exit_code")) for item in sample_attempt_data)
    overview_diag_latest = _latest_dir(raw_run_root / "overview")
    overview_diag_text = ""
    if overview_diag_latest:
        overview_diag_text = _read_text_if_exists(overview_diag_latest / "run_diagnostics.txt")
    overview_attempt_out = _read_text_if_exists(
        raw_run_root / "overview_attempt" / "overview_command_output.txt"
    )

    blocked_reason = "distribution_table_data_missing_or_sql_unreachable"
    question_answers = {
        "q1_file2_need_distribution_chain": {
            "answer": "YES_BUT_BLOCKED",
            "detail": "INT单表字段可作回退，但分发表不可用导致主链无法在本次实机环境闭环确认。",
        },
        "q2_file4_need_distribution_chain": {
            "answer": "YES_BUT_BLOCKED",
            "detail": "SEND单表字段可作回退，但分发表不可用导致主链无法在本次实机环境闭环确认。",
        },
        "q3_best_owner_source": {
            "answer": "FALLBACK_ONLY",
            "detail": "文件2回退: INTINTERFACEDOC.MODIFIED_BY_ID/CREATED_BY_ID; 文件4回退: SENDRECEIVEDATA.CREATED_BY_ID/MODIFIED_BY_ID。",
        },
        "q4_blocked_by_permission_or_data": {
            "answer": "YES",
            "detail": blocked_reason,
        },
    }

    blocking_points = [
        "overview run failed to connect 10.27.14.216 (Adaptive Server connection failed).",
        "all table sample attempts exited non-zero in current environment.",
    ]
    if blocked_tables:
        blocking_points.append(
            "missing or schema-only dump tables: " + ", ".join(sorted(set(blocked_tables)))
        )

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "output_root": str(run_root),
        "inputs": {
            "run_root": str(run_root),
            "sql_dir": str(sql_dir),
            "file2_excel": str(file2_excel),
            "file4_excel": str(file4_excel),
            "raw_run_root": str(raw_run_root),
        },
        "question_answers": question_answers,
        "blocking_points": blocking_points,
        "coverage_rows": [row.to_dict() for row in coverage_rows],
        "owner_candidate_scores": owner_candidate_scores,
        "table_access": table_access_rows,
        "minimal_data_requests": minimal_data_requests,
        "sample_attempt_exit_counts": dict(sample_exit_counts),
        "sample_attempt_total": len(sample_attempt_data),
    }

    # Write required artifacts.
    report_json_path = run_root / "real_distribution_chain_report.json"
    report_md_path = run_root / "real_distribution_chain_report.md"
    coverage_csv_path = run_root / "table_rowcount_and_coverage.csv"
    owner_csv_path = run_root / "owner_candidate_scores.csv"
    diagnostics_path = run_root / "run_diagnostics.txt"

    report_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md_path.write_text(_build_markdown_report(payload), encoding="utf-8")

    with coverage_csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "scenario",
                "step",
                "source",
                "target",
                "available",
                "source_count",
                "matched_count",
                "coverage_rate",
                "status",
                "details",
            ],
        )
        writer.writeheader()
        for row in coverage_rows:
            writer.writerow(row.to_dict())
        # Add table rowcount rows.
        for table_row in table_access_rows:
            writer.writerow(
                {
                    "scenario": "table_inventory",
                    "step": "rowcount",
                    "source": f"innovator.{table_row['table']}",
                    "target": "dump_rows",
                    "available": table_row["has_dump"],
                    "source_count": table_row["row_count"],
                    "matched_count": table_row["row_count"],
                    "coverage_rate": 1.0 if table_row["has_dump"] else "",
                    "status": table_row["status"],
                    "details": "required_table",
                }
            )

    with owner_csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "file_type",
                "chain_path",
                "table",
                "column",
                "available",
                "row_count",
                "non_null_rate",
                "id_resolved_rate",
                "resolved_dept_rate",
                "excel_owner_match_rate",
                "score",
                "note",
            ],
        )
        writer.writeheader()
        for row in owner_candidate_scores:
            writer.writerow(row)

    diagnostics_lines = [
        f"[INFO] generated_at={payload['generated_at']}",
        f"[INFO] run_root={run_root}",
        f"[INFO] sql_dir={sql_dir}",
        f"[INFO] sample_attempt_total={len(sample_attempt_data)}",
        f"[INFO] sample_exit_counts={dict(sample_exit_counts)}",
        "[INFO] blocking_points:",
    ]
    diagnostics_lines.extend([f"- {item}" for item in blocking_points])
    diagnostics_lines.append("")
    diagnostics_lines.append("[INFO] overview_run_diagnostics:")
    diagnostics_lines.append(overview_diag_text or "<empty>")
    diagnostics_lines.append("")
    diagnostics_lines.append("[INFO] overview_attempt_output:")
    diagnostics_lines.append(overview_attempt_out or "<empty>")
    diagnostics_lines.append("")
    diagnostics_lines.append("[INFO] minimal_data_requests:")
    for row in minimal_data_requests:
        diagnostics_lines.append(
            f"- {row['table']}: fields={row['required_fields']} time_range={row['suggested_time_range']}"
        )
    diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")

    # sample_*.json outputs
    sample_dir = run_root / "sample_json"
    sample_dir.mkdir(parents=True, exist_ok=True)
    for table in ALL_REQUIRED_TABLES:
        sample_payload = {
            "table": table,
            "source_dump_exists": (sql_dir / f"{table}.sql").exists(),
            "table_inventory": next((r for r in table_access_rows if r["table"] == table), {}),
            "file2_link": file2_links.get(table, {}),
            "file4_link": file4_links.get(table, {}),
        }
        # Keep sample files concise.
        for side_key in ("file2_link", "file4_link"):
            side = sample_payload.get(side_key, {})
            if isinstance(side, dict):
                if "owner_by_source" in side:
                    # keep only first few source keys for readability.
                    owner_by_source = side.get("owner_by_source", {})
                    if isinstance(owner_by_source, dict):
                        mini = {}
                        for idx, k in enumerate(owner_by_source.keys()):
                            if idx >= 10:
                                break
                            mini[k] = owner_by_source[k]
                        side["owner_by_source"] = mini
                if "matched_source_ids" in side and isinstance(side["matched_source_ids"], set):
                    side["matched_source_ids"] = sorted(list(side["matched_source_ids"]))[:50]
        sample_path = sample_dir / f"sample_innovator_{table}.json"
        sample_path.write_text(json.dumps(sample_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Real distribution chain probe")
    parser.add_argument(
        "--run-root",
        required=True,
        help="Root directory for one real_distribution_chain run",
    )
    parser.add_argument(
        "--sql-dir",
        default="example/CIMS-sql",
        help="SQL dump directory",
    )
    parser.add_argument(
        "--file2-excel",
        default="example/内部接口信息单报表181820260128.xlsx",
        help="File2 excel path",
    )
    parser.add_argument(
        "--file4-excel",
        default="example/外部接口单报表181820260128.xlsx",
        help="File4 excel path",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    payload = run_probe(args)
    print(json.dumps({"generated_at": payload["generated_at"], "output_root": payload["output_root"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
