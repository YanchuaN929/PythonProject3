"""
测试用户间勾选状态隔离

验证当用户切换时,勾选状态不会互相影响
"""
import pytest
import os
import json
import tempfile
from file_manager import FileIdentityManager


class TestUserCheckboxIsolation:
    """测试用户间勾选状态隔离"""
    
    @pytest.fixture
    def temp_cache_file(self):
        """创建临时缓存文件"""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        # 清理
        if os.path.exists(path):
            os.remove(path)
    
    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        import tempfile
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # 清理
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_different_users_different_checkboxes(self, temp_cache_file, temp_cache_dir):
        """测试不同用户的勾选状态相互独立"""
        manager = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        file_path = "test_file.xlsx"
        
        # 用户A勾选行1和行2
        manager.set_row_completed(file_path, 1, True, user_name="用户A")
        manager.set_row_completed(file_path, 2, True, user_name="用户A")
        
        # 用户B勾选行3和行4
        manager.set_row_completed(file_path, 3, True, user_name="用户B")
        manager.set_row_completed(file_path, 4, True, user_name="用户B")
        
        # 验证用户A的勾选状态
        assert manager.is_row_completed(file_path, 1, user_name="用户A") == True
        assert manager.is_row_completed(file_path, 2, user_name="用户A") == True
        assert manager.is_row_completed(file_path, 3, user_name="用户A") == False  # 用户B的数据
        assert manager.is_row_completed(file_path, 4, user_name="用户A") == False  # 用户B的数据
        
        # 验证用户B的勾选状态
        assert manager.is_row_completed(file_path, 1, user_name="用户B") == False  # 用户A的数据
        assert manager.is_row_completed(file_path, 2, user_name="用户B") == False  # 用户A的数据
        assert manager.is_row_completed(file_path, 3, user_name="用户B") == True
        assert manager.is_row_completed(file_path, 4, user_name="用户B") == True
        
        # 验证get_completed_rows
        completed_a = manager.get_completed_rows(file_path, user_name="用户A")
        completed_b = manager.get_completed_rows(file_path, user_name="用户B")
        
        assert completed_a == {1, 2}
        assert completed_b == {3, 4}
    
    def test_user_switch_preserves_checkboxes(self, temp_cache_file, temp_cache_dir):
        """测试用户切换后重新加载,勾选状态保留"""
        file_path = "test_file.xlsx"
        
        # 第一次使用：用户A勾选
        manager1 = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        manager1.set_row_completed(file_path, 10, True, user_name="用户A")
        manager1.set_row_completed(file_path, 20, True, user_name="用户A")
        
        # 用户B勾选
        manager1.set_row_completed(file_path, 30, True, user_name="用户B")
        
        # 模拟程序重启：创建新的manager实例
        manager2 = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        # 验证用户A的勾选状态仍然存在
        assert manager2.is_row_completed(file_path, 10, user_name="用户A") == True
        assert manager2.is_row_completed(file_path, 20, user_name="用户A") == True
        assert manager2.is_row_completed(file_path, 30, user_name="用户A") == False
        
        # 验证用户B的勾选状态仍然存在
        assert manager2.is_row_completed(file_path, 10, user_name="用户B") == False
        assert manager2.is_row_completed(file_path, 20, user_name="用户B") == False
        assert manager2.is_row_completed(file_path, 30, user_name="用户B") == True
    
    def test_old_format_migration(self, temp_cache_file, temp_cache_dir):
        """测试旧格式缓存自动迁移到新格式"""
        # 手动创建旧格式缓存文件
        old_format_data = {
            "file_identities": {},
            "completed_rows": {
                "file1.xlsx": {
                    "1": True,
                    "2": True
                },
                "file2.xlsx": {
                    "10": True
                }
            },
            "last_update": "2025-01-01T00:00:00"
        }
        
        with open(temp_cache_file, 'w', encoding='utf-8') as f:
            json.dump(old_format_data, f)
        
        # 加载旧格式缓存
        manager = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        # 验证旧数据被迁移到"默认用户"
        assert manager.is_row_completed("file1.xlsx", 1, user_name="默认用户") == True
        assert manager.is_row_completed("file1.xlsx", 2, user_name="默认用户") == True
        assert manager.is_row_completed("file2.xlsx", 10, user_name="默认用户") == True
        
        # 验证新格式保存
        completed_default = manager.get_completed_rows("file1.xlsx", user_name="默认用户")
        assert completed_default == {1, 2}
    
    def test_new_format_structure(self, temp_cache_file, temp_cache_dir):
        """测试新格式的缓存文件结构"""
        manager = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        # 设置不同用户的勾选
        manager.set_row_completed("file1.xlsx", 1, True, user_name="张三")
        manager.set_row_completed("file1.xlsx", 2, True, user_name="李四")
        
        # 读取缓存文件验证结构
        with open(temp_cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 验证新格式结构: {user: {file: {row: bool}}}
        assert "completed_rows" in data
        assert "张三" in data["completed_rows"]
        assert "李四" in data["completed_rows"]
        assert "file1.xlsx" in data["completed_rows"]["张三"]
        assert "file1.xlsx" in data["completed_rows"]["李四"]
        assert "1" in data["completed_rows"]["张三"]["file1.xlsx"]
        assert "2" in data["completed_rows"]["李四"]["file1.xlsx"]
    
    def test_clear_file_for_specific_user(self, temp_cache_file, temp_cache_dir):
        """测试清空指定用户的指定文件"""
        manager = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        file_path = "test_file.xlsx"
        
        # 两个用户都勾选同一文件
        manager.set_row_completed(file_path, 1, True, user_name="用户A")
        manager.set_row_completed(file_path, 2, True, user_name="用户B")
        
        # 清空用户A的该文件
        manager.clear_file_completed_rows(file_path, user_name="用户A")
        
        # 验证用户A的勾选被清空
        assert manager.is_row_completed(file_path, 1, user_name="用户A") == False
        
        # 验证用户B的勾选仍然存在
        assert manager.is_row_completed(file_path, 2, user_name="用户B") == True
    
    def test_clear_file_for_all_users(self, temp_cache_file, temp_cache_dir):
        """测试清空所有用户的指定文件"""
        manager = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        file_path = "test_file.xlsx"
        
        # 多个用户勾选同一文件
        manager.set_row_completed(file_path, 1, True, user_name="用户A")
        manager.set_row_completed(file_path, 2, True, user_name="用户B")
        manager.set_row_completed(file_path, 3, True, user_name="用户C")
        
        # 清空所有用户的该文件（不传user_name）
        manager.clear_file_completed_rows(file_path)
        
        # 验证所有用户的勾选都被清空
        assert manager.is_row_completed(file_path, 1, user_name="用户A") == False
        assert manager.is_row_completed(file_path, 2, user_name="用户B") == False
        assert manager.is_row_completed(file_path, 3, user_name="用户C") == False


class TestDefaultUserHandling:
    """测试默认用户处理"""
    
    @pytest.fixture
    def temp_cache_file(self):
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)
    
    @pytest.fixture
    def temp_cache_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_empty_username_defaults_to_default_user(self, temp_cache_file, temp_cache_dir):
        """测试空用户名自动使用'默认用户'"""
        manager = FileIdentityManager(cache_file=temp_cache_file, result_cache_dir=temp_cache_dir)
        
        file_path = "test_file.xlsx"
        
        # 使用空用户名勾选
        manager.set_row_completed(file_path, 1, True, user_name="")
        
        # 验证数据被存储到"默认用户"
        assert manager.is_row_completed(file_path, 1, user_name="") == True
        assert manager.is_row_completed(file_path, 1, user_name="默认用户") == True
        
        # 验证get_completed_rows
        completed_empty = manager.get_completed_rows(file_path, user_name="")
        completed_default = manager.get_completed_rows(file_path, user_name="默认用户")
        assert completed_empty == {1}
        assert completed_default == {1}

