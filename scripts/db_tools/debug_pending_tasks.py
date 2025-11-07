#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调试脚本：检查数据库中的待审查任务"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from registry.config import load_config
from registry.db import get_connection
import json

def main():
    # 【修复】读取config.json获取folder_path，然后传递给load_config
    folder_path = None
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            folder_path = config.get('folder_path', '').strip()
    except:
        pass
    
    cfg = load_config(data_folder=folder_path)
    db_path = cfg.get('registry_db_path')
    
    if not db_path or not os.path.exists(db_path):
        print("[错误] 数据库不存在")
        return
    
    print(f"[信息] 数据库路径: {db_path}\n")
    
    conn = get_connection(db_path, True)
    
    # 查询所有有display_status的任务
    print("=" * 80)
    print("所有有display_status的任务（应该在主窗口显示）")
    print("=" * 80)
    
    cursor = conn.execute("""
        SELECT file_type, project_id, interface_id, 
               display_status, status, 
               source_file, row_index,
               interface_time, completed_at
        FROM tasks
        WHERE display_status IS NOT NULL 
          AND display_status != ''
          AND status != 'confirmed'
          AND status != 'archived'
        ORDER BY file_type, project_id, interface_id
        LIMIT 20
    """)
    
    tasks = cursor.fetchall()
    
    if not tasks:
        print("\n[重要] 没有找到任何有display_status的任务！")
        print("[原因可能] 所有任务的display_status都是NULL")
    else:
        print(f"\n找到{len(tasks)}个任务：\n")
        for row in tasks:
            print(f"文件类型{row[0]} | 项目{row[1]} | 接口{row[2][:40]}")
            print(f"  display_status: {row[3]}")
            print(f"  status: {row[4]}")
            print(f"  source_file: {row[5]}")
            print(f"  row_index: {row[6]}")
            print(f"  interface_time: {row[7]}")
            print(f"  completed_at: {row[8]}")
            print("-" * 80)
    
    # 专门查询"待审查"的任务
    print("\n" + "=" * 80)
    print("状态为'待审查'或'待指派人审查'的任务")
    print("=" * 80)
    
    cursor = conn.execute("""
        SELECT file_type, interface_id, display_status, status
        FROM tasks
        WHERE display_status IN ('待审查', '待指派人审查')
        LIMIT 10
    """)
    
    review_tasks = cursor.fetchall()
    
    if review_tasks:
        print(f"\n找到{len(review_tasks)}个待审查任务：\n")
        for row in review_tasks:
            print(f"文件类型{row[0]} | 接口{row[1][:40]} | 状态:{row[2]} | status:{row[3]}")
    else:
        print("\n[重要] 没有找到待审查的任务！")
        print("[原因可能] 没有任务被设置为'待审查'状态")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

