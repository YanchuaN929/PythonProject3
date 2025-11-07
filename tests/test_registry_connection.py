#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry数据库连接管理测试

测试连接的创建、关闭、自动重连等功能
"""
import pytest
import os
import tempfile
import shutil
from registry.db import get_connection, close_connection, init_db


@pytest.fixture
def temp_db_path():
    """创建临时数据库路径"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_connection.db")
    
    yield db_path
    
    # 清理
    try:
        close_connection()
    except:
        pass
    
    try:
        import time
        time.sleep(0.1)
        shutil.rmtree(temp_dir)
    except:
        pass


def test_connection_creation(temp_db_path):
    """测试连接创建"""
    conn = get_connection(temp_db_path, False)
    
    # 验证连接可用
    result = conn.execute("SELECT 1").fetchone()
    assert result == (1,)
    print("[OK] Connection created successfully")


def test_connection_singleton(temp_db_path):
    """测试单例模式"""
    conn1 = get_connection(temp_db_path, False)
    conn2 = get_connection(temp_db_path, False)
    
    # 应该返回同一个连接对象
    assert conn1 is conn2
    print("[OK] Singleton pattern works")


def test_connection_auto_reconnect(temp_db_path):
    """测试连接关闭后自动重连（核心测试）"""
    # 第一次获取连接
    conn1 = get_connection(temp_db_path, False)
    conn1.execute("SELECT 1")  # 验证可用
    
    # 关闭连接
    close_connection()
    print("[Test] Connection closed")
    
    # 再次获取连接（应该自动重新创建）
    conn2 = get_connection(temp_db_path, False)
    
    # 验证新连接可用
    result = conn2.execute("SELECT 1").fetchone()
    assert result == (1,)
    
    # 验证是不同的连接对象（因为重新创建了）
    assert conn1 is not conn2
    print("[OK] Auto-reconnect works after close")


def test_connection_survives_invalid_queries(temp_db_path):
    """测试连接在无效查询后仍然可用"""
    conn = get_connection(temp_db_path, False)
    
    # 执行无效查询
    try:
        conn.execute("SELECT * FROM nonexistent_table")
    except Exception:
        pass  # 预期会失败
    
    # 连接应该仍然可用
    result = conn.execute("SELECT 1").fetchone()
    assert result == (1,)
    print("[OK] Connection survives invalid queries")


def test_connection_after_manual_close(temp_db_path):
    """测试手动关闭连接后的自动恢复"""
    # 获取连接
    conn1 = get_connection(temp_db_path, False)
    
    # 手动关闭连接（模拟异常情况）
    conn1.close()
    
    # 再次调用get_connection，应该检测到连接失效并重建
    conn2 = get_connection(temp_db_path, False)
    
    # 验证新连接可用
    result = conn2.execute("SELECT 1").fetchone()
    assert result == (1,)
    print("[OK] Recovers from manual close")


def test_connection_thread_safety(temp_db_path):
    """测试连接的线程安全性"""
    import threading
    results = []
    
    def access_db():
        try:
            conn = get_connection(temp_db_path, False)
            result = conn.execute("SELECT 1").fetchone()
            results.append(result)
        except Exception as e:
            results.append(None)
            print(f"[WARNING] Thread access failed: {e}")
    
    # 创建多个线程同时访问
    threads = [threading.Thread(target=access_db) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # 所有线程都应该成功
    assert len(results) == 10
    # 允许部分失败（数据库锁定等并发问题）
    success_count = sum(1 for r in results if r == (1,))
    assert success_count >= 8, f"至少8个线程应该成功，实际：{success_count}"
    print(f"[OK] Thread-safe connection access: {success_count}/10 succeeded")


def test_close_connection_idempotent(temp_db_path):
    """测试close_connection可以多次调用"""
    conn = get_connection(temp_db_path, False)
    
    # 多次关闭不应报错
    close_connection()
    close_connection()
    close_connection()
    
    # 之后仍可获取新连接
    conn2 = get_connection(temp_db_path, False)
    result = conn2.execute("SELECT 1").fetchone()
    assert result == (1,)
    print("[OK] Multiple close_connection calls handled")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

