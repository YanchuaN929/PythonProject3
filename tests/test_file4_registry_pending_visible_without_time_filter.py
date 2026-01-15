import sqlite3

import pandas as pd


def test_file4_registry_pending_visible_even_if_time_filter_fails(monkeypatch, tmp_path):
    """
    回文已填后进入“待审查/待指派人审查”，上级应能看到；
    即使时间窗口筛选(process3_rows)不通过，也必须从registry加回。
    """
    import main as main_module

    # 1) 伪造Excel读取：至少5列，E列(索引4)为接口号
    df = pd.DataFrame(
        {
            0: ["hdr", "x"],
            1: ["hdr", "x"],
            2: ["hdr", "x"],
            3: ["hdr", "x"],
            4: ["hdr", "S-GT---1JJ-05-25C2-25C3(设计人员)"],
        }
    )
    monkeypatch.setattr(main_module.pd, "read_excel", lambda *a, **k: df, raising=True)

    # 2) 让筛选：科室/类别通过，但时间/完成列都不通过 → 原始final_rows为空
    monkeypatch.setattr(main_module, "execute4_process1", lambda _df: {1}, raising=True)
    monkeypatch.setattr(main_module, "execute4_process2", lambda _df: {1}, raising=True)
    monkeypatch.setattr(main_module, "execute4_process3", lambda _df, _now, _pid=None: set(), raising=True)  # time fail
    monkeypatch.setattr(main_module, "execute4_process4", lambda _df: set(), raising=True)

    # 3) 准备registry.db最小表结构
    db_path = tmp_path / "registry.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE tasks (
            interface_id TEXT,
            project_id TEXT,
            display_status TEXT,
            file_type INTEGER,
            ignored INTEGER,
            status TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO tasks(interface_id, project_id, display_status, file_type, ignored, status) VALUES(?,?,?,?,?,?)",
        ("S-GT---1JJ-05-25C2-25C3", "1818", "待审查", 4, 0, "completed"),
    )
    conn.commit()

    # 4) monkeypatch registry配置/连接
    import registry.hooks as hooks
    import registry.db as reg_db

    monkeypatch.setattr(hooks, "_cfg", lambda: {"registry_db_path": str(db_path), "registry_enabled": True}, raising=True)

    def fake_get_connection(_path, _wal=True):
        return conn

    monkeypatch.setattr(reg_db, "get_connection", fake_get_connection, raising=True)

    # 5) 路径必须含4位项目号，否则现有excel_index按文件名无法匹配project_id
    out = main_module.process_target_file4(str(tmp_path / "1818_test.xlsx"), pd.Timestamp("2025-12-12"))
    assert not out.empty
    assert "原始行号" in out.columns

