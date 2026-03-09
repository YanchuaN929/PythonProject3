#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel 工作簿安全读写辅助工具。
"""

from __future__ import annotations

import os
import tempfile

from openpyxl import load_workbook


def _needs_keep_vba(file_path: str) -> bool:
    """xlsm 文件需要保留 VBA 内容。"""
    return str(file_path).lower().endswith(".xlsm")


def open_workbook_for_edit(file_path: str):
    """以可编辑方式打开工作簿，并尽量保留原有宏内容。"""
    return load_workbook(file_path, keep_vba=_needs_keep_vba(file_path))


def atomic_save_workbook(workbook, file_path: str) -> None:
    """
    先保存到同目录临时文件，再原子替换目标文件，避免中途失败把原文件写坏。
    """
    file_path = os.path.abspath(file_path)
    parent_dir = os.path.dirname(file_path) or "."
    suffix = os.path.splitext(file_path)[1] or ".xlsx"
    fd = None
    temp_path = None

    try:
        fd, temp_path = tempfile.mkstemp(
            prefix=".__excel_write_",
            suffix=suffix,
            dir=parent_dir,
        )
        os.close(fd)
        fd = None

        workbook.save(temp_path)

        # 先验证临时文件可正常打开，再替换正式文件。
        verify_wb = open_workbook_for_edit(temp_path)
        verify_wb.close()

        os.replace(temp_path, file_path)
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
