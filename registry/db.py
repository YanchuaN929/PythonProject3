"""
数据库操作模块

提供SQLite连接管理、建表和基础CRUD操作。
"""
import sqlite3
import os
from threading import Lock
from typing import Optional

# 全局连接缓存和锁
_CONN: Optional[sqlite3.Connection] = None
_LOCK = Lock()

def get_connection(db_path: str, wal: bool = True) -> sqlite3.Connection:
    """
    获取或创建数据库连接（单例模式）
    
    参数:
        db_path: 数据库文件路径
        wal: 是否启用WAL模式
        
    返回:
        sqlite3.Connection 实例
    """
    global _CONN
    
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
        
        # 创建连接
        conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
        
        # 配置WAL模式和其他性能优化
        try:
            if wal:
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception as e:
            print(f"[Registry] 数据库配置失败: {e}")
        
        init_db(conn)
        
        # 【数据库迁移】检查并升级旧数据库
        try:
            from .migrate import migrate_if_needed
            migrate_if_needed(db_path)
        except Exception as e:
            print(f"[Registry] 数据库迁移检查失败: {e}")
        
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
            confirmed_at TEXT NULL,
            assigned_by TEXT DEFAULT NULL,
            assigned_at TEXT DEFAULT NULL,
            display_status TEXT DEFAULT NULL,
            confirmed_by TEXT DEFAULT NULL,
            responsible_person TEXT DEFAULT NULL,
            response_number TEXT DEFAULT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            missing_since TEXT NULL,
            archive_reason TEXT NULL,
            UNIQUE(file_type, project_id, interface_id, source_file, row_index)
        );
        """
    )
    
    # 创建索引
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_ft_pid ON tasks(file_type, project_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_last_seen ON tasks(last_seen_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_business_id ON tasks(business_id);")
    
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
    
    conn.commit()

def close_connection():
    """关闭全局数据库连接"""
    global _CONN
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except:
                pass
            _CONN = None

