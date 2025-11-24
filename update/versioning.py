# -*- coding: utf-8 -*-
"""
版本标记文件(version.json)的读写与比较工具。
"""
from __future__ import annotations

import json
import os
from typing import Iterable, Tuple

DEFAULT_VERSION = "0.0.0.0"


def read_version(file_path: str) -> str:
    """
    读取指定路径的 version.json，返回版本号字符串。
    若文件不存在或无法解析，则返回 DEFAULT_VERSION。
    """
    if not file_path:
        return DEFAULT_VERSION

    try:
        if not os.path.exists(file_path):
            return DEFAULT_VERSION

        with open(file_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        if isinstance(data, dict):
            value = data.get("version", "").strip()
            return value or DEFAULT_VERSION

        if isinstance(data, str):
            value = data.strip()
            return value or DEFAULT_VERSION

        # 兼容列表形式 ["2025.11.21.1"]
        if isinstance(data, Iterable):
            for item in data:
                if isinstance(item, str) and item.strip():
                    return item.strip()
    except Exception:
        pass

    return DEFAULT_VERSION


def parse_version(version: str) -> Tuple[int, ...]:
    """
    将版本号字符串转换为整型元组用于比较。
    支持日期规则 `YYYY.MM.DD.N` 或任意「.」分隔的数字。
    """
    if not version:
        version = DEFAULT_VERSION

    parts = []
    for part in str(version).split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)

    # 统一长度，便于比较
    while len(parts) < 4:
        parts.append(0)

    return tuple(parts[:4])


def compare_versions(local: str, remote: str) -> int:
    """
    比较两个版本号。
    返回值：
        -1 -> remote > local
         0 -> 相等
         1 -> local > remote
    """
    local_tuple = parse_version(local)
    remote_tuple = parse_version(remote)

    if local_tuple == remote_tuple:
        return 0

    return -1 if local_tuple < remote_tuple else 1

