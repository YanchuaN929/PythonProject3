import sqlite3

import pandas as pd


def test_file1_registry_pending_includes_null_ignored(monkeypatch, tmp_path):
    """
    兼容旧数据：tasks.ignored 为NULL时，也应视为“未忽略”，待审查任务要能加回到主列表。
    """
    import main as main_module

    # 1) 伪造Excel：提供“接口号”列（extract_interface_id会自动去角色后缀）
    df = pd.DataFrame(
        {
            "接口号": ["hdr", "S-GT---1JJ-05-25C2-25C3(设计人员)"],
            "H": ["hdr", "25C2"],  # 不重要，筛选函数会被monkeypatch
        }
    )
    monkeypatch.setattr(main_module.pd, "read_excel", lambda *a, **k: df, raising=True)

    # 2) 让四步筛选：只有科室筛选通过，其他为空，保证原始final_rows为空
    monkeypatch.setattr(main_module, "execute_process1", lambda _df: {1}, raising=True)
    monkeypatch.setattr(main_module, "execute_process2", lambda _df, _now: set(), raising=True)
    monkeypatch.setattr(main_module, "execute_process3", lambda _df: set(), raising=True)
    monkeypatch.setattr(main_module, "execute_process4", lambda _df: set(), raising=True)

    # 3) 创建最小registry.db（ignored为NULL）
    db_path = tmp_path / "registry.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE tasks (
            file_type INTEGER,
            interface_id TEXT,
            project_id TEXT,
            display_status TEXT,
            row_index INTEGER,
            source_file TEXT,
            ignored INTEGER,
            status TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO tasks(file_type, interface_id, project_id, display_status, row_index, source_file, ignored, status) VALUES(?,?,?,?,?,?,?,?)",
        (1, "S-GT---1JJ-05-25C2-25C3", "1818", "待审查", 6, "1818按项目导出IDI手册2025-12-03-09_31_29.xlsx", None, "completed"),
    )
    conn.commit()

    # 4) monkeypatch registry配置/连接
    import registry.hooks as hooks
    import registry.db as reg_db

    monkeypatch.setattr(hooks, "_cfg", lambda: {"registry_db_path": str(db_path), "registry_enabled": True, "registry_wal": False}, raising=True)
    monkeypatch.setattr(reg_db, "get_connection", lambda _p, _w=False: conn, raising=True)

    out = main_module.process_target_file("1818按项目导出IDI手册2025-12-03-09_31_29.xlsx", pd.Timestamp("2025-12-12"))
    assert not out.empty



