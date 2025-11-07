#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Registry归档逻辑

验证：
1. 任务消失后正确标记missing_since
2. 超期任务自动归档（7天后）
3. 未超期任务不归档（6天）
4. 已确认任务不标记消失
5. 归档事件正确记录
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry import hooks as registry_hooks
from registry.service import finalize_scan, upsert_task
from registry.db import get_connection
from registry.models import Status


def test_mark_missing_tasks():
    """测试标记消失的任务"""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        # 创建任务（昨天见到）
        yesterday = datetime(2025, 11, 4, 10, 0, 0)
        today = datetime(2025, 11, 5, 10, 0, 0)
        
        print("\n[步骤1] 创建昨天的任务")
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-001',
            'source_file': 'test.xlsx',
            'row_index': 10
        }
        fields = {
            'interface_time': '2025.11.10',
            'display_status': '待完成',
            'status': Status.OPEN
        }
        
        upsert_task(temp_db, True, key, fields, yesterday)
        print("  任务已创建，last_seen_at=昨天")
        
        # 执行归档扫描（今天）
        print("\n[步骤2] 执行归档扫描（今天）")
        finalize_scan(temp_db, True, today, missing_keep_days=7)
        
        # 验证任务被标记为missing
        conn = get_connection(temp_db, True)
        cursor = conn.execute("""
            SELECT missing_since FROM tasks
            WHERE interface_id = 'TEST-001'
        """)
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] is not None, "应该标记missing_since"
        print(f"  [OK] 任务已标记消失: missing_since={row[0]}")
        
        print("\n[SUCCESS] 标记消失任务测试通过")
        
    finally:
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


def test_archive_old_tasks():
    """测试归档超期任务（7天后）"""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        # 创建任务（10天前见到）
        ten_days_ago = datetime(2025, 10, 26, 10, 0, 0)
        eight_days_ago = datetime(2025, 10, 28, 10, 0, 0)
        today = datetime(2025, 11, 5, 10, 0, 0)
        
        print("\n[步骤1] 创建10天前的任务")
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'OLD-TASK',
            'source_file': 'old.xlsx',
            'row_index': 10
        }
        fields = {
            'interface_time': '2025.10.20',
            'display_status': '待完成',
            'status': Status.OPEN
        }
        
        upsert_task(temp_db, True, key, fields, ten_days_ago)
        
        # 第一次扫描（8天前），标记missing_since
        print("\n[步骤2] 第一次扫描（8天前），标记消失")
        finalize_scan(temp_db, True, eight_days_ago, missing_keep_days=7)
        
        # 验证已标记
        conn = get_connection(temp_db, True)
        cursor = conn.execute("SELECT missing_since, status FROM tasks WHERE interface_id = 'OLD-TASK'")
        row = cursor.fetchone()
        assert row[0] is not None, "应该标记missing_since"
        assert row[1] == Status.OPEN, "status应该仍是open"
        print(f"  [OK] 任务已标记消失（8天前）")
        
        # 第二次扫描（今天），归档任务（超过7天）
        print("\n[步骤3] 第二次扫描（今天），归档超期任务")
        finalize_scan(temp_db, True, today, missing_keep_days=7)
        
        # 验证已归档
        cursor = conn.execute("""
            SELECT status, archive_reason FROM tasks
            WHERE interface_id = 'OLD-TASK'
        """)
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == Status.ARCHIVED, f"应该归档，实际status={row[0]}"
        assert row[1] == 'missing_from_source', f"归档原因应该是missing_from_source，实际：{row[1]}"
        print(f"  [OK] 任务已归档: status={row[0]}, reason={row[1]}")
        
        # 验证ARCHIVED事件
        cursor = conn.execute("SELECT event FROM events WHERE event = 'archived'")
        event = cursor.fetchone()
        assert event is not None, "应该记录ARCHIVED事件"
        print(f"  [OK] ARCHIVED事件已记录")
        
        print("\n[SUCCESS] 归档超期任务测试通过")
        
    finally:
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


def test_not_archive_recent_tasks():
    """测试未超期任务不归档（6天）"""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        # 创建任务（6天前标记消失）
        six_days_ago = datetime(2025, 10, 30, 10, 0, 0)
        today = datetime(2025, 11, 5, 10, 0, 0)
        
        print("\n[测试] 未超期任务不归档（6天 < 7天）")
        
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'RECENT-TASK',
            'source_file': 'test.xlsx',
            'row_index': 20
        }
        fields = {
            'interface_time': '2025.10.25',
            'status': Status.OPEN
        }
        
        upsert_task(temp_db, True, key, fields, six_days_ago)
        
        # 标记missing_since（6天前）
        conn = get_connection(temp_db, True)
        conn.execute("""
            UPDATE tasks
            SET missing_since = ?
            WHERE interface_id = 'RECENT-TASK'
        """, (six_days_ago.isoformat(),))
        conn.commit()
        
        # 归档扫描（今天）
        finalize_scan(temp_db, True, today, missing_keep_days=7)
        
        # 验证未归档
        cursor = conn.execute("SELECT status FROM tasks WHERE interface_id = 'RECENT-TASK'")
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] != Status.ARCHIVED, f"不应该归档（只过了6天），实际status={row[0]}"
        print(f"  [OK] 任务未归档（6天 < 7天）: status={row[0]}")
        
        print("\n[SUCCESS] 未超期任务测试通过")
        
    finally:
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


def test_confirmed_tasks_not_marked_missing():
    """测试已确认任务不标记消失"""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        yesterday = datetime(2025, 11, 4, 10, 0, 0)
        today = datetime(2025, 11, 5, 10, 0, 0)
        
        print("\n[测试] 已确认任务不标记消失")
        
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'CONFIRMED-TASK',
            'source_file': 'test.xlsx',
            'row_index': 30
        }
        fields = {
            'interface_time': '2025.10.20',
            'status': Status.CONFIRMED,  # 已确认
            'confirmed_at': '2025-10-25T10:00:00'
        }
        
        upsert_task(temp_db, True, key, fields, yesterday)
        
        # 归档扫描（今天）
        finalize_scan(temp_db, True, today, missing_keep_days=7)
        
        # 验证未标记missing
        conn = get_connection(temp_db, True)
        cursor = conn.execute("SELECT missing_since FROM tasks WHERE interface_id = 'CONFIRMED-TASK'")
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] is None, f"已确认任务不应该标记消失，实际missing_since={row[0]}"
        print(f"  [OK] 已确认任务未标记消失")
        
        print("\n[SUCCESS] 已确认任务测试通过")
        
    finally:
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


if __name__ == "__main__":
    print("=" * 80)
    print("Registry归档逻辑测试")
    print("=" * 80)
    
    test_mark_missing_tasks()
    test_archive_old_tasks()
    test_not_archive_recent_tasks()
    test_confirmed_tasks_not_marked_missing()
    
    print("\n" + "=" * 80)
    print("所有测试通过！[SUCCESS]")
    print("=" * 80)

