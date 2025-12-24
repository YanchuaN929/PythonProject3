import os
import tempfile

import pandas as pd


def test_registry_bootstrap_writes_when_db_empty(monkeypatch):
    """
    回归：当绑定到的 registry.db 是空库（tasks=0）时，即使本轮走缓存命中路径，
    也应该允许一次 bootstrap 写入，使 get_display_status 能查到状态。
    """
    import registry.hooks as registry_hooks
    from registry.config import load_config
    from registry.db import get_connection
    from registry.util import make_task_id, get_source_basename

    tmpdir = tempfile.mkdtemp()
    try:
        # 绑定 data_folder（会生成 <tmpdir>/.registry/registry.db）
        registry_hooks.set_data_folder(tmpdir)
        cfg = load_config(data_folder=tmpdir, ensure_registry_dir=True)
        db_path = cfg["registry_db_path"]
        wal = bool(cfg.get("registry_wal", False))

        # 确认 tasks 表存在但为空
        conn = get_connection(db_path, wal)
        conn.execute("DELETE FROM tasks")
        conn.commit()
        c0 = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert c0 == 0

        # 构造一行“处理结果”（模拟任意 file_type=1）
        df = pd.DataFrame(
            {
                "接口号": ["S-TEST-001"],
                "项目号": ["1818"],
                "原始行号": [7],
                "接口时间": ["2025.12.25"],
                "责任人": ["张三"],
            }
        )

        # 执行一次写入（等价于 bootstrap 写入目标）
        registry_hooks.on_process_done(
            file_type=1,
            project_id="1818",
            source_file=get_source_basename("1818按项目导出IDI手册.xlsx"),
            result_df=df,
        )

        c1 = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        assert c1 == 1

        # 现在应能查到 display_status
        tid = make_task_id(1, "1818", "S-TEST-001", get_source_basename("1818按项目导出IDI手册.xlsx"), 7)
        status = registry_hooks.get_display_status(
            [
                {
                    "file_type": 1,
                    "project_id": "1818",
                    "interface_id": "S-TEST-001",
                    "source_file": get_source_basename("1818按项目导出IDI手册.xlsx"),
                    "row_index": 7,
                    "interface_time": "2025.12.25",
                }
            ]
        )
        assert tid in status
        assert status[tid], "写入后应有默认 display_status（至少为“待完成”）"
    finally:
        try:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


