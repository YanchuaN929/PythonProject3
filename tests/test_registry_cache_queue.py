"""
测试 Registry 本地缓存和写入队列功能

测试内容：
1. LocalCacheManager - 本地只读缓存
2. WriteQueue - 写入队列化
3. 读写分离函数
"""

import pytest
import sqlite3
import tempfile
import os
import time
import threading

from registry.local_cache import LocalCacheManager, get_cache_manager, cleanup_global_cache
from registry.write_queue import WriteQueue, WriteOperation, get_write_queue, shutdown_write_queue
from registry.db import (
    get_connection, close_connection, init_db,
    get_read_connection, get_write_connection, 
    invalidate_read_cache, set_local_cache_enabled
)


class TestLocalCacheManager:
    """测试本地缓存管理器（基础功能）"""
    
    def test_init_creates_cache_dir(self):
        """测试初始化时创建缓存目录"""
        import shutil
        cache_dir = tempfile.mkdtemp()
        cache_subdir = os.path.join(cache_dir, 'test_cache')
        
        # 创建一个临时数据库文件
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            manager = LocalCacheManager(db_path, local_cache_dir=cache_subdir)
            assert os.path.exists(cache_subdir)
            manager.cleanup()
        finally:
            shutil.rmtree(cache_dir, ignore_errors=True)
            try:
                os.unlink(db_path)
            except:
                pass
    
    def test_disabled_cache_returns_none(self):
        """测试禁用缓存时返回None"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        cache_dir = tempfile.mkdtemp()
        
        try:
            manager = LocalCacheManager(db_path, local_cache_dir=cache_dir)
            manager.set_enabled(False)
            
            conn = manager.get_read_connection()
            assert conn is None
            
            manager.cleanup()
        finally:
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            try:
                os.unlink(db_path)
            except:
                pass
    
    def test_get_cache_info_returns_dict(self):
        """测试获取缓存信息返回字典"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        cache_dir = tempfile.mkdtemp()
        
        try:
            manager = LocalCacheManager(db_path, local_cache_dir=cache_dir)
            info = manager.get_cache_info()
            
            assert isinstance(info, dict)
            assert 'enabled' in info
            assert 'network_db_path' in info
            
            manager.cleanup()
        finally:
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)
            try:
                os.unlink(db_path)
            except:
                pass


class TestWriteQueue:
    """测试写入队列（基础功能）"""
    
    def test_queue_initialization(self):
        """测试队列初始化"""
        queue = WriteQueue(db_path=None, enabled=False)
        
        assert queue.is_enabled() is False
        assert queue.get_queue_size() == 0
        
    def test_disabled_queue_properties(self):
        """测试禁用队列的属性"""
        queue = WriteQueue(db_path=None, enabled=False)
        
        assert queue.is_enabled() is False
        assert queue.get_queue_size() == 0
        
        # 验证统计初始状态
        stats = queue.get_stats()
        assert stats['total_requests'] == 0
        assert stats['total_success'] == 0
    
    def test_queue_stats_initial(self):
        """测试队列统计初始状态"""
        queue = WriteQueue(db_path=None, enabled=False)
        
        stats = queue.get_stats()
        
        assert 'total_requests' in stats
        assert 'total_batches' in stats
        assert 'total_success' in stats
        assert 'total_failed' in stats
    
    def test_set_enabled(self):
        """测试设置启用/禁用"""
        queue = WriteQueue(db_path=None, enabled=False)
        
        assert queue.is_enabled() is False
        
        queue.set_enabled(True)
        assert queue.is_enabled() is True
        
        queue.set_enabled(False)
        assert queue.is_enabled() is False


class TestReadWriteSeparation:
    """测试读写分离（基础功能）"""
    
    def test_set_local_cache_enabled(self):
        """测试设置本地缓存启用/禁用"""
        # 这个测试只验证函数可以正常调用
        set_local_cache_enabled(False)
        set_local_cache_enabled(True)
        # 无异常即通过
    
    def test_invalidate_read_cache_no_error(self):
        """测试使读缓存失效不抛异常"""
        # 即使没有初始化缓存也不应抛异常
        invalidate_read_cache()


class TestHooksIntegration:
    """测试 hooks 集成"""
    
    def test_invalidate_cache_no_error(self):
        """测试 invalidate_cache 不抛异常"""
        from registry.hooks import invalidate_cache
        
        # 即使缓存未初始化也不应抛异常
        invalidate_cache()  # 不应抛异常
    
    def test_get_cache_status_returns_dict(self):
        """测试 get_cache_status 返回字典"""
        from registry.hooks import get_cache_status
        
        status = get_cache_status()
        
        assert isinstance(status, dict)
    
    def test_get_write_queue_stats_returns_dict(self):
        """测试 get_write_queue_stats 返回字典"""
        from registry.hooks import get_write_queue_stats
        
        stats = get_write_queue_stats()
        
        assert isinstance(stats, dict)
    
    def test_flush_write_queue_returns_bool(self):
        """测试 flush_write_queue 返回布尔值"""
        from registry.hooks import flush_write_queue
        
        result = flush_write_queue(timeout=1.0)
        
        assert isinstance(result, bool)


class TestConfigIntegration:
    """测试配置集成"""
    
    def test_default_config_has_cache_settings(self):
        """测试默认配置包含缓存设置"""
        from registry.config import DEFAULTS
        
        assert 'registry_local_cache_enabled' in DEFAULTS
        assert 'registry_local_cache_sync_interval' in DEFAULTS
        assert 'registry_write_queue_enabled' in DEFAULTS
        assert 'registry_write_batch_interval' in DEFAULTS
        assert 'registry_write_batch_size' in DEFAULTS
        assert 'registry_query_cache_enabled' in DEFAULTS
    
    def test_get_config_returns_dict(self):
        """测试 get_config 返回字典"""
        from registry.config import get_config
        
        config = get_config()
        
        assert isinstance(config, dict)
        assert 'registry_enabled' in config


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

