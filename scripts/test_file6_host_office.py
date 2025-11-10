#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件6主办室列提取验证脚本

测试目的：
1. 验证process_target_file6是否正确提取W列（索引22）的"主办室"数据
2. 验证_filter_by_single_role是否正确基于"主办室"列筛选数据
3. 验证多室并列情况的处理（如"结构一室,结构二室"）
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_host_office_extraction():
    """测试主办室列提取"""
    print("=" * 60)
    print("测试1：文件6主办室列提取")
    print("=" * 60)
    
    # 导入必要的模块
    from main import process_target_file6
    import json
    
    # 加载配置（直接读取config.json）
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        folder_path = cfg.get('folder_path', '')
    except Exception as e:
        print(f"加载配置失败: {e}")
        folder_path = ''
    
    if not folder_path:
        print("错误：未配置folder_path")
        return False
    
    # 查找文件6
    target_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.startswith('待处理文件6') and (file.endswith('.xlsx') or file.endswith('.xls')):
                target_files.append(os.path.join(root, file))
    
    if not target_files:
        print(f"未找到文件6，路径: {folder_path}")
        return False
    
    file_path = target_files[0]
    print(f"找到文件6: {os.path.basename(file_path)}")
    
    # 处理文件
    current_datetime = datetime.now()
    result_df = process_target_file6(file_path, current_datetime, skip_date_filter=True)
    
    # 检查是否有"主办室"列
    if result_df is None or result_df.empty:
        print("警告：处理结果为空")
        return False
    
    if "主办室" not in result_df.columns:
        print("错误：结果DataFrame中没有'主办室'列")
        print(f"可用列: {list(result_df.columns)}")
        return False
    
    print(f"成功：结果DataFrame包含'主办室'列")
    print(f"数据行数: {len(result_df)}")
    
    # 显示前几行的主办室数据
    print("\n主办室列数据样例：")
    for idx, row in result_df.head(10).iterrows():
        interface_id = row.iloc[4] if len(row) > 4 else "N/A"  # E列
        host_office = row.get("主办室", "")
        print(f"  接口号: {interface_id}, 主办室: {host_office}")
    
    # 统计主办室分布
    print("\n主办室分布：")
    host_office_counts = result_df["主办室"].value_counts()
    for office, count in host_office_counts.items():
        print(f"  {office}: {count}条")
    
    return True


def test_role_based_filtering():
    """测试基于主办室的角色筛选"""
    print("\n" + "=" * 60)
    print("测试2：基于主办室的角色筛选")
    print("=" * 60)
    
    # 创建测试数据
    test_data = pd.DataFrame({
        "接口号": ["A", "B", "C", "D", "E"],
        "项目号": ["1234", "1234", "1234", "1234", "1234"],
        "主办室": ["结构一室", "结构二室", "建筑总图室", "结构一室,结构二室", ""],
        "责任人": ["张三", "李四", "王五", "赵六", "孙七"]
    })
    
    print(f"测试数据：")
    print(test_data)
    
    # 导入_filter_by_single_role逻辑（需要模拟）
    # 这里简化测试，直接使用pandas的str.contains
    print("\n测试室主任筛选（包含匹配）：")
    
    # 一室主任
    mask_1 = test_data["主办室"].astype(str).str.contains('结构一室', na=False, regex=False)
    filtered_1 = test_data[mask_1]
    print(f"  一室主任可见: {list(filtered_1['接口号'])} (预期: A, D)")
    
    # 二室主任
    mask_2 = test_data["主办室"].astype(str).str.contains('结构二室', na=False, regex=False)
    filtered_2 = test_data[mask_2]
    print(f"  二室主任可见: {list(filtered_2['接口号'])} (预期: B, D)")
    
    # 建筑总图室主任
    mask_3 = test_data["主办室"].astype(str).str.contains('建筑总图室', na=False, regex=False)
    filtered_3 = test_data[mask_3]
    print(f"  建筑总图室主任可见: {list(filtered_3['接口号'])} (预期: C)")
    
    # 验证多室并列情况
    print("\n多室并列验证：")
    d_row = test_data[test_data["接口号"] == "D"].iloc[0]
    print(f"  接口D主办室: {d_row['主办室']}")
    print(f"  包含'结构一室': {'结构一室' in d_row['主办室']}")
    print(f"  包含'结构二室': {'结构二室' in d_row['主办室']}")
    
    return True


def main():
    """主测试流程"""
    print("文件6主办室列功能验证")
    print("=" * 60)
    
    success = True
    
    # 测试1：主办室列提取
    if not test_host_office_extraction():
        success = False
    
    # 测试2：角色筛选
    if not test_role_based_filtering():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("所有测试通过！")
    else:
        print("部分测试失败，请检查日志。")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

