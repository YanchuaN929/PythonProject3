"""Deep-dive probe for file6 SQL routing and field rules."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd

from .file4_ah_owner_chain_probe import _owner_match
from .file4_dist_route_probe import DIST_COLS, DIST_IDX, _extract_values_blob, _iter_insert_statements, _split_sql_values
from .file6_distribution_chain_probe import _build_relation_map, _expand_relation_ids
from .real_distribution_chain_probe import _clean_text, _norm_key, _safe_get
from .roster import load_all_roster_names
from .validate_cims_sql_dump import iter_insert_rows, normalize_hex32, parse_create_columns, parse_department_map, parse_user_map


ORG_FILTER = "河北分公司.建筑结构所"
SNAPSHOT_DATE = date(2026, 3, 4)
RUNTIME_DATE = date(2026, 3, 11)
FILE6_PATTERN = re.compile(r"^收发文清单(?P<project>\d{4})?.*\.xlsx$")
SEP_RE = re.compile(r"[,，;；/、]+")
INVALID_TEXT = {"", "nan", "none", "null", "nat"}
NOT_REPLIED = {"尚未回复", "超期未回复"}
INT_ITEM_TABLES = ("TA", "CR", "DCR", "NCR", "TCR")
SEND_SIDE_TABLES = (
    "TA",
    "CR",
    "DCR",
    "FCR",
    "NCR",
    "TCR",
    "TAREPLY",
    "CRREPLY",
    "DCRREPLY",
    "FCRREPLY",
    "NCRREPLY",
    "TCRREPLY",
    "FILETRANSMISSION",
    "MEMORANDUM",
    "TELEFAX",
    "INTERNALMINUTES",
    "EXTERNALMINUTES",
    "FUNOTIFY",
    "CANCELNOTIFY",
    "DESIGNREVIEWOPNION",
    "DESIGNREVIEWREPLY",
)


def _rate(hit: int, total: int) -> float:
    return round(hit / total, 6) if total else 0.0


def _norm_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return ""
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text or text.lower() in INVALID_TEXT:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if parsed is not pd.NaT and not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")
    match = re.search(r"(\d{4})[-/\.](\d{1,2})[-/\.](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return text[:10]


def _to_date(value: Any) -> date | None:
    text = _norm_date(value)
    if not text:
        return None
    try:
        return pd.to_datetime(text).date()
    except Exception:
        return None


def _truthy(value: Any) -> bool | None:
    text = _clean_text(value).upper()
    if not text:
        return None
    if text in {"1", "Y", "YES", "TRUE", "T", "是"}:
        return True
    if text in {"0", "N", "NO", "FALSE", "F", "否"}:
        return False
    return None


def _version_rank(value: Any) -> int:
    text = _clean_text(value)
    if not text:
        return 0
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return 0
    return ord(match.group(0).upper()) - ord("A") + 1


def _classify_key(value: Any) -> str:
    raw = _clean_text(value).upper()
    compact = _norm_key(value)
    if not raw:
        return "empty_key"
    if "-ZL-" in raw:
        return "int_key"
    if compact.startswith(tuple(f"{project}BW" for project in ["1818", "1907", "1915", "1916", "2016", "2026", "2306", "0000"])):
        return "special_bw"
    return "letter_key"


def _split_multi(value: Any) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    result: List[str] = []
    for token in SEP_RE.split(text):
        token = token.strip()
        if token and token not in result:
            result.append(token)
    return result


def _normalize_org_tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    for token in _split_multi(value):
        current = token.replace(" ", "")
        if current and current not in tokens:
            tokens.append(current)
        if current.startswith("河北分公司.") and current[6:] not in tokens:
            tokens.append(current[6:])
        if "建筑结构所" in current and "河北分公司.建筑结构所" not in tokens:
            tokens.append("河北分公司.建筑结构所")
        if any(code in current.upper() for code in ("25C1", "25C2", "25C3")):
            for candidate in ("河北分公司.建筑结构所", "建筑结构所"):
                if candidate not in tokens:
                    tokens.append(candidate)
    return tokens


def _normalize_office_tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    for token in _split_multi(value):
        current = token.replace(" ", "")
        if "." in current:
            current = current.split(".")[-1]
        if current and current not in tokens:
            tokens.append(current)
    return tokens


def _derive_offices_from_orgs(values: Sequence[Any]) -> List[str]:
    offices: List[str] = []
    for value in values:
        for token in _normalize_org_tokens(value):
            current = token.replace("河北分公司.", "")
            if "." not in current:
                continue
            office = current.split(".")[-1]
            if office and office not in offices:
                offices.append(office)
    return offices


def _resolve_sql35_table_path(sql35_dir: Path, table_name: str) -> Path:
    candidates = [
        sql35_dir / f"{table_name}_20260305.sql",
        sql35_dir / f"{table_name}.sql",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _org_match(excel_value: Any, sql_values: Sequence[Any]) -> bool:
    excel_tokens = _normalize_org_tokens(excel_value)
    if not excel_tokens:
        return False
    sql_tokens: List[str] = []
    for value in sql_values:
        for token in _normalize_org_tokens(value):
            if token not in sql_tokens:
                sql_tokens.append(token)
    for excel_token in excel_tokens:
        excel_norm = excel_token.replace("河北分公司.", "")
        for sql_token in sql_tokens:
            sql_norm = sql_token.replace("河北分公司.", "")
            if excel_token == sql_token or excel_norm == sql_norm:
                return True
            if excel_norm and (excel_norm.endswith(sql_norm) or sql_norm.endswith(excel_norm)):
                return True
    return False


def _office_match(excel_value: Any, sql_values: Sequence[Any]) -> bool:
    excel_tokens = _normalize_office_tokens(excel_value)
    if not excel_tokens:
        return False
    sql_tokens = _derive_offices_from_orgs(sql_values)
    return bool(set(excel_tokens) & set(sql_tokens))


def _status_from_fields(answer_date: Any, reply_deadline: Any, reference_date: date, need_reply: Any = None) -> str:
    need_flag = _truthy(need_reply)
    ans = _to_date(answer_date)
    ddl = _to_date(reply_deadline)
    if ans:
        if ddl and ans > ddl:
            return "超期回复"
        return "按时回复"
    if need_flag is False:
        return "无需回复"
    if ddl:
        return "超期未回复" if ddl < reference_date else "尚未回复"
    return "尚未回复"


def _filter_highest_version(rows: Sequence[Dict[str, Any]]) -> Set[Tuple[str, int]]:
    best_rank: Dict[str, int] = {}
    best_rows: Dict[str, List[Tuple[str, int]]] = {}
    for row in rows:
        key = row["e_key"]
        if not key:
            continue
        rank = row["version_rank"]
        marker = (row["workbook"], row["excel_row"])
        current = best_rank.get(key)
        if current is None or rank > current:
            best_rank[key] = rank
            best_rows[key] = [marker]
        elif rank == current:
            best_rows.setdefault(key, []).append(marker)
    result: Set[Tuple[str, int]] = set()
    for markers in best_rows.values():
        result.update(markers)
    return result


def _metric_by_project(rows: Sequence[Dict[str, Any]], flag_getter) -> Dict[str, Any]:
    by_project: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "hit": 0})
    hit = 0
    for row in rows:
        by_project[row["project"]]["total"] += 1
        if flag_getter(row):
            hit += 1
            by_project[row["project"]]["hit"] += 1
    return {
        "total": len(rows),
        "hit": hit,
        "rate": _rate(hit, len(rows)),
        "by_project": {
            project: {
                "total": payload["total"],
                "hit": payload["hit"],
                "rate": _rate(payload["hit"], payload["total"]),
            }
            for project, payload in sorted(by_project.items())
        },
    }


def load_file6_rows(excel_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(excel_dir.glob("收发文清单*.xlsx")):
        match = FILE6_PATTERN.match(path.name)
        if not match:
            continue
        project = match.group("project") or ""
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
        for row_no in range(len(df)):
            values = df.iloc[row_no].tolist()
            e_raw = _safe_get(values, 4)
            rows.append(
                {
                    "project": project,
                    "workbook": path.name,
                    "excel_row": row_no + 2,
                    "e_raw": _clean_text(e_raw),
                    "e_key": _norm_key(e_raw),
                    "key_type": _classify_key(e_raw),
                    "a_raw": _clean_text(_safe_get(values, 0)),
                    "h_raw": _clean_text(_safe_get(values, 7)),
                    "i_raw": _safe_get(values, 8),
                    "j_raw": _safe_get(values, 9),
                    "m_raw": _clean_text(_safe_get(values, 12)),
                    "v_raw": _clean_text(_safe_get(values, 21)),
                    "w_raw": _clean_text(_safe_get(values, 22)),
                    "x_raw": _clean_text(_safe_get(values, 23)),
                    "ac_raw": _clean_text(_safe_get(values, 28)),
                    "version_rank": _version_rank(_safe_get(values, 28)),
                }
            )
    return rows


def scan_int_table(path: Path, needed_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "ITEM_NUMBER",
        "PROPOSED_DEPT",
        "RECEIVE_DEPT",
        "RESP_SHEZONG",
        "RE_OPEN_RESP_SHEZONG",
        "RELEVANT_PERSON",
        "CREATED_BY_ID",
        "MODIFIED_BY_ID",
        "REPLY_DEADLINE",
        "ANSWER_DATE",
        "REV",
        "SUBMIT_DATE",
        "RELEASE_DATE",
        "MODIFIED_ON",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    is_current_idx = mapping.get("is_current", -1)
    by_key: Dict[str, Dict[str, Any]] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if is_current_idx >= 0 and str(_safe_get(row, is_current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        item_key = _norm_key(_safe_get(row, idx["ITEM_NUMBER"]))
        if not item_key or item_key not in needed_keys:
            continue
        matched += 1
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["row_score"] = (
            _norm_date(payload.get("SUBMIT_DATE")),
            _norm_date(payload.get("RELEASE_DATE")),
            _clean_text(payload.get("MODIFIED_ON")),
            _clean_text(payload.get("REV")),
        )
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                normalize_hex32(payload.get("ID")),
                normalize_hex32(payload.get("CONFIG_ID")),
            )
            if rel_id
        }
        obj_id = normalize_hex32(payload.get("ID"))
        if obj_id:
            by_id[obj_id] = payload
        previous = by_key.get(item_key)
        if previous is None or payload["row_score"] >= previous["row_score"]:
            by_key[item_key] = payload
    return {"scanned": scanned, "matched": matched, "by_key": by_key, "by_id": by_id}


def scan_send_table(path: Path, needed_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "CLASSIFICATION",
        "AUTHOR_UNIT",
        "RECEIVE_UNIT",
        "CORRESP_LETTER_REC_NO",
        "LETTER_SEND_NO",
        "NEED_REPLY",
        "REPLY_DEADLINE",
        "IS_ANSWERED",
        "ANSWER_DATE",
        "SEND_DATE",
        "RECEIVE_DATE",
        "SEND_RECV_LETT_DATE",
        "CREATED_BY_ID",
        "MODIFIED_BY_ID",
        "MODIFIED_ON",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    is_current_idx = mapping.get("is_current", -1)
    by_id: Dict[str, Dict[str, Any]] = {}
    rec_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    send_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if is_current_idx >= 0 and str(_safe_get(row, is_current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        rec_key = _norm_key(_safe_get(row, idx["CORRESP_LETTER_REC_NO"]))
        send_key = _norm_key(_safe_get(row, idx["LETTER_SEND_NO"]))
        if rec_key not in needed_keys and send_key not in needed_keys:
            continue
        matched += 1
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["row_score"] = (
            _norm_date(payload.get("ANSWER_DATE")),
            _norm_date(payload.get("REPLY_DEADLINE")),
            _clean_text(payload.get("MODIFIED_ON")),
            _clean_text(payload.get("LETTER_SEND_NO")),
            _clean_text(payload.get("CORRESP_LETTER_REC_NO")),
        )
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                normalize_hex32(payload.get("ID")),
                normalize_hex32(payload.get("CONFIG_ID")),
            )
            if rel_id
        }
        obj_id = normalize_hex32(payload.get("ID"))
        if not obj_id:
            continue
        by_id[obj_id] = payload
        if rec_key in needed_keys:
            rec_to_ids[rec_key].add(obj_id)
        if send_key in needed_keys:
            send_to_ids[send_key].add(obj_id)
    return {"scanned": scanned, "matched": matched, "by_id": by_id, "rec_to_ids": rec_to_ids, "send_to_ids": send_to_ids}


def scan_child_table(path: Path, table_name: str, needed_send_ids: Set[str], needed_item_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "ITEM_NUMBER",
        "SEND_RECEIVE_DATA",
        "CREATED_BY_ID",
        "MODIFIED_BY_ID",
        "AUTHOR_UNIT",
        "RECEIVE_UNIT",
        "SEND_DATE",
        "NEED_REPLY_DATE",
        "RELEASE_DATE",
        "MAJOR_REV",
        "MINOR_REV",
        "MODIFIED_ON",
        "CREATED_ON",
        "CR",
        "DCR",
        "FCR",
        "TA",
        "NCR",
        "TCR",
        "MASTER_SEND",
        "FILE_TRANSMISSION",
        "REF_FILE_TRANSMISSION",
        "REF_MEMO",
        "REF_FAX",
        "DESIGN_REVIEW_OPNION",
        "DESIGN_REVIEW_REPLY",
        "OPPOSITE_DOCUMENT_NUMBER",
        "DISPATCH_NUM",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    is_current_idx = mapping.get("is_current", -1)
    by_id: Dict[str, Dict[str, Any]] = {}
    send_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    item_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if is_current_idx >= 0 and str(_safe_get(row, is_current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        send_id = normalize_hex32(_safe_get(row, idx["SEND_RECEIVE_DATA"]))
        item_key = _norm_key(_safe_get(row, idx["ITEM_NUMBER"]))
        if (send_id not in needed_send_ids) and (item_key not in needed_item_keys):
            continue
        matched += 1
        obj_id = normalize_hex32(_safe_get(row, idx["ID"]))
        if not obj_id:
            continue
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["table"] = table_name
        payload["row_score"] = (
            _norm_date(payload.get("RELEASE_DATE")),
            _clean_text(payload.get("MODIFIED_ON")),
            _clean_text(payload.get("CREATED_ON")),
            _clean_text(payload.get("ITEM_NUMBER")),
            _clean_text(payload.get("MAJOR_REV")),
        )
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                normalize_hex32(payload.get("ID")),
                normalize_hex32(payload.get("CONFIG_ID")),
                normalize_hex32(payload.get("CR")),
                normalize_hex32(payload.get("DCR")),
                normalize_hex32(payload.get("FCR")),
                normalize_hex32(payload.get("TA")),
                normalize_hex32(payload.get("NCR")),
                normalize_hex32(payload.get("TCR")),
                normalize_hex32(payload.get("MASTER_SEND")),
                normalize_hex32(payload.get("FILE_TRANSMISSION")),
                normalize_hex32(payload.get("REF_FILE_TRANSMISSION")),
                normalize_hex32(payload.get("REF_MEMO")),
                normalize_hex32(payload.get("REF_FAX")),
                normalize_hex32(payload.get("DESIGN_REVIEW_OPNION")),
                normalize_hex32(payload.get("DESIGN_REVIEW_REPLY")),
            )
            if rel_id
        }
        by_id[obj_id] = payload
        if send_id in needed_send_ids:
            send_to_ids[send_id].add(obj_id)
        if item_key in needed_item_keys:
            item_to_ids[item_key].add(obj_id)
    return {
        "table": table_name,
        "scanned": scanned,
        "matched": matched,
        "by_id": by_id,
        "send_to_ids": send_to_ids,
        "item_to_ids": item_to_ids,
    }


def scan_filetransmission_route(path: Path, needed_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "SEND_RECEIVE_DATA",
        "REF_FILE_TRANSMISSION",
        "CSS",
        "CONTENT",
        "THEME",
        "CREATED_BY_ID",
        "MODIFIED_BY_ID",
        "RELEASE_DATE",
        "MODIFIED_ON",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    is_current_idx = mapping.get("is_current", -1)
    by_id: Dict[str, Dict[str, Any]] = {}
    key_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0

    def _extract_doc_keys(text: Any) -> List[str]:
        raw = _clean_text(text)
        if not raw:
            return []
        captured: List[str] = []
        match = re.search(r"发文号:(.+?)-文件传递单", raw)
        if match:
            captured.extend(_split_multi(match.group(1)))
        for token in re.findall(r"[A-Z0-9]+(?:-[A-Z0-9]+){2,}", raw.upper()):
            captured.append(token)
        result: List[str] = []
        for token in captured:
            key = _norm_key(token)
            if key and key in needed_keys and key not in result:
                result.append(key)
        return result

    for row in iter_insert_rows(path):
        scanned += 1
        if is_current_idx >= 0 and str(_safe_get(row, is_current_idx) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        keys: List[str] = []
        for field in ("CSS", "CONTENT", "THEME"):
            keys.extend(_extract_doc_keys(_safe_get(row, idx[field])))
        keys = list(dict.fromkeys(keys))
        if not keys:
            continue
        matched += 1
        obj_id = normalize_hex32(_safe_get(row, idx["ID"]))
        if not obj_id:
            continue
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["row_score"] = (_norm_date(payload.get("RELEASE_DATE")), _clean_text(payload.get("MODIFIED_ON")), _clean_text(payload.get("CSS")))
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                normalize_hex32(payload.get("ID")),
                normalize_hex32(payload.get("CONFIG_ID")),
                normalize_hex32(payload.get("SEND_RECEIVE_DATA")),
                normalize_hex32(payload.get("REF_FILE_TRANSMISSION")),
            )
            if rel_id
        }
        by_id[obj_id] = payload
        for key in keys:
            key_to_ids[key].add(obj_id)
    return {"scanned": scanned, "matched": matched, "by_id": by_id, "key_to_ids": key_to_ids}


def _best_id(ids: Iterable[str], by_id: Dict[str, Dict[str, Any]]) -> str:
    choice = ""
    best_score: Tuple[str, ...] = ()
    for obj_id in sorted(set(ids)):
        score = tuple(str(item) for item in by_id.get(obj_id, {}).get("row_score", ()))
        if not choice or score >= best_score:
            choice = obj_id
            best_score = score
    return choice


def scan_distribution(path: Path, target_ids: Set[str]) -> Dict[str, Any]:
    object_groups: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {"sender_ids": set(), "ops": [], "latest": pd.Timestamp.min, "source_types": set()}
    )
    statement_count = 0
    matched_count = 0
    for statement in _iter_insert_statements(path):
        statement_count += 1
        values_blob = _extract_values_blob(statement)
        if not values_blob:
            continue
        row = _split_sql_values(values_blob)
        if len(row) < len(DIST_COLS):
            continue
        if str(row[DIST_IDX["is_current"]] or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_object_id = normalize_hex32(row[DIST_IDX["source_object_id"]])
        if not source_object_id or source_object_id not in target_ids:
            continue
        sender = normalize_hex32(row[DIST_IDX["sender"]]) or _clean_text(row[DIST_IDX["sender"]])
        operator = _clean_text(row[DIST_IDX["operator"]])
        operation_time = pd.to_datetime(str(row[DIST_IDX["operation_time"]] or "").strip(), errors="coerce")
        if operation_time is pd.NaT:
            operation_time = pd.Timestamp.min
        group = object_groups[source_object_id]
        if sender:
            group["sender_ids"].add(sender)
        if operator:
            group["ops"].append((operator, operation_time))
        if operation_time > group["latest"]:
            group["latest"] = operation_time
        source_type = _clean_text(row[DIST_IDX["source_type"]])
        if source_type:
            group["source_types"].add(source_type)
        matched_count += 1

    leaves_by_id: Dict[str, List[str]] = {}
    latest_leaves_by_id: Dict[str, List[str]] = {}
    for source_object_id, payload in object_groups.items():
        union_leafs: List[str] = []
        latest_leafs: List[str] = []
        for operator, operation_time in payload["ops"]:
            operator_id = normalize_hex32(operator)
            compare_key = operator_id or operator
            if compare_key in payload["sender_ids"]:
                continue
            if operator not in union_leafs:
                union_leafs.append(operator)
            if payload["latest"] is not pd.Timestamp.min and operation_time == payload["latest"] and operator not in latest_leafs:
                latest_leafs.append(operator)
        leaves_by_id[source_object_id] = union_leafs
        latest_leaves_by_id[source_object_id] = latest_leafs
    return {
        "statement_count": statement_count,
        "matched_count": matched_count,
        "object_group_count": len(object_groups),
        "leaves_by_id": leaves_by_id,
        "latest_leaves_by_id": latest_leaves_by_id,
    }


def _field_metric(rows: Sequence[Dict[str, Any]], matcher, kind: str) -> Dict[str, Any]:
    return {"kind": kind, **_metric_by_project(rows, matcher)}


def _candidate_metric(rows: Sequence[Dict[str, Any]], getter, *, matcher) -> Dict[str, Any]:
    non_empty_rows = [row for row in rows if _clean_text(row.get("x_raw"))]
    return _metric_by_project(non_empty_rows, lambda row: matcher(row["x_raw"], getter(row)))


def _match_owner(excel_value: Any, sql_value: Any, user_map: Dict[str, Dict[str, Any]], roster_names: Set[str]) -> bool:
    return _owner_match(excel_value, sql_value, user_map, roster_names)


def _derive_runtime_rule(row: Dict[str, Any], *, reference_date: date) -> Dict[str, bool]:
    i_value = row.get("sql_i")
    v_values = row.get("sql_v_values", [])
    status = row.get("sql_status_runtime") if reference_date == RUNTIME_DATE else row.get("sql_status_snapshot")
    i_date = _to_date(i_value)
    return {
        "p1_v": _org_match(ORG_FILTER, v_values),
        "p_i_not_empty": bool(_norm_date(i_value)),
        "p3_i_window": bool(i_date and (i_date - reference_date).days <= 14),
        "p4_m": status in NOT_REPLIED,
    }


def run(excel_dir: Path, sql35_dir: Path, sql37_dir: Path, output_path: Path) -> Dict[str, Any]:
    rows = load_file6_rows(excel_dir)
    version_best = _filter_highest_version(rows)
    dept_map = parse_department_map(_resolve_sql35_table_path(sql35_dir, "DEPARTMENT"))
    user_map = parse_user_map(_resolve_sql35_table_path(sql35_dir, "USER"), dept_map)
    roster_names = load_all_roster_names()

    int_rows = [row for row in rows if row["key_type"] == "int_key" and row["e_key"]]
    send_rows = [row for row in rows if row["key_type"] != "empty_key" and row["key_type"] != "int_key" and row["e_key"]]

    int_scan = scan_int_table(_resolve_sql35_table_path(sql35_dir, "INTINTERFACEDOC"), {row["e_key"] for row in int_rows})
    send_scan = scan_send_table(_resolve_sql35_table_path(sql35_dir, "SENDRECEIVEDATA"), {row["e_key"] for row in send_rows})

    needed_send_ids: Set[str] = set()
    for mapping_name in ("rec_to_ids", "send_to_ids"):
        for send_ids in send_scan[mapping_name].values():
            needed_send_ids.update(send_ids)

    child_tables: Dict[str, Dict[str, Any]] = {}
    child_item_keys = {row["e_key"] for row in send_rows}
    for table_name in SEND_SIDE_TABLES:
        sql_path = _resolve_sql35_table_path(sql35_dir, table_name)
        if not sql_path.exists():
            continue
        child_tables[table_name] = scan_child_table(sql_path, table_name, needed_send_ids, child_item_keys)
    ft_direct = scan_filetransmission_route(_resolve_sql35_table_path(sql35_dir, "FILETRANSMISSION"), {row["e_key"] for row in send_rows})

    for table_name in INT_ITEM_TABLES:
        scan = child_tables.get(table_name)
        if not scan:
            continue
        for item_key, ids in scan["item_to_ids"].items():
            send_ids = {normalize_hex32(scan["by_id"][obj_id].get("SEND_RECEIVE_DATA")) for obj_id in ids}
            send_ids = {item for item in send_ids if item}
            if send_ids:
                send_scan["send_to_ids"][item_key].update(send_ids)
    relation_map = _build_relation_map(int_scan, send_scan, ft_direct, *child_tables.values())

    object_ids_for_dist: Set[str] = set(int_scan["by_id"].keys()) | set(send_scan["by_id"].keys()) | set(ft_direct["by_id"].keys())
    for payload in int_scan["by_key"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
    for payload in send_scan["by_id"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
    for payload in ft_direct["by_id"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
    for scan in child_tables.values():
        object_ids_for_dist.update(scan["by_id"].keys())
        for payload in scan["by_id"].values():
            object_ids_for_dist.update(payload.get("relation_ids", set()))
    object_ids_for_dist = _expand_relation_ids(object_ids_for_dist, relation_map)
    dist_scan = scan_distribution(_resolve_sql35_table_path(sql35_dir, "DISTRIBUTERECORD"), object_ids_for_dist)

    route_counter = Counter()
    route_by_project: DefaultDict[str, Counter] = defaultdict(Counter)
    unresolved_samples: List[Dict[str, Any]] = []
    int_matched: List[Dict[str, Any]] = []
    send_matched: List[Dict[str, Any]] = []

    for row in rows:
        row["version_best"] = (row["workbook"], row["excel_row"]) in version_best
        row["branch"] = "unresolved"
        row["sql_i"] = None
        row["sql_j"] = None
        row["sql_v_values"] = []
        row["sql_status_snapshot"] = ""
        row["sql_status_runtime"] = ""
        row["sql_h"] = None
        row["sql_ac"] = None
        row["send_id"] = ""
        row["int_id"] = ""
        row["doc_tables"] = []
        row["dist_leafs"] = []

        if row["key_type"] == "int_key" and row["e_key"] in int_scan["by_key"]:
            payload = int_scan["by_key"][row["e_key"]]
            row["branch"] = "INT"
            row["int_id"] = normalize_hex32(payload.get("ID"))
            row["sql_i"] = payload.get("REPLY_DEADLINE")
            row["sql_j"] = payload.get("ANSWER_DATE")
            row["sql_v_values"] = [payload.get("PROPOSED_DEPT"), payload.get("RECEIVE_DEPT")]
            row["sql_status_snapshot"] = _status_from_fields(payload.get("ANSWER_DATE"), payload.get("REPLY_DEADLINE"), SNAPSHOT_DATE)
            row["sql_status_runtime"] = _status_from_fields(payload.get("ANSWER_DATE"), payload.get("REPLY_DEADLINE"), RUNTIME_DATE)
            row["sql_ac"] = payload.get("REV")
            for obj_id in payload.get("relation_ids", set()):
                for operator in dist_scan["leaves_by_id"].get(obj_id, []):
                    if operator not in row["dist_leafs"]:
                        row["dist_leafs"].append(operator)
            int_matched.append(row)
        else:
            send_ids = set(send_scan["rec_to_ids"].get(row["e_key"], set())) | set(send_scan["send_to_ids"].get(row["e_key"], set()))
            send_id = _best_id(send_ids, send_scan["by_id"])
            ft_id = _best_id(ft_direct["key_to_ids"].get(row["e_key"], set()), ft_direct["by_id"])
            if not send_id and ft_id:
                linked_send = normalize_hex32(ft_direct["by_id"].get(ft_id, {}).get("SEND_RECEIVE_DATA"))
                if linked_send:
                    send_id = linked_send
            matched_child_tables: List[Tuple[str, Set[str]]] = []
            for table_name, scan in child_tables.items():
                child_ids: Set[str] = set(scan["item_to_ids"].get(row["e_key"], set()))
                if send_id:
                    child_ids.update(scan["send_to_ids"].get(send_id, set()))
                if child_ids:
                    matched_child_tables.append((table_name, child_ids))
            if send_id or ft_id or matched_child_tables:
                payload = send_scan["by_id"].get(send_id, {})
                row["branch"] = "SEND"
                row["send_id"] = send_id
                row["sql_i"] = payload.get("REPLY_DEADLINE")
                row["sql_j"] = payload.get("ANSWER_DATE")
                row["sql_h"] = payload.get("NEED_REPLY")
                row["sql_v_values"] = [payload.get("AUTHOR_UNIT"), payload.get("RECEIVE_UNIT")]
                row["sql_status_snapshot"] = _status_from_fields(payload.get("ANSWER_DATE"), payload.get("REPLY_DEADLINE"), SNAPSHOT_DATE, payload.get("NEED_REPLY"))
                row["sql_status_runtime"] = _status_from_fields(payload.get("ANSWER_DATE"), payload.get("REPLY_DEADLINE"), RUNTIME_DATE, payload.get("NEED_REPLY"))
                doc_tables: List[str] = []
                doc_ids: List[str] = list(payload.get("relation_ids", set()))
                if ft_id:
                    doc_tables.append("FILETRANSMISSION_ROUTE")
                    doc_ids.extend(sorted(ft_direct["by_id"].get(ft_id, {}).get("relation_ids", {ft_id})))
                for table_name, child_ids in matched_child_tables:
                    doc_tables.append(table_name)
                    scan = child_tables[table_name]
                    for child_id in child_ids:
                        doc_ids.extend(sorted(scan["by_id"].get(child_id, {}).get("relation_ids", {child_id})))
                doc_ids = sorted(_expand_relation_ids(doc_ids, relation_map))
                row["doc_tables"] = sorted(set(doc_tables))
                for obj_id in doc_ids:
                    for operator in dist_scan["leaves_by_id"].get(obj_id, []):
                        if operator not in row["dist_leafs"]:
                            row["dist_leafs"].append(operator)
                row["sql_ac"] = ""
                send_matched.append(row)
            elif len(unresolved_samples) < 40 and row["e_key"]:
                unresolved_samples.append(
                    {
                        "project": row["project"],
                        "workbook": row["workbook"],
                        "excel_row": row["excel_row"],
                        "e_raw": row["e_raw"],
                        "key_type": row["key_type"],
                        "a_raw": row["a_raw"],
                    }
                )

        route_counter[row["branch"]] += 1
        route_by_project[row["project"]][row["branch"]] += 1

    int_owner_candidates = {
        "distribution_leaf_union": _candidate_metric(int_matched, lambda row: ",".join(row["dist_leafs"]), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
        "RESP_SHEZONG": _candidate_metric(int_matched, lambda row: int_scan["by_key"].get(row["e_key"], {}).get("RESP_SHEZONG"), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
        "RE_OPEN_RESP_SHEZONG": _candidate_metric(int_matched, lambda row: int_scan["by_key"].get(row["e_key"], {}).get("RE_OPEN_RESP_SHEZONG"), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
        "RELEVANT_PERSON": _candidate_metric(int_matched, lambda row: int_scan["by_key"].get(row["e_key"], {}).get("RELEVANT_PERSON"), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
        "MODIFIED_BY_ID": _candidate_metric(int_matched, lambda row: int_scan["by_key"].get(row["e_key"], {}).get("MODIFIED_BY_ID"), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
    }

    send_owner_candidates: Dict[str, Dict[str, Any]] = {
        "distribution_leaf_union": _candidate_metric(send_matched, lambda row: ",".join(row["dist_leafs"]), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
        "SENDRECEIVEDATA.CREATED_BY_ID": _candidate_metric(send_matched, lambda row: send_scan["by_id"].get(row["send_id"], {}).get("CREATED_BY_ID"), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
        "SENDRECEIVEDATA.MODIFIED_BY_ID": _candidate_metric(send_matched, lambda row: send_scan["by_id"].get(row["send_id"], {}).get("MODIFIED_BY_ID"), matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names)),
    }
    for table_name, scan in child_tables.items():
        send_owner_candidates[f"{table_name}.CREATED_BY_ID"] = _candidate_metric(
            send_matched,
            lambda row, scan=scan: scan["by_id"].get(_best_id(scan["send_to_ids"].get(row["send_id"], set()), scan["by_id"]), {}).get("CREATED_BY_ID"),
            matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names),
        )
        send_owner_candidates[f"{table_name}.MODIFIED_BY_ID"] = _candidate_metric(
            send_matched,
            lambda row, scan=scan: scan["by_id"].get(_best_id(scan["send_to_ids"].get(row["send_id"], set()), scan["by_id"]), {}).get("MODIFIED_BY_ID"),
            matcher=lambda excel, sql: _match_owner(excel, sql, user_map, roster_names),
        )

    send_aux_tables: Dict[str, Dict[str, Any]] = {}
    for table_name, scan in child_tables.items():
        send_aux_tables[table_name] = {
            "rows_scanned": scan["scanned"],
            "rows_matched": scan["matched"],
            "send_link_coverage": _metric_by_project(send_matched, lambda row, scan=scan: bool(scan["send_to_ids"].get(row["send_id"], set()))),
            "item_key_coverage": _metric_by_project(send_rows, lambda row, scan=scan: bool(scan["item_to_ids"].get(row["e_key"], set()))),
        }

    runtime_rows = [row for row in rows if row["version_best"] and row["branch"] in {"INT", "SEND"}]
    runtime_excel = {}
    runtime_sql = {}
    for label, reference_date in {"snapshot": SNAPSHOT_DATE, "runtime": RUNTIME_DATE}.items():
        excel_hits = []
        sql_hits = []
        for row in runtime_rows:
            i_date = _to_date(row["i_raw"])
            excel_rule = {
                "p1_v": ORG_FILTER in _clean_text(row["v_raw"]),
                "p_i_not_empty": bool(_norm_date(row["i_raw"])),
                "p3_i_window": bool(i_date and (i_date - reference_date).days <= 14),
                "p4_m": row["m_raw"] in NOT_REPLIED,
            }
            sql_rule = _derive_runtime_rule(row, reference_date=reference_date)
            excel_hits.append(excel_rule)
            sql_hits.append(sql_rule)

        def _rule_metric(key: str) -> Dict[str, Any]:
            total = len(runtime_rows)
            hit = sum(1 for excel_rule, sql_rule in zip(excel_hits, sql_hits) if excel_rule[key] == sql_rule[key])
            return {"total": total, "hit": hit, "rate": _rate(hit, total)}

        runtime_excel[label] = {
            "p1_v": sum(1 for item in excel_hits if item["p1_v"]),
            "p_i_not_empty": sum(1 for item in excel_hits if item["p_i_not_empty"]),
            "p3_i_window": sum(1 for item in excel_hits if item["p3_i_window"]),
            "p4_m": sum(1 for item in excel_hits if item["p4_m"]),
            "final": sum(1 for item in excel_hits if item["p1_v"] and item["p_i_not_empty"] and item["p3_i_window"] and item["p4_m"]),
        }
        runtime_sql[label] = {
            "p1_v": sum(1 for item in sql_hits if item["p1_v"]),
            "p_i_not_empty": sum(1 for item in sql_hits if item["p_i_not_empty"]),
            "p3_i_window": sum(1 for item in sql_hits if item["p3_i_window"]),
            "p4_m": sum(1 for item in sql_hits if item["p4_m"]),
            "final": sum(1 for item in sql_hits if item["p1_v"] and item["p_i_not_empty"] and item["p3_i_window"] and item["p4_m"]),
            "agreement": {
                "p1_v": _rule_metric("p1_v"),
                "p_i_not_empty": _rule_metric("p_i_not_empty"),
                "p3_i_window": _rule_metric("p3_i_window"),
                "p4_m": _rule_metric("p4_m"),
                "final": {
                    "total": len(runtime_rows),
                    "hit": sum(
                        1
                        for excel_rule, sql_rule in zip(excel_hits, sql_hits)
                        if (excel_rule["p1_v"] and excel_rule["p_i_not_empty"] and excel_rule["p3_i_window"] and excel_rule["p4_m"])
                        == (sql_rule["p1_v"] and sql_rule["p_i_not_empty"] and sql_rule["p3_i_window"] and sql_rule["p4_m"])
                    ),
                    "rate": _rate(
                        sum(
                            1
                            for excel_rule, sql_rule in zip(excel_hits, sql_hits)
                            if (excel_rule["p1_v"] and excel_rule["p_i_not_empty"] and excel_rule["p3_i_window"] and excel_rule["p4_m"])
                            == (sql_rule["p1_v"] and sql_rule["p_i_not_empty"] and sql_rule["p3_i_window"] and sql_rule["p4_m"])
                        ),
                        len(runtime_rows),
                    ),
                },
            },
        }

    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
            "sql37_dir": str(sql37_dir),
            "snapshot_date": str(SNAPSHOT_DATE),
            "runtime_date": str(RUNTIME_DATE),
        },
        "word_guidance": {
            "file6_section": [
                "待处理文件文件6",
                "E列去掉-后再搜索",
                "I列来自页面上的要求答复日期/回文时间需求等信息",
                "责任人看分发信息里的最末级办理人",
                "出现回文日期即视为完成",
                "文档类型应能在数据库中找到专门字段或对象类型",
            ]
        },
        "row_counts": {"all_rows": len(rows), "version_best_rows": len(version_best)},
        "route_summary": {
            "by_branch": dict(sorted(route_counter.items())),
            "by_project": {project: dict(sorted(counter.items())) for project, counter in sorted(route_by_project.items())},
            "by_key_type": dict(sorted(Counter(row["key_type"] for row in rows).items())),
            "coverage": {
                "resolved": _rate(sum(1 for row in rows if row["branch"] in {"INT", "SEND"}), len(rows)),
                "int_branch": _rate(len(int_matched), len(rows)),
                "send_branch": _rate(len(send_matched), len(rows)),
            },
            "unresolved_samples": unresolved_samples,
        },
        "table_scans": {
            "INTINTERFACEDOC": {"rows_scanned": int_scan["scanned"], "rows_matched": int_scan["matched"]},
            "SENDRECEIVEDATA": {"rows_scanned": send_scan["scanned"], "rows_matched": send_scan["matched"]},
            "FILETRANSMISSION_ROUTE": {"rows_scanned": ft_direct["scanned"], "rows_matched": ft_direct["matched"]},
            "DISTRIBUTERECORD": {
                "statement_count": dist_scan["statement_count"],
                "matched_count": dist_scan["matched_count"],
                "object_group_count": dist_scan["object_group_count"],
            },
            "send_aux_tables": send_aux_tables,
        },
        "field_metrics": {
            "INT": {
                "E": _field_metric(int_matched, lambda row: row["e_key"] in int_scan["by_key"], "direct"),
                "I": _field_metric(int_matched, lambda row: _norm_date(row["i_raw"]) == _norm_date(row["sql_i"]), "direct"),
                "J": _field_metric(int_matched, lambda row: _norm_date(row["j_raw"]) == _norm_date(row["sql_j"]), "direct"),
                "M_snapshot": _field_metric(int_matched, lambda row: row["m_raw"] == row["sql_status_snapshot"], "derived"),
                "M_runtime": _field_metric(int_matched, lambda row: row["m_raw"] == row["sql_status_runtime"], "derived"),
                "V": _field_metric(int_matched, lambda row: _org_match(row["v_raw"], row["sql_v_values"]), "dictionary"),
                "W": _field_metric(int_matched, lambda row: _office_match(row["w_raw"], row["sql_v_values"]), "dictionary"),
                "X_leaf": int_owner_candidates["distribution_leaf_union"],
                "AC": _field_metric(int_matched, lambda row: _clean_text(row["ac_raw"]).upper() == _clean_text(row["sql_ac"]).upper(), "direct"),
            },
            "SEND": {
                "E": _field_metric(send_matched, lambda row: bool(row["send_id"]), "direct"),
                "I": _field_metric(send_matched, lambda row: _norm_date(row["i_raw"]) == _norm_date(row["sql_i"]), "direct"),
                "J": _field_metric(send_matched, lambda row: _norm_date(row["j_raw"]) == _norm_date(row["sql_j"]), "direct"),
                "M_snapshot": _field_metric(send_matched, lambda row: row["m_raw"] == row["sql_status_snapshot"], "derived"),
                "M_runtime": _field_metric(send_matched, lambda row: row["m_raw"] == row["sql_status_runtime"], "derived"),
                "V": _field_metric(send_matched, lambda row: _org_match(row["v_raw"], row["sql_v_values"]), "dictionary"),
                "W": _field_metric(send_matched, lambda row: _office_match(row["w_raw"], row["sql_v_values"]), "dictionary"),
                "X_leaf": send_owner_candidates["distribution_leaf_union"],
                "AC": _field_metric(send_matched, lambda row: bool(_clean_text(row["ac_raw"])) and False, "unresolved"),
            },
        },
        "owner_candidates": {"INT": int_owner_candidates, "SEND": send_owner_candidates},
        "extra_checks": {
            "H_need_reply": {
                "SENDRECEIVEDATA.NEED_REPLY": _field_metric(send_matched, lambda row: (_truthy(row["h_raw"]) == _truthy(row["sql_h"])) if _clean_text(row["h_raw"]) else False, "direct"),
                "INTINTERFACEDOC": {"kind": "unresolved", "note": "当前 INTINTERFACEDOC 快照未见直接 NEED_REPLY 字段，文件6 H 在 INT 分支尚未闭环。"},
            },
            "document_type_signal": {
                "excel_type_distribution": dict(sorted(Counter(_clean_text(row["a_raw"]) for row in rows if _clean_text(row["a_raw"])).items())),
                "send_doc_table_hits": {table_name: _metric_by_project(send_matched, lambda row, table_name=table_name: table_name in row["doc_tables"]) for table_name in INT_ITEM_TABLES},
            },
        },
        "runtime_alignment": {"excel": runtime_excel, "sql": runtime_sql},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep-dive probe for file6 SQL rules")
    parser.add_argument("--excel-dir", type=Path, default=Path("example/CIMS-SQL-3.5/EXCEL导出数据"))
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--sql37-dir", type=Path, default=Path("example/CIMS-sql-3.7"))
    parser.add_argument("--output", type=Path, default=Path("tmp/file6_sql_deep_dive_20260311.json"))
    args = parser.parse_args()
    payload = run(args.excel_dir, args.sql35_dir, args.sql37_dir, args.output)
    print(json.dumps({"output": str(args.output), "rows": payload["row_counts"]["all_rows"], "resolved_rate": payload["route_summary"]["coverage"]["resolved"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
