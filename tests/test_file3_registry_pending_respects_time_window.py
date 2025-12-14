import os
import sqlite3
from datetime import datetime

import pandas as pd


def test_file3_registry_pending_respects_time_window(tmp_path, monkeypatch):
    """
    复现/防回归：
    - 文件3原始筛选有时间窗口（M/L列日期），远未来(2028)不应进入结果
    - Registry“加回待审查任务”也必须遵守时间窗口，不能把远未来行加回
    """
    import main

    # 1) 构造一个最小的“待处理文件3”Excel（至少包含 I(8), L(11), M(12), Q(16), T(19), AL(37), AO(40), AP(41), C(2)）
    cols = [f"c{i}" for i in range(0, 42)]
    df = pd.DataFrame([[None] * 42, [None] * 42], columns=cols)
    # 第2行（index=1）作为有效数据行
    df.iloc[1, 8] = "B"  # I列 -> process1
    df.iloc[1, 37] = "河北分公司-建筑结构所xxx"  # AL列 -> process2
    df.iloc[1, 12] = "2028.03.15"  # M列远未来 -> 应被时间窗口排除
    df.iloc[1, 19] = ""  # T列为空 -> process6
    df.iloc[1, 16] = ""  # Q列为空 -> process5
    df.iloc[1, 2] = "INT-001"  # C列接口号
    df.iloc[1, 40] = "结构一室"  # AO列科室（不影响本测试）
    df.iloc[1, 41] = ""  # AP列责任人（可空）

    excel_path = tmp_path / "2026_待处理文件3.xlsx"
    df.to_excel(excel_path, index=False)

    # 2) 构造一个临时 registry.db，并插入一条“待审查”任务（同 interface_id + project_id）
    reg_dir = tmp_path / ".registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    db_path = reg_dir / "registry.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            file_type INTEGER NOT NULL,
            project_id TEXT NOT NULL,
            interface_id TEXT NOT NULL,
            source_file TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            display_status TEXT DEFAULT NULL,
            ignored INTEGER DEFAULT 0
        )
        """
    )
    # 只要能被 main.py 的查询捞到即可：file_type=3, display_status in ('待审查','待指派人审查'), ignored=0, status != archived
    conn.execute(
        """
        INSERT OR REPLACE INTO tasks(id, file_type, project_id, interface_id, source_file, row_index, status, display_status, ignored)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("tid-1", 3, "2026", "INT-001", os.path.basename(str(excel_path)), 3, "completed", "待审查", 0),
    )
    conn.commit()
    conn.close()

    # 3) patch registry.hooks._cfg() 指向这个临时db
    from registry import hooks as registry_hooks

    def _fake_cfg():
        return {
            "registry_enabled": True,
            "registry_db_path": str(db_path),
            "registry_wal": False,
        }

    monkeypatch.setattr(registry_hooks, "_cfg", _fake_cfg, raising=True)

    # 4) 运行文件3处理：由于时间窗口不包含2028，这条行应始终被排除（即使registry试图加回）
    now = datetime(2025, 12, 12, 10, 0, 0)  # 12号（<=19），时间窗口应为当年1/1~12/31
    result = main.process_target_file3(str(excel_path), now)
    assert result is not None
    assert result.empty


