#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键修复的集成测试

测试场景：
1. 科室为空时自动填充"请室主任确认"
2. 忽略任务后，重新处理文件时ignored状态保持不变
3. ignored=1的任务不显示在主界面（通过get_display_status验证）
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os
import sqlite3


def test_department_default_value_in_upsert():
    """测试1：upsert时科室为空自动填充默认值"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection
        from registry.service import upsert_task
        
        # 初始化数据库
        conn = get_connection(db_path, wal=False)
        conn.close()
        
        # 测试场景1：department为空字符串
        task_key = {
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'TEST-EMPTY-DEPT-001',
            'source_file': 'test.xlsx',
            'row_index': 2,
            'interface_time': '2025.11.15'
        }
        
        task_fields = {
            'department': '',  # 空字符串
            'interface_time': '2025.11.15',
            'role': '设计人员'
        }
        
        upsert_task(db_path, False, task_key, task_fields, datetime.now())
        
        # 查询验证
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT department FROM tasks 
            WHERE interface_id = 'TEST-EMPTY-DEPT-001'
        """)
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None, "任务应该存在"
        department = row[0]
        assert department == '请室主任确认', f"空字符串应该被替换为'请室主任确认'，实际是'{department}'"
        
        print(f"\n✓ 测试1通过：空字符串 → '请室主任确认'")
        
        # 测试场景2：department为None
        task_key2 = {
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'TEST-NONE-DEPT-002',
            'source_file': 'test.xlsx',
            'row_index': 3,
            'interface_time': '2025.11.15'
        }
        
        task_fields2 = {
            'department': None,  # None
            'interface_time': '2025.11.15',
            'role': '设计人员'
        }
        
        conn = get_connection(db_path, wal=False)
        conn.close()
        upsert_task(db_path, False, task_key2, task_fields2, datetime.now())
        
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT department FROM tasks 
            WHERE interface_id = 'TEST-NONE-DEPT-002'
        """)
        row = cursor.fetchone()
        conn.close()
        
        department2 = row[0]
        assert department2 == '请室主任确认', f"None应该被替换为'请室主任确认'，实际是'{department2}'"
        
        print(f"✓ 测试2通过：None → '请室主任确认'")
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_ignored_status_preserved_on_reprocess():
    """测试2：重新处理文件时，ignored状态保持不变"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection
        from registry.service import upsert_task, mark_ignored_batch
        
        # 初始化数据库
        conn = get_connection(db_path, wal=False)
        conn.close()
        
        # 第一步：创建任务
        task_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JJ-01-25C1-25C3',
            'source_file': 'test.xlsx',
            'row_index': 2,
            'interface_time': '2025.11.07'
        }
        
        task_fields = {
            'department': '结构一室',
            'interface_time': '2025.11.07',
            'role': '设计人员',
            'responsible_person': '张敬武'
        }
        
        upsert_task(db_path, False, task_key, task_fields, datetime.now())
        
        # 第二步：标记为忽略
        result = mark_ignored_batch(
            db_path=db_path,
            wal=False,
            task_keys=[task_key],
            ignored_by='闫伟',
            ignored_reason='测试忽略'
        )
        
        assert result['success_count'] == 1, "应该成功忽略1个任务"
        
        # 验证ignored=1
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT ignored, ignored_by FROM tasks 
            WHERE interface_id = 'S-SA---1JJ-01-25C1-25C3'
        """)
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None
        ignored, ignored_by = row
        assert ignored == 1, f"忽略后ignored应该是1，实际是{ignored}"
        assert ignored_by == '闫伟', f"ignored_by应该是'闫伟'，实际是'{ignored_by}'"
        
        print(f"\n✓ 第一步：成功标记为忽略 (ignored=1)")
        
        # 第三步：模拟重新处理文件（upsert相同任务，但不带ignored字段）
        task_fields_reprocess = {
            'department': '结构一室',
            'interface_time': '2025.11.07',  # 时间未变
            'role': '设计人员',
            'responsible_person': '张敬武'
            # 注意：这里没有ignored字段，模拟从Excel重新读取
        }
        
        upsert_task(db_path, False, task_key, task_fields_reprocess, datetime.now())
        
        # 验证ignored仍然=1
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT ignored, ignored_by, ignored_reason FROM tasks 
            WHERE interface_id = 'S-SA---1JJ-01-25C1-25C3'
        """)
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None
        ignored_after, ignored_by_after, ignored_reason_after = row
        
        assert ignored_after == 1, f"重新处理后ignored应该仍是1，但实际是{ignored_after}"
        assert ignored_by_after == '闫伟', f"ignored_by应该保持为'闫伟'，但实际是'{ignored_by_after}'"
        assert ignored_reason_after == '测试忽略', f"ignored_reason应该保持，但实际是'{ignored_reason_after}'"
        
        print(f"✓ 第二步：重新处理后ignored状态保持不变 (ignored={ignored_after})")
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_ignored_tasks_filtered_from_display():
    """测试3：ignored=1的任务不显示在主界面"""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection
        from registry.service import upsert_task, mark_ignored_batch, get_display_status
        
        # 初始化数据库
        conn = get_connection(db_path, wal=False)
        conn.close()
        
        # 创建3个任务
        tasks = [
            {
                'key': {
                    'file_type': 1,
                    'project_id': '1818',
                    'interface_id': 'TASK-NORMAL',
                    'source_file': 'test.xlsx',
                    'row_index': 2,
                    'interface_time': '2025.11.15'
                },
                'fields': {
                    'department': '结构一室',
                    'interface_time': '2025.11.15',
                    'role': '设计人员'
                }
            },
            {
                'key': {
                    'file_type': 1,
                    'project_id': '1818',
                    'interface_id': 'TASK-IGNORED',
                    'source_file': 'test.xlsx',
                    'row_index': 3,
                    'interface_time': '2025.11.15'
                },
                'fields': {
                    'department': '结构二室',
                    'interface_time': '2025.11.15',
                    'role': '设计人员'
                }
            },
            {
                'key': {
                    'file_type': 1,
                    'project_id': '1818',
                    'interface_id': 'TASK-ALSO-NORMAL',
                    'source_file': 'test.xlsx',
                    'row_index': 4,
                    'interface_time': '2025.11.15'
                },
                'fields': {
                    'department': '建筑总图室',
                    'interface_time': '2025.11.15',
                    'role': '设计人员'
                }
            }
        ]
        
        # 创建所有任务
        for task in tasks:
            upsert_task(db_path, False, task['key'], task['fields'], datetime.now())
        
        # 忽略第2个任务
        mark_ignored_batch(
            db_path=db_path,
            wal=False,
            task_keys=[tasks[1]['key']],
            ignored_by='测试用户',
            ignored_reason='测试'
        )
        
        # 查询显示状态
        task_keys_for_display = [
            {**task['key'], 'interface_time': task['fields']['interface_time']}
            for task in tasks
        ]
        
        display_status = get_display_status(db_path, False, task_keys_for_display, [])
        
        # 验证：ignored=1的任务应该不在返回结果中
        # 或者返回空字符串（表示不显示）
        print(f"\n✓ 显示状态查询结果:")
        for task in tasks:
            interface_id = task['key']['interface_id']
            from registry.util import make_task_id
            tid = make_task_id(
                task['key']['file_type'],
                task['key']['project_id'],
                task['key']['interface_id'],
                task['key']['source_file'],
                task['key']['row_index']
            )
            status = display_status.get(tid, '(未返回)')
            print(f"  {interface_id}: {status}")
        
        # TASK-IGNORED应该不显示或返回空
        from registry.util import make_task_id
        ignored_tid = make_task_id(
            tasks[1]['key']['file_type'],
            tasks[1]['key']['project_id'],
            tasks[1]['key']['interface_id'],
            tasks[1]['key']['source_file'],
            tasks[1]['key']['row_index']
        )
        
        ignored_status = display_status.get(ignored_tid, '')
        
        # get_display_status会过滤ignored=1的任务，所以不应该返回或返回空
        assert ignored_status == '', f"被忽略的任务不应该有显示状态，但返回了'{ignored_status}'"
        
        print(f"✓ 被忽略的任务正确过滤（不显示）")
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

