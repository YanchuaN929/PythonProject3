"""Discovery engine for time/owner candidate columns."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .profiling import profile_records
from .roster import validate_owner_values

TIME_KEYWORDS = (
    "time",
    "date",
    "deadline",
    "due",
    "submit",
    "start",
    "close",
    "finish",
    "forecast",
    "schedule",
    "reply",
    "answer",
    "swap",
    "author_date",
    "meeting_date",
    "send_date",
    "receive_date",
    "created_on",
    "modified_on",
    "plan",
    "expected",
    "接口时间",
    "时间",
    "日期",
    "期限",
    "计划",
)

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
    "dept_user",
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

FILE_TYPE_TABLE_HINTS = {
    "1": ("idiacp1000", "idiinterfacereopeninfolink", "intinterfacedocidiacp1000"),
    "2": ("intinterfacedoc", "intinterfacedocidiacp1000", "internalminutes"),
    "3": ("icmacp1000", "icminterfacereopeninfolink", "iics", "iitf"),
    "4": ("iitf", "iics", "icmacp1000"),
    "6": (
        "sendreceivedata",
        "ta",
        "tareply",
        "telefax",
        "memorandum",
        "internalminutes",
        "externalminutes",
        "filetransmission",
    ),
}


@dataclass
class Candidate:
    """Candidate column with score/evidence."""

    table_ref: str
    column: str
    score: float
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_ref": self.table_ref,
            "column": self.column,
            "score": round(self.score, 6),
            "evidence": self.evidence,
        }


def _keyword_score(name: str, keywords: Sequence[str]) -> float:
    lowered = name.lower()
    hit = 0
    for keyword in keywords:
        if keyword.lower() in lowered:
            hit += 1
    return min(1.0, 0.35 * hit)


def _calc_owner_metrics(
    values: Iterable[Any],
    roster_names: Set[str],
    user_id_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return validate_owner_values(values, roster_names, user_id_map=user_id_map)


def _time_score(column_name: str, profile: Dict[str, Any]) -> float:
    score = 0.0
    score += 0.65 * float(profile.get("date_parse_rate", 0.0))
    score += 0.20 * _keyword_score(column_name, TIME_KEYWORDS)
    score += 0.10 * (1.0 - min(1.0, float(profile.get("null_rate", 1.0))))
    score += 0.05 * min(1.0, float(profile.get("unique_rate", 0.0)))
    return max(0.0, min(1.0, score))


def _owner_score(
    column_name: str,
    profile: Dict[str, Any],
    owner_metrics: Dict[str, Any],
) -> float:
    keyword_score = _keyword_score(column_name, OWNER_KEYWORDS)
    roster_match_rate = float(owner_metrics.get("name_in_roster_rate", 0.0))
    id_resolved_rate = float(owner_metrics.get("id_resolved_rate", 0.0))
    resolved_name_rate = float(owner_metrics.get("resolved_name_rate", 0.0))
    resolved_dept_rate = float(owner_metrics.get("resolved_dept_rate", 0.0))
    id_token_count = float(owner_metrics.get("id_token_count", 0.0))
    keyword_gate = 0.4 + 0.6 * keyword_score

    score = 0.0
    score += 0.28 * keyword_score
    score += 0.18 * float(profile.get("chinese_name_rate", 0.0))
    score += 0.24 * roster_match_rate
    score += 0.20 * id_resolved_rate * keyword_gate
    score += 0.07 * resolved_name_rate * keyword_gate
    score += 0.03 * resolved_dept_rate * keyword_gate
    score += 0.05 * float(profile.get("multi_owner_rate", 0.0))

    avg_length = float(profile.get("avg_length", 0.0))
    unique_rate = float(profile.get("unique_rate", 0.0))
    if avg_length > 40 and keyword_score < 0.35 and id_resolved_rate < 0.2:
        score -= 0.18
    if avg_length > 120:
        score -= 0.12
    if id_token_count > 1000:
        score -= 0.12
    if (
        unique_rate > 0.98
        and keyword_score < 0.01
        and roster_match_rate < 0.01
        and id_resolved_rate < 0.01
    ):
        score -= 0.08
    return max(0.0, min(1.0, score))


def discover_candidates(
    sampled_tables: List[Dict[str, Any]],
    roster_names: Optional[Set[str]] = None,
    user_id_map: Optional[Dict[str, Dict[str, Any]]] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    """Discover global time/owner candidate columns from sampled tables."""

    roster_names = roster_names or set()
    user_id_map = user_id_map or {}
    time_candidates: List[Candidate] = []
    owner_candidates: List[Candidate] = []
    table_profiles: List[Dict[str, Any]] = []

    for table_data in sampled_tables:
        table_ref = str(table_data.get("table_ref", ""))
        records = table_data.get("records", []) or []
        profiles = profile_records(records)
        table_profiles.append({"table_ref": table_ref, "profiles": profiles})

        for col_name, profile in profiles.items():
            values = [record.get(col_name) for record in records]
            owner_metrics = _calc_owner_metrics(values, roster_names, user_id_map)

            t_score = _time_score(col_name, profile)
            o_score = _owner_score(col_name, profile, owner_metrics)

            t_evidence = {
                "date_parse_rate": profile.get("date_parse_rate", 0.0),
                "null_rate": profile.get("null_rate", 1.0),
                "keyword_score": _keyword_score(col_name, TIME_KEYWORDS),
                "top_values": profile.get("top_values", [])[:3],
            }
            o_evidence = {
                "chinese_name_rate": profile.get("chinese_name_rate", 0.0),
                "roster_match_rate": owner_metrics.get("name_in_roster_rate", 0.0),
                "id_resolved_rate": owner_metrics.get("id_resolved_rate", 0.0),
                "resolved_name_rate": owner_metrics.get("resolved_name_rate", 0.0),
                "resolved_dept_rate": owner_metrics.get("resolved_dept_rate", 0.0),
                "multi_owner_rate": profile.get("multi_owner_rate", 0.0),
                "keyword_score": _keyword_score(col_name, OWNER_KEYWORDS),
                "resolved_user_examples": owner_metrics.get("resolved_user_examples", [])[:3],
                "unresolved_id_examples": owner_metrics.get("unresolved_id_examples", [])[:3],
                "top_values": profile.get("top_values", [])[:3],
            }

            time_candidates.append(Candidate(table_ref, col_name, t_score, t_evidence))
            owner_candidates.append(Candidate(table_ref, col_name, o_score, o_evidence))

    time_candidates.sort(key=lambda item: item.score, reverse=True)
    owner_candidates.sort(key=lambda item: item.score, reverse=True)

    return {
        "global_time_candidates": [item.to_dict() for item in time_candidates[:top_n]],
        "global_owner_candidates": [item.to_dict() for item in owner_candidates[:top_n]],
        "table_profiles": table_profiles,
        "file_type_candidates": _project_file_type_candidates(
            time_candidates, owner_candidates, top_n
        ),
    }


def _project_file_type_candidates(
    time_candidates: List[Candidate], owner_candidates: List[Candidate], top_n: int
) -> Dict[str, Any]:
    """Project global candidates to file-type scoped results by table-name hints."""

    result: Dict[str, Any] = {}
    for file_type, hints in FILE_TYPE_TABLE_HINTS.items():
        filtered_time = _filter_by_hints(time_candidates, hints)
        filtered_owner = _filter_by_hints(owner_candidates, hints)

        time_rows = filtered_time[:top_n] if filtered_time else time_candidates[:top_n]
        owner_rows = filtered_owner[:top_n] if filtered_owner else owner_candidates[:top_n]

        result[file_type] = {
            "time_candidates": [item.to_dict() for item in time_rows],
            "owner_candidates": [item.to_dict() for item in owner_rows],
            "hint_matched": bool(filtered_time or filtered_owner),
            "hints": list(hints),
        }
    return result


def _filter_by_hints(candidates: List[Candidate], hints: Sequence[str]) -> List[Candidate]:
    rows: List[Candidate] = []
    for item in candidates:
        matched = any(_table_hint_matched(item.table_ref, hint) for hint in hints)
        if matched:
            rows.append(item)
    rows.sort(key=lambda c: c.score + math.log1p(len(c.table_ref)) * 0.001, reverse=True)
    return rows


def _table_hint_matched(table_ref: str, hint: str) -> bool:
    """Match table hint with bounded/semantic logic."""

    table_name = table_ref.split(".")[-1].strip("[] ").lower()
    hint_norm = (hint or "").strip().lower()
    if not table_name or not hint_norm:
        return False

    # Chinese hints keep substring behavior.
    if re.search(r"[\u4e00-\u9fff]", hint_norm):
        return hint_norm in table_ref.lower()

    # Exact is the strongest signal.
    if hint_norm == table_name:
        return True

    # Prefix support for short, meaningful identifiers like TA/IITF/IICS.
    if hint_norm in {"ta", "iitf", "iics"} and table_name.startswith(hint_norm):
        return True

    # Long English hints use contains match.
    if len(hint_norm) >= 4 and hint_norm in table_name:
        return True

    # Token-level fallback for snake-case or mixed separators.
    tokens = [token for token in re.split(r"[^a-z0-9]+", table_name) if token]
    return hint_norm in tokens
