#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry状态提醒系统测试

测试状态显示、导出过滤、角色解耦等功能
"""
import pytest
import os
import sqlite3
import tempfile
import shutil
from datetime import datetime
from registry.db import init_db, get_connection
from registry.service import upsert_task, mark_completed, mark_confirmed, get_display_status
from registry.models import Status
from registry.util import make_task_id


@pytest.fixture
def temp_db_path():
    """创建临时数据库"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_status.db")
    
    # 初始化数据库（直接使用sqlite3，避免get_connection的单例问题）
    import sqlite3
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.commit()
    conn.close()
    
    yield db_path
    
    # 清理：关闭所有连接
    try:
        from registry.db import close_connection
        close_connection()
    except:
        pass
    
    try:
        import time
        time.sleep(0.1)  # 给Windows时间释放文件句柄
        shutil.rmtree(temp_dir)
    except:
        pass


def test_status_display_for_pending_tasks(temp_db_path):
    """测试待完成任务的状态显示"""
    db_path = temp_db_path
    wal = False
    now = datetime.now()
    
    # 创建一个已指派的任务
    key = {
        'file_type': 1,
        'project_id': 'TEST001',
        'interface_id': 'IF-001',
        'source_file': 'test.xlsx',
        'row_index': 2
    }
    
    fields = {
        'department': '测试部门',
        'interface_time': '2025.01.01',
        'role': '设计人员',
        'assigned_by': '张经理（室主任）',
        'assigned_at': now.isoformat(),
        'display_status': '待完成',
        'responsible_person': '李工'
    }
    
    upsert_task(db_path, wal, key, fields, now)
    
    # 查询状态
    status_map = get_display_status(db_path, wal, [key])
    
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    assert tid in status_map
    assert '待完成' in status_map[tid]
    assert status_map[tid].startswith('📌')  # Emoji前缀
    print("[OK] Pending task status displayed correctly")


def test_status_display_for_completed_tasks(temp_db_path):
    """测试已完成待确认任务的状态显示"""
    db_path = temp_db_path
    wal = False
    now = datetime.now()
    
    # 创建任务并标记为completed
    key = {
        'file_type': 1,
        'project_id': 'TEST002',
        'interface_id': 'IF-002',
        'source_file': 'test.xlsx',
        'row_index': 3
    }
    
    # 先创建任务（模拟指派）
    fields = {
        'department': '测试部门',
        'role': '设计人员',
        'assigned_by': '王工（1818接口工程师）',
        'display_status': '待完成'
    }
    upsert_task(db_path, wal, key, fields, now)
    
    # 标记为completed（设计人员填写回文单号）
    from registry.service import mark_completed
    mark_completed(db_path, wal, key, now)
    
    # 更新display_status为"待指派人确认"
    fields_update = {'display_status': '待指派人确认'}
    upsert_task(db_path, wal, key, fields_update, now)
    
    # 查询状态
    status_map = get_display_status(db_path, wal, [key])
    
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    assert tid in status_map
    assert '待指派人确认' in status_map[tid] or '待确认' in status_map[tid]
    assert status_map[tid].startswith('⏳')  # Emoji前缀
    print("[OK] Completed task status displayed correctly")


def test_status_cleared_after_confirmation(temp_db_path):
    """测试确认后状态被清除"""
    db_path = temp_db_path
    wal = False
    now = datetime.now()
    
    # 创建任务并标记为completed
    key = {
        'file_type': 1,
        'project_id': 'TEST003',
        'interface_id': 'IF-003',
        'source_file': 'test.xlsx',
        'row_index': 4
    }
    
    fields = {
        'role': '设计人员',
        'display_status': '待上级确认'
    }
    upsert_task(db_path, wal, key, fields, now)
    mark_completed(db_path, wal, key, now)
    
    # 上级确认
    mark_confirmed(db_path, wal, key, now, confirmed_by='张主任')
    
    # 查询状态，应该不再显示
    status_map = get_display_status(db_path, wal, [key])
    
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    assert tid not in status_map  # 确认后不应再显示状态
    print("[OK] 确认后状态已清除")


def test_role_decoupling(temp_db_path):
    """测试角色解耦 - 同一接口不同角色独立存储"""
    db_path = temp_db_path
    wal = False
    now = datetime.now()
    
    # 同一接口，不同角色
    base_key = {
        'file_type': 1,
        'project_id': 'TEST004',
        'interface_id': 'IF-004',
        'source_file': 'test.xlsx',
    }
    
    # 角色1：设计人员（行2）
    key1 = {**base_key, 'row_index': 2}
    fields1 = {'role': '设计人员', 'display_status': '待完成'}
    upsert_task(db_path, wal, key1, fields1, now)
    
    # 角色2：1818接口工程师（行3，虽然接口号相同，但是不同行）
    key2 = {**base_key, 'row_index': 3}
    fields2 = {'role': '1818接口工程师', 'display_status': '待确认（可自行确认）'}
    upsert_task(db_path, wal, key2, fields2, now)
    
    # 查询状态
    status_map = get_display_status(db_path, wal, [key1, key2])
    
    tid1 = make_task_id(key1['file_type'], key1['project_id'], key1['interface_id'], 
                        key1['source_file'], key1['row_index'])
    tid2 = make_task_id(key2['file_type'], key2['project_id'], key2['interface_id'], 
                        key2['source_file'], key2['row_index'])
    
    # 两个任务应该有不同的ID和状态
    assert tid1 != tid2
    assert tid1 in status_map
    assert tid2 in status_map
    assert '待完成' in status_map[tid1]
    assert '待确认' in status_map[tid2]
    print("[OK] 角色解耦测试通过")


def test_batch_query_performance(temp_db_path):
    """测试批量查询性能"""
    db_path = temp_db_path
    wal = False
    now = datetime.now()
    
    # 创建100个任务
    keys = []
    for i in range(100):
        key = {
            'file_type': 1,
            'project_id': f'TEST{i:03d}',
            'interface_id': f'IF-{i:03d}',
            'source_file': 'test.xlsx',
            'row_index': i + 2
        }
        fields = {'display_status': '待完成' if i % 2 == 0 else None}
        upsert_task(db_path, wal, key, fields, now)
        keys.append(key)
    
    # 批量查询
    import time
    start = time.time()
    status_map = get_display_status(db_path, wal, keys)
    elapsed = time.time() - start
    
    # 验证结果
    assert len(status_map) == 50  # 只有一半有status
    print(f"[OK] 批量查询100个任务耗时: {elapsed:.3f}秒")
    assert elapsed < 1.0  # 应该在1秒内完成


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

