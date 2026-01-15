import os


def test_write_task_cache_permission_error_degrades(monkeypatch, tmp_path):
    """
    当 result_cache 目录不可写时，WriteTaskCache 不应让程序崩溃，而应降级为“仅内存”。
    """
    from write_tasks.cache import WriteTaskCache

    state_path = tmp_path / "result_cache" / "write_tasks_state.json"

    # 模拟 os.makedirs 抛 PermissionError（典型：自启动 working dir/安装目录不可写）
    def _raise_permission_error(*args, **kwargs):
        raise PermissionError(5, "拒绝访问", str(args[0]) if args else "result_cache")

    monkeypatch.setattr(os, "makedirs", _raise_permission_error)

    cache = WriteTaskCache(state_path)
    # disabled 后 load/save 都应安全返回
    assert cache.load() == []
    cache.save([])  # 不应抛异常


