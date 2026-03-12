"""Probe file6 X/V/W against full distribution-chain actors."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd

from .file4_ah_owner_chain_probe import _owner_match
from .file4_dist_route_probe import DIST_COLS, DIST_IDX, _extract_values_blob, _iter_insert_statements, _split_sql_values
from .identity_resolver import resolve_owner_value
from .real_distribution_chain_probe import _clean_text, _norm_key, _safe_get
from .roster import load_all_roster_names
from .validate_cims_sql_dump import iter_insert_rows, normalize_hex32, parse_create_columns, parse_user_map

FILE6_PATTERN = re.compile(r"^收发文清单(?P<project>\d{4})?.*\.xlsx$")
TITLE_KEY_RE = re.compile(r"\b(?:\d{4}BW[0-9A-Z]+|[A-Z0-9]+(?:-[A-Z0-9]+){2,})\b", re.IGNORECASE)
COMPACT_PROJECT_KEY_RE = re.compile(r"\b\d{4}(?=[0-9A-Z]{6,}\b)(?=[0-9A-Z]*[A-Z])[0-9A-Z]+\b", re.IGNORECASE)
SEND_SIDE_TABLES = (
    "TA",
    "CR",
    "DCR",
    "NCR",
    "TCR",
    "TAREPLY",
    "CRREPLY",
    "DCRREPLY",
    "FCRREPLY",
    "NCRREPLY",
    "TCRREPLY",
    "FILETRANSMISSION",
)
PARENT_TABLE_BY_REPLY = {
    "CRREPLY": "CR",
    "TAREPLY": "TA",
    "NCRREPLY": "NCR",
    "DCRREPLY": "DCR",
    "FCRREPLY": "DCR",
    "TCRREPLY": "TCR",
}


def _rate(hit: int, total: int) -> float:
    return round(hit / total, 6) if total else 0.0


def _add_unique(items: List[str], value: Any) -> None:
    text = _clean_text(value)
    if text and text not in items:
        items.append(text)


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


def _version_rank(value: Any) -> int:
    text = _clean_text(value)
    if not text:
        return 0
    match = re.search(r"[A-Za-z]", text)
    if not match:
        return 0
    return ord(match.group(0).upper()) - ord("A") + 1


def _split_multi(value: Any) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    normalized = text
    for sep in [",", "，", ";", "；", "/", "、", "\n"]:
        normalized = normalized.replace(sep, ",")
    result: List[str] = []
    for token in normalized.split(","):
        token = token.strip()
        if token and token not in result:
            result.append(token)
    return result


def _extract_candidate_keys(*values: Any) -> List[str]:
    keys: List[str] = []
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        if re.fullmatch(r"[A-Z0-9-]{4,}", text.upper()):
            key = _norm_key(text)
            if key and key not in keys:
                keys.append(key)
        for token in TITLE_KEY_RE.findall(text.upper()):
            key = _norm_key(token)
            if key and key not in keys:
                keys.append(key)
        for token in COMPACT_PROJECT_KEY_RE.findall(text.upper()):
            key = _norm_key(token)
            if key and key not in keys:
                keys.append(key)
    return keys


def _normalize_org_tokens(value: Any) -> List[str]:
    tokens: List[str] = []
    for token in _split_multi(value):
        current = token.replace(" ", "")
        if current and current not in tokens:
            tokens.append(current)
        if current.startswith("河北分公司."):
            tail = current[len("河北分公司.") :]
            if tail and tail not in tokens:
                tokens.append(tail)
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


def _org_match(excel_value: Any, sql_values: Sequence[Any]) -> bool:
    excel_tokens = _normalize_org_tokens(excel_value)
    if not excel_tokens:
        return False
    sql_tokens: List[str] = []
    for value in sql_values:
        for token in _normalize_org_tokens(value):
            _add_unique(sql_tokens, token)
    for excel_token in excel_tokens:
        excel_norm = excel_token.replace("河北分公司.", "")
        for sql_token in sql_tokens:
            sql_norm = sql_token.replace("河北分公司.", "")
            if excel_token == sql_token or excel_norm == sql_norm:
                return True
            if excel_norm and sql_norm and (excel_norm.endswith(sql_norm) or sql_norm.endswith(excel_norm)):
                return True
    return False


def _office_match(excel_value: Any, sql_values: Sequence[Any]) -> bool:
    excel_tokens = _normalize_office_tokens(excel_value)
    if not excel_tokens:
        return False
    sql_tokens: List[str] = []
    for value in sql_values:
        for token in _normalize_office_tokens(value):
            _add_unique(sql_tokens, token)
    return bool(set(excel_tokens) & set(sql_tokens))


def _best_id(ids: Iterable[str], by_id: Dict[str, Dict[str, Any]]) -> str:
    choice = ""
    best_score: Tuple[str, ...] = ()
    for obj_id in sorted(set(ids)):
        score = tuple(str(item) for item in by_id.get(obj_id, {}).get("row_score", ()))
        if not choice or score >= best_score:
            choice = obj_id
            best_score = score
    return choice


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
                    "a_raw": _clean_text(_safe_get(values, 0)),
                    "e_raw": _clean_text(e_raw),
                    "e_key": _norm_key(e_raw),
                    "key_type": _classify_key(e_raw),
                    "v_raw": _clean_text(_safe_get(values, 21)),
                    "w_raw": _clean_text(_safe_get(values, 22)),
                    "x_raw": _clean_text(_safe_get(values, 23)),
                    "version_rank": _version_rank(_safe_get(values, 28)),
                }
            )
    return rows


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


def parse_department_tree(path: Path) -> Dict[str, Dict[str, str]]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    result: Dict[str, Dict[str, str]] = {}
    for row in iter_insert_rows(path):
        dept_id = normalize_hex32(_safe_get(row, mapping.get("id", -1)))
        if not dept_id:
            continue
        if mapping.get("is_current", -1) >= 0 and str(_safe_get(row, mapping.get("is_current", -1)) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        result[dept_id] = {
            "dept_id": dept_id,
            "dept_name": _clean_text(_safe_get(row, mapping.get("name", mapping.get("name_memo", mapping.get("keyed_name", -1))))),
            "dept_number": _clean_text(_safe_get(row, mapping.get("dept_number", -1))),
            "parent_id": normalize_hex32(_safe_get(row, mapping.get("parent", -1))) or "",
        }
    return result


def _department_chain_names(dept_id: Any, department_map: Dict[str, Dict[str, str]]) -> List[str]:
    current = normalize_hex32(dept_id)
    seen: Set[str] = set()
    names: List[str] = []
    while current and current not in seen:
        seen.add(current)
        payload = department_map.get(current)
        if not payload:
            break
        _add_unique(names, payload.get("dept_name"))
        current = normalize_hex32(payload.get("parent_id"))
    names.reverse()
    return names


def _department_tokens_from_chain(chain: Sequence[str]) -> Dict[str, List[str]]:
    names = [_clean_text(item) for item in chain if _clean_text(item)]
    org_values: List[str] = []
    office_values: List[str] = []
    if not names:
        return {"org_values": org_values, "office_values": office_values}

    for name in names:
        _add_unique(org_values, name)
    for idx in range(len(names) - 1):
        _add_unique(org_values, f"{names[idx]}.{names[idx + 1]}")
    for idx in range(len(names) - 2):
        _add_unique(org_values, f"{names[idx]}.{names[idx + 1]}.{names[idx + 2]}")

    if "河北分公司" in names:
        branch_idx = names.index("河北分公司")
        if branch_idx + 1 < len(names):
            _add_unique(org_values, f"河北分公司.{names[branch_idx + 1]}")
        if branch_idx + 2 < len(names):
            _add_unique(org_values, f"河北分公司.{names[branch_idx + 1]}.{names[branch_idx + 2]}")
            _add_unique(office_values, names[branch_idx + 2])

    if len(names) >= 2:
        _add_unique(org_values, f"{names[-2]}.{names[-1]}")
        if names[-2] != "河北分公司":
            _add_unique(office_values, names[-1])
    return {"org_values": org_values, "office_values": office_values}

def _resolve_distribution_entities(
    values: Sequence[Any],
    user_map: Dict[str, Dict[str, Any]],
    department_map: Dict[str, Dict[str, str]],
) -> Dict[str, List[str]]:
    names: List[str] = []
    org_values: List[str] = []
    office_values: List[str] = []
    for value in values:
        resolved = resolve_owner_value(value, user_map)
        if resolved.get("resolved_users"):
            for user in resolved.get("resolved_users", []):
                _add_unique(names, user.get("user_name"))
                _add_unique(org_values, user.get("dept_name"))
                tokens = _department_tokens_from_chain(
                    _department_chain_names(user.get("dept_id"), department_map)
                )
                for token in tokens["org_values"]:
                    _add_unique(org_values, token)
                for token in tokens["office_values"]:
                    _add_unique(office_values, token)
        else:
            for token in _split_multi(value):
                _add_unique(names, token)
    return {"names": names, "org_values": org_values, "office_values": office_values}


def scan_int_table(path: Path, needed_keys: Set[str], needed_chain_ids: Set[str] | None = None) -> Dict[str, Any]:
    needed_chain_ids = needed_chain_ids or set()
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "ITEM_NUMBER",
        "REF_ITEM_NUMBER",
        "INTINTERFACEDOC",
        "CSS",
        "MODIFIED_ON",
        "CREATED_ON",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    by_key: Dict[str, Dict[str, Any]] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    ref_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    chain_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if mapping.get("is_current", -1) >= 0 and str(_safe_get(row, mapping.get("is_current", -1)) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        item_key = _norm_key(_safe_get(row, idx["ITEM_NUMBER"]))
        ref_key = _norm_key(_safe_get(row, idx["REF_ITEM_NUMBER"]))
        obj_id = normalize_hex32(_safe_get(row, idx["ID"]))
        parent_chain_id = normalize_hex32(_safe_get(row, idx["INTINTERFACEDOC"]))
        chain_id = parent_chain_id or obj_id
        if not item_key and not ref_key and not chain_id:
            continue
        if item_key not in needed_keys and ref_key not in needed_keys and chain_id not in needed_chain_ids:
            continue
        matched += 1
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["chain_id"] = chain_id or ""
        payload["candidate_keys"] = set(
            _extract_candidate_keys(
                payload.get("ITEM_NUMBER"),
                payload.get("REF_ITEM_NUMBER"),
                payload.get("CSS"),
            )
        )
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                obj_id,
                normalize_hex32(payload.get("CONFIG_ID")),
                normalize_hex32(payload.get("INTINTERFACEDOC")),
            )
            if rel_id
        }
        payload["row_score"] = (
            _clean_text(payload.get("MODIFIED_ON")),
            _clean_text(payload.get("CREATED_ON")),
            _clean_text(payload.get("ITEM_NUMBER")),
        )
        if item_key:
            by_key[item_key] = payload
        if obj_id:
            by_id[obj_id] = payload
        if ref_key and obj_id:
            ref_to_ids[ref_key].add(obj_id)
        if chain_id and obj_id:
            chain_to_ids[chain_id].add(obj_id)
    return {
        "scanned": scanned,
        "matched": matched,
        "by_key": by_key,
        "by_id": by_id,
        "ref_to_ids": ref_to_ids,
        "chain_to_ids": chain_to_ids,
    }


def merge_int_scans(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    base["scanned"] += extra.get("scanned", 0)
    base["matched"] += extra.get("matched", 0)
    base["by_key"].update(extra.get("by_key", {}))
    base["by_id"].update(extra.get("by_id", {}))
    for key, ids in extra.get("ref_to_ids", {}).items():
        base["ref_to_ids"][key].update(ids)
    for key, ids in extra.get("chain_to_ids", {}).items():
        base["chain_to_ids"][key].update(ids)
    return base


def scan_send_table(path: Path, needed_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "CORRESP_LETTER_REC_NO",
        "LETTER_SEND_NO",
        "RECEIVE_LETTER_NO",
        "FORWARD_LETTER_NO",
        "CHANNEL_NUMBER",
        "DESCRIPTION",
        "MODIFIED_ON",
        "ANSWER_DATE",
        "REPLY_DEADLINE",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    by_id: Dict[str, Dict[str, Any]] = {}
    rec_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    send_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if mapping.get("is_current", -1) >= 0 and str(_safe_get(row, mapping.get("is_current", -1)) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        rec_key = _norm_key(_safe_get(row, idx["CORRESP_LETTER_REC_NO"]))
        send_key = _norm_key(_safe_get(row, idx["LETTER_SEND_NO"]))
        if rec_key not in needed_keys and send_key not in needed_keys:
            continue
        matched += 1
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["candidate_keys"] = set(
            _extract_candidate_keys(
                payload.get("CORRESP_LETTER_REC_NO"),
                payload.get("LETTER_SEND_NO"),
                payload.get("RECEIVE_LETTER_NO"),
                payload.get("FORWARD_LETTER_NO"),
                payload.get("CHANNEL_NUMBER"),
                payload.get("DESCRIPTION"),
            )
        )
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                normalize_hex32(payload.get("ID")),
                normalize_hex32(payload.get("CONFIG_ID")),
            )
            if rel_id
        }
        payload["row_score"] = (
            _clean_text(payload.get("ANSWER_DATE")),
            _clean_text(payload.get("REPLY_DEADLINE")),
            _clean_text(payload.get("MODIFIED_ON")),
            _clean_text(payload.get("LETTER_SEND_NO")),
            _clean_text(payload.get("CORRESP_LETTER_REC_NO")),
        )
        obj_id = normalize_hex32(payload.get("ID"))
        if not obj_id:
            continue
        by_id[obj_id] = payload
        if rec_key in needed_keys:
            rec_to_ids[rec_key].add(obj_id)
        if send_key in needed_keys:
            send_to_ids[send_key].add(obj_id)
    return {
        "scanned": scanned,
        "matched": matched,
        "by_id": by_id,
        "rec_to_ids": rec_to_ids,
        "send_to_ids": send_to_ids,
    }


def scan_child_table(
    path: Path,
    table_name: str,
    needed_send_ids: Set[str],
    needed_item_keys: Set[str],
    needed_ids: Set[str] | None = None,
) -> Dict[str, Any]:
    needed_ids = needed_ids or set()
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = [
        "ID",
        "CONFIG_ID",
        "ITEM_NUMBER",
        "SEND_RECEIVE_DATA",
        "CR",
        "TA",
        "NCR",
        "MASTER_SEND",
        "REF_FILE_TRANSMISSION",
        "OPPOSITE_DOCUMENT_NUMBER",
        "DISPATCH_NUM",
        "CSS",
        "THEME",
        "REPLY_THEME",
        "MODIFIED_ON",
        "CREATED_ON",
    ]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    by_id: Dict[str, Dict[str, Any]] = {}
    send_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0
    for row in iter_insert_rows(path):
        scanned += 1
        if mapping.get("is_current", -1) >= 0 and str(_safe_get(row, mapping.get("is_current", -1)) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        obj_id = normalize_hex32(_safe_get(row, idx["ID"]))
        send_id = normalize_hex32(_safe_get(row, idx["SEND_RECEIVE_DATA"]))
        item_key = _norm_key(_safe_get(row, idx["ITEM_NUMBER"]))
        if (send_id not in needed_send_ids) and (item_key not in needed_item_keys) and (obj_id not in needed_ids):
            continue
        matched += 1
        if not obj_id:
            continue
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["table"] = table_name
        payload["relation_ids"] = {
            rel_id
            for rel_id in (
                normalize_hex32(payload.get("ID")),
                normalize_hex32(payload.get("CONFIG_ID")),
                normalize_hex32(payload.get("CR")),
                normalize_hex32(payload.get("TA")),
                normalize_hex32(payload.get("NCR")),
                normalize_hex32(payload.get("MASTER_SEND")),
                normalize_hex32(payload.get("REF_FILE_TRANSMISSION")),
            )
            if rel_id
        }
        payload["candidate_keys"] = set(
            _extract_candidate_keys(
                payload.get("ITEM_NUMBER"),
                payload.get("OPPOSITE_DOCUMENT_NUMBER"),
                payload.get("DISPATCH_NUM"),
                payload.get("CSS"),
                payload.get("THEME"),
                payload.get("REPLY_THEME"),
            )
        )
        payload["row_score"] = (
            _clean_text(payload.get("MODIFIED_ON")),
            _clean_text(payload.get("CREATED_ON")),
            _clean_text(payload.get("ITEM_NUMBER")),
        )
        by_id[obj_id] = payload
        if send_id in needed_send_ids:
            send_to_ids[send_id].add(obj_id)
    return {
        "table": table_name,
        "scanned": scanned,
        "matched": matched,
        "by_id": by_id,
        "send_to_ids": send_to_ids,
    }


def merge_child_scans(base: Dict[str, Any] | None, extra: Dict[str, Any]) -> Dict[str, Any]:
    if not base:
        return extra
    base["scanned"] += extra.get("scanned", 0)
    base["matched"] += extra.get("matched", 0)
    base["by_id"].update(extra.get("by_id", {}))
    for key, ids in extra.get("send_to_ids", {}).items():
        base["send_to_ids"][key].update(ids)
    return base


def scan_filetransmission_route(path: Path, needed_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    wanted = ["ID", "CONFIG_ID", "SEND_RECEIVE_DATA", "REF_FILE_TRANSMISSION", "CSS", "CONTENT", "THEME", "MODIFIED_ON"]
    idx = {name: mapping.get(name.lower(), -1) for name in wanted}
    by_id: Dict[str, Dict[str, Any]] = {}
    key_to_ids: DefaultDict[str, Set[str]] = defaultdict(set)
    scanned = 0
    matched = 0

    def extract_doc_keys(text: Any) -> List[str]:
        keys: List[str] = []
        for key in _extract_candidate_keys(text):
            if key in needed_keys and key not in keys:
                keys.append(key)
        return keys

    for row in iter_insert_rows(path):
        scanned += 1
        if mapping.get("is_current", -1) >= 0 and str(_safe_get(row, mapping.get("is_current", -1)) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        keys: List[str] = []
        for field in ("CSS", "CONTENT", "THEME"):
            for key in extract_doc_keys(_safe_get(row, idx[field])):
                if key not in keys:
                    keys.append(key)
        if not keys:
            continue
        matched += 1
        obj_id = normalize_hex32(_safe_get(row, idx["ID"]))
        if not obj_id:
            continue
        payload = {name: _safe_get(row, col) for name, col in idx.items() if col >= 0}
        payload["candidate_keys"] = set(_extract_candidate_keys(payload.get("CSS"), payload.get("CONTENT"), payload.get("THEME")))
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
        payload["row_score"] = (_clean_text(payload.get("MODIFIED_ON")), _clean_text(payload.get("CSS")))
        by_id[obj_id] = payload
        for key in keys:
            key_to_ids[key].add(obj_id)
    return {"scanned": scanned, "matched": matched, "by_id": by_id, "key_to_ids": key_to_ids}


def scan_objectreplylink(path: Path, needed_keys: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    scanned = 0
    matched = 0
    by_key: DefaultDict[str, Dict[str, Any]] = defaultdict(
        lambda: {"relation_ids": set(), "candidate_keys": set(), "source_types": set(), "reply_types": set()}
    )

    for row in iter_insert_rows(path):
        scanned += 1
        if mapping.get("is_current", -1) >= 0 and str(_safe_get(row, mapping.get("is_current", -1)) or "").strip().upper() not in {"", "1", "Y", "TRUE", "T"}:
            continue
        source_number = _clean_text(_safe_get(row, mapping.get("source_object_number", -1)))
        reply_number = _clean_text(_safe_get(row, mapping.get("reply_object_number", -1)))
        source_keys = set(_extract_candidate_keys(source_number))
        reply_keys = set(_extract_candidate_keys(reply_number))
        hit_keys = (source_keys | reply_keys) & needed_keys
        if not hit_keys:
            continue

        matched += 1
        relation_ids = {
            value
            for value in (
                normalize_hex32(_safe_get(row, mapping.get("source_object_id", -1))),
                normalize_hex32(_safe_get(row, mapping.get("reply_object_id", -1))),
            )
            if value
        }
        candidate_keys = source_keys | reply_keys
        source_type = _clean_text(_safe_get(row, mapping.get("source_object_type", -1)))
        reply_type = _clean_text(_safe_get(row, mapping.get("reply_object_type", -1)))
        for key in hit_keys:
            payload = by_key[key]
            payload["relation_ids"].update(relation_ids)
            payload["candidate_keys"].update(candidate_keys)
            if source_type:
                payload["source_types"].add(source_type)
            if reply_type:
                payload["reply_types"].add(reply_type)

    return {
        "scanned": scanned,
        "matched": matched,
        "by_key": {
            key: {
                "relation_ids": sorted(value["relation_ids"]),
                "candidate_keys": sorted(value["candidate_keys"]),
                "source_types": sorted(value["source_types"]),
                "reply_types": sorted(value["reply_types"]),
            }
            for key, value in by_key.items()
        },
    }


def scan_distribution(path: Path, target_ids: Set[str], needed_title_keys: Set[str]) -> Dict[str, Any]:
    groups: DefaultDict[str, Dict[str, Any]] = defaultdict(lambda: {"actors": [], "source_types": set(), "titles": []})
    statement_count = 0
    matched_count = 0
    matched_by_title_count = 0
    title_key_to_group_ids: DefaultDict[str, Set[str]] = defaultdict(set)
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
        row_id = normalize_hex32(row[DIST_IDX["id"]])
        title_keys = set(_extract_candidate_keys(_safe_get(row, DIST_IDX["bo_title"])))
        title_hits = title_keys & needed_title_keys
        if (not source_object_id or source_object_id not in target_ids) and not title_hits:
            continue
        group_id = source_object_id or row_id or f"ROW_{statement_count}"
        group = groups[group_id]
        sender = normalize_hex32(row[DIST_IDX["sender"]]) or _clean_text(row[DIST_IDX["sender"]])
        operator = normalize_hex32(row[DIST_IDX["operator"]]) or _clean_text(row[DIST_IDX["operator"]])
        if sender and sender not in group["actors"]:
            group["actors"].append(sender)
        if operator and operator not in group["actors"]:
            group["actors"].append(operator)
        source_type = _clean_text(row[DIST_IDX["source_type"]])
        if source_type:
            group["source_types"].add(source_type)
        title = _clean_text(_safe_get(row, DIST_IDX["bo_title"]))
        if title and title not in group["titles"]:
            group["titles"].append(title)
        for key in title_hits:
            title_key_to_group_ids[key].add(group_id)
        matched_count += 1
        if title_hits:
            matched_by_title_count += 1
    return {
        "statement_count": statement_count,
        "matched_count": matched_count,
        "matched_by_title_count": matched_by_title_count,
        "group_count": len(groups),
        "actors_by_group": {key: value["actors"] for key, value in groups.items()},
        "source_types_by_group": {key: sorted(value["source_types"]) for key, value in groups.items()},
        "titles_by_group": {key: value["titles"] for key, value in groups.items()},
        "title_key_to_group_ids": {key: sorted(value) for key, value in title_key_to_group_ids.items()},
    }


def _metric(rows: Sequence[Dict[str, Any]], excel_field: str, getter, matcher) -> Dict[str, Any]:
    target_rows = [row for row in rows if _clean_text(row.get(excel_field))]
    hit = 0
    by_project: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "hit": 0})
    by_type: DefaultDict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "hit": 0})
    for row in target_rows:
        by_project[row["project"]]["total"] += 1
        by_type[row["a_raw"]]["total"] += 1
        if matcher(row[excel_field], getter(row)):
            hit += 1
            by_project[row["project"]]["hit"] += 1
            by_type[row["a_raw"]]["hit"] += 1
    return {
        "total": len(target_rows),
        "hit": hit,
        "rate": _rate(hit, len(target_rows)),
        "by_project": {
            project: {"total": item["total"], "hit": item["hit"], "rate": _rate(item["hit"], item["total"])}
            for project, item in sorted(by_project.items())
        },
        "by_type": {
            a_type: {"total": item["total"], "hit": item["hit"], "rate": _rate(item["hit"], item["total"])}
            for a_type, item in sorted(by_type.items())
        },
    }


def run(excel_dir: Path, sql35_dir: Path, output_path: Path) -> Dict[str, Any]:
    rows = load_file6_rows(excel_dir)
    version_best = _filter_highest_version(rows)
    department_map = parse_department_tree(sql35_dir / "DEPARTMENT_20260305.sql")
    user_map = parse_user_map(sql35_dir / "USER_20260305.sql", department_map)
    roster_names = load_all_roster_names()

    int_rows = [row for row in rows if row["key_type"] == "int_key" and row["e_key"]]
    send_rows = [row for row in rows if row["key_type"] not in {"empty_key", "int_key"} and row["e_key"]]

    int_needed_keys = {row["e_key"] for row in int_rows}
    int_scan = scan_int_table(sql35_dir / "INTINTERFACEDOC_20260305.sql", int_needed_keys)
    needed_chain_ids = {
        payload.get("chain_id", "")
        for payload in int_scan["by_key"].values()
        if _clean_text(payload.get("chain_id"))
    }
    if needed_chain_ids:
        int_rescan = scan_int_table(sql35_dir / "INTINTERFACEDOC_20260305.sql", set(), needed_chain_ids=needed_chain_ids)
        int_scan = merge_int_scans(int_scan, int_rescan)
    send_scan = scan_send_table(sql35_dir / "SENDRECEIVEDATA_20260305.sql", {row["e_key"] for row in send_rows})

    needed_send_ids: Set[str] = set()
    for mapping_name in ("rec_to_ids", "send_to_ids"):
        for send_ids in send_scan[mapping_name].values():
            needed_send_ids.update(send_ids)

    child_tables: Dict[str, Dict[str, Any]] = {}
    child_item_keys = {row["e_key"] for row in send_rows}
    for table_name in SEND_SIDE_TABLES:
        sql_path = sql35_dir / f"{table_name}_20260305.sql"
        if not sql_path.exists():
            continue
        child_tables[table_name] = scan_child_table(sql_path, table_name, needed_send_ids, child_item_keys)

    for reply_table, parent_table in PARENT_TABLE_BY_REPLY.items():
        scan = child_tables.get(reply_table)
        if not scan:
            continue
        needed_parent_ids: Set[str] = set()
        for payload in scan["by_id"].values():
            for field_name in ("CR", "TA", "NCR"):
                rel_id = normalize_hex32(payload.get(field_name))
                if rel_id:
                    needed_parent_ids.add(rel_id)
        if not needed_parent_ids:
            continue
        sql_path = sql35_dir / f"{parent_table}_20260305.sql"
        if not sql_path.exists():
            continue
        rescan = scan_child_table(sql_path, parent_table, needed_send_ids, child_item_keys, needed_ids=needed_parent_ids)
        child_tables[parent_table] = merge_child_scans(child_tables.get(parent_table), rescan)

    ft_direct = scan_filetransmission_route(sql35_dir / "FILETRANSMISSION_20260305.sql", {row["e_key"] for row in send_rows})
    obj_reply = scan_objectreplylink(sql35_dir / "OBJECTREPLYLINK_20260305.sql", {row["e_key"] for row in send_rows})

    object_ids_for_dist: Set[str] = set(int_scan["by_id"].keys()) | set(send_scan["by_id"].keys()) | set(ft_direct["by_id"].keys())
    needed_title_keys: Set[str] = {row["e_key"] for row in rows if row["e_key"]}
    for payload in int_scan["by_key"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
        needed_title_keys.update(payload.get("candidate_keys", set()))
    for payload in send_scan["by_id"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
        needed_title_keys.update(payload.get("candidate_keys", set()))
    for payload in ft_direct["by_id"].values():
        object_ids_for_dist.update(payload.get("relation_ids", set()))
        needed_title_keys.update(payload.get("candidate_keys", set()))
    for payload in obj_reply["by_key"].values():
        object_ids_for_dist.update(payload.get("relation_ids", []))
        needed_title_keys.update(payload.get("candidate_keys", []))
    for scan in child_tables.values():
        object_ids_for_dist.update(scan["by_id"].keys())
        for payload in scan["by_id"].values():
            object_ids_for_dist.update(payload.get("relation_ids", set()))
            needed_title_keys.update(payload.get("candidate_keys", set()))

    dist_scan = scan_distribution(sql35_dir / "DISTRIBUTERECORD_20260305.sql", object_ids_for_dist, needed_title_keys)

    branch_counter = Counter()
    type_counter = Counter()
    matched_rows: List[Dict[str, Any]] = []
    unresolved_samples: List[Dict[str, Any]] = []

    for row in rows:
        row["version_best"] = (row["workbook"], row["excel_row"]) in version_best
        row["branch"] = "UNRESOLVED"
        row["send_id"] = ""
        row["int_id"] = ""
        row["title_keys"] = [row["e_key"]] if row["e_key"] else []
        row["group_ids"] = []
        row["dist_people_all"] = []
        row["dist_org_values"] = []
        row["dist_office_values"] = []
        row["dist_source_types"] = []
        row["doc_tables"] = []

        direct_ids: Set[str] = set()
        title_keys: Set[str] = set(row["title_keys"])

        if row["key_type"] == "int_key" and row["e_key"] in int_scan["by_key"]:
            payload = int_scan["by_key"][row["e_key"]]
            row["branch"] = "INT"
            row["int_id"] = normalize_hex32(payload.get("ID")) or ""
            direct_ids.update(payload.get("relation_ids", set()))
            title_keys.update(payload.get("candidate_keys", set()))
            related_ids = set(int_scan["ref_to_ids"].get(row["e_key"], set()))
            chain_id = normalize_hex32(payload.get("chain_id"))
            if chain_id:
                related_ids.update(int_scan["chain_to_ids"].get(chain_id, set()))
            if related_ids:
                row["doc_tables"].append("INT_CHAIN")
            for related_id in related_ids:
                related_payload = int_scan["by_id"].get(related_id, {})
                direct_ids.update(related_payload.get("relation_ids", set()))
                title_keys.update(related_payload.get("candidate_keys", set()))
        else:
            send_ids = set(send_scan["rec_to_ids"].get(row["e_key"], set())) | set(send_scan["send_to_ids"].get(row["e_key"], set()))
            send_id = _best_id(send_ids, send_scan["by_id"])
            ft_id = _best_id(ft_direct["key_to_ids"].get(row["e_key"], set()), ft_direct["by_id"])
            if not send_id and ft_id:
                linked_send = normalize_hex32(ft_direct["by_id"].get(ft_id, {}).get("SEND_RECEIVE_DATA"))
                if linked_send:
                    send_id = linked_send
            if send_id or ft_id:
                row["branch"] = "SEND"
                row["send_id"] = send_id
                if send_id:
                    send_payload = send_scan["by_id"].get(send_id, {})
                    direct_ids.update(send_payload.get("relation_ids", set()))
                    title_keys.update(send_payload.get("candidate_keys", set()))
                if ft_id:
                    row["doc_tables"].append("FILETRANSMISSION_ROUTE")
                    ft_payload = ft_direct["by_id"].get(ft_id, {})
                    direct_ids.update(ft_payload.get("relation_ids", set()))
                    title_keys.update(ft_payload.get("candidate_keys", set()))
                obj_reply_payload = obj_reply["by_key"].get(row["e_key"], {})
                if obj_reply_payload:
                    row["doc_tables"].append("OBJECTREPLYLINK")
                    direct_ids.update(obj_reply_payload.get("relation_ids", []))
                    title_keys.update(obj_reply_payload.get("candidate_keys", []))
                for table_name, scan in child_tables.items():
                    child_ids = list(scan["send_to_ids"].get(send_id, set())) if send_id else []
                    if child_ids:
                        row["doc_tables"].append(table_name)
                    for child_id in child_ids:
                        child_payload = scan["by_id"].get(child_id, {})
                        direct_ids.update(child_payload.get("relation_ids", set()))
                        title_keys.update(child_payload.get("candidate_keys", set()))
            elif row["e_key"] and len(unresolved_samples) < 60:
                unresolved_samples.append(
                    {
                        "project": row["project"],
                        "workbook": row["workbook"],
                        "excel_row": row["excel_row"],
                        "a_raw": row["a_raw"],
                        "e_raw": row["e_raw"],
                        "key_type": row["key_type"],
                    }
                )

        group_ids: Set[str] = set()
        for obj_id in direct_ids:
            if obj_id in dist_scan["actors_by_group"]:
                group_ids.add(obj_id)
        for key in title_keys:
            group_ids.update(dist_scan["title_key_to_group_ids"].get(key, []))

        actors: List[str] = []
        source_types: List[str] = []
        for group_id in sorted(group_ids):
            for actor in dist_scan["actors_by_group"].get(group_id, []):
                _add_unique(actors, actor)
            for source_type in dist_scan["source_types_by_group"].get(group_id, []):
                _add_unique(source_types, source_type)

        row["title_keys"] = sorted(title_keys)
        row["group_ids"] = sorted(group_ids)
        row["dist_source_types"] = source_types
        resolved = _resolve_distribution_entities(actors, user_map, department_map)
        row["dist_people_all"] = resolved["names"]
        row["dist_org_values"] = resolved["org_values"]
        row["dist_office_values"] = resolved["office_values"]

        branch_counter[row["branch"]] += 1
        type_counter[row["a_raw"]] += 1
        matched_rows.append(row)

    int_rows_matched = [row for row in matched_rows if row["branch"] == "INT"]
    send_rows_matched = [row for row in matched_rows if row["branch"] == "SEND"]
    version_rows = [row for row in matched_rows if row["version_best"] and row["branch"] in {"INT", "SEND"}]

    payload = {
        "inputs": {
            "excel_dir": str(excel_dir),
            "sql35_dir": str(sql35_dir),
        },
        "row_counts": {
            "all_rows": len(rows),
            "version_best_rows": len(version_best),
        },
        "route_summary": {
            "by_branch": dict(sorted(branch_counter.items())),
            "by_type": dict(sorted(type_counter.items())),
            "coverage": {
                "resolved": _rate(sum(1 for row in matched_rows if row["branch"] in {"INT", "SEND"}), len(matched_rows)),
                "int_branch": _rate(len(int_rows_matched), len(matched_rows)),
                "send_branch": _rate(len(send_rows_matched), len(matched_rows)),
            },
            "unresolved_samples": unresolved_samples,
        },
        "table_scans": {
            "INTINTERFACEDOC": {"rows_scanned": int_scan["scanned"], "rows_matched": int_scan["matched"]},
            "SENDRECEIVEDATA": {"rows_scanned": send_scan["scanned"], "rows_matched": send_scan["matched"]},
            "FILETRANSMISSION_ROUTE": {"rows_scanned": ft_direct["scanned"], "rows_matched": ft_direct["matched"]},
            "OBJECTREPLYLINK": {"rows_scanned": obj_reply["scanned"], "rows_matched": obj_reply["matched"]},
            "DISTRIBUTERECORD": {
                "statement_count": dist_scan["statement_count"],
                "matched_count": dist_scan["matched_count"],
                "matched_by_title_count": dist_scan["matched_by_title_count"],
                "group_count": dist_scan["group_count"],
            },
            "send_aux_tables": {
                table_name: {
                    "rows_scanned": scan["scanned"],
                    "rows_matched": scan["matched"],
                    "send_link_rows": sum(len(ids) for ids in scan["send_to_ids"].values()),
                }
                for table_name, scan in sorted(child_tables.items())
            },
        },
        "distribution_metrics": {
            "INT": {
                "X_all": _metric(
                    int_rows_matched,
                    "x_raw",
                    lambda row: ",".join(row["dist_people_all"]),
                    lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
                ),
                "V_all": _metric(int_rows_matched, "v_raw", lambda row: row["dist_org_values"], _org_match),
                "W_all": _metric(int_rows_matched, "w_raw", lambda row: row["dist_office_values"], _office_match),
            },
            "SEND": {
                "X_all": _metric(
                    send_rows_matched,
                    "x_raw",
                    lambda row: ",".join(row["dist_people_all"]),
                    lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
                ),
                "V_all": _metric(send_rows_matched, "v_raw", lambda row: row["dist_org_values"], _org_match),
                "W_all": _metric(send_rows_matched, "w_raw", lambda row: row["dist_office_values"], _office_match),
            },
            "version_best_overall": {
                "X_all": _metric(
                    version_rows,
                    "x_raw",
                    lambda row: ",".join(row["dist_people_all"]),
                    lambda excel, sql: _owner_match(excel, sql, user_map, roster_names),
                ),
                "V_all": _metric(version_rows, "v_raw", lambda row: row["dist_org_values"], _org_match),
                "W_all": _metric(version_rows, "w_raw", lambda row: row["dist_office_values"], _office_match),
            },
        },
        "samples": {
            "matched_examples": [
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "branch": row["branch"],
                    "title_keys": row["title_keys"][:8],
                    "group_ids": row["group_ids"][:8],
                    "dist_source_types": row["dist_source_types"][:6],
                    "dist_people_all": row["dist_people_all"][:20],
                    "dist_org_values": row["dist_org_values"][:12],
                    "dist_office_values": row["dist_office_values"][:12],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
                for row in version_rows
                if row["group_ids"] and (_clean_text(row["x_raw"]) or _clean_text(row["v_raw"]) or _clean_text(row["w_raw"]))
            ][:40],
            "no_distribution_examples": [
                {
                    "project": row["project"],
                    "workbook": row["workbook"],
                    "excel_row": row["excel_row"],
                    "a_raw": row["a_raw"],
                    "e_raw": row["e_raw"],
                    "branch": row["branch"],
                    "title_keys": row["title_keys"][:8],
                    "doc_tables": row["doc_tables"],
                    "x_raw": row["x_raw"],
                    "v_raw": row["v_raw"],
                    "w_raw": row["w_raw"],
                }
                for row in version_rows
                if not row["group_ids"] and (_clean_text(row["x_raw"]) or _clean_text(row["v_raw"]) or _clean_text(row["w_raw"]))
            ][:60],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe file6 X/V/W against full distribution-chain actors")
    parser.add_argument("--excel-dir", type=Path, default=Path("example/CIMS-SQL-3.5/EXCEL导出数据"))
    parser.add_argument("--sql35-dir", type=Path, default=Path("example/CIMS-SQL-3.5"))
    parser.add_argument("--output", type=Path, default=Path("tmp/file6_distribution_chain_probe_20260312.json"))
    args = parser.parse_args()
    payload = run(args.excel_dir, args.sql35_dir, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": payload["row_counts"]["all_rows"],
                "resolved_rate": payload["route_summary"]["coverage"]["resolved"],
                "send_x_rate": payload["distribution_metrics"]["SEND"]["X_all"]["rate"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
