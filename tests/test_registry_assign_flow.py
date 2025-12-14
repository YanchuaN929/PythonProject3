"""
Test script to verify the assign -> rescan workflow
Tests if responsible_person is correctly preserved after rescanning
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from registry import hooks as registry_hooks
from registry.service import upsert_task, batch_upsert_tasks, get_display_status
from registry.util import make_task_id
from registry.db import get_connection
import pandas as pd

def main():
    print("=" * 80)
    print("[TEST] Registry Assign -> Rescan Flow")
    print("=" * 80)
    
    # Setup test data
    file_type = 1
    project_id = "TEST2016"
    interface_id = "TEST-INTERFACE-001"
    source_file = "test_file.xlsx"
    row_index = 10
    
    task_key = {
        'file_type': file_type,
        'project_id': project_id,
        'interface_id': interface_id,
        'source_file': source_file,
        'row_index': row_index
    }
    
    task_id = make_task_id(file_type, project_id, interface_id, source_file, row_index)
    print(f"\n[INFO] Test Task ID: {task_id}")
    print(f"  file_type: {file_type}")
    print(f"  project_id: {project_id}")
    print(f"  interface_id: {interface_id}")
    print(f"  source_file: {source_file}")
    print(f"  row_index: {row_index}")
    
    # Get DB connection (this will initialize DB)
    from registry import config as registry_config
    cfg = registry_config.load_config()
    db_path = cfg['registry_db_path']
    wal = False
    
    print(f"\n[INFO] Database path: {db_path}")
    
    conn = get_connection(db_path, wal)
    print("[OK] Database initialized")
    
    # Step 1: Simulate assignment
    print("\n" + "-" * 80)
    print("[STEP 1] Simulate assignment")
    print("-" * 80)
    
    assigned_by = "Test Manager"
    assigned_to = "Zhang San"
    now = datetime.now()
    
    registry_hooks.on_assigned(
        file_type=file_type,
        file_path=source_file,
        row_index=row_index,
        interface_id=interface_id,
        project_id=project_id,
        assigned_by=assigned_by,
        assigned_to=assigned_to,
        now=now
    )
    
    print(f"[OK] Assignment completed: assigned_to='{assigned_to}'")
    
    # Verify assignment was saved
    cursor = conn.execute(
        "SELECT assigned_by, responsible_person, display_status FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    if row:
        print(f"\n[CHECK] After assignment:")
        print(f"  assigned_by: {row[0]}")
        print(f"  responsible_person: {row[1]}")
        print(f"  display_status: {row[2]}")
        
        if row[1] == assigned_to:
            print(f"  => [OK] responsible_person is correctly set!")
        else:
            print(f"  => [ERROR] responsible_person should be '{assigned_to}', but got '{row[1]}'")
    else:
        print("[ERROR] Task not found after assignment!")
        return
    
    # Step 2: Simulate rescan (batch_upsert_tasks)
    print("\n" + "-" * 80)
    print("[STEP 2] Simulate rescan (like 'Start Processing')")
    print("-" * 80)
    
    # Create a fake DataFrame row (mimicking processed result)
    df_row = pd.Series({
        '原始行号': row_index,
        '项目号': project_id,
        '接口号': interface_id,
        '部门': 'Test Department',
        '接口时间': '11.01',
        '角色来源': 'Designer'
    })
    
    # Build task data as would be done by on_process_done
    from registry.util import build_task_key_from_row, build_task_fields_from_row
    
    rescan_key = build_task_key_from_row(df_row, file_type, source_file)
    rescan_fields = build_task_fields_from_row(df_row)
    
    print(f"\n[INFO] Rescan task key:")
    print(f"  {rescan_key}")
    print(f"\n[INFO] Rescan fields:")
    print(f"  {rescan_fields}")
    
    # Call batch_upsert_tasks
    tasks_data = [{'key': rescan_key, 'fields': rescan_fields}]
    count = batch_upsert_tasks(db_path, wal, tasks_data, now)
    
    print(f"\n[OK] Batch upsert completed: {count} tasks")
    
    # Step 3: Verify responsible_person is preserved
    print("\n" + "-" * 80)
    print("[STEP 3] Verify responsible_person after rescan")
    print("-" * 80)
    
    cursor = conn.execute(
        "SELECT assigned_by, responsible_person, display_status, interface_time FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    if row:
        print(f"\n[CHECK] After rescan:")
        print(f"  assigned_by: {row[0]}")
        print(f"  responsible_person: {row[1]}")
        print(f"  display_status: {row[2]}")
        print(f"  interface_time: {row[3]}")
        
        if row[1] == assigned_to:
            print(f"\n  => [SUCCESS] responsible_person is preserved!")
        else:
            print(f"\n  => [FAILURE] responsible_person should be '{assigned_to}', but got '{row[1]}'")
            return
        
        if row[0] == assigned_by:
            print(f"  => [SUCCESS] assigned_by is preserved!")
        else:
            print(f"  => [FAILURE] assigned_by should be '{assigned_by}', but got '{row[0]}'")
            return
    else:
        print("[ERROR] Task not found after rescan!")
        return
    
    # Step 4: Test get_display_status for superior role
    print("\n" + "-" * 80)
    print("[STEP 4] Test status display for superior role")
    print("-" * 80)
    
    test_task_keys = [rescan_key]
    test_task_keys[0]['interface_time'] = '11.01'  # Add interface_time
    
    # Test as superior
    superior_roles = ["Test Manager (Room Director)", "2016 Interface Engineer"]
    status_map = get_display_status(db_path, wal, test_task_keys, superior_roles)
    
    if task_id in status_map:
        status_text = status_map[task_id]
        # Remove emoji for console display
        status_text_no_emoji = status_text.encode('ascii', errors='ignore').decode('ascii').strip()
        print(f"\n[CHECK] Superior sees: '{status_text_no_emoji}'")
        
        if "请指派" in status_text:
            print(f"  => [FAILURE] Should NOT show '请指派' (task is already assigned!)")
        elif "待设计人员完成" in status_text or "待完成" in status_text:
            print(f"  => [SUCCESS] Correct status!")
        else:
            print(f"  => [WARNING] Unexpected status")
    else:
        print(f"[WARNING] No status returned for task {task_id}")
    
    # Test as designer
    designer_roles = ["Zhang San (Designer)"]
    status_map = get_display_status(db_path, wal, test_task_keys, designer_roles)
    
    if task_id in status_map:
        status_text = status_map[task_id]
        status_text_no_emoji = status_text.encode('ascii', errors='ignore').decode('ascii').strip()
        print(f"\n[CHECK] Designer sees: '{status_text_no_emoji}'")
        
        if "待完成" in status_text:
            print(f"  => [SUCCESS] Correct status!")
        else:
            print(f"  => [WARNING] Unexpected status")
    
    # Final summary
    print("\n" + "=" * 80)
    print("[SUMMARY]")
    print("=" * 80)
    print("Test completed! Check results above.")
    print("=" * 80)

if __name__ == "__main__":
    main()

