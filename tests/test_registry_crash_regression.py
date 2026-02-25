#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry 闪退回归测试：
1) 验证连接关闭不会跨线程误伤
2) 验证指派/回文单号在维护模式开关下的退出行为
"""

import threading
from unittest.mock import patch

import pytest


pytestmark = pytest.mark.allow_empty_name


@pytest.fixture
def registry_runtime(tmp_path):
    from registry import hooks as registry_hooks
    from registry import config as registry_config
    from registry.config import load_config, set_config
    from registry import db as registry_db

    data_folder = tmp_path / "data"
    data_folder.mkdir(parents=True, exist_ok=True)

    old_folder = registry_hooks.get_data_folder()
    old_cache = registry_config._config_cache

    registry_hooks.set_data_folder(str(data_folder))
    cfg = load_config(data_folder=str(data_folder), ensure_registry_dir=True)
    set_config(cfg)
    db_path = cfg["registry_db_path"]
    wal = bool(cfg.get("registry_wal", False))

    conn = registry_db.get_connection(db_path, wal=wal)
    conn.execute("SELECT 1").fetchone()
    registry_db.close_connection()

    yield {
        "data_folder": str(data_folder),
        "db_path": db_path,
        "wal": wal,
    }

    try:
        registry_db.disable_maintenance_mode(str(data_folder))
    except Exception:
        pass
    registry_db.close_connection()
    registry_hooks._DATA_FOLDER = old_folder
    registry_config._config_cache = old_cache


def test_close_connection_after_use_does_not_close_other_thread_connection(tmp_path):
    from registry import db as registry_db

    db_path = tmp_path / "data" / ".registry" / "registry.db"
    ready = threading.Event()
    proceed = threading.Event()
    result = {}

    def worker():
        conn = registry_db.get_connection(str(db_path), wal=False)
        ready.set()
        proceed.wait(timeout=3.0)
        try:
            conn.execute("SELECT 1").fetchone()
            result["ok"] = True
        except Exception as e:  # pragma: no cover - 失败路径用于回归定位
            result["ok"] = False
            result["error"] = str(e)
        finally:
            registry_db.close_connection()

    t = threading.Thread(target=worker, name="registry-worker", daemon=True)
    t.start()

    assert ready.wait(timeout=3.0), "worker 未按预期建立连接"

    # 主线程关闭“自己的连接”后，不应影响 worker 线程当前连接
    registry_db.close_connection_after_use()
    proceed.set()
    t.join(timeout=3.0)

    assert result.get("ok") is True, result.get("error", "unknown error")


def test_get_connection_returns_different_instances_per_thread(tmp_path):
    from registry import db as registry_db

    db_path = tmp_path / "data" / ".registry" / "registry.db"
    main_conn = registry_db.get_connection(str(db_path), wal=False)
    main_conn_id = id(main_conn)

    worker_result = {}
    done = threading.Event()

    def worker():
        try:
            conn = registry_db.get_connection(str(db_path), wal=False)
            worker_result["conn_id"] = id(conn)
        finally:
            registry_db.close_connection()
            done.set()

    t = threading.Thread(target=worker, name="registry-worker-2", daemon=True)
    t.start()
    assert done.wait(timeout=3.0), "worker 未按预期完成连接获取"
    t.join(timeout=3.0)

    registry_db.close_connection()
    assert worker_result.get("conn_id") is not None
    assert worker_result["conn_id"] != main_conn_id


def test_on_assigned_no_maintenance_not_exit(registry_runtime):
    from registry import hooks as registry_hooks

    file_path = f"{registry_runtime['data_folder']}/source.xlsx"
    with patch("os._exit") as mock_exit:
        registry_hooks.on_assigned(
            file_type=1,
            file_path=file_path,
            row_index=2,
            interface_id="S-TEST-ASSIGN",
            project_id="2016",
            assigned_by="测试用户（接口工程师）",
            assigned_to="张三",
        )
    assert mock_exit.called is False


def test_on_assigned_maintenance_triggers_exit(registry_runtime):
    from registry import hooks as registry_hooks
    from registry import db as registry_db

    registry_db.enable_maintenance_mode(registry_runtime["data_folder"])
    file_path = f"{registry_runtime['data_folder']}/source.xlsx"

    with patch("os._exit") as mock_exit:
        registry_hooks.on_assigned(
            file_type=1,
            file_path=file_path,
            row_index=3,
            interface_id="S-TEST-ASSIGN-M",
            project_id="2016",
            assigned_by="测试用户（接口工程师）",
            assigned_to="李四",
        )
    assert mock_exit.called is True


def test_on_response_written_no_maintenance_not_exit(registry_runtime):
    from registry import hooks as registry_hooks

    file_path = f"{registry_runtime['data_folder']}/source.xlsx"
    with patch("os._exit") as mock_exit:
        registry_hooks.on_response_written(
            file_type=1,
            file_path=file_path,
            row_index=4,
            interface_id="S-TEST-RESP",
            response_number="HF-001",
            user_name="测试设计",
            project_id="2016",
            source_column="S",
            role="设计人员",
        )
    assert mock_exit.called is False


def test_on_response_written_maintenance_triggers_exit(registry_runtime):
    from registry import hooks as registry_hooks
    from registry import db as registry_db

    registry_db.enable_maintenance_mode(registry_runtime["data_folder"])
    file_path = f"{registry_runtime['data_folder']}/source.xlsx"

    with patch("os._exit") as mock_exit:
        registry_hooks.on_response_written(
            file_type=1,
            file_path=file_path,
            row_index=5,
            interface_id="S-TEST-RESP-M",
            response_number="HF-002",
            user_name="测试设计",
            project_id="2016",
            source_column="S",
            role="设计人员",
        )
    assert mock_exit.called is True
