#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证“应用端任何读取/写入 Registry 后都立即断开连接”的关键路径：
- WriteTaskManager 同步共享任务日志后应关闭连接
"""

import pytest


pytestmark = pytest.mark.allow_empty_name


def test_write_task_manager_sync_closes_registry_connection(tmp_path, monkeypatch):
    from write_tasks.models import WriteTask
    from write_tasks import manager as wt_manager
    from registry import db as registry_db

    db_path = tmp_path / "registry.db"

    class _DummyHooks:
        @staticmethod
        def _cfg():
            return {
                "registry_enabled": True,
                "registry_db_path": str(db_path),
                "registry_wal": False,
            }

    # 强制让同步逻辑走到 get_connection
    monkeypatch.setattr(wt_manager, "registry_hooks", _DummyHooks())
    monkeypatch.setattr(wt_manager, "_shared_log_upsert_task", lambda conn, task: conn.execute("SELECT 1"))

    mgr = wt_manager.WriteTaskManager()
    try:
        task = WriteTask(
            task_id="t1",
            task_type="assignment",
            payload={},
            submitted_by="tester",
            description="test",
        )

        mgr._sync_to_shared_log(task)

        assert registry_db._CONN is None
    finally:
        try:
            mgr.shutdown()
        except Exception:
            pass

