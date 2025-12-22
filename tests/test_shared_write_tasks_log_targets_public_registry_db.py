import sqlite3

import pytest


@pytest.fixture
def isolated_registry_folder(tmp_path, monkeypatch):
    """
    构造一个“公共盘根目录”的模拟结构：
    <data_folder>/registry/registry.db
    并把 registry.hooks 的 data_folder 指向该目录。
    """
    from registry import hooks as registry_hooks
    from registry.db import close_connection

    data_folder = tmp_path / "data_folder"
    data_folder.mkdir(parents=True, exist_ok=True)

    legacy_dir = data_folder / "registry"
    legacy_dir.mkdir(parents=True, exist_ok=True)

    # 只要目录存在即可；db 文件可由 sqlite 自动创建，但这里也创建一个空文件更贴近现场
    (legacy_dir / "registry.db").write_bytes(b"")

    # 隔离：避免受其他测试/开发环境残留连接影响
    close_connection()

    registry_hooks.set_data_folder(str(data_folder))
    yield data_folder

    # 清理
    close_connection()
    registry_hooks.set_data_folder(None)


def test_write_tasks_log_is_written_to_public_registry_db(isolated_registry_folder):
    """
    验证“写入任务记录”确实写入到被 registry 选中的 registry_db_path，
    且该路径应当优先是 <data_folder>/registry/registry.db（你的现场结构）。
    """
    from registry import hooks as registry_hooks
    from registry.db import get_connection
    from write_tasks.models import WriteTask
    from write_tasks.shared_log import upsert_task

    cfg = registry_hooks._cfg()
    db_path = cfg.get("registry_db_path") or ""

    assert db_path.replace("\\", "/").endswith("/registry/registry.db")

    conn = get_connection(db_path, wal=False)

    task = WriteTask(
        task_id="test-task-001",
        task_type="assignment",
        payload={"assignments": [{"file_path": "A.xlsx", "file_type": 1, "project_id": "2016", "row_index": 2}]},
        submitted_by="pytest-user",
        description="pytest 端到端验证：写入共享 write_tasks_log",
        status="completed",
        submitted_at="2025-12-19T10:00:00",
        started_at="2025-12-19T10:00:01",
        completed_at="2025-12-19T10:00:02",
        error=None,
    )
    upsert_task(conn, task)

    # 用 sqlite3 直连同一个文件，确保数据真的落到该 db 文件里（不是仅内存/别的连接）
    raw = sqlite3.connect(db_path)
    try:
        row = raw.execute(
            "SELECT task_id, submitted_by, status FROM write_tasks_log WHERE task_id=?",
            (task.task_id,),
        ).fetchone()
    finally:
        raw.close()

    assert row == (task.task_id, task.submitted_by, task.status)



