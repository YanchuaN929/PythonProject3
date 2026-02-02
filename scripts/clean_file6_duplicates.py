#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理文件6的重复记录脚本

此脚本会：
1. 查找所有重复的business_id记录
2. 保留最新的记录（first_seen_at最新的）
3. 删除其他旧记录
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clean_duplicates():
    """清理文件6的重复接口记录"""
    print("=" * 80)
    print("文件6重复记录清理工具")
    print("=" * 80)
    print()
    
    from registry.hooks import _cfg
    from registry.db import get_connection
    
    cfg = _cfg()
    db_path = cfg.get('registry_db_path')
    
    if not db_path:
        print("[ERROR] 无法获取数据库路径，请检查配置")
        return
    
    if not os.path.exists(db_path):
        print(f"[ERROR] 数据库不存在: {db_path}")
        return
    
    print(f"数据库路径: {db_path}")
    print()
    
    conn = get_connection(db_path, True)
    
    # 1. 统计文件6的总记录数
    cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE file_type = 6")
    total_count = cursor.fetchone()[0]
    print(f"文件6总记录数: {total_count}")
    print()
    
    # 2. 找到所有重复的接口（同一project_id和interface_id）
    print("[1] 查找重复的接口...")
    cursor = conn.execute("""
        SELECT project_id, interface_id, COUNT(*) as cnt
        FROM tasks
        WHERE file_type = 6
        GROUP BY project_id, interface_id
        HAVING cnt > 1
    """)
    
    interface_duplicates = cursor.fetchall()
    
    if not interface_duplicates:
        print("    [OK] 没有发现重复的接口记录")
        print()
    else:
        print(f"    [WARN] 发现{len(interface_duplicates)}个重复的接口")
        print()
        
        total_deleted = 0
        
        for pid, iid, cnt in interface_duplicates:
            print(f"  处理 项目{pid} - 接口{iid} ({cnt}条记录)")
            
            # 获取所有相关记录
            cursor = conn.execute("""
                SELECT id, row_index, first_seen_at, 
                       status, display_status, responsible_person, response_number,
                       completed_at, confirmed_at, source_file
                FROM tasks
                WHERE file_type = 6 AND project_id = ? AND interface_id = ?
                ORDER BY first_seen_at DESC
            """, (pid, iid))
            
            records = cursor.fetchall()
            
            # 打印所有记录
            for idx, record in enumerate(records, 1):
                rid, row_idx, first_seen, status, ds, rp, rn, ca, conf, sf = record
                print(f"    记录{idx}: id={rid[:8]}...")
                print(f"      - row_index: {row_idx}")
                print(f"      - source_file: {sf}")
                print(f"      - first_seen_at: {first_seen}")
                print(f"      - status: {status}")
                print(f"      - display_status: {ds}")
                print(f"      - responsible_person: {rp}")
                print(f"      - response_number: {rn}")
                print(f"      - completed_at: {ca}")
            
            # 选择最新的记录作为主记录
            primary = records[0]
            print("    => 保留记录1 (最新)")
            
            # 删除其他记录
            for record in records[1:]:
                rid = record[0]
                print(f"    => 删除记录{records.index(record)+1}")
                conn.execute("DELETE FROM tasks WHERE id = ?", (rid,))
                total_deleted += 1
            
            print()
        
        conn.commit()
        print(f"[完成] 共删除{total_deleted}条重复记录")
        print()
    
    # 3. 找到所有重复的business_id（如果有）
    print("[2] 查找重复的business_id...")
    cursor = conn.execute("""
        SELECT business_id, COUNT(*) as cnt
        FROM tasks
        WHERE file_type = 6 AND business_id IS NOT NULL
        GROUP BY business_id
        HAVING cnt > 1
    """)
    
    bid_duplicates = cursor.fetchall()
    
    if not bid_duplicates:
        print("    [OK] 没有发现重复的business_id")
        print()
    else:
        print(f"    [WARN] 发现{len(bid_duplicates)}个重复的business_id")
        print()
        
        total_deleted = 0
        
        for bid, cnt in bid_duplicates:
            print(f"  处理 business_id: {bid} ({cnt}条记录)")
            
            # 获取所有相关记录
            cursor = conn.execute("""
                SELECT id, project_id, interface_id, row_index, first_seen_at, 
                       status, display_status, responsible_person, response_number,
                       completed_at
                FROM tasks
                WHERE business_id = ?
                ORDER BY first_seen_at DESC
            """, (bid,))
            
            records = cursor.fetchall()
            
            # 选择最新的记录作为主记录
            primary = records[0]
            print(f"    保留最新记录: {primary[0][:8]}... (first_seen: {primary[4]})")
            
            # 删除其他记录
            for record in records[1:]:
                print(f"    删除旧记录: {record[0][:8]}... (first_seen: {record[4]})")
                conn.execute("DELETE FROM tasks WHERE id = ?", (record[0],))
                total_deleted += 1
            
            print()
        
        conn.commit()
        print(f"[完成] 共删除{total_deleted}条重复记录")
        print()
    
    # 4. 统计清理后的记录数
    cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE file_type = 6")
    final_count = cursor.fetchone()[0]
    print(f"清理后文件6记录数: {final_count} (减少了{total_count - final_count}条)")
    print()
    
    print("=" * 80)
    print("清理完成")
    print("=" * 80)

if __name__ == "__main__":
    # 确认操作
    print()
    print("警告：此操作将删除重复的任务记录！")
    print("建议先备份数据库文件：.registry/registry.db")
    print()
    confirm = input("确认执行清理？(输入 yes 继续): ")
    
    if confirm.lower() == "yes":
        clean_duplicates()
    else:
        print("操作已取消")

