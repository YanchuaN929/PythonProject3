"""
测试数据库网络路径检测和WAL模式禁用功能

确保在网络盘上自动禁用WAL模式，避免独占锁问题。
"""
import pytest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry.db import _is_network_path, _cleanup_wal_files, get_connection, close_connection


class TestIsNetworkPath:
    """测试网络路径检测函数"""
    
    def test_unc_path_double_backslash(self):
        """UNC路径（双反斜杠）应该被识别为网络路径"""
        assert _is_network_path("\\\\10.102.2.7\\share\\folder") == True
    
    def test_unc_path_double_forward_slash(self):
        """UNC路径（双正斜杠）应该被识别为网络路径"""
        assert _is_network_path("//10.102.2.7/share/folder") == True
    
    def test_local_path_c_drive(self):
        """本地C盘路径不应该被识别为网络路径"""
        assert _is_network_path("C:\\Users\\test\\file.db") == False
    
    def test_local_path_d_drive(self):
        """本地D盘路径不应该被识别为网络路径"""
        assert _is_network_path("D:\\Projects\\test.db") == False
    
    def test_relative_path(self):
        """相对路径不应该被识别为网络路径"""
        assert _is_network_path("./data/test.db") == False
    
    def test_empty_path(self):
        """空路径不应该被识别为网络路径"""
        assert _is_network_path("") == False
    
    def test_path_with_special_characters(self):
        """包含特殊字符的路径应正确处理"""
        assert _is_network_path("\\\\server\\建筑结构所\\接口文件") == True


class TestCleanupWalFiles:
    """测试WAL文件清理函数"""
    
    def test_cleanup_existing_wal_files(self):
        """应该能清理存在的WAL文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            wal_path = db_path + "-wal"
            shm_path = db_path + "-shm"
            
            # 创建模拟的WAL文件
            open(wal_path, 'w').close()
            open(shm_path, 'w').close()
            
            assert os.path.exists(wal_path)
            assert os.path.exists(shm_path)
            
            # 清理
            _cleanup_wal_files(db_path)
            
            # 验证文件被删除
            assert not os.path.exists(wal_path)
            assert not os.path.exists(shm_path)
    
    def test_cleanup_nonexistent_files(self):
        """清理不存在的WAL文件不应该报错"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "nonexistent.db")
            
            # 不应该抛出异常
            _cleanup_wal_files(db_path)
    
    def test_cleanup_partial_files(self):
        """只存在部分WAL文件时应该能正确清理"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            wal_path = db_path + "-wal"
            
            # 只创建-wal文件
            open(wal_path, 'w').close()
            
            assert os.path.exists(wal_path)
            
            # 清理
            _cleanup_wal_files(db_path)
            
            # 验证文件被删除
            assert not os.path.exists(wal_path)


class TestGetConnectionNetworkPath:
    """测试网络路径下的数据库连接"""
    
    def teardown_method(self):
        """每个测试后关闭连接"""
        close_connection()
    
    def test_local_path_uses_wal(self):
        """本地路径应该使用WAL模式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "local_test.db")
            
            close_connection()  # 确保没有现有连接
            conn = get_connection(db_path, wal=True)
            
            # 查询当前日志模式
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0].lower()
            
            # 关闭连接后再验证，避免临时目录删除失败
            close_connection()
            
            assert mode == "wal", f"本地路径应该使用WAL模式，实际是: {mode}"
    
    def test_network_path_disables_wal(self):
        """网络路径应该自动禁用WAL模式，使用DELETE模式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 模拟网络路径（实际上使用临时目录测试逻辑）
            db_path = os.path.join(tmpdir, "network_test.db")
            
            close_connection()  # 确保没有现有连接
            
            # 模拟 _is_network_path 返回 True
            with patch('registry.db._is_network_path', return_value=True):
                conn = get_connection(db_path, wal=True)
                
                # 查询当前日志模式
                cursor = conn.execute("PRAGMA journal_mode")
                mode = cursor.fetchone()[0].lower()
                
                # 关闭连接
                close_connection()
                
                assert mode == "delete", f"网络路径应该使用DELETE模式，实际是: {mode}"
    
    def test_increased_busy_timeout_for_network(self):
        """网络路径应该有更长的繁忙超时时间（60秒）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "timeout_test.db")
            
            close_connection()
            
            with patch('registry.db._is_network_path', return_value=True):
                conn = get_connection(db_path, wal=True)
                
                # 查询繁忙超时
                cursor = conn.execute("PRAGMA busy_timeout")
                timeout = cursor.fetchone()[0]
                
                # 关闭连接
                close_connection()
                
                # 网络路径使用更长的超时：60000ms (60秒)
                assert timeout == 60000, f"网络路径繁忙超时应该是60000ms，实际是: {timeout}"


class TestConnectionSingleton:
    """测试连接单例模式"""
    
    def teardown_method(self):
        """每个测试后关闭连接"""
        close_connection()
    
    def test_same_connection_returned(self):
        """多次调用应该返回同一个连接"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "singleton_test.db")
            
            close_connection()
            conn1 = get_connection(db_path)
            conn2 = get_connection(db_path)
            
            is_same = conn1 is conn2
            
            # 关闭连接
            close_connection()
            
            assert is_same, "应该返回同一个连接对象"
    
    def test_close_connection_works(self):
        """关闭连接后应该能创建新连接"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "close_test.db")
            
            close_connection()
            conn1 = get_connection(db_path)
            
            # 关闭连接
            close_connection()
            
            # 应该能创建新连接
            conn2 = get_connection(db_path)
            
            # 新连接应该是有效的
            cursor = conn2.execute("SELECT 1")
            result = cursor.fetchone()[0]
            
            # 关闭连接
            close_connection()
            
            assert result == 1


class TestDatabaseInitialization:
    """测试数据库初始化"""
    
    def teardown_method(self):
        """每个测试后关闭连接"""
        close_connection()
    
    def test_tables_created(self):
        """应该自动创建必要的表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "init_test.db")
            
            close_connection()
            conn = get_connection(db_path)
            
            # 检查tasks表
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
            )
            tasks_exists = cursor.fetchone() is not None
            
            # 检查events表
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
            )
            events_exists = cursor.fetchone() is not None
            
            # 检查ignored_snapshots表
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ignored_snapshots'"
            )
            snapshots_exists = cursor.fetchone() is not None
            
            # 关闭连接
            close_connection()
            
            assert tasks_exists, "tasks表应该存在"
            assert events_exists, "events表应该存在"
            assert snapshots_exists, "ignored_snapshots表应该存在"

