# -*- coding: utf-8 -*-
"""
测试 update.exe 自更新功能

确保主程序能够正确同步更新 update.exe
"""
import os
import sys
import tempfile
import shutil
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update.manager import UpdateManager


class TestSyncUpdateExecutable:
    """测试 sync_update_executable 方法"""
    
    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录结构"""
        # 本地目录
        local_dir = tempfile.mkdtemp(prefix="local_")
        # 远程目录（模拟共享文件夹/EXE目录）
        remote_base = tempfile.mkdtemp(prefix="remote_")
        remote_exe_dir = os.path.join(remote_base, "EXE")
        os.makedirs(remote_exe_dir)
        
        yield {
            "local": local_dir,
            "remote_base": remote_base,
            "remote_exe": remote_exe_dir,
        }
        
        # 清理
        shutil.rmtree(local_dir, ignore_errors=True)
        shutil.rmtree(remote_base, ignore_errors=True)
    
    def test_sync_when_local_not_exists(self, temp_dirs):
        """测试：本地不存在 update.exe 时应该复制"""
        local_dir = temp_dirs["local"]
        remote_exe_dir = temp_dirs["remote_exe"]
        
        # 创建远程 update.exe
        remote_update = os.path.join(remote_exe_dir, "update.exe")
        with open(remote_update, "wb") as f:
            f.write(b"remote_update_content_v1")
        
        # 创建 UpdateManager
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步
        result = manager.sync_update_executable(temp_dirs["remote_base"])
        
        # 验证
        assert result is True
        local_update = os.path.join(local_dir, "update.exe")
        assert os.path.exists(local_update)
        with open(local_update, "rb") as f:
            assert f.read() == b"remote_update_content_v1"
    
    def test_sync_when_files_are_same(self, temp_dirs):
        """测试：文件相同时不应该更新"""
        local_dir = temp_dirs["local"]
        remote_exe_dir = temp_dirs["remote_exe"]
        content = b"same_content_12345"
        
        # 创建相同内容的文件
        local_update = os.path.join(local_dir, "update.exe")
        remote_update = os.path.join(remote_exe_dir, "update.exe")
        
        with open(local_update, "wb") as f:
            f.write(content)
        with open(remote_update, "wb") as f:
            f.write(content)
        
        # 记录本地文件修改时间
        local_mtime_before = os.path.getmtime(local_update)
        
        # 等待一小段时间，确保如果复制发生，时间戳会不同
        import time
        time.sleep(0.1)
        
        # 创建 UpdateManager
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步
        result = manager.sync_update_executable(temp_dirs["remote_base"])
        
        # 验证：应该返回 True，且文件时间戳不变
        assert result is True
        local_mtime_after = os.path.getmtime(local_update)
        assert local_mtime_before == local_mtime_after
    
    def test_sync_when_files_are_different(self, temp_dirs):
        """测试：文件不同时应该更新"""
        local_dir = temp_dirs["local"]
        remote_exe_dir = temp_dirs["remote_exe"]
        
        # 创建不同内容的文件
        local_update = os.path.join(local_dir, "update.exe")
        remote_update = os.path.join(remote_exe_dir, "update.exe")
        
        with open(local_update, "wb") as f:
            f.write(b"old_local_content")
        with open(remote_update, "wb") as f:
            f.write(b"new_remote_content_updated")
        
        # 创建 UpdateManager
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步
        result = manager.sync_update_executable(temp_dirs["remote_base"])
        
        # 验证：应该更新为远程内容
        assert result is True
        with open(local_update, "rb") as f:
            assert f.read() == b"new_remote_content_updated"
    
    def test_sync_when_remote_not_exists(self, temp_dirs):
        """测试：远程不存在 update.exe 时应该跳过"""
        local_dir = temp_dirs["local"]
        
        # 本地有文件，远程没有
        local_update = os.path.join(local_dir, "update.exe")
        with open(local_update, "wb") as f:
            f.write(b"local_only_content")
        
        # 创建 UpdateManager
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步（远程目录存在但没有 update.exe）
        result = manager.sync_update_executable(temp_dirs["remote_base"])
        
        # 验证：应该返回 True（跳过），本地文件不变
        assert result is True
        with open(local_update, "rb") as f:
            assert f.read() == b"local_only_content"
    
    def test_sync_when_no_folder_path(self, temp_dirs):
        """测试：没有 folder_path 时应该跳过"""
        local_dir = temp_dirs["local"]
        
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步（无 folder_path）
        result = manager.sync_update_executable(None)
        
        # 验证：应该返回 True（跳过）
        assert result is True
    
    def test_sync_when_remote_dir_not_exists(self, temp_dirs):
        """测试：远程 EXE 目录不存在时应该跳过"""
        local_dir = temp_dirs["local"]
        
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步（使用不存在的路径）
        result = manager.sync_update_executable("/nonexistent/path")
        
        # 验证：应该返回 True（跳过）
        assert result is True
    
    def test_sync_finds_update_in_internal_dir(self, temp_dirs):
        """测试：能在 _internal 目录中找到 update.exe"""
        local_dir = temp_dirs["local"]
        remote_exe_dir = temp_dirs["remote_exe"]
        
        # 在 _internal 目录创建 update.exe
        internal_dir = os.path.join(remote_exe_dir, "_internal")
        os.makedirs(internal_dir)
        remote_update = os.path.join(internal_dir, "update.exe")
        with open(remote_update, "wb") as f:
            f.write(b"internal_update_content")
        
        # 创建 UpdateManager
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步
        result = manager.sync_update_executable(temp_dirs["remote_base"])
        
        # 验证
        assert result is True
        local_update = os.path.join(local_dir, "update.exe")
        assert os.path.exists(local_update)
        with open(local_update, "rb") as f:
            assert f.read() == b"internal_update_content"
    
    def test_sync_prefers_root_over_internal(self, temp_dirs):
        """测试：根目录的 update.exe 优先于 _internal 目录"""
        local_dir = temp_dirs["local"]
        remote_exe_dir = temp_dirs["remote_exe"]
        
        # 在根目录和 _internal 目录都创建 update.exe
        root_update = os.path.join(remote_exe_dir, "update.exe")
        with open(root_update, "wb") as f:
            f.write(b"root_update_content")
        
        internal_dir = os.path.join(remote_exe_dir, "_internal")
        os.makedirs(internal_dir)
        internal_update = os.path.join(internal_dir, "update.exe")
        with open(internal_update, "wb") as f:
            f.write(b"internal_update_content")
        
        # 创建 UpdateManager
        manager = UpdateManager(app_root=local_dir)
        
        # 执行同步
        result = manager.sync_update_executable(temp_dirs["remote_base"])
        
        # 验证：应该使用根目录的版本
        assert result is True
        local_update = os.path.join(local_dir, "update.exe")
        with open(local_update, "rb") as f:
            assert f.read() == b"root_update_content"


class TestUpdateExeSyncIntegration:
    """集成测试：验证 update.exe 同步在整体流程中的正确性"""
    
    def test_sync_called_during_init_simulation(self, tmp_path):
        """模拟：在程序初始化时调用同步"""
        local_dir = tmp_path / "local"
        local_dir.mkdir()
        
        remote_base = tmp_path / "remote"
        remote_exe = remote_base / "EXE"
        remote_exe.mkdir(parents=True)
        
        # 创建远程 update.exe
        remote_update = remote_exe / "update.exe"
        remote_update.write_bytes(b"new_version_from_server")
        
        # 模拟初始化过程
        manager = UpdateManager(app_root=str(local_dir))
        folder_path = str(remote_base)
        
        # 调用同步（模拟 base.py 中的调用）
        if manager and folder_path:
            result = manager.sync_update_executable(folder_path)
            assert result is True
        
        # 验证本地 update.exe 已更新
        local_update = local_dir / "update.exe"
        assert local_update.exists()
        assert local_update.read_bytes() == b"new_version_from_server"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

