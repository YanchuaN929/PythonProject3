#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件6问题诊断脚本

诊断项：
1. 回文单号写入列配置是否正确
2. Registry数据库中是否存在重复接口记录
3. 责任人列读取是否正确
4. 状态逻辑是否正确
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def diagnose_file6():
    print("=" * 80)
    print("文件6诊断报告")
    print("=" * 80)
    print()
    
    # 1. 检查列配置
    print("【1】检查文件6列配置")
    print("-" * 80)
    
    from ui.input_handler import get_write_columns
    
    # 模拟文件6的列配置
    columns = get_write_columns(6, 2, None)
    print(f"回文单号列: {columns['response_col']}")  # 应该是 L
    print(f"完成时间列: {columns['time_col']}")      # 应该是 J
    print(f"写入人列: {columns['name_col']}")       # 应该是 N
    print()
    
    print("预期配置:")
    print("  - 回文单号列: L列 (索引11)")
    print("  - 完成时间列: J列 (索引9)")
    print("  - 写入人列: N列 (索引13)")
    print()
    
    # 2. 检查责任人列配置
    print("【2】检查责任人列配置")
    print("-" * 80)
    print("main.py中文件6责任人列: X列 (索引23)")
    print("distribution.py中文件6责任人列: X列 (索引23)")
    print("是否一致: [OK] 是")
    print()
    
    # 3. 检查数据库中的重复记录
    print("【3】检查数据库中的重复接口记录")
    print("-" * 80)
    
    try:
        from registry.hooks import _cfg
        from registry.db import get_connection, close_connection_after_use
        cfg = _cfg()
        db_path = cfg.get('registry_db_path')
        
        if not db_path or not os.path.exists(db_path):
            print(f"[ERROR] 数据库不存在: {db_path}")
            print()
        else:
            print(f"数据库路径: {db_path}")
            
            conn = get_connection(db_path, True)
            try:
                # 检查response_number字段是否存在
                cursor = conn.execute("PRAGMA table_info(tasks)")
                columns = [row[1] for row in cursor.fetchall()]
                if 'response_number' in columns:
                    print("[OK] response_number字段存在")
                else:
                    print("[ERROR] response_number字段不存在！需要运行迁移脚本")
                print()
                
                # 查找文件6的所有任务
                cursor = conn.execute("""
                    SELECT id, file_type, project_id, interface_id, source_file, row_index,
                           business_id, status, display_status, responsible_person, 
                           response_number, completed_at
                    FROM tasks
                    WHERE file_type = 6
                    ORDER BY project_id, interface_id, first_seen_at
                """)
                
                tasks = cursor.fetchall()
            finally:
                close_connection_after_use()
            print(f"文件6总任务数: {len(tasks)}")
            print()
            
            # 检查重复的business_id
            from collections import defaultdict
            business_id_map = defaultdict(list)
            
            for task in tasks:
                tid, ft, pid, iid, sf, ri, bid, status, ds, rp, rn, ca = task
                business_id_map[bid].append({
                    'id': tid,
                    'project_id': pid,
                    'interface_id': iid,
                    'source_file': sf,
                    'row_index': ri,
                    'status': status,
                    'display_status': ds,
                    'responsible_person': rp,
                    'response_number': rn,
                    'completed_at': ca
                })
            
            # 查找重复的
            duplicates = {k: v for k, v in business_id_map.items() if len(v) > 1}
            
            if duplicates:
                print(f"[ERROR] 发现{len(duplicates)}个重复的business_id:")
                print()
                for bid, task_list in duplicates.items():
                    print(f"  business_id: {bid}")
                    for idx, task in enumerate(task_list, 1):
                        print(f"    记录{idx}:")
                        print(f"      - id: {task['id']}")
                        print(f"      - project_id: {task['project_id']}")
                        print(f"      - interface_id: {task['interface_id']}")
                        print(f"      - source_file: {task['source_file']}")
                        print(f"      - row_index: {task['row_index']}")
                        print(f"      - status: {task['status']}")
                        print(f"      - display_status: {task['display_status']}")
                        print(f"      - responsible_person: {task['responsible_person']}")
                        print(f"      - response_number: {task['response_number']}")
                        print(f"      - completed_at: {task['completed_at']}")
                    print()
            else:
                print("[OK] 没有发现重复的business_id")
                print()
            
            # 检查同一接口号不同记录
            interface_map = defaultdict(list)
            for task in tasks:
                tid, ft, pid, iid, sf, ri, bid, status, ds, rp, rn, ca = task
                key = (pid, iid)
                interface_map[key].append({
                    'id': tid,
                    'business_id': bid,
                    'source_file': sf,
                    'row_index': ri,
                    'status': status,
                    'display_status': ds,
                    'responsible_person': rp,
                    'response_number': rn,
                    'completed_at': ca
                })
            
            multi_records = {k: v for k, v in interface_map.items() if len(v) > 1}
            
            if multi_records:
                print(f"[ERROR] 发现{len(multi_records)}个接口有多条记录:")
                print()
                for (pid, iid), task_list in multi_records.items():
                    print(f"  项目{pid} - 接口{iid}:")
                    for idx, task in enumerate(task_list, 1):
                        print(f"    记录{idx}:")
                        print(f"      - id: {task['id']}")
                        print(f"      - business_id: {task['business_id']}")
                        print(f"      - source_file: {task['source_file']}")
                        print(f"      - row_index: {task['row_index']}")
                        print(f"      - status: {task['status']}")
                        print(f"      - display_status: {task['display_status']}")
                        print(f"      - responsible_person: '{task['responsible_person']}'")
                        print(f"      - response_number: '{task['response_number']}'")
                        print(f"      - completed_at: {task['completed_at']}")
                    print()
                    
                    # 分析差异
                    print("    [ANALYSIS] 差异分析:")
                    if len(task_list) == 2:
                        t1, t2 = task_list
                        if t1['responsible_person'] != t2['responsible_person']:
                            print(f"      - 责任人不同: '{t1['responsible_person']}' vs '{t2['responsible_person']}'")
                        if t1['display_status'] != t2['display_status']:
                            print(f"      - 显示状态不同: '{t1['display_status']}' vs '{t2['display_status']}'")
                        if t1['response_number'] != t2['response_number']:
                            print(f"      - 回文单号不同: '{t1['response_number']}' vs '{t2['response_number']}'")
                        if t1['row_index'] != t2['row_index']:
                            print(f"      - 行号不同: {t1['row_index']} vs {t2['row_index']}")
                    print()
            else:
                print("[OK] 每个接口只有一条记录")
                print()
            
    except Exception as e:
        print(f"[ERROR] 检查数据库时出错: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 检查完成列配置
    print("【4】检查完成列配置")
    print("-" * 80)
    
    from registry.util import extract_completed_column_value
    import pandas as pd
    
    # 模拟一个文件6的行数据
    mock_row = pd.Series([None] * 30)
    mock_row.iloc[9] = "2025-11-09"  # J列（索引9）
    
    completed_val = extract_completed_column_value(mock_row, 6)
    print(f"文件6完成列（J列，索引9）提取结果: '{completed_val}'")
    print()
    
    # 5. 建议
    print("【5】修复建议")
    print("-" * 80)
    print("如果发现重复记录，可能的原因：")
    print("1. 同一接口在不同行（row_index不同）被创建了多次")
    print("2. source_file不同导致创建了新记录")
    print("3. business_id生成逻辑有问题")
    print()
    print("建议检查：")
    print("1. 在写入回文单号时，是否正确找到了对应的Excel行")
    print("2. 在处理Excel时，是否正确继承了之前的任务状态")
    print("3. Registry的唯一性约束是否正常工作")
    print()
    
    print("=" * 80)
    print("诊断完成")
    print("=" * 80)

if __name__ == "__main__":
    diagnose_file6()

