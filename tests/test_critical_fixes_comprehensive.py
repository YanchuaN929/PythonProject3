"""
综合测试：验证严重问题修复和新的忽略快照机制
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import registry.hooks as registry_hooks
from registry.service import (
    upsert_task, batch_upsert_tasks, mark_ignored_batch,
    query_task_history, get_display_status
)
from registry.db import init_db, get_connection
from registry.migrate import migrate_if_needed


@pytest.fixture
def temp_db(tmp_path):
    """创建临时数据库用于测试"""
    db_path = tmp_path / "registry.db"
    
    # 配置registry使用临时数据库
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': str(db_path),
        'wal': False
    }):
        # 初始化数据库
        conn = get_connection(str(db_path), False)
        conn.close()
        
        yield str(db_path)
    
    # 清理
    try:
        if db_path.exists():
            os.unlink(db_path)
    except:
        pass


def test_row_index_change_preserves_status(temp_db):
    """测试1：行号变化不应导致已审查任务变成待完成"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建任务并完成、确认
        tasks_data = [{
            'key': {
                'file_type': 2,
                'project_id': '2016',
                'interface_id': 'S-TEST-001',
                'source_file': 'test_file.xlsx',
                'row_index': 100
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025-11-10',
                'role': '设计人员',
                'display_status': '待完成',
                'responsible_person': '张三'
            }
        }]
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 2. 标记为completed和confirmed
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            UPDATE tasks
            SET status = 'confirmed',
                completed_at = ?,
                completed_by = '张三',
                confirmed_at = ?,
                confirmed_by = '李四',
                display_status = '已审查'
            WHERE interface_id = 'S-TEST-001'
              AND project_id = '2016'
        """, (now.isoformat(), now.isoformat()))
        conn.commit()
        conn.close()
        
        # 3. 模拟Excel文件编辑导致行号变化（从100变成120）
        tasks_data[0]['key']['row_index'] = 120
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 4. 验证状态应该被保留
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT status, completed_at, confirmed_at, display_status
            FROM tasks
            WHERE interface_id = 'S-TEST-001'
              AND project_id = '2016'
              AND status != 'archived'
            ORDER BY last_seen_at DESC
            LIMIT 1
        """)
        task = cursor.fetchone()
        conn.close()
        
        assert task is not None, "任务应该存在"
        assert task['status'] == 'confirmed', "状态应该仍然是confirmed"
        assert task['completed_at'] is not None, "completed_at应该被保留"
        assert task['confirmed_at'] is not None, "confirmed_at应该被保留"


def test_new_completed_task_visible_to_superior(temp_db):
    """测试2：设计人完成的新任务应该能被上级看到"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建新任务
        tasks_data = [{
            'key': {
                'file_type': 2,
                'project_id': '2016',
                'interface_id': 'S-TEST-002',
                'source_file': 'test_file.xlsx',
                'row_index': 200
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025-11-10',
                'role': '设计人员',
                'display_status': '待完成',
                'responsible_person': '张三'
            }
        }]
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 2. 设计人完成任务
        tasks_data[0]['fields']['_completed_col_value'] = 'ABC-123'
        tasks_data[0]['fields']['display_status'] = '待审查'
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 3. 验证状态
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT status, completed_at, completed_by, display_status
            FROM tasks
            WHERE interface_id = 'S-TEST-002'
              AND project_id = '2016'
              AND status != 'archived'
            ORDER BY last_seen_at DESC
            LIMIT 1
        """)
        task = cursor.fetchone()
        conn.close()
        
        assert task is not None, "任务应该存在"
        assert task['status'] == 'completed', "状态应该是completed"
        assert task['completed_at'] is not None, "completed_at应该有值"
        assert '待审查' in task['display_status'], "显示状态应该是待审查"


def test_ignore_snapshot_creation(temp_db):
    """测试3：忽略操作应该创建快照记录"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建任务
        tasks_data = [{
            'key': {
                'file_type': 2,
                'project_id': '2016',
                'interface_id': 'S-TEST-003',
                'source_file': 'test_file.xlsx',
                'row_index': 300
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025-11-10',
                'role': '设计人员',
                'display_status': '待完成',
                'responsible_person': '张三'
            }
        }]
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 2. 忽略任务
        task_keys = [{
            'file_type': 2,
            'project_id': '2016',
            'interface_id': 'S-TEST-003',
            'source_file': 'test_file.xlsx',
            'row_index': 300
        }]
        result = mark_ignored_batch(temp_db, False, task_keys, '所领导', '测试忽略', now)
        
        assert result['success_count'] == 1, "应该成功忽略1个任务"
        
        # 3. 验证快照记录
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT snapshot_interface_time, ignored_by, ignored_reason
            FROM ignored_snapshots
            WHERE interface_id = 'S-TEST-003'
              AND project_id = '2016'
        """)
        snapshot = cursor.fetchone()
        conn.close()
        
        assert snapshot is not None, "应该创建快照记录"
        assert snapshot['snapshot_interface_time'] == '2025-11-10', "快照时间应该正确"
        assert snapshot['ignored_by'] == '所领导', "忽略人应该正确"
        assert snapshot['ignored_reason'] == '测试忽略', "忽略原因应该正确"


def test_time_change_cancels_ignore(temp_db):
    """测试4：预期时间变化应该自动取消忽略"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建任务
        tasks_data = [{
            'key': {
                'file_type': 2,
                'project_id': '2016',
                'interface_id': 'S-TEST-004',
                'source_file': 'test_file.xlsx',
                'row_index': 400
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025-11-10',
                'role': '设计人员',
                'display_status': '待完成',
                'responsible_person': '张三'
            }
        }]
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 2. 忽略任务
        task_keys = [{
            'file_type': 2,
            'project_id': '2016',
            'interface_id': 'S-TEST-004',
            'source_file': 'test_file.xlsx',
            'row_index': 400
        }]
        result = mark_ignored_batch(temp_db, False, task_keys, '所领导', '测试忽略', now)
        assert result['success_count'] == 1
        
        # 3. 修改预期时间并重新upsert
        tasks_data[0]['fields']['interface_time'] = '2025-12-20'
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 4. 验证忽略状态应该被取消
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT ignored, ignored_at
            FROM tasks
            WHERE interface_id = 'S-TEST-004'
              AND project_id = '2016'
              AND status != 'archived'
            ORDER BY last_seen_at DESC
            LIMIT 1
        """)
        task = cursor.fetchone()
        
        # 5. 验证快照应该被删除
        cursor2 = conn.execute("""
            SELECT COUNT(*) as count
            FROM ignored_snapshots
            WHERE interface_id = 'S-TEST-004'
              AND project_id = '2016'
        """)
        snapshot_count = cursor2.fetchone()[0]
        conn.close()
        
        assert task is not None, "任务应该存在"
        assert (task['ignored'] or 0) == 0, "忽略标记应该被取消"
        assert snapshot_count == 0, "快照记录应该被删除"


def test_time_format_change_does_not_cancel_ignore(temp_db):
    """测试5：仅时间格式变化不应取消忽略"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建任务
        tasks_data = [{
            'key': {
                'file_type': 2,
                'project_id': '2016',
                'interface_id': 'S-TEST-005',
                'source_file': 'test_file.xlsx',
                'row_index': 500
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025-11-10',
                'role': '设计人员',
                'display_status': '待完成',
                'responsible_person': '张三'
            }
        }]
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 2. 忽略任务
        task_keys = [{
            'file_type': 2,
            'project_id': '2016',
            'interface_id': 'S-TEST-005',
            'source_file': 'test_file.xlsx',
            'row_index': 500
        }]
        result = mark_ignored_batch(temp_db, False, task_keys, '所领导', '测试忽略', now)
        assert result['success_count'] == 1
        
        # 3. 修改时间格式（但实际日期相同）并重新upsert
        tasks_data[0]['fields']['interface_time'] = '2025.11.10'  # 格式变化
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 4. 验证忽略状态应该保持
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT ignored
            FROM tasks
            WHERE interface_id = 'S-TEST-005'
              AND project_id = '2016'
              AND status != 'archived'
            ORDER BY last_seen_at DESC
            LIMIT 1
        """)
        task = cursor.fetchone()
        conn.close()
        
        assert task is not None, "任务应该存在"
        assert task['ignored'] == 1, "忽略标记应该保持"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

