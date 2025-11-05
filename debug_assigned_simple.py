"""Simple debug script to check assigned tasks in registry database"""

import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from registry import config as registry_config

def main():
    cfg = registry_config.load_config()
    db_path = cfg.get('registry_db_path')
    
    if not db_path:
        print("[ERROR] DB path not configured")
        return
    
    if not os.path.exists(db_path):
        print(f"[ERROR] DB file not found: {db_path}")
        return
    
    print(f"[OK] Found DB: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tasks with assigned_by
    print("=" * 80)
    print("[CHECK 1] Tasks with assigned_by (should have responsible_person)")
    print("=" * 80)
    
    cursor.execute("""
        SELECT 
            id, file_type, project_id, interface_id, source_file, row_index,
            assigned_by, responsible_person, display_status, last_seen_at
        FROM tasks
        WHERE assigned_by IS NOT NULL
        ORDER BY last_seen_at DESC
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"\nFound {len(rows)} assigned tasks:\n")
        for row in rows:
            print(f"ID: {row[0]}")
            print(f"  Type: {row[1]}, Project: {row[2]}, Interface: {row[3]}")
            print(f"  File: {row[4]}, Row: {row[5]}")
            print(f"  assigned_by: {row[6]}")
            print(f"  => responsible_person: [{row[7]}]  {'<-- NULL!' if row[7] is None else ''}")
            print(f"  => display_status: [{row[8]}]")
            print(f"  Last seen: {row[9]}")
            print("-" * 80)
    else:
        print("No assigned tasks found")
    
    # Check problematic tasks
    print("\n" + "=" * 80)
    print("[CHECK 2] Problematic tasks (assigned_by != NULL but responsible_person == NULL)")
    print("=" * 80)
    
    cursor.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE assigned_by IS NOT NULL AND responsible_person IS NULL
    """)
    
    problem_count = cursor.fetchone()[0]
    if problem_count > 0:
        print(f"\n[PROBLEM] Found {problem_count} problematic tasks!")
        
        cursor.execute("""
            SELECT id, file_type, project_id, interface_id, assigned_by, last_seen_at
            FROM tasks
            WHERE assigned_by IS NOT NULL AND responsible_person IS NULL
            LIMIT 3
        """)
        
        for row in cursor.fetchall():
            print(f"\nID: {row[0]}")
            print(f"  Type: {row[1]}, Project: {row[2]}, Interface: {row[3]}")
            print(f"  assigned_by: {row[4]}")
            print(f"  Last seen: {row[5]}")
    else:
        print("\n[OK] No problematic tasks found")
    
    # Statistics
    print("\n" + "=" * 80)
    print("[STATS]")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_by IS NOT NULL")
    assigned = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE responsible_person IS NOT NULL")
    has_resp = cursor.fetchone()[0]
    
    print(f"\nTotal tasks: {total}")
    print(f"Tasks with assigned_by: {assigned}")
    print(f"Tasks with responsible_person: {has_resp}")
    
    if assigned > 0 and has_resp < assigned:
        print(f"\n[WARNING] {assigned - has_resp} assigned tasks missing responsible_person!")
    
    conn.close()
    print("\n" + "=" * 80)
    print("[DONE]")

if __name__ == "__main__":
    main()

