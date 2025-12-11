#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
姓名录入弹窗相关单元测试
"""

import pytest
from unittest.mock import MagicMock


@pytest.mark.allow_empty_name
def test_prompt_for_user_name_saves_config(monkeypatch):
    """确保弹窗成功填写姓名后会保存配置并刷新状态"""
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.root = MagicMock()
    app.config = {"user_name": ""}
    app._should_show_popup = MagicMock(return_value=True)
    app._name_prompt_active = False

    monkeypatch.setattr(app, '_show_name_input_dialog', lambda message: "  李雷  ")

    handler_calls = {}

    def fake_handler(name, trigger_refresh=False):
        handler_calls["name"] = name
        handler_calls["refresh"] = trigger_refresh

    monkeypatch.setattr(app, '_handle_user_name_change', fake_handler)

    assert app._prompt_for_user_name(reason="start_processing") is True
    assert handler_calls == {"name": "李雷", "refresh": False}


@pytest.mark.allow_empty_name
def test_enforce_gate_reprompts_until_success(monkeypatch):
    """当姓名为空时，若用户取消一次也会再次弹出，直到填写成功"""
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.config = {"user_name": ""}
    app.process_button = MagicMock()
    app.export_button = MagicMock()
    app.auto_mode = False
    app._should_show_popup = MagicMock(return_value=True)
    app._name_prompt_active = False

    prompt_calls = []
    responses = [False, True]

    def fake_prompt(reason):
        prompt_calls.append(reason)
        result = responses.pop(0)
        if result:
            app.config["user_name"] = "张三"
        return result

    monkeypatch.setattr(app, '_prompt_for_user_name', fake_prompt)

    app._enforce_user_name_gate(show_popup=True)

    assert prompt_calls == ["first_run", "first_run"]
    assert app.config["user_name"] == "张三"

