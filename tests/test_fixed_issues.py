"""
测试修复后的两个关键问题
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import patch

import registry.hooks as registry_hooks
from registry.service import batch_upsert_tasks, mark_ignored_batch
from registry.db import get_connection


@pytest.fixture
def temp_db(tmp_path):
    """创建临时数据库用于测试"""
    db_path = tmp_path / "registry.db"
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': str(db_path),
        'wal': False
    }):
        conn = get_connection(str(db_path), False)
        conn.close()
        yield str(db_path)
    
    try:
        if db_path.exists():
            os.unlink(db_path)
    except:
        pass


def test_confirmed_task_time_change_archives(temp_db):
    """问题1测试：已确认任务的预期时间变化应该归档旧记录并重置"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建并确认任务
        tasks_data = [{
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'S-TEST-001',
                'source_file': 'test.xlsx',
                'row_index': 100
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025-11-10',
                'role': '设计人员',
                'display_status': '待完成',
                'responsible_person': '张三',
                '_completed_col_value': 'ABC-123'
            }
        }]
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 手动设置为已确认状态
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            UPDATE tasks
            SET status = 'confirmed',
                completed_at = ?,
                completed_by = '张三',
                confirmed_at = ?,
                confirmed_by = '李四'
            WHERE interface_id = 'S-TEST-001'
        """, (now.isoformat(), now.isoformat()))
        conn.commit()
        conn.close()
        
        # 2. 修改预期时间
        tasks_data[0]['fields']['interface_time'] = '2025-12-20'
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 3. 验证应该有一条归档记录
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM tasks
            WHERE interface_id = 'S-TEST-001'
              AND status = 'archived'
        """)
        archived_count = cursor.fetchone()['count']
        
        # 4. 验证新记录状态是待完成
        cursor2 = conn.execute("""
            SELECT status, display_status, completed_at, confirmed_at
            FROM tasks
            WHERE interface_id = 'S-TEST-001'
              AND status != 'archived'
            ORDER BY last_seen_at DESC
            LIMIT 1
        """)
        new_task = cursor2.fetchone()
        conn.close()
        
        assert archived_count == 1, "应该有1条归档记录"
        assert new_task is not None, "应该有新的活跃记录"
        assert new_task['status'] == 'open', "新记录状态应该是open"
        assert new_task['completed_at'] is None, "新记录的completed_at应该是None"
        assert new_task['confirmed_at'] is None, "新记录的confirmed_at应该是None"


def test_ignored_task_time_change_unignores(temp_db):
    """问题2测试：已忽略任务的预期时间变化应该取消忽略"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        now = datetime.now()
        
        # 1. 创建任务
        tasks_data = [{
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'S-TEST-002',
                'source_file': 'test.xlsx',
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
        
        # 2. 忽略任务
        task_keys = [{
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-TEST-002',
            'source_file': 'test.xlsx',
            'row_index': 200
        }]
        mark_ignored_batch(temp_db, False, task_keys, '所领导', '测试忽略', now)
        
        # 3. 验证快照已创建
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT COUNT(*) as count
            FROM ignored_snapshots
            WHERE interface_id = 'S-TEST-002'
        """)
        snapshot_count_before = cursor.fetchone()['count']
        conn.close()
        
        # 4. 修改预期时间
        tasks_data[0]['fields']['interface_time'] = '2025-12-20'
        batch_upsert_tasks(temp_db, False, tasks_data, now)
        
        # 5. 验证忽略状态被取消
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("""
            SELECT ignored
            FROM tasks
            WHERE interface_id = 'S-TEST-002'
              AND status != 'archived'
            ORDER BY last_seen_at DESC
            LIMIT 1
        """)
        task = cursor.fetchone()
        
        # 6. 验证快照被删除
        cursor2 = conn.execute("""
            SELECT COUNT(*) as count
            FROM ignored_snapshots
            WHERE interface_id = 'S-TEST-002'
        """)
        snapshot_count_after = cursor2.fetchone()['count']
        conn.close()
        
        assert snapshot_count_before == 1, "忽略前应该有1个快照"
        assert task is not None, "任务应该存在"
        assert (task['ignored'] or 0) == 0, "忽略标记应该被取消"
        assert snapshot_count_after == 0, "快照应该被删除"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

