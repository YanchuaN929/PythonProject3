"""
测试Excel责任人列同步到数据库

验证：
1. Excel中的责任人会被同步到数据库
2. 通过指派设置的责任人不会被Excel覆盖
3. 上级角色能正确看到状态
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
import pandas as pd
from registry.service import batch_upsert_tasks, get_display_status
from registry.util import build_task_key_from_row, build_task_fields_from_row, make_task_id
from registry.db import get_connection
from registry import hooks as registry_hooks

def main():
    print("=" * 80)
    print("[TEST] Excel Responsible Person Sync")
    print("=" * 80)
    
    # Get DB
    from registry import config as registry_config
    cfg = registry_config.load_config()
    db_path = cfg.get('registry_db_path', os.path.join('result_cache', 'registry.db'))
    wal = cfg.get('registry_wal', True)
    
    print(f"\n[INFO] Database: {db_path}")
    
    conn = get_connection(db_path, wal)
    print("[OK] Database initialized")
    
    # Test 1: Task with responsible_person in Excel (not assigned)
    print("\n" + "=" * 80)
    print("[TEST 1] Task with responsible_person in Excel (not assigned)")
    print("=" * 80)
    
    df_row1 = pd.Series({
        '原始行号': 100,
        '项目号': 'TEST2016',
        '接口号': 'TEST-001',
        '责任人': 'Li Si',  # Excel has responsible person
        '部门': 'Dept A',
        '接口时间': '11.15',
        '角色来源': 'Designer'
    })
    
    key1 = build_task_key_from_row(df_row1, 1, 'test1.xlsx')
    fields1 = build_task_fields_from_row(df_row1)
    
    print(f"\n[INPUT] Excel row has:")
    print(f"  责任人: Li Si")
    print(f"\n[EXTRACTED] fields:")
    print(f"  {fields1}")
    
    # Upsert
    tasks_data = [{'key': key1, 'fields': fields1}]
    batch_upsert_tasks(db_path, wal, tasks_data, datetime.now())
    
    # Check DB
    task_id1 = make_task_id(1, 'TEST2016', 'TEST-001', 'test1.xlsx', 100)
    cursor = conn.execute(
        "SELECT assigned_by, responsible_person FROM tasks WHERE id = ?",
        (task_id1,)
    )
    row = cursor.fetchone()
    
    print(f"\n[DATABASE] After upsert:")
    print(f"  assigned_by: {row[0]}")
    print(f"  responsible_person: {row[1]}")
    
    if row[1] == 'Li Si':
        print(f"  => [OK] Excel responsible_person synced to DB")
    else:
        print(f"  => [FAIL] Expected 'Li Si', got '{row[1]}'")
    
    # Check display status
    test_key = key1.copy()
    test_key['interface_time'] = '11.15'
    
    superior_roles = ["Test Manager (Director)"]
    status_map = get_display_status(db_path, wal, [test_key], superior_roles)
    
    if task_id1 in status_map:
        status_text = status_map[task_id1]
        status_clean = status_text.encode('ascii', errors='ignore').decode('ascii').strip()
        print(f"\n[DISPLAY] Superior sees: {status_clean}")
        
        if "Please Assign" in status_text or "请指派" in status_text:
            print(f"  => [FAIL] Should NOT show 'Please Assign' (has responsible_person)")
        else:
            print(f"  => [OK] Shows correct status")
    
    # Test 2: Assigned task, then rescan with different Excel value
    print("\n" + "=" * 80)
    print("[TEST 2] Assigned task should not be overwritten by Excel")
    print("=" * 80)
    
    # First, assign the task
    registry_hooks.on_assigned(
        file_type=1,
        file_path='test2.xlsx',
        row_index=200,
        interface_id='TEST-002',
        project_id='TEST2016',
        assigned_by='Manager Wang',
        assigned_to='Zhang San'
    )
    
    print(f"\n[ASSIGNED] Task assigned to: Zhang San")
    
    # Check DB (reconnect because on_assigned may have closed connection)
    conn = get_connection(db_path, wal)
    task_id2 = make_task_id(1, 'TEST2016', 'TEST-002', 'test2.xlsx', 200)
    cursor = conn.execute(
        "SELECT assigned_by, responsible_person FROM tasks WHERE id = ?",
        (task_id2,)
    )
    row = cursor.fetchone()
    print(f"[DATABASE] After assignment:")
    print(f"  assigned_by: {row[0]}")
    print(f"  responsible_person: {row[1]}")
    
    # Now rescan with different Excel value
    df_row2 = pd.Series({
        '原始行号': 200,
        '项目号': 'TEST2016',
        '接口号': 'TEST-002',
        '责任人': 'DIFFERENT PERSON',  # Excel has different value
        '部门': 'Dept B',
        '接口时间': '11.20',
        '角色来源': 'Designer'
    })
    
    key2 = build_task_key_from_row(df_row2, 1, 'test2.xlsx')
    fields2 = build_task_fields_from_row(df_row2)
    
    print(f"\n[RESCAN] Excel now has: DIFFERENT PERSON")
    
    # Upsert again
    tasks_data = [{'key': key2, 'fields': fields2}]
    batch_upsert_tasks(db_path, wal, tasks_data, datetime.now())
    
    # Check DB again (reconnect)
    conn = get_connection(db_path, wal)
    cursor = conn.execute(
        "SELECT assigned_by, responsible_person FROM tasks WHERE id = ?",
        (task_id2,)
    )
    row = cursor.fetchone()
    
    print(f"\n[DATABASE] After rescan:")
    print(f"  assigned_by: {row[0]}")
    print(f"  responsible_person: {row[1]}")
    
    if row[1] == 'Zhang San':
        print(f"  => [OK] Assigned responsible_person NOT overwritten by Excel")
    else:
        print(f"  => [FAIL] Should be 'Zhang San', got '{row[1]}'")
    
    # Summary
    print("\n" + "=" * 80)
    print("[SUMMARY]")
    print("=" * 80)
    print("\nIf both tests passed:")
    print("1. Excel responsible_person will sync to DB")
    print("2. Assigned tasks won't be overwritten")
    print("3. Superior users will see correct status (not 'Please Assign')")
    print("=" * 80)

if __name__ == "__main__":
    main()

