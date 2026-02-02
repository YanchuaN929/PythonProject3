#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空结果提示文本测试：
- 文件5：空结果应显示“无三维接口”
"""

import pandas as pd
import pytest


pytestmark = pytest.mark.allow_empty_name


def test_display_results5_empty_message(base_app, monkeypatch):
    messages = []

    def record_message(_viewer, message):
        messages.append(message)

    monkeypatch.setattr(base_app.window_manager, "show_empty_message", record_message)

    base_app.display_results5(pd.DataFrame(), show_popup=False)

    assert base_app.has_processed_results5 is True
    assert messages, "应该调用 show_empty_message"
    assert messages[-1] == "无三维接口"


def test_on_tab_changed_file5_empty_message_even_without_target_files(base_app, monkeypatch):
    messages = []

    def record_message(_viewer, message):
        messages.append(message)

    monkeypatch.setattr(base_app.window_manager, "show_empty_message", record_message)

    # 模拟：文件5已处理但结果为空，同时 target_files5 为空（例如缓存/路径变化导致）
    base_app.has_processed_results5 = True
    base_app.processing_results5 = pd.DataFrame()
    base_app.target_files5 = []

    # 切换到tab5（三维提资接口），触发渲染逻辑
    base_app.notebook.select(4)
    base_app.on_tab_changed(None)

    assert messages, "应该调用 show_empty_message"
    assert messages[-1] == "无三维接口"

