"""
测试指派操作是否正确记录入档案
"""
import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import registry.hooks as registry_hooks
from registry.service import upsert_task, query_task_history, get_display_status
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


def test_assignment_records_assigned_by(temp_db):
    """测试指派操作是否正确记录assigned_by字段"""
    
    # 模拟指派操作
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        registry_hooks.on_assigned(
            file_type=1,
            file_path="test_file.xlsx",
            row_index=5,
            interface_id="S-TEST-001",
            project_id="2016",
            assigned_by="张三（所领导）",  # 实际用户信息
            assigned_to="李四"
        )
    
    # 验证数据库记录
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT assigned_by, assigned_at, responsible_person, display_status
        FROM tasks
        WHERE interface_id = 'S-TEST-001'
          AND project_id = '2016'
          AND status != 'archived'
        ORDER BY last_seen_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None, "指派任务应该被记录到数据库"
    assert row['assigned_by'] == "张三（所领导）", "assigned_by应该是实际用户而非'系统用户'"
    assert row['assigned_at'] is not None, "assigned_at应该有值"
    assert row['responsible_person'] == "李四", "responsible_person应该是被指派人"
    assert row['display_status'] == "待完成", "指派后显示状态应该是待完成"


def test_assignment_creates_event_record(temp_db):
    """测试指派操作是否创建事件记录"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        registry_hooks.on_assigned(
            file_type=1,
            file_path="test_file.xlsx",
            row_index=5,
            interface_id="S-TEST-002",
            project_id="2016",
            assigned_by="王五（室主任）",
            assigned_to="赵六"
        )
    
    # 验证事件记录
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT event, interface_id, project_id, extra
        FROM events
        WHERE interface_id = 'S-TEST-002'
          AND project_id = '2016'
          AND event = 'assigned'
        ORDER BY ts DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None, "指派操作应该创建事件记录"
    assert row['event'] == "assigned", "事件类型应该是assigned"
    
    # 验证extra字段包含指派信息
    import json
    extra = json.loads(row['extra']) if row['extra'] else {}
    assert extra.get('assigned_by') == "王五（室主任）", "事件记录应包含正确的assigned_by"
    assert extra.get('assigned_to') == "赵六", "事件记录应包含正确的assigned_to"


def test_assignment_visible_in_history(temp_db):
    """测试指派操作在历史查询中可见"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        # 模拟完整流程：创建任务 -> 指派 -> 完成 -> 确认
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-TEST-003',
            'source_file': 'test_file.xlsx',
            'row_index': 10
        }
        
        # 1. 创建任务
        fields = {
            'department': '测试科室',
            'interface_time': '2025-11-10',
            'role': '设计人员',
            'display_status': '待完成',
            'responsible_person': ''
        }
        upsert_task(temp_db, False, key, fields, datetime.now())
        
        # 2. 指派任务
        registry_hooks.on_assigned(
            file_type=1,
            file_path="test_file.xlsx",
            row_index=10,
            interface_id="S-TEST-003",
            project_id="2016",
            assigned_by="李经理（接口工程师）",
            assigned_to="小明"
        )
        
        # 3. 查询历史记录
        history = query_task_history(temp_db, False, '2016', 'S-TEST-003', 1)
    
    assert len(history) > 0, "应该有历史记录"
    
    # 找到最新的非归档记录
    active_record = None
    for record in history:
        if record.get('status') != 'archived':
            active_record = record
            break
    
    assert active_record is not None, "应该有活跃的任务记录"
    assert active_record.get('assigned_by') == "李经理（接口工程师）", "历史记录中应包含assigned_by信息"
    assert active_record.get('responsible_person') == "小明", "历史记录中应包含responsible_person"


def test_multiple_assignments_preserved(temp_db):
    """测试多次指派操作都能正确记录"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        # 第一次指派
        registry_hooks.on_assigned(
            file_type=1,
            file_path="test_file.xlsx",
            row_index=15,
            interface_id="S-TEST-004",
            project_id="2016",
            assigned_by="张三（所领导）",
            assigned_to="李四"
        )
        
        # 第二次指派（重新指派）
        registry_hooks.on_assigned(
            file_type=1,
            file_path="test_file.xlsx",
            row_index=15,
            interface_id="S-TEST-004",
            project_id="2016",
            assigned_by="王五（室主任）",
            assigned_to="赵六"
        )
    
    # 验证事件记录有两条
    conn = sqlite3.connect(temp_db)
    cursor = conn.execute("""
        SELECT COUNT(*) as count
        FROM events
        WHERE interface_id = 'S-TEST-004'
          AND project_id = '2016'
          AND event = 'assigned'
    """)
    count = cursor.fetchone()[0]
    conn.close()
    
    assert count == 2, "应该有两条指派事件记录"
    
    # 验证最新的任务记录是第二次指派的结果
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT assigned_by, responsible_person
        FROM tasks
        WHERE interface_id = 'S-TEST-004'
          AND project_id = '2016'
          AND status != 'archived'
        ORDER BY last_seen_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    assert row['assigned_by'] == "王五（室主任）", "最新记录应该是第二次指派的信息"
    assert row['responsible_person'] == "赵六", "最新记录应该是第二次指派的责任人"


def test_assignment_without_role_info(temp_db):
    """测试没有角色信息的指派（兼容性测试）"""
    
    with patch.object(registry_hooks, '_cfg', lambda: {
        'registry_db_path': temp_db,
        'wal': False
    }):
        # 只有用户名，没有角色信息
        registry_hooks.on_assigned(
            file_type=1,
            file_path="test_file.xlsx",
            row_index=20,
            interface_id="S-TEST-005",
            project_id="2016",
            assigned_by="张三",  # 没有角色信息
            assigned_to="李四"
        )
    
    # 验证数据库记录
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT assigned_by, responsible_person
        FROM tasks
        WHERE interface_id = 'S-TEST-005'
          AND project_id = '2016'
          AND status != 'archived'
        ORDER BY last_seen_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None, "指派任务应该被记录"
    assert row['assigned_by'] == "张三", "即使没有角色信息也应该正确记录用户名"
    assert row['responsible_person'] == "李四", "responsible_person应该正确记录"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

