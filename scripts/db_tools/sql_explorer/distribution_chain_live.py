"""Live SQL distribution-chain probe for file2/file4."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .identity_resolver import normalize_hex32, resolve_owner_value
from .roster import normalize_owner_tokens, validate_owner_values
from .sampling import sample_table

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
REPLY_TABLES = ["CRREPLY", "DCRREPLY", "FCRREPLY", "NCRREPLY", "TCRREPLY", "TAREPLY"]

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

NON_ALNUM_RE = re.compile(r"[^A-Z0-9]+")
TAIL_DIGITS_RE = re.compile(r"\d+$")
INVALID_TEXT = {"", "nan", "none", "null", "nat"}


def _json_default(value: Any) -> str:
    """Safe JSON fallback for datetime/bytes/other non-serializable values."""

    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (bytes, bytearray, memoryview)):
        data = bytes(value)
        preview = data[:24].hex()
        return f"<BINARY:{len(data)}:{preview}>"
    if hasattr(value, "isoformat"):
        try:
            return str(value.isoformat())
        except Exception:
            pass
    return str(value)


@dataclass
class CoverageRow:
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
    key = _norm_key(value)
    if not key:
        return ""
    return TAIL_DIGITS_RE.sub("", key)


def _is_current_flag(value: Any) -> bool:
    text = str(value or "").strip().upper()
    return text in {"", "1", "Y", "TRUE", "T"}


def _excel_col_index(col: str) -> int:
    col = col.strip().upper()
    idx = 0
    for ch in col:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _safe_get(row: Sequence[Any], idx: int) -> Any:
    if idx < 0 or idx >= len(row):
        return None
    return row[idx]


def _find_table_entry(schema_snapshot: Dict[str, Any], schema_name: str, table_name: str) -> Optional[Dict[str, Any]]:
    for entry in schema_snapshot.get("tables", []) or []:
        if str(entry.get("schema", "")).lower() == schema_name.lower() and str(
            entry.get("table", "")
        ).lower() == table_name.lower():
            return entry
    return None


def _sample_table_with_fallback(
    conn: Any,
    table_ref: str,
    top_n: int,
    has_is_current: bool,
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    if has_is_current:
        try:
            sampled = sample_table(conn, table_ref, top_n=top_n, where_clause="IS_CURRENT='1'")
            return sampled, "ok", ""
        except Exception as exc:
            # Fallback without where if where query fails on this table.
            try:
                sampled = sample_table(conn, table_ref, top_n=top_n, where_clause=None)
                return sampled, "ok_fallback_no_where", f"{exc}"
            except Exception as exc2:
                return None, "error", f"{exc2}"
    try:
        sampled = sample_table(conn, table_ref, top_n=top_n, where_clause=None)
        return sampled, "ok", ""
    except Exception as exc:
        return None, "error", f"{exc}"


def _value_ci(row: Dict[str, Any], candidates: Sequence[str]) -> Any:
    if not row:
        return None
    lower_map = {str(k).lower(): v for k, v in row.items()}
    for name in candidates:
        value = lower_map.get(name.lower())
        if value is not None:
            return value
    return None


def _is_pymssql_connection(conn: Any) -> bool:
    text = f"{getattr(conn.__class__, '__module__', '')}.{getattr(conn.__class__, '__name__', '')}".lower()
    return ("pymssql" in text) or ("_mssql" in text)


def _fetch_records_with_params(conn: Any, sql_qmark: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    if _is_pymssql_connection(conn):
        cursor.execute(sql_qmark.replace("?", "%s"), tuple(params))
    else:
        cursor.execute(sql_qmark, tuple(params))

    rows = cursor.fetchall() or []
    columns = [item[0] for item in cursor.description] if cursor.description else []
    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append({columns[idx]: row[idx] for idx in range(len(columns))})
    return records


def _chunked(values: Sequence[str], size: int) -> List[List[str]]:
    if size <= 0:
        return [list(values)]
    chunks: List[List[str]] = []
    start = 0
    while start < len(values):
        chunks.append(list(values[start : start + size]))
        start += size
    return chunks


def _is_connection_interruption(exc: Exception) -> bool:
    text = str(exc or "").lower()
    markers = (
        "not connected to any ms sql server",
        "dbprocess is dead",
        "adaptive server connection timed out",
        "connection timed out",
        "communication link failure",
        "connection is closed",
        "08s01",
    )
    return any(marker in text for marker in markers)


def _sql_norm_expr(col_name: str) -> str:
    expr = f"UPPER(COALESCE([{col_name}], ''))"
    for token in (" ", "-", ".", "/", "\\", "_", "(", ")", "[", "]"):
        expr = f"REPLACE({expr}, '{token}', '')"
    return expr


def _record_id_key(record: Dict[str, Any], index: int) -> str:
    row_id = normalize_hex32(_value_ci(record, ["ID", "id"]))
    if row_id:
        return row_id
    return f"row_{index}"


def _merge_unique_records(*record_groups: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    offset = 0
    for group in record_groups:
        for idx, record in enumerate(group):
            key = _record_id_key(record, offset + idx)
            if key not in merged:
                merged[key] = record
        offset += len(group)
    return list(merged.values())


def _fetch_table_by_norm_keys(
    conn: Any,
    *,
    schema_name: str,
    table_name: str,
    key_columns: Sequence[str],
    norm_keys: Set[str],
    has_is_current: bool,
    batch_size: int = 80,
) -> List[Dict[str, Any]]:
    if not norm_keys:
        return []
    keys = sorted({str(k or "").strip().upper() for k in norm_keys if str(k or "").strip()})
    if not keys:
        return []

    records: List[Dict[str, Any]] = []
    for chunk in _chunked(keys, batch_size):
        placeholders = ",".join("?" for _ in chunk)
        current_filter = (
            "([IS_CURRENT]='1' OR [IS_CURRENT]=1 OR [IS_CURRENT] IS NULL) AND "
            if has_is_current
            else ""
        )
        key_conds = [f"{_sql_norm_expr(col)} IN ({placeholders})" for col in key_columns]
        sql = (
            f"SELECT * FROM [{schema_name}].[{table_name}] "
            f"WHERE {current_filter}(" + " OR ".join(key_conds) + ")"
        )
        params: List[Any] = []
        for _ in key_columns:
            params.extend(chunk)
        records.extend(_fetch_records_with_params(conn, sql, params))
    return _merge_unique_records(records)


def _fetch_table_by_source_ids(
    conn: Any,
    *,
    schema_name: str,
    table_name: str,
    source_columns: Sequence[str],
    source_ids: Set[str],
    has_is_current: bool,
    batch_size: int = 200,
) -> List[Dict[str, Any]]:
    if not source_ids:
        return []
    ids = sorted({normalize_hex32(x) for x in source_ids if normalize_hex32(x)})
    if not ids:
        return []

    records: List[Dict[str, Any]] = []
    for chunk in _chunked(ids, batch_size):
        placeholders = ",".join("?" for _ in chunk)
        current_filter = (
            "([IS_CURRENT]='1' OR [IS_CURRENT]=1 OR [IS_CURRENT] IS NULL) AND "
            if has_is_current
            else ""
        )
        id_conds = [f"[{col}] IN ({placeholders})" for col in source_columns]
        sql = (
            f"SELECT * FROM [{schema_name}].[{table_name}] "
            f"WHERE {current_filter}(" + " OR ".join(id_conds) + ")"
        )
        params: List[Any] = []
        for _ in source_columns:
            params.extend(chunk)
        records.extend(_fetch_records_with_params(conn, sql, params))
    return _merge_unique_records(records)


def _fetch_table_by_exact_keys(
    conn: Any,
    *,
    schema_name: str,
    table_name: str,
    key_columns: Sequence[str],
    raw_keys: Set[str],
    has_is_current: bool,
    batch_size: int = 150,
) -> List[Dict[str, Any]]:
    if not raw_keys:
        return []
    keys = sorted({str(k or "").strip() for k in raw_keys if str(k or "").strip()})
    if not keys:
        return []

    records: List[Dict[str, Any]] = []
    for chunk in _chunked(keys, batch_size):
        placeholders = ",".join("?" for _ in chunk)
        current_filter = (
            "([IS_CURRENT]='1' OR [IS_CURRENT]=1 OR [IS_CURRENT] IS NULL) AND "
            if has_is_current
            else ""
        )
        key_conds = [f"[{col}] IN ({placeholders})" for col in key_columns]
        sql = (
            f"SELECT * FROM [{schema_name}].[{table_name}] "
            f"WHERE {current_filter}(" + " OR ".join(key_conds) + ")"
        )
        params: List[Any] = []
        for _ in key_columns:
            params.extend(chunk)
        records.extend(_fetch_records_with_params(conn, sql, params))
    return _merge_unique_records(records)


def load_excel_file2(path: Path) -> List[Dict[str, Any]]:
    import pandas as pd

    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    col_a = _excel_col_index("A")
    col_d = _excel_col_index("D")
    col_am = _excel_col_index("AM")

    rows: List[Dict[str, Any]] = []
    for idx in range(len(df)):
        line = df.iloc[idx].tolist()
        a_raw = _safe_get(line, col_a)
        d_raw = _safe_get(line, col_d)
        owner_raw = _safe_get(line, col_am)
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
    import pandas as pd

    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    col_e = _excel_col_index("E")
    col_ah = _excel_col_index("AH")

    rows: List[Dict[str, Any]] = []
    for idx in range(len(df)):
        line = df.iloc[idx].tolist()
        e_raw = _safe_get(line, col_e)
        owner_raw = _safe_get(line, col_ah)
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


def _owner_tokens_with_id_resolution(value: Any, user_map: Dict[str, Dict[str, Any]]) -> List[str]:
    tokens = normalize_owner_tokens(value)
    resolved = resolve_owner_value(value, user_map)
    for name in resolved.get("resolved_names", []):
        name = str(name or "").strip()
        if name and name not in tokens:
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


def _semantic_tag(table: str, column: str) -> str:
    col = str(column).upper()
    tbl = str(table).upper()
    if "CC" in col or "DISTRIBUTE" in col:
        return "抄送"
    if col in {"CREATED_BY_ID", "MODIFIED_BY_ID"}:
        return "回退"
    if col in {"OPERATOR", "SENDER", "FILE_RECEIVER", "RELEVANT_PERSON", "RESP_SHEZONG"}:
        return "主责"
    if tbl.endswith("REPLY") and col in {"CREATED_BY_ID", "MODIFIED_BY_ID"}:
        return "主责"
    return "主责"


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
            "semantic_tag": _semantic_tag(table, column),
            "available": False,
            "row_count": len(values),
            "non_null_rate": "",
            "id_resolved_rate": "",
            "resolved_dept_rate": "",
            "excel_owner_match_rate": "",
            "score": "",
            "note": note,
        }

    non_empty = sum(1 for value in values if _clean_text(value))
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
        "semantic_tag": _semantic_tag(table, column),
        "available": True,
        "row_count": len(values),
        "non_null_rate": round(non_null_rate, 6),
        "id_resolved_rate": round(id_rate, 6),
        "resolved_dept_rate": round(dept_rate, 6),
        "excel_owner_match_rate": round(excel_match, 6),
        "score": round(score, 6),
        "note": note,
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


def _build_int_data(records: List[Dict[str, Any]], needed_item_keys: Set[str], needed_ref_keys: Set[str]) -> Dict[str, Any]:
    owner_cols = ["CREATED_BY_ID", "MODIFIED_BY_ID", "RESP_SHEZONG", "RELEVANT_PERSON", "DEPART_USER"]
    d_to_item_ids: Dict[str, Set[str]] = {}
    d_to_ref_ids: Dict[str, Set[str]] = {}
    pair_to_ids: Dict[Tuple[str, str], Set[str]] = {}
    id_owner_values: Dict[str, Dict[str, Any]] = {}
    number_keys: Set[str] = set()

    for row in records:
        if _value_ci(row, ["IS_CURRENT"]) is not None and not _is_current_flag(
            _value_ci(row, ["IS_CURRENT"])
        ):
            continue

        item_key = _norm_key(_value_ci(row, ["ITEM_NUMBER"]))
        ref_key = _norm_key(_value_ci(row, ["REF_ITEM_NUMBER"]))
        if not item_key and not ref_key:
            continue
        if (item_key not in needed_item_keys and item_key not in needed_ref_keys) and (
            ref_key not in needed_ref_keys
        ):
            continue

        obj_id = normalize_hex32(_value_ci(row, ["ID", "id"]))
        if not obj_id:
            continue

        if item_key in needed_item_keys:
            d_to_item_ids.setdefault(item_key, set()).add(obj_id)
        if ref_key in needed_ref_keys:
            d_to_ref_ids.setdefault(ref_key, set()).add(obj_id)
        if item_key in needed_item_keys and ref_key in needed_ref_keys:
            pair_to_ids.setdefault((item_key, ref_key), set()).add(obj_id)
        if item_key:
            number_keys.add(item_key)
        if ref_key:
            number_keys.add(ref_key)

        owner_payload = id_owner_values.setdefault(obj_id, {})
        for col in owner_cols:
            value = _value_ci(row, [col])
            if _clean_text(value):
                owner_payload[col] = value

    return {
        "d_to_item_ids": d_to_item_ids,
        "d_to_ref_ids": d_to_ref_ids,
        "pair_to_ids": pair_to_ids,
        "id_owner_values": id_owner_values,
        "owner_columns": [c for c in owner_cols if any(_clean_text(_value_ci(r, [c])) for r in records)],
        "number_keys": number_keys,
    }


def _build_send_data(
    records: List[Dict[str, Any]],
    needed_e_keys: Set[str],
    needed_e_tail_keys: Set[str],
) -> Dict[str, Any]:
    owner_cols = ["CREATED_BY_ID", "MODIFIED_BY_ID"]
    e_to_send_ids: Dict[str, Set[str]] = {}
    e_to_rec_ids: Dict[str, Set[str]] = {}
    e_to_send_tail_ids: Dict[str, Set[str]] = {}
    e_to_rec_tail_ids: Dict[str, Set[str]] = {}
    id_owner_values: Dict[str, Dict[str, Any]] = {}
    number_keys: Set[str] = set()

    for row in records:
        if _value_ci(row, ["IS_CURRENT"]) is not None and not _is_current_flag(
            _value_ci(row, ["IS_CURRENT"])
        ):
            continue

        send_val = _value_ci(row, ["LETTER_SEND_NO"])
        rec_val = _value_ci(row, ["CORRESP_LETTER_REC_NO"])
        send_key = _norm_key(send_val)
        rec_key = _norm_key(rec_val)
        send_tail = _norm_drop_tail_digits(send_val)
        rec_tail = _norm_drop_tail_digits(rec_val)
        if (
            send_key not in needed_e_keys
            and rec_key not in needed_e_keys
            and send_tail not in needed_e_tail_keys
            and rec_tail not in needed_e_tail_keys
        ):
            continue

        send_id = normalize_hex32(_value_ci(row, ["ID", "id"]))
        if not send_id:
            continue

        if send_key in needed_e_keys:
            e_to_send_ids.setdefault(send_key, set()).add(send_id)
            number_keys.add(send_key)
        if rec_key in needed_e_keys:
            e_to_rec_ids.setdefault(rec_key, set()).add(send_id)
            number_keys.add(rec_key)
        if send_tail in needed_e_tail_keys:
            e_to_send_tail_ids.setdefault(send_tail, set()).add(send_id)
        if rec_tail in needed_e_tail_keys:
            e_to_rec_tail_ids.setdefault(rec_tail, set()).add(send_id)

        owner_payload = id_owner_values.setdefault(send_id, {})
        for col in owner_cols:
            value = _value_ci(row, [col])
            if _clean_text(value):
                owner_payload[col] = value

    return {
        "e_to_send_ids": e_to_send_ids,
        "e_to_rec_ids": e_to_rec_ids,
        "e_to_send_tail_ids": e_to_send_tail_ids,
        "e_to_rec_tail_ids": e_to_rec_tail_ids,
        "id_owner_values": id_owner_values,
        "owner_columns": [c for c in owner_cols if any(_clean_text(_value_ci(r, [c])) for r in records)],
        "number_keys": number_keys,
    }


def _build_link_data(
    records: List[Dict[str, Any]],
    source_ids: Set[str],
    source_candidates: Sequence[str],
    owner_candidates: Sequence[str],
) -> Dict[str, Any]:
    if not records:
        return {
            "available": False,
            "reason": "empty_table",
            "matched_source_ids": set(),
            "owner_by_source": {},
            "owner_columns": [],
            "row_count": 0,
            "sample_rows": [],
        }

    owner_by_source: Dict[str, Dict[str, Any]] = {}
    matched_source_ids: Set[str] = set()
    sample_rows: List[Dict[str, Any]] = []
    row_count = 0
    source_col_name = ""

    for row in records:
        row_count += 1
        if _value_ci(row, ["IS_CURRENT"]) is not None and not _is_current_flag(
            _value_ci(row, ["IS_CURRENT"])
        ):
            continue
        src_value = _value_ci(row, source_candidates)
        if src_value is not None and not source_col_name:
            source_col_name = next((c for c in source_candidates if _value_ci(row, [c]) is not None), "")
        src_id = normalize_hex32(src_value)
        if not src_id or src_id not in source_ids:
            continue
        matched_source_ids.add(src_id)
        payload = owner_by_source.setdefault(src_id, {})
        for col in owner_candidates:
            value = _value_ci(row, [col])
            if _clean_text(value) and not _clean_text(payload.get(col)):
                payload[col] = value
        if len(sample_rows) < 30:
            sample_row = {"source_id": src_id}
            for col in owner_candidates:
                sample_row[col] = _value_ci(row, [col])
            sample_rows.append(sample_row)

    available = row_count > 0
    reason = "" if available else "empty_table"
    present_owner_cols = [c for c in owner_candidates if any(_clean_text(_value_ci(r, [c])) for r in records)]
    return {
        "available": available,
        "reason": reason,
        "matched_source_ids": matched_source_ids,
        "owner_by_source": owner_by_source,
        "owner_columns": present_owner_cols,
        "row_count": row_count,
        "source_column": source_col_name or "",
        "sample_rows": sample_rows,
    }


def _pick_owner_value_from_ids(
    source_ids: Sequence[str],
    owner_map: Dict[str, Dict[str, Any]],
    column: str,
) -> Any:
    for source_id in source_ids:
        value = (owner_map.get(source_id, {}) or {}).get(column)
        if _clean_text(value):
            return value
    return ""


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
    health = payload.get("targeted_query_health") or {}
    if health:
        lines.append("## 定向查询健康度")
        lines.append(
            "- "
            f"attempted={health.get('attempted', 0)}, "
            f"retried={health.get('retried', 0)}, "
            f"connection_interruptions={health.get('connection_interruptions', 0)}, "
            f"failed={health.get('failed', 0)}"
        )
        failed_steps = health.get("failed_steps") or []
        if failed_steps:
            lines.append("- 失败步骤:")
            for item in failed_steps[:8]:
                lines.append(f"  - {item}")
        lines.append("")
    lines.append("## Coverage Highlights")
    for row in payload.get("coverage_rows", [])[:16]:
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
                f"excel_match={row['excel_owner_match_rate']} tag={row.get('semantic_tag', '')}"
            )
    lines.append("")
    lines.append("## Fallback")
    lines.append("- 文件2 fallback: `INTINTERFACEDOC.MODIFIED_BY_ID` / `INTINTERFACEDOC.CREATED_BY_ID`")
    lines.append("- 文件4 fallback: `SENDRECEIVEDATA.CREATED_BY_ID` / `SENDRECEIVEDATA.MODIFIED_BY_ID`")
    lines.append("- 标记：以上回退口径为 `non_final`，需实机可访问分发表后二次确认。")
    lines.append("")
    lines.append("## 最小补数清单")
    for row in payload.get("minimal_data_requests", []):
        fields = ", ".join(row.get("required_fields", []))
        lines.append(
            f"- {row['table']} | fields=[{fields}] | suggested_time_range={row['suggested_time_range']}"
        )
    return "\n".join(lines) + "\n"


def execute_distribution_chain(
    *,
    conn: Any,
    schema_snapshot: Dict[str, Any],
    run_root: Path,
    schema_name: str,
    sample_top_n: int,
    file2_excel: Path,
    file4_excel: Path,
    user_id_map: Dict[str, Dict[str, Any]],
    diag: Callable[[str], None],
    connection_factory: Optional[Callable[[], Any]] = None,
) -> Dict[str, Any]:
    run_root.mkdir(parents=True, exist_ok=True)
    probe_dir = run_root / "distribution_probe"
    probe_dir.mkdir(parents=True, exist_ok=True)

    file2_rows = load_excel_file2(file2_excel)
    file4_rows = load_excel_file4(file4_excel)
    file2_a_keys = {row["a_key"] for row in file2_rows if row["a_key"]}
    file2_d_keys = {row["d_key"] for row in file2_rows if row["d_key"]}
    file2_raw_keys = {
        str(v).strip()
        for row in file2_rows
        for v in (row.get("a_raw", ""), row.get("d_raw", ""))
        if str(v).strip()
    }
    file4_e_keys = {row["e_key"] for row in file4_rows if row["e_key"]}
    file4_e_tail_keys = {row["e_key_tail"] for row in file4_rows if row["e_key_tail"]}
    file4_raw_keys = {str(row.get("e_raw", "")).strip() for row in file4_rows if str(row.get("e_raw", "")).strip()}

    sampled_map: Dict[str, Dict[str, Any]] = {}
    table_access_rows: List[Dict[str, Any]] = []
    targeted_query_health: Dict[str, Any] = {
        "attempted": 0,
        "retried": 0,
        "connection_interruptions": 0,
        "failed": 0,
        "failed_steps": [],
    }

    def _run_targeted_query(step_name: str, runner: Callable[[Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        targeted_query_health["attempted"] += 1
        try:
            return runner(conn)
        except Exception as exc:
            if connection_factory and _is_connection_interruption(exc):
                targeted_query_health["connection_interruptions"] += 1
                diag(f"[WARN] {step_name} 查询连接中断，准备重连重试: {exc}")
                retry_conn = None
                try:
                    retry_conn = connection_factory()
                    targeted_query_health["retried"] += 1
                    result = runner(retry_conn)
                    diag(f"[INFO] {step_name} 重连重试成功。")
                    return result
                except Exception as retry_exc:
                    targeted_query_health["failed"] += 1
                    targeted_query_health["failed_steps"].append(f"{step_name}: {retry_exc}")
                    diag(f"[WARN] {step_name} 重连重试失败，回退采样结果: {retry_exc}")
                    return []
                finally:
                    if retry_conn is not None:
                        try:
                            retry_conn.close()
                        except Exception:
                            pass

            targeted_query_health["failed"] += 1
            targeted_query_health["failed_steps"].append(f"{step_name}: {exc}")
            diag(f"[WARN] {step_name} 定向查询失败，回退采样结果: {exc}")
            return []

    diag("[PROGRESS] 分发链深采样开始 ...")
    for table in ALL_REQUIRED_TABLES:
        table_ref = f"{schema_name}.{table}"
        entry = _find_table_entry(schema_snapshot, schema_name=schema_name, table_name=table)
        if entry is None:
            sampled_map[table] = {"available": False, "status": "missing_table", "records": [], "error": ""}
            table_access_rows.append(
                {
                    "table": table,
                    "in_schema": False,
                    "has_sample": False,
                    "row_count": 0,
                    "status": "missing_table",
                }
            )
            diag(f"[WARN] 关键表缺失: {table_ref}")
            continue

        cols = {str(col.get("name", "")).upper() for col in (entry.get("columns", []) or [])}
        has_is_current = "IS_CURRENT" in cols
        sampled, sample_status, sample_error = _sample_table_with_fallback(
            conn=conn,
            table_ref=table_ref,
            top_n=sample_top_n,
            has_is_current=has_is_current,
        )
        records: List[Dict[str, Any]] = []
        row_count = 0
        if sampled:
            records = list(sampled.get("records", []) or [])
            row_count = int(sampled.get("row_count_sampled", len(records)))

        if sample_status == "error":
            status = "error"
        elif not records:
            status = "empty_table"
        else:
            status = "ok"

        sampled_map[table] = {
            "available": status == "ok",
            "status": status,
            "records": records,
            "columns": list(sampled.get("columns", []) if sampled else []),
            "error": sample_error,
            "sample_status": sample_status,
            "row_count_sampled": row_count,
        }
        table_access_rows.append(
            {
                "table": table,
                "in_schema": True,
                "has_sample": bool(sampled),
                "row_count": row_count,
                "status": status,
            }
        )

        sample_root_file = run_root / f"sample_{schema_name}_{table}.json"
        sample_probe_file = probe_dir / f"{schema_name}_{table}" / "sample_result.json"
        sample_probe_file.parent.mkdir(parents=True, exist_ok=True)
        sample_payload = sampled or {"table_ref": table_ref, "records": [], "columns": []}
        sample_root_file.write_text(
            json.dumps(sample_payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )
        sample_probe_file.write_text(
            json.dumps(sample_payload, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )

        msg = f"[INFO] 采样 {table_ref}: status={status}, rows={row_count}"
        if sample_error:
            msg += f", error={sample_error}"
        diag(msg)

    int_sample_records = sampled_map.get("INTINTERFACEDOC", {}).get("records", []) or []
    send_sample_records = sampled_map.get("SENDRECEIVEDATA", {}).get("records", []) or []

    int_target_records: List[Dict[str, Any]] = []
    send_target_records: List[Dict[str, Any]] = []

    int_entry = _find_table_entry(schema_snapshot, schema_name=schema_name, table_name="INTINTERFACEDOC")
    send_entry = _find_table_entry(schema_snapshot, schema_name=schema_name, table_name="SENDRECEIVEDATA")
    int_has_is_current = bool(
        int_entry and ("IS_CURRENT" in {str(col.get("name", "")).upper() for col in (int_entry.get("columns", []) or [])})
    )
    send_has_is_current = bool(
        send_entry and ("IS_CURRENT" in {str(col.get("name", "")).upper() for col in (send_entry.get("columns", []) or [])})
    )

    int_target_exact = _run_targeted_query(
        f"定向查询 {schema_name}.INTINTERFACEDOC(精确键)",
        lambda c: _fetch_table_by_exact_keys(
            c,
            schema_name=schema_name,
            table_name="INTINTERFACEDOC",
            key_columns=["ITEM_NUMBER", "REF_ITEM_NUMBER"],
            raw_keys=file2_raw_keys,
            has_is_current=int_has_is_current,
        ),
    )
    int_target_records = list(int_target_exact)
    # 归一化匹配可补齐编码格式差异；大键集会显著放大 SQL 负载，需限流。
    if len(file2_a_keys | file2_d_keys) <= 8000:
        int_target_norm = _run_targeted_query(
            f"定向查询 {schema_name}.INTINTERFACEDOC(归一化键)",
            lambda c: _fetch_table_by_norm_keys(
                c,
                schema_name=schema_name,
                table_name="INTINTERFACEDOC",
                key_columns=["ITEM_NUMBER", "REF_ITEM_NUMBER"],
                norm_keys=(file2_a_keys | file2_d_keys),
                has_is_current=int_has_is_current,
            ),
        )
        int_target_records = _merge_unique_records(int_target_records, int_target_norm)
    else:
        diag("[INFO] INTINTERFACEDOC 归一化键规模过大，跳过归一化定向查询以降低超时风险。")
    diag(f"[INFO] 定向查询 INTINTERFACEDOC 命中行: {len(int_target_records)}")

    send_target_exact = _run_targeted_query(
        f"定向查询 {schema_name}.SENDRECEIVEDATA(精确键)",
        lambda c: _fetch_table_by_exact_keys(
            c,
            schema_name=schema_name,
            table_name="SENDRECEIVEDATA",
            key_columns=["LETTER_SEND_NO", "CORRESP_LETTER_REC_NO"],
            raw_keys=file4_raw_keys,
            has_is_current=send_has_is_current,
        ),
    )
    send_target_records = list(send_target_exact)
    if len(file4_e_keys) <= 8000:
        send_target_norm = _run_targeted_query(
            f"定向查询 {schema_name}.SENDRECEIVEDATA(归一化键)",
            lambda c: _fetch_table_by_norm_keys(
                c,
                schema_name=schema_name,
                table_name="SENDRECEIVEDATA",
                key_columns=["LETTER_SEND_NO", "CORRESP_LETTER_REC_NO"],
                norm_keys=file4_e_keys,
                has_is_current=send_has_is_current,
            ),
        )
        send_target_records = _merge_unique_records(send_target_records, send_target_norm)
    else:
        diag("[INFO] SENDRECEIVEDATA 归一化键规模过大，跳过归一化定向查询以降低超时风险。")
    diag(f"[INFO] 定向查询 SENDRECEIVEDATA 命中行: {len(send_target_records)}")

    int_records_for_chain = _merge_unique_records(int_target_records, int_sample_records)
    send_records_for_chain = _merge_unique_records(send_target_records, send_sample_records)

    int_data = _build_int_data(
        int_records_for_chain,
        file2_a_keys,
        file2_d_keys,
    )
    send_data = _build_send_data(
        send_records_for_chain,
        file4_e_keys,
        file4_e_tail_keys,
    )

    file2_joined: List[Dict[str, Any]] = []
    pair_hit = 0
    for row in file2_rows:
        pair_ids = set(int_data["pair_to_ids"].get((row["a_key"], row["d_key"]), set()))
        if not pair_ids and row["d_key"]:
            pair_ids |= set(int_data["d_to_ref_ids"].get(row["d_key"], set()))
            pair_ids |= set(int_data["d_to_item_ids"].get(row["d_key"], set()))
        int_ids = sorted(pair_ids)
        chosen_id = int_ids[0] if int_ids else ""
        if int_ids:
            pair_hit += 1
        file2_joined.append({**row, "int_id": chosen_id, "int_ids": int_ids})

    file4_joined: List[Dict[str, Any]] = []
    send_hit = 0
    send_hit_tail = 0
    for row in file4_rows:
        send_ids = set(send_data["e_to_send_ids"].get(row["e_key"], set()))
        match_mode = "exact"
        if not send_ids:
            send_ids = set(send_data["e_to_rec_ids"].get(row["e_key"], set()))
            if send_ids:
                match_mode = "rec_exact"
        if not send_ids and row.get("e_key_tail"):
            send_ids = set(send_data["e_to_send_tail_ids"].get(row["e_key_tail"], set()))
            if not send_ids:
                send_ids = set(send_data["e_to_rec_tail_ids"].get(row["e_key_tail"], set()))
            if send_ids:
                match_mode = "tail_relaxed"
        send_id_list = sorted(send_ids)
        chosen_id = send_id_list[0] if send_id_list else ""
        if send_id_list:
            send_hit += 1
            if match_mode == "tail_relaxed":
                send_hit_tail += 1
        file4_joined.append({**row, "send_id": chosen_id, "send_ids": send_id_list, "match_mode": match_mode})

    matched_int_ids = {sid for row in file2_joined for sid in row.get("int_ids", []) if sid}
    matched_send_ids = {sid for row in file4_joined for sid in row.get("send_ids", []) if sid}

    link_specs = [
        ("DISTRIBUTERECORD", ["SOURCE_OBJECT_ID"], ["OPERATOR", "SENDER", "CREATED_BY_ID", "MODIFIED_BY_ID"]),
        ("OBJECTREPLYLINK", ["SOURCE_OBJECT_ID", "REPLY_OBJECT_ID"], ["CREATED_BY_ID", "MODIFIED_BY_ID"]),
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
    source_number_keys = set(int_data.get("number_keys", set())) | set(send_data.get("number_keys", set()))
    chain_records_by_table: Dict[str, List[Dict[str, Any]]] = {}
    for table, source_cols, _owner_cols in link_specs:
        base_records = sampled_map.get(table, {}).get("records", []) or []
        table_entry = _find_table_entry(schema_snapshot, schema_name=schema_name, table_name=table)
        table_cols = {
            str(col.get("name", "")).upper()
            for col in ((table_entry or {}).get("columns", []) or [])
        }
        has_is_current = "IS_CURRENT" in table_cols

        target_records: List[Dict[str, Any]] = []
        id_source_cols = [c for c in source_cols if c.upper() in table_cols]
        source_ids_union = matched_int_ids | matched_send_ids
        if id_source_cols and source_ids_union:
            target_records = _run_targeted_query(
                f"定向查询 {schema_name}.{table}(源ID)",
                lambda c: _fetch_table_by_source_ids(
                    c,
                    schema_name=schema_name,
                    table_name=table,
                    source_columns=id_source_cols,
                    source_ids=source_ids_union,
                    has_is_current=has_is_current,
                ),
            )

        if table == "OBJECTREPLYLINK":
            num_cols = [c for c in ["SOURCE_OBJECT_NUMBER", "REPLY_OBJECT_NUMBER"] if c in table_cols]
            if num_cols and source_number_keys:
                if len(source_number_keys) <= 8000:
                    number_records = _run_targeted_query(
                        f"定向查询 {schema_name}.{table}(编号归一化键)",
                        lambda c: _fetch_table_by_norm_keys(
                            c,
                            schema_name=schema_name,
                            table_name=table,
                            key_columns=num_cols,
                            norm_keys=source_number_keys,
                            has_is_current=has_is_current,
                        ),
                    )
                    target_records = _merge_unique_records(target_records, number_records)
                else:
                    diag("[INFO] OBJECTREPLYLINK 编号归一化键规模过大，跳过归一化定向查询以降低超时风险。")

        merged_records = _merge_unique_records(target_records, base_records)
        chain_records_by_table[table] = merged_records
        if target_records:
            diag(f"[INFO] 定向链路查询 {schema_name}.{table} 命中行: {len(target_records)}")
            sampled_map[table]["records"] = merged_records
            sampled_map[table]["available"] = True
            sampled_map[table]["status"] = "ok_targeted" if sampled_map[table].get("status") != "ok" else "ok"
            sampled_map[table]["row_count_sampled"] = len(merged_records)
            for row in table_access_rows:
                if row.get("table") == table:
                    row["status"] = "ok_targeted" if row.get("status") != "ok" else "ok"
                    row["has_sample"] = True
                    row["row_count"] = max(int(row.get("row_count", 0) or 0), len(merged_records))
                    break

    file2_links: Dict[str, Dict[str, Any]] = {}
    file4_links: Dict[str, Dict[str, Any]] = {}
    for table, source_cols, owner_cols in link_specs:
        file2_links[table] = _build_link_data(
            chain_records_by_table.get(table, []),
            matched_int_ids,
            source_cols,
            owner_cols,
        )
        file4_links[table] = _build_link_data(
            chain_records_by_table.get(table, []),
            matched_send_ids,
            source_cols,
            owner_cols,
        )

    coverage_rows: List[CoverageRow] = []
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
                (
                    "OBJECTREPLYLINK.SOURCE_OBJECT_ID/REPLY_OBJECT_ID"
                    if table == "OBJECTREPLYLINK"
                    else f"{table}.SOURCE_OBJECT_ID"
                ),
                bool(link.get("available")),
                len(matched_int_ids),
                matched_count,
                status,
                link.get("reason", ""),
            )
        )

    unique_e_count = len(file4_e_keys)
    unique_e_send_hit = sum(1 for key in file4_e_keys if len(send_data["e_to_send_ids"].get(key, set())) == 1)
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
            "tail-relaxed hit",
        )
    )

    for table, source_col in (
        ("DISTRIBUTERECORD", "SOURCE_OBJECT_ID"),
        ("OBJECTREPLYLINK", "SOURCE_OBJECT_ID/REPLY_OBJECT_ID"),
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

    for table in REPLY_TABLES:
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

    for col in int_data["owner_columns"]:
        values, owners = [], []
        for row in file2_joined:
            value = _pick_owner_value_from_ids(
                row.get("int_ids", []),
                int_data["id_owner_values"],
                col,
            )
            values.append(value)
            owners.append(row.get("owner_raw", ""))
        owner_candidate_scores.append(
            _build_candidate_row(
                file_type="2",
                chain_path="file2:A,D->INT",
                table="INTINTERFACEDOC",
                column=col,
                values=values,
                excel_owner_values=owners,
                user_map=user_id_map,
                available=True,
            )
        )

    for col in send_data["owner_columns"]:
        values, owners = [], []
        for row in file4_joined:
            value = _pick_owner_value_from_ids(
                row.get("send_ids", []),
                send_data["id_owner_values"],
                col,
            )
            values.append(value)
            owners.append(row.get("owner_raw", ""))
        owner_candidate_scores.append(
            _build_candidate_row(
                file_type="4",
                chain_path="file4:E->SEND",
                table="SENDRECEIVEDATA",
                column=col,
                values=values,
                excel_owner_values=owners,
                user_map=user_id_map,
                available=True,
            )
        )

    for table, _source_cols, owner_cols in link_specs:
        link2 = file2_links[table]
        link4 = file4_links[table]
        for col in owner_cols:
            values2, owners2 = [], []
            for row in file2_joined:
                val = _pick_owner_value_from_ids(
                    row.get("int_ids", []),
                    link2.get("owner_by_source", {}) or {},
                    col,
                )
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
                    user_map=user_id_map,
                    available=bool(link2.get("available")),
                    note=str(link2.get("reason", "")),
                )
            )

            values4, owners4 = [], []
            for row in file4_joined:
                val = _pick_owner_value_from_ids(
                    row.get("send_ids", []),
                    link4.get("owner_by_source", {}) or {},
                    col,
                )
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
                    user_map=user_id_map,
                    available=bool(link4.get("available")),
                    note=str(link4.get("reason", "")),
                )
            )

    blocked_tables = [row["table"] for row in table_access_rows if not str(row.get("status", "")).startswith("ok")]
    minimal_data_requests = [
        {
            "table": table,
            "required_fields": MINIMAL_SUPPLEMENT_FIELDS.get(
                table, ["ID", "CREATED_BY_ID", "MODIFIED_BY_ID", "CREATED_ON"]
            ),
            "suggested_time_range": "近3-5年",
        }
        for table in blocked_tables
    ]

    file2_link_ok = any(
        row.scenario == "file2"
        and row.step in {"int_id_to_distributerecord", "int_id_to_objectreplylink"}
        and row.matched_count > 0
        for row in coverage_rows
    )
    file4_link_ok = any(
        row.scenario == "file4"
        and row.step in {"send_id_to_distributerecord", "send_id_to_objectreplylink", "send_id_to_filetransmission"}
        and row.matched_count > 0
        for row in coverage_rows
    )

    blocking_points: List[str] = []
    for row in table_access_rows:
        if not str(row.get("status", "")).startswith("ok"):
            blocking_points.append(f"{row['table']} => {row['status']}")
    if targeted_query_health.get("connection_interruptions", 0) > 0:
        blocking_points.append(
            "定向查询阶段发生连接中断，部分查询未执行或仅使用回退采样结果（详见 targeted_query_health）。"
        )
    if not file2_link_ok:
        blocking_points.append("文件2分发表链路覆盖不足（DISTRIBUTERECORD/OBJECTREPLYLINK 未形成有效命中）。")
    if not file4_link_ok:
        blocking_points.append("文件4分发表链路覆盖不足（DISTRIBUTERECORD/OBJECTREPLYLINK/FILETRANSMISSION 未形成有效命中）。")

    top_file2 = sorted(
        [x for x in owner_candidate_scores if x["file_type"] == "2" and x["available"]],
        key=lambda x: float(x.get("score") or 0.0),
        reverse=True,
    )
    top_file4 = sorted(
        [x for x in owner_candidate_scores if x["file_type"] == "4" and x["available"]],
        key=lambda x: float(x.get("score") or 0.0),
        reverse=True,
    )
    best_owner = {
        "file2": top_file2[0] if top_file2 else {},
        "file4": top_file4[0] if top_file4 else {},
    }

    question_answers = {
        "q1_file2_need_distribution_chain": {
            "answer": "YES" if file2_link_ok else "YES_BUT_BLOCKED",
            "detail": "需要分发链路来定位主责字段。",
        },
        "q2_file4_need_distribution_chain": {
            "answer": "YES" if file4_link_ok else "YES_BUT_BLOCKED",
            "detail": "需要分发链路来定位主责字段。",
        },
        "q3_best_owner_source": {
            "answer": (
                f"文件2={best_owner['file2'].get('table', '')}.{best_owner['file2'].get('column', '')}; "
                f"文件4={best_owner['file4'].get('table', '')}.{best_owner['file4'].get('column', '')}"
            ),
            "detail": "若链路覆盖不足，则采用非最终口径回退字段。",
        },
        "q4_blocked_by_permission_or_data": {
            "answer": "YES" if blocking_points else "NO",
            "detail": "; ".join(blocking_points) if blocking_points else "无阻塞",
        },
    }

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "output_root": str(run_root),
        "question_answers": question_answers,
        "coverage_rows": [row.to_dict() for row in coverage_rows],
        "owner_candidate_scores": owner_candidate_scores,
        "table_access": table_access_rows,
        "targeted_query_health": targeted_query_health,
        "minimal_data_requests": minimal_data_requests,
        "blocking_points": blocking_points,
    }

    (run_root / "real_distribution_chain_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    (run_root / "real_distribution_chain_report.md").write_text(
        _build_markdown_report(payload),
        encoding="utf-8",
    )

    with (run_root / "table_rowcount_and_coverage.csv").open("w", encoding="utf-8-sig", newline="") as stream:
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
        for row in table_access_rows:
            writer.writerow(
                {
                    "scenario": "table_inventory",
                    "step": "sample_rowcount",
                    "source": f"{schema_name}.{row['table']}",
                    "target": "sample_rows",
                    "available": str(row["status"]).startswith("ok"),
                    "source_count": row["row_count"],
                    "matched_count": row["row_count"],
                    "coverage_rate": 1.0 if str(row["status"]).startswith("ok") else "",
                    "status": row["status"],
                    "details": "required_table",
                }
            )

    with (run_root / "owner_candidate_scores.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "file_type",
                "chain_path",
                "table",
                "column",
                "semantic_tag",
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

    return payload
