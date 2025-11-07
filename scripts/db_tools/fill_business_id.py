#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
填充现有任务的business_id

运行此脚本将为所有business_id为NULL的任务生成并填充business_id值
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from registry.db import get_connection
from registry.config import load_config

def main():
    print("=" * 80)
    print("Registry - 填充business_id工具")
    print("=" * 80)
    
    # 加载配置
    cfg = load_config()
    db_path = cfg.get('registry_db_path')
    
    if not db_path:
        print("\n[错误] 未配置registry_db_path")
        return
    
    if not os.path.exists(db_path):
        print(f"\n[错误] 数据库文件不存在: {db_path}")
        return
    
    print(f"\n[信息] 数据库路径: {db_path}")
    
    # 获取连接
    conn = get_connection(db_path, True)
    
    # 统计需要填充的任务数
    cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE business_id IS NULL")
    null_count = cursor.fetchone()[0]
    
    if null_count == 0:
        print("\n[成功] 所有任务的business_id都已填充，无需操作")
        return
    
    print(f"\n[信息] 发现{null_count}个任务的business_id为NULL")
    print("[操作] 正在填充business_id...")
    
    # 填充business_id
    try:
        cursor = conn.execute("""
            UPDATE tasks 
            SET business_id = file_type || '|' || project_id || '|' || interface_id
            WHERE business_id IS NULL
        """)
        
        count = cursor.rowcount
        conn.commit()
        
        print(f"\n[成功] 已为{count}个任务填充business_id")
        
        # 验证
        cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE business_id IS NULL")
        remaining = cursor.fetchone()[0]
        
        if remaining == 0:
            print("[验证] ✓ 所有任务的business_id都已填充")
        else:
            print(f"[警告] 仍有{remaining}个任务的business_id为NULL")
        
        # 显示示例
        cursor = conn.execute("""
            SELECT file_type, project_id, interface_id, business_id
            FROM tasks
            LIMIT 5
        """)
        
        print("\n[示例] 前5个任务的business_id:")
        for row in cursor.fetchall():
            print(f"  文件类型{row[0]}, 项目{row[1]}, 接口{row[2][:30]}... → {row[3]}")
        
    except Exception as e:
        print(f"\n[错误] 填充失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    
    print("\n" + "=" * 80)
    print("操作完成")
    print("=" * 80)

if __name__ == "__main__":
    main()

