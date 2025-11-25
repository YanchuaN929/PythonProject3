#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试自动更新模块在中文路径下的行为
"""

import os
import sys
import tempfile
import shutil
import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update.updater_cli import (
    copy_directory_atomic,
    sync_directory,
    wait_for_main_exit,
    restart_main_program,
    perform_update,
    parse_args,
)


class TestChinesePathHandling:
    """测试中文路径处理"""
    
    @pytest.fixture
    def chinese_temp_dir(self):
        """创建包含中文的临时目录"""
        # 使用系统临时目录
        base_temp = tempfile.gettempdir()
        chinese_dir = os.path.join(base_temp, "测试文件_接口筛选_更新测试")
        
        # 清理并创建
        if os.path.exists(chinese_dir):
            shutil.rmtree(chinese_dir)
        os.makedirs(chinese_dir)
        
        yield chinese_dir
        
        # 清理
        if os.path.exists(chinese_dir):
            shutil.rmtree(chinese_dir, ignore_errors=True)
    
    def test_tempfile_mkdtemp_with_chinese_parent(self, chinese_temp_dir):
        """测试在中文父目录下创建临时目录"""
        try:
            tmp_dir = tempfile.mkdtemp(prefix="update_tmp_", dir=chinese_temp_dir)
            print(f"[OK] 临时目录创建成功: {tmp_dir}")
            assert os.path.exists(tmp_dir)
            shutil.rmtree(tmp_dir)
        except Exception as e:
            pytest.fail(f"在中文路径下创建临时目录失败: {e}")
    
    def test_shutil_copytree_chinese_path(self, chinese_temp_dir):
        """测试复制包含中文的目录"""
        # 创建源目录结构
        source_dir = os.path.join(chinese_temp_dir, "源目录_中文")
        target_dir = os.path.join(chinese_temp_dir, "目标目录_中文")
        
        os.makedirs(source_dir)
        
        # 创建一些测试文件
        test_files = [
            "测试文件1.txt",
            "config.json",
            "_internal/中文子目录/文件.dat"
        ]
        
        for file_path in test_files:
            full_path = os.path.join(source_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(f"测试内容: {file_path}")
        
        try:
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            print(f"[OK] 目录复制成功: {source_dir} -> {target_dir}")
            assert os.path.exists(target_dir)
            
            # 验证文件
            for file_path in test_files:
                full_path = os.path.join(target_dir, file_path)
                assert os.path.exists(full_path), f"文件不存在: {full_path}"
            
        except Exception as e:
            pytest.fail(f"复制中文路径目录失败: {e}")
    
    def test_sync_directory_chinese_path(self, chinese_temp_dir):
        """测试sync_directory函数处理中文路径"""
        source_dir = os.path.join(chinese_temp_dir, "同步源_中文目录")
        target_dir = os.path.join(chinese_temp_dir, "同步目标_中文目录")
        
        os.makedirs(source_dir)
        
        # 创建测试文件
        test_file = os.path.join(source_dir, "子目录", "测试.txt")
        os.makedirs(os.path.dirname(test_file), exist_ok=True)
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("中文内容测试")
        
        try:
            sync_directory(source_dir, target_dir)
            print(f"[OK] sync_directory成功: {source_dir} -> {target_dir}")
            
            target_file = os.path.join(target_dir, "子目录", "测试.txt")
            assert os.path.exists(target_file), f"同步后文件不存在: {target_file}"
            
        except Exception as e:
            pytest.fail(f"sync_directory处理中文路径失败: {e}")
    
    def test_copy_directory_atomic_chinese_path(self, chinese_temp_dir):
        """测试copy_directory_atomic函数处理中文路径"""
        source_dir = os.path.join(chinese_temp_dir, "原子复制源_EXE")
        target_dir = os.path.join(chinese_temp_dir, "原子复制目标_接口筛选")
        
        os.makedirs(source_dir)
        os.makedirs(target_dir)
        
        # 创建测试文件
        files = [
            "接口筛选.exe",
            "update.exe",
            "version.json",
            "_internal/base_library.zip"
        ]
        
        for f in files:
            full_path = os.path.join(source_dir, f)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as fp:
                fp.write(f"内容: {f}")
        
        try:
            copy_directory_atomic(source_dir, target_dir)
            print(f"[OK] copy_directory_atomic成功")
            
            # 验证文件
            for f in files:
                full_path = os.path.join(target_dir, f)
                assert os.path.exists(full_path), f"文件不存在: {full_path}"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            pytest.fail(f"copy_directory_atomic处理中文路径失败: {e}")
    
    def test_parse_args_chinese_path(self):
        """测试命令行参数解析包含中文路径"""
        test_args = [
            "--remote", r"D:\Programs\接口筛选\测试文件\EXE",
            "--local", r"D:\Programs\接口筛选",
            "--version", "2025.11.23.2",
            "--main-exe", "接口筛选.exe",
        ]
        
        try:
            args = parse_args(test_args)
            print(f"[OK] 参数解析成功:")
            print(f"  remote: {args.remote}")
            print(f"  local: {args.local}")
            print(f"  version: {args.version}")
            print(f"  main_exe: {args.main_exe}")
            
            assert args.remote == r"D:\Programs\接口筛选\测试文件\EXE"
            assert args.local == r"D:\Programs\接口筛选"
            assert args.main_exe == "接口筛选.exe"
            
        except Exception as e:
            pytest.fail(f"解析中文路径参数失败: {e}")
    
    def test_os_path_operations_chinese(self, chinese_temp_dir):
        """测试os.path操作中文路径"""
        test_path = os.path.join(chinese_temp_dir, "子目录", "中文文件.txt")
        
        # 测试各种路径操作
        print(f"测试路径: {test_path}")
        print(f"  os.path.dirname: {os.path.dirname(test_path)}")
        print(f"  os.path.basename: {os.path.basename(test_path)}")
        print(f"  os.path.abspath: {os.path.abspath(test_path)}")
        
        # 创建文件测试
        os.makedirs(os.path.dirname(test_path), exist_ok=True)
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write("测试")
        
        assert os.path.exists(test_path)
        print(f"[OK] 中文路径文件操作成功")


class TestUpdateCLIErrorHandling:
    """测试更新CLI的错误处理"""
    
    def test_perform_update_with_nonexistent_remote(self):
        """测试远程目录不存在时的处理"""
        from argparse import Namespace
        
        args = Namespace(
            remote=r"D:\不存在的目录\EXE",
            local=r"D:\本地目录",
            version="1.0.0",
            resume="",
            main_exe="",
            auto_mode=False,
        )
        
        # 应该返回False，而不是崩溃
        result = perform_update(args)
        assert result == False, "远程目录不存在时应返回False"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

