#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深度诊断：待审查任务显示和状态重置问题"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from registry.config import load_config
from registry.db import get_connection
import pandas as pd
import json

def check_problem1():
    """问题1：检查数据库中是否有待审查任务，以及Registry查询逻辑"""
    print("=" * 80)
    print("问题1诊断：待审查任务不显示")
    print("=" * 80)
    
    # 【修复】读取folder_path并传递给load_config
    folder_path = None
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            folder_path = config.get('folder_path', '').strip()
    except:
        pass
    
    cfg = load_config(data_folder=folder_path)
    db_path = cfg.get('registry_db_path')
    
    print(f"[信息] 配置的数据库路径: {db_path}")
    print(f"[信息] folder_path: {folder_path}")
    
    # 【修复】尝试多个可能的数据库位置
    possible_paths = []
    
    if db_path:
        possible_paths.append(('配置路径', db_path))
    
    # 尝试本地路径
    local_db = os.path.join('result_cache', 'registry.db')
    possible_paths.append(('本地路径', local_db))
    
    # 尝试数据文件夹
    if folder_path:
        data_folder_db = os.path.join(folder_path, '.registry', 'registry.db')
        possible_paths.append(('数据文件夹', data_folder_db))
    
    # 查找存在的数据库
    db_path = None
    for location_name, path in possible_paths:
        # 【修复】规范化路径（统一使用正斜杠或反斜杠）
        normalized_path = os.path.normpath(path)
        print(f"[检查] {location_name}: {normalized_path}")
        
        if os.path.exists(normalized_path):
            db_path = normalized_path
            print(f"  ✓ 找到数据库！")
            break
        else:
            # 再尝试原始路径（有时规范化会出错）
            if os.path.exists(path):
                db_path = path
                print(f"  ✓ 找到数据库（原始路径）！")
                break
            else:
                print(f"  ✗ 不存在")
    
    if not db_path:
        print("\n[错误] 在所有可能的位置都没有找到数据库文件")
        print("\n[调试] 请手动检查：")
        if folder_path:
            manual_check = os.path.join(folder_path, '.registry')
            print(f"  1. 数据文件夹是否存在: {folder_path}")
            print(f"  2. .registry目录是否存在: {manual_check}")
            print(f"  3. 请手动ls查看该目录下是否有registry.db")
        return
    
    print(f"\n[使用数据库] {db_path}\n")
    
    conn = get_connection(db_path, True)
    
    # 步骤1：检查表结构
    print("\n[步骤1] 检查表结构")
    cursor = conn.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"  表字段: {', '.join(columns)}")
    
    if 'display_status' not in columns:
        print("  [错误] 缺少display_status字段！")
        return
    
    if 'business_id' not in columns:
        print("  [警告] 缺少business_id字段！")
    
    # 步骤2：统计任务
    print("\n[步骤2] 统计任务")
    cursor = conn.execute("SELECT COUNT(*) FROM tasks")
    total = cursor.fetchone()[0]
    print(f"  总任务数: {total}")
    
    cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE display_status IS NOT NULL AND display_status != ''")
    has_status = cursor.fetchone()[0]
    print(f"  有display_status的任务: {has_status}")
    
    cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE display_status IN ('待审查', '待指派人审查')")
    pending = cursor.fetchone()[0]
    print(f"  待审查的任务: {pending}")
    
    cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
    completed = cursor.fetchone()[0]
    print(f"  status=completed的任务: {completed}")
    
    # 步骤3：查看具体任务
    if pending > 0:
        print(f"\n[步骤3] 查看待审查任务详情")
        cursor = conn.execute("""
            SELECT interface_id, display_status, status, completed_at, 
                   interface_time, source_file, row_index
            FROM tasks
            WHERE display_status IN ('待审查', '待指派人审查')
            LIMIT 5
        """)
        
        print("  待审查任务示例：")
        for row in cursor.fetchall():
            print(f"    接口: {row[0][:40]}")
            print(f"      display_status: {row[1]}")
            print(f"      status: {row[2]}")
            print(f"      completed_at: {row[3]}")
            print(f"      interface_time: {row[4]}")
            print(f"      source_file: {row[5]}")
            print(f"      row_index: {row[6]}")
            print()
    else:
        print(f"\n[关键发现] 数据库中没有待审查的任务！")
        print("  [可能原因]")
        print("  1. on_response_written没有正确设置display_status")
        print("  2. 接口号继承逻辑错误地重置了display_status")
        print("  3. 用户还没有填写过回文单号")


def check_problem2():
    """问题2：检查状态重置逻辑"""
    print("\n" + "=" * 80)
    print("问题2诊断：删除完成列后状态应该重置但没有")
    print("=" * 80)
    
    # 【修复】读取folder_path并传递给load_config
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
    
    conn = get_connection(db_path, True)
    
    # 查找status=completed的任务（应该有M列值）
    print("\n[检查] status=completed的任务")
    cursor = conn.execute("""
        SELECT interface_id, display_status, status, completed_at, interface_time
        FROM tasks
        WHERE status = 'completed'
        LIMIT 5
    """)
    
    completed_tasks = cursor.fetchall()
    
    if completed_tasks:
        print(f"  找到{len(completed_tasks)}个completed任务：")
        for row in completed_tasks:
            print(f"    接口: {row[0][:40]}")
            print(f"      display_status: {row[1]}")
            print(f"      status: {row[2]}")
            print(f"      completed_at: {row[3]}")
            print(f"      interface_time: {row[4]}")
            print()
        
        print("\n[分析] 状态重置逻辑")
        print("  当前逻辑：检测completed_at是否存在，以及Excel中完成列的实际值")
        print("  完成列定义：")
        print("    - 文件1: M列（索引12）")
        print("    - 文件2: N列（索引13）")
        print("    - 文件3: Q列或T列（索引16/19）")
        print("    - 文件4: V列（索引21）")
        print("    - 文件5: N列（索引13）")
        print("    - 文件6: J列（索引9）")
        print()
        print("  [已修复] 特殊检测逻辑（registry/service.py 138-141行）")
        print("  if not new_completed_val and old_task['completed_at']:")
        print("      need_reset = True  # 强制重置")
        print()
        print("  [效果] 即使Excel中完成列被删除，也会触发状态重置")
    else:
        print("  没有completed任务")


if __name__ == "__main__":
    check_problem1()
    check_problem2()

