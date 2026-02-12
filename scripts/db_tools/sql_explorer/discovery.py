"""Discovery engine for time/owner candidate columns."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from .profiling import CHINESE_NAME_PATTERN, OWNER_DELIMITERS, profile_records

TIME_KEYWORDS = (
    "time",
    "date",
    "deadline",
    "due",
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
    "责任人",
    "负责人",
    "经办",
    "主办",
    "办理人",
    "设计人",
)

FILE_TYPE_TABLE_HINTS = {
    "1": ("idi", "internal", "open", "打开", "内部"),
    "2": ("internal", "reply", "回复", "内部"),
    "3": ("external", "icm", "open", "外部"),
    "4": ("external", "reply", "外部", "回复"),
    "6": ("receive", "send", "doc", "函", "收发"),
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


def _calc_owner_match_rate(values: Iterable[Any], roster_names: Set[str]) -> float:
    if not roster_names:
        return 0.0

    valid_hits = 0
    valid_total = 0
    for value in values:
        if value is None:
            continue
        raw = str(value).strip()
        if not raw:
            continue
        normalized = raw
        for sep in OWNER_DELIMITERS:
            normalized = normalized.replace(sep, ",")
        tokens = [item.strip() for item in normalized.split(",") if item.strip()]
        if not tokens:
            continue
        for token in tokens:
            valid_total += 1
            name_match = CHINESE_NAME_PATTERN.findall(token)
            candidate_name = "".join(name_match) if name_match else token
            candidate_name = re.sub(r"[a-zA-Z]+$", "", candidate_name).strip()
            if candidate_name in roster_names:
                valid_hits += 1
    if valid_total == 0:
        return 0.0
    return valid_hits / valid_total


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
    owner_match_rate: float,
) -> float:
    score = 0.0
    score += 0.35 * _keyword_score(column_name, OWNER_KEYWORDS)
    score += 0.30 * float(profile.get("chinese_name_rate", 0.0))
    score += 0.25 * owner_match_rate
    score += 0.10 * float(profile.get("multi_owner_rate", 0.0))
    return max(0.0, min(1.0, score))


def discover_candidates(
    sampled_tables: List[Dict[str, Any]],
    roster_names: Optional[Set[str]] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    """Discover global time/owner candidate columns from sampled tables."""

    roster_names = roster_names or set()
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
            owner_match_rate = _calc_owner_match_rate(values, roster_names)

            t_score = _time_score(col_name, profile)
            o_score = _owner_score(col_name, profile, owner_match_rate)

            t_evidence = {
                "date_parse_rate": profile.get("date_parse_rate", 0.0),
                "null_rate": profile.get("null_rate", 1.0),
                "keyword_score": _keyword_score(col_name, TIME_KEYWORDS),
                "top_values": profile.get("top_values", [])[:3],
            }
            o_evidence = {
                "chinese_name_rate": profile.get("chinese_name_rate", 0.0),
                "roster_match_rate": round(owner_match_rate, 6),
                "multi_owner_rate": profile.get("multi_owner_rate", 0.0),
                "keyword_score": _keyword_score(col_name, OWNER_KEYWORDS),
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
        table_name = item.table_ref.lower()
        matched = any(hint.lower() in table_name for hint in hints)
        if matched:
            rows.append(item)
    rows.sort(key=lambda c: c.score + math.log1p(len(c.table_ref)) * 0.001, reverse=True)
    return rows
