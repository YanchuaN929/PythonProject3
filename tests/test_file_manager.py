# -*- coding: utf-8 -*-
"""
测试文件标识管理器

测试内容：
1. 文件标识生成（基于文件名+大小+修改时间）
2. 勾选状态持久化（JSON格式）
3. 文件变化检测
4. 清空勾选逻辑
"""

import pytest
import os
import json
import time
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from file_manager import FileIdentityManager


class TestFileIdentityManager:
    """测试文件标识管理器"""
    
    def test_generate_file_identity(self, tmp_path):
        """测试文件标识生成"""
        # 创建临时文件
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("test content", encoding='utf-8')
        
        # 创建管理器
        manager = FileIdentityManager(cache_file=str(tmp_path / "test_cache.json"))
        
        # 生成标识
        identity1 = manager.generate_file_identity(str(test_file))
        
        assert identity1 is not None, "应该成功生成文件标识"
        assert isinstance(identity1, str), "标识应该是字符串"
        assert len(identity1) == 32, "MD5哈希应该是32个字符"
        
        # 再次生成，应该相同
        identity2 = manager.generate_file_identity(str(test_file))
        assert identity1 == identity2, "相同文件应该生成相同标识"
    
    def test_file_identity_changes_on_modification(self, tmp_path):
        """测试文件修改后标识变化"""
        test_file = tmp_path / "test.xlsx"
        test_file.write_text("original content", encoding='utf-8')
        
        manager = FileIdentityManager(cache_file=str(tmp_path / "test_cache.json"))
        
        # 生成初始标识
        identity1 = manager.generate_file_identity(str(test_file))
        
        # 等待一小段时间确保修改时间不同
        time.sleep(0.1)
        
        # 修改文件
        test_file.write_text("modified content", encoding='utf-8')
        
        # 重新生成标识
        identity2 = manager.generate_file_identity(str(test_file))
        
        assert identity1 != identity2, "文件修改后标识应该改变"
    
    def test_set_and_get_row_completed(self, tmp_path):
        """测试勾选状态设置和查询"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        file_path = "test_file.xlsx"
        
        # 设置行完成状态
        manager.set_row_completed(file_path, 5, True)
        manager.set_row_completed(file_path, 10, True)
        manager.set_row_completed(file_path, 15, True)
        
        # 查询状态
        assert manager.is_row_completed(file_path, 5) == True
        assert manager.is_row_completed(file_path, 10) == True
        assert manager.is_row_completed(file_path, 15) == True
        assert manager.is_row_completed(file_path, 20) == False
    
    def test_get_completed_rows(self, tmp_path):
        """测试获取所有已完成行"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        file_path = "test_file.xlsx"
        
        # 设置多行完成
        manager.set_row_completed(file_path, 2, True)
        manager.set_row_completed(file_path, 4, True)
        manager.set_row_completed(file_path, 6, True)
        
        # 获取所有已完成行
        completed = manager.get_completed_rows(file_path)
        
        assert completed == {2, 4, 6}
    
    def test_clear_row_completed(self, tmp_path):
        """测试取消勾选"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        file_path = "test_file.xlsx"
        
        # 设置勾选
        manager.set_row_completed(file_path, 5, True)
        assert manager.is_row_completed(file_path, 5) == True
        
        # 取消勾选
        manager.set_row_completed(file_path, 5, False)
        assert manager.is_row_completed(file_path, 5) == False
    
    def test_persistence(self, tmp_path):
        """测试持久化功能"""
        cache_file = tmp_path / "test_cache.json"
        
        # 第一个管理器实例
        manager1 = FileIdentityManager(cache_file=str(cache_file))
        manager1.set_row_completed("file1.xlsx", 10, True)
        manager1.set_row_completed("file1.xlsx", 20, True)
        manager1.file_identities["file1.xlsx"] = "abc123"
        manager1._save_cache()
        
        # 创建新的管理器实例（模拟程序重启）
        manager2 = FileIdentityManager(cache_file=str(cache_file))
        
        # 验证数据已恢复
        assert manager2.is_row_completed("file1.xlsx", 10) == True
        assert manager2.is_row_completed("file1.xlsx", 20) == True
        assert manager2.file_identities.get("file1.xlsx") == "abc123"
    
    def test_check_files_changed_new_file(self, tmp_path):
        """测试检测新文件"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 创建新文件
        test_file = tmp_path / "new_file.xlsx"
        test_file.write_text("content", encoding='utf-8')
        
        # 检测变化（新文件，缓存中没有）
        changed = manager.check_files_changed([str(test_file)])
        
        assert changed == True, "新文件应该被检测为变化"
    
    def test_check_files_changed_no_change(self, tmp_path):
        """测试无变化的情况"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 创建文件并更新标识
        test_file = tmp_path / "file.xlsx"
        test_file.write_text("content", encoding='utf-8')
        manager.update_file_identities([str(test_file)])
        
        # 再次检测（无变化）
        changed = manager.check_files_changed([str(test_file)])
        
        assert changed == False, "未修改的文件不应该被检测为变化"
    
    def test_check_files_changed_file_modified(self, tmp_path):
        """测试检测文件修改"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 创建文件并更新标识
        test_file = tmp_path / "file.xlsx"
        test_file.write_text("original", encoding='utf-8')
        manager.update_file_identities([str(test_file)])
        
        # 等待并修改文件
        time.sleep(0.1)
        test_file.write_text("modified", encoding='utf-8')
        
        # 检测变化
        changed = manager.check_files_changed([str(test_file)])
        
        assert changed == True, "修改后的文件应该被检测为变化"
    
    def test_check_files_changed_multiple_files_one_changed(self, tmp_path):
        """测试多文件中有一个变化的情况"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 创建多个文件
        file1 = tmp_path / "file1.xlsx"
        file2 = tmp_path / "file2.xlsx"
        file3 = tmp_path / "file3.xlsx"
        
        file1.write_text("content1", encoding='utf-8')
        file2.write_text("content2", encoding='utf-8')
        file3.write_text("content3", encoding='utf-8')
        
        # 更新所有文件的标识
        manager.update_file_identities([str(file1), str(file2), str(file3)])
        
        # 修改其中一个文件
        time.sleep(0.1)
        file2.write_text("modified content2", encoding='utf-8')
        
        # 检测变化
        changed = manager.check_files_changed([str(file1), str(file2), str(file3)])
        
        assert changed == True, "多文件中有一个变化，应该检测为变化"
    
    def test_clear_all_completed_rows(self, tmp_path):
        """测试清空所有勾选"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 为多个文件设置勾选
        manager.set_row_completed("file1.xlsx", 5, True)
        manager.set_row_completed("file1.xlsx", 10, True)
        manager.set_row_completed("file2.xlsx", 3, True)
        manager.set_row_completed("file3.xlsx", 7, True)
        
        # 清空所有勾选
        manager.clear_all_completed_rows()
        
        # 验证所有勾选已清空
        assert manager.get_completed_rows("file1.xlsx") == set()
        assert manager.get_completed_rows("file2.xlsx") == set()
        assert manager.get_completed_rows("file3.xlsx") == set()
    
    def test_clear_file_completed_rows(self, tmp_path):
        """测试清空指定文件的勾选"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 为多个文件设置勾选
        manager.set_row_completed("file1.xlsx", 5, True)
        manager.set_row_completed("file2.xlsx", 10, True)
        
        # 清空file1的勾选
        manager.clear_file_completed_rows("file1.xlsx")
        
        # 验证file1已清空，file2保留
        assert manager.get_completed_rows("file1.xlsx") == set()
        assert manager.get_completed_rows("file2.xlsx") == {10}
    
    def test_update_file_identities(self, tmp_path):
        """测试更新文件标识"""
        cache_file = tmp_path / "test_cache.json"
        manager = FileIdentityManager(cache_file=str(cache_file))
        
        # 创建文件
        file1 = tmp_path / "file1.xlsx"
        file2 = tmp_path / "file2.xlsx"
        file1.write_text("content1", encoding='utf-8')
        file2.write_text("content2", encoding='utf-8')
        
        # 更新标识
        manager.update_file_identities([str(file1), str(file2)])
        
        # 验证标识已存储
        assert str(file1) in manager.file_identities
        assert str(file2) in manager.file_identities
        assert manager.file_identities[str(file1)] is not None
        assert manager.file_identities[str(file2)] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

