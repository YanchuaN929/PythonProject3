#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

import pytest


pytestmark = pytest.mark.allow_empty_name


def test_is_lock_error_recognizes_busy_and_locked():
    from registry import hooks

    assert hooks._is_lock_error(sqlite3.OperationalError("database is locked")) is True
    assert hooks._is_lock_error(sqlite3.OperationalError("database is busy")) is True
    assert hooks._is_lock_error(sqlite3.OperationalError("syntax error")) is False


def test_on_assigned_retries_when_database_locked(monkeypatch):
    from registry import hooks
    from registry import service as registry_service

    attempts = {"count": 0}

    def flaky_upsert(*_args, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return None

    monkeypatch.setattr(hooks, "_ensure_data_folder_from_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        hooks,
        "_cfg",
        lambda: {
            "registry_enabled": True,
            "registry_db_path": "E:/dummy/.registry/registry.db",
            "registry_wal": False,
        },
    )
    monkeypatch.setattr(registry_service, "upsert_task", flaky_upsert)
    monkeypatch.setattr(hooks, "write_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(hooks, "close_connection", lambda: None)
    monkeypatch.setattr(hooks, "close_connection_after_use", lambda: None)
    monkeypatch.setattr(hooks.time, "sleep", lambda _s: None)
    monkeypatch.setattr(hooks.random, "uniform", lambda _a, _b: 0.0)

    hooks.on_assigned(
        file_type=1,
        file_path="E:/dummy/source.xlsx",
        row_index=2,
        interface_id="S-TEST-LOCK",
        project_id="2016",
        assigned_by="测试用户（接口工程师）",
        assigned_to="张三",
    )

    assert attempts["count"] == 3


def test_malformed_error_disables_registry_runtime(monkeypatch):
    from registry import hooks

    hooks._RUNTIME_DISABLED_REASON = ""
    hooks._RUNTIME_DISABLE_NOTIFIED = False

    notified = []
    monkeypatch.setattr(
        "services.db_status.notify_error",
        lambda message, show_dialog=True: notified.append((message, show_dialog)),
    )

    hooks._handle_runtime_registry_error(Exception("database disk image is malformed"))

    assert "malformed" in hooks._RUNTIME_DISABLED_REASON.lower()
    assert notified
    assert notified[0][1] is True
    assert hooks._enabled({"registry_enabled": True}) is False
