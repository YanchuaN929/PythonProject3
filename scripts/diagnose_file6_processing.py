#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断文件6处理逻辑

检查：
1. target_files6中的元组是否正确匹配
2. process_target_file6是否正确设置source_file
3. 项目号和文件名的匹配关系
"""

import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def diagnose():
    """诊断文件6处理"""
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
    
    print(f"数据文件夹: {folder_path}")
    print("=" * 80)
    
    # 查找所有Excel文件
    import glob
    excel_files = []
    for ext in ['*.xlsx', '*.xls']:
        excel_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    print(f"\n找到 {len(excel_files)} 个Excel文件")
    
    # 使用main.py的逻辑查找文件6
    from core import main
    target_files6 = main.find_all_target_files6(excel_files)
    
    print(f"\n文件6列表: {len(target_files6)} 个文件")
    for file_path, project_id in target_files6:
        file_name = os.path.basename(file_path)
        print(f"  文件: {file_name}")
        print(f"  项目号: {project_id}")
        print(f"  完整路径: {file_path}")
        print()
    
    # 处理每个文件6，检查结果
    from datetime import datetime
    current_datetime = datetime.now()
    
    print("\n" + "=" * 80)
    print("处理每个文件6并检查结果:")
    print("=" * 80)
    
    for file_path, expected_project_id in target_files6:
        file_name = os.path.basename(file_path)
        print(f"\n处理文件: {file_name}")
        print(f"期望项目号: {expected_project_id}")
        
        try:
            # 处理文件
            result_df = main.process_target_file6(file_path, current_datetime, skip_date_filter=True)
            
            if result_df is None or result_df.empty:
                print("  结果: 无数据")
                continue
            
            print(f"  结果行数: {len(result_df)}")
            
            # 检查source_file列
            if 'source_file' in result_df.columns:
                unique_source_files = result_df['source_file'].unique()
                print(f"  source_file列: {len(unique_source_files)} 个唯一值")
                for sf in unique_source_files:
                    print(f"    - {sf}")
                    # 检查是否是绝对路径
                    if os.path.isabs(sf):
                        print("      ✓ 是绝对路径")
                    else:
                        print("      ✗ 不是绝对路径")
            else:
                print("  ✗ 没有source_file列")
            
            # 检查项目号列（如果添加了）
            if '项目号' in result_df.columns:
                unique_project_ids = result_df['项目号'].unique()
                print(f"  项目号列: {unique_project_ids}")
            else:
                print("  注意: 没有项目号列（会在start_processing中添加）")
            
            # 显示前几行的接口号
            if len(result_df) > 0:
                print("  前3个接口号:")
                for i, row in result_df.head(3).iterrows():
                    interface_id = row.iloc[4] if len(row) > 4 else "N/A"  # E列
                    print(f"    {i}: {interface_id}")
        
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        diagnose()
    except Exception as e:
        print(f"\n诊断过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

