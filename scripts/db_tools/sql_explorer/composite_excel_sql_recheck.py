"""Composite multi-project SQL/Excel recheck for files 1-4."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Set, Tuple

import pandas as pd

from .identity_resolver import normalize_hex32, resolve_owner_value
from .real_distribution_chain_probe import (
    _clean_text,
    _excel_col_index,
    _norm_drop_tail_digits,
    _norm_key,
    _safe_get,
    parse_link_table,
)
from .roster import normalize_owner_tokens
from .validate_cims_sql_dump import (
    iter_insert_rows,
    parse_create_columns,
    parse_department_map,
    parse_user_map,
)

WORKBOOK_PATTERNS = {
    "file1": re.compile(r"^(?P<project>\d{4})按项目导出IDI手册.*\.xlsx$"),
    "file2": re.compile(r"^内部接口信息单报表(?P<project>\d{4}).*\.xlsx$"),
    "file3": re.compile(r"^外部接口ICM报表(?P<project>\d{4}).*\.xlsx$"),
    "file4": re.compile(r"^外部接口单报表(?P<project>\d{4}).*\.xlsx$"),
}


def collect_workbooks(excel_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    result = {key: [] for key in WORKBOOK_PATTERNS}
    for path in sorted(excel_dir.glob("*.xlsx")):
        for file_type, pattern in WORKBOOK_PATTERNS.items():
            match = pattern.match(path.name)
            if match:
                result[file_type].append({"path": path, "project": match.group("project"), "name": path.name})
                break
    return result


def load_excel_file1(path: Path, project: str) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    col_a = _excel_col_index("A")
    col_r = _excel_col_index("R")
    rows = []
    for idx in range(len(df)):
        values = df.iloc[idx].tolist()
        item_raw = _safe_get(values, col_a)
        item_key = _norm_key(item_raw)
        if not item_key:
            continue
        rows.append(
            {
                "project": project,
                "workbook": path.name,
                "excel_row": idx + 2,
                "item_key": item_key,
                "owner_raw": _clean_text(_safe_get(values, col_r)),
            }
        )
    return rows


def load_excel_file3(path: Path, project: str) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    idx_c = _excel_col_index("C")
    idx_i = _excel_col_index("I")
    idx_l = _excel_col_index("L")
    idx_m = _excel_col_index("M")
    idx_al = _excel_col_index("AL")
    idx_ap = _excel_col_index("AP")
    rows = []
    for row_no in range(len(df)):
        values = df.iloc[row_no].tolist()
        item_key = _norm_key(_safe_get(values, idx_c))
        if not item_key:
            continue
        rows.append(
            {
                "project": project,
                "workbook": path.name,
                "excel_row": row_no + 2,
                "c_key": item_key,
                "i_raw": _clean_text(_safe_get(values, idx_i)),
                "l_raw": _safe_get(values, idx_l),
                "m_raw": _safe_get(values, idx_m),
                "al_raw": _clean_text(_safe_get(values, idx_al)),
                "ap_raw": _clean_text(_safe_get(values, idx_ap)),
            }
        )
    return rows


def load_excel_file2_full(path: Path, project: str) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    idx_a = _excel_col_index("A")
    idx_d = _excel_col_index("D")
    idx_m = _excel_col_index("M")
    idx_n = _excel_col_index("N")
    idx_r = _excel_col_index("R")
    idx_am = _excel_col_index("AM")
    rows = []
    for row_no in range(len(df)):
        values = df.iloc[row_no].tolist()
        a_key = _norm_key(_safe_get(values, idx_a))
        if not a_key:
            continue
        rows.append(
            {
                "project": project,
                "workbook": path.name,
                "excel_row": row_no + 2,
                "a_key": a_key,
                "d_key": _norm_key(_safe_get(values, idx_d)),
                "m_raw": _safe_get(values, idx_m),
                "n_raw": _safe_get(values, idx_n),
                "r_key": _norm_key(_safe_get(values, idx_r)),
                "owner_raw": _clean_text(_safe_get(values, idx_am)),
            }
        )
    return rows


def load_excel_file4_full(path: Path, project: str) -> List[Dict[str, Any]]:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    idx_e = _excel_col_index("E")
    idx_f = _excel_col_index("F")
    idx_p = _excel_col_index("P")
    idx_s = _excel_col_index("S")
    idx_v = _excel_col_index("V")
    idx_ah = _excel_col_index("AH")
    rows = []
    for row_no in range(len(df)):
        values = df.iloc[row_no].tolist()
        e_raw = _safe_get(values, idx_e)
        e_key = _norm_key(e_raw)
        if not e_key:
            continue
        rows.append(
            {
                "project": project,
                "workbook": path.name,
                "excel_row": row_no + 2,
                "e_key": e_key,
                "e_key_tail": _norm_drop_tail_digits(e_raw),
                "f_raw": _safe_get(values, idx_f),
                "p_raw": _clean_text(_safe_get(values, idx_p)),
                "s_raw": _safe_get(values, idx_s),
                "v_raw": _safe_get(values, idx_v),
                "owner_raw": _clean_text(_safe_get(values, idx_ah)),
            }
        )
    return rows


def norm_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return ""
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    if not text or text.lower() in {"", "nan", "none", "null", "nat"}:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if parsed is not pd.NaT and not pd.isna(parsed):
        return parsed.strftime("%Y-%m-%d")
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    return text[:10]


def dept_prefix(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    for sep in ("-", "(", "（", "/", " "):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
    idx = text.find("所")
    if idx >= 0:
        return text[: idx + 1]
    return text[:4]


def owner_match(excel_value: Any, sql_value: Any, user_map: Dict[str, Dict[str, Any]]) -> bool:
    excel_tokens = normalize_owner_tokens(excel_value)
    if not excel_tokens:
        return False
    sql_tokens = normalize_owner_tokens(sql_value)
    resolved = resolve_owner_value(sql_value, user_map)
    for name in resolved.get("resolved_names", []) or []:
        text = _clean_text(name)
        if text and text not in sql_tokens:
            sql_tokens.append(text)
    return bool(set(excel_tokens) & set(sql_tokens))


def build_current_map(
    path: Path,
    key_column: str,
    wanted_columns: Sequence[str],
    *,
    key_normalizer: Callable[[Any], str] = _norm_key,
    order_columns: Sequence[str] = ("MODIFIED_ON", "CREATED_ON", "RELEASE_DATE", "ITEM_NUMBER"),
) -> Dict[str, Dict[str, Any]]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    key_idx = mapping.get(key_column.lower(), -1)
    idx_map = {name: mapping.get(name.lower(), -1) for name in set(wanted_columns) | {key_column, "id", *order_columns}}
    rows: Dict[str, Dict[str, Any]] = {}
    for row in iter_insert_rows(path):
        if current_idx >= 0 and not str(_safe_get(row, current_idx) or "").strip().upper() in {"", "1", "Y", "TRUE", "T"}:
            continue
        key = key_normalizer(_safe_get(row, key_idx))
        if not key:
            continue
        payload = {name: _safe_get(row, idx) for name, idx in idx_map.items() if idx >= 0}
        score = tuple(_clean_text(payload.get(col)) for col in order_columns)
        if key not in rows or score >= tuple(_clean_text(rows[key].get(col)) for col in order_columns):
            rows[key] = payload
    return rows


def parse_int_rows(path: Path, needed_a: Set[str], needed_d: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_id = mapping.get("id", -1)
    idx_item = mapping.get("item_number", -1)
    idx_ref = mapping.get("ref_item_number", -1)
    idx_map = {name: mapping.get(name.lower(), -1) for name in ["REPLY_DEADLINE", "ANSWER_DATE", "MODIFIED_BY_ID", "CREATED_BY_ID"]}
    by_id: Dict[str, Dict[str, Any]] = {}
    item_to_ids: Dict[str, Set[str]] = {}
    pair_to_ids: Dict[Tuple[str, str], Set[str]] = {}
    for row in iter_insert_rows(path):
        if current_idx >= 0 and not str(_safe_get(row, current_idx) or "").strip().upper() in {"", "1", "Y", "TRUE", "T"}:
            continue
        item_key = _norm_key(_safe_get(row, idx_item))
        ref_key = _norm_key(_safe_get(row, idx_ref))
        if item_key not in needed_a and ref_key not in needed_d:
            continue
        obj_id = normalize_hex32(_safe_get(row, idx_id))
        if not obj_id:
            continue
        by_id[obj_id] = {name: _safe_get(row, idx) for name, idx in idx_map.items() if idx >= 0}
        if item_key in needed_a:
            item_to_ids.setdefault(item_key, set()).add(obj_id)
        if item_key in needed_a and ref_key in needed_d:
            pair_to_ids.setdefault((item_key, ref_key), set()).add(obj_id)
    return {"by_id": by_id, "item_to_ids": item_to_ids, "pair_to_ids": pair_to_ids}


def parse_send_rows(path: Path, needed_e: Set[str], needed_tail: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_id = mapping.get("id", -1)
    idx_send = mapping.get("letter_send_no", -1)
    idx_rec = mapping.get("corresp_letter_rec_no", -1)
    idx_map = {name: mapping.get(name.lower(), -1) for name in ["SEND_RECV_LETT_DATE", "REPLY_DEADLINE", "CREATED_BY_ID", "MODIFIED_BY_ID"]}
    by_id: Dict[str, Dict[str, Any]] = {}
    send_exact: Dict[str, Set[str]] = {}
    rec_exact: Dict[str, Set[str]] = {}
    send_tail: Dict[str, Set[str]] = {}
    for row in iter_insert_rows(path):
        if current_idx >= 0 and not str(_safe_get(row, current_idx) or "").strip().upper() in {"", "1", "Y", "TRUE", "T"}:
            continue
        send_key = _norm_key(_safe_get(row, idx_send))
        rec_key = _norm_key(_safe_get(row, idx_rec))
        send_tail_key = _norm_drop_tail_digits(_safe_get(row, idx_send))
        if send_key not in needed_e and rec_key not in needed_e and send_tail_key not in needed_tail:
            continue
        obj_id = normalize_hex32(_safe_get(row, idx_id))
        if not obj_id:
            continue
        by_id[obj_id] = {name: _safe_get(row, idx) for name, idx in idx_map.items() if idx >= 0}
        if send_key in needed_e:
            send_exact.setdefault(send_key, set()).add(obj_id)
        if rec_key in needed_e:
            rec_exact.setdefault(rec_key, set()).add(obj_id)
        if send_tail_key in needed_tail:
            send_tail.setdefault(send_tail_key, set()).add(obj_id)
    return {"by_id": by_id, "send_exact": send_exact, "rec_exact": rec_exact, "send_tail": send_tail}


def parse_child_rows(path: Path, needed_send_ids: Set[str]) -> Dict[str, Any]:
    columns = parse_create_columns(path)
    mapping = {name.lower(): idx for idx, name in enumerate(columns)}
    current_idx = mapping.get("is_current", -1)
    idx_id = mapping.get("id", -1)
    idx_send = mapping.get("send_receive_data", -1)
    idx_map = {name: mapping.get(name.lower(), -1) for name in ["RELEASE_DATE", "CREATED_ON", "CREATED_BY_ID", "MODIFIED_BY_ID", "ITEM_NUMBER", "REV"]}
    by_id: Dict[str, Dict[str, Any]] = {}
    send_to_ids: Dict[str, Set[str]] = {}
    for row in iter_insert_rows(path):
        if current_idx >= 0 and not str(_safe_get(row, current_idx) or "").strip().upper() in {"", "1", "Y", "TRUE", "T"}:
            continue
        send_id = normalize_hex32(_safe_get(row, idx_send))
        if not send_id or send_id not in needed_send_ids:
            continue
        obj_id = normalize_hex32(_safe_get(row, idx_id))
        if not obj_id:
            continue
        payload = {name: _safe_get(row, idx) for name, idx in idx_map.items() if idx >= 0}
        score = tuple(_clean_text(payload.get(col)) for col in ("RELEASE_DATE", "CREATED_ON", "ITEM_NUMBER", "REV"))
        if obj_id not in by_id or score >= tuple(_clean_text(by_id[obj_id].get(col)) for col in ("RELEASE_DATE", "CREATED_ON", "ITEM_NUMBER", "REV")):
            by_id[obj_id] = payload
        send_to_ids.setdefault(send_id, set()).add(obj_id)
    return {"by_id": by_id, "send_to_ids": send_to_ids}


def best_child_id(child_ids: Iterable[str], child_rows: Dict[str, Dict[str, Any]]) -> str:
    chosen = ""
    best_score: Tuple[str, ...] = ()
    for child_id in sorted(set(child_ids)):
        score = tuple(_clean_text(child_rows.get(child_id, {}).get(col)) for col in ("RELEASE_DATE", "CREATED_ON", "ITEM_NUMBER", "REV"))
        if not chosen or score >= best_score:
            chosen = child_id
            best_score = score
    return chosen


def prefilter_sql(sql_path: Path, tokens: Set[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    token_path = out_path.with_suffix(".tokens.txt")
    token_path.write_text("\n".join(sorted(tokens)), encoding="utf-8")
    with out_path.open("wb") as stream:
        subprocess.run(["rg", "-F", "-f", str(token_path), str(sql_path)], stdout=stream, stderr=subprocess.PIPE, check=False)


def metric(rows: Sequence[Dict[str, Any]], flag: str) -> Dict[str, Any]:
    by_project = defaultdict(lambda: {"total": 0, "hit": 0})
    for row in rows:
        by_project[row["project"]]["total"] += 1
        if row.get(flag):
            by_project[row["project"]]["hit"] += 1
    total = len(rows)
    hit = sum(1 for row in rows if row.get(flag))
    return {
        "total": total,
        "hit": hit,
        "rate": round(hit / total, 6) if total else 0.0,
        "by_project": {
            key: {"total": data["total"], "hit": data["hit"], "rate": round(data["hit"] / data["total"], 6) if data["total"] else 0.0}
            for key, data in sorted(by_project.items())
        },
    }


def run(excel_dir: Path, sql35_dir: Path, sql37_dir: Path, output_path: Path, temp_dir: Path) -> Dict[str, Any]:
    workbooks = collect_workbooks(excel_dir)
    user_map = parse_user_map(sql35_dir / "USER_20260305.sql", parse_department_map(sql35_dir / "DEPARTMENT_20260305.sql"))

    file1_rows = [row for wb in workbooks["file1"] for row in load_excel_file1(wb["path"], wb["project"])]
    file2_rows = [row for wb in workbooks["file2"] for row in load_excel_file2_full(wb["path"], wb["project"])]
    file3_rows = [row for wb in workbooks["file3"] for row in load_excel_file3(wb["path"], wb["project"])]
    file4_rows = [row for wb in workbooks["file4"] for row in load_excel_file4_full(wb["path"], wb["project"])]

    idi_by_item = build_current_map(sql35_dir / "IDIACP1000_20260305.sql", "ITEM_NUMBER", ["DEPART_USER"])
    idi_by_id = build_current_map(sql35_dir / "IDIACP1000_20260305.sql", "id", ["ITEM_NUMBER", "DEPART_USER"], key_normalizer=lambda value: normalize_hex32(value) or "")
    icm_by_item = build_current_map(
        sql35_dir / "ICMACP1000_20260305.sql",
        "ITEM_NUMBER",
        ["RESP_DEPART", "DEPART_USER", "RELEASE_PARTY", "PRE_FORECAST_DATE", "FINAL_FORECAST_DATE"],
    )
    int_data = parse_int_rows(sql35_dir / "INTINTERFACEDOC_20260305.sql", {r["a_key"] for r in file2_rows}, {r["d_key"] for r in file2_rows})
    bridge = build_current_map(
        sql35_dir / "INTINTERFACEDOCIDIACP1000_20260305.sql",
        "id",
        ["SOURCE_ID", "RELATED_ID"],
        key_normalizer=lambda value: normalize_hex32(value) or "",
        order_columns=("MODIFIED_ON", "CREATED_ON"),
    )
    bridge_by_source: Dict[str, Set[str]] = defaultdict(set)
    for payload in bridge.values():
        source_id = normalize_hex32(payload.get("SOURCE_ID"))
        related_id = normalize_hex32(payload.get("RELATED_ID"))
        if source_id and related_id:
            bridge_by_source[source_id].add(related_id)

    send_data = parse_send_rows(sql35_dir / "SENDRECEIVEDATA_20260305.sql", {r["e_key"] for r in file4_rows}, {r["e_key_tail"] for r in file4_rows})
    needed_send_ids = {sid for ids in send_data["send_exact"].values() for sid in ids} | {sid for ids in send_data["send_tail"].values() for sid in ids}
    iics = parse_child_rows(sql35_dir / "IICS_20260305.sql", needed_send_ids)
    iitf = parse_child_rows(sql35_dir / "IITF_20260305.sql", needed_send_ids)
    iitf_by_item = build_current_map(sql35_dir / "IITF_20260305.sql", "ITEM_NUMBER", ["SEND_RECEIVE_DATA"])

    for row in file1_rows:
        idi = idi_by_item.get(row["item_key"], {})
        row["hit_item"] = bool(idi)
        row["sql_owner"] = idi.get("DEPART_USER")

    matched_int_ids: Set[str] = set()
    for row in file2_rows:
        pair_ids = int_data["pair_to_ids"].get((row["a_key"], row["d_key"]), set())
        row["hit_a"] = bool(int_data["item_to_ids"].get(row["a_key"], set()))
        row["hit_pair"] = bool(pair_ids)
        row["int_id"] = sorted(pair_ids)[0] if pair_ids else ""
        if row["int_id"]:
            matched_int_ids.add(row["int_id"])
        row["hit_r_bridge"] = any(_norm_key(idi_by_id.get(rel_id, {}).get("ITEM_NUMBER")) == row["r_key"] for rel_id in bridge_by_source.get(row["int_id"], set()))
        row["sql_m"] = int_data["by_id"].get(row["int_id"], {}).get("REPLY_DEADLINE")
        row["sql_n"] = int_data["by_id"].get(row["int_id"], {}).get("ANSWER_DATE")

    matched_iitf_ids: Set[str] = set()
    matched_iics_ids: Set[str] = set()
    for row in file3_rows:
        icm = icm_by_item.get(row["c_key"], {})
        row["hit_item"] = bool(icm)
        row["hit_al"] = dept_prefix(row["al_raw"]) == dept_prefix(icm.get("RESP_DEPART"))
        row["hit_ap"] = owner_match(row["ap_raw"], icm.get("DEPART_USER"), user_map) if row["ap_raw"] else False
        row["hit_i"] = _norm_key(row["i_raw"]) == _norm_key(icm.get("RELEASE_PARTY"))
        row["hit_l"] = norm_date(row["l_raw"]) == norm_date(icm.get("PRE_FORECAST_DATE"))
        row["hit_m"] = norm_date(row["m_raw"]) == norm_date(icm.get("FINAL_FORECAST_DATE"))

    for row in file4_rows:
        exact_ids = send_data["send_exact"].get(row["e_key"], set())
        row["hit_e_direct_iitf"] = bool(iitf_by_item.get(row["e_key"]))
        row["hit_e_send"] = bool(exact_ids)
        row["hit_e_rec"] = bool(send_data["rec_exact"].get(row["e_key"], set()))
        send_ids = exact_ids or send_data["send_tail"].get(row["e_key_tail"], set())
        row["hit_e_send_any"] = bool(send_ids)
        row["send_id"] = sorted(send_ids)[0] if send_ids else ""
        row["tail_extra"] = bool(send_ids) and not bool(exact_ids)
        row["hit_f_send"] = any(
            norm_date(row.get("f_raw")) == norm_date(send_data["by_id"].get(send_id, {}).get("SEND_RECV_LETT_DATE"))
            for send_id in send_ids
        )
        row["hit_s"] = any(
            norm_date(row.get("s_raw")) == norm_date(send_data["by_id"].get(send_id, {}).get("REPLY_DEADLINE"))
            for send_id in send_ids
        )
        iitf_ids = set()
        iics_ids = set()
        for send_id in send_ids:
            iitf_ids.update(iitf["send_to_ids"].get(send_id, set()))
            iics_ids.update(iics["send_to_ids"].get(send_id, set()))
        row["hit_iitf"] = bool(iitf_ids)
        row["hit_iics"] = bool(iics_ids)
        row["iitf_id"] = best_child_id(iitf_ids, iitf["by_id"])
        row["iics_id"] = best_child_id(iics_ids, iics["by_id"])
        matched_iitf_ids.update(iitf_ids)
        matched_iics_ids.update(iics_ids)
        row["hit_f_iitf"] = any(
            norm_date(row.get("f_raw")) == norm_date(iitf["by_id"].get(child_id, {}).get("RELEASE_DATE"))
            for child_id in iitf_ids
        )
        row["hit_v"] = any(
            norm_date(row.get("v_raw")) == norm_date(iics["by_id"].get(child_id, {}).get("RELEASE_DATE"))
            for child_id in iics_ids
        )
        row["sql_owner_iics"] = iics["by_id"].get(row["iics_id"], {}).get("CREATED_BY_ID")

    temp_dir.mkdir(parents=True, exist_ok=True)
    dist_int = parse_link_table("DISTRIBUTERECORD", sql35_dir, matched_int_ids, ["SOURCE_OBJECT_ID"], ["OPERATOR", "SENDER", "CREATED_BY_ID", "MODIFIED_BY_ID"])
    dist_iitf = parse_link_table("DISTRIBUTERECORD", sql35_dir, matched_iitf_ids, ["SOURCE_OBJECT_ID"], ["OPERATOR", "SENDER", "CREATED_BY_ID", "MODIFIED_BY_ID"])
    prefilter_sql(sql37_dir / "WORKFLOWPROCESSESBIND_20260307.sql", matched_int_ids | matched_iics_ids | matched_iitf_ids, temp_dir / "WORKFLOWPROCESSESBIND.sql")
    prefilter_sql(sql37_dir / "USERVOTERECORD_20260307.sql", matched_int_ids | matched_iics_ids | matched_iitf_ids, temp_dir / "USERVOTERECORD.sql")
    wf_int = parse_link_table("WORKFLOWPROCESSESBIND", temp_dir, matched_int_ids, ["SOURCE_OBJECT_ID"], ["CREATED_BY_ID", "MODIFIED_BY_ID", "SOURCE_TYPE"])
    wf_iics = parse_link_table("WORKFLOWPROCESSESBIND", temp_dir, matched_iics_ids, ["SOURCE_OBJECT_ID"], ["CREATED_BY_ID", "MODIFIED_BY_ID", "SOURCE_TYPE"])
    wf_iitf = parse_link_table("WORKFLOWPROCESSESBIND", temp_dir, matched_iitf_ids, ["SOURCE_OBJECT_ID"], ["CREATED_BY_ID", "MODIFIED_BY_ID", "SOURCE_TYPE"])
    vote_int = parse_link_table("USERVOTERECORD", temp_dir, matched_int_ids, ["SOURCE_OBJECT_ID"], ["OPERATOR", "ACTIVITY_NAME", "OPERATION_TIME"])
    vote_iics = parse_link_table("USERVOTERECORD", temp_dir, matched_iics_ids, ["SOURCE_OBJECT_ID"], ["OPERATOR", "ACTIVITY_NAME", "OPERATION_TIME"])
    vote_iitf = parse_link_table("USERVOTERECORD", temp_dir, matched_iitf_ids, ["SOURCE_OBJECT_ID"], ["OPERATOR", "ACTIVITY_NAME", "OPERATION_TIME"])

    for row in file4_rows:
        row["sql_owner_dist"] = (dist_iitf["owner_by_source"].get(row.get("iitf_id", ""), {}) or {}).get("OPERATOR")
        row["sql_owner_wf"] = (wf_iics["owner_by_source"].get(row.get("iics_id", ""), {}) or {}).get("CREATED_BY_ID")
        row["sql_owner_vote"] = (vote_iics["owner_by_source"].get(row.get("iics_id", ""), {}) or {}).get("OPERATOR")
        row["hit_owner_iics"] = owner_match(row.get("owner_raw"), row.get("sql_owner_iics"), user_map) if row.get("owner_raw") else False
        row["hit_owner_dist"] = owner_match(row.get("owner_raw"), row.get("sql_owner_dist"), user_map) if row.get("owner_raw") else False
        row["hit_owner_wf"] = owner_match(row.get("owner_raw"), row.get("sql_owner_wf"), user_map) if row.get("owner_raw") else False
        row["hit_owner_vote"] = owner_match(row.get("owner_raw"), row.get("sql_owner_vote"), user_map) if row.get("owner_raw") else False

    for row in file1_rows:
        row["hit_owner"] = owner_match(row.get("owner_raw"), row.get("sql_owner"), user_map) if row.get("owner_raw") else False

    payload = {
        "inputs": {"excel_dir": str(excel_dir), "sql35_dir": str(sql35_dir), "sql37_dir": str(sql37_dir)},
        "workbook_counts": {key: len(value) for key, value in workbooks.items()},
        "file1": {
            "rows": len(file1_rows),
            "a_to_item": metric(file1_rows, "hit_item"),
            "r_to_depart_user": metric([row for row in file1_rows if row.get("owner_raw")], "hit_owner"),
        },
        "file2": {
            "rows": len(file2_rows),
            "am_non_empty_rows": sum(1 for row in file2_rows if row.get("owner_raw")),
            "a_to_item": metric(file2_rows, "hit_a"),
            "pair_to_int": metric(file2_rows, "hit_pair"),
            "r_via_bridge": metric([row for row in file2_rows if row.get("r_key")], "hit_r_bridge"),
            "m_to_reply_deadline": metric([dict(row, hit_tmp=norm_date(row.get("m_raw")) == norm_date(row.get("sql_m"))) for row in file2_rows if norm_date(row.get("m_raw"))], "hit_tmp"),
            "n_to_answer_date": metric([dict(row, hit_tmp=norm_date(row.get("n_raw")) == norm_date(row.get("sql_n"))) for row in file2_rows if norm_date(row.get("n_raw"))], "hit_tmp"),
            "int_to_distributionrecord": {"total": len(matched_int_ids), "hit": len(dist_int["matched_source_ids"]), "rate": round(len(dist_int["matched_source_ids"]) / len(matched_int_ids), 6) if matched_int_ids else 0.0},
            "int_to_workflow": {"total": len(matched_int_ids), "hit": len(wf_int["matched_source_ids"]), "rate": round(len(wf_int["matched_source_ids"]) / len(matched_int_ids), 6) if matched_int_ids else 0.0},
            "int_to_vote": {"total": len(matched_int_ids), "hit": len(vote_int["matched_source_ids"]), "rate": round(len(vote_int["matched_source_ids"]) / len(matched_int_ids), 6) if matched_int_ids else 0.0},
        },
        "file3": {
            "rows": len(file3_rows),
            "c_to_item": metric(file3_rows, "hit_item"),
            "al_to_resp_depart": metric([row for row in file3_rows if dept_prefix(row.get("al_raw"))], "hit_al"),
            "ap_to_depart_user": metric([row for row in file3_rows if row.get("ap_raw")], "hit_ap"),
            "i_to_release_party": metric([row for row in file3_rows if row.get("i_raw")], "hit_i"),
            "l_to_pre_forecast": metric([row for row in file3_rows if norm_date(row.get("l_raw"))], "hit_l"),
            "m_to_final_forecast": metric([row for row in file3_rows if norm_date(row.get("m_raw"))], "hit_m"),
        },
        "file4": {
            "rows": len(file4_rows),
            "ah_non_empty_rows": sum(1 for row in file4_rows if row.get("owner_raw")),
            "p_non_empty_rows": sum(1 for row in file4_rows if row.get("p_raw")),
            "e_to_iitf_direct": metric(file4_rows, "hit_e_direct_iitf"),
            "e_to_send": metric(file4_rows, "hit_e_send"),
            "e_to_rec": metric(file4_rows, "hit_e_rec"),
            "e_to_send_any": metric(file4_rows, "hit_e_send_any"),
            "tail_extra": metric([row for row in file4_rows if row.get("tail_extra")], "tail_extra"),
            "send_to_iitf": metric(file4_rows, "hit_iitf"),
            "send_to_iics": metric(file4_rows, "hit_iics"),
            "f_to_send_date": metric([row for row in file4_rows if norm_date(row.get("f_raw"))], "hit_f_send"),
            "f_to_iitf_release_date": metric([row for row in file4_rows if norm_date(row.get("f_raw"))], "hit_f_iitf"),
            "s_to_reply_deadline": metric([row for row in file4_rows if norm_date(row.get("s_raw"))], "hit_s"),
            "v_to_iics_release_date": metric([row for row in file4_rows if norm_date(row.get("v_raw"))], "hit_v"),
            "iitf_to_distributionrecord": {"total": len(matched_iitf_ids), "hit": len(dist_iitf["matched_source_ids"]), "rate": round(len(dist_iitf["matched_source_ids"]) / len(matched_iitf_ids), 6) if matched_iitf_ids else 0.0},
            "iics_to_workflow": {"total": len(matched_iics_ids), "hit": len(wf_iics["matched_source_ids"]), "rate": round(len(wf_iics["matched_source_ids"]) / len(matched_iics_ids), 6) if matched_iics_ids else 0.0},
            "iics_to_vote": {"total": len(matched_iics_ids), "hit": len(vote_iics["matched_source_ids"]), "rate": round(len(vote_iics["matched_source_ids"]) / len(matched_iics_ids), 6) if matched_iics_ids else 0.0},
            "iitf_to_workflow": {"total": len(matched_iitf_ids), "hit": len(wf_iitf["matched_source_ids"]), "rate": round(len(wf_iitf["matched_source_ids"]) / len(matched_iitf_ids), 6) if matched_iitf_ids else 0.0},
            "iitf_to_vote": {"total": len(matched_iitf_ids), "hit": len(vote_iitf["matched_source_ids"]), "rate": round(len(vote_iitf["matched_source_ids"]) / len(matched_iitf_ids), 6) if matched_iitf_ids else 0.0},
            "owner_candidates": {
                "iics_created_by": metric([row for row in file4_rows if row.get("owner_raw")], "hit_owner_iics"),
                "iitf_distribution_operator": metric([row for row in file4_rows if row.get("owner_raw")], "hit_owner_dist"),
                "iics_workflow_created_by": metric([row for row in file4_rows if row.get("owner_raw")], "hit_owner_wf"),
                "iics_vote_operator": metric([row for row in file4_rows if row.get("owner_raw")], "hit_owner_vote"),
            },
        },
        "word_rules": {
            "file2": [
                "A is transmission sheet number, R is IDI number, owner must come from distribution info, N is reply-page submit date.",
            ],
            "file4": [
                "E is reached through interface-sheet page, F is sheet publish date, S is reply deadline, V is IICS publish date, P remains unresolved in the authoritative Word doc.",
            ],
            "file3": [
                "AP is internal compiler; blank AP falls back to admin reminder logic outside CIMS.",
            ],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Composite recheck for files 1-4")
    parser.add_argument("--excel-dir", required=True)
    parser.add_argument("--sql35-dir", required=True)
    parser.add_argument("--sql37-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--temp-dir", required=True)
    args = parser.parse_args()
    run(Path(args.excel_dir), Path(args.sql35_dir), Path(args.sql37_dir), Path(args.output), Path(args.temp_dir))


if __name__ == "__main__":
    main()
