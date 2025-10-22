#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试开机自启动和导出弹窗功能
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import winreg
import sys
import os


class TestAutoStartup:
    """测试开机自启动功能"""
    
    def test_add_to_startup_success_py_script(self):
        """测试：成功添加Python脚本到开机自启动"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg, \
             patch('base.sys.argv', ['test_script.py']), \
             patch('base.sys.executable', 'C:\\Python\\python.exe'), \
             patch('base.os.path.abspath', return_value='C:\\app\\test_script.py'):
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock注册表操作
            mock_key = MagicMock()
            mock_verify_key = MagicMock()
            
            def open_key_side_effect(root, path, reserved, access):
                if access & winreg.KEY_WRITE:
                    return mock_key
                else:
                    return mock_verify_key
            
            mock_winreg.OpenKey.side_effect = open_key_side_effect
            mock_winreg.QueryValueEx.return_value = (
                '"C:\\Python\\python.exe" "C:\\app\\test_script.py" --auto',
                winreg.REG_SZ
            )
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            mock_winreg.REG_SZ = winreg.REG_SZ
            
            # 执行添加
            app.add_to_startup()
            
            # 验证注册表操作
            assert mock_winreg.SetValueEx.called
            call_args = mock_winreg.SetValueEx.call_args[0]
            # SetValueEx(key, value_name, reserved, type, value)
            assert call_args[1] == "ExcelProcessor"
            assert '--auto' in call_args[4]  # call_args[4]是value参数
            assert mock_winreg.CloseKey.called
    
    def test_add_to_startup_success_exe(self):
        """测试：成功添加可执行文件到开机自启动"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg, \
             patch('base.sys.argv', ['test_app.exe']), \
             patch('base.os.path.abspath', return_value='C:\\app\\test_app.exe'):
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock注册表操作
            mock_key = MagicMock()
            mock_verify_key = MagicMock()
            
            def open_key_side_effect(root, path, reserved, access):
                if access & winreg.KEY_WRITE:
                    return mock_key
                else:
                    return mock_verify_key
            
            mock_winreg.OpenKey.side_effect = open_key_side_effect
            mock_winreg.QueryValueEx.return_value = (
                '"C:\\app\\test_app.exe" --auto',
                winreg.REG_SZ
            )
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            mock_winreg.REG_SZ = winreg.REG_SZ
            
            # 执行添加
            app.add_to_startup()
            
            # 验证命令格式
            call_args = mock_winreg.SetValueEx.call_args[0]
            assert '.exe' in call_args[4]  # call_args[4]是value参数
            assert '--auto' in call_args[4]
    
    def test_add_to_startup_permission_error(self):
        """测试：权限不足时的错误处理"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg, \
             patch('base.sys.argv', ['test_script.py']), \
             patch('base.os.path.abspath', return_value='C:\\app\\test_script.py'):
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock权限错误
            mock_winreg.OpenKey.side_effect = PermissionError("Access denied")
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            
            # 执行添加（应该捕获异常）
            app.add_to_startup()
            
            # 验证状态回滚
            assert app.auto_startup_var.get() == False
    
    def test_add_to_startup_verification_failed(self):
        """测试：写入验证失败的处理"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg, \
             patch('base.sys.argv', ['test_script.py']), \
             patch('base.os.path.abspath', return_value='C:\\app\\test_script.py'):
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock注册表操作
            mock_key = MagicMock()
            mock_verify_key = MagicMock()
            
            def open_key_side_effect(root, path, reserved, access):
                if access & winreg.KEY_WRITE:
                    return mock_key
                else:
                    return mock_verify_key
            
            mock_winreg.OpenKey.side_effect = open_key_side_effect
            # 验证时返回不同的值
            mock_winreg.QueryValueEx.return_value = (
                'WRONG_VALUE',
                winreg.REG_SZ
            )
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            mock_winreg.REG_SZ = winreg.REG_SZ
            
            # 执行添加（验证应该失败）
            app.add_to_startup()
            
            # 验证状态回滚
            assert app.auto_startup_var.get() == False
    
    def test_remove_from_startup_success(self):
        """测试：成功移除开机自启动"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.auto_startup_var.set(True)
            
            # Mock注册表操作
            mock_key = MagicMock()
            mock_verify_key = MagicMock()
            
            def open_key_side_effect(root, path, reserved, access):
                if access & winreg.KEY_WRITE:
                    return mock_key
                else:
                    return mock_verify_key
            
            mock_winreg.OpenKey.side_effect = open_key_side_effect
            # 验证时抛出FileNotFoundError表示删除成功
            mock_winreg.QueryValueEx.side_effect = FileNotFoundError()
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            
            # 执行移除
            app.remove_from_startup()
            
            # 验证删除操作被调用
            assert mock_winreg.DeleteValue.called
            call_args = mock_winreg.DeleteValue.call_args[0]
            assert call_args[1] == "ExcelProcessor"
    
    def test_remove_from_startup_not_exists(self):
        """测试：移除不存在的启动项（应该静默成功）"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock注册表操作 - 值不存在
            mock_winreg.OpenKey.side_effect = FileNotFoundError()
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            
            # 执行移除（不应该报错）
            app.remove_from_startup()
            
            # 不应该有异常
    
    def test_remove_from_startup_permission_error(self):
        """测试：移除时权限不足的错误处理"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            app.auto_startup_var.set(False)
            
            # Mock权限错误
            mock_winreg.OpenKey.side_effect = PermissionError("Access denied")
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            
            # 执行移除（应该捕获异常）
            app.remove_from_startup()
            
            # 验证状态回滚
            assert app.auto_startup_var.get() == True
    
    def test_toggle_auto_startup_enable(self):
        """测试：切换开启自启动"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg, \
             patch('base.sys.argv', ['test.py']), \
             patch('base.os.path.abspath', return_value='C:\\app\\test.py'):
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock注册表
            mock_key = MagicMock()
            mock_verify_key = MagicMock()
            
            def open_key_side_effect(root, path, reserved, access):
                if access & winreg.KEY_WRITE:
                    return mock_key
                else:
                    return mock_verify_key
            
            mock_winreg.OpenKey.side_effect = open_key_side_effect
            mock_winreg.QueryValueEx.return_value = ('test', winreg.REG_SZ)
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            mock_winreg.REG_SZ = winreg.REG_SZ
            
            # 开启自启动
            app.auto_startup_var.set(True)
            app.toggle_auto_startup()
            
            # 验证配置被更新
            assert app.config["auto_startup"] == True
            
            # 验证add_to_startup被调用
            assert mock_winreg.SetValueEx.called
    
    def test_toggle_auto_startup_disable(self):
        """测试：切换关闭自启动"""
        with patch('base.WindowManager'), \
             patch('base.winreg') as mock_winreg:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock注册表
            mock_key = MagicMock()
            mock_verify_key = MagicMock()
            
            def open_key_side_effect(root, path, reserved, access):
                if access & winreg.KEY_WRITE:
                    return mock_key
                else:
                    return mock_verify_key
            
            mock_winreg.OpenKey.side_effect = open_key_side_effect
            mock_winreg.QueryValueEx.side_effect = FileNotFoundError()
            mock_winreg.HKEY_CURRENT_USER = winreg.HKEY_CURRENT_USER
            mock_winreg.KEY_WRITE = winreg.KEY_WRITE
            mock_winreg.KEY_READ = winreg.KEY_READ
            
            # 关闭自启动
            app.auto_startup_var.set(False)
            app.toggle_auto_startup()
            
            # 验证配置被更新
            assert app.config["auto_startup"] == False
            
            # 验证remove_from_startup被调用
            assert mock_winreg.DeleteValue.called or mock_winreg.OpenKey.called


class TestExportPopup:
    """测试导出弹窗功能"""
    
    def test_show_summary_popup_basic(self):
        """测试：基本的弹窗显示功能"""
        with patch('base.WindowManager'), \
             patch('base.tk.Toplevel') as mock_toplevel, \
             patch('builtins.open', create=True) as mock_open:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock文件内容
            test_content = "测试导出结果\n01.06需回复1个\n  接口号：TEST-001、TEST-002"
            mock_open.return_value.__enter__.return_value.read.return_value = test_content
            
            # Mock对话框
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            
            # 调用弹窗
            app._show_summary_popup('test_summary.txt')
            
            # 验证对话框被创建
            assert mock_toplevel.called
            assert mock_dialog.title.called
            assert mock_dialog.geometry.called
    
    def test_show_summary_popup_with_interface_numbers(self):
        """测试：弹窗显示包含接口号信息"""
        with patch('base.WindowManager'), \
             patch('base.tk.Toplevel') as mock_toplevel, \
             patch('base.tk.Text') as mock_text, \
             patch('builtins.open', create=True) as mock_open:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock包含接口号的文件内容
            test_content = """导出结果汇总
            
内部需回复接口：
  1818项目：
    01.06需回复1个（已延误！！）
      接口号：INT-001、INT-002、INT-003
    01.08需回复2个
      接口号：INT-004"""
            
            mock_open.return_value.__enter__.return_value.read.return_value = test_content
            
            # Mock对话框和文本框
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            mock_text_widget = MagicMock()
            mock_text.return_value = mock_text_widget
            
            # 调用弹窗
            app._show_summary_popup('test_summary.txt')
            
            # 验证文件被打开
            mock_open.assert_called_with('test_summary.txt', 'r', encoding='utf-8')
    
    def test_show_summary_popup_copy_functionality(self):
        """测试：弹窗支持复制功能"""
        with patch('base.WindowManager'), \
             patch('base.tk.Toplevel') as mock_toplevel, \
             patch('base.tk.Text') as mock_text, \
             patch('base.ttk.Button') as mock_button, \
             patch('builtins.open', create=True) as mock_open:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock文件内容
            test_content = "导出结果测试"
            mock_open.return_value.__enter__.return_value.read.return_value = test_content
            
            # Mock组件
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            mock_text_widget = MagicMock()
            mock_text.return_value = mock_text_widget
            
            # 调用弹窗
            app._show_summary_popup('test_summary.txt')
            
            # 验证文本框被正确配置（可选中但不可编辑）
            assert mock_text.called
            # 验证按钮被创建（包括"复制全部"按钮）
            assert mock_button.call_count >= 2  # 至少有"复制全部"和"关闭"按钮
    
    def test_show_summary_popup_file_not_found(self):
        """测试：文件不存在时的错误处理"""
        with patch('base.WindowManager'), \
             patch('base.tk.Toplevel') as mock_toplevel, \
             patch('base.tk.Text') as mock_text, \
             patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock对话框
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            mock_text_widget = MagicMock()
            mock_text.return_value = mock_text_widget
            
            # 调用弹窗（应该显示错误消息）
            app._show_summary_popup('non_existent.txt')
            
            # 验证对话框仍然被创建（显示错误信息）
            assert mock_toplevel.called
    
    def test_show_summary_popup_selectable_text(self):
        """测试：文本可选择性"""
        with patch('base.WindowManager'), \
             patch('base.tk.Toplevel') as mock_toplevel, \
             patch('base.tk.Text') as mock_text, \
             patch('builtins.open', create=True) as mock_open:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock文件内容
            test_content = "可选择的文本内容"
            mock_open.return_value.__enter__.return_value.read.return_value = test_content
            
            # Mock组件
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            mock_text_widget = MagicMock()
            mock_text.return_value = mock_text_widget
            
            # 调用弹窗
            app._show_summary_popup('test_summary.txt')
            
            # 验证文本框的配置
            # 注意：不应该调用text.config(state='disabled')，而是使用事件绑定
            config_calls = [call for call in mock_text_widget.method_calls if 'config' in str(call)]
            # 验证没有设置为disabled状态
            for call in config_calls:
                if 'state' in str(call):
                    assert 'disabled' not in str(call)
    
    def test_show_summary_popup_context_menu(self):
        """测试：右键菜单功能"""
        with patch('base.WindowManager'), \
             patch('base.tk.Toplevel') as mock_toplevel, \
             patch('base.tk.Text') as mock_text, \
             patch('base.tk.Menu') as mock_menu, \
             patch('builtins.open', create=True) as mock_open:
            
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # Mock文件内容
            test_content = "测试内容"
            mock_open.return_value.__enter__.return_value.read.return_value = test_content
            
            # Mock组件
            mock_dialog = MagicMock()
            mock_toplevel.return_value = mock_dialog
            mock_text_widget = MagicMock()
            mock_text.return_value = mock_text_widget
            mock_context_menu = MagicMock()
            mock_menu.return_value = mock_context_menu
            
            # 调用弹窗
            app._show_summary_popup('test_summary.txt')
            
            # 验证右键菜单被创建
            assert mock_menu.called
            # 验证菜单项被添加（至少有"复制"和"全选"）
            assert mock_context_menu.add_command.call_count >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

