#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest

from ui.window import WindowManager, _generate_registry_status_sort_key


pytestmark = pytest.mark.allow_empty_name


def test_status_sort_key_uses_clean_status_text():
    assert _generate_registry_status_sort_key("❗ 请指派")[1] == "请指派"
    assert _generate_registry_status_sort_key("! 请指派")[1] == "请指派"
    assert _generate_registry_status_sort_key("⏳ （已延期）待审查")[1] == "待审查"
    assert _generate_registry_status_sort_key("📌 待设计人员完成")[1] == "待设计人员完成"


def test_window_status_column_sort_key_no_longer_collapses_all_statuses():
    manager = WindowManager.__new__(WindowManager)

    values = [
        "❗ 请指派",
        "⏳ （已延期）待审查",
        "📌 待设计人员完成",
    ]
    keys = [manager._generate_sort_key("状态", value, False) for value in values]

    assert len(set(keys)) == len(values)
