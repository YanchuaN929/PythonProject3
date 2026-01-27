import types


def test_assignment_registry_updates_uses_payload_when_df_missing(tmp_path, monkeypatch):
    """
    回归：指派写入成功后，Registry 更新不应因为 df 读取失败而变成 0。
    应至少使用 assignment payload 的 interface_id/project_id 作为兜底调用 on_assigned。
    """
    import services.distribution as distribution

    # 准备一个“存在且可 r+b 打开”的伪 Excel 文件
    xlsx = tmp_path / "a.xlsx"
    xlsx.write_bytes(b"dummy")

    # 让 read_excel 失败（df=None）
    monkeypatch.setattr(distribution.pd, "read_excel", lambda *a, **k: None)

    # 伪造 workbook/worksheet，满足 ws["A1"]=... 与 save/close
    class DummyWS:
        def __setitem__(self, key, value):
            return None

    class DummyWB:
        def __init__(self):
            self.active = DummyWS()

        def save(self, path):
            # touch
            return None

        def close(self):
            return None

    monkeypatch.setattr(distribution, "load_workbook", lambda *a, **k: DummyWB())

    calls = []
    import registry.hooks as hooks

    def fake_on_assigned(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(hooks, "on_assigned", fake_on_assigned)

    assignments = [
        {
            "file_type": 1,
            "file_path": str(xlsx),
            "row_index": 3,
            "assigned_name": "张三",
            "assigned_by": "李四（接口工程师）",
            "interface_id": "IF-001",
            "project_id": "1907",
        }
    ]

    result = distribution.save_assignments_batch(assignments)
    assert result["success_count"] == 1
    assert result["registry_updates"] == 1
    assert len(calls) == 1
    assert calls[0]["interface_id"] == "IF-001"
    assert calls[0]["project_id"] == "1907"


