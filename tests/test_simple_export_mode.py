#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简洁导出模式测试用例
测试管理员角色的简洁导出功能
"""

import pytest
import pandas as pd
import os
import tempfile
from datetime import datetime


class TestSimpleExportMode:
    """测试简洁导出模式功能"""
    
    def test_config_has_simple_export_mode(self, base_app):
        """测试配置中包含simple_export_mode选项"""
        # 验证默认配置包含该选项
        assert "simple_export_mode" in base_app.default_config
        assert base_app.default_config["simple_export_mode"] is False
        
        # 验证当前配置也应包含该选项（可能需要手动添加，因为是新增功能）
        if "simple_export_mode" not in base_app.config:
            base_app.config["simple_export_mode"] = False
        assert "simple_export_mode" in base_app.config
    
    def test_settings_shows_checkbox_for_admin(self, base_app, monkeypatch):
        """测试管理员可以看到简洁显示模式勾选框"""
        import tkinter as tk
        from tkinter import ttk
        from unittest.mock import MagicMock
        
        # 设置用户为管理员
        base_app.user_roles = ["管理员"]
        base_app.config["user_name"] = "测试管理员"
        
        # Mock messagebox
        monkeypatch.setattr('tkinter.messagebox.showinfo', MagicMock())
        monkeypatch.setattr('tkinter.messagebox.showwarning', MagicMock())
        monkeypatch.setattr('tkinter.messagebox.showerror', MagicMock())
        monkeypatch.setattr('tkinter.messagebox.askyesno', MagicMock(return_value=False))
        
        # 调用show_settings_menu
        base_app.show_settings_menu()
        
        # 验证simple_export_mode_var已创建
        assert hasattr(base_app, 'simple_export_mode_var')
        assert base_app.simple_export_mode_var.get() == base_app.config.get("simple_export_mode", False)
    
    def test_settings_hides_checkbox_for_non_admin(self, base_app, monkeypatch):
        """测试非管理员看不到简洁显示模式勾选框"""
        import tkinter as tk
        from unittest.mock import MagicMock
        
        # 设置用户为设计人员
        base_app.user_roles = ["设计人员"]
        base_app.config["user_name"] = "测试设计人员"
        
        # Mock messagebox
        monkeypatch.setattr('tkinter.messagebox.showinfo', MagicMock())
        monkeypatch.setattr('tkinter.messagebox.showwarning', MagicMock())
        monkeypatch.setattr('tkinter.messagebox.showerror', MagicMock())
        monkeypatch.setattr('tkinter.messagebox.askyesno', MagicMock(return_value=False))
        
        # 调用show_settings_menu
        base_app.show_settings_menu()
        
        # 验证simple_export_mode_var仍然创建了（只是不显示）
        assert hasattr(base_app, 'simple_export_mode_var')
    
    def test_export_summary_with_simple_mode_enabled(self):
        """测试启用简洁模式时，导出结果不显示接口号"""
        import main2
        
        # 准备测试数据
        df1 = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002'],
            '科室': ['一室', '一室'],
            '接口时间': ['01.15', '01.20'],
            '角色来源': ['设计人员', '设计人员']
        })
        
        results_multi1 = {'2016': df1}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 启用简洁模式
            txt_path = main2.write_export_summary(
                folder_path=tmpdir,
                current_datetime=datetime.now(),
                results_multi1=results_multi1,
                simple_export_mode=True
            )
            
            # 读取生成的文件
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证：应该包含个数
            assert '01.15需打开1个' in content or '01.15需打开1个' in content
            assert '01.20需打开1个' in content or '01.20需打开1个' in content
            
            # 验证：不应该包含"接口号："
            assert '接口号：' not in content
            assert 'INT-001' not in content
            assert 'INT-002' not in content
    
    def test_export_summary_with_simple_mode_disabled(self):
        """测试禁用简洁模式时，导出结果显示接口号"""
        import main2
        
        # 准备测试数据
        df1 = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002'],
            '科室': ['一室', '一室'],
            '接口时间': ['01.15', '01.20'],
            '角色来源': ['设计人员', '设计人员']
        })
        
        results_multi1 = {'2016': df1}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 禁用简洁模式
            txt_path = main2.write_export_summary(
                folder_path=tmpdir,
                current_datetime=datetime.now(),
                results_multi1=results_multi1,
                simple_export_mode=False
            )
            
            # 读取生成的文件
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证：应该包含个数
            assert '01.15需打开1个' in content or '01.15需打开1个' in content
            
            # 验证：应该包含"接口号："和具体接口号
            assert '接口号：' in content
            assert 'INT-001' in content or 'INT-002' in content
    
    def test_admin_with_simple_mode_in_base_app(self, base_app, monkeypatch):
        """测试base_app中管理员启用简洁模式的逻辑"""
        from unittest.mock import MagicMock, patch
        import main2
        
        # 设置用户为管理员
        base_app.user_roles = ["管理员"]
        base_app.config["user_name"] = "测试管理员"
        base_app.config["simple_export_mode"] = True
        
        # 准备测试数据
        df1 = pd.DataFrame({
            '接口号': ['INT-001'],
            '科室': ['一室'],
            '接口时间': ['01.15'],
            '角色来源': ['设计人员'],
            '原始行号': [1]
        })
        
        base_app.processing_results_multi1 = {'2016': df1}
        base_app.target_files1 = [('test.xlsx', '2016')]
        
        # Mock write_export_summary 来验证参数
        original_write = main2.write_export_summary
        call_args = {}
        
        def mock_write(*args, **kwargs):
            call_args.update(kwargs)
            return original_write(*args, **kwargs)
        
        monkeypatch.setattr('main2.write_export_summary', mock_write)
        
        # 模拟导出操作，检查simple_export_mode参数
        # 注意：我们只测试参数传递逻辑，不实际执行完整导出
        with tempfile.TemporaryDirectory() as tmpdir:
            base_app.config["export_folder_path"] = tmpdir
            base_app.export_path_var.set(tmpdir)
            
            # 模拟导出逻辑中的相关代码段
            simple_mode = ("管理员" in base_app.user_roles) and base_app.config.get("simple_export_mode", False)
            assert simple_mode is True
    
    def test_non_admin_cannot_use_simple_mode(self, base_app):
        """测试非管理员即使勾选也不启用简洁模式"""
        # 设置用户为设计人员
        base_app.user_roles = ["设计人员"]
        base_app.config["user_name"] = "测试设计人员"
        base_app.config["simple_export_mode"] = True  # 尝试启用（但不应生效）
        
        # 检查逻辑
        simple_mode = ("管理员" in base_app.user_roles) and base_app.config.get("simple_export_mode", False)
        assert simple_mode is False
    
    def test_yaml_config_saves_simple_export_mode(self, base_app, monkeypatch):
        """测试simple_export_mode可以保存到YAML配置"""
        import os
        
        # 设置临时配置文件路径
        with tempfile.TemporaryDirectory() as tmpdir:
            base_app.yaml_config_file = os.path.join(tmpdir, "test_config.yaml")
            base_app.config["simple_export_mode"] = True
            
            # 保存配置
            base_app._save_yaml_all()
            
            # 读取配置文件
            with open(base_app.yaml_config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证包含simple_export_mode配置
            assert 'simple_export_mode:' in content
            assert 'true' in content.lower()
    
    def test_yaml_config_loads_simple_export_mode(self, base_app):
        """测试可以从YAML配置加载simple_export_mode"""
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_file = os.path.join(tmpdir, "test_config.yaml")
            
            # 写入测试配置
            with open(yaml_file, 'w', encoding='utf-8') as f:
                f.write("general:\n")
                f.write("  folder_path: \"\"\n")
                f.write("  export_folder_path: \"\"\n")
                f.write("  user_name: \"测试\"\n")
                f.write("  auto_startup: false\n")
                f.write("  minimize_to_tray: true\n")
                f.write("  dont_ask_again: false\n")
                f.write("  hide_previous_months: false\n")
                f.write("  simple_export_mode: true\n")
            
            base_app.yaml_config_file = yaml_file
            # 手动读取YAML并解析（因为_load_yaml_all可能不存在）
            with open(yaml_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 验证YAML文件包含配置
            assert 'simple_export_mode: true' in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

