#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel数据处理模块
此文件包含所有Excel文件的数据处理逻辑
"""

import pandas as pd
import numpy as np
import datetime
import os
from pathlib import Path
import warnings
import re
from copy import copy

# 忽略pandas警告
warnings.filterwarnings('ignore')


def process_excel_files(excel_files, current_datetime):
    """
    处理Excel文件的主函数
    
    参数:
        excel_files (list): Excel文件路径列表
        current_datetime (datetime): 当前日期时间
    
    返回:
        pandas.DataFrame: 处理后的结果数据
    """
    print(f"开始处理 {len(excel_files)} 个Excel文件...")
    print(f"处理时间: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 记录到监控器
    try:
        import Monitor
        Monitor.log_info(f"开始处理 {len(excel_files)} 个Excel文件")
        Monitor.log_info(f"处理时间: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    except:
        pass
    
    # 查找待处理文件1（特定格式的文件）
    target_file, project_id = find_target_file(excel_files)
    
    if target_file is None:
        error_msg = "未找到符合格式要求的待处理文件（四位数字+按项目导出IDI手册+日期格式）"
        print(error_msg)
        try:
            import Monitor
            Monitor.log_error(error_msg)
        except:
            pass
        return pd.DataFrame({'错误信息': ['未找到符合格式的文件']})
    
    print(f"找到待处理文件1: {os.path.basename(target_file)}")
    try:
        import Monitor
        Monitor.log_success(f"找到待处理文件1: {os.path.basename(target_file)}")
    except:
        pass
    
    try:
        # 处理特定文件
        result = process_target_file(target_file, current_datetime)
        
        if result is not None and not result.empty:
            print(f"待处理文件1处理完成，生成 {len(result)} 行完成处理数据")
            return result
        else:
            print("处理完成，但没有符合条件的数据")
            return pd.DataFrame({'信息': ['没有符合条件的数据']})
                
    except Exception as e:
        print(f"处理待处理文件1时发生错误: {str(e)}")
        return pd.DataFrame({'错误信息': [str(e)]})


def find_target_file(excel_files):
    """
    查找符合特定格式的待处理文件1
    格式：四位数字+按项目导出IDI手册+日期
    例如：2016按项目导出IDI手册2025-08-01-17_55_52
    返回：(文件路径, 项目号) 或 (None, None)
    """
    pattern = r'^(\d{4})按项目导出IDI手册\d{4}-\d{2}-\d{2}.*\.(xlsx|xls)$'
    for file_path in excel_files:
        file_name = os.path.basename(file_path)
        m = re.match(pattern, file_name)
        if m:
            project_id = m.group(1)
            print(f"匹配到待处理文件1格式: {file_name}, 项目号: {project_id}")
            return file_path, project_id
    return None, None


def find_target_file2(excel_files):
    """
    查找符合特定格式的待处理文件2
    格式：内部接口信息单报表+12位数字，前4位为项目号
    例如：内部接口信息单报表201612345678
    返回：(文件路径, 项目号) 或 (None, None)
    """
    pattern = r'^内部接口信息单报表(\d{4})\d{8}\.(xlsx|xls)$'
    for file_path in excel_files:
        file_name = os.path.basename(file_path)
        m = re.match(pattern, file_name)
        if m:
            project_id = m.group(1)
            print(f"匹配到待处理文件2格式: {file_name}, 项目号: {project_id}")
            return file_path, project_id
    return None, None


def find_target_file3(excel_files):
    """
    查找符合特定格式的待处理文件3
    格式：外部接口ICM报表+四位数字（项目号）+日期（8位）
    例如：外部接口ICM报表201620250801.xlsx
    返回：(文件路径, 项目号) 或 (None, None)
    """
    pattern = r'^外部接口ICM报表(\d{4})\d{8}\.(xlsx|xls)$'
    for file_path in excel_files:
        file_name = os.path.basename(file_path)
        m = re.match(pattern, file_name)
        if m:
            project_id = m.group(1)
            print(f"匹配到待处理文件3格式: {file_name}, 项目号: {project_id}")
            return file_path, project_id
    return None, None


def find_target_file4(excel_files):
    """
    查找符合特定格式的待处理文件4
    格式：外部接口单报表+四位数字（项目号）+日期（8位）
    例如：外部接口单报表201620250801.xlsx
    返回：(文件路径, 项目号) 或 (None, None)
    """
    pattern = r'^外部接口单报表(\d{4})\d{8}\.(xlsx|xls)$'
    for file_path in excel_files:
        file_name = os.path.basename(file_path)
        m = re.match(pattern, file_name)
        if m:
            project_id = m.group(1)
            print(f"匹配到待处理文件4格式: {file_name}, 项目号: {project_id}")
            return file_path, project_id
    return None, None


def process_target_file(file_path, current_datetime):
    """
    处理待处理文件1的主函数
    
    参数:
        file_path (str): 待处理文件1的路径
        current_datetime (datetime): 当前日期时间
    
    返回:
        pandas.DataFrame: 完成处理数据
    """
    print(f"开始处理待处理文件1: {os.path.basename(file_path)}")
    try:
        import Monitor
        Monitor.log_process(f"开始处理待处理文件1: {os.path.basename(file_path)}")
    except:
        pass
    
    # 读取Excel文件的Sheet1
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')
    else:
        df = pd.read_excel(file_path, sheet_name='Sheet1', engine='xlrd')
        
    if df.empty:
        print("文件为空")
        try:
            import Monitor
            Monitor.log_error("文件为空，无法处理")
        except:
            pass
            return pd.DataFrame()
        
    print(f"读取到数据：{len(df)} 行，{len(df.columns)} 列")
    try:
        import Monitor
        Monitor.log_info(f"读取到数据：{len(df)} 行，{len(df.columns)} 列")
    except:
        pass
    
    # 显示前几行的数据概览，确保数据正确加载
    print("数据概览（前3行）：")
    for i in range(min(3, len(df))):
        if i == 0:
            print(f"第{i+1}行（表头）: {list(df.iloc[i])[:5]}...")  # 只显示前5列
        else:
            print(f"第{i+1}行（数据）: {list(df.iloc[i])[:5]}...")  # 只显示前5列
    
    # 执行四个处理步骤
    process1_rows = execute_process1(df)  # H列25C1/25C2/25C3筛选
    process2_rows = execute_process2(df, current_datetime)  # K列日期筛选
    process3_rows = execute_process3(df)  # M列空值且A列非空筛选
    process4_rows = execute_process4(df)  # 作废数据筛选
    
    # 计算最终结果：满足处理1、处理2、处理3，但排除处理4
    final_rows = process1_rows & process2_rows & process3_rows - process4_rows
    
    print(f"调试各步骤 - 处理1符合条件: {len(process1_rows)} 行 {sorted(process1_rows)}")
    print(f"调试各步骤 - 处理2符合条件: {len(process2_rows)} 行 {sorted(process2_rows)}")
    print(f"调试各步骤 - 处理3符合条件: {len(process3_rows)} 行 {sorted(process3_rows)}") 
    print(f"调试各步骤 - 处理4需排除: {len(process4_rows)} 行 {sorted(process4_rows)}")
    print(f"调试各步骤 - 最终完成处理数据: {len(final_rows)} 行 {sorted(final_rows)}")
    
    # 记录到监控器
    try:
        import Monitor
        Monitor.log_info(f"处理1符合条件: {len(process1_rows)} 行")
        Monitor.log_info(f"处理2符合条件: {len(process2_rows)} 行")
        Monitor.log_info(f"处理3符合条件: {len(process3_rows)} 行")
        Monitor.log_info(f"处理4需排除: {len(process4_rows)} 行")
        if len(final_rows) > 0:
            Monitor.log_success(f"最终完成处理数据: {len(final_rows)} 行")
        else:
            Monitor.log_warning("经过四步筛选后，无符合条件的数据")
    except:
        pass
    
    if not final_rows:
        return pd.DataFrame()
    
    # 获取最终结果数据（排除第一行标题行）
    final_indices = [i for i in final_rows if i > 0]  # 排除第一行
    print(f"调试 - final_rows(pandas索引): {sorted(final_rows)}")
    print(f"调试 - final_indices(排除表头后): {sorted(final_indices)}")
    
    result_df = df.iloc[final_indices].copy()
    
    # 添加行号信息 - 修正行号计算以匹配用户期望
    # 用户反馈：筛选出3、5、6行，但程序生成2、4、5行，需要+1修正
    excel_row_numbers = [i + 2 for i in final_indices]  # pandas索引+2 = 用户期望的Excel行号
    print(f"调试 - pandas索引final_indices: {sorted(final_indices)}")
    print(f"调试 - 修正后的Excel行号(+2): {sorted(excel_row_numbers)}")
    
    result_df['原始行号'] = excel_row_numbers
    print(f"调试 - 最终使用的Excel行号: {sorted(excel_row_numbers)}")
    
    return result_df


def execute_process1(df):
    """
    处理1：H列数据筛选，筛选出包含"25C1"、"25C2"、"25C3"的数据
    
    参数:
        df (pandas.DataFrame): 原始数据
    
    返回:
        set: 符合条件的行索引集合
    """
    result_rows = set()
    
    # 记录处理开始
    try:
        import Monitor
        Monitor.log_process("开始执行处理1：筛选H列数据（25C1、25C2、25C3）")
    except:
        pass
    
    # 检查H列是否存在（列索引7，因为从0开始）
    if len(df.columns) <= 7:
        warning_msg = "警告：数据列数不足，无H列"
        print(warning_msg)
        try:
            import Monitor
            Monitor.log_warning(warning_msg)
        except:
            pass
        return result_rows
    
    h_column = df.iloc[:, 7]  # H列是第8列（索引7）
    
    # 搜索包含指定字符串的行
    target_values = ["25C1", "25C2", "25C3"]
    
    for idx, cell_value in h_column.items():
        if idx == 0:  # 跳过第一行标题
            continue
            
        cell_str = str(cell_value) if cell_value is not None else ""
        
        # 添加调试信息，确保处理每一行数据
        if idx <= 5:  # 只显示前5行的调试信息，避免输出过多
            print(f"处理1调试：检查第{idx+1}行H列数据: '{cell_str}'")
        
        for target in target_values:
            if target in cell_str:
                result_rows.add(idx)
                print(f"处理1：第{idx+1}行H列包含'{target}': {cell_str}")
                break
    
    print(f"处理1完成：共找到 {len(result_rows)} 行符合H列筛选条件")
    try:
        import Monitor
        Monitor.log_success(f"处理1完成：共找到 {len(result_rows)} 行符合H列筛选条件")
    except:
        pass
    return result_rows


def execute_process2(df, current_datetime):
    """
    处理2：K列日期筛选逻辑
    根据当前日期决定筛选范围：
    - 如果今天是1-20号：筛选同年同月数据
    - 如果今天是21-31号：筛选同年同月及次月数据
    
    参数:
        df (pandas.DataFrame): 原始数据
        current_datetime (datetime): 当前日期时间
    
    返回:
        set: 符合条件的行索引集合
    """
    result_rows = set()
    
    # 记录处理开始
    try:
        import Monitor
        Monitor.log_process("开始执行处理2：筛选K列日期数据")
    except:
        pass
    
    # 检查K列是否存在（列索引10，因为从0开始）
    if len(df.columns) <= 10:
        warning_msg = "警告：数据列数不足，无K列"
        print(warning_msg)
        try:
            import Monitor
            Monitor.log_warning(warning_msg)
        except:
            pass
        return result_rows
    
    k_column = df.iloc[:, 10]  # K列是第11列（索引10）
    
    # 获取当前日期信息
    current_day = current_datetime.day
    current_year = current_datetime.year
    current_month = current_datetime.month
    
    print(f"当前日期：{current_datetime.strftime('%Y-%m-%d')}，今天是{current_day}号")
    
    # 确定筛选日期范围
    if current_day <= 20:
        # 1-20号：筛选同年同月数据
        start_date = datetime.datetime(current_year, current_month, 1)
        # 获取当月最后一天
        if current_month == 12:
            end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)
        print(f"当日为{current_day}号，筛选范围：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    else:
        # 21-31号：筛选同年同月及次月数据
        start_date = datetime.datetime(current_year, current_month, 1)
        # 获取次月最后一天
        if current_month == 12:
            end_date = datetime.datetime(current_year + 1, 2, 1) - datetime.timedelta(days=1)
        elif current_month == 11:
            end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(current_year, current_month + 2, 1) - datetime.timedelta(days=1)
        print(f"当日为{current_day}号，筛选范围：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    # 遍历K列数据进行筛选
    for idx, cell_value in k_column.items():
        if idx == 0:  # 跳过第一行标题
            continue
        
        if pd.isna(cell_value):
            if idx <= 5:  # 调试信息
                print(f"处理2调试：第{idx+1}行K列数据为空，跳过")
            continue
        
        # 添加调试信息
        if idx <= 5:
            print(f"处理2调试：检查第{idx+1}行K列数据: '{cell_value}'")
        
        try:
            # 尝试解析日期，支持多种格式
            if isinstance(cell_value, str):
                # 尝试多种日期格式
                date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']
                cell_date = None
                
                for fmt in date_formats:
                    try:
                        cell_date = pd.to_datetime(cell_value, format=fmt, errors='raise')
                        break
                    except:
                        continue
                
                # 如果固定格式都失败，使用智能解析
                if cell_date is None or pd.isna(cell_date):
                    cell_date = pd.to_datetime(cell_value, errors='coerce')
            else:
                cell_date = pd.to_datetime(cell_value, errors='coerce')
            
            if pd.isna(cell_date):
                continue
            
            # 检查日期是否在筛选范围内
            if start_date <= cell_date <= end_date:
                result_rows.add(idx)
                print(f"处理2：第{idx+1}行K列日期符合条件: {cell_date.strftime('%Y-%m-%d')}")
                
        except Exception as e:
            print(f"处理2：第{idx+1}行K列日期解析失败: {cell_value}, 错误: {e}")
            continue
    
    print(f"处理2完成：共找到 {len(result_rows)} 行符合K列日期筛选条件")
    try:
        import Monitor
        Monitor.log_success(f"处理2完成：共找到 {len(result_rows)} 行符合K列日期筛选条件")
    except:
        pass
    return result_rows


def execute_process3(df):
    """
    处理3：M列空值且A列非空筛选
    筛选M列为空值，同时A列不为空值的数据
    
    参数:
        df (pandas.DataFrame): 原始数据
    
    返回:
        set: 符合条件的行索引集合
    """
    result_rows = set()
    
    # 记录处理开始
    try:
        import Monitor
        Monitor.log_process("开始执行处理3：筛选M列空值且A列非空数据")
    except:
        pass
    
    # 检查A列和M列是否存在
    if len(df.columns) <= 0:
        warning_msg = "警告：数据列数不足，无A列"
        print(warning_msg)
        try:
            import Monitor
            Monitor.log_warning(warning_msg)
        except:
            pass
        return result_rows
    
    if len(df.columns) <= 12:
        warning_msg = "警告：数据列数不足，无M列"
        print(warning_msg)
        try:
            import Monitor
            Monitor.log_warning(warning_msg)
        except:
            pass
        return result_rows
    
    a_column = df.iloc[:, 0]   # A列是第1列（索引0）
    m_column = df.iloc[:, 12]  # M列是第13列（索引12）
    
    # 遍历数据进行筛选
    for idx in range(len(df)):
        if idx == 0:  # 跳过第一行标题
            continue
            
        a_value = a_column.iloc[idx]
        m_value = m_column.iloc[idx]
        
        # 添加调试信息
        if idx <= 5:
            print(f"处理3调试：检查第{idx+1}行 - A列: '{a_value}', M列: '{m_value}'")
        
        # 检查A列不为空且M列为空
        a_not_empty = not (pd.isna(a_value) or str(a_value).strip() == "")
        m_is_empty = pd.isna(m_value) or str(m_value).strip() == ""
        
        if a_not_empty and m_is_empty:
            result_rows.add(idx)
            print(f"处理3：第{idx+1}行符合条件 - A列: '{a_value}', M列: 空值")
    
    print(f"处理3完成：共找到 {len(result_rows)} 行符合M列空值且A列非空条件")
    try:
        import Monitor
        Monitor.log_success(f"处理3完成：共找到 {len(result_rows)} 行符合M列空值且A列非空条件")
    except:
        pass
    return result_rows


def execute_process4(df):
    """
    处理4：筛选"作废"数据
    仅检查B列中是否包含"作废"标记
    
    参数:
        df (pandas.DataFrame): 原始数据
    
    返回:
        set: 符合条件的行索引集合（需要排除的行）
    """
    result_rows = set()
    
    # 记录处理开始
    try:
        import Monitor
        Monitor.log_process("开始执行处理4：筛选B列作废数据")
    except:
        pass
    
    # 检查B列是否存在（列索引1，因为从0开始）
    if len(df.columns) <= 1:
        warning_msg = "警告：数据列数不足，无B列"
        print(warning_msg)
        try:
            import Monitor
            Monitor.log_warning(warning_msg)
        except:
            pass
        return result_rows
    
    # 仅检查B列查找"作废"标记
    b_column = df.iloc[:, 1]  # B列是第2列（索引1）
    
    for idx, cell_value in b_column.items():
        if idx == 0:  # 跳过第一行标题
            continue
            
        cell_str = str(cell_value) if cell_value is not None else ""
        
        # 添加调试信息
        if idx <= 5:
            print(f"处理4调试：检查第{idx+1}行B列数据: '{cell_str}'")
        
        if "作废" in cell_str:
            result_rows.add(idx)
            print(f"处理4：第{idx+1}行B列包含'作废': {cell_str}")
    
    print(f"处理4完成：共找到 {len(result_rows)} 行B列包含作废标记（需要排除）")
    try:
        import Monitor
        if len(result_rows) > 0:
            Monitor.log_warning(f"处理4完成：共找到 {len(result_rows)} 行B列包含作废标记（需要排除）")
        else:
            Monitor.log_success("处理4完成：未发现作废数据")
    except:
        pass
    return result_rows


def export_result_to_excel(df, original_file_path, current_datetime, output_dir):
    """
    导出完成处理数据到Excel文件
    复制原文件，重命名，在新文件中新建sheet3并写入符合条件的完整数据
    
    参数:
        df (pandas.DataFrame): 完成处理数据（包含原始行号）
        original_file_path (str): 原始文件路径  
        current_datetime (datetime): 当前日期时间
        output_dir (str): 输出目录
    
    返回:
        str: 导出文件路径
    """
    import shutil
    from openpyxl import load_workbook
    
    try:
        # 生成输出文件名，处理重名文件
        date_str = current_datetime.strftime('%Y-%m-%d')
        base_filename = f"应打开接口{date_str}"
        output_filename = f"{base_filename}.xlsx"
        output_path = os.path.join(output_dir, output_filename)
        
        # 处理重名文件，自动加序号
        counter = 1
        while os.path.exists(output_path):
            output_filename = f"{base_filename}({counter}).xlsx"
            output_path = os.path.join(output_dir, output_filename)
            counter += 1
        
        # 第一步：复制原文件到新位置
        shutil.copy2(original_file_path, output_path)
        print(f"已复制原文件到: {output_path}")
        
        # 第二步：使用openpyxl读取原始文件（保持格式）
        original_wb = load_workbook(original_file_path)
        original_ws = original_wb['Sheet1']
        
        # 第三步：读取数据用于处理
        if original_file_path.endswith('.xlsx'):
            original_df = pd.read_excel(original_file_path, sheet_name='Sheet1', engine='openpyxl', header=None)
        else:
            original_df = pd.read_excel(original_file_path, sheet_name='Sheet1', engine='xlrd', header=None)
        
        # 第四步：使用openpyxl在复制的文件中新建sheet3
        wb = load_workbook(output_path)
        
        # 创建新的工作表"应打开接口"
        if "应打开接口" in wb.sheetnames:
            del wb["应打开接口"]
        
        ws = wb.create_sheet("应打开接口")
        
        # 第五步：复制表头（原文件第一行，包括格式）
        if original_ws.max_row > 0:
            # 确保从A列开始复制所有列，使用更大的范围以防遗漏
            max_col = max(original_ws.max_column, len(original_df.columns))
            print(f"导出表头：从第1列到第{max_col}列")
            # 复制第一行的所有单元格（包括格式）
            for col_idx in range(1, max_col + 1):
                source_cell = original_ws.cell(row=1, column=col_idx)
                target_cell = ws.cell(row=1, column=col_idx)
                
                # 复制值
                target_cell.value = source_cell.value
                
                # 复制格式（使用copy避免StyleProxy错误）
                try:
                    if source_cell.font:
                        target_cell.font = copy(source_cell.font)
                    if source_cell.fill:
                        target_cell.fill = copy(source_cell.fill)
                    if source_cell.border:
                        target_cell.border = copy(source_cell.border)
                    if source_cell.alignment:
                        target_cell.alignment = copy(source_cell.alignment)
                    if source_cell.number_format:
                        target_cell.number_format = source_cell.number_format
                except Exception as style_error:
                    # 如果样式复制失败，仅复制值
                    print(f"样式复制失败，仅复制值: {style_error}")
            
            print("已复制表头（包括格式）到Sheet '应打开接口'")
        
        # 第六步：写入符合条件的数据行
        if not df.empty and '原始行号' in df.columns:
            qualified_rows = df['原始行号'].tolist()
            print(f"调试导出 - 准备导出 {len(qualified_rows)} 行符合条件的数据")
            print(f"调试导出 - 原始行号列表: {sorted(qualified_rows)}")
            print(f"调试导出 - 原始文件行数: {len(original_df)}")
            
            write_row = 2  # 从第二行开始写入数据
            exported_count = 0
            
            for excel_row_num in sorted(qualified_rows):
                # 确保行号在有效范围内（Excel行号从1开始，第1行是表头，数据从第2行开始）
                print(f"调试导出 - 检查Excel第{excel_row_num}行，有效范围：2到{len(original_df)}")
                if excel_row_num > 1 and excel_row_num <= len(original_df):
                    print(f"调试导出 - ✓ 导出第{excel_row_num}行数据到新文件第{write_row}行")
                    # 复制整行数据，使用与表头相同的列范围
                    max_col = max(original_ws.max_column, len(original_df.columns))
                    for col_idx in range(1, max_col + 1):
                        source_cell = original_ws.cell(row=excel_row_num, column=col_idx)
                        target_cell = ws.cell(row=write_row, column=col_idx)
                        
                        # 复制值
                        target_cell.value = source_cell.value
                        
                        # 复制格式（使用copy避免StyleProxy错误）
                        try:
                            if source_cell.font:
                                target_cell.font = copy(source_cell.font)
                            if source_cell.fill:
                                target_cell.fill = copy(source_cell.fill)
                            if source_cell.border:
                                target_cell.border = copy(source_cell.border)
                            if source_cell.alignment:
                                target_cell.alignment = copy(source_cell.alignment)
                            if source_cell.number_format:
                                target_cell.number_format = source_cell.number_format
                        except Exception as style_error:
                            # 如果样式复制失败，仅复制值
                            print(f"数据行样式复制失败，仅复制值: {style_error}")
                    
                    write_row += 1
                    exported_count += 1
                else:
                    print(f"调试导出 - ✗ 跳过Excel第{excel_row_num}行（超出范围或是表头）")
            
            print(f"调试导出 - 实际导出了 {exported_count} 行数据")
            print(f"调试导出 - 已写入 {write_row - 2} 行数据到Sheet '应打开接口'")
        else:
            print("没有符合条件的数据行需要导出")
        
        # 保存文件
        original_wb.close()
        wb.save(output_path)
        wb.close()
        
        print(f"导出完成！文件保存到: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"导出数据时发生错误: {str(e)}")
        raise


# ===================== 待处理文件2（需回复接口）相关处理 =====================
def process_target_file2(file_path, current_datetime):
    """
    处理待处理文件2（需回复接口）的主函数
    返回：pandas.DataFrame，包含原始行号
    """
    print(f"开始处理待处理文件2: {os.path.basename(file_path)}")
    try:
        import Monitor
        Monitor.log_process(f"开始处理待处理文件2: {os.path.basename(file_path)}")
    except:
        pass

    # 读取Excel文件的Sheet1
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')
    else:
        df = pd.read_excel(file_path, sheet_name='Sheet1', engine='xlrd')

    if df.empty:
        print("文件为空")
        try:
            import Monitor
            Monitor.log_error("文件为空，无法处理")
        except:
            pass
        return pd.DataFrame()

    # 处理1
    process1_rows = execute2_process1(df)
    # 处理2
    process2_rows = execute2_process2(df, current_datetime)
    # 处理3
    process3_rows = execute2_process3(df)
    # 处理4
    process4_rows = execute2_process4(df)

    # 结果：满足1、2、4，排除3
    final_rows = process1_rows & process2_rows & process4_rows - process3_rows

    # 日志
    try:
        import Monitor
        Monitor.log_info(f"处理1符合条件: {len(process1_rows)} 行")
        Monitor.log_info(f"处理2符合条件: {len(process2_rows)} 行")
        Monitor.log_info(f"处理3需排除: {len(process3_rows)} 行")
        Monitor.log_info(f"处理4符合条件: {len(process4_rows)} 行")
        if len(final_rows) > 0:
            Monitor.log_success(f"最终完成处理数据: {len(final_rows)} 行")
        else:
            Monitor.log_warning("经过四步筛选后，无符合条件的数据")
    except:
        pass

    if not final_rows:
        return pd.DataFrame()

    final_indices = [i for i in final_rows if i > 0]
    excel_row_numbers = [i + 2 for i in final_indices]  # pandas索引+2=Excel行号
    result_df = df.iloc[final_indices].copy()
    result_df['原始行号'] = excel_row_numbers
    return result_df

def execute2_process1(df):
    """I列包含“河北分公司-建筑结构所”"""
    result_rows = set()
    if len(df.columns) <= 8:
        return result_rows
    i_column = df.iloc[:, 8]
    for idx, val in i_column.items():
        if idx == 0:
            continue
        if "河北分公司-建筑结构所" in str(val):
            result_rows.add(idx)
    return result_rows

def execute2_process2(df, current_datetime):
    """M列日期筛选，逻辑同文件1的K列"""
    result_rows = set()
    if len(df.columns) <= 12:
        return result_rows
    m_column = df.iloc[:, 12]
    current_day = current_datetime.day
    current_year = current_datetime.year
    current_month = current_datetime.month
    if current_day <= 20:
        start_date = datetime.datetime(current_year, current_month, 1)
        if current_month == 12:
            end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)
    else:
        start_date = datetime.datetime(current_year, current_month, 1)
        if current_month == 12:
            end_date = datetime.datetime(current_year + 1, 2, 1) - datetime.timedelta(days=1)
        elif current_month == 11:
            end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.datetime(current_year, current_month + 2, 1) - datetime.timedelta(days=1)
    for idx, val in m_column.items():
        if idx == 0:
            continue
        cell_date = None
        try:
            if isinstance(val, str):
                for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S']:
                    try:
                        cell_date = pd.to_datetime(val, format=fmt, errors='raise')
                        break
                    except:
                        continue
                if cell_date is None or pd.isna(cell_date):
                    cell_date = pd.to_datetime(val, errors='coerce')
            else:
                cell_date = pd.to_datetime(val, errors='coerce')
            if pd.isna(cell_date):
                continue
            if start_date <= cell_date <= end_date:
                result_rows.add(idx)
        except:
            continue
    return result_rows

def execute2_process3(df):
    """AB列以4444开头，且F列为“传递”"""
    result_rows = set()
    if len(df.columns) <= 27 or len(df.columns) <= 5:
        return result_rows
    ab_column = df.iloc[:, 27]
    f_column = df.iloc[:, 5]
    for idx in range(len(df)):
        if idx == 0:
            continue
        ab_val = ab_column.iloc[idx]
        f_val = f_column.iloc[idx]
        if str(ab_val).startswith("4444") and str(f_val) == "传递":
            result_rows.add(idx)
    return result_rows

def execute2_process4(df):
    """N列为空且A列不为空"""
    result_rows = set()
    if len(df.columns) <= 13 or len(df.columns) <= 0:
        return result_rows
    n_column = df.iloc[:, 13]
    a_column = df.iloc[:, 0]
    for idx in range(len(df)):
        if idx == 0:
            continue
        n_val = n_column.iloc[idx]
        a_val = a_column.iloc[idx]
        a_not_empty = not (pd.isna(a_val) or str(a_val).strip() == "")
        n_is_empty = pd.isna(n_val) or str(n_val).strip() == ""
        if a_not_empty and n_is_empty:
            result_rows.add(idx)
    return result_rows

def export_result_to_excel2(df, original_file_path, current_datetime, output_dir):
    """
    导出需回复接口处理结果到Excel文件
    复制原文件，重命名，在新文件中新建sheet2并写入符合条件的完整数据
    """
    import shutil
    from openpyxl import load_workbook
    try:
        date_str = current_datetime.strftime('%Y-%m-%d')
        base_filename = f"需打开接口{date_str}"
        output_filename = f"{base_filename}.xlsx"
        output_path = os.path.join(output_dir, output_filename)
        counter = 1
        while os.path.exists(output_path):
            output_filename = f"{base_filename}({counter}).xlsx"
            output_path = os.path.join(output_dir, output_filename)
            counter += 1
        shutil.copy2(original_file_path, output_path)
        print(f"已复制原文件到: {output_path}")
        original_wb = load_workbook(original_file_path)
        original_ws = original_wb['Sheet1']
        if original_file_path.endswith('.xlsx'):
            original_df = pd.read_excel(original_file_path, sheet_name='Sheet1', engine='openpyxl', header=None)
        else:
            original_df = pd.read_excel(original_file_path, sheet_name='Sheet1', engine='xlrd', header=None)
        wb = load_workbook(output_path)
        if "需打开接口" in wb.sheetnames:
            del wb["需打开接口"]
        ws = wb.create_sheet("需打开接口")
        # 复制表头
        if original_ws.max_row > 0:
            max_col = max(original_ws.max_column, len(original_df.columns))
            for col_idx in range(1, max_col + 1):
                source_cell = original_ws.cell(row=1, column=col_idx)
                target_cell = ws.cell(row=1, column=col_idx)
                target_cell.value = source_cell.value
                try:
                    if source_cell.font:
                        target_cell.font = copy(source_cell.font)
                    if source_cell.fill:
                        target_cell.fill = copy(source_cell.fill)
                    if source_cell.border:
                        target_cell.border = copy(source_cell.border)
                    if source_cell.alignment:
                        target_cell.alignment = copy(source_cell.alignment)
                    if source_cell.number_format:
                        target_cell.number_format = source_cell.number_format
                except Exception as style_error:
                    print(f"样式复制失败，仅复制值: {style_error}")
        # 写入数据行
        if not df.empty and '原始行号' in df.columns:
            qualified_rows = df['原始行号'].tolist()
            write_row = 2
            for excel_row_num in sorted(qualified_rows):
                if excel_row_num > 1 and excel_row_num <= len(original_df):
                    max_col = max(original_ws.max_column, len(original_df.columns))
                    for col_idx in range(1, max_col + 1):
                        source_cell = original_ws.cell(row=excel_row_num, column=col_idx)
                        target_cell = ws.cell(row=write_row, column=col_idx)
                        target_cell.value = source_cell.value
                        try:
                            if source_cell.font:
                                target_cell.font = copy(source_cell.font)
                            if source_cell.fill:
                                target_cell.fill = copy(source_cell.fill)
                            if source_cell.border:
                                target_cell.border = copy(source_cell.border)
                            if source_cell.alignment:
                                target_cell.alignment = copy(source_cell.alignment)
                            if source_cell.number_format:
                                target_cell.number_format = source_cell.number_format
                        except Exception as style_error:
                            print(f"数据行样式复制失败，仅复制值: {style_error}")
                    write_row += 1
        original_wb.close()
        wb.save(output_path)
        wb.close()
        print(f"导出完成！文件保存到: {output_path}")
        return output_path
    except Exception as e:
        print(f"导出数据时发生错误: {str(e)}")
        raise


# ===================== 待处理文件3（外部接口ICM）相关处理 =====================
def process_target_file3(file_path, current_datetime):
    """
    处理待处理文件3（外部接口ICM）的主函数
    
    参数:
        file_path (str): 待处理文件3的路径
        current_datetime (datetime): 当前日期时间
    
    返回:
        pandas.DataFrame: 完成处理数据，包含原始行号
    """
    print(f"开始处理待处理文件3: {os.path.basename(file_path)}")
    try:
        import Monitor
        Monitor.log_process(f"开始处理待处理文件3: {os.path.basename(file_path)}")
    except:
        pass
    
    # 读取Excel文件的Sheet1
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')
    else:
        df = pd.read_excel(file_path, sheet_name='Sheet1', engine='xlrd')
        
    if df.empty:
        print("文件为空")
        try:
            import Monitor
            Monitor.log_error("文件为空，无法处理")
        except:
            pass
        return pd.DataFrame()
        
    print(f"读取到数据：{len(df)} 行，{len(df.columns)} 列")
    try:
        import Monitor
        Monitor.log_info(f"读取到数据：{len(df)} 行，{len(df.columns)} 列")
    except:
        pass
    
    # 执行六个处理步骤
    process1_rows = execute3_process1(df)  # I列为"B"的数据
    process2_rows = execute3_process2(df)  # AL列以"河北分公司-建筑结构所"开头的数据
    process3_rows = execute3_process3(df, current_datetime)  # M列时间数据筛选
    process4_rows = execute3_process4(df, current_datetime)  # L列时间数据筛选
    process5_rows = execute3_process5(df)  # Q列为空值的数据
    process6_rows = execute3_process6(df)  # T列为空值的数据
    
    # 最终汇总逻辑：
    # (处理1 AND 处理2 AND 处理3 AND NOT 处理6) OR (处理1 AND 处理2 AND 处理4 AND NOT 处理5)
    group1 = process1_rows & process2_rows & process3_rows - process6_rows
    group2 = process1_rows & process2_rows & process4_rows - process5_rows
    final_rows = group1 | group2  # 并集关系
    
    # 日志记录
    try:
        import Monitor
        Monitor.log_info(f"处理1(I列为B): {len(process1_rows)} 行")
        Monitor.log_info(f"处理2(AL列河北分公司-建筑结构所开头): {len(process2_rows)} 行")
        Monitor.log_info(f"处理3(M列时间筛选): {len(process3_rows)} 行")
        Monitor.log_info(f"处理4(L列时间筛选): {len(process4_rows)} 行")
        Monitor.log_info(f"处理5(Q列为空): {len(process5_rows)} 行")
        Monitor.log_info(f"处理6(T列为空): {len(process6_rows)} 行")
        Monitor.log_info(f"组1(1&2&3-6): {len(group1)} 行")
        Monitor.log_info(f"组2(1&2&4-5): {len(group2)} 行")
        if len(final_rows) > 0:
            Monitor.log_success(f"最终完成处理数据: {len(final_rows)} 行")
        else:
            Monitor.log_warning("经过筛选后，无符合条件的数据")
    except:
        pass
    
    if not final_rows:
        return pd.DataFrame()
    
    # 转换为最终结果DataFrame
    final_indices = [i for i in final_rows if i >= 0]
    excel_row_numbers = [i + 2 for i in final_indices]  # pandas索引+2=Excel行号
    result_df = df.iloc[final_indices].copy()
    result_df['原始行号'] = excel_row_numbers
    return result_df


def execute3_process1(df):
    """
    处理1：读取待处理文件3中的I列的数据，筛选这一列中为"B"的数据
    
    参数:
        df (pandas.DataFrame): 输入数据
    
    返回:
        set: 符合条件的行索引集合
    """
    print("执行处理1：筛选I列为'B'的数据")
    try:
        import Monitor
        Monitor.log_process("处理1：筛选I列为'B'的数据")
    except:
        pass
    
    qualified_rows = set()
    
    if len(df.columns) <= 8:  # I列索引为8
        print("警告：文件列数不足，无法访问I列")
        try:
            import Monitor
            Monitor.log_warning("文件列数不足，无法访问I列")
        except:
            pass
        return qualified_rows
    
    try:
        # I列索引为8（从0开始）
        i_column = df.iloc[:, 8]
        
        for index, value in enumerate(i_column):
            if pd.notna(value) and str(value).strip() == "B":
                qualified_rows.add(index)
        
        print(f"处理1完成：找到 {len(qualified_rows)} 行符合条件")
        try:
            import Monitor
            Monitor.log_info(f"处理1完成：找到 {len(qualified_rows)} 行符合条件")
        except:
            pass
            
    except Exception as e:
        print(f"处理1执行出错: {e}")
        try:
            import Monitor
            Monitor.log_error(f"处理1执行出错: {e}")
        except:
            pass
    
    return qualified_rows


def execute3_process2(df):
    """
    处理2：读取待处理文件3中AL列的数据，筛选这一列中以"河北分公司-建筑结构所"开头的数据
    
    参数:
        df (pandas.DataFrame): 输入数据
    
    返回:
        set: 符合条件的行索引集合
    """
    print("执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据")
    try:
        import Monitor
        Monitor.log_process("处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据")
    except:
        pass
    
    qualified_rows = set()
    
    if len(df.columns) <= 37:  # AL列索引为37
        print("警告：文件列数不足，无法访问AL列")
        try:
            import Monitor
            Monitor.log_warning("文件列数不足，无法访问AL列")
        except:
            pass
        return qualified_rows
    
    try:
        # AL列索引为37（从0开始）
        al_column = df.iloc[:, 37]
        target_prefix = "河北分公司-建筑结构所"
        
        for index, value in enumerate(al_column):
            if pd.notna(value) and str(value).strip().startswith(target_prefix):
                qualified_rows.add(index)
        
        print(f"处理2完成：找到 {len(qualified_rows)} 行符合条件")
        try:
            import Monitor
            Monitor.log_info(f"处理2完成：找到 {len(qualified_rows)} 行符合条件")
        except:
            pass
            
    except Exception as e:
        print(f"处理2执行出错: {e}")
        try:
            import Monitor
            Monitor.log_error(f"处理2执行出错: {e}")
        except:
            pass
    
    return qualified_rows


def execute3_process3(df, current_datetime):
    """
    处理3：读取处理文件3中M列的数据，根据当前日期进行时间筛选
    
    参数:
        df (pandas.DataFrame): 输入数据
        current_datetime (datetime): 当前日期时间
    
    返回:
        set: 符合条件的行索引集合
    """
    print("执行处理3：筛选M列时间数据")
    try:
        import Monitor
        Monitor.log_process("处理3：筛选M列时间数据")
    except:
        pass
    
    qualified_rows = set()
    
    if len(df.columns) <= 12:  # M列索引为12
        print("警告：文件列数不足，无法访问M列")
        try:
            import Monitor
            Monitor.log_warning("文件列数不足，无法访问M列")
        except:
            pass
        return qualified_rows
    
    try:
        # M列索引为12（从0开始）
        m_column = df.iloc[:, 12]
        current_day = current_datetime.day
        current_year = current_datetime.year
        current_month = current_datetime.month
        
        # 确定筛选的日期范围
        if 1 <= current_day <= 20:
            # 当前月的数据
            start_date = datetime.datetime(current_year, current_month, 1)
            if current_month == 12:
                end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)
        else:
            # 当前月和下个月的数据
            start_date = datetime.datetime(current_year, current_month, 1)
            if current_month == 11:
                end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
            elif current_month == 12:
                end_date = datetime.datetime(current_year + 1, 2, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.datetime(current_year, current_month + 2, 1) - datetime.timedelta(days=1)
        
        print(f"筛选日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
        
        for index, value in enumerate(m_column):
            if pd.notna(value):
                try:
                    # 尝试解析日期，支持多种格式
                    date_value = None
                    value_str = str(value).strip()
                    
                    # 尝试不同的日期格式
                    date_formats = [
                        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
                        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            date_value = datetime.datetime.strptime(value_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    # 如果是pandas的Timestamp对象
                    if date_value is None and hasattr(value, 'year'):
                        date_value = datetime.datetime(value.year, value.month, value.day)
                    
                    if date_value and start_date <= date_value <= end_date:
                        qualified_rows.add(index)
                        
                except Exception as parse_error:
                    print(f"日期解析失败（第{index+1}行）: {value} - {parse_error}")
                    continue
        
        print(f"处理3完成：找到 {len(qualified_rows)} 行符合条件")
        try:
            import Monitor
            Monitor.log_info(f"处理3完成：找到 {len(qualified_rows)} 行符合条件")
        except:
            pass
            
    except Exception as e:
        print(f"处理3执行出错: {e}")
        try:
            import Monitor
            Monitor.log_error(f"处理3执行出错: {e}")
        except:
            pass
    
    return qualified_rows


def execute3_process4(df, current_datetime):
    """
    处理4：读取处理文件3中L列的数据，进行时间筛选（包括4444开头的特殊处理）
    
    参数:
        df (pandas.DataFrame): 输入数据
        current_datetime (datetime): 当前日期时间
    
    返回:
        set: 符合条件的行索引集合
    """
    print("执行处理4：筛选L列时间数据（包括4444开头特殊处理）")
    try:
        import Monitor
        Monitor.log_process("处理4：筛选L列时间数据（包括4444开头特殊处理）")
    except:
        pass
    
    qualified_rows = set()
    
    if len(df.columns) <= 11:  # L列索引为11
        print("警告：文件列数不足，无法访问L列")
        try:
            import Monitor
            Monitor.log_warning("文件列数不足，无法访问L列")
        except:
            pass
        return qualified_rows
    
    try:
        # L列索引为11（从0开始）
        l_column = df.iloc[:, 11]
        current_day = current_datetime.day
        current_year = current_datetime.year
        current_month = current_datetime.month
        
        # 确定筛选的日期范围（与处理3相同的逻辑）
        if 1 <= current_day <= 20:
            start_date = datetime.datetime(current_year, current_month, 1)
            if current_month == 12:
                end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)
        else:
            start_date = datetime.datetime(current_year, current_month, 1)
            if current_month == 11:
                end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
            elif current_month == 12:
                end_date = datetime.datetime(current_year + 1, 2, 1) - datetime.timedelta(days=1)
            else:
                end_date = datetime.datetime(current_year, current_month + 2, 1) - datetime.timedelta(days=1)
        
        print(f"筛选日期范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
        
        for index, value in enumerate(l_column):
            if pd.notna(value):
                try:
                    value_str = str(value).strip()
                    date_value = None
                    
                    # 特殊处理：4444开头的数据当做当年处理
                    if value_str.startswith('4444'):
                        # 将4444替换为当前年份
                        modified_value_str = value_str.replace('4444', str(current_year), 1)
                        print(f"4444开头数据转换: {value_str} -> {modified_value_str}")
                        value_str = modified_value_str
                    
                    # 尝试不同的日期格式
                    date_formats = [
                        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
                        '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            date_value = datetime.datetime.strptime(value_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    # 如果是pandas的Timestamp对象
                    if date_value is None and hasattr(value, 'year'):
                        date_value = datetime.datetime(value.year, value.month, value.day)
                    
                    if date_value and start_date <= date_value <= end_date:
                        qualified_rows.add(index)
                        
                except Exception as parse_error:
                    print(f"日期解析失败（第{index+1}行）: {value} - {parse_error}")
                    continue
        
        print(f"处理4完成：找到 {len(qualified_rows)} 行符合条件")
        try:
            import Monitor
            Monitor.log_info(f"处理4完成：找到 {len(qualified_rows)} 行符合条件")
        except:
            pass
            
    except Exception as e:
        print(f"处理4执行出错: {e}")
        try:
            import Monitor
            Monitor.log_error(f"处理4执行出错: {e}")
        except:
            pass
    
    return qualified_rows


def execute3_process5(df):
    """
    处理5：读取待处理文件3中Q列的数据，筛选这一列中为空值的数据
    
    参数:
        df (pandas.DataFrame): 输入数据
    
    返回:
        set: 符合条件的行索引集合
    """
    print("执行处理5：筛选Q列为空值的数据")
    try:
        import Monitor
        Monitor.log_process("处理5：筛选Q列为空值的数据")
    except:
        pass
    
    qualified_rows = set()
    
    if len(df.columns) <= 16:  # Q列索引为16
        print("警告：文件列数不足，无法访问Q列")
        try:
            import Monitor
            Monitor.log_warning("文件列数不足，无法访问Q列")
        except:
            pass
        return qualified_rows
    
    try:
        # Q列索引为16（从0开始）
        q_column = df.iloc[:, 16]
        
        for index, value in enumerate(q_column):
            if pd.isna(value) or str(value).strip() == '':
                qualified_rows.add(index)
        
        print(f"处理5完成：找到 {len(qualified_rows)} 行符合条件")
        try:
            import Monitor
            Monitor.log_info(f"处理5完成：找到 {len(qualified_rows)} 行符合条件")
        except:
            pass
            
    except Exception as e:
        print(f"处理5执行出错: {e}")
        try:
            import Monitor
            Monitor.log_error(f"处理5执行出错: {e}")
        except:
            pass
    
    return qualified_rows


def execute3_process6(df):
    """
    处理6：读取待处理文件3中T列的数据，筛选这一列中为空值的数据
    
    参数:
        df (pandas.DataFrame): 输入数据
    
    返回:
        set: 符合条件的行索引集合
    """
    print("执行处理6：筛选T列为空值的数据")
    try:
        import Monitor
        Monitor.log_process("处理6：筛选T列为空值的数据")
    except:
        pass
    
    qualified_rows = set()
    
    if len(df.columns) <= 19:  # T列索引为19
        print("警告：文件列数不足，无法访问T列")
        try:
            import Monitor
            Monitor.log_warning("文件列数不足，无法访问T列")
        except:
            pass
        return qualified_rows
    
    try:
        # T列索引为19（从0开始）
        t_column = df.iloc[:, 19]
        
        for index, value in enumerate(t_column):
            if pd.isna(value) or str(value).strip() == '':
                qualified_rows.add(index)
        
        print(f"处理6完成：找到 {len(qualified_rows)} 行符合条件")
        try:
            import Monitor
            Monitor.log_info(f"处理6完成：找到 {len(qualified_rows)} 行符合条件")
        except:
            pass
            
    except Exception as e:
        print(f"处理6执行出错: {e}")
        try:
            import Monitor
            Monitor.log_error(f"处理6执行出错: {e}")
        except:
            pass
    
    return qualified_rows


def export_result_to_excel3(df, original_file_path, current_datetime, output_dir):
    """
    导出外部接口ICM处理结果到Excel文件
    复制原文件，重命名，在新文件中新建sheet并写入符合条件的完整数据
    """
    import shutil
    from openpyxl import load_workbook
    from copy import copy
    
    try:
        # 生成输出文件名
        date_str = current_datetime.strftime('%Y-%m-%d')
        base_filename = f"外部接口ICM{date_str}"
        output_filename = f"{base_filename}.xlsx"
        output_path = os.path.join(output_dir, output_filename)
        
        # 处理文件名冲突
        counter = 1
        while os.path.exists(output_path):
            output_filename = f"{base_filename}({counter}).xlsx"
            output_path = os.path.join(output_dir, output_filename)
            counter += 1
        
        # 复制原文件
        shutil.copy2(original_file_path, output_path)
        print(f"已复制原文件到: {output_path}")
        
        # 加载原始工作簿和工作表
        original_wb = load_workbook(original_file_path)
        original_ws = original_wb['Sheet1']
        
        # 读取原始数据（不含表头）
        if original_file_path.endswith('.xlsx'):
            original_df = pd.read_excel(original_file_path, sheet_name='Sheet1', engine='openpyxl', header=None)
        else:
            original_df = pd.read_excel(original_file_path, sheet_name='Sheet1', engine='xlrd', header=None)
        
        # 打开目标工作簿
        wb = load_workbook(output_path)
        
        # 删除现有的外部接口ICM工作表（如果存在）
        if "外部接口ICM" in wb.sheetnames:
            del wb["外部接口ICM"]
        
        # 创建新的外部接口ICM工作表
        ws = wb.create_sheet("外部接口ICM")
        
        # 复制表头（第一行）
        if original_ws.max_row > 0:
            max_col = max(original_ws.max_column, len(original_df.columns))
            for col_idx in range(1, max_col + 1):
                source_cell = original_ws.cell(row=1, column=col_idx)
                target_cell = ws.cell(row=1, column=col_idx)
                target_cell.value = source_cell.value
                
                # 复制样式
                try:
                    if source_cell.font:
                        target_cell.font = copy(source_cell.font)
                    if source_cell.fill:
                        target_cell.fill = copy(source_cell.fill)
                    if source_cell.border:
                        target_cell.border = copy(source_cell.border)
                    if source_cell.alignment:
                        target_cell.alignment = copy(source_cell.alignment)
                    if source_cell.number_format:
                        target_cell.number_format = source_cell.number_format
                except Exception as style_error:
                    print(f"表头样式复制失败，仅复制值: {style_error}")
        
        # 写入符合条件的数据行
        if not df.empty and '原始行号' in df.columns:
            qualified_rows = df['原始行号'].tolist()
            write_row = 2  # 从第二行开始写入数据
            
            for excel_row_num in sorted(qualified_rows):
                # 确保行号有效
                if excel_row_num > 1 and excel_row_num <= len(original_df):
                    max_col = max(original_ws.max_column, len(original_df.columns))
                    
                    # 复制整行数据和样式
                    for col_idx in range(1, max_col + 1):
                        source_cell = original_ws.cell(row=excel_row_num, column=col_idx)
                        target_cell = ws.cell(row=write_row, column=col_idx)
                        target_cell.value = source_cell.value
                        
                        # 复制样式
                        try:
                            if source_cell.font:
                                target_cell.font = copy(source_cell.font)
                            if source_cell.fill:
                                target_cell.fill = copy(source_cell.fill)
                            if source_cell.border:
                                target_cell.border = copy(source_cell.border)
                            if source_cell.alignment:
                                target_cell.alignment = copy(source_cell.alignment)
                            if source_cell.number_format:
                                target_cell.number_format = source_cell.number_format
                        except Exception as style_error:
                            print(f"数据行样式复制失败，仅复制值: {style_error}")
                    
                    write_row += 1
        
        # 关闭原始工作簿
        original_wb.close()
        
        # 保存并关闭目标工作簿
        wb.save(output_path)
        wb.close()
        
        print(f"外部接口ICM导出完成！文件保存到: {output_path}")
        try:
            import Monitor
            Monitor.log_success(f"外部接口ICM导出完成！文件保存到: {output_path}")
        except:
            pass
        
        return output_path
        
    except Exception as e:
        print(f"导出外部接口ICM数据时发生错误: {str(e)}")
        try:
            import Monitor
            Monitor.log_error(f"导出外部接口ICM数据时发生错误: {str(e)}")
        except:
            pass
        raise


if __name__ == "__main__":
    # 如果直接运行此文件，显示提示信息
    print("Excel数据处理模块已加载")
    print("请通过主程序(base.py)来使用此模块")