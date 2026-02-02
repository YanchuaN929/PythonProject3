#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件6完整流程

诊断：
1. 处理后的DataFrame是否包含source_file列
2. 项目号是否正确提取
3. 接口号是否正确提取
4. 原始行号是否正确
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import pytest

def test_file6_processing():
    print("=" * 80)
    print("文件6处理流程测试")
    print("=" * 80)
    print()
    
    # 1. 查找文件6
    print("[1] 查找文件6...")
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    
    if not os.path.exists(config_path):
        print(f"配置文件不存在: {config_path}")
        return
    
    import json
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    folder_path = config.get('folder_path')
    if not folder_path:
        pytest.skip("配置文件中缺少folder_path，跳过文件6流程测试")

    # 避免在 pytest 默认运行时走 UNC 网络盘导致卡死/失败
    if (folder_path.startswith("\\\\") or folder_path.startswith("//")) and not os.environ.get("RUN_NETWORK_TESTS"):
        pytest.skip("folder_path 为 UNC 网络路径，默认跳过（设置 RUN_NETWORK_TESTS=1 可强制运行）")

    if not os.path.exists(folder_path):
        pytest.skip(f"folder_path 不存在或不可访问：{folder_path}")
    
    print(f"源文件夹: {folder_path}")
    
    # 查找Excel文件
    excel_files = []
    try:
        for file in os.listdir(folder_path):
            if file.endswith(('.xlsx', '.xls')):
                excel_files.append(os.path.join(folder_path, file))
    except Exception as e:
        pytest.skip(f"无法访问 folder_path：{folder_path}，原因：{e}")
    
    # 查找文件6
    from core import main
    target_files6 = main.find_all_target_files6(excel_files)
    
    if not target_files6:
        print("未找到文件6（收发文清单）")
        return
    
    print(f"找到{len(target_files6)}个文件6:")
    for file_path, project_id in target_files6:
        print(f"  - {os.path.basename(file_path)} (项目号: {project_id or '空'})")
    print()
    
    # 2. 处理第一个文件6
    file_path, project_id = target_files6[0]
    print(f"[2] 处理文件: {os.path.basename(file_path)}")
    print(f"    项目号: {project_id or '空'}")
    print()
    
    current_datetime = datetime.now()
    result_df = main.process_target_file6(file_path, current_datetime, skip_date_filter=True)
    
    if result_df.empty:
        print("处理后的DataFrame为空")
        return
    
    print(f"处理结果: {len(result_df)}行")
    print()
    
    # 3. 检查列
    print("[3] 检查列...")
    print(f"总列数: {len(result_df.columns)}")
    print(f"列名: {list(result_df.columns)}")
    print()
    
    # 关键列检查
    key_columns = ['接口号', '项目号', '原始行号', 'source_file', '责任人', '接口时间']
    for col in key_columns:
        if col in result_df.columns:
            print(f"  [OK] {col}列存在")
        else:
            print(f"  [ERROR] {col}列不存在！")
    print()
    
    # 4. 检查第一行数据
    if len(result_df) > 0:
        print("[4] 检查第一行数据...")
        first_row = result_df.iloc[0]
        
        print(f"  接口号: {first_row.get('接口号', 'N/A')}")
        print(f"  项目号: {first_row.get('项目号', 'N/A')}")
        print(f"  原始行号: {first_row.get('原始行号', 'N/A')}")
        print(f"  source_file: {first_row.get('source_file', 'N/A')}")
        print(f"  责任人: {first_row.get('责任人', 'N/A')}")
        print(f"  接口时间: {first_row.get('接口时间', 'N/A')}")
        print()
        
        # 检查source_file是否是绝对路径
        source_file = first_row.get('source_file', '')
        if source_file:
            if os.path.isabs(source_file):
                print("  [OK] source_file是绝对路径")
            else:
                print(f"  [WARN] source_file是相对路径: {source_file}")
            
            if os.path.exists(source_file):
                print("  [OK] source_file文件存在")
            else:
                print("  [ERROR] source_file文件不存在！")
        print()
    
    # 5. 模拟写入回文单号
    if len(result_df) > 0 and 'source_file' in result_df.columns:
        print("[5] 模拟写入回文单号流程...")
        first_row = result_df.iloc[0]
        
        test_params = {
            'file_path': first_row.get('source_file'),
            'file_type': 6,
            'row_index': first_row.get('原始行号'),
            'response_number': 'TEST-2025-001',
            'user_name': '测试用户',
            'project_id': first_row.get('项目号', ''),
            'source_column': None
        }
        
        print("  模拟参数:")
        for key, value in test_params.items():
            print(f"    {key}: {value}")
        print()
        
        # 检查这些参数是否正确
        issues = []
        if not test_params['file_path']:
            issues.append("file_path为空")
        if not test_params['row_index']:
            issues.append("row_index为空")
        if not os.path.exists(test_params['file_path']):
            issues.append(f"文件不存在: {test_params['file_path']}")
        
        if issues:
            print("  [ERROR] 发现问题:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  [OK] 参数检查通过")
        print()
    
    # 6. 检查Registry记录
    print("[6] 检查Registry记录...")
    try:
        from registry.hooks import _cfg
        from registry.db import get_connection, close_connection_after_use
        
        cfg = _cfg()
        db_path = cfg.get('registry_db_path')
        
        if not db_path or not os.path.exists(db_path):
            print(f"  [WARN] Registry数据库不存在: {db_path}")
        else:
            conn = get_connection(db_path, True)
            try:
                cursor = conn.execute("""
                    SELECT COUNT(*) 
                    FROM tasks 
                    WHERE file_type = 6
                """)
                count = cursor.fetchone()[0]
                print(f"  [INFO] 数据库中文件6的任务数: {count}")
                
                if count > 0:
                    cursor = conn.execute("""
                        SELECT project_id, interface_id, source_file, row_index, 
                               display_status, responsible_person, response_number
                        FROM tasks
                        WHERE file_type = 6
                        LIMIT 3
                    """)
                    print("  前3条记录:")
                    for row in cursor.fetchall():
                        pid, iid, sf, ri, ds, rp, rn = row
                        print(f"    - {pid}/{iid} | row:{ri} | status:{ds} | resp_person:{rp} | resp_num:{rn}")
            finally:
                close_connection_after_use()
    except Exception as e:
        print(f"  [ERROR] 检查Registry失败: {e}")
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_file6_processing()

