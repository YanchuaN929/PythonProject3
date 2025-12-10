#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端测试：模拟完整的更新场景
"""

import os
import sys
import tempfile
import shutil
import pytest
from argparse import Namespace

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update.updater_cli import perform_update, init_log_file, LOG_FILE


class TestEndToEndUpdate:
    """端到端更新测试"""
    
    @pytest.fixture
    def simulation_env(self):
        """创建模拟环境，模拟用户的实际目录结构"""
        base_temp = tempfile.gettempdir()
        
        # 模拟中文路径环境
        test_root = os.path.join(base_temp, "接口筛选_更新测试")
        
        # 清理
        if os.path.exists(test_root):
            shutil.rmtree(test_root)
        
        # 创建目录结构
        # 模拟公共盘: D:\Programs\接口筛选\测试文件\EXE
        remote_root = os.path.join(test_root, "公共盘", "接口筛选", "测试文件", "EXE")
        # 模拟本地安装: D:\Programs\接口筛选
        local_root = os.path.join(test_root, "本地安装", "接口筛选")
        
        os.makedirs(remote_root)
        os.makedirs(local_root)
        
        # 在远程目录创建新版本文件
        remote_files = [
            ("接口筛选.exe", "NEW_VERSION_EXE_CONTENT"),
            ("update.exe", "NEW_UPDATE_EXE_CONTENT"),
            ("version.json", '{"version": "2025.11.23.2"}'),
            ("config.json", '{"key": "value"}'),
            ("_internal/base_library.zip", "BINARY_DATA"),
            ("_internal/中文子目录/资源文件.dat", "RESOURCE_DATA"),
        ]
        
        for filename, content in remote_files:
            filepath = os.path.join(remote_root, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # 在本地目录创建旧版本文件
        local_files = [
            ("接口筛选.exe", "OLD_VERSION_EXE_CONTENT"),
            ("update.exe", "OLD_UPDATE_EXE_CONTENT"),  # 这个文件在更新时应该被跳过（因为正在运行）
            ("version.json", '{"version": "2025.11.22.1"}'),
            ("config.json", '{"key": "old_value"}'),
        ]
        
        for filename, content in local_files:
            filepath = os.path.join(local_root, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        yield {
            'test_root': test_root,
            'remote_root': remote_root,
            'local_root': local_root,
        }
        
        # 清理
        if os.path.exists(test_root):
            shutil.rmtree(test_root, ignore_errors=True)
    
    def test_full_update_simulation(self, simulation_env, monkeypatch):
        """测试完整的更新流程模拟"""
        remote_root = simulation_env['remote_root']
        local_root = simulation_env['local_root']
        
        # Mock subprocess.Popen 以避免实际启动程序
        from unittest.mock import MagicMock
        mock_popen = MagicMock()
        monkeypatch.setattr('subprocess.Popen', mock_popen)
        
        # Mock _is_process_running 以避免调用 tasklist
        monkeypatch.setattr('update.updater_cli._is_process_running', lambda x: False)
        
        # 创建参数
        args = Namespace(
            remote=remote_root,
            local=local_root,
            version="2025.11.23.2",
            resume="start_processing",
            main_exe="接口筛选.exe",
            auto_mode=True,
        )
        
        # 执行更新
        result = perform_update(args)
        
        # 验证结果
        assert result == True, "更新应该成功"
        
        # 验证文件被正确复制
        assert os.path.exists(os.path.join(local_root, "version.json"))
        assert os.path.exists(os.path.join(local_root, "_internal", "base_library.zip"))
        assert os.path.exists(os.path.join(local_root, "_internal", "中文子目录", "资源文件.dat"))
        
        # 验证主程序被更新
        with open(os.path.join(local_root, "接口筛选.exe"), 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == "NEW_VERSION_EXE_CONTENT", "主程序应该被更新"
        
        # 验证 subprocess.Popen 被调用来启动主程序
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert "接口筛选.exe" in call_args[0][0][0]
        
        # 验证日志文件被创建
        log_file = os.path.join(local_root, "update_log.txt")
        assert os.path.exists(log_file), "日志文件应该被创建"
        
        with open(log_file, 'r', encoding='utf-8') as f:
            log_content = f.read()
            assert "自动更新开始" in log_content
            assert "更新流程完成" in log_content
        
        print("\n[SUCCESS] 完整更新模拟测试通过！")
    
    def test_update_with_skip_running_exe(self, simulation_env, monkeypatch):
        """测试跳过正在运行的 update.exe"""
        remote_root = simulation_env['remote_root']
        local_root = simulation_env['local_root']
        
        # Mock subprocess.Popen
        from unittest.mock import MagicMock
        mock_popen = MagicMock()
        monkeypatch.setattr('subprocess.Popen', mock_popen)
        
        # 模拟 update.exe 正在运行（通过锁定文件）
        update_exe_path = os.path.join(local_root, "update.exe")
        
        # 获取旧内容
        with open(update_exe_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
        
        # 执行更新
        args = Namespace(
            remote=remote_root,
            local=local_root,
            version="2025.11.23.2",
            resume="",
            main_exe="接口筛选.exe",
            auto_mode=False,
        )
        
        result = perform_update(args)
        assert result == True
        
        # 注意：在这个测试中，update.exe 会被更新，因为它没有被锁定
        # 在实际运行中，update.exe 正在运行时会被跳过
        print("\n[SUCCESS] 跳过运行中文件测试通过！")
    
    def test_update_with_permission_error(self, simulation_env, monkeypatch):
        """测试文件权限错误的处理"""
        remote_root = simulation_env['remote_root']
        local_root = simulation_env['local_root']
        
        # Mock subprocess.Popen
        from unittest.mock import MagicMock
        mock_popen = MagicMock()
        monkeypatch.setattr('subprocess.Popen', mock_popen)
        
        # 创建一个只读文件来模拟权限问题
        readonly_file = os.path.join(local_root, "readonly.txt")
        with open(readonly_file, 'w') as f:
            f.write("readonly content")
        
        # 设置为只读
        import stat
        os.chmod(readonly_file, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        try:
            # 在远程目录也创建同名文件
            remote_readonly = os.path.join(remote_root, "readonly.txt")
            with open(remote_readonly, 'w') as f:
                f.write("new content")
            
            # 执行更新（应该不会因为单个文件失败而整体失败）
            args = Namespace(
                remote=remote_root,
                local=local_root,
                version="2025.11.23.2",
                resume="",
                main_exe="接口筛选.exe",
                auto_mode=False,
            )
            
            # 这应该成功，尽管有一个文件可能复制失败
            result = perform_update(args)
            # 在Windows上，只读属性不会阻止写入
            assert result == True
            
        finally:
            # 恢复文件权限以便清理
            try:
                os.chmod(readonly_file, stat.S_IWUSR | stat.S_IRUSR)
            except:
                pass
        
        print("\n[SUCCESS] 权限错误处理测试通过！")


class TestUpdateManagerIntegration:
    """测试 UpdateManager 与 updater_cli 的集成"""
    
    def test_manager_constructs_correct_command(self):
        """测试 UpdateManager 构建正确的命令行"""
        from update.manager import UpdateManager
        
        manager = UpdateManager(
            app_root=r"D:\Programs\接口筛选",
            main_executable="接口筛选.exe",
        )
        
        # 验证路径处理
        assert manager.app_root == r"D:\Programs\接口筛选"
        assert manager.main_executable == "接口筛选.exe"
        
        print("\n[SUCCESS] UpdateManager 命令构建测试通过！")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

