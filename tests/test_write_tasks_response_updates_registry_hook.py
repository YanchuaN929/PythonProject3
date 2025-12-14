def test_response_executor_calls_registry_hook(monkeypatch):
    # 延迟导入，避免测试加载时触发线程等副作用
    import write_tasks.executors as executors
    import input_handler
    from registry import hooks as registry_hooks

    called = {"ok": False, "args": None, "kwargs": None}

    def fake_write_response_to_excel(**kwargs):
        return True

    def fake_on_response_written(*args, **kwargs):
        called["ok"] = True
        called["args"] = args
        called["kwargs"] = kwargs

    monkeypatch.setattr(input_handler, "write_response_to_excel", fake_write_response_to_excel, raising=True)
    monkeypatch.setattr(registry_hooks, "on_response_written", fake_on_response_written, raising=True)

    payload = {
        "file_path": "D:/Programs/接口筛选/测试文件/a.xlsx",
        "file_type": 4,
        "row_index": 12,
        "interface_id": "S-GT---1JJ-06-25C2-25C3(设计人员)",
        "response_number": "XYZ-001",
        "user_name": "张三",
        "project_id": "1818",
        "source_column": None,
        "role": "设计人员",
    }
    ok = executors.execute_response_task(payload)
    assert ok is True
    assert called["ok"] is True
    # interface_id应去除角色后缀
    assert called["kwargs"]["interface_id"] == "S-GT---1JJ-06-25C2-25C3"
    assert called["kwargs"]["project_id"] == "1818"


