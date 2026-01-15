def test_registry_disabled_when_no_data_folder():
    from registry.config import load_config

    cfg = load_config(data_folder=None, ensure_registry_dir=True)
    assert cfg.get("registry_enabled") is False
    assert cfg.get("registry_db_path") in (None, "")
    assert "禁用" in (cfg.get("registry_disabled_reason") or "")


