#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指派记忆功能测试模块

测试内容：
1. AssignmentMemory 类的核心功能
2. 指派记忆的保存、获取、批量保存、清除
3. 接口号规范化（去除角色后缀）
4. apply_assignment_memory 辅助函数
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


# 标记整个模块跳过 conftest.py 中的 autouse fixture（避免创建Tkinter窗口）
pytestmark = pytest.mark.allow_empty_name


@pytest.fixture
def temp_storage_path():
    """创建临时存储路径"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "assignment_memory.json"
        yield storage_path


@pytest.fixture
def memory_instance(temp_storage_path):
    """创建指派记忆实例"""
    from services.assignment_memory import AssignmentMemory
    return AssignmentMemory(storage_path=temp_storage_path)


@pytest.fixture
def reset_singleton():
    """重置单例"""
    import services.assignment_memory as am
    am._memory_instance = None
    yield
    am._memory_instance = None


class TestAssignmentMemory:
    """指派记忆模块测试"""

    def test_save_and_get_memory(self, memory_instance):
        """测试保存和获取单条记忆"""
        # 保存记忆
        memory_instance.save_memory(
            file_type=1,
            project_id="1907",
            interface_id="HQ-TA-3999",
            assigned_name="张三"
        )

        # 获取记忆
        result = memory_instance.get_memory(
            file_type=1,
            project_id="1907",
            interface_id="HQ-TA-3999"
        )

        assert result == "张三"

    def test_get_memory_not_found(self, memory_instance):
        """测试获取不存在的记忆"""
        result = memory_instance.get_memory(
            file_type=1,
            project_id="9999",
            interface_id="NOT-EXIST"
        )
        assert result is None

    def test_normalize_interface_id_with_role_suffix(self, memory_instance):
        """测试接口号规范化 - 去除角色后缀"""
        # 保存带角色后缀的接口号
        memory_instance.save_memory(
            file_type=2,
            project_id="1818",
            interface_id="HQ-TA-4000(设计人员)",
            assigned_name="李四"
        )

        # 用不带后缀的接口号获取
        result = memory_instance.get_memory(
            file_type=2,
            project_id="1818",
            interface_id="HQ-TA-4000"
        )
        assert result == "李四"

        # 用带后缀的接口号获取（应该也能找到，因为规范化后是一样的）
        result2 = memory_instance.get_memory(
            file_type=2,
            project_id="1818",
            interface_id="HQ-TA-4000(设计人员)"
        )
        assert result2 == "李四"

    def test_batch_save_memories(self, memory_instance):
        """测试批量保存记忆"""
        assignments = [
            {
                'file_type': 1,
                'project_id': '1907',
                'interface_id': 'HQ-TA-001',
                'assigned_name': '张三'
            },
            {
                'file_type': 1,
                'project_id': '1907',
                'interface_id': 'HQ-TA-002',
                'assigned_name': '李四'
            },
            {
                'file_type': 2,
                'project_id': '1818',
                'interface_id': 'HQ-TA-003',
                'assigned_name': '王五'
            },
            # 空的assigned_name应该被跳过
            {
                'file_type': 1,
                'project_id': '1907',
                'interface_id': 'HQ-TA-004',
                'assigned_name': ''
            },
        ]

        count = memory_instance.batch_save_memories(assignments)

        # 只有3条有效记忆被保存
        assert count == 3
        assert memory_instance.get_memory(1, '1907', 'HQ-TA-001') == '张三'
        assert memory_instance.get_memory(1, '1907', 'HQ-TA-002') == '李四'
        assert memory_instance.get_memory(2, '1818', 'HQ-TA-003') == '王五'
        assert memory_instance.get_memory(1, '1907', 'HQ-TA-004') is None

    def test_clear_memory(self, memory_instance):
        """测试清除单条记忆"""
        # 先保存
        memory_instance.save_memory(1, '1907', 'HQ-TA-001', '张三')
        assert memory_instance.get_memory(1, '1907', 'HQ-TA-001') == '张三'

        # 清除
        result = memory_instance.clear_memory(1, '1907', 'HQ-TA-001')
        assert result is True
        assert memory_instance.get_memory(1, '1907', 'HQ-TA-001') is None

        # 清除不存在的记忆
        result2 = memory_instance.clear_memory(1, '9999', 'NOT-EXIST')
        assert result2 is False

    def test_clear_all(self, memory_instance):
        """测试清除所有记忆"""
        memory_instance.save_memory(1, '1907', 'HQ-TA-001', '张三')
        memory_instance.save_memory(2, '1818', 'HQ-TA-002', '李四')
        assert memory_instance.get_memory_count() == 2

        memory_instance.clear_all()
        assert memory_instance.get_memory_count() == 0

    def test_persistence(self, temp_storage_path):
        """测试记忆持久化"""
        from services.assignment_memory import AssignmentMemory

        # 第一个实例保存记忆
        memory1 = AssignmentMemory(storage_path=temp_storage_path)
        memory1.save_memory(1, '1907', 'HQ-TA-001', '张三')

        # 第二个实例应该能读取到
        memory2 = AssignmentMemory(storage_path=temp_storage_path)
        result = memory2.get_memory(1, '1907', 'HQ-TA-001')
        assert result == '张三'

    def test_key_format(self, memory_instance):
        """测试key格式"""
        key = memory_instance._make_key(1, '1907', 'HQ-TA-3999')
        assert key == '1|1907|HQ-TA-3999'

    def test_different_file_types_same_interface(self, memory_instance):
        """测试不同文件类型相同接口号的记忆是独立的"""
        # 同一个接口号在不同文件类型中可能有不同的指派
        memory_instance.save_memory(1, '1907', 'HQ-TA-001', '张三')
        memory_instance.save_memory(2, '1907', 'HQ-TA-001', '李四')

        assert memory_instance.get_memory(1, '1907', 'HQ-TA-001') == '张三'
        assert memory_instance.get_memory(2, '1907', 'HQ-TA-001') == '李四'


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_get_assignment_memory_singleton(self, tmp_path, monkeypatch, reset_singleton):
        """测试单例模式"""
        # Mock LOCALAPPDATA
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import get_assignment_memory

        instance1 = get_assignment_memory()
        instance2 = get_assignment_memory()
        assert instance1 is instance2

    def test_convenience_functions(self, tmp_path, monkeypatch, reset_singleton):
        """测试便捷函数"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import (
            save_memory, get_memory, batch_save_memories, clear_memory
        )

        # 保存
        save_memory(1, '1907', 'HQ-TA-001', '张三')

        # 获取
        result = get_memory(1, '1907', 'HQ-TA-001')
        assert result == '张三'

        # 批量保存
        count = batch_save_memories([
            {'file_type': 2, 'project_id': '1818', 'interface_id': 'HQ-TA-002', 'assigned_name': '李四'}
        ])
        assert count == 1

        # 清除
        result = clear_memory(1, '1907', 'HQ-TA-001')
        assert result is True


class TestApplyAssignmentMemory:
    """测试 apply_assignment_memory 辅助函数"""

    def test_apply_memory_fills_empty_responsible(self, tmp_path, monkeypatch, reset_singleton):
        """测试：为空责任人填充记忆"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import save_memory
        from core.main import apply_assignment_memory

        # 创建测试DataFrame
        sample_df = pd.DataFrame({
            '项目号': ['1907', '1907', '1818', '1818'],
            '接口号': ['HQ-TA-001', 'HQ-TA-002', 'HQ-TA-003', 'HQ-TA-004'],
            '责任人': ['', '已有责任人', '', ''],
            'source_file': ['file1.xlsx'] * 4,
            '原始行号': [2, 3, 4, 5],
        })

        # 预先保存记忆
        save_memory(1, '1907', 'HQ-TA-001', '张三')
        save_memory(1, '1818', 'HQ-TA-003', '王五')

        # 应用记忆
        result_df = apply_assignment_memory(sample_df.copy(), file_type=1)

        # 验证结果
        assert result_df.loc[0, '责任人'] == '张三'  # 从记忆填充
        assert result_df.loc[1, '责任人'] == '已有责任人'  # 保持原值
        assert result_df.loc[2, '责任人'] == '王五'  # 从记忆填充
        assert result_df.loc[3, '责任人'] == ''  # 没有记忆，保持为空

    def test_apply_memory_respects_existing_responsible(self, tmp_path, monkeypatch, reset_singleton):
        """测试：不覆盖已有责任人"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import save_memory
        from core.main import apply_assignment_memory

        sample_df = pd.DataFrame({
            '项目号': ['1907'],
            '接口号': ['HQ-TA-002'],
            '责任人': ['已有责任人'],
        })

        # 为第2行也保存记忆
        save_memory(1, '1907', 'HQ-TA-002', '李四')

        result_df = apply_assignment_memory(sample_df.copy(), file_type=1)

        # 应该保持"已有责任人"，不被覆盖
        assert result_df.loc[0, '责任人'] == '已有责任人'

    def test_apply_memory_empty_df(self, tmp_path, monkeypatch, reset_singleton):
        """测试：空DataFrame不报错"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from core.main import apply_assignment_memory

        empty_df = pd.DataFrame()
        result = apply_assignment_memory(empty_df, file_type=1)
        assert result is not None

    def test_apply_memory_missing_columns(self, tmp_path, monkeypatch, reset_singleton):
        """测试：缺少必要列时不报错"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from core.main import apply_assignment_memory

        # 缺少'责任人'列
        df = pd.DataFrame({'项目号': ['1907']})
        result = apply_assignment_memory(df, file_type=1)
        assert result is not None

    def test_apply_memory_with_role_suffix_in_interface(self, tmp_path, monkeypatch, reset_singleton):
        """测试：接口号带角色后缀时能正确匹配"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import save_memory
        from core.main import apply_assignment_memory

        # 保存时不带后缀
        save_memory(1, '1907', 'HQ-TA-001', '张三')

        # DataFrame中的接口号带后缀
        df = pd.DataFrame({
            '项目号': ['1907'],
            '接口号': ['HQ-TA-001(设计人员)'],
            '责任人': [''],
        })

        result_df = apply_assignment_memory(df.copy(), file_type=1)
        assert result_df.loc[0, '责任人'] == '张三'


class TestForceAssignDialog:
    """测试强制指派弹窗"""

    def test_file_type_names_mapping(self):
        """测试文件类型名称映射"""
        from services.distribution import ForceAssignDialog

        assert ForceAssignDialog.FILE_TYPE_NAMES[1] == "内部需打开"
        assert ForceAssignDialog.FILE_TYPE_NAMES[2] == "内部需回复"
        assert ForceAssignDialog.FILE_TYPE_NAMES[3] == "外部需打开"
        assert ForceAssignDialog.FILE_TYPE_NAMES[4] == "外部需回复"
        assert ForceAssignDialog.FILE_TYPE_NAMES[5] == "三维提资"
        assert ForceAssignDialog.FILE_TYPE_NAMES[6] == "收发文函"

    def test_find_source_file_method(self, tmp_path):
        """测试源文件查找方法"""
        from services.distribution import ForceAssignDialog

        # 创建测试目录结构
        (tmp_path / "待处理文件1").mkdir()
        (tmp_path / "待处理文件1" / "test_file.xlsx").touch()
        (tmp_path / "待处理文件2").mkdir()
        (tmp_path / "待处理文件2" / "test_file2.xlsx").touch()

        # 创建一个mock dialog来测试_find_source_file方法
        with patch.object(ForceAssignDialog, '__init__', return_value=None):
            dialog = ForceAssignDialog.__new__(ForceAssignDialog)

            # 测试文件1
            result = dialog._find_source_file(str(tmp_path), "test_file.xlsx", 1)
            assert result is not None
            assert "test_file.xlsx" in result

            # 测试文件2
            result2 = dialog._find_source_file(str(tmp_path), "test_file2.xlsx", 2)
            assert result2 is not None
            assert "test_file2.xlsx" in result2

            # 测试不存在的文件
            result3 = dialog._find_source_file(str(tmp_path), "not_exist.xlsx", 1)
            assert result3 is None

            # 测试无效的数据文件夹
            result4 = dialog._find_source_file("", "test_file.xlsx", 1)
            assert result4 is None

    def test_resolve_data_folder_prefers_registry_hook(self, tmp_path):
        """测试：_resolve_data_folder 优先使用 hooks 已设置的路径"""
        from services.distribution import ForceAssignDialog
        from registry import hooks as registry_hooks

        original = registry_hooks._DATA_FOLDER
        try:
            preferred = "E:/preferred/data"
            registry_hooks._DATA_FOLDER = preferred

            with patch.object(ForceAssignDialog, "__init__", return_value=None):
                dialog = ForceAssignDialog.__new__(ForceAssignDialog)
                db_path = tmp_path / "data" / ".registry" / "registry.db"
                result = dialog._resolve_data_folder(str(db_path))
                assert result == preferred
        finally:
            registry_hooks._DATA_FOLDER = original

    def test_resolve_data_folder_fallbacks_to_db_path(self, tmp_path):
        """测试：_resolve_data_folder 在 hooks 未设置时从 db_path 反推"""
        from services.distribution import ForceAssignDialog
        from registry import hooks as registry_hooks

        original = registry_hooks._DATA_FOLDER
        try:
            registry_hooks._DATA_FOLDER = None
            db_path = tmp_path / "data" / ".registry" / "registry.db"
            expected = tmp_path / "data"

            with patch.object(ForceAssignDialog, "__init__", return_value=None):
                dialog = ForceAssignDialog.__new__(ForceAssignDialog)
                result = dialog._resolve_data_folder(str(db_path))
                assert str(expected) == result
        finally:
            registry_hooks._DATA_FOLDER = original


class TestFindTasksForForceAssign:
    """测试数据库查询函数"""

    def test_find_tasks_returns_matching_tasks(self, tmp_path):
        """测试查找返回匹配的任务"""
        db_path = str(tmp_path / "test1.db")
        from registry.db import init_db, get_connection, close_connection_after_use
        from registry.service import find_tasks_for_force_assign

        conn = get_connection(db_path, wal=False)
        try:
            init_db(conn)
            conn.execute("""
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file, row_index,
                    business_id, status, first_seen_at, last_seen_at
                ) VALUES
                ('task1', 1, '1907', 'HQ-TA-001', 'file1.xlsx', 10, '1|1907|HQ-TA-001', 'open', '2025-01-01', '2025-01-01'),
                ('task2', 1, '1907', 'HQ-TA-001', 'file2.xlsx', 20, '1|1907|HQ-TA-001', 'open', '2025-01-01', '2025-01-01')
            """)
            conn.commit()
        finally:
            close_connection_after_use()

        tasks = find_tasks_for_force_assign(
            db_path=db_path,
            wal=False,
            file_type=1,
            project_id='1907',
            interface_id='HQ-TA-001'
        )

        # 应该找到2个任务（在不同源文件中）
        assert len(tasks) == 2
        assert tasks[0]['source_file'] in ['file1.xlsx', 'file2.xlsx']

    def test_find_tasks_excludes_archived(self, tmp_path):
        """测试排除已归档的任务"""
        db_path = str(tmp_path / "test2.db")
        from registry.db import init_db, get_connection, close_connection_after_use
        from registry.service import find_tasks_for_force_assign

        conn = get_connection(db_path, wal=False)
        try:
            init_db(conn)
            conn.execute("""
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file, row_index,
                    business_id, status, first_seen_at, last_seen_at
                ) VALUES
                ('task_archived', 1, '1907', 'HQ-TA-003', 'file1.xlsx', 40, '1|1907|HQ-TA-003', 'archived', '2025-01-01', '2025-01-01')
            """)
            conn.commit()
        finally:
            close_connection_after_use()

        tasks = find_tasks_for_force_assign(
            db_path=db_path,
            wal=False,
            file_type=1,
            project_id='1907',
            interface_id='HQ-TA-003'
        )

        # 归档的任务不应该被返回
        assert len(tasks) == 0

    def test_find_tasks_returns_empty_for_nonexistent(self, tmp_path):
        """测试查找不存在的任务返回空列表"""
        db_path = str(tmp_path / "test3.db")
        from registry.db import init_db, get_connection, close_connection_after_use
        from registry.service import find_tasks_for_force_assign

        conn = get_connection(db_path, wal=False)
        try:
            init_db(conn)
            conn.commit()
        finally:
            close_connection_after_use()

        tasks = find_tasks_for_force_assign(
            db_path=db_path,
            wal=False,
            file_type=1,
            project_id='9999',
            interface_id='NOT-EXIST'
        )

        assert len(tasks) == 0


class TestSaveAssignmentsBatchMemory:
    """测试 save_assignments_batch 中的指派记忆保存"""

    def test_memory_saved_after_successful_assignment(self, tmp_path, monkeypatch, reset_singleton):
        """测试成功指派后保存记忆"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        # 创建临时Excel文件
        file_path = tmp_path / "test.xlsx"
        df = pd.DataFrame({
            'A': ['接口1', '接口2'],
            'B': ['数据1', '数据2'],
        })
        df.to_excel(file_path, index=False, engine='openpyxl')

        from services.distribution import save_assignments_batch
        from services.assignment_memory import get_memory

        # Mock Registry hooks to avoid database operations
        with patch('registry.hooks.on_assigned'):
            assignments = [
                {
                    'file_type': 1,
                    'file_path': str(file_path),
                    'row_index': 2,
                    'assigned_name': '张三',
                    'interface_id': 'HQ-TA-001',
                    'project_id': '1907',
                }
            ]

            result = save_assignments_batch(assignments)

            # 验证成功
            assert result['success_count'] == 1

            # 验证记忆被保存
            memory = get_memory(1, '1907', 'HQ-TA-001')
            assert memory == '张三'

    def test_memory_not_saved_for_failed_assignment(self, tmp_path, monkeypatch, reset_singleton):
        """测试失败指派不保存记忆"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.distribution import save_assignments_batch
        from services.assignment_memory import get_memory

        assignments = [
            {
                'file_type': 1,
                'file_path': '/nonexistent/path/file.xlsx',  # 不存在的文件
                'row_index': 2,
                'assigned_name': '张三',
                'interface_id': 'HQ-TA-001',
                'project_id': '1907',
            }
        ]

        result = save_assignments_batch(assignments)

        # 验证失败
        assert result['success_count'] == 0
        assert len(result['failed_tasks']) == 1

        # 验证记忆没有被保存
        memory = get_memory(1, '1907', 'HQ-TA-001')
        assert memory is None


class TestIntegrationFlow:
    """集成测试：完整业务流程"""

    def test_full_memory_flow(self, tmp_path, monkeypatch, reset_singleton):
        """测试完整的指派记忆流程"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import save_memory
        from core.main import apply_assignment_memory

        # 步骤1：模拟用户指派（保存记忆）
        save_memory(file_type=2, project_id='1818', interface_id='HQ-TA-5000', assigned_name='王丹丹')

        # 步骤2：模拟下次处理Excel（应用记忆）
        df = pd.DataFrame({
            '项目号': ['1818', '1907'],
            '接口号': ['HQ-TA-5000', 'HQ-TA-6000'],
            '责任人': ['', ''],  # 都是空的
            'source_file': ['file.xlsx', 'file.xlsx'],
        })

        result_df = apply_assignment_memory(df.copy(), file_type=2)

        # 验证：只有第一行被填充（因为有记忆）
        assert result_df.loc[0, '责任人'] == '王丹丹'
        assert result_df.loc[1, '责任人'] == ''  # 没有记忆

    def test_memory_overwrite(self, tmp_path, monkeypatch, reset_singleton):
        """测试指派记忆覆盖"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        from services.assignment_memory import save_memory, get_memory

        # 第一次指派
        save_memory(1, '1907', 'HQ-TA-001', '张三')
        assert get_memory(1, '1907', 'HQ-TA-001') == '张三'

        # 重新指派（覆盖）
        save_memory(1, '1907', 'HQ-TA-001', '李四')
        assert get_memory(1, '1907', 'HQ-TA-001') == '李四'

    def test_memory_persists_across_sessions(self, tmp_path, monkeypatch, reset_singleton):
        """测试指派记忆跨会话持久化"""
        monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))

        import services.assignment_memory as am

        # 模拟第一次会话
        from services.assignment_memory import save_memory
        save_memory(1, '1907', 'HQ-TA-001', '张三')

        # 模拟重启（重置单例）
        am._memory_instance = None

        # 模拟第二次会话
        from services.assignment_memory import get_memory
        result = get_memory(1, '1907', 'HQ-TA-001')

        assert result == '张三'
