"""
本地只读缓存管理

功能：
1. 启动时复制/同步网络盘数据库到本地
2. 所有读操作使用本地缓存
3. 写操作同时更新本地和网络盘
4. 定期检测并同步变化

使用场景：
- 80人同时使用时，避免所有读操作都访问网络盘
- 减少网络IO和锁竞争
"""

import os
import shutil
import sqlite3
import time
import threading
from typing import Optional
from datetime import datetime


class LocalCacheManager:
    """本地缓存管理器"""
    
    def __init__(self, network_db_path: str, local_cache_dir: str = None, 
                 sync_interval: int = 300):
        """
        初始化本地缓存管理器
        
        参数:
            network_db_path: 网络盘数据库路径
            local_cache_dir: 本地缓存目录（默认为用户临时目录）
            sync_interval: 同步间隔（秒），默认5分钟
        """
        self.network_db_path = network_db_path
        self.sync_interval = sync_interval
        
        # 本地缓存目录
        if local_cache_dir is None:
            local_cache_dir = os.path.join(
                os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                'InterfaceFilter',
                'cache'
            )
        
        os.makedirs(local_cache_dir, exist_ok=True)
        self.local_cache_dir = local_cache_dir
        self.local_db_path = os.path.join(local_cache_dir, 'registry_local.db')
        self.last_sync_time = None
        self._local_conn = None
        self._lock = threading.Lock()
        self._enabled = True
    
    def is_enabled(self) -> bool:
        """检查本地缓存是否启用"""
        return self._enabled
    
    def set_enabled(self, enabled: bool):
        """设置本地缓存是否启用"""
        self._enabled = enabled
        if not enabled:
            self._close_local_conn()
    
    def ensure_local_cache(self) -> bool:
        """
        确保本地缓存存在且有效
        
        返回:
            True = 缓存可用, False = 需要从网络盘同步
        """
        if not self._enabled:
            return False
            
        with self._lock:
            # 检查网络盘数据库是否存在
            if not os.path.exists(self.network_db_path):
                print(f"[LocalCache] 网络盘数据库不存在: {self.network_db_path}")
                return False
            
            if not os.path.exists(self.local_db_path):
                return self._full_sync()
            
            # 检查本地缓存是否过期
            try:
                local_mtime = os.path.getmtime(self.local_db_path)
                if time.time() - local_mtime > self.sync_interval:
                    return self._incremental_sync()
            except OSError:
                return self._full_sync()
            
            return True
    
    def _full_sync(self) -> bool:
        """完整同步：复制整个数据库"""
        try:
            print("[LocalCache] 首次同步，复制数据库...")
            
            # 关闭现有连接
            self._close_local_conn_internal()
            
            # 复制文件（带重试）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    shutil.copy2(self.network_db_path, self.local_db_path)
                    break
                except (IOError, OSError) as e:
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                    else:
                        raise e
            
            self.last_sync_time = datetime.now()
            print(f"[LocalCache] 同步完成: {self.local_db_path}")
            return True
            
        except Exception as e:
            print(f"[LocalCache] 同步失败: {e}")
            return False
    
    def _incremental_sync(self) -> bool:
        """增量同步：检查是否需要更新"""
        try:
            # 获取网络盘最后更新时间
            network_mtime = os.path.getmtime(self.network_db_path)
            local_mtime = os.path.getmtime(self.local_db_path)
            
            if network_mtime <= local_mtime:
                # 网络盘没有更新，无需同步
                # 更新本地文件时间以延长缓存有效期
                os.utime(self.local_db_path, None)
                return True
            
            print("[LocalCache] 检测到网络盘更新，重新同步...")
            return self._full_sync()
            
        except Exception as e:
            print(f"[LocalCache] 增量同步检查失败: {e}")
            # 降级：直接使用现有缓存
            return os.path.exists(self.local_db_path)
    
    def get_read_connection(self) -> Optional[sqlite3.Connection]:
        """
        获取只读连接（使用本地缓存）
        
        返回:
            sqlite3.Connection 或 None（如果缓存不可用）
        """
        if not self._enabled:
            return None
            
        with self._lock:
            if self._local_conn is None:
                if not self.ensure_local_cache():
                    return None
                    
                try:
                    self._local_conn = sqlite3.connect(
                        self.local_db_path,
                        check_same_thread=False,
                        timeout=5.0
                    )
                    # 设置为只读模式
                    self._local_conn.execute("PRAGMA query_only = ON")
                    print("[LocalCache] 本地缓存连接已建立")
                except Exception as e:
                    print(f"[LocalCache] 创建本地连接失败: {e}")
                    return None
                    
            return self._local_conn
    
    def _close_local_conn_internal(self):
        """内部方法：关闭本地连接（不加锁）"""
        if self._local_conn:
            try:
                self._local_conn.close()
            except Exception:
                pass
            self._local_conn = None
    
    def _close_local_conn(self):
        """关闭本地连接"""
        with self._lock:
            self._close_local_conn_internal()
    
    def invalidate_cache(self):
        """标记缓存失效，下次读取时重新同步"""
        with self._lock:
            self._close_local_conn_internal()
            if os.path.exists(self.local_db_path):
                try:
                    # 修改文件时间为很久以前，触发下次同步
                    os.utime(self.local_db_path, (0, 0))
                    print("[LocalCache] 缓存已标记为失效")
                except OSError as e:
                    print(f"[LocalCache] 标记缓存失效失败: {e}")
    
    def force_sync(self) -> bool:
        """强制同步（用户手动刷新时调用）"""
        with self._lock:
            self._close_local_conn_internal()
            return self._full_sync()
    
    def get_cache_info(self) -> dict:
        """获取缓存信息（用于调试/显示）"""
        info = {
            'enabled': self._enabled,
            'network_db_path': self.network_db_path,
            'local_db_path': self.local_db_path,
            'sync_interval': self.sync_interval,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'cache_exists': os.path.exists(self.local_db_path),
            'connection_active': self._local_conn is not None,
        }
        
        if os.path.exists(self.local_db_path):
            try:
                info['cache_size_kb'] = os.path.getsize(self.local_db_path) // 1024
                info['cache_mtime'] = datetime.fromtimestamp(
                    os.path.getmtime(self.local_db_path)
                ).isoformat()
            except OSError:
                pass
        
        return info
    
    def cleanup(self):
        """清理资源"""
        self._close_local_conn()
    
    def __del__(self):
        """析构时清理"""
        try:
            self.cleanup()
        except Exception:
            pass


# 模块级单例
_cache_manager: Optional[LocalCacheManager] = None
_cache_lock = threading.Lock()


def get_cache_manager(network_db_path: str = None, 
                      sync_interval: int = 300) -> Optional[LocalCacheManager]:
    """
    获取全局缓存管理器单例
    
    参数:
        network_db_path: 网络盘数据库路径（首次调用时必须提供）
        sync_interval: 同步间隔（秒）
    
    返回:
        LocalCacheManager 实例
    """
    global _cache_manager
    
    with _cache_lock:
        if _cache_manager is None:
            if network_db_path is None:
                return None
            _cache_manager = LocalCacheManager(network_db_path, sync_interval=sync_interval)
        elif network_db_path and _cache_manager.network_db_path != network_db_path:
            # 路径变化，重新创建
            _cache_manager.cleanup()
            _cache_manager = LocalCacheManager(network_db_path, sync_interval=sync_interval)
        
        return _cache_manager


def invalidate_global_cache():
    """使全局缓存失效"""
    global _cache_manager
    if _cache_manager:
        _cache_manager.invalidate_cache()


def cleanup_global_cache():
    """清理全局缓存"""
    global _cache_manager
    with _cache_lock:
        if _cache_manager:
            _cache_manager.cleanup()
            _cache_manager = None

