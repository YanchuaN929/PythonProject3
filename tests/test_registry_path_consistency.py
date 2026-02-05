#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 Registry 路径一致性

验证修复：
1. get_data_folder() 正确返回当前设置的路径
2. _ensure_data_folder_from_path() 在 _DATA_FOLDER 已设置时不会覆盖
3. submit_assignment_task() 正确传入 data_folder
4. submit_response_task() 正确传入 data_folder
5. execute_assignment_task() 正确设置 data_folder
6. execute_response_task() 正确设置 data_folder
7. 所有 hooks 函数正确处理路径
"""

import pytest
from unittest.mock import MagicMock, patch
import os
import tempfile


class TestRegistryHooksDataFolder:
    """测试 registry/hooks.py 中的路径处理"""

    def test_get_data_folder_returns_none_when_not_set(self):
        """测试：未设置时 get_data_folder 返回 None"""
        from registry import hooks
        
        # 保存原始值
        original = hooks._DATA_FOLDER
        try:
            hooks._DATA_FOLDER = None
            result = hooks.get_data_folder()
            assert result is None
        finally:
            hooks._DATA_FOLDER = original

    def test_get_data_folder_returns_correct_path(self):
        """测试：已设置时 get_data_folder 返回正确路径"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            test_path = "E:/test/data/folder"
            hooks._DATA_FOLDER = test_path
            result = hooks.get_data_folder()
            assert result == test_path
        finally:
            hooks._DATA_FOLDER = original

    def test_set_data_folder_updates_global(self):
        """测试：set_data_folder 正确更新全局变量"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            with patch.object(hooks, 'load_config', return_value={'registry_enabled': False}):
                test_path = "E:/new/test/path"
                hooks.set_data_folder(test_path)
                assert hooks._DATA_FOLDER == test_path
        finally:
            hooks._DATA_FOLDER = original

    def test_ensure_data_folder_skips_when_already_set(self):
        """测试：_DATA_FOLDER 已设置时，_ensure_data_folder_from_path 不会覆盖"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            # 先设置一个路径
            existing_path = "E:/existing/path"
            hooks._DATA_FOLDER = existing_path
            
            # 调用 _ensure_data_folder_from_path 尝试从另一个路径推导
            different_path = "E:/different/path/file.xlsx"
            hooks._ensure_data_folder_from_path(different_path)
            
            # 验证原路径没有被覆盖
            assert hooks._DATA_FOLDER == existing_path
        finally:
            hooks._DATA_FOLDER = original

    def test_ensure_data_folder_sets_when_not_set(self):
        """测试：_DATA_FOLDER 未设置时，_ensure_data_folder_from_path 会尝试推导"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            hooks._DATA_FOLDER = None
            
            # 使用临时目录创建测试路径
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = os.path.join(tmpdir, "test.xlsx")
                hooks._ensure_data_folder_from_path(test_file)
                
                # 验证路径已被设置（应该是文件所在目录）
                assert hooks._DATA_FOLDER is not None
        finally:
            hooks._DATA_FOLDER = original


class TestRegistryConfigCacheRefresh:
    """测试 registry/config.get_config 的缓存刷新逻辑"""

    def test_get_config_refreshes_with_data_folder(self, tmp_path):
        from registry import config as registry_config
        from registry import hooks as registry_hooks

        original_cache = registry_config._config_cache
        original_folder = registry_hooks._DATA_FOLDER
        try:
            registry_hooks._DATA_FOLDER = str(tmp_path / "data")
            registry_config._config_cache = registry_config.load_config(
                data_folder=None,
                ensure_registry_dir=False,
            )

            cfg = registry_config.get_config()
            expected = str(tmp_path / "data" / ".registry" / "registry.db")
            assert cfg.get("registry_db_path") == expected
        finally:
            registry_config._config_cache = original_cache
            registry_hooks._DATA_FOLDER = original_folder


class TestRegistryDbConnectionSwitch:
    """测试 registry/db.py 连接切换逻辑"""

    def test_get_connection_switches_on_db_path_change(self, tmp_path):
        """测试：db_path 变化时应切换连接"""
        from registry import db as registry_db

        db_path1 = tmp_path / "data1" / ".registry" / "registry.db"
        db_path2 = tmp_path / "data2" / ".registry" / "registry.db"

        conn1 = registry_db.get_connection(str(db_path1), wal=False)
        conn1_id = id(conn1)

        conn2 = registry_db.get_connection(str(db_path2), wal=False)
        conn2_id = id(conn2)

        assert conn1_id != conn2_id
        assert registry_db._DB_PATH == str(db_path2)

        registry_db.close_connection()


class TestRegistryDbLocalCacheSwitch:
    """测试本地缓存管理器在路径变化时重置"""

    def test_get_read_connection_resets_local_cache_on_path_change(self, tmp_path, monkeypatch):
        from registry import db as registry_db

        class DummyCache:
            def __init__(self, path):
                self.network_db_path = path
                self.cleaned = False

            def cleanup(self):
                self.cleaned = True

        original_cache = registry_db._local_cache_manager
        original_enabled = registry_db._local_cache_enabled
        try:
            registry_db._local_cache_enabled = True
            registry_db._local_cache_manager = DummyCache("old_path")

            monkeypatch.setattr(registry_db, "ensure_not_in_maintenance", lambda **_kwargs: None)
            monkeypatch.setattr(registry_db, "_is_network_path", lambda _p: False)
            monkeypatch.setattr(registry_db, "get_connection", lambda _p, wal=True: "conn")

            conn = registry_db.get_read_connection(str(tmp_path / "new.db"))
            assert conn == "conn"
            assert registry_db._local_cache_manager is None
        finally:
            registry_db._local_cache_manager = original_cache
            registry_db._local_cache_enabled = original_enabled


class TestRegistryDbIsolatedConnection:
    """测试独立连接不影响全局连接"""

    def test_open_isolated_connection_does_not_touch_global_conn(self, tmp_path):
        from registry import db as registry_db

        registry_db.close_connection()
        db_path = tmp_path / "data" / ".registry" / "registry.db"

        conn = registry_db.open_isolated_connection(str(db_path), wal=False)
        try:
            conn.execute("SELECT 1").fetchone()
            assert registry_db._CONN is None
        finally:
            conn.close()


class TestWriteTasksManager:
    """测试 write_tasks/manager.py 中的路径处理"""

    def test_submit_assignment_task_includes_data_folder(self):
        """测试：submit_assignment_task 正确包含 data_folder"""
        from write_tasks.manager import WriteTaskManager
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            # 设置测试路径
            test_data_folder = "E:/test/data/folder"
            hooks._DATA_FOLDER = test_data_folder
            
            # 创建 manager（mock 缓存和队列）
            with patch('write_tasks.manager.WriteTaskCache'):
                manager = WriteTaskManager.__new__(WriteTaskManager)
                manager.tasks = {}
                manager.cache = MagicMock()
                manager._queue = MagicMock()
                manager._listeners = []
                
                # Mock _sync_to_shared_log
                manager._sync_to_shared_log = MagicMock()
                
                # 调用 submit_assignment_task
                assignments = [{"interface_id": "S-TEST-01", "assigned_name": "测试人"}]
                task = manager.submit_assignment_task(assignments, "提交者", "测试描述")
                
                # 验证 payload 包含 data_folder
                assert "data_folder" in task.payload
                assert task.payload["data_folder"] == test_data_folder
        finally:
            hooks._DATA_FOLDER = original

    def test_submit_response_task_includes_data_folder(self):
        """测试：submit_response_task 正确包含 data_folder"""
        from write_tasks.manager import WriteTaskManager
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            # 设置测试路径
            test_data_folder = "E:/test/data/folder"
            hooks._DATA_FOLDER = test_data_folder
            
            # 创建 manager
            with patch('write_tasks.manager.WriteTaskCache'):
                manager = WriteTaskManager.__new__(WriteTaskManager)
                manager.tasks = {}
                manager.cache = MagicMock()
                manager._queue = MagicMock()
                manager._listeners = []
                manager._sync_to_shared_log = MagicMock()
                
                # 调用 submit_response_task
                task = manager.submit_response_task(
                    file_path="E:/test/file.xlsx",
                    file_type=1,
                    row_index=10,
                    interface_id="S-TEST-01",
                    response_number="HFMR001",
                    user_name="测试用户",
                    project_id="2024",
                    source_column="回复列",
                    description="测试回复"
                )
                
                # 验证 payload 包含 data_folder
                assert "data_folder" in task.payload
                assert task.payload["data_folder"] == test_data_folder
        finally:
            hooks._DATA_FOLDER = original


class TestWriteTasksExecutors:
    """测试 write_tasks/executors.py 中的路径处理"""

    def test_execute_assignment_task_sets_data_folder(self):
        """测试：execute_assignment_task 正确设置 data_folder"""
        from write_tasks import executors
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            hooks._DATA_FOLDER = None
            
            test_data_folder = "E:/test/assignment/folder"
            
            # Mock save_assignments_batch（在被导入的模块中 patch）
            with patch('services.distribution.save_assignments_batch') as mock_save:
                mock_save.return_value = {'success_count': 1, 'failed_tasks': []}
                
                payload = {
                    "assignments": [{"interface_id": "S-TEST-01"}],
                    "data_folder": test_data_folder
                }
                
                executors.execute_assignment_task(payload)
                
                # 验证 data_folder 被设置
                assert hooks._DATA_FOLDER == test_data_folder
        finally:
            hooks._DATA_FOLDER = original

    def test_execute_response_task_sets_data_folder(self):
        """测试：execute_response_task 正确设置 data_folder"""
        from write_tasks import executors
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            hooks._DATA_FOLDER = None
            
            test_data_folder = "E:/test/response/folder"
            
            # Mock write_response_to_excel（在被导入的模块中 patch）
            with patch('ui.input_handler.write_response_to_excel') as mock_write:
                mock_write.return_value = True
                
                with patch.object(hooks, 'on_response_written'):
                    payload = {
                        "file_path": "E:/test/file.xlsx",
                        "file_type": 1,
                        "row_index": 10,
                        "interface_id": "S-TEST-01",
                        "response_number": "HFMR001",
                        "user_name": "测试用户",
                        "project_id": "2024",
                        "data_folder": test_data_folder
                    }
                    
                    executors.execute_response_task(payload)
                    
                    # 验证 data_folder 被设置
                    assert hooks._DATA_FOLDER == test_data_folder
        finally:
            hooks._DATA_FOLDER = original

    def test_execute_assignment_task_without_data_folder(self):
        """测试：execute_assignment_task 在无 data_folder 时不会报错"""
        from write_tasks import executors
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            existing_path = "E:/existing/path"
            hooks._DATA_FOLDER = existing_path
            
            with patch('services.distribution.save_assignments_batch') as mock_save:
                mock_save.return_value = {'success_count': 0, 'failed_tasks': []}
                
                # payload 不包含 data_folder
                payload = {"assignments": []}
                
                # 不应该报错
                executors.execute_assignment_task(payload)
                
                # 原路径应保持不变
                assert hooks._DATA_FOLDER == existing_path
        finally:
            hooks._DATA_FOLDER = original


class TestRegistryHooksPathHandling:
    """测试各个 hooks 函数的路径处理"""

    def test_on_assigned_uses_ensure_data_folder(self):
        """测试：on_assigned 调用 _ensure_data_folder_from_path"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            test_path = "E:/test/on_assigned"
            hooks._DATA_FOLDER = test_path
            
            with patch.object(hooks, '_cfg', return_value={'registry_enabled': False}):
                hooks.on_assigned(
                    file_type=1,
                    file_path="E:/other/path/file.xlsx",
                    row_index=10,
                    interface_id="S-TEST-01",
                    project_id="2024",
                    assigned_by="测试人",
                    assigned_to="被指派人"
                )
                
                # 原路径不应被覆盖
                assert hooks._DATA_FOLDER == test_path
        finally:
            hooks._DATA_FOLDER = original

    def test_on_response_written_uses_ensure_data_folder(self):
        """测试：on_response_written 调用 _ensure_data_folder_from_path"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            test_path = "E:/test/on_response"
            hooks._DATA_FOLDER = test_path
            
            with patch.object(hooks, '_cfg', return_value={'registry_enabled': False}):
                hooks.on_response_written(
                    file_type=1,
                    file_path="E:/other/path/file.xlsx",
                    row_index=10,
                    interface_id="S-TEST-01",
                    response_number="HFMR001",
                    user_name="测试用户",
                    project_id="2024"
                )
                
                # 原路径不应被覆盖
                assert hooks._DATA_FOLDER == test_path
        finally:
            hooks._DATA_FOLDER = original

    def test_on_export_done_uses_ensure_data_folder(self):
        """测试：on_export_done 调用 _ensure_data_folder_from_path"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            test_path = "E:/test/on_export"
            hooks._DATA_FOLDER = test_path
            
            with patch.object(hooks, '_cfg', return_value={'registry_enabled': False}):
                hooks.on_export_done(
                    file_type=1,
                    project_id="2024",
                    export_path="E:/other/export/file.xlsx",
                    count=100
                )
                
                # 原路径不应被覆盖
                assert hooks._DATA_FOLDER == test_path
        finally:
            hooks._DATA_FOLDER = original

    def test_on_confirmed_by_superior_uses_ensure_data_folder(self):
        """测试：on_confirmed_by_superior 调用 _ensure_data_folder_from_path"""
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            test_path = "E:/test/on_confirmed"
            hooks._DATA_FOLDER = test_path
            
            with patch.object(hooks, '_cfg', return_value={'registry_enabled': False}):
                hooks.on_confirmed_by_superior(
                    file_type=1,
                    file_path="E:/other/path/file.xlsx",
                    row_index=10,
                    user_name="上级用户",
                    project_id="2024",
                    interface_id="S-TEST-01"
                )
                
                # 原路径不应被覆盖
                assert hooks._DATA_FOLDER == test_path
        finally:
            hooks._DATA_FOLDER = original


class TestEndToEndPathConsistency:
    """端到端路径一致性测试"""

    def test_assignment_flow_path_consistency(self):
        """测试：指派任务完整流程中路径保持一致"""
        from write_tasks.manager import WriteTaskManager
        from write_tasks import executors
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            # 1. 设置初始路径（模拟用户刷新文件列表）
            user_selected_path = "E:/user/selected/path"
            hooks._DATA_FOLDER = user_selected_path
            
            # 2. 创建并提交任务
            with patch('write_tasks.manager.WriteTaskCache'):
                manager = WriteTaskManager.__new__(WriteTaskManager)
                manager.tasks = {}
                manager.cache = MagicMock()
                manager._queue = MagicMock()
                manager._listeners = []
                manager._sync_to_shared_log = MagicMock()
                
                task = manager.submit_assignment_task(
                    assignments=[{"interface_id": "S-TEST-01", "assigned_name": "测试"}],
                    submitted_by="提交者",
                    description="测试"
                )
                
                # 验证 payload 中的路径
                assert task.payload["data_folder"] == user_selected_path
            
            # 3. 模拟执行器执行（先重置 _DATA_FOLDER 模拟后台线程环境）
            hooks._DATA_FOLDER = None
            
            with patch('services.distribution.save_assignments_batch') as mock_save:
                mock_save.return_value = {'success_count': 1, 'failed_tasks': []}
                executors.execute_assignment_task(task.payload)
                
                # 验证路径被正确恢复
                assert hooks._DATA_FOLDER == user_selected_path
        finally:
            hooks._DATA_FOLDER = original

    def test_response_flow_path_consistency(self):
        """测试：回文单号写入完整流程中路径保持一致"""
        from write_tasks.manager import WriteTaskManager
        from write_tasks import executors
        from registry import hooks
        
        original = hooks._DATA_FOLDER
        try:
            # 1. 设置初始路径
            user_selected_path = "E:/user/selected/path"
            hooks._DATA_FOLDER = user_selected_path
            
            # 2. 创建并提交任务
            with patch('write_tasks.manager.WriteTaskCache'):
                manager = WriteTaskManager.__new__(WriteTaskManager)
                manager.tasks = {}
                manager.cache = MagicMock()
                manager._queue = MagicMock()
                manager._listeners = []
                manager._sync_to_shared_log = MagicMock()
                
                task = manager.submit_response_task(
                    file_path="E:/test/file.xlsx",
                    file_type=1,
                    row_index=10,
                    interface_id="S-TEST-01",
                    response_number="HFMR001",
                    user_name="测试用户",
                    project_id="2024",
                    source_column="回复列",
                    description="测试"
                )
                
                # 验证 payload 中的路径
                assert task.payload["data_folder"] == user_selected_path
            
            # 3. 模拟执行器执行
            hooks._DATA_FOLDER = None
            
            with patch('ui.input_handler.write_response_to_excel') as mock_write:
                mock_write.return_value = True
                with patch.object(hooks, 'on_response_written'):
                    executors.execute_response_task(task.payload)
                    
                    # 验证路径被正确恢复
                    assert hooks._DATA_FOLDER == user_selected_path
        finally:
            hooks._DATA_FOLDER = original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
