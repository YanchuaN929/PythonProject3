#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库状态显示器单元测试
测试db_status.py模块的核心功能
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# 确保项目根目录在sys.path中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_status import (
    DatabaseStatus,
    DatabaseStatusIndicator,
    set_db_status_indicator,
    get_db_status_indicator,
    notify_syncing,
    notify_connected,
    notify_error,
    notify_waiting,
    _global_indicator
)


class TestDatabaseStatus:
    """测试DatabaseStatus枚举类"""
    
    def test_status_values(self):
        """测试状态枚举值"""
        assert DatabaseStatus.NOT_CONFIGURED == "not_configured"
        assert DatabaseStatus.CONNECTED == "connected"
        assert DatabaseStatus.SYNCING == "syncing"
        assert DatabaseStatus.WAITING == "waiting"
        assert DatabaseStatus.ERROR == "error"
    
    def test_all_statuses_defined(self):
        """测试所有状态都已定义"""
        expected_statuses = [
            "not_configured",
            "connected", 
            "syncing",
            "waiting",
            "error"
        ]
        for status in expected_statuses:
            assert hasattr(DatabaseStatus, status.upper())


class TestDatabaseStatusIndicator:
    """测试DatabaseStatusIndicator类"""
    
    @pytest.fixture
    def mock_parent_frame(self):
        """创建模拟的父框架"""
        frame = MagicMock()
        frame.winfo_exists.return_value = True
        return frame
    
    @pytest.fixture
    def indicator(self, mock_parent_frame):
        """创建DatabaseStatusIndicator实例"""
        with patch('tkinter.Label'), \
             patch('tkinter.ttk.Frame'):
            indicator = DatabaseStatusIndicator(mock_parent_frame, row=5, column=0)
            return indicator
    
    def test_init_default_status(self, indicator):
        """测试初始化默认状态为未配置"""
        assert indicator._current_status == DatabaseStatus.NOT_CONFIGURED
    
    def test_status_config_exists(self, indicator):
        """测试所有状态都有对应的配置"""
        statuses = [
            DatabaseStatus.NOT_CONFIGURED,
            DatabaseStatus.CONNECTED,
            DatabaseStatus.SYNCING,
            DatabaseStatus.WAITING,
            DatabaseStatus.ERROR
        ]
        for status in statuses:
            assert status in indicator.STATUS_CONFIG
            config = indicator.STATUS_CONFIG[status]
            assert len(config) == 3  # 图标, 文字, 颜色
    
    def test_set_connected(self, indicator):
        """测试设置已连接状态"""
        with patch.object(indicator, '_update_display'):
            indicator.set_connected(db_path="/test/path.db")
            assert indicator._current_status == DatabaseStatus.CONNECTED
            assert indicator._detail_info.get('db_path') == "/test/path.db"
    
    def test_set_syncing(self, indicator):
        """测试设置同步中状态"""
        with patch.object(indicator, '_update_display'):
            indicator.set_syncing(current=5, total=10)
            assert indicator._current_status == DatabaseStatus.SYNCING
    
    def test_set_waiting(self, indicator):
        """测试设置等待锁定状态"""
        with patch.object(indicator, '_update_display'):
            indicator.set_waiting()
            assert indicator._current_status == DatabaseStatus.WAITING
    
    def test_set_error(self, indicator):
        """测试设置错误状态"""
        with patch.object(indicator, '_update_display'), \
             patch.object(indicator, '_show_error_dialog'):
            indicator.set_error("测试错误信息", show_dialog=False)
            assert indicator._current_status == DatabaseStatus.ERROR
            assert indicator._error_message == "测试错误信息"
    
    def test_set_not_configured(self, indicator):
        """测试设置未配置状态"""
        with patch.object(indicator, '_update_display'):
            # 先设置为其他状态
            indicator._current_status = DatabaseStatus.CONNECTED
            # 再设置为未配置
            indicator.set_not_configured()
            assert indicator._current_status == DatabaseStatus.NOT_CONFIGURED
    
    def test_get_tooltip_text(self, indicator):
        """测试获取tooltip文本"""
        indicator._detail_info = {
            'db_path': '/test/path.db',
            'task_count': 100
        }
        indicator._last_sync_time = datetime(2025, 11, 25, 10, 30, 0)
        
        tooltip = indicator._get_tooltip_text()
        
        # tooltip应该包含路径和时间信息
        assert "路径" in tooltip
        assert "/test/path.db" in tooltip


class TestGlobalIndicatorFunctions:
    """测试全局指示器函数"""
    
    @pytest.fixture(autouse=True)
    def reset_global_indicator(self):
        """每个测试前重置全局指示器"""
        import db_status
        db_status._global_indicator = None
        yield
        db_status._global_indicator = None
    
    def test_set_and_get_indicator(self):
        """测试设置和获取全局指示器"""
        mock_indicator = MagicMock()
        
        set_db_status_indicator(mock_indicator)
        result = get_db_status_indicator()
        
        assert result == mock_indicator
    
    def test_get_indicator_when_none(self):
        """测试获取未设置的指示器"""
        result = get_db_status_indicator()
        assert result is None
    
    def test_notify_syncing(self):
        """测试notify_syncing函数"""
        mock_indicator = MagicMock()
        set_db_status_indicator(mock_indicator)
        
        notify_syncing(current=5, total=10)
        
        mock_indicator.set_syncing.assert_called_once_with(5, 10)
    
    def test_notify_connected(self):
        """测试notify_connected函数"""
        mock_indicator = MagicMock()
        set_db_status_indicator(mock_indicator)
        
        notify_connected(db_path="/test.db", task_count=50)
        
        mock_indicator.set_connected.assert_called_once_with("/test.db", 50)
    
    def test_notify_error(self):
        """测试notify_error函数"""
        mock_indicator = MagicMock()
        set_db_status_indicator(mock_indicator)
        
        notify_error("测试错误", False)
        
        mock_indicator.set_error.assert_called_once_with("测试错误", False)
    
    def test_notify_waiting(self):
        """测试notify_waiting函数"""
        mock_indicator = MagicMock()
        set_db_status_indicator(mock_indicator)
        
        notify_waiting()
        
        mock_indicator.set_waiting.assert_called_once_with()
    
    def test_notify_functions_when_no_indicator(self):
        """测试没有设置指示器时调用notify函数不报错"""
        # 不应该抛出异常
        notify_syncing()
        notify_connected()
        notify_error("test")
        notify_waiting()


class TestWindowManagerIntegration:
    """测试与WindowManager的集成"""
    
    def test_window_manager_creates_db_status(self):
        """测试WindowManager创建数据库状态显示器"""
        with patch('tkinter.Tk') as mock_tk, \
             patch('db_status.DatabaseStatusIndicator') as mock_indicator_class:
            
            mock_root = MagicMock()
            mock_tk.return_value = mock_root
            
            # 模拟ttk.Frame
            with patch('tkinter.ttk.Frame'):
                from window import WindowManager
                
                # WindowManager初始化时应该能访问db_status
                wm = WindowManager(mock_root)
                
                # 确认viewers初始化
                assert 'tab1' in wm.viewers


class TestStatusTransitions:
    """测试状态转换"""
    
    @pytest.fixture
    def indicator(self):
        """创建模拟的指示器"""
        with patch('tkinter.Label'), \
             patch('tkinter.ttk.Frame'):
            mock_parent = MagicMock()
            mock_parent.winfo_exists.return_value = True
            indicator = DatabaseStatusIndicator(mock_parent, row=5, column=0)
            # 禁用实际的UI更新
            indicator._update_display = MagicMock()
            return indicator
    
    def test_transition_not_configured_to_connected(self, indicator):
        """测试从未配置到已连接的转换"""
        assert indicator._current_status == DatabaseStatus.NOT_CONFIGURED
        
        indicator.set_connected(db_path="/test.db")
        
        assert indicator._current_status == DatabaseStatus.CONNECTED
        assert indicator._detail_info['db_path'] == "/test.db"
    
    def test_transition_connected_to_syncing(self, indicator):
        """测试从已连接到同步中的转换"""
        indicator.set_connected(db_path="/test.db")
        
        indicator.set_syncing(current=0, total=100)
        
        assert indicator._current_status == DatabaseStatus.SYNCING
    
    def test_transition_syncing_to_connected(self, indicator):
        """测试同步完成后回到已连接"""
        indicator.set_syncing(current=0, total=100)
        
        indicator.set_connected(db_path="/test.db", task_count=100)
        
        assert indicator._current_status == DatabaseStatus.CONNECTED
    
    def test_transition_to_error_and_back(self, indicator):
        """测试进入错误状态后可以恢复"""
        indicator.set_connected(db_path="/test.db")
        
        with patch.object(indicator, '_show_error_dialog'):
            indicator.set_error("测试错误", show_dialog=False)
        
        assert indicator._current_status == DatabaseStatus.ERROR
        
        # 恢复连接
        indicator.set_connected(db_path="/test.db")
        
        assert indicator._current_status == DatabaseStatus.CONNECTED
    
    def test_last_sync_time_updated(self, indicator):
        """测试最后同步时间在连接成功时更新"""
        before = indicator._last_sync_time
        
        indicator.set_connected(db_path="/test.db")
        
        assert indicator._last_sync_time is not None
        assert indicator._last_sync_time != before


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

