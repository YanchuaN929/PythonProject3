def test_on_assigned_does_not_trigger_time_reset_when_interface_time_not_provided(tmp_path, monkeypatch):
    """
    回归：on_assigned 是“局部更新”，不应因为 fields 不含 interface_time 而被 upsert_task 误判为“时间变化重置”，
    从而把 display_status 回退成“请指派”。
    """
    from datetime import datetime

    from registry import hooks
    from registry.service import upsert_task

    # 让 hooks 使用临时 db
    db_path = str(tmp_path / "registry.db")
    cfg = {
        "registry_enabled": True,
        "registry_db_path": db_path,
        "registry_wal": False,
    }
    monkeypatch.setattr(hooks, "_cfg", lambda: cfg)

    # 预置一条旧任务（请指派 + 有 interface_time）
    file_type = 2
    project_id = "1907"
    interface_id = "IF-001"
    source_file = "a.xlsx"
    row_index = 5013
    now = datetime(2025, 12, 21, 12, 0, 0).isoformat()
    upsert_task(
        db_path=db_path,
        wal=False,
        key={
            "file_type": file_type,
            "project_id": project_id,
            "interface_id": interface_id,
            "source_file": source_file,
            "row_index": row_index,
        },
        fields={
            "department": "请室主任确认",
            "interface_time": "2025-12-30",
            "display_status": "请指派",
        },
        now=datetime.fromisoformat(now),
    )

    # 调用 on_assigned（不带 interface_time）
    hooks.on_assigned(
        file_type=file_type,
        file_path=r"\\server\share\a.xlsx",
        row_index=row_index,
        interface_id=interface_id,
        project_id=project_id,
        assigned_by="张三（接口工程师）",
        assigned_to="严鹏南",
    )

    from registry.db import get_connection
    from registry.util import make_task_id

    tid = make_task_id(file_type, project_id, interface_id, source_file, row_index)
    conn = get_connection(db_path, wal=False)
    row = conn.execute("SELECT display_status, responsible_person FROM tasks WHERE id=?", (tid,)).fetchone()
    assert row is not None
    assert row[0] == "待完成"
    assert row[1] == "严鹏南"


