import os


def test_load_config_no_makedirs_when_deferred(monkeypatch):
    """
    启动阶段用于“只计算路径，不触网”的模式：
    ensure_registry_dir=False 时不应调用 os.makedirs。
    """
    from registry.config import load_config

    called = {"makedirs": False}

    def _makedirs(*args, **kwargs):
        called["makedirs"] = True
        raise AssertionError("os.makedirs 不应在 ensure_registry_dir=False 时被调用")

    monkeypatch.setattr(os, "makedirs", _makedirs)

    data_folder = r"\\10.102.2.7\文件服务器\建筑结构所\接口文件\各项目内外部接口手册"
    cfg = load_config(data_folder=data_folder, ensure_registry_dir=False)

    assert called["makedirs"] is False
    assert cfg["registry_db_path"]
    assert ".registry" in cfg["registry_db_path"]
    assert cfg["registry_db_path"].endswith(os.path.join(".registry", "registry.db"))


def test_load_config_calls_makedirs_and_fallback_on_error(monkeypatch):
    """
    刷新阶段用于“允许触网/确保目录”的模式：
    ensure_registry_dir=True 时会尝试 os.makedirs；失败则回退到本地 result_cache/registry.db。
    """
    from registry.config import load_config

    called = {"makedirs": False}

    def _makedirs(*args, **kwargs):
        called["makedirs"] = True
        raise OSError("simulated network failure")

    monkeypatch.setattr(os, "makedirs", _makedirs)

    data_folder = r"\\10.102.2.7\文件服务器\建筑结构所\接口文件\各项目内外部接口手册"
    cfg = load_config(data_folder=data_folder, ensure_registry_dir=True)

    assert called["makedirs"] is True
    assert "result_cache" in os.path.normcase(cfg["registry_db_path"])


