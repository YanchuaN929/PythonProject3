#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
姓名变更处理逻辑测试
"""

from unittest.mock import MagicMock


def _make_app():
    from base import ExcelProcessorApp
    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.config = {}
    app.save_config = MagicMock()
    app.load_user_role = MagicMock()
    app._enforce_user_name_gate = MagicMock()
    app.refresh_all_processed_results = MagicMock()
    return app


def test_handle_user_name_change_without_refresh():
    app = _make_app()
    app._handle_user_name_change("  张三  ", trigger_refresh=False)

    assert app.config["user_name"] == "张三"
    app.save_config.assert_called_once()
    app.load_user_role.assert_called_once()
    app._enforce_user_name_gate.assert_called_once_with(show_popup=False)
    app.refresh_all_processed_results.assert_not_called()


def test_handle_user_name_change_with_refresh():
    app = _make_app()
    app._handle_user_name_change("李四", trigger_refresh=True)

    app.refresh_all_processed_results.assert_called_once()

