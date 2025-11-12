#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry忽略延期任务功能测试
"""

import pytest
import os
import sqlite3
import tempfile
from datetime import datetime
import pandas as pd

from registry import service as registry_service
from registry.util import make_task_id, make_business_id
from registry import hooks as registry_hooks
from registry.db import get_connection, init_db


@pytest.fixture
def temp_db_path():
    """创建临时数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # 初始化数据库
    conn = get_connection(path, wal=False)
    init_db(conn)
    
    yield path
    
    # 清理
    try:
        conn.close()
    except:
        pass
    
    # 尝试删除文件，带重试
    import time
    for _ in range(3):
        try:
            os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)


def test_mark_ignored_single_task(temp_db_path):
    """测试：标记单个任务为忽略"""
    # 1. 创建任务
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    result_df = pd.DataFrame({
        '原始行号': [2],
        '接口号': ['TEST-001'],
        '项目号': ['1818'],
        '接口时间': ['2024.01.15']  # 延期时间
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 12, 10, 0, 0)
    )
    
    # 2. 标记为忽略
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'TEST-001',
        'source_file': 'test.xlsx',
        'row_index': 2,
        'interface_time': '2024.01.15'  # 延期时间
    }]
    
    result = registry_service.mark_ignored_batch(
        db_path=temp_db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='测试忽略'
    )
    
    # 3. 验证
    assert result['success_count'] == 1
    assert len(result['failed_tasks']) == 0
    
    # 4. 查询数据库确认
    conn = sqlite3.connect(temp_db_path)
    tid = make_task_id(1, '1818', 'TEST-001', 'test.xlsx', 2)
    cursor = conn.execute(
        "SELECT ignored, ignored_by, ignored_reason, interface_time_when_ignored FROM tasks WHERE id = ?",
        (tid,)
    )
    row = cursor.fetchone()
    
    assert row is not None
    assert row[0] == 1  # ignored
    assert row[1] == '测试所领导'  # ignored_by
    assert row[2] == '测试忽略'  # ignored_reason
    assert row[3] == '2024.01.15'  # interface_time_when_ignored
    
    conn.close()
    print("[PASS] test_mark_ignored_single_task")


def test_auto_unignore_on_time_change(temp_db_path):
    """测试：预期时间变化时自动取消忽略"""
    # 1. 创建并忽略任务
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    result_df = pd.DataFrame({
        '原始行号': [2],
        '接口号': ['TEST-002'],
        '项目号': ['1818'],
        '接口时间': ['2024.01.15']
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 12, 10, 0, 0)
    )
    
    # 标记为忽略
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'TEST-002',
        'source_file': 'test.xlsx',
        'row_index': 2,
        'interface_time': '2024.01.15'
    }]
    
    registry_service.mark_ignored_batch(
        db_path=temp_db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='测试忽略'
    )
    
    # 2. 模拟预期时间变化（扫描时更新）
    result_df2 = pd.DataFrame({
        '原始行号': [2],
        '接口号': ['TEST-002'],
        '项目号': ['1818'],
        '接口时间': ['2026.01.15']  # 时间变化！
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df2,
        now=datetime(2025, 11, 12, 11, 0, 0)
    )
    
    # 3. 验证忽略已取消
    conn = sqlite3.connect(temp_db_path)
    tid = make_task_id(1, '1818', 'TEST-002', 'test.xlsx', 2)
    cursor = conn.execute(
        "SELECT ignored FROM tasks WHERE id = ?",
        (tid,)
    )
    row = cursor.fetchone()
    
    assert row is not None
    assert row[0] == 0  # ignored应该变为0
    
    conn.close()
    print("[PASS] test_auto_unignore_on_time_change")


def test_ignored_task_not_displayed(temp_db_path):
    """测试：被忽略的任务不在显示状态中返回"""
    # 1. 创建并忽略任务
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    result_df = pd.DataFrame({
        '原始行号': [2],
        '接口号': ['TEST-003'],
        '项目号': ['1818'],
        '接口时间': ['2024.01.15']
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 12, 10, 0, 0)
    )
    
    # 标记为忽略
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'TEST-003',
        'source_file': 'test.xlsx',
        'row_index': 2,
        'interface_time': '2024.01.15'
    }]
    
    registry_service.mark_ignored_batch(
        db_path=temp_db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='测试忽略'
    )
    
    # 2. 查询显示状态
    query_task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'TEST-003',
        'source_file': 'test.xlsx',
        'row_index': 2,
        'interface_time': '2024.01.15'
    }]
    
    status_map = registry_hooks.get_display_status(query_task_keys, "设计人员")
    
    # 3. 验证
    tid = make_task_id(1, '1818', 'TEST-003', 'test.xlsx', 2)
    assert status_map[tid] == ''  # 应返回空字符串
    
    print("[PASS] test_ignored_task_not_displayed")


def test_batch_ignore_multiple_tasks(temp_db_path):
    """测试：批量忽略多个任务"""
    # 创建10个延期任务
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    rows = []
    for i in range(10):
        rows.append({
            '原始行号': [i + 2],
            '接口号': [f'TEST-{i:03d}'],
            '项目号': ['1818'],
            '接口时间': ['2024.01.15']
        })
    
    result_df = pd.DataFrame({
        '原始行号': [i + 2 for i in range(10)],
        '接口号': [f'TEST-{i:03d}' for i in range(10)],
        '项目号': ['1818'] * 10,
        '接口时间': ['2024.01.15'] * 10
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 12, 10, 0, 0)
    )
    
    # 批量忽略
    task_keys = []
    for i in range(10):
        task_keys.append({
            'file_type': 1,
            'project_id': '1818',
            'interface_id': f'TEST-{i:03d}',
            'source_file': 'test.xlsx',
            'row_index': i + 2,
            'interface_time': '2024.01.15'
        })
    
    result = registry_service.mark_ignored_batch(
        db_path=temp_db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='批量测试'
    )
    
    # 验证
    assert result['success_count'] == 10
    assert len(result['failed_tasks']) == 0
    
    print("[PASS] test_batch_ignore_multiple_tasks")


def test_cannot_ignore_already_ignored_task(temp_db_path):
    """测试：不能重复忽略已忽略的任务"""
    # 1. 创建并忽略任务
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    result_df = pd.DataFrame({
        '原始行号': [2],
        '接口号': ['TEST-004'],
        '项目号': ['1818'],
        '接口时间': ['2024.01.15']
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 12, 10, 0, 0)
    )
    
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'TEST-004',
        'source_file': 'test.xlsx',
        'row_index': 2,
        'interface_time': '2024.01.15'
    }]
    
    # 第一次忽略
    result1 = registry_service.mark_ignored_batch(
        db_path=temp_db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='测试忽略'
    )
    
    assert result1['success_count'] == 1
    assert len(result1['failed_tasks']) == 0
    
    # 2. 尝试再次忽略（应该失败）
    result2 = registry_service.mark_ignored_batch(
        db_path=temp_db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='测试忽略'
    )
    
    assert result2['success_count'] == 0
    assert len(result2['failed_tasks']) == 1
    assert result2['failed_tasks'][0]['reason'] == '已经被忽略'
    
    print("[PASS] test_cannot_ignore_already_ignored_task")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

