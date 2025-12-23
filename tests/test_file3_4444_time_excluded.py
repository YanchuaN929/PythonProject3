from datetime import datetime

import pandas as pd


def test_file3_4444_year_is_excluded(tmp_path, monkeypatch):
    """
    业务规则：待处理文件3中，如果接口时间以 4444 作为年份（占位/特殊表达），
    则该行不应进入处理结果（不参与时间窗口筛选）。
    """
    import main

    # 构造最小Excel：让它原本应该走 group2（L路径）：
    # group2 = process1 & process2 & process4(L时间) & process5(Q空)
    cols = [f"c{i}" for i in range(0, 42)]
    df = pd.DataFrame([[None] * 42, [None] * 42], columns=cols)
    df.iloc[1, 8] = "B"  # I列 -> process1
    df.iloc[1, 37] = "河北分公司-建筑结构所xxx"  # AL列 -> process2
    df.iloc[1, 11] = "4444.01.15"  # L列：4444年份，占位 -> 应被排除
    df.iloc[1, 16] = ""  # Q列为空 -> process5
    df.iloc[1, 19] = "not empty"  # T列非空，确保不走 group1
    df.iloc[1, 2] = "INT-4444"

    excel_path = tmp_path / "2026_待处理文件3.xlsx"
    df.to_excel(excel_path, index=False)

    # 禁用Registry加回逻辑
    from registry import hooks as registry_hooks

    def _fake_cfg():
        return {"registry_enabled": False, "registry_db_path": None, "registry_wal": False}

    monkeypatch.setattr(registry_hooks, "_cfg", _fake_cfg, raising=True)

    now = datetime(2025, 12, 12, 10, 0, 0)
    out = main.process_target_file3(str(excel_path), now)

    assert out.empty, "4444年份占位的行不应进入文件3处理结果"


