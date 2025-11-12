#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库迁移顺序修复

验证：
1. 数据库迁移在init_db之前执行
2. ignored列能够正确创建和使用
3. 索引能够正确创建
"""
import pytest
import tempfile
import os
import sqlite3
from datetime import datetime


def test_database_migration_order():
    """测试数据库迁移顺序：应该先迁移再创建索引"""
    # 1. 创建一个旧版本的数据库（没有ignored列）
    fd, old_db_path = tempfile.mkstemp(suffix='_old.db')
    os.close(fd)
    
    try:
        # 创建旧表结构（模拟旧版本数据库）
        conn = sqlite3.connect(old_db_path)
        conn.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                file_type INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                interface_id TEXT NOT NULL,
                source_file TEXT,
                row_index INTEGER,
                interface_time TEXT,
                status TEXT DEFAULT 'open',
                completed_at TEXT,
                confirmed_at TEXT,
                archived_at TEXT,
                last_seen_at TEXT,
                missing_since TEXT,
                display_status TEXT,
                business_id TEXT
            )
        """)
        conn.commit()
        
        # 插入测试数据
        conn.execute("""
            INSERT INTO tasks (id, file_type, project_id, interface_id, status)
            VALUES ('test123', 1, '1818', 'TEST-001', 'open')
        """)
        conn.commit()
        conn.close()
        
        print(f"\n✓ 创建旧版本数据库: {old_db_path}")
        
        # 2. 使用registry的get_connection（会自动触发迁移）
        from registry.db import get_connection
        from registry.migrate import check_column_exists
        
        conn = get_connection(old_db_path, wal=False)
        
        # 3. 验证ignored列已存在
        assert check_column_exists(conn, 'tasks', 'ignored'), "ignored列应该已被添加"
        assert check_column_exists(conn, 'tasks', 'ignored_at'), "ignored_at列应该已被添加"
        assert check_column_exists(conn, 'tasks', 'ignored_by'), "ignored_by列应该已被添加"
        
        print("✓ ignored相关列已正确添加")
        
        # 4. 验证索引能够正常创建（不会报错）
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_ignored'")
        index_row = cursor.fetchone()
        assert index_row is not None, "idx_tasks_ignored索引应该已被创建"
        
        print("✓ idx_tasks_ignored索引已正确创建")
        
        # 5. 验证能够正常使用ignored列
        conn.execute("UPDATE tasks SET ignored = 1 WHERE id = 'test123'")
        conn.commit()
        
        cursor = conn.execute("SELECT ignored FROM tasks WHERE id = 'test123'")
        row = cursor.fetchone()
        assert row[0] == 1, "ignored字段应该能够正常读写"
        
        print("✓ ignored字段能够正常读写")
        
        conn.close()
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(old_db_path):
                os.unlink(old_db_path)
        except:
            pass


def test_new_database_with_ignored_column():
    """测试新建数据库时ignored列是否正确创建"""
    fd, new_db_path = tempfile.mkstemp(suffix='_new.db')
    os.close(fd)
    
    try:
        # 删除临时文件，让get_connection创建新数据库
        os.unlink(new_db_path)
        
        from registry.db import get_connection
        from registry.migrate import check_column_exists
        
        # 创建新数据库
        conn = get_connection(new_db_path, wal=False)
        
        # 验证ignored列存在
        assert check_column_exists(conn, 'tasks', 'ignored'), "新数据库应该包含ignored列"
        assert check_column_exists(conn, 'tasks', 'ignored_at'), "新数据库应该包含ignored_at列"
        assert check_column_exists(conn, 'tasks', 'ignored_by'), "新数据库应该包含ignored_by列"
        assert check_column_exists(conn, 'tasks', 'interface_time_when_ignored'), "新数据库应该包含interface_time_when_ignored列"
        assert check_column_exists(conn, 'tasks', 'ignored_reason'), "新数据库应该包含ignored_reason列"
        
        print("\n✓ 新数据库包含所有ignored相关列")
        
        # 验证索引存在
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_ignored'")
        index_row = cursor.fetchone()
        assert index_row is not None, "新数据库应该包含idx_tasks_ignored索引"
        
        print("✓ 新数据库包含idx_tasks_ignored索引")
        
        conn.close()
        
    finally:
        # 清理临时文件
        try:
            if os.path.exists(new_db_path):
                os.unlink(new_db_path)
        except:
            pass


def test_migrate_preserves_existing_data():
    """测试迁移过程中不会丢失现有数据"""
    fd, db_path = tempfile.mkstemp(suffix='_preserve.db')
    os.close(fd)
    
    try:
        # 1. 创建旧版本数据库并插入数据
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                file_type INTEGER NOT NULL,
                project_id TEXT NOT NULL,
                interface_id TEXT NOT NULL,
                status TEXT DEFAULT 'open'
            )
        """)
        
        test_data = [
            ('id1', 1, '1818', 'TEST-001', 'open'),
            ('id2', 2, '1818', 'TEST-002', 'completed'),
            ('id3', 3, '2016', 'TEST-003', 'confirmed')
        ]
        
        for data in test_data:
            conn.execute("INSERT INTO tasks (id, file_type, project_id, interface_id, status) VALUES (?, ?, ?, ?, ?)", data)
        
        conn.commit()
        conn.close()
        
        print(f"\n✓ 创建旧数据库并插入 {len(test_data)} 条数据")
        
        # 2. 触发迁移
        from registry.db import get_connection
        conn = get_connection(db_path, wal=False)
        
        # 3. 验证数据完整性
        cursor = conn.execute("SELECT id, file_type, project_id, interface_id, status, ignored FROM tasks ORDER BY id")
        rows = cursor.fetchall()
        
        assert len(rows) == len(test_data), f"应该有{len(test_data)}条数据，实际有{len(rows)}条"
        
        for i, (expected, actual) in enumerate(zip(test_data, rows)):
            assert actual[0] == expected[0], f"第{i+1}条数据ID不匹配"
            assert actual[1] == expected[1], f"第{i+1}条数据file_type不匹配"
            assert actual[2] == expected[2], f"第{i+1}条数据project_id不匹配"
            assert actual[3] == expected[3], f"第{i+1}条数据interface_id不匹配"
            assert actual[4] == expected[4], f"第{i+1}条数据status不匹配"
            assert actual[5] == 0 or actual[5] is None, f"第{i+1}条数据ignored应该为0或NULL"
        
        print(f"✓ 迁移后数据完整，共 {len(rows)} 条")
        
        conn.close()
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

