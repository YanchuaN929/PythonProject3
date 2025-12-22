import json
from pathlib import Path


def test_load_config_prefers_existing_registry_db_in_registry_folder(tmp_path):
    """
    现场信息：
    - 公共盘 DB 实际位于：<data_folder>/registry/registry.db

    当前实现：
    - 默认会使用：<data_folder>/.registry/registry.db

    这个用例用“期望偏好 registry/registry.db”来锁定路径不一致问题：
    修复前应当 FAIL，修复后应当 PASS。
    """
    from registry.config import load_config

    data_folder = tmp_path / "data"
    data_folder.mkdir(parents=True, exist_ok=True)
    # 模拟现场已有的公共盘数据库路径结构：registry/registry.db
    reg_dir = data_folder / "registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    (reg_dir / "registry.db").write_bytes(b"")  # 只需要存在即可

    # 提供一个最小 config.json，避免读取工作区真实 config.json 影响测试
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"registry_force_network_mode": False}, ensure_ascii=False), encoding="utf-8")

    cfg = load_config(config_path=str(config_path), data_folder=str(data_folder), ensure_registry_dir=True)
    db_path = Path(cfg["registry_db_path"])

    assert db_path.as_posix().endswith("/registry/registry.db")


