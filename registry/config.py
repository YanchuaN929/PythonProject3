"""
配置管理模块

提供默认配置和配置文件加载功能。
"""
import json
import os
import sys

# 默认配置
DEFAULTS = {
    "registry_enabled": True,
    # 重要：数据库路径应该指向公共盘，以便多用户共享
    # 默认为None，会自动使用 数据目录/.registry/registry.db
    "registry_db_path": None,
    "registry_missing_keep_days": 7,
    # 固定使用DELETE模式（不再使用WAL，避免网络盘/多用户锁问题）
    "registry_wal": False,
    # 【新增】强制网络模式：本地路径也使用网络兼容设置（用于开发测试）
    "registry_force_network_mode": True,
    
    # ============================================================
    # 本地缓存配置（第二阶段优化）
    # ============================================================
    "registry_local_cache_enabled": True,      # 是否启用本地只读缓存
    "registry_local_cache_sync_interval": 600, # 同步间隔（秒），默认5分钟
    
    # ============================================================
    # 写入队列配置（第三阶段优化）
    # ============================================================
    "registry_write_queue_enabled": True,      # 是否启用写入队列
    "registry_write_batch_interval": 1.0,      # 批量写入间隔（秒）
    "registry_write_batch_size": 50,           # 单批最大任务数
    
    # ============================================================
    # 查询缓存配置
    # ============================================================
    "registry_query_cache_enabled": True,      # 是否启用查询结果缓存
    "registry_query_cache_ttl": 60,            # 缓存有效期（秒）
    
    # UI过滤相关（第二步UI使用）
    "view_hide_overdue_for_designer_default": False,
    "view_overdue_days_threshold": 30,
    # 禁用原因（仅用于提示，不参与业务逻辑）
    "registry_disabled_reason": "",
}

def load_config(
    config_path: str = "config.json",
    data_folder: str = None,
    *,
    ensure_registry_dir: bool = True
) -> dict:
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
        
        # 【新增】应用强制网络模式设置
        if config.get('registry_force_network_mode', False):
            from .db import set_force_network_mode
            set_force_network_mode(True)
            
    except Exception as e:
        print(f"[Registry] 配置文件加载失败，使用默认值: {e}")
    
    # 【多用户协作】如果未指定数据库路径，自动放在数据文件夹下
    #
    # 注意：ensure_registry_dir=False 时仅“计算出”应使用的 db_path，不做任何文件系统操作，
    # 用于避免程序启动阶段触发网络盘访问（如 UNC 路径不可用导致卡死）。
    if config['registry_db_path'] is None and data_folder:
        # 固定使用新结构：<data_folder>/.registry/registry.db
        registry_dir = os.path.join(data_folder, '.registry')
        new_db_path = os.path.join(registry_dir, 'registry.db')
        config['registry_db_path'] = new_db_path
        if ensure_registry_dir:
            # 确保目录存在（可能触发网络盘访问）
            try:
                os.makedirs(registry_dir, exist_ok=True)
                # 数据库路径信息已在db.py的get_connection中打印，这里不再重复输出
            except Exception as e:
                # 关键策略：不再回退到本地 result_cache/registry.db，避免产生“每人一份本地库”
                # 直接禁用 Registry 并提示用户检查公共盘权限/路径
                print(f"[Registry] 创建数据库目录失败，Registry已禁用（不会回退本地库）: {e}")
                config["registry_enabled"] = False
                config["registry_disabled_reason"] = f"无法创建公共盘数据库目录: {e}"
    elif config['registry_db_path'] is None:
        # 如果没有数据文件夹：彻底禁用 Registry（不再生成/使用本地 result_cache/registry.db）
        config["registry_enabled"] = False
        config["registry_db_path"] = None
        config["registry_disabled_reason"] = "未选择数据文件夹，Registry已禁用（不会回退本地库）"
    
    return config


# 全局配置缓存
_config_cache = None


def get_config() -> dict:
    """
    获取当前配置（使用缓存）
    
    返回:
        配置字典
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    else:
        # 如果 hooks 已设置 data_folder，确保缓存里的 db_path 与之同步
        data_folder = None
        try:
            hooks = sys.modules.get("registry.hooks")
            if hooks and hasattr(hooks, "get_data_folder"):
                data_folder = hooks.get_data_folder()
        except Exception:
            data_folder = None
        if data_folder:
            expected_db_path = os.path.join(data_folder, ".registry", "registry.db")
            if _config_cache.get("registry_db_path") != expected_db_path:
                _config_cache = load_config(data_folder=data_folder, ensure_registry_dir=True)
    return _config_cache


def set_config(config: dict):
    """
    设置配置缓存
    
    参数:
        config: 配置字典
    """
    global _config_cache
    _config_cache = config


def reload_config(config_path: str = "config.json", data_folder: str = None) -> dict:
    """
    重新加载配置
    
    参数:
        config_path: 配置文件路径
        data_folder: 数据文件夹路径
        
    返回:
        配置字典
    """
    global _config_cache
    _config_cache = load_config(config_path, data_folder)
    return _config_cache

