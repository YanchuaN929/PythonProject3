from datetime import datetime

import pandas as pd


def test_file3_interface_time_matches_source_column(tmp_path, monkeypatch):
    """
    防回归：文件3筛选路径为L列时，展示的“接口时间”必须来自L列，而不是M列。
    否则会出现“筛选看起来不可能通过(例如M=2028)，但列表里仍显示”的错觉。
    """
    import main

    # 构造最小Excel：让它走 group2（L路径）：
    # group2 = process1 & process2 & process4(L时间) & process5(Q空)
    cols = [f"c{i}" for i in range(0, 42)]
    df = pd.DataFrame([[None] * 42, [None] * 42], columns=cols)
    df.iloc[1, 8] = "B"  # I列 -> process1
    df.iloc[1, 37] = "河北分公司-建筑结构所xxx"  # AL列 -> process2
    df.iloc[1, 11] = "2025.12.31"  # L列在窗口内（12/12，窗口为2025年内）
    df.iloc[1, 12] = "2028.03.15"  # M列远未来（不应被用于展示）
    df.iloc[1, 16] = ""  # Q列为空 -> process5
    df.iloc[1, 19] = "not empty"  # T列非空，确保不走 group1
    df.iloc[1, 2] = "INT-001"
    df.iloc[1, 40] = "结构一室"

    excel_path = tmp_path / "2026_待处理文件3.xlsx"
    df.to_excel(excel_path, index=False)

    # 禁用Registry加回逻辑：让 registry.db 不存在即可
    from registry import hooks as registry_hooks

    def _fake_cfg():
        return {"registry_enabled": False, "registry_db_path": None, "registry_wal": False}

    monkeypatch.setattr(registry_hooks, "_cfg", _fake_cfg, raising=True)

    now = datetime(2025, 12, 12, 10, 0, 0)
    result = main.process_target_file3(str(excel_path), now)
    assert not result.empty
    assert "接口时间" in result.columns
    # 关键断言：展示应来自L列
    assert result.iloc[0]["接口时间"] == "2025.12.31"


