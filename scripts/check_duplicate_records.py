#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中的重复记录

用于诊断文件6的2条记录问题
"""

import os
import sys
import sqlite3
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_duplicates():
    """检查数据库中的重复记录"""
    # 加载配置
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        folder_path = cfg.get('folder_path', '')
    except Exception as e:
        print(f"加载配置失败: {e}")
        return
    
    if not folder_path:
        print("错误：未配置folder_path")
        return
    
    # 数据库路径
    db_path = os.path.join(folder_path, '.registry', 'registry.db')
    
    if not os.path.exists(db_path):
        print(f"数据库不存在: {db_path}")
        return
    
    print(f"数据库路径: {db_path}")
    print("=" * 80)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查询所有任务，按 business_id 分组
    print("\n检查重复的 business_id:")
    cursor.execute("""
        SELECT business_id, COUNT(*) as cnt, 
               GROUP_CONCAT(id) as task_ids,
               GROUP_CONCAT(display_status) as statuses,
               GROUP_CONCAT(source_file) as source_files
        FROM tasks
        WHERE business_id IS NOT NULL
        GROUP BY business_id
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"\n发现 {len(duplicates)} 个重复的 business_id:")
        for business_id, cnt, task_ids, statuses, source_files in duplicates:
            print(f"\n  business_id: {business_id}")
            print(f"  记录数: {cnt}")
            print(f"  task_ids: {task_ids}")
            print(f"  statuses: {statuses}")
            print(f"  source_files: {source_files}")
            
            # 查询详细信息
            cursor.execute("""
                SELECT id, file_type, project_id, interface_id, 
                       source_file, row_index, display_status, status,
                       first_seen_at, last_seen_at
                FROM tasks
                WHERE business_id = ?
                ORDER BY last_seen_at DESC
            """, (business_id,))
            
            tasks = cursor.fetchall()
            print(f"\n  详细信息:")
            for i, task in enumerate(tasks, 1):
                print(f"    记录{i}:")
                print(f"      id: {task[0]}")
                print(f"      file_type: {task[1]}")
                print(f"      project_id: {task[2]}")
                print(f"      interface_id: {task[3]}")
                print(f"      source_file: {task[4]}")
                print(f"      row_index: {task[5]}")
                print(f"      display_status: {task[6]}")
                print(f"      status: {task[7]}")
                print(f"      first_seen_at: {task[8]}")
                print(f"      last_seen_at: {task[9]}")
    else:
        print("  未发现重复记录")
    
    # 检查文件6的所有记录
    print("\n" + "=" * 80)
    print("\n检查文件6的所有记录:")
    cursor.execute("""
        SELECT id, project_id, interface_id, business_id,
               source_file, row_index, display_status, status,
               first_seen_at, last_seen_at
        FROM tasks
        WHERE file_type = 6
        ORDER BY last_seen_at DESC
        LIMIT 20
    """)
    
    file6_tasks = cursor.fetchall()
    if file6_tasks:
        print(f"\n文件6记录数: {len(file6_tasks)} (显示最近20条)")
        for task in file6_tasks:
            print(f"\n  id: {task[0]}")
            print(f"  project_id: {task[1]}")
            print(f"  interface_id: {task[2]}")
            print(f"  business_id: {task[3]}")
            print(f"  source_file: {task[4]}")
            print(f"  row_index: {task[5]}")
            print(f"  display_status: {task[6]}")
            print(f"  status: {task[7]}")
            print(f"  first_seen_at: {task[8][:19] if task[8] else 'N/A'}")
            print(f"  last_seen_at: {task[9][:19] if task[9] else 'N/A'}")
    else:
        print("  未找到文件6的记录")
    
    conn.close()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        check_duplicates()
    except Exception as e:
        print(f"\n检查过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

