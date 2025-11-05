"""
配置管理模块

提供默认配置和配置文件加载功能。
"""
import json
import os

# 默认配置
DEFAULTS = {
    "registry_enabled": True,
    # 重要：数据库路径应该指向公共盘，以便多用户共享
    # 默认为None，会自动使用 数据目录/.registry/registry.db
    "registry_db_path": None,
    "registry_missing_keep_days": 7,
    "registry_wal": True,
    # UI过滤相关（第二步UI使用）
    "view_hide_overdue_for_designer_default": True,
    "view_overdue_days_threshold": 30,
}

def load_config(config_path: str = "config.json", data_folder: str = None) -> dict:
    """
    加载配置文件，若不存在或读取失败则返回默认值
    
    参数:
        config_path: 配置文件路径
        data_folder: 数据文件夹路径（用于自动确定数据库位置）
        
    返回:
        配置字典（合并了默认值和文件值）
    """
    config = DEFAULTS.copy()
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # 只更新registry相关的配置
                for key in DEFAULTS.keys():
                    if key in user_config:
                        config[key] = user_config[key]
    except Exception as e:
        print(f"[Registry] 配置文件加载失败，使用默认值: {e}")
    
    # 【多用户协作】如果未指定数据库路径，自动放在数据文件夹下
    if config['registry_db_path'] is None and data_folder:
        registry_dir = os.path.join(data_folder, '.registry')
        config['registry_db_path'] = os.path.join(registry_dir, 'registry.db')
        # 确保目录存在
        try:
            os.makedirs(registry_dir, exist_ok=True)
            print(f"[Registry] 数据库路径: {config['registry_db_path']}")
        except Exception as e:
            print(f"[Registry] 创建数据库目录失败: {e}")
            # 回退到本地
            config['registry_db_path'] = os.path.join("result_cache", "registry.db")
    elif config['registry_db_path'] is None:
        # 如果没有数据文件夹，使用本地路径（向后兼容）
        config['registry_db_path'] = os.path.join("result_cache", "registry.db")
    
    return config

