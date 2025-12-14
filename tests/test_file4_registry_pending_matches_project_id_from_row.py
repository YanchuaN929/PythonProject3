import sqlite3

import pandas as pd


def test_file4_registry_pending_matches_project_id_from_row_when_filename_missing(monkeypatch, tmp_path):
    """
    文件名不包含4位项目号时，应从行数据的“项目号”列提取，以便registry加回能匹配到。
    """
    import main as main_module

    # 1) 伪造Excel：贴近真实结构：提供“项目号”列和“接口号”列
    df = pd.DataFrame(
        {
            "项目号": ["hdr", "1818"],
            "接口号": ["hdr", "S-GT---1JJ-05-25C2-25C3(设计人员)"],
            "X": ["hdr", "x"],
        }
    )
    monkeypatch.setattr(main_module.pd, "read_excel", lambda *a, **k: df, raising=True)

    # 2) 让筛选：科室/类别通过，原始final_rows为空
    monkeypatch.setattr(main_module, "execute4_process1", lambda _df: {1}, raising=True)
    monkeypatch.setattr(main_module, "execute4_process2", lambda _df: {1}, raising=True)
    monkeypatch.setattr(main_module, "execute4_process3", lambda _df, _now: set(), raising=True)
    monkeypatch.setattr(main_module, "execute4_process4", lambda _df: set(), raising=True)

    # 3) registry.db最小表结构
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

    import registry.hooks as hooks
    import registry.db as reg_db

    monkeypatch.setattr(hooks, "_cfg", lambda: {"registry_db_path": str(db_path), "registry_enabled": True}, raising=True)
    monkeypatch.setattr(reg_db, "get_connection", lambda _p, _w=True: conn, raising=True)

    # 4) 文件名不含4位数字
    out = main_module.process_target_file4(str(tmp_path / "外部接口单报表_无项目号.xlsx"), pd.Timestamp("2025-12-12"))
    assert not out.empty


