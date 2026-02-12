"""Roster loading and validation helpers."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd

INVALID_OWNER_VALUES = {"", "无", "nan", "none", "null"}


def get_repo_root() -> Path:
    """Resolve repository root from module path."""

    # scripts/db_tools/sql_explorer/roster.py -> repo root
    return Path(__file__).resolve().parents[3]


def get_resource_path(relative_path: str) -> Path:
    """Resolve resource path with PyInstaller support."""

    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative_path
    return get_repo_root() / relative_path


def resolve_default_roster_file() -> Optional[Path]:
    """Resolve roster file according to current department profile."""

    try:
        from utils.dept_config import get_role_table_file  # type: ignore

        rel_path = get_role_table_file()
    except Exception:
        rel_path = "excel_bin/姓名角色表.xlsx"

    candidate = get_resource_path(rel_path)
    if candidate.exists():
        return candidate
    fallback = get_resource_path("excel_bin/姓名角色表.xlsx")
    if fallback.exists():
        return fallback
    return None


def load_roster_names(roster_file: Optional[str] = None) -> Set[str]:
    """Load roster names from excel file first column."""

    if roster_file:
        path = Path(roster_file)
    else:
        default_path = resolve_default_roster_file()
        if not default_path:
            return set()
        path = default_path

    if not path.exists():
        return set()

    try:
        df = pd.read_excel(path)
    except Exception:
        return set()

    if df.empty or len(df.columns) == 0:
        return set()

    names = set()
    for value in df.iloc[:, 0].dropna().astype(str).tolist():
        name = value.strip()
        if name and name.lower() not in INVALID_OWNER_VALUES:
            names.add(name)
    return names


def normalize_owner_tokens(value: Any) -> List[str]:
    """Normalize owner field into token list."""

    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() in INVALID_OWNER_VALUES:
        return []

    normalized = text
    for sep in [",", "，", ";", "；", "/", "、"]:
        normalized = normalized.replace(sep, ",")

    names: List[str] = []
    for token in normalized.split(","):
        token = token.strip()
        if not token:
            continue
        chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", token))
        candidate = chinese or token
        candidate = re.sub(r"[a-zA-Z]+$", "", candidate).strip()
        if candidate and candidate.lower() not in INVALID_OWNER_VALUES:
            names.append(candidate)
    return names


def validate_owner_values(
    values: Iterable[Any], roster_names: Set[str]
) -> Dict[str, Any]:
    """Validate owner values against roster names."""

    total_tokens = 0
    match_tokens = 0
    invalid_examples: List[str] = []
    multi_owner_rows = 0
    non_empty_rows = 0

    for value in values:
        tokens = normalize_owner_tokens(value)
        if not tokens:
            continue
        non_empty_rows += 1
        if len(tokens) >= 2:
            multi_owner_rows += 1
        for token in tokens:
            total_tokens += 1
            if token in roster_names:
                match_tokens += 1
            elif len(invalid_examples) < 20 and token not in invalid_examples:
                invalid_examples.append(token)

    match_rate = (match_tokens / total_tokens) if total_tokens else 0.0
    multi_rate = (multi_owner_rows / non_empty_rows) if non_empty_rows else 0.0
    return {
        "name_in_roster_rate": round(match_rate, 6),
        "multi_owner_rate": round(multi_rate, 6),
        "invalid_name_examples": invalid_examples,
        "total_name_tokens": total_tokens,
        "matched_name_tokens": match_tokens,
    }
