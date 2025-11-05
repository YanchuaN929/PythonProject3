"""
测试"状态"列独立显示功能
验证：
1. "状态"列独立显示在最左侧
2. 延期数据的状态列显示 ⚠️
3. 复制接口号时不包含 ⚠️ 标记
"""
import sys
import io

# 设置标准输出为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import tkinter as tk
from tkinter import ttk
import pandas as pd
from window import WindowManager
from date_utils import is_date_overdue

def test_status_column():
    """测试状态列的独立显示"""
    root = tk.Tk()
    root.title("状态列测试")
    root.geometry("1200x600")
    
    # 创建WindowManager实例
    wm = WindowManager(root)
    
    # 创建测试数据（包含延期和正常数据）
    test_data = pd.DataFrame({
        "原始行号": [1, 2, 3, 4, 5],
        "项目号": ["2016", "2016", "1907", "1907", "2026"],
        "接口号": [
            "INT-001(设计人员)",
            "INT-002(设计人员)",
            "INT-003(2016接口工程师)",
            "INT-004(设计人员)",
            "INT-005(设计人员)"
        ],
        "接口时间": ["08.15", "10.25", "08.10", "11.05", "09.20"],  # 前3个延期（假设今天是10月28日）
        "角色来源": ["设计人员", "设计人员", "2016接口工程师", "设计人员", "设计人员"]
    })
    
    # 添加"状态"列
    status_values = []
    for idx in range(len(test_data)):
        time_value = test_data.iloc[idx]["接口时间"]
        if is_date_overdue(time_value):
            status_values.append("⚠️")
        else:
            status_values.append("")
    test_data["状态"] = status_values
    
    # 创建显示DataFrame（模拟_create_optimized_display的输出）
    display_df = pd.DataFrame({
        "状态": test_data["状态"],
        "项目号": test_data["项目号"],
        "接口号": test_data["接口号"],
        "是否已完成": ["☐"] * 5,
        "接口时间": test_data["接口时间"]  # 保留用于逻辑判断
    })
    
    # 创建Treeview
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    viewer = ttk.Treeview(frame, selectmode='extended')
    viewer.pack(side="left", fill="both", expand=True)
    
    # 添加滚动条
    scrollbar_y = ttk.Scrollbar(frame, orient="vertical", command=viewer.yview)
    scrollbar_y.pack(side="right", fill="y")
    viewer.configure(yscrollcommand=scrollbar_y.set)
    
    scrollbar_x = ttk.Scrollbar(root, orient="horizontal", command=viewer.xview)
    scrollbar_x.pack(fill="x")
    viewer.configure(xscrollcommand=scrollbar_x.set)
    
    # 配置列（过滤掉接口时间）
    columns = [col for col in display_df.columns if col != "接口时间"]
    viewer["columns"] = columns
    viewer["show"] = "tree headings"
    
    # 配置列宽
    viewer.column("#0", width=60, minwidth=60)
    viewer.heading("#0", text="行号")
    
    column_widths = {
        "状态": 50,
        "项目号": 80,
        "接口号": 250,
        "是否已完成": 100
    }
    
    for col in columns:
        width = column_widths.get(col, 100)
        viewer.heading(col, text=col)
        viewer.column(col, width=width, minwidth=width, anchor='center')
    
    # 配置延期tag
    viewer.tag_configure('overdue', 
                        foreground='#8B0000',
                        font=('', 10, 'bold italic'))
    
    # 插入数据
    for index in range(len(display_df)):
        row = display_df.iloc[index]
        row_number = test_data.iloc[index]["原始行号"]
        
        display_values = []
        for col in columns:
            val = row[col]
            if pd.isna(val):
                display_values.append("")
            else:
                display_values.append(str(val))
        
        # 判断是否延期
        is_overdue = is_date_overdue(str(display_df.iloc[index]["接口时间"]))
        tags = ('overdue',) if is_overdue else ()
        
        viewer.insert("", "end", text=str(row_number), values=display_values, tags=tags)
        
        if is_overdue:
            print(f"[测试] 行{row_number}: 延期数据, 状态={row['状态']}, 接口号={row['接口号']}")
    
    # 添加复制功能测试按钮
    def test_copy():
        """测试复制功能"""
        selection = viewer.selection()
        if not selection:
            print("[测试] 请先选择要复制的行")
            return
        
        # 获取接口号列的索引（状态列是第0列，项目号是第1列，接口号是第2列）
        interface_col_idx = columns.index("接口号")
        
        copied_values = []
        for item_id in selection:
            values = viewer.item(item_id, 'values')
            if interface_col_idx < len(values):
                interface_value = values[interface_col_idx]
                copied_values.append(interface_value)
        
        result = '\n'.join(copied_values)
        root.clipboard_clear()
        root.clipboard_append(result)
        
        print(f"[测试] 已复制 {len(copied_values)} 行接口号:")
        print(result)
        print(f"[验证] 复制内容{'包含' if '⚠️' in result else '不包含'} ⚠️ 标记")
    
    # 创建按钮框架
    btn_frame = ttk.Frame(root)
    btn_frame.pack(fill="x", padx=10, pady=5)
    
    ttk.Button(btn_frame, text="复制选中的接口号", command=test_copy).pack(side="left", padx=5)
    
    info_label = ttk.Label(btn_frame, text="提示: 选择行后点击'复制'按钮，验证复制内容不包含⚠️标记", foreground="blue")
    info_label.pack(side="left", padx=10)
    
    # 显示测试说明
    print("=" * 60)
    print("状态列独立显示测试")
    print("=" * 60)
    print("预期效果:")
    print("1. '状态'列在最左侧，宽度50px")
    print("2. 延期数据的'状态'列显示 ⚠️")
    print("3. '接口号'列不包含 ⚠️ 标记")
    print("4. 复制接口号时只复制接口号，不包含⚠️")
    print("=" * 60)
    print("\n当前数据:")
    print(f"- 总共 {len(display_df)} 行数据")
    overdue_count = sum(1 for idx in range(len(display_df)) if is_date_overdue(str(display_df.iloc[idx]["接口时间"])))
    print(f"- 延期数据 {overdue_count} 行")
    print(f"- 正常数据 {len(display_df) - overdue_count} 行")
    print("=" * 60)
    
    root.mainloop()

if __name__ == "__main__":
    test_status_column()

