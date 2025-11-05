"""
调试脚本：检查已指派任务的responsible_person字段

用于排查为什么指派后重新扫描，responsible_person字段丢失的问题
"""

import sqlite3
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from registry import config as registry_config

def check_assigned_tasks():
    """检查所有已指派的任务"""
    
    # 加载配置
    cfg = registry_config.load_config()
    db_path = cfg.get('registry_db_path')
    
    if not db_path:
        print("[ERROR] Registry DB path not configured")
        return
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database file not found: {db_path}")
        print(f"[INFO] Please check if registry is enabled and database has been created")
        return
    
    print(f"[INFO] Connecting to database: {db_path}")
    print("=" * 100)
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查询所有有assigned_by的任务（已指派的任务）
    print("\n【1】查询所有已指派的任务（assigned_by不为NULL）:\n")
    cursor.execute("""
        SELECT 
            id,
            file_type,
            project_id,
            interface_id,
            source_file,
            row_index,
            assigned_by,
            assigned_at,
            responsible_person,
            display_status,
            status,
            first_seen_at,
            last_seen_at
        FROM tasks
        WHERE assigned_by IS NOT NULL
        ORDER BY last_seen_at DESC
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"找到 {len(rows)} 条已指派任务:\n")
        for row in rows:
            print(f"任务ID: {row[0]}")
            print(f"  文件类型: {row[1]}")
            print(f"  项目号: {row[2]}")
            print(f"  接口号: {row[3]}")
            print(f"  源文件: {row[4]}")
            print(f"  行号: {row[5]}")
            print(f"  指派人: {row[6]}")
            print(f"  指派时间: {row[7]}")
            print(f"  ⭐ responsible_person: {row[8]}")
            print(f"  ⭐ display_status: {row[9]}")
            print(f"  状态: {row[10]}")
            print(f"  首次扫描: {row[11]}")
            print(f"  最后扫描: {row[12]}")
            print("-" * 100)
    else:
        print("没有找到已指派的任务")
    
    # 查询所有有responsible_person的任务
    print("\n【2】查询所有有责任人的任务（responsible_person不为NULL）:\n")
    cursor.execute("""
        SELECT 
            id,
            file_type,
            project_id,
            interface_id,
            responsible_person,
            assigned_by,
            display_status,
            last_seen_at
        FROM tasks
        WHERE responsible_person IS NOT NULL
        ORDER BY last_seen_at DESC
        LIMIT 10
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"找到 {len(rows)} 条有责任人的任务:\n")
        for row in rows:
            print(f"任务ID: {row[0]}")
            print(f"  文件类型: {row[1]}, 项目号: {row[2]}, 接口号: {row[3]}")
            print(f"  ⭐ responsible_person: {row[4]}")
            print(f"  assigned_by: {row[5]}")
            print(f"  display_status: {row[6]}")
            print(f"  最后扫描: {row[7]}")
            print("-" * 100)
    else:
        print("没有找到有责任人的任务")
    
    # 查询最近的ASSIGNED事件
    print("\n【3】查询最近的ASSIGNED事件:\n")
    cursor.execute("""
        SELECT 
            id,
            event_type,
            timestamp,
            payload
        FROM events
        WHERE event_type = 'ASSIGNED'
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"找到 {len(rows)} 条ASSIGNED事件:\n")
        for row in rows:
            print(f"事件ID: {row[0]}")
            print(f"  类型: {row[1]}")
            print(f"  时间: {row[2]}")
            print(f"  数据: {row[3]}")
            print("-" * 100)
    else:
        print("没有找到ASSIGNED事件")
    
    # 统计信息
    print("\n【4】数据库统计信息:\n")
    
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    print(f"总任务数: {total_tasks}")
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_by IS NOT NULL")
    assigned_tasks = cursor.fetchone()[0]
    print(f"已指派任务数（assigned_by不为NULL）: {assigned_tasks}")
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE responsible_person IS NOT NULL")
    has_responsible = cursor.fetchone()[0]
    print(f"有责任人的任务数（responsible_person不为NULL）: {has_responsible}")
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE display_status LIKE '%待完成%'")
    pending_tasks = cursor.fetchone()[0]
    print(f"待完成任务数: {pending_tasks}")
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE display_status LIKE '%请指派%'")
    need_assign_tasks = cursor.fetchone()[0]
    print(f"请指派任务数: {need_assign_tasks}")
    
    # 检查COALESCE逻辑是否正常
    print("\n【5】检查可能的问题任务（assigned_by有值但responsible_person为NULL）:\n")
    cursor.execute("""
        SELECT 
            id,
            file_type,
            project_id,
            interface_id,
            assigned_by,
            responsible_person,
            display_status,
            last_seen_at
        FROM tasks
        WHERE assigned_by IS NOT NULL AND responsible_person IS NULL
        LIMIT 5
    """)
    
    rows = cursor.fetchall()
    if rows:
        print(f"⚠️ 发现 {len(rows)} 条异常任务（assigned_by有值但responsible_person为NULL）:\n")
        for row in rows:
            print(f"任务ID: {row[0]}")
            print(f"  文件类型: {row[1]}, 项目号: {row[2]}, 接口号: {row[3]}")
            print(f"  assigned_by: {row[4]}")
            print(f"  ❌ responsible_person: {row[5]} (应该不为NULL!)")
            print(f"  display_status: {row[6]}")
            print(f"  最后扫描: {row[7]}")
            print("-" * 100)
    else:
        print("✅ 没有发现异常任务")
    
    conn.close()
    print("\n" + "=" * 100)
    print("检查完成！")

if __name__ == "__main__":
    check_assigned_tasks()

