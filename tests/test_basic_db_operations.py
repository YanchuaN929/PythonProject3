"""
基础数据库操作测试
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from unittest.mock import patch

import registry.hooks as registry_hooks
from registry.service import upsert_task
from registry.db import get_connection


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


def test_simple_upsert(temp_db):
    """测试简单的upsert操作"""
    
    now = datetime.now()
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-TEST-001',
        'source_file': 'test.xlsx',
        'row_index': 10
    }
    fields = {
        'department': '测试科室',
        'interface_time': '2025-11-10',
        'role': '设计人员',
        'display_status': '待完成',
        'responsible_person': '张三'
    }
    
    # 插入任务
    upsert_task(temp_db, False, key, fields, now)
    
    # 验证任务被创建
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT interface_id, project_id, status, responsible_person
        FROM tasks
        WHERE interface_id = 'S-TEST-001'
    """)
    task = cursor.fetchone()
    conn.close()
    
    assert task is not None, "任务应该被创建"
    assert task['interface_id'] == 'S-TEST-001'
    assert task['responsible_person'] == '张三'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

