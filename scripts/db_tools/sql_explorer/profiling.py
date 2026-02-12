"""Column profiling utilities."""

from __future__ import annotations

import re
import warnings
from typing import Any, Dict, Iterable, List

import pandas as pd

OWNER_DELIMITERS = [",", "，", ";", "；", "/", "、"]
CHINESE_NAME_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,8}")


def _normalize_for_owner(value: str) -> str:
    text = value
    for sep in OWNER_DELIMITERS:
        text = text.replace(sep, ",")
    return text


def _to_series(values: Iterable[Any]) -> pd.Series:
    return pd.Series(list(values), dtype="object")


def profile_series(values: Iterable[Any]) -> Dict[str, Any]:
    """Profile a single column values iterable."""

    series = _to_series(values)
    total = int(series.shape[0])
    non_null_series = series.dropna()
    non_null = int(non_null_series.shape[0])
    null_count = total - non_null
    null_rate = float(null_count / total) if total else 1.0

    as_text = non_null_series.astype(str).str.strip()
    text_non_empty = as_text[as_text != ""]
    non_empty_count = int(text_non_empty.shape[0])

    unique_count = int(text_non_empty.nunique()) if non_empty_count else 0
    unique_rate = float(unique_count / non_empty_count) if non_empty_count else 0.0

    top_values = []
    if non_empty_count:
        value_counts = text_non_empty.value_counts().head(8)
        top_values = [
            {"value": str(idx), "count": int(cnt)} for idx, cnt in value_counts.items()
        ]

    date_parse_rate = 0.0
    if non_empty_count:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=UserWarning)
            parsed = pd.to_datetime(text_non_empty, errors="coerce")
        date_parse_rate = float(parsed.notna().mean())

    avg_length = float(text_non_empty.str.len().mean()) if non_empty_count else 0.0

    chinese_name_hit = 0
    multi_owner_hit = 0
    for text in text_non_empty.tolist():
        if CHINESE_NAME_PATTERN.search(text):
            chinese_name_hit += 1
        normalized = _normalize_for_owner(text)
        token_count = len([item for item in normalized.split(",") if item.strip()])
        if token_count >= 2:
            multi_owner_hit += 1

    chinese_name_rate = float(chinese_name_hit / non_empty_count) if non_empty_count else 0.0
    multi_owner_rate = float(multi_owner_hit / non_empty_count) if non_empty_count else 0.0

    return {
        "total": total,
        "non_null": non_null,
        "null_count": null_count,
        "null_rate": round(null_rate, 6),
        "non_empty_count": non_empty_count,
        "unique_count": unique_count,
        "unique_rate": round(unique_rate, 6),
        "date_parse_rate": round(date_parse_rate, 6),
        "avg_length": round(avg_length, 3),
        "chinese_name_rate": round(chinese_name_rate, 6),
        "multi_owner_rate": round(multi_owner_rate, 6),
        "top_values": top_values,
    }


def profile_records(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Profile all columns from record list."""

    if not records:
        return {}

    df = pd.DataFrame.from_records(records)
    result: Dict[str, Dict[str, Any]] = {}
    for col in df.columns:
        result[str(col)] = profile_series(df[col].tolist())
    return result
