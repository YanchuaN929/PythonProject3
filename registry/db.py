"""
数据库操作模块

提供SQLite连接管理、建表和基础CRUD操作。

【重要】网络盘兼容性说明：
SQLite 在网络文件系统上有严重的锁定问题。本模块实现了以下策略：
1. 自动检测网络路径，禁用 WAL 模式
2. 使用短连接模式，减少锁持有时间
3. 智能重试机制，应对临时锁定
"""
import sqlite3
import os
import time
import random
from threading import Lock
from typing import Optional, Callable, TypeVar

# 全局连接缓存和锁
_CONN: Optional[sqlite3.Connection] = None
_LOCK = Lock()
_IS_NETWORK_PATH: Optional[bool] = None  # 缓存网络路径检测结果
_DB_PATH: Optional[str] = None  # 缓存数据库路径
_FORCE_NETWORK_MODE: bool = False  # 强制使用网络模式（用于本地测试）

T = TypeVar('T')


class MaintenanceModeError(RuntimeError):
    """Registry 维护模式异常（用于协作式释放连接）。"""


def _get_data_folder_from_db_path(db_path: str) -> str:
    """从数据库路径推导数据目录（data_folder）。"""
    registry_dir = os.path.dirname(db_path)
    return os.path.dirname(registry_dir)


def get_maintenance_flag_path(db_path: Optional[str] = None, data_folder: Optional[str] = None) -> str:
    """获取维护标志路径：<data_folder>/.registry/maintenance.lock"""
    base_folder = data_folder or (_get_data_folder_from_db_path(db_path) if db_path else None)
    if not base_folder:
        raise ValueError("data_folder 和 db_path 不能同时为空")
    return os.path.join(base_folder, ".registry", "maintenance.lock")


def is_maintenance_mode(db_path: Optional[str] = None, data_folder: Optional[str] = None) -> bool:
    """检查是否处于维护模式（存在维护标志文件）。"""
    try:
        flag_path = get_maintenance_flag_path(db_path=db_path, data_folder=data_folder)
    except Exception:
        return False
    return os.path.exists(flag_path)


def ensure_not_in_maintenance(db_path: Optional[str] = None, data_folder: Optional[str] = None) -> None:
    """检测维护模式，若开启则抛出异常。"""
    if is_maintenance_mode(db_path=db_path, data_folder=data_folder):
        raise MaintenanceModeError("Registry 正在维护中，请稍后重试")


def enable_maintenance_mode(data_folder: str) -> str:
    """开启维护模式（创建维护标志文件）。"""
    flag_path = get_maintenance_flag_path(data_folder=data_folder)
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write(time.strftime("enabled_at=%Y-%m-%d %H:%M:%S", time.localtime()))
    return flag_path


def disable_maintenance_mode(data_folder: str) -> bool:
    """关闭维护模式（删除维护标志文件）。"""
    flag_path = get_maintenance_flag_path(data_folder=data_folder)
    if os.path.exists(flag_path):
        os.remove(flag_path)
        return True
    return False


def close_connection_after_use() -> None:
    """便捷关闭连接（用于读写结束后立即释放）。"""
    try:
        close_connection()
    except Exception:
        pass


def set_force_network_mode(enabled: bool = True) -> None:
    """
    强制使用网络模式（用于本地开发测试）
    
    启用后，即使数据库路径是本地路径，也会：
    - 禁用 WAL 模式，使用 DELETE 模式
    - 使用更长的超时时间
    - 禁用内存映射
    - 启用重试机制
    
    参数:
        enabled: True 强制网络模式，False 自动检测
    """
    global _FORCE_NETWORK_MODE, _IS_NETWORK_PATH
    _FORCE_NETWORK_MODE = enabled
    _IS_NETWORK_PATH = None  # 重置缓存，下次连接时重新评估
    
    # 控制台输出优化：已验证逻辑，默认不输出

def _is_network_path(path: str) -> bool:
    """
    检测路径是否为网络路径
    
    参数:
        path: 文件路径
        
    返回:
        True 如果是网络路径（UNC路径或映射的网络驱动器）
    """
    # UNC 路径 (\\server\share)
    if path.startswith('\\\\') or path.startswith('//'):
        return True
    
    # 检查是否是映射的网络驱动器（Windows）
    try:
        import ctypes
        
        drive = os.path.splitdrive(path)[0]
        if drive and len(drive) >= 2:
            # GetDriveType: 4 = DRIVE_REMOTE (网络驱动器)
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + '\\')
            if drive_type == 4:
                return True
    except Exception:
        pass
    
    return False


def _cleanup_wal_files(db_path: str) -> None:
    """
    清理WAL模式的辅助文件（-shm和-wal）
    
    当从WAL模式切换到DELETE模式时调用，避免残留文件导致问题。
    
    参数:
        db_path: 数据库文件路径
    """
    wal_file = db_path + "-wal"
    shm_file = db_path + "-shm"
    
    for f in [wal_file, shm_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f"[Registry] 已清理旧WAL文件: {os.path.basename(f)}")
            except PermissionError:
                print(f"[Registry] 警告: 无法删除 {os.path.basename(f)}，文件可能被占用")
            except Exception as e:
                print(f"[Registry] 清理WAL文件失败: {e}")


def execute_with_retry(
    func: Callable[[], T],
    max_retries: int = 5,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
    operation_name: str = "数据库操作"
) -> T:
    """
    带智能重试的数据库操作执行器
    
    使用指数退避 + 随机抖动的重试策略，专门应对网络盘锁定问题。
    
    参数:
        func: 要执行的函数
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        operation_name: 操作名称（用于日志）
    
    返回:
        函数执行结果
    
    抛出:
        最后一次失败的异常
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            
            # 检查是否是锁定相关错误
            if "locked" in error_msg or "busy" in error_msg:
                last_exception = e
                
                if attempt < max_retries:
                    # 指数退避 + 随机抖动
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 0.5), max_delay)
                    print(f"[Registry] {operation_name}被锁定，{delay:.1f}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    
                    # 尝试关闭并重新获取连接
                    close_connection()
                    continue
            else:
                # 非锁定错误，直接抛出
                raise
        except Exception:
            raise
    
    # 所有重试都失败
    print(f"[Registry] {operation_name}在{max_retries}次重试后仍然失败")
    raise last_exception


def get_connection(db_path: str, wal: bool = True) -> sqlite3.Connection:
    """
    获取或创建数据库连接（单例模式）
    
    参数:
        db_path: 数据库文件路径
        wal: 是否启用WAL模式（网络路径自动禁用）
        
    返回:
        sqlite3.Connection 实例
    """
    global _CONN, _IS_NETWORK_PATH, _DB_PATH
    
    # 维护模式检测：若开启则禁止连接
    ensure_not_in_maintenance(db_path=db_path)
    
    with _LOCK:
        # 【修复Bug】检查连接是否已关闭
        if _CONN is not None:
            try:
                # 测试连接是否有效
                _CONN.execute("SELECT 1")
                return _CONN
            except (sqlite3.ProgrammingError, sqlite3.OperationalError):
                # 连接已关闭，需要重新创建
                print("[Registry] 检测到连接已关闭，重新创建...")
                _CONN = None
        
        # 确保目录存在
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # 缓存网络路径检测结果（避免重复检测）
        if _DB_PATH != db_path:
            if _FORCE_NETWORK_MODE:
                _IS_NETWORK_PATH = True
            else:
                _IS_NETWORK_PATH = _is_network_path(db_path)
                # 控制台输出优化：已验证逻辑，默认不输出
            _DB_PATH = db_path
        
        is_network = _IS_NETWORK_PATH or _FORCE_NETWORK_MODE
        
        # 【关键修复】网络路径自动禁用WAL模式
        if is_network and wal:
            wal = False
            # 尝试清理旧的WAL文件
            _cleanup_wal_files(db_path)
        
        # 创建连接，网络路径使用更短的超时（避免长时间阻塞）
        timeout = 30.0 if is_network else 60.0
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=timeout)
        
        # 配置日志模式和性能优化
        try:
            # 设置日志模式
            if wal:
                result = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            else:
                result = conn.execute("PRAGMA journal_mode=DELETE").fetchone()
            
            actual_mode = result[0] if result else "unknown"
            expected_mode = "wal" if wal else "delete"
            
            if actual_mode.lower() != expected_mode:
                print(f"[Registry] 警告: 日志模式设置失败! 期望={expected_mode}, 实际={actual_mode}")
                # 如果是网络路径且模式不对，尝试强制切换
                if is_network and actual_mode.lower() == "wal":
                    print("[Registry] 尝试强制切换到DELETE模式...")
                    # 执行一个空事务来刷新WAL
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("COMMIT")
                    result = conn.execute("PRAGMA journal_mode=DELETE").fetchone()
                    print(f"[Registry] 重试后日志模式: {result[0] if result else 'unknown'}")
            else:
                # 控制台输出优化：已验证逻辑，默认不输出
                pass
            
            # 设置繁忙超时（网络路径使用更长的超时）
            busy_timeout = 60000 if is_network else 30000  # 60秒 或 30秒
            conn.execute(f"PRAGMA busy_timeout={busy_timeout}")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # 网络路径：禁用内存映射，使用传统IO（更可靠）
            if is_network:
                conn.execute("PRAGMA mmap_size=0")
            
        except Exception as e:
            print(f"[Registry] 数据库配置失败: {e}")
        
        # 【关键修复】先检查并迁移数据库，再初始化
        try:
            from .migrate import migrate_if_needed
            migrate_if_needed(db_path)
        except Exception as e:
            print(f"[Registry] 数据库迁移检查失败: {e}")
        
        init_db(conn)
        
        _CONN = conn
        return conn

def init_db(conn: sqlite3.Connection) -> None:
    """
    初始化数据库表结构
    
    参数:
        conn: 数据库连接
    """
    cur = conn.cursor()
    
    # 创建tasks表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            file_type INTEGER NOT NULL,
            project_id TEXT NOT NULL,
            interface_id TEXT NOT NULL,
            source_file TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            business_id TEXT DEFAULT NULL,
            department TEXT DEFAULT '',
            interface_time TEXT DEFAULT '',
            role TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'open',
            completed_at TEXT NULL,
            completed_by TEXT DEFAULT NULL,
            confirmed_at TEXT NULL,
            confirmed_by TEXT DEFAULT NULL,
            assigned_by TEXT DEFAULT NULL,
            assigned_at TEXT DEFAULT NULL,
            display_status TEXT DEFAULT NULL,
            responsible_person TEXT DEFAULT NULL,
            response_number TEXT DEFAULT NULL,
            ignored INTEGER DEFAULT 0,
            ignored_at TEXT DEFAULT NULL,
            ignored_by TEXT DEFAULT NULL,
            interface_time_when_ignored TEXT DEFAULT NULL,
            ignored_reason TEXT DEFAULT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            missing_since TEXT NULL,
            archive_reason TEXT NULL,
            archived_at TEXT NULL
        );
        """
    )
    
    # 创建索引
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_ft_pid ON tasks(file_type, project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_last_seen ON tasks(last_seen_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_business_id ON tasks(business_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_ignored ON tasks(ignored, status);")
    # 2025-12-08: 新增索引优化 Registry 查询性能
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_interface_id ON tasks(interface_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_display_status ON tasks(display_status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_lookup ON tasks(file_type, project_id, interface_id);")
    
    # 创建events表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event TEXT NOT NULL,
            file_type INTEGER,
            project_id TEXT,
            interface_id TEXT,
            source_file TEXT,
            row_index INTEGER,
            extra TEXT
        );
        """
    )
    
    # 为events表创建索引
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_ft_pid ON events(file_type, project_id);")
    
    # 创建ignored_snapshots表（忽略时的快照数据，用于检测变化）
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ignored_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_type INTEGER NOT NULL,
            project_id TEXT NOT NULL,
            interface_id TEXT NOT NULL,
            source_file TEXT NOT NULL,
            row_index INTEGER NOT NULL,
            snapshot_interface_time TEXT,
            snapshot_completed_col TEXT,
            ignored_at TEXT NOT NULL,
            ignored_by TEXT,
            ignored_reason TEXT,
            UNIQUE(file_type, project_id, interface_id, source_file, row_index)
        );
        """
    )
    
    # 为ignored_snapshots表创建索引
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ignored_snapshots_key ON ignored_snapshots(file_type, project_id, interface_id);")
    
    conn.commit()

def close_connection():
    """关闭全局数据库连接"""
    global _CONN
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:
                pass
            _CONN = None


def is_network_database() -> bool:
    """检查当前数据库是否在网络路径上（或强制网络模式）"""
    return _IS_NETWORK_PATH or _FORCE_NETWORK_MODE


# ============================================================
# 读写分离支持（第二阶段优化）
# ============================================================

_local_cache_manager = None
_local_cache_enabled = True  # 默认启用


def set_local_cache_enabled(enabled: bool = True) -> None:
    """
    设置是否启用本地只读缓存
    
    参数:
        enabled: True 启用，False 禁用
    """
    global _local_cache_enabled, _local_cache_manager
    _local_cache_enabled = enabled
    
    if not enabled and _local_cache_manager:
        _local_cache_manager.set_enabled(False)
    elif enabled and _local_cache_manager:
        _local_cache_manager.set_enabled(True)
    
    print(f"[Registry] 本地缓存{'已启用' if enabled else '已禁用'}")


def get_read_connection(db_path: str) -> sqlite3.Connection:
    """
    获取只读连接（优先使用本地缓存）
    
    对于网络盘数据库，使用本地缓存可以：
    - 避免网络IO延迟
    - 减少锁竞争
    - 提高读取速度
    
    参数:
        db_path: 数据库路径
        
    返回:
        sqlite3.Connection（本地缓存或直连）
    """
    global _local_cache_manager
    
    # 维护模式检测：若开启则禁止读取
    ensure_not_in_maintenance(db_path=db_path)
    
    # 检查是否为网络路径且启用了本地缓存
    if _local_cache_enabled and _is_network_path(db_path):
        try:
            if _local_cache_manager is None:
                from registry.local_cache import LocalCacheManager
                from registry.config import get_config
                
                config = get_config()
                sync_interval = config.get('registry_local_cache_sync_interval', 300)
                
                _local_cache_manager = LocalCacheManager(
                    db_path, 
                    sync_interval=sync_interval
                )
            
            # 尝试获取本地缓存连接
            local_conn = _local_cache_manager.get_read_connection()
            if local_conn:
                return local_conn
                
        except Exception as e:
            print(f"[Registry] 本地缓存初始化失败，降级为直连: {e}")
    
    # 降级：直接连接（本地路径或缓存不可用）
    return get_connection(db_path, wal=not _is_network_path(db_path))


def get_write_connection(db_path: str) -> sqlite3.Connection:
    """
    获取写入连接（直接连接网络盘）
    
    写入操作必须直接操作网络盘数据库，确保数据一致性。
    
    参数:
        db_path: 数据库路径
        
    返回:
        sqlite3.Connection
    """
    # 维护模式检测：若开启则禁止写入
    ensure_not_in_maintenance(db_path=db_path)
    # 写入时使用网络盘数据库的直连
    return get_connection(db_path, wal=not _is_network_path(db_path))


def invalidate_read_cache():
    """
    使读缓存失效（写入操作后调用）
    
    每次写入网络盘数据库后，应调用此函数使本地缓存失效，
    确保下次读取时能获取最新数据。
    """
    global _local_cache_manager
    if _local_cache_manager:
        _local_cache_manager.invalidate_cache()


def force_sync_cache() -> bool:
    """
    强制同步缓存（手动刷新时调用）
    
    返回:
        True = 同步成功，False = 同步失败
    """
    global _local_cache_manager
    if _local_cache_manager:
        return _local_cache_manager.force_sync()
    return False


def get_cache_info() -> dict:
    """
    获取缓存信息（用于调试/状态显示）
    
    返回:
        包含缓存状态的字典
    """
    global _local_cache_manager
    if _local_cache_manager:
        return _local_cache_manager.get_cache_info()
    return {'enabled': _local_cache_enabled, 'initialized': False}

