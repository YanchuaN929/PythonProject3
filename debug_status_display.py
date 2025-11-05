"""
调试状态显示问题：为什么已有责任人的任务还显示"请指派"

检查点：
1. Excel中的责任人列
2. 数据库中的responsible_person字段
3. get_display_status的查询结果
4. 完整的数据流
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import json

def main():
    print("=" * 80)
    print("[DEBUG] Status Display Issue - Why 'Please Assign' shows for assigned tasks")
    print("=" * 80)
    
    # 1. 读取配置获取数据库路径
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"[ERROR] Cannot read config.json: {e}")
        return
    
    folder_path = config.get('folder_path', '').strip()
    
    # 确定数据库路径（优先检查数据文件夹，然后检查本地）
    db_paths_to_check = []
    
    if folder_path:
        data_folder_db = os.path.join(folder_path, '.registry', 'registry.db')
        db_paths_to_check.append(('Data Folder', data_folder_db))
    
    local_db = os.path.join('result_cache', 'registry.db')
    db_paths_to_check.append(('Local', local_db))
    
    print(f"\n[INFO] Checking database locations...")
    
    db_path = None
    for location_name, path in db_paths_to_check:
        print(f"  [{location_name}] {path}")
        if os.path.exists(path):
            print(f"    => FOUND!")
            db_path = path
            break
        else:
            print(f"    => Not found")
    
    if not db_path:
        print(f"\n[ERROR] No database found in any location!")
        print("[INFO] Please run the main program first to create the database.")
        return
    
    print(f"\n[USING] {db_path}")
    
    # 2. 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 3. 查询所有display_status='待完成'的任务
    print("\n" + "=" * 80)
    print("[CHECK 1] All tasks with display_status='待完成'")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            id,
            file_type,
            project_id,
            interface_id,
            source_file,
            row_index,
            assigned_by,
            responsible_person,
            display_status,
            department,
            role
        FROM tasks
        WHERE display_status = '待完成'
        ORDER BY last_seen_at DESC
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"\nFound {len(rows)} tasks with display_status='待完成':\n")
        for i, row in enumerate(rows, 1):
            print(f"[Task {i}]")
            print(f"  ID: {row[0][:40]}...")
            print(f"  File Type: {row[1]}, Project: {row[2]}, Interface: {row[3]}")
            print(f"  Source: {row[4]}, Row: {row[5]}")
            print(f"  => assigned_by: [{row[6]}]")
            print(f"  => responsible_person: [{row[7]}]  {'<-- EMPTY!' if not row[7] else '<-- HAS VALUE'}")
            print(f"  => display_status: [{row[8]}]")
            print(f"  Department: {row[9]}, Role: {row[10]}")
            
            # 判断应该显示什么
            if not row[7]:  # responsible_person is empty
                expected_status = "Please Assign (no responsible_person)"
            else:
                expected_status = "Waiting Designer Complete (has responsible_person)"
            
            print(f"  Expected for superior: {expected_status}")
            print("-" * 80)
    else:
        print("\nNo tasks with display_status='待完成' found.")
    
    # 4. 统计responsible_person字段
    print("\n" + "=" * 80)
    print("[CHECK 2] Statistics of responsible_person field")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE display_status = '待完成'")
    total_pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE display_status = '待完成' AND responsible_person IS NOT NULL AND responsible_person != ''")
    has_person = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE display_status = '待完成' AND (responsible_person IS NULL OR responsible_person = '')")
    no_person = cursor.fetchone()[0]
    
    print(f"\nTotal tasks with '待完成': {total_pending}")
    print(f"  - With responsible_person: {has_person}")
    print(f"  - Without responsible_person: {no_person}")
    
    if no_person > 0:
        print(f"\n[FINDING] {no_person} tasks have '待完成' but NO responsible_person")
        print("[REASON] These will show '请指派' for superior users")
        print("\n[QUESTION] Why don't these tasks have responsible_person?")
        print("  Possible reasons:")
        print("  1. Tasks created by file scan (not through assignment)")
        print("  2. Excel has '责任人' column, but DB doesn't sync it")
        print("  3. Assignment function was not called")
    
    # 5. 检查是否有assigned_by但没有responsible_person的任务（异常情况）
    print("\n" + "=" * 80)
    print("[CHECK 3] Abnormal: has assigned_by but NO responsible_person")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            id, interface_id, assigned_by, responsible_person, assigned_at
        FROM tasks
        WHERE assigned_by IS NOT NULL 
          AND (responsible_person IS NULL OR responsible_person = '')
        LIMIT 5
    """)
    
    abnormal = cursor.fetchall()
    if abnormal:
        print(f"\n[PROBLEM] Found {len(abnormal)} abnormal tasks!")
        print("[REASON] These tasks have assigned_by but missing responsible_person")
        print("[THIS IS A BUG] - assigned_by and responsible_person should be set together\n")
        
        for row in abnormal:
            print(f"Task: {row[0][:40]}...")
            print(f"  Interface: {row[1]}")
            print(f"  assigned_by: {row[2]}")
            print(f"  responsible_person: {row[3] or 'NULL'}")
            print(f"  assigned_at: {row[4]}")
            print("-" * 80)
    else:
        print("\n[OK] No abnormal tasks found")
        print("[INFO] All tasks with assigned_by have responsible_person")
    
    # 6. 最关键的检查：实际测试get_display_status函数
    print("\n" + "=" * 80)
    print("[CHECK 4] Test get_display_status function")
    print("=" * 80)
    
    # 获取一个有responsible_person的任务
    cursor.execute("""
        SELECT 
            file_type, project_id, interface_id, source_file, row_index,
            interface_time, responsible_person
        FROM tasks
        WHERE display_status = '待完成'
          AND responsible_person IS NOT NULL
          AND responsible_person != ''
        LIMIT 1
    """)
    
    test_task = cursor.fetchone()
    if test_task:
        print(f"\n[TEST TASK]")
        print(f"  Type: {test_task[0]}, Project: {test_task[1]}, Interface: {test_task[2]}")
        print(f"  File: {test_task[3]}, Row: {test_task[4]}")
        print(f"  Interface Time: {test_task[5]}")
        print(f"  => responsible_person: [{test_task[6]}]")
        
        # 调用get_display_status
        from registry.service import get_display_status
        
        task_key = {
            'file_type': test_task[0],
            'project_id': test_task[1],
            'interface_id': test_task[2],
            'source_file': test_task[3],
            'row_index': test_task[4],
            'interface_time': test_task[5] or ''
        }
        
        # 测试上级角色
        superior_roles = ["Test Manager (Room Director)"]
        result = get_display_status(db_path, True, [task_key], superior_roles)
        
        from registry.util import make_task_id
        task_id = make_task_id(test_task[0], test_task[1], test_task[2], test_task[3], test_task[4])
        
        if task_id in result:
            status_text = result[task_id]
            # Remove non-ASCII for display
            status_display = ''.join(c for c in status_text if ord(c) < 128 or ord(c) > 255)
            
            print(f"\n[RESULT] Superior sees: {status_display}")
            
            if "Please Assign" in status_text or "请指派" in status_text:
                print(f"  => [BUG] Should NOT show 'Please Assign'!")
                print(f"  => Task has responsible_person='{test_task[6]}'")
            else:
                print(f"  => [OK] Correct status")
        else:
            print(f"\n[WARNING] Task ID not in result: {task_id}")
    else:
        print("\n[INFO] No tasks with responsible_person found to test")
    
    # 7. 检查最近一次扫描的任务
    print("\n" + "=" * 80)
    print("[CHECK 5] Recent scanned tasks (last 5)")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            interface_id, source_file, row_index,
            assigned_by, responsible_person, display_status,
            last_seen_at
        FROM tasks
        ORDER BY last_seen_at DESC
        LIMIT 5
    """)
    
    recent = cursor.fetchall()
    if recent:
        print("\nMost recently scanned tasks:")
        for row in recent:
            print(f"\nInterface: {row[0]}")
            print(f"  File: {row[1]}, Row: {row[2]}")
            print(f"  assigned_by: {row[3] or 'NULL'}")
            print(f"  responsible_person: {row[4] or 'NULL'}")
            print(f"  display_status: {row[5] or 'NULL'}")
            print(f"  Last seen: {row[6]}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("[SUMMARY]")
    print("=" * 80)
    print("\nPlease check the output above to find:")
    print("1. Do tasks have responsible_person in DB?")
    print("2. If yes, does get_display_status return correct status?")
    print("3. If no, why responsible_person is not set?")
    print("=" * 80)

if __name__ == "__main__":
    main()

