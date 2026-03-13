#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helpers for scanning offline SQL dump files with lightweight line filtering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence

from scripts.db_tools.sql_explorer.validate_cims_sql_dump import _decode_sql_token, _extract_values_blob, _split_sql_values


def build_line_matcher(tokens: Optional[Sequence[str]] = None) -> Callable[[str], bool]:
    values = [str(token) for token in (tokens or []) if str(token or "").strip()]
    if not values:
        return lambda _line: True
    if len(values) == 1:
        token = values[0]
        return lambda line: token in line

    grouped: Dict[str, List[str]] = {}
    for token in values:
        prefix = token[:6] if len(token) >= 6 else token
        grouped.setdefault(prefix, []).append(token)
    prefix_items = tuple(grouped.items())

    def matches(line: str) -> bool:
        for prefix, group in prefix_items:
            if prefix not in line:
                continue
            for token in group:
                if token in line:
                    return True
        return False

    return matches


def iter_filtered_insert_dicts(
    path: Path,
    columns: Sequence[str],
    required_tokens: Optional[Sequence[str]] = None,
) -> Iterator[Dict[str, Any]]:
    matcher = build_line_matcher(required_tokens)
    upper_columns = [str(name).upper() for name in columns]
    buffer = ""
    collecting = False
    matched = False

    with path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            stripped = line.lstrip()
            if not collecting:
                if not stripped.upper().startswith("INSERT INTO"):
                    continue
                buffer = line
                collecting = True
                matched = matcher(line)
            else:
                buffer += line
                if not matched and matcher(line):
                    matched = True

            blob = _extract_values_blob(buffer)
            if blob is None:
                continue
            if matched:
                row = _split_sql_values(blob)
                yield {upper_columns[idx]: row[idx] for idx in range(min(len(upper_columns), len(row)))}
            buffer = ""
            collecting = False
            matched = False


def extract_first_insert_value(sql_text: str) -> Optional[str]:
    upper = sql_text.upper()
    pos = upper.find("VALUES")
    if pos < 0:
        return None
    start = sql_text.find("(", pos)
    if start < 0:
        return None
    idx = start + 1
    total = len(sql_text)
    while idx < total and sql_text[idx].isspace():
        idx += 1

    buf: List[str] = []
    in_quote = False
    while idx < total:
        ch = sql_text[idx]
        if ch == "'":
            buf.append(ch)
            if in_quote and idx + 1 < total and sql_text[idx + 1] == "'":
                buf.append("'")
                idx += 2
                continue
            in_quote = not in_quote
            idx += 1
            continue
        if ch == "," and not in_quote:
            break
        buf.append(ch)
        idx += 1
    return _decode_sql_token("".join(buf).strip())


def iter_insert_dicts_by_first_id(
    path: Path,
    columns: Sequence[str],
    target_ids: Sequence[str],
) -> Iterator[Dict[str, Any]]:
    id_set = {str(item or "").strip().upper() for item in target_ids if str(item or "").strip()}
    if not id_set:
        return

    upper_columns = [str(name).upper() for name in columns]
    with path.open("r", encoding="utf-8", errors="ignore") as stream:
        for line in stream:
            stripped = line.lstrip()
            if not stripped.upper().startswith("INSERT INTO"):
                continue
            first_value = str(extract_first_insert_value(line) or "").strip().upper()
            if first_value not in id_set:
                continue
            blob = _extract_values_blob(line)
            if blob is None:
                continue
            row = _split_sql_values(blob)
            yield {upper_columns[idx]: row[idx] for idx in range(min(len(upper_columns), len(row)))}
