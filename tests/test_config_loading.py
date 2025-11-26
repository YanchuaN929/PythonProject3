#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载单元测试
测试config.json的加载和参数读取功能
"""

import pytest
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# 确保项目根目录在sys.path中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestConfigStructure:
    """测试config.json结构"""
    
    @pytest.fixture
    def config_path(self):
        """获取项目根目录的config.json路径"""
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.json"
        )
    
    def test_config_file_exists(self, config_path):
        """测试config.json文件存在"""
        assert os.path.exists(config_path), f"config.json不存在: {config_path}"
    
    def test_config_is_valid_json(self, config_path):
        """测试config.json是有效的JSON"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        assert isinstance(config, dict)
    
    def test_config_has_required_keys(self, config_path):
        """测试config.json包含必需的键"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_keys = [
            "folder_path",
            "export_folder_path",
            "user_name",
            "auto_startup",
            "minimize_to_tray",
            "dont_ask_again",
            "hide_previous_months",
            "simple_export_mode",
            "defaults",
            "role_export_days"
        ]
        
        for key in required_keys:
            assert key in config, f"缺少必需的配置键: {key}"
    
    def test_defaults_structure(self, config_path):
        """测试defaults配置结构"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        defaults = config.get("defaults", {})
        assert "folder_path" in defaults, "defaults缺少folder_path"
        assert "export_path" in defaults, "defaults缺少export_path"
    
    def test_role_export_days_structure(self, config_path):
        """测试role_export_days配置结构"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        role_days = config.get("role_export_days", {})
        expected_roles = ["一室主任", "二室主任", "建筑总图室主任", "所领导", "管理员", "设计人员"]
        
        for role in expected_roles:
            assert role in role_days, f"role_export_days缺少角色: {role}"
    
class TestConfigLoading:
    """测试配置加载逻辑"""
    
    @pytest.fixture
    def mock_app(self):
        """创建模拟的应用实例"""
        with patch('tkinter.Tk'), \
             patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            # 创建临时配置目录
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch('os.path.expanduser', return_value=tmpdir):
                    app = MagicMock(spec=ExcelProcessorApp)
                    app.config = {}
                    app.default_config = {}
                    yield app
    
    def test_default_folder_path_applied(self):
        """测试默认文件夹路径被正确应用"""
        # 模拟配置
        config = {"folder_path": "", "defaults": {"folder_path": "/test/path"}}
        
        # 当folder_path为空时，应该使用defaults中的值
        if not config.get("folder_path", "").strip():
            defaults = config.get("defaults", {})
            config["folder_path"] = defaults.get("folder_path", "")
        
        assert config["folder_path"] == "/test/path"
    
    def test_user_path_takes_priority(self):
        """测试用户设置的路径优先于默认路径"""
        config = {
            "folder_path": "/user/custom/path",
            "defaults": {"folder_path": "/default/path"}
        }
        
        # 当folder_path有值时，不应该被覆盖
        if not config.get("folder_path", "").strip():
            defaults = config.get("defaults", {})
            config["folder_path"] = defaults.get("folder_path", "")
        
        assert config["folder_path"] == "/user/custom/path"
    
    def test_role_export_days_merge(self):
        """测试role_export_days合并逻辑"""
        default_config = {
            "role_export_days": {
                "一室主任": 7,
                "二室主任": 7,
                "所领导": 2
            }
        }
        
        user_config = {
            "role_export_days": {
                "一室主任": 10  # 用户自定义值
            }
        }
        
        # 合并逻辑：用户值优先，缺失的用默认值填充
        for k, v in default_config["role_export_days"].items():
            if k not in user_config["role_export_days"]:
                user_config["role_export_days"][k] = v
        
        assert user_config["role_export_days"]["一室主任"] == 10  # 保留用户值
        assert user_config["role_export_days"]["二室主任"] == 7   # 使用默认值
        assert user_config["role_export_days"]["所领导"] == 2     # 使用默认值
    
class TestConfigValues:
    """测试配置值的有效性"""
    
    @pytest.fixture
    def config(self):
        """加载config.json"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config.json"
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def test_role_export_days_values(self, config):
        """测试角色导出天数值"""
        role_days = config.get("role_export_days", {})
        
        # 室主任应该是7天
        assert role_days.get("一室主任") == 7
        assert role_days.get("二室主任") == 7
        assert role_days.get("建筑总图室主任") == 7
        
        # 所领导应该是2天
        assert role_days.get("所领导") == 2
        
        # 管理员和设计人员应该是None（无限制）
        assert role_days.get("管理员") is None
        assert role_days.get("设计人员") is None
    
    def test_default_paths_not_empty(self, config):
        """测试默认路径非空"""
        defaults = config.get("defaults", {})
        
        default_folder = defaults.get("folder_path", "")
        default_export = defaults.get("export_path", "")
        
        assert default_folder, "默认数据文件夹路径不应为空"
        assert default_export, "默认导出路径不应为空"
    
    def test_boolean_values_are_boolean(self, config):
        """测试布尔值确实是布尔类型"""
        boolean_keys = [
            "auto_startup",
            "minimize_to_tray",
            "dont_ask_again",
            "hide_previous_months",
            "simple_export_mode"
        ]
        
        for key in boolean_keys:
            value = config.get(key)
            assert isinstance(value, bool), f"{key}应该是布尔类型，实际是{type(value)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

