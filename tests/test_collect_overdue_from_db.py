#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试从数据库收集延期任务功能

验证：
1. _collect_overdue_tasks能够从数据库正确读取延期任务
2. 不依赖UI的viewer状态
3. 正确过滤已归档和已忽略的任务
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


def test_collect_overdue_from_database():
    """测试从数据库读取延期任务"""
    # 创建临时数据库
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        # 1. 初始化数据库并插入测试数据
        from registry.db import get_connection, init_db
        conn = get_connection(db_path, wal=False)
        
        # 构建测试日期
        overdue_date1 = (datetime.now() - timedelta(days=10)).strftime("%Y.%m.%d")
        overdue_date2 = (datetime.now() - timedelta(days=5)).strftime("%Y.%m.%d")
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y.%m.%d")
        today_date = datetime.now().strftime("%Y.%m.%d")
        
        # 插入测试任务
        test_tasks = [
            # (id, file_type, project_id, interface_id, source_file, row_index, interface_time, status, ignored)
            ('task1', 1, '1818', 'INT-001', 'test1.xlsx', 2, overdue_date1, 'open', 0),        # 延期10天
            ('task2', 1, '1818', 'INT-002', 'test1.xlsx', 3, overdue_date2, 'completed', 0),   # 延期5天
            ('task3', 2, '2016', 'REPLY-001', 'test2.xlsx', 2, overdue_date1, 'open', 0),      # 延期10天
            ('task4', 1, '1818', 'INT-003', 'test1.xlsx', 4, future_date, 'open', 0),          # 未来，不延期
            ('task5', 1, '1818', 'INT-004', 'test1.xlsx', 5, today_date, 'open', 0),           # 今天，不延期
            ('task6', 1, '1818', 'INT-005', 'test1.xlsx', 6, overdue_date1, 'open', 1),        # 延期但已忽略
            ('task7', 1, '1818', 'INT-006', 'test1.xlsx', 7, overdue_date2, 'archived', 0),    # 延期但已归档
        ]
        
        for task_data in test_tasks:
            conn.execute("""
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file, 
                    row_index, interface_time, status, ignored,
                    first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, task_data)
        
        conn.commit()
        conn.close()
        
        print(f"\n✓ 插入 {len(test_tasks)} 个测试任务")
        print(f"  - 3个延期任务（INT-001, INT-002, REPLY-001）")
        print(f"  - 2个未延期任务（INT-003未来, INT-004今天）")
        print(f"  - 1个已忽略（INT-005）")
        print(f"  - 1个已归档（INT-006）")
        
        # 2. Mock ExcelProcessorApp并配置registry
        from base import ExcelProcessorApp
        
        # 创建临时目录作为数据文件夹
        tmp_dir = tempfile.mkdtemp()
        
        # 移动数据库到临时目录（模拟registry的数据文件夹）
        import shutil
        registry_db_path = os.path.join(tmp_dir, '.registry', 'registry.db')
        os.makedirs(os.path.dirname(registry_db_path), exist_ok=True)
        shutil.copy(db_path, registry_db_path)
        
        # 设置registry配置
        import registry.hooks as registry_hooks
        registry_hooks.set_data_folder(tmp_dir)
        
        # 创建mock app
        app = Mock(spec=ExcelProcessorApp)
        
        # 绑定真实的方法
        app._collect_overdue_tasks = ExcelProcessorApp._collect_overdue_tasks.__get__(app, type(app))
        
        # 3. 执行收集
        overdue_tasks = app._collect_overdue_tasks()
        
        print(f"\n收集结果:")
        for task in overdue_tasks:
            print(f"  - {task['interface_id']} ({task['project_id']}) - {task['interface_time']}")
        
        # 4. 验证结果
        assert len(overdue_tasks) == 3, f"应该收集到3个延期任务，实际收集到{len(overdue_tasks)}个"
        
        # 验证具体任务
        interface_ids = [task['interface_id'] for task in overdue_tasks]
        assert 'INT-001' in interface_ids, "应包含INT-001（延期10天）"
        assert 'INT-002' in interface_ids, "应包含INT-002（延期5天）"
        assert 'REPLY-001' in interface_ids, "应包含REPLY-001（延期10天）"
        
        # 验证不应包含的任务
        assert 'INT-003' not in interface_ids, "不应包含未来日期的任务"
        assert 'INT-004' not in interface_ids, "不应包含今天的任务"
        assert 'INT-005' not in interface_ids, "不应包含已忽略的任务"
        assert 'INT-006' not in interface_ids, "不应包含已归档的任务"
        
        # 验证file_type
        for task in overdue_tasks:
            if task['interface_id'] == 'INT-001':
                assert task['file_type'] == 1
                assert task['tab_name'] == '内部需打开接口'
            elif task['interface_id'] == 'REPLY-001':
                assert task['file_type'] == 2
                assert task['tab_name'] == '内部需回复接口'
        
        print("\n✓ 测试通过：从数据库收集延期任务功能正常")
        
        # 清理临时目录
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_collect_overdue_empty_database():
    """测试空数据库的情况"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        # 创建空数据库
        from registry.db import get_connection
        conn = get_connection(db_path, wal=False)
        conn.close()
        
        # 创建临时目录
        import shutil
        tmp_dir = tempfile.mkdtemp()
        registry_db_path = os.path.join(tmp_dir, '.registry', 'registry.db')
        os.makedirs(os.path.dirname(registry_db_path), exist_ok=True)
        shutil.copy(db_path, registry_db_path)
        
        # 设置registry
        import registry.hooks as registry_hooks
        registry_hooks.set_data_folder(tmp_dir)
        
        # Mock app
        from base import ExcelProcessorApp
        app = Mock(spec=ExcelProcessorApp)
        app._collect_overdue_tasks = ExcelProcessorApp._collect_overdue_tasks.__get__(app, type(app))
        
        # 执行收集
        overdue_tasks = app._collect_overdue_tasks()
        
        print(f"\n✓ 空数据库：收集到 {len(overdue_tasks)} 个任务")
        assert len(overdue_tasks) == 0, "空数据库应该返回0个任务"
        
        # 清理
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_collect_overdue_all_ignored():
    """测试所有延期任务都被忽略的情况"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection
        conn = get_connection(db_path, wal=False)
        
        overdue_date = (datetime.now() - timedelta(days=5)).strftime("%Y.%m.%d")
        
        # 插入3个延期任务，全部标记为已忽略
        for i in range(3):
            conn.execute("""
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file,
                    row_index, interface_time, status, ignored,
                    first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (f'task{i}', 1, '1818', f'INT-{i:03d}', 'test.xlsx', i+2, overdue_date, 'open', 1))
        
        conn.commit()
        conn.close()
        
        # 创建临时目录
        import shutil
        tmp_dir = tempfile.mkdtemp()
        registry_db_path = os.path.join(tmp_dir, '.registry', 'registry.db')
        os.makedirs(os.path.dirname(registry_db_path), exist_ok=True)
        shutil.copy(db_path, registry_db_path)
        
        # 设置registry
        import registry.hooks as registry_hooks
        registry_hooks.set_data_folder(tmp_dir)
        
        # Mock app
        from base import ExcelProcessorApp
        app = Mock(spec=ExcelProcessorApp)
        app._collect_overdue_tasks = ExcelProcessorApp._collect_overdue_tasks.__get__(app, type(app))
        
        # 执行收集
        overdue_tasks = app._collect_overdue_tasks()
        
        print(f"\n✓ 所有任务已忽略：收集到 {len(overdue_tasks)} 个任务")
        assert len(overdue_tasks) == 0, "所有延期任务都被忽略时应该返回0个"
        
        # 清理
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_collect_overdue_mixed_status():
    """测试混合状态的任务"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection
        conn = get_connection(db_path, wal=False)
        
        overdue_date = (datetime.now() - timedelta(days=3)).strftime("%Y.%m.%d")
        
        # 插入不同状态的延期任务
        test_tasks = [
            ('task1', 1, '1818', 'OPEN-001', 'test.xlsx', 2, overdue_date, 'open', 0),        # 待完成
            ('task2', 1, '1818', 'COMP-001', 'test.xlsx', 3, overdue_date, 'completed', 0),   # 待审查
            ('task3', 1, '1818', 'CONF-001', 'test.xlsx', 4, overdue_date, 'confirmed', 0),   # 已审查
            ('task4', 1, '1818', 'ARCH-001', 'test.xlsx', 5, overdue_date, 'archived', 0),    # 已归档
        ]
        
        for task_data in test_tasks:
            conn.execute("""
                INSERT INTO tasks (
                    id, file_type, project_id, interface_id, source_file,
                    row_index, interface_time, status, ignored,
                    first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, task_data)
        
        conn.commit()
        conn.close()
        
        # 创建临时目录
        import shutil
        tmp_dir = tempfile.mkdtemp()
        registry_db_path = os.path.join(tmp_dir, '.registry', 'registry.db')
        os.makedirs(os.path.dirname(registry_db_path), exist_ok=True)
        shutil.copy(db_path, registry_db_path)
        
        # 设置registry
        import registry.hooks as registry_hooks
        registry_hooks.set_data_folder(tmp_dir)
        
        # Mock app
        from base import ExcelProcessorApp
        app = Mock(spec=ExcelProcessorApp)
        app._collect_overdue_tasks = ExcelProcessorApp._collect_overdue_tasks.__get__(app, type(app))
        
        # 执行收集
        overdue_tasks = app._collect_overdue_tasks()
        
        print(f"\n混合状态任务收集结果:")
        for task in overdue_tasks:
            print(f"  - {task['interface_id']} (status={task['status']})")
        
        # 验证：应该收集除了archived之外的所有任务
        assert len(overdue_tasks) == 3, f"应该收集到3个任务（不包括已归档），实际{len(overdue_tasks)}个"
        
        interface_ids = [task['interface_id'] for task in overdue_tasks]
        assert 'OPEN-001' in interface_ids, "应包含open状态"
        assert 'COMP-001' in interface_ids, "应包含completed状态"
        assert 'CONF-001' in interface_ids, "应包含confirmed状态"
        assert 'ARCH-001' not in interface_ids, "不应包含archived状态"
        
        print("✓ 测试通过：混合状态任务过滤正确")
        
        # 清理
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

