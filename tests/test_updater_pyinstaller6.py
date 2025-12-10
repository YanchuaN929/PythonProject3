"""
测试更新程序的进程检测和等待退出功能

使用进程检测方式判断主程序是否退出，比文件锁检测更可靠。
"""
import pytest
import os
import sys
import tempfile
import subprocess
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update.updater_cli import (
    _is_process_running,
    _is_file_locked,
    wait_for_main_exit,
)


class TestIsProcessRunning:
    """测试进程检测函数"""
    
    def test_detect_running_process(self):
        """应该能检测到正在运行的进程"""
        # python.exe 或 python3.exe 应该正在运行（因为我们正在运行测试）
        # 在 Windows 上通常是 python.exe
        assert _is_process_running("python.exe") == True or _is_process_running("python3.exe") == True
    
    def test_detect_nonexistent_process(self):
        """应该检测到不存在的进程"""
        # 使用一个肯定不存在的进程名
        assert _is_process_running("nonexistent_process_12345.exe") == False
    
    def test_process_name_case_insensitive(self):
        """进程名检测应该不区分大小写"""
        # tasklist 输出通常包含进程名，检测应该不区分大小写
        result1 = _is_process_running("PYTHON.EXE")
        result2 = _is_process_running("python.exe")
        # 两者结果应该相同
        assert result1 == result2
    
    def test_handles_subprocess_error(self):
        """当 subprocess 失败时应该返回 False"""
        with patch('update.updater_cli.subprocess.run', side_effect=Exception("模拟错误")):
            # 异常时应该返回 False（假设进程已退出）
            assert _is_process_running("any.exe") == False


class TestIsFileLocked:
    """测试文件锁定检测"""
    
    def test_unlocked_file(self):
        """未锁定的文件应返回 False"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filepath = f.name
        
        try:
            assert _is_file_locked(filepath) == False
        finally:
            os.unlink(filepath)
    
    def test_nonexistent_file(self):
        """不存在的文件应返回 True（无法打开）"""
        assert _is_file_locked("/nonexistent/path/file.exe") == True


class TestWaitForMainExit:
    """测试等待主程序退出"""
    
    def test_nonexistent_exe_skips_wait(self):
        """exe 不存在时跳过等待"""
        result = wait_for_main_exit("/nonexistent/test.exe", timeout=5)
        assert result == True
    
    def test_none_exe_skips_wait(self):
        """exe 为 None 时跳过等待"""
        result = wait_for_main_exit(None, timeout=5)
        assert result == True
    
    def test_empty_exe_skips_wait(self):
        """exe 为空字符串时跳过等待"""
        result = wait_for_main_exit("", timeout=5)
        assert result == True
    
    def test_process_not_running_returns_immediately(self):
        """进程不存在时应立即返回"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = os.path.join(tmpdir, "nonexistent_app.exe")
            open(exe_path, 'w').close()
            
            # 模拟进程不存在
            with patch('update.updater_cli._is_process_running', return_value=False):
                result = wait_for_main_exit(exe_path, timeout=10)
            
            assert result == True
    
    def test_process_running_then_exits(self):
        """进程运行一段时间后退出"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = os.path.join(tmpdir, "test_app.exe")
            open(exe_path, 'w').close()
            
            call_count = [0]
            
            def mock_is_running(name):
                call_count[0] += 1
                # 前2次返回True（运行中），之后返回False（已退出）
                return call_count[0] <= 2
            
            with patch('update.updater_cli._is_process_running', side_effect=mock_is_running):
                result = wait_for_main_exit(exe_path, timeout=10)
            
            assert result == True
            assert call_count[0] >= 3  # 至少调用了3次
    
    def test_timeout_with_fallback_to_file_check(self):
        """超时后会尝试文件锁检测"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = os.path.join(tmpdir, "test_app.exe")
            open(exe_path, 'w').close()
            
            # 进程检测一直返回True（运行中），但文件未锁定
            with patch('update.updater_cli._is_process_running', return_value=True):
                with patch('update.updater_cli._is_file_locked', return_value=False):
                    # 使用很短的超时
                    result = wait_for_main_exit(exe_path, timeout=2)
            
            # 虽然进程检测超时，但文件锁检测通过
            assert result == True


class TestProcessDetectionReliability:
    """测试进程检测的可靠性"""
    
    def test_uses_tasklist_command(self):
        """应该使用 tasklist 命令"""
        with patch('update.updater_cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            
            _is_process_running("test.exe")
            
            # 验证调用了 tasklist
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert 'tasklist' in call_args[0][0]
    
    def test_tasklist_filter_by_imagename(self):
        """应该按进程名过滤"""
        with patch('update.updater_cli.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            
            _is_process_running("myapp.exe")
            
            call_args = mock_run.call_args
            # 检查过滤参数
            args_list = call_args[0][0]
            assert '/FI' in args_list
            assert 'IMAGENAME eq myapp.exe' in args_list


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_works_with_chinese_exe_name(self):
        """应该支持中文程序名"""
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = os.path.join(tmpdir, "接口筛选.exe")
            open(exe_path, 'w').close()
            
            # 模拟进程不存在
            with patch('update.updater_cli._is_process_running', return_value=False):
                result = wait_for_main_exit(exe_path, timeout=5)
            
            assert result == True
    
    def test_handles_special_characters_in_path(self):
        """应该处理路径中的特殊字符"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建包含空格的路径
            special_dir = os.path.join(tmpdir, "Program Files")
            os.makedirs(special_dir)
            exe_path = os.path.join(special_dir, "test app.exe")
            open(exe_path, 'w').close()
            
            with patch('update.updater_cli._is_process_running', return_value=False):
                result = wait_for_main_exit(exe_path, timeout=5)
            
            assert result == True
