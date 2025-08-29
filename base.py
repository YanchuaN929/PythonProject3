#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel数据处理程序
支持Win7+系统，具备GUI界面、后台运行、系统托盘等功能
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.scrolledtext as scrolledtext
import os
import sys
import json
import datetime
import threading
import winreg
from pathlib import Path
import pandas as pd
import subprocess

# 尝试导入系统托盘相关模块
try:
    import pystray
    from PIL import Image
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("警告: 未安装pystray或PIL，系统托盘功能不可用")

class ExcelProcessorApp:
    """主应用程序类"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.load_config()
        # 四个勾选框变量
        self.process_file1_var = tk.BooleanVar(value=True)
        self.process_file2_var = tk.BooleanVar(value=False)
        self.process_file3_var = tk.BooleanVar(value=False)
        self.process_file4_var = tk.BooleanVar(value=False)
        self.create_widgets()
        self.setup_layout()
        self.tray_icon = None
        self.is_closing = False
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        # 当前日期时间
        self.current_datetime = datetime.datetime.now()
        
        # Excel文件列表
        self.excel_files = []
        
        # 四类文件及项目号
        self.target_file1 = None
        self.target_file1_project_id = None
        self.target_file2 = None
        self.target_file2_project_id = None
        self.target_file3 = None
        self.target_file3_project_id = None
        self.target_file4 = None
        self.target_file4_project_id = None
        # 文件数据存储
        self.file1_data = None
        self.file2_data = None
        self.file3_data = None
        self.file4_data = None
        # 处理结果
        self.processing_results = None
        self.processing_results2 = None
        self.processing_results3 = None
        self.processing_results4 = None
        # 处理结果状态标记 - 用于判断是否显示处理后的结果
        self.has_processed_results1 = False
        self.has_processed_results2 = False
        self.has_processed_results3 = False
        self.has_processed_results4 = False
        # 监控器
        self.monitor = None
        
        # 勾选框变量
        

    def setup_window(self):
        """设置主窗口属性"""
        self.root.title("Excel数据处理程序")
        
        # 获取屏幕分辨率并适配
        self.setup_window_size()
        
        # 设置最小窗口大小
        self.root.minsize(1200, 800)
        
        # 设置窗口图标
        try:
            icon_path = "ico_bin/tubiao.ico"
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置窗口图标失败: {e}")

    def setup_window_size(self):
        """设置窗口大小以适配不同分辨率"""
        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        print(f"检测到屏幕分辨率: {screen_width}x{screen_height}")
        
        # 常见分辨率适配
        if screen_width >= 1920 and screen_height >= 1080:
            # 1920x1080 或更高分辨率 - 全屏
            self.root.state('zoomed')
        elif screen_width >= 1600 and screen_height >= 900:
            # 1600x900 - 使用90%屏幕空间
            width = int(screen_width * 0.9)
            height = int(screen_height * 0.9)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        elif screen_width >= 1366 and screen_height >= 768:
            # 1366x768 - 使用85%屏幕空间
            width = int(screen_width * 0.85)
            height = int(screen_height * 0.85)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        else:
            # 更小的分辨率 - 使用最小推荐尺寸
            width = min(1200, screen_width - 100)
            height = min(800, screen_height - 100)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # 确保窗口在屏幕范围内
        self.root.update_idletasks()
        self.center_window_if_needed()

    def load_config(self):
        """加载配置文件"""
        self.config_file = "config.json"
        self.default_config = {
            "folder_path": "",
            "auto_startup": False,
            "minimize_to_tray": True,
            "dont_ask_again": False
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self.default_config.copy()
        except:
            self.config = self.default_config.copy()

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def create_widgets(self):
        """创建GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # 第一行：文件夹路径
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="文件夹路径:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.path_var = tk.StringVar(value=self.config.get("folder_path", ""))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        self.path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        self.browse_button = ttk.Button(path_frame, text="浏览", command=self.browse_folder)
        self.browse_button.grid(row=0, column=2, sticky=tk.W)
        
        # 右上角：设置菜单按钮
        self.settings_button = ttk.Button(path_frame, text="⚙", command=self.show_settings_menu)
        self.settings_button.grid(row=0, column=3, sticky=tk.E, padx=(20, 0))
        
        # 初始化设置相关变量
        self.auto_startup_var = tk.BooleanVar(value=self.config.get("auto_startup", False))
        self.show_close_dialog_var = tk.BooleanVar(value=not self.config.get("dont_ask_again", False))
        
        # 第二行：文件信息显示
        info_frame = ttk.LabelFrame(main_frame, text="Excel文件信息", padding="5")
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        info_frame.columnconfigure(0, weight=1)
        
        # 根据屏幕高度调整文本区域高度
        screen_height = self.root.winfo_screenheight()
        if screen_height >= 1080:
            text_height = 6
        elif screen_height >= 900:
            text_height = 5
        else:
            text_height = 4
        
        self.file_info_text = scrolledtext.ScrolledText(info_frame, height=text_height, state='disabled')
        self.file_info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 中间主体：选项卡显示区域
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 选项卡勾选框区域
        tab_check_frame = ttk.Frame(main_frame)
        tab_check_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 2))
        
        # 创建选项卡
        self.create_tabs()
        
        # 底部按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0))
        
        self.process_button = ttk.Button(
            button_frame, 
            text="开始处理", 
            command=self.start_processing,
            style="Accent.TButton"
        )
        self.process_button.pack(side=tk.LEFT, padx=(0, 20))
        
        self.export_button = ttk.Button(
            button_frame, 
            text="导出结果", 
            command=self.export_results,
            state='disabled'
        )
        self.export_button.pack(side=tk.LEFT)
        
        # 刷新文件列表按钮
        self.refresh_button = ttk.Button(
            button_frame,
            text="刷新文件列表",
            command=self.refresh_file_list
        )
        self.refresh_button.pack(side=tk.LEFT, padx=(20, 0))
        
        # 打开监控按钮
        self.monitor_button = ttk.Button(
            button_frame,
            text="打开监控",
            command=self.open_monitor
        )
        self.monitor_button.pack(side=tk.LEFT, padx=(10, 0))

    def create_tabs(self):
        """创建选项卡"""
        # 选项卡1：应打开接口
        self.tab1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1_frame, text="应打开接口")
        self.tab1_frame.columnconfigure(0, weight=1)
        self.tab1_frame.rowconfigure(1, weight=1)
        self.tab1_check = ttk.Checkbutton(self.tab1_frame, text="处理应打开接口", variable=self.process_file1_var)
        self.tab1_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡2：需回复接口
        self.tab2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2_frame, text="需回复接口")
        self.tab2_frame.columnconfigure(0, weight=1)
        self.tab2_frame.rowconfigure(1, weight=1)
        self.tab2_check = ttk.Checkbutton(self.tab2_frame, text="处理需打开接口", variable=self.process_file2_var)
        self.tab2_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡3：外部接口ICM
        self.tab3_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3_frame, text="外部接口ICM")
        self.tab3_frame.columnconfigure(0, weight=1)
        self.tab3_frame.rowconfigure(1, weight=1)
        self.tab3_check = ttk.Checkbutton(self.tab3_frame, text="处理外部接口ICM", variable=self.process_file3_var)
        self.tab3_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡4：外部接口单
        self.tab4_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab4_frame, text="外部接口单")
        self.tab4_frame.columnconfigure(0, weight=1)
        self.tab4_frame.rowconfigure(1, weight=1)
        self.tab4_check = ttk.Checkbutton(self.tab4_frame, text="处理外部接口单", variable=self.process_file4_var)
        self.tab4_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 为每个选项卡创建Excel预览控件
        self.create_excel_viewer(self.tab1_frame, "tab1")
        self.create_excel_viewer(self.tab2_frame, "tab2")
        self.create_excel_viewer(self.tab3_frame, "tab3")
        self.create_excel_viewer(self.tab4_frame, "tab4")
        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        # 存储选项卡引用以便后续修改状态
        self.tabs = {
            'tab1': 0,  # 应打开接口
            'tab2': 1,  # 需回复接口
            'tab3': 2,  # 外部接口ICM
            'tab4': 3   # 外部接口单
        }

    def create_excel_viewer(self, parent, tab_id):
        """为选项卡创建Excel预览控件，布局全部用grid，row=1"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        # 创建Treeview用于Excel预览
        viewer = ttk.Treeview(parent)
        viewer.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        # 添加滚动条
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=viewer.yview)
        v_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        viewer.configure(yscrollcommand=v_scrollbar.set)
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=viewer.xview)
        h_scrollbar.grid(row=2, column=0, sticky=(tk.W, tk.E))
        viewer.configure(xscrollcommand=h_scrollbar.set)
        # 存储viewer引用
        setattr(self, f'{tab_id}_viewer', viewer)
        # 默认显示提示信息
        self.show_empty_message(viewer, f"等待{self.notebook.tab(getattr(self, 'tabs', {}).get(tab_id, 0), 'text') or '数据'}...")

    def show_empty_message(self, viewer, message):
        """在viewer中显示提示信息"""
        # 清空现有内容
        for item in viewer.get_children():
            viewer.delete(item)
        
        # 设置合适的列宽而不是单列显示
        # 创建5个默认列用于显示（对应A, B, H, K, M列的布局）
        default_columns = ["A列", "B列", "H列", "K列", "M列"]
        viewer["columns"] = default_columns
        viewer["show"] = "tree headings"
        
        # 配置序号列
        viewer.column("#0", width=60, minwidth=60, anchor='center')
        viewer.heading("#0", text="行号")
        
        # 配置数据列，使用紧凑但合理的宽度
        for col in default_columns:
            viewer.heading(col, text=col)
            viewer.column(col, width=120, minwidth=100, anchor='center')
        
        # 插入提示信息（显示在第一列）
        empty_values = [message] + [""] * (len(default_columns) - 1)
        viewer.insert("", "end", text="", values=empty_values)

    def on_tab_changed(self, event):
        """选项卡切换事件处理"""
        selected_tab = self.notebook.index(self.notebook.select())
        
        # 根据选择的选项卡加载相应数据，优先显示处理结果
        if selected_tab == 0 and self.target_file1:  # 应打开接口
            # 如果有处理结果，显示过滤后的数据；否则显示原始数据
            if self.has_processed_results1 and self.processing_results is not None and not self.processing_results.empty:
                print("显示处理后的过滤结果")
                self.filter_and_display_results(self.processing_results)
            elif self.has_processed_results1 and (self.processing_results is None or self.processing_results.empty):
                print("显示无数据结果")
                self.show_no_data_result(show_popup=False)
            elif self.file1_data is not None:
                print("显示原始文件数据")
                self.display_excel_data(self.tab1_viewer, self.file1_data, "应打开接口")
            else:
                self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "应打开接口")
        elif selected_tab == 1 and self.target_file2:  # 需回复接口
            if self.has_processed_results2 and self.processing_results2 is not None and not self.processing_results2.empty:
                display_df = self.processing_results2.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results2['原始行号'])
                self.display_excel_data_with_original_rows(self.tab2_viewer, display_df, "需回复接口", excel_row_numbers)
            elif self.has_processed_results2:
                self.show_empty_message(self.tab2_viewer, "无需回复接口")
            elif self.file2_data is not None:
                self.display_excel_data(self.tab2_viewer, self.file2_data, "需回复接口")
            else:
                self.load_file_to_viewer(self.target_file2, self.tab2_viewer, "需回复接口")
        elif selected_tab == 2 and self.target_file3:  # 外部接口ICM
            if self.has_processed_results3 and self.processing_results3 is not None and not self.processing_results3.empty:
                display_df = self.processing_results3.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results3['原始行号'])
                self.display_excel_data_with_original_rows(self.tab3_viewer, display_df, "外部接口ICM", excel_row_numbers)
            elif self.has_processed_results3:
                self.show_empty_message(self.tab3_viewer, "无外部接口ICM")
            elif self.file3_data is not None:
                self.display_excel_data(self.tab3_viewer, self.file3_data, "外部接口ICM")
            else:
                self.load_file_to_viewer(self.target_file3, self.tab3_viewer, "外部接口ICM")
        elif selected_tab == 3 and self.target_file4:  # 外部接口单
            if self.has_processed_results4 and self.processing_results4 is not None and not self.processing_results4.empty:
                display_df = self.processing_results4.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results4['原始行号'])
                self.display_excel_data_with_original_rows(self.tab4_viewer, display_df, "外部接口单", excel_row_numbers)
            elif self.has_processed_results4:
                self.show_empty_message(self.tab4_viewer, "无外部接口单")
            elif self.file4_data is not None:
                self.display_excel_data(self.tab4_viewer, self.file4_data, "外部接口单")
            else:
                self.load_file_to_viewer(self.target_file4, self.tab4_viewer, "外部接口单")

    def load_file_to_viewer(self, file_path, viewer, tab_name):
        """加载Excel文件到预览器"""
        try:
            print(f"正在加载 {tab_name} 文件: {os.path.basename(file_path)}")
            
            # 读取Excel文件
            if file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path, sheet_name='Sheet1', engine='openpyxl')
            else:
                df = pd.read_excel(file_path, sheet_name='Sheet1', engine='xlrd')
            
            if df.empty:
                self.show_empty_message(viewer, f"{tab_name}文件为空")
                return
            
            # 存储数据
            if tab_name == "应打开接口":
                self.file1_data = df
            elif tab_name == "需回复接口":
                self.file2_data = df
            elif tab_name == "外部接口ICM":
                self.file3_data = df
            elif tab_name == "外部接口单":
                self.file4_data = df
            
            self.display_excel_data(viewer, df, tab_name)
            
        except Exception as e:
            print(f"加载{tab_name}文件失败: {e}")
            self.show_empty_message(viewer, f"加载{tab_name}文件失败")

    def display_excel_data(self, viewer, df, tab_name):
        """在viewer中显示Excel数据"""
        # 清空现有内容
        for item in viewer.get_children():
            viewer.delete(item)
        
        # 对不同的文件类型进行优化显示（仅显示关键列）
        if tab_name == "应打开接口" and len(df.columns) >= 13:
            # 创建优化后的显示数据
            display_df = self.create_optimized_display_data(df)
            columns = list(display_df.columns)
        elif tab_name == "需回复接口" and len(df.columns) >= 28:
            # 待处理文件2优化显示
            display_df = self.create_optimized_display_data_file2(df)
            columns = list(display_df.columns)
        elif tab_name == "外部接口ICM" and len(df.columns) >= 38:
            # 待处理文件3优化显示
            display_df = self.create_optimized_display_data_file3(df)
            columns = list(display_df.columns)
        elif tab_name == "外部接口单" and len(df.columns) >= 32:
            # 待处理文件4优化显示
            display_df = self.create_optimized_display_data_file4(df)
            columns = list(display_df.columns)
        else:
            # 其他情况正常显示
            display_df = df
            columns = list(df.columns)
        
        viewer["columns"] = columns
        viewer["show"] = "tree headings"
        
        # 配置序号列
        viewer.column("#0", width=60, minwidth=60)
        viewer.heading("#0", text="行号")
        
        # 配置数据列（基于第二行数据计算固定列宽）
        column_widths = self.calculate_column_widths(display_df, columns)
        
        for i, col in enumerate(columns):
            col_width = column_widths[i] if i < len(column_widths) else 100
            
            viewer.heading(col, text=str(col))
            # 设置固定列宽，并居中显示
            viewer.column(col, width=col_width, minwidth=col_width, anchor='center')
        
        # 添加数据行，限制显示前30行
        row_count = 0
        for index, row in display_df.iterrows():
            if row_count >= 30:  # 限制显示前30行
                break
            
            # 处理数据显示格式
            display_values = []
            for val in row:
                if pd.isna(val):
                    display_values.append("")
                elif isinstance(val, (int, float)):
                    if isinstance(val, float) and val.is_integer():
                        display_values.append(str(int(val)))
                    else:
                        display_values.append(str(val))
                else:
                    display_values.append(str(val))
            
            # 插入行，使用Excel行号（从1开始）
            viewer.insert("", "end", text=str(index + 1), values=display_values)
            row_count += 1
        
        # 如果有更多行，添加提示信息
        if len(display_df) > 30:
            viewer.insert("", "end", text="...", values=["...（其他行已省略显示）"] + [""] * (len(columns) - 1))
        
        print(f"{tab_name}数据加载完成：{len(df)} 行，{len(df.columns)} 列 -> 显示：{len(display_df.columns)} 列")

    def display_excel_data_with_original_rows(self, viewer, df, tab_name, original_row_numbers):
        """在viewer中显示Excel数据，使用原始Excel行号"""
        # 清空现有内容
        for item in viewer.get_children():
            viewer.delete(item)
        
        # 对不同的文件类型进行优化显示（仅显示关键列）
        if tab_name == "应打开接口" and len(df.columns) >= 13:
            # 创建优化后的显示数据
            display_df = self.create_optimized_display_data(df)
            columns = list(display_df.columns)
        elif tab_name == "需回复接口" and len(df.columns) >= 28:
            # 待处理文件2优化显示
            display_df = self.create_optimized_display_data_file2(df)
            columns = list(display_df.columns)
        elif tab_name == "外部接口ICM" and len(df.columns) >= 38:
            # 待处理文件3优化显示
            display_df = self.create_optimized_display_data_file3(df)
            columns = list(display_df.columns)
        elif tab_name == "外部接口单" and len(df.columns) >= 32:
            # 待处理文件4优化显示
            display_df = self.create_optimized_display_data_file4(df)
            columns = list(display_df.columns)
        else:
            # 其他情况正常显示
            display_df = df
            columns = list(df.columns)
        
        viewer["columns"] = columns
        viewer["show"] = "tree headings"
        
        # 配置序号列
        viewer.column("#0", width=60, minwidth=60)
        viewer.heading("#0", text="行号")
        
        # 配置数据列（基于第二行数据计算固定列宽）
        column_widths = self.calculate_column_widths(display_df, columns)
        
        for i, col in enumerate(columns):
            col_width = column_widths[i] if i < len(column_widths) else 100
            
            viewer.heading(col, text=str(col))
            # 设置固定列宽，并居中显示
            viewer.column(col, width=col_width, minwidth=col_width, anchor='center')
        
        # 添加数据行，使用原始Excel行号，限制显示前30行
        row_count = 0
        for index, row in display_df.iterrows():
            if row_count >= 30:  # 限制显示前30行
                break
            
            # 处理数据显示格式
            display_values = []
            for val in row:
                if pd.isna(val):
                    display_values.append("")
                elif isinstance(val, (int, float)):
                    if isinstance(val, float) and val.is_integer():
                        display_values.append(str(int(val)))
                    else:
                        display_values.append(str(val))
                else:
                    display_values.append(str(val))
            
            # 使用原始Excel行号而不是DataFrame索引
            if index < len(original_row_numbers):
                row_number_display = original_row_numbers[index]
                # 如果是字符串（如表头的"行号"），直接使用；如果是数字，转换为字符串
                if isinstance(row_number_display, str):
                    display_text = row_number_display
                else:
                    display_text = str(row_number_display)
                viewer.insert("", "end", text=display_text, values=display_values)
            else:
                # 防错处理
                viewer.insert("", "end", text=str(index + 1), values=display_values)
            
            row_count += 1
        
        # 如果有更多行，添加提示信息
        if len(display_df) > 30:
            viewer.insert("", "end", text="...", values=["...（其他行已省略显示）"] + [""] * (len(columns) - 1))
        
        print(f"{tab_name}数据加载完成（使用原始行号）：{len(df)} 行，{len(df.columns)} 列 -> 显示：{len(display_df.columns)} 列")

    def calculate_column_widths(self, df, columns):
        """基于第二行数据计算列宽，确保内容完全显示"""
        try:
            column_widths = []
            
            # 选择用于计算列宽的行：优先使用第二行（数据行），如果没有则使用第一行（表头行）
            if len(df) >= 2:
                # 有数据行，使用第二行计算
                calc_row = df.iloc[1]
                print("使用第二行数据计算列宽")
            elif len(df) >= 1:
                # 只有表头行，使用表头计算
                calc_row = df.iloc[0]
                print("使用表头行计算列宽")
            else:
                # 没有数据，返回紧凑的默认宽度
                return [80] * len(columns)
            
            for i, col in enumerate(columns):
                try:
                    # 获取列标题和数据内容的长度
                    header_length = len(str(col))
                    
                    if i < len(calc_row):
                        data_value = calc_row.iloc[i] if hasattr(calc_row, 'iloc') else calc_row[i]
                        data_length = len(str(data_value)) if not pd.isna(data_value) else 0
                    else:
                        data_length = 0
                    
                    # 取标题和数据中较长者，并转换为像素宽度
                    max_content_length = max(header_length, data_length)
                    
                    # 基础计算：每个字符约8像素，中文字符约16像素
                    content_str = str(data_value) if i < len(calc_row) and not pd.isna(calc_row.iloc[i] if hasattr(calc_row, 'iloc') else calc_row[i]) else str(col)
                    
                    # 粗略估算：英文字符8像素，中文字符16像素
                    estimated_width = 0
                    for char in content_str:
                        if ord(char) > 127:  # 中文字符
                            estimated_width += 16
                        else:  # 英文字符
                            estimated_width += 8
                    
                    # 增加1.2倍富余量，并设置最小最大值
                    col_width = int(estimated_width * 1.2)
                    col_width = max(60, min(col_width, 300))  # 最小60，最大300
                    
                    column_widths.append(col_width)
                    
                except Exception as e:
                    print(f"计算第{i}列宽度时出错: {e}")
                    column_widths.append(100)  # 默认宽度
            
            print(f"计算列宽完成: {column_widths}")
            return column_widths
            
        except Exception as e:
            print(f"计算列宽失败: {e}")
            return [100] * len(columns)

    def create_optimized_display_data(self, df):
        """为待处理文件1创建优化的显示数据（仅显示A,B,H,K,M列）"""
        try:
            # 确保有足够的列
            if len(df.columns) < 13:
                return df
            
            # 获取列名（转换为列表以支持索引）
            original_columns = list(df.columns)
            
            # 定义要显示的列（A=0, B=1, H=7, K=10, M=12）
            key_column_indices = [0, 1, 7, 10, 12]  # A, B, H, K, M列的索引
            
            # 创建新的列名：仅显示关键列，去除"其他列"
            new_columns = []
            for i in key_column_indices:
                if i < len(original_columns):
                    new_columns.append(original_columns[i])
            
            # 构建显示数据
            display_data = []
            for _, row in df.iterrows():
                new_row = []
                # 仅添加关键列数据
                for i in key_column_indices:
                    if i < len(row):
                        new_row.append(row.iloc[i])
                    else:
                        new_row.append("")
                display_data.append(new_row)
            
            # 创建新的DataFrame
            display_df = pd.DataFrame(display_data, columns=new_columns)
            
            print(f"优化显示：原始{len(original_columns)}列 -> 显示关键列A,B,H,K,M")
            return display_df
            
        except Exception as e:
            print(f"创建优化显示数据失败: {e}")
            return df

    def create_optimized_display_data_file2(self, df):
        """为待处理文件2创建优化的显示数据（仅显示A、I、M、N、F、AB列）"""
        try:
            # 确保有足够的列
            required_cols = max(0, 8, 12, 13, 5, 27)  # A=0, I=8, M=12, N=13, F=5, AB=27
            if len(df.columns) <= required_cols:
                return df
            
            # 获取列名（转换为列表以支持索引）
            original_columns = list(df.columns)
            
            # 定义要显示的列（A=0, I=8, M=12, N=13, F=5, AB=27）
            key_column_indices = [0, 8, 12, 13, 5, 27]  # A, I, M, N, F, AB列的索引
            
            # 创建新的列名：仅显示关键列
            new_columns = []
            for i in key_column_indices:
                if i < len(original_columns):
                    new_columns.append(original_columns[i])
            
            # 构建显示数据
            display_data = []
            for _, row in df.iterrows():
                new_row = []
                # 仅添加关键列数据
                for i in key_column_indices:
                    if i < len(row):
                        new_row.append(row.iloc[i])
                    else:
                        new_row.append("")
                display_data.append(new_row)
            
            # 创建新的DataFrame
            display_df = pd.DataFrame(display_data, columns=new_columns)
            
            print(f"优化显示文件2：原始{len(original_columns)}列 -> 显示关键列A,I,M,N,F,AB")
            return display_df
            
        except Exception as e:
            print(f"创建优化显示数据失败(文件2): {e}")
            return df

    def create_optimized_display_data_file3(self, df):
        """为待处理文件3创建优化的显示数据（仅显示C、AL、I、M、Q、T、L、N列）"""
        try:
            # 确保有足够的列（C=2, AL=37, I=8, M=12, Q=16, T=19, L=11, N=13）
            required_cols = max(2, 37, 8, 12, 16, 19, 11, 13)
            if len(df.columns) <= required_cols:
                return df
            
            # 获取列名（转换为列表以支持索引）
            original_columns = list(df.columns)
            
            # 定义要显示的列（C=2, AL=37, I=8, M=12, Q=16, T=19, L=11, N=13）
            key_column_indices = [2, 37, 8, 12, 16, 19, 11, 13]  # C, AL, I, M, Q, T, L, N列的索引
            
            # 创建新的列名：仅显示关键列
            new_columns = []
            for i in key_column_indices:
                if i < len(original_columns):
                    new_columns.append(original_columns[i])
            
            # 构建显示数据
            display_data = []
            for _, row in df.iterrows():
                new_row = []
                # 仅添加关键列数据
                for i in key_column_indices:
                    if i < len(row):
                        new_row.append(row.iloc[i])
                    else:
                        new_row.append("")
                display_data.append(new_row)
            
            # 创建新的DataFrame
            display_df = pd.DataFrame(display_data, columns=new_columns)
            
            print(f"优化显示文件3：原始{len(original_columns)}列 -> 显示关键列C,AL,I,M,Q,T,L,N")
            return display_df
            
        except Exception as e:
            print(f"创建优化显示数据失败(文件3): {e}")
            return df

    def create_optimized_display_data_file4(self, df):
        """为待处理文件4创建优化的显示数据（仅显示E、P、V、S、AF列）"""
        try:
            # 确保有足够的列（E=4, P=15, V=21, S=18, AF=31）
            required_cols = max(4, 15, 21, 18, 31)
            if len(df.columns) <= required_cols:
                return df
            
            # 获取列名（转换为列表以支持索引）
            original_columns = list(df.columns)
            
            # 定义要显示的列（E=4, P=15, V=21, S=18, AF=31）- E列挪到P列之前
            key_column_indices = [4, 15, 21, 18, 31]  # E, P, V, S, AF列的索引
            
            # 创建新的列名：仅显示关键列
            new_columns = []
            for i in key_column_indices:
                if i < len(original_columns):
                    new_columns.append(original_columns[i])
            
            # 构建显示数据
            display_data = []
            for _, row in df.iterrows():
                new_row = []
                # 仅添加关键列数据
                for i in key_column_indices:
                    if i < len(row):
                        new_row.append(row.iloc[i])
                    else:
                        new_row.append("")
                display_data.append(new_row)
            
            # 创建新的DataFrame
            display_df = pd.DataFrame(display_data, columns=new_columns)
            
            print(f"优化显示文件4：原始{len(original_columns)}列 -> 显示关键列E,P,V,S,AF")
            return display_df
            
        except Exception as e:
            print(f"创建优化显示数据失败(文件4): {e}")
            return df

    def update_tab_color(self, tab_index, color="green"):
        """更新选项卡颜色"""
        # 注意：tkinter的ttk.Notebook默认不直接支持选项卡颜色修改
        # 这里我们通过修改选项卡文本来表示状态
        current_text = self.notebook.tab(tab_index, "text")
        if color == "green" and not current_text.endswith(" ✓"):
            self.notebook.tab(tab_index, text=current_text + " ✓")
        elif color != "green" and current_text.endswith(" ✓"):
            self.notebook.tab(tab_index, text=current_text.replace(" ✓", ""))

    def center_window_if_needed(self):
        """如果需要，将窗口居中显示"""
        # 获取窗口实际大小
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # 获取屏幕大小
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # 如果窗口不是最大化状态，确保它在屏幕中央
        if self.root.state() != 'zoomed':
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")

    def setup_layout(self):
        """设置布局和样式"""
        # 设置样式
        style = ttk.Style()
        style.theme_use('winnative')  # Windows原生主题
        
        # 根据屏幕大小调整字体大小
        self.adjust_font_sizes()
        
        # 显示初始欢迎信息，等待用户手动刷新
        self.show_initial_welcome_message()

    def show_initial_welcome_message(self):
        """显示初始欢迎信息"""
        welcome_text = "欢迎使用本程序，请点击刷新文件列表按钮加载内容。"
        self.update_file_info(welcome_text)
        
        # 为所有选项卡显示欢迎信息
        self.show_empty_message(self.tab1_viewer, "等待加载应打开接口数据")
        self.show_empty_message(self.tab2_viewer, "等待加载需回复接口数据")
        self.show_empty_message(self.tab3_viewer, "等待加载外部接口ICM数据")
        self.show_empty_message(self.tab4_viewer, "等待加载外部接口单数据")

    def adjust_font_sizes(self):
        """根据屏幕分辨率调整字体大小"""
        screen_width = self.root.winfo_screenwidth()
        
        # 根据屏幕宽度调整字体
        if screen_width >= 1920:
            font_size = 10
        elif screen_width >= 1600:
            font_size = 9
        elif screen_width >= 1366:
            font_size = 9
        else:
            font_size = 8
        
        # 设置默认字体
        default_font = ('Microsoft YaHei UI', font_size)
        
        style = ttk.Style()
        style.configure('TLabel', font=default_font)
        style.configure('TButton', font=default_font)
        style.configure('TEntry', font=default_font)
        style.configure('TCheckbutton', font=default_font)
        style.configure('Treeview', font=default_font)
        style.configure('Treeview.Heading', font=(default_font[0], font_size + 1, 'bold'))

    def browse_folder(self):
        """浏览文件夹"""
        folder_path = filedialog.askdirectory(
            title="选择包含Excel文件的文件夹",
            initialdir=self.path_var.get() or os.path.expanduser("~")
        )
        
        if folder_path:
            self.path_var.set(folder_path)
            self.config["folder_path"] = folder_path
            self.save_config()
            self.refresh_file_list()

    def show_settings_menu(self):
        """显示设置菜单"""
        # 创建设置菜单窗口
        settings_menu = tk.Toplevel(self.root)
        settings_menu.title("设置")
        settings_menu.geometry("250x120")
        settings_menu.transient(self.root)
        settings_menu.grab_set()
        
        # 设置窗口图标
        try:
            icon_path = "ico_bin/tubiao.ico"
            if os.path.exists(icon_path):
                settings_menu.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置菜单图标失败: {e}")
        
        # 居中显示
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 125
        y = self.root.winfo_rooty() + 50
        settings_menu.geometry(f"+{x}+{y}")
        
        # 设置框架
        frame = ttk.Frame(settings_menu, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 开机自启动选项
        auto_startup_check = ttk.Checkbutton(
            frame,
            text="开机自启动",
            variable=self.auto_startup_var,
            command=self.toggle_auto_startup
        )
        auto_startup_check.pack(anchor=tk.W, pady=(0, 10))
        
        # 关闭时弹窗提醒选项
        close_dialog_check = ttk.Checkbutton(
            frame,
            text="关闭时弹窗提醒",
            variable=self.show_close_dialog_var,
            command=self.toggle_close_dialog
        )
        close_dialog_check.pack(anchor=tk.W, pady=(0, 10))
        
        # 关闭按钮
        close_button = ttk.Button(frame, text="确定", command=settings_menu.destroy)
        close_button.pack(pady=(10, 0))

    def show_waiting_dialog(self, title, message):
        """显示等待对话框"""
        waiting_dialog = tk.Toplevel(self.root)
        waiting_dialog.title(title)
        waiting_dialog.geometry("280x100")
        waiting_dialog.transient(self.root)
        waiting_dialog.grab_set()
        waiting_dialog.resizable(False, False)
        
        # 设置窗口图标
        try:
            icon_path = "ico_bin/tubiao.ico"
            if os.path.exists(icon_path):
                waiting_dialog.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置等待对话框图标失败: {e}")
        
        # 居中显示
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 140
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 50
        waiting_dialog.geometry(f"+{x}+{y}")
        
        # 等待消息框架
        frame = ttk.Frame(waiting_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 显示等待消息
        message_label = ttk.Label(frame, text=message, font=("Microsoft YaHei UI", 10))
        message_label.pack(pady=(10, 0))
        
        # 进度条（无限滚动模式）
        progress = ttk.Progressbar(frame, mode='indeterminate')
        progress.pack(pady=(15, 10), fill=tk.X)
        progress.start(10)  # 开始动画
        
        # 更新窗口以确保正确显示
        waiting_dialog.update()
        
        return waiting_dialog, message_label
    
    def show_export_waiting_dialog(self, title, message, total_count):
        """显示导出等待对话框，支持进度显示"""
        waiting_dialog = tk.Toplevel(self.root)
        waiting_dialog.title(title)
        waiting_dialog.geometry("320x120")
        waiting_dialog.transient(self.root)
        waiting_dialog.grab_set()
        waiting_dialog.resizable(False, False)
        
        # 设置窗口图标
        try:
            icon_path = "ico_bin/tubiao.ico"
            if os.path.exists(icon_path):
                waiting_dialog.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置导出等待对话框图标失败: {e}")
        
        # 居中显示
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - 160
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - 60
        waiting_dialog.geometry(f"+{x}+{y}")
        
        # 等待消息框架
        frame = ttk.Frame(waiting_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 显示主要消息
        main_label = ttk.Label(frame, text=message, font=("Microsoft YaHei UI", 10))
        main_label.pack(pady=(5, 0))
        
        # 显示进度信息
        progress_label = ttk.Label(frame, text=f"正在导出: (0/{total_count})", font=("Microsoft YaHei UI", 9))
        progress_label.pack(pady=(5, 0))
        
        # 进度条（无限滚动模式）
        progress = ttk.Progressbar(frame, mode='indeterminate')
        progress.pack(pady=(10, 5), fill=tk.X)
        progress.start(10)  # 开始动画
        
        # 更新窗口以确保正确显示
        waiting_dialog.update()
        
        return waiting_dialog, progress_label
    
    def update_export_progress(self, dialog, progress_label, current, total):
        """更新导出进度"""
        if dialog and dialog.winfo_exists() and progress_label:
            progress_label.config(text=f"正在导出: ({current}/{total})")
            dialog.update()

    def close_waiting_dialog(self, dialog):
        """关闭等待对话框"""
        if dialog and dialog.winfo_exists():
            dialog.destroy()

    def refresh_file_list(self, show_popup=True):
        """刷新Excel文件列表"""
        folder_path = self.path_var.get().strip()
        if not folder_path or not os.path.exists(folder_path):
            self.update_file_info("请选择有效的文件夹路径")
            return
        
        # 显示等待对话框
        waiting_dialog, _ = self.show_waiting_dialog("刷新文件列表", "正在刷新中，请稍后。。。 。。。")
        
        # 使用after方法延迟执行实际刷新操作，确保等待对话框能正确显示
        def do_refresh():
            try:
                # 查找Excel文件
                excel_extensions = ['.xlsx', '.xls']
                self.excel_files = []
                
                for file_path in Path(folder_path).iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in excel_extensions:
                        self.excel_files.append(str(file_path))
                
                # 识别特定文件并更新选项卡状态
                self.identify_target_files()
                
                # 更新文件信息显示
                if self.excel_files:
                    file_info = f"找到 {len(self.excel_files)} 个Excel文件:\n"
                    
                    # 显示待处理文件信息
                    if self.target_file1:
                        file_info += f"✓ 待处理文件1 (应打开接口): {os.path.basename(self.target_file1)}\n"
                    if self.target_file2:
                        file_info += f"✓ 待处理文件2 (需回复接口): {os.path.basename(self.target_file2)}\n"
                    if self.target_file3:
                        file_info += f"✓ 待处理文件3 (外部接口ICM): {os.path.basename(self.target_file3)}\n"
                    if self.target_file4:
                        file_info += f"✓ 待处理文件4 (外部接口单): {os.path.basename(self.target_file4)}\n"
                    
                    file_info += f"\n全部文件列表:\n"
                    for i, file_path in enumerate(self.excel_files, 1):
                        file_name = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path)
                        file_info += f"{i}. {file_name} ({file_size} 字节)\n"
                else:
                    file_info = "在指定路径下未找到Excel文件"
                
                self.update_file_info(file_info)
                
            except Exception as e:
                self.update_file_info(f"读取文件列表时发生错误: {str(e)}")
            
            # 刷新完成后，更新当前选项卡的显示
            self.refresh_current_tab_display()
            
            # 关闭等待对话框
            self.close_waiting_dialog(waiting_dialog)
            
            # 仅在手动刷新时显示弹窗
            if show_popup:
                messagebox.showinfo("刷新完成", "已完成刷新")
        
        # 延迟执行刷新操作，确保等待对话框能够显示
        self.root.after(100, do_refresh)

    def refresh_current_tab_display(self):
        """刷新当前选项卡的显示内容"""
        try:
            # 获取当前选中的选项卡索引
            current_tab = self.notebook.index(self.notebook.select())
            
            # 根据当前选项卡刷新对应的显示内容
            if current_tab == 0 and self.target_file1:  # 应打开接口
                self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "应打开接口")
            elif current_tab == 1 and self.target_file2:  # 需回复接口
                self.load_file_to_viewer(self.target_file2, self.tab2_viewer, "需回复接口")
            elif current_tab == 2 and self.target_file3:  # 外部接口ICM
                self.load_file_to_viewer(self.target_file3, self.tab3_viewer, "外部接口ICM")
            elif current_tab == 3 and self.target_file4:  # 外部接口单
                self.load_file_to_viewer(self.target_file4, self.tab4_viewer, "外部接口单")
            else:
                # 如果当前选项卡没有对应的文件，显示空提示
                tab_names = ["应打开接口", "需回复接口", "外部接口ICM", "外部接口单"]
                viewers = [self.tab1_viewer, self.tab2_viewer, self.tab3_viewer, self.tab4_viewer]
                if 0 <= current_tab < len(tab_names):
                    self.show_empty_message(viewers[current_tab], f"等待加载{tab_names[current_tab]}数据")
        except Exception as e:
            print(f"刷新当前选项卡显示失败: {e}")

    def identify_target_files(self):
        """识别特定格式的目标文件"""
        # 重置文件状态
        self.target_file1 = None
        self.target_file1_project_id = None
        self.target_file2 = None
        self.target_file2_project_id = None
        self.target_file3 = None
        self.target_file3_project_id = None
        self.target_file4 = None
        self.target_file4_project_id = None
        self.file1_data = None
        self.file2_data = None
        self.file3_data = None
        self.file4_data = None
        # 重置处理结果状态标记
        self.has_processed_results1 = False
        self.has_processed_results2 = False
        self.has_processed_results3 = False
        self.has_processed_results4 = False
        # 重置选项卡状态
        self.update_tab_color(0, "normal")
        self.update_tab_color(1, "normal")
        self.update_tab_color(2, "normal")
        self.update_tab_color(3, "normal")
        if not self.excel_files:
            return
        try:
            if os.path.exists("main.py"):
                import main
                # 识别待处理文件1
                if hasattr(main, 'find_target_file'):
                    self.target_file1, self.target_file1_project_id = main.find_target_file(self.excel_files)
                    if self.target_file1:
                        self.update_tab_color(0, "green")
                        self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "应打开接口")
                # 识别待处理文件2
                if hasattr(main, 'find_target_file2'):
                    self.target_file2, self.target_file2_project_id = main.find_target_file2(self.excel_files)
                    if self.target_file2:
                        self.update_tab_color(1, "green")
                        try:
                            if self.target_file2.endswith('.xlsx'):
                                self.file2_data = pd.read_excel(self.target_file2, sheet_name='Sheet1', engine='openpyxl')
                            else:
                                self.file2_data = pd.read_excel(self.target_file2, sheet_name='Sheet1', engine='xlrd')
                        except Exception as e:
                            print(f"预加载待处理文件2失败: {e}")
                # 识别待处理文件3
                if hasattr(main, 'find_target_file3'):
                    self.target_file3, self.target_file3_project_id = main.find_target_file3(self.excel_files)
                    if self.target_file3:
                        self.update_tab_color(2, "green")
                        try:
                            if self.target_file3.endswith('.xlsx'):
                                self.file3_data = pd.read_excel(self.target_file3, sheet_name='Sheet1', engine='openpyxl')
                            else:
                                self.file3_data = pd.read_excel(self.target_file3, sheet_name='Sheet1', engine='xlrd')
                        except Exception as e:
                            print(f"预加载待处理文件3失败: {e}")
                # 识别待处理文件4
                if hasattr(main, 'find_target_file4'):
                    self.target_file4, self.target_file4_project_id = main.find_target_file4(self.excel_files)
                    if self.target_file4:
                        self.update_tab_color(3, "green")
                        try:
                            if self.target_file4.endswith('.xlsx'):
                                self.file4_data = pd.read_excel(self.target_file4, sheet_name='Sheet1', engine='openpyxl')
                            else:
                                self.file4_data = pd.read_excel(self.target_file4, sheet_name='Sheet1', engine='xlrd')
                        except Exception as e:
                            print(f"预加载待处理文件4失败: {e}")
        except Exception as e:
            print(f"识别目标文件时发生错误: {e}")

    def update_file_info(self, text):
        """更新文件信息显示"""
        self.file_info_text.config(state='normal')
        self.file_info_text.delete('1.0', tk.END)
        self.file_info_text.insert('1.0', text)
        self.file_info_text.config(state='disabled')

    def start_processing(self):
        """开始处理Excel文件"""
        print("自动刷新文件列表...")
        self.refresh_file_list(show_popup=False)  # 不显示刷新弹窗
        
        # 检查勾选状态
        process_file1 = self.process_file1_var.get()
        process_file2 = self.process_file2_var.get()
        process_file3 = self.process_file3_var.get()
        process_file4 = self.process_file4_var.get()
        if not (process_file1 or process_file2 or process_file3 or process_file4):
            messagebox.showwarning("警告", "请至少勾选一个需要处理的接口类型！")
            return
        
        # 显示等待对话框
        processing_dialog, _ = self.show_waiting_dialog("开始处理", "正在处理中，请稍后。。。 。。。")
            
        self.process_button.config(state='disabled', text="处理中...")
        
        def process_files():
            try:
                import main
                results1 = None
                results2 = None
                results3 = None
                results4 = None
                
                # 处理各个文件
                if process_file1 and self.target_file1:
                    if hasattr(main, 'process_target_file'):
                        results1 = main.process_target_file(self.target_file1, self.current_datetime)
                if process_file2 and self.target_file2:
                    if hasattr(main, 'process_target_file2'):
                        results2 = main.process_target_file2(self.target_file2, self.current_datetime)
                if process_file3 and self.target_file3:
                    if hasattr(main, 'process_target_file3'):
                        try:
                            results3 = main.process_target_file3(self.target_file3, self.current_datetime)
                        except NotImplementedError:
                            results3 = None
                if process_file4 and self.target_file4:
                    if hasattr(main, 'process_target_file4'):
                        try:
                            results4 = main.process_target_file4(self.target_file4, self.current_datetime)
                        except NotImplementedError:
                            results4 = None
                
                def update_display():
                    # 统一处理结果显示和弹窗
                    processed_count = 0
                    completion_messages = []
                    active_tab = 0  # 默认显示第一个选项卡
                    
                    if process_file1 and results1 is not None:
                        self.display_results(results1, show_popup=False)
                        active_tab = 0  # 应打开接口
                        if not results1.empty:
                            processed_count += 1
                            completion_messages.append(f"应打开接口：{len(results1)} 行数据")
                        else:
                            completion_messages.append("应打开接口：无符合条件的数据")
                    
                    if process_file2 and results2 is not None:
                        self.display_results2(results2, show_popup=False)
                        if active_tab == 0 and not process_file1:  # 如果file1没处理，显示file2
                            active_tab = 1
                        if not results2.empty:
                            processed_count += 1
                            completion_messages.append(f"需回复接口：{len(results2)} 行数据")
                        else:
                            completion_messages.append("需回复接口：无符合条件的数据")
                    
                    if process_file3 and results3 is not None:
                        self.display_results3(results3, show_popup=False)
                        if active_tab == 0 and not process_file1 and not process_file2:  # 显示优先级
                            active_tab = 2
                        if not results3.empty:
                            processed_count += 1
                            completion_messages.append(f"外部接口ICM：{len(results3)} 行数据")
                        else:
                            completion_messages.append("外部接口ICM：无符合条件的数据")
                    
                    if process_file4 and results4 is not None:
                        self.display_results4(results4, show_popup=False)
                        if active_tab == 0 and not process_file1 and not process_file2 and not process_file3:
                            active_tab = 3
                        if not results4.empty:
                            processed_count += 1
                            completion_messages.append(f"外部接口单：{len(results4)} 行数据")
                        else:
                            completion_messages.append("外部接口单：无符合条件的数据")
                    
                    # 选择显示的选项卡（优先级：file1 > file2 > file3 > file4）
                    self.notebook.select(active_tab)
                    
                    # 关闭等待对话框
                    self.close_waiting_dialog(processing_dialog)
                    
                    # 统一弹窗显示处理结果
                    if completion_messages:
                        combined_message = "数据处理完成！\n\n" + "\n".join(completion_messages)
                        messagebox.showinfo("处理完成", combined_message)
                    
                    self.process_button.config(state='normal', text="开始处理")
                
                self.root.after(0, update_display)
                
            except Exception as e:
                self.root.after(0, lambda: self.close_waiting_dialog(processing_dialog))
                self.root.after(0, lambda: messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}"))
                self.root.after(0, lambda: self.process_button.config(state='normal', text="开始处理"))
        
        thread = threading.Thread(target=process_files, daemon=True)
        thread.start()

    def display_results(self, results, show_popup=True):
        """显示处理结果"""
        # 检查处理结果
        if not isinstance(results, pd.DataFrame) or results.empty:
            if isinstance(results, pd.DataFrame) and len(results.columns) > 0:
                # 如果是包含错误信息的DataFrame
                error_msg = "处理过程中出现问题:\n"
                for col in results.columns:
                    for val in results[col]:
                        error_msg += f"- {val}\n"
                if show_popup:
                    messagebox.showwarning("处理结果", error_msg)
            else:
                # 处理完成但没有符合条件的数据
                self.show_no_data_result(show_popup)
            return
        
        # 检查结果是否为空（所有行都被剔除）
        if len(results) == 0:
            self.show_no_data_result(show_popup)
            return
        
        # 保存处理结果供导出使用
        self.processing_results = results
        self.has_processed_results1 = True  # 标记已有处理结果
        
        print(f"处理完成：原始数据经过筛选后剩余 {len(results)} 行符合条件的数据")
        
        # 基于原始文件数据，过滤显示符合条件的行
        self.filter_and_display_results(results)
        
        # 更新导出按钮状态
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            row_count = len(results)
            messagebox.showinfo("处理完成", f"数据处理完成！\n经过四步筛选后，共剩余 {row_count} 行符合条件的数据\n结果已在【应打开接口】选项卡中更新显示。")

    def show_no_data_result(self, show_popup=True):
        """显示无数据结果"""
        # 清空处理结果
        self.processing_results = None
        self.has_processed_results1 = True  # 标记已处理，即使结果为空
        
        # 无符合条件的数据时，直接显示空提示信息，不显示任何数据行
        self.show_empty_message(self.tab1_viewer, "无应打开接口")
        
        # 更新导出按钮状态（基于所有处理结果）
        self.update_export_button_state()
        
        # 显示提示信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", "无应打开接口\n\n经过四步筛选后，没有符合条件的数据。")

    def update_export_button_state(self):
        """更新导出按钮状态，基于所有处理结果的综合状态"""
        # 检查是否有任何处理结果可以导出
        has_exportable_results = False
        
        # 检查待处理文件1的结果
        if (self.has_processed_results1 and 
            self.processing_results is not None and 
            not self.processing_results.empty):
            has_exportable_results = True
        
        # 检查待处理文件2的结果
        if (self.has_processed_results2 and 
            self.processing_results2 is not None and 
            not self.processing_results2.empty):
            has_exportable_results = True
        
        # 检查待处理文件3的结果
        if (self.has_processed_results3 and 
            self.processing_results3 is not None and 
            not self.processing_results3.empty):
            has_exportable_results = True
        
        # 检查待处理文件4的结果
        if (self.has_processed_results4 and 
            self.processing_results4 is not None and 
            not self.processing_results4.empty):
            has_exportable_results = True
        
        # 根据结果设置导出按钮状态
        if has_exportable_results:
            self.export_button.config(state='normal')
        else:
            self.export_button.config(state='disabled')

    def filter_and_display_results(self, results):
        """
        只显示最终筛选出来的数据行，行号以Excel原表为准，不显示表头。
        """
        try:
            if results is None or results.empty or '原始行号' not in results.columns:
                self.show_empty_message(self.tab1_viewer, "无应打开接口")
                return

            # 只取最终结果的所有数据行
            display_df = results.drop(columns=['原始行号'], errors='ignore')
            excel_row_numbers = list(results['原始行号'])

            # 只显示数据行，不显示表头
            self.display_excel_data_with_original_rows(self.tab1_viewer, display_df, "应打开接口", excel_row_numbers)
        except Exception as e:
            print(f"显示最终筛选数据时发生错误: {e}")
            self.show_empty_message(self.tab1_viewer, "数据过滤失败")
            # 处理失败时也需要更新导出按钮状态
            self.update_export_button_state()

    def display_results2(self, results, show_popup=True):
        """显示需回复接口处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results2 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab2_viewer, "无需回复接口")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        self.processing_results2 = results
        self.has_processed_results2 = True  # 标记已有处理结果
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab2_viewer, display_df, "需回复接口", excel_row_numbers)
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", f"需回复接口数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【需回复接口】选项卡中更新显示。")

    def display_results3(self, results, show_popup=True):
        """显示外部接口ICM处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results3 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab3_viewer, "无外部接口ICM")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        self.processing_results3 = results
        self.has_processed_results3 = True  # 标记已有处理结果
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab3_viewer, display_df, "外部接口ICM", excel_row_numbers)
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", f"外部接口ICM数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【外部接口ICM】选项卡中更新显示。")

    def display_results4(self, results, show_popup=True):
        """显示外部接口单处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results4 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab4_viewer, "无外部接口单")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        self.processing_results4 = results
        self.has_processed_results4 = True  # 标记已有处理结果
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab4_viewer, display_df, "外部接口单", excel_row_numbers)
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", f"外部接口单数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【外部接口单】选项卡中更新显示。")

    def export_results(self):
        current_tab = self.notebook.index(self.notebook.select())
        import main
        export_tasks = []
        # 只导出有数据的部分
        if self.process_file1_var.get() and self.processing_results is not None and isinstance(self.processing_results, pd.DataFrame) and not self.processing_results.empty:
            export_tasks.append(('应打开接口', main.export_result_to_excel, self.processing_results, self.target_file1, self.current_datetime))
        if self.process_file2_var.get() and self.processing_results2 is not None and isinstance(self.processing_results2, pd.DataFrame) and not self.processing_results2.empty:
            export_tasks.append(('需打开接口', main.export_result_to_excel2, self.processing_results2, self.target_file2, self.current_datetime))
        if self.process_file3_var.get() and self.processing_results3 is not None and isinstance(self.processing_results3, pd.DataFrame) and not self.processing_results3.empty:
            if hasattr(main, 'export_result_to_excel3'):
                export_tasks.append(('外部接口ICM', main.export_result_to_excel3, self.processing_results3, self.target_file3, self.current_datetime))
        if self.process_file4_var.get() and self.processing_results4 is not None and isinstance(self.processing_results4, pd.DataFrame) and not self.processing_results4.empty:
            if hasattr(main, 'export_result_to_excel4'):
                export_tasks.append(('外部接口单', main.export_result_to_excel4, self.processing_results4, self.target_file4, self.current_datetime))
        if not export_tasks:
            messagebox.showinfo("导出提示", "无可导出的数据")
            return
        
        # 显示导出等待对话框
        total_count = len(export_tasks)
        export_dialog, progress_label = self.show_export_waiting_dialog("导出结果", "正在导出中，请稍后。。。 。。。", total_count)
        
        # 使用after方法延迟执行导出操作，确保等待对话框能正确显示
        def do_export():
            folder_path = self.path_var.get().strip()
            success_count = 0
            success_messages = []
            
            for i, (name, func, results, original_file, dt) in enumerate(export_tasks, 1):
                # 更新进度
                self.update_export_progress(export_dialog, progress_label, i-1, total_count)
                
                try:
                    output_path = func(results, original_file, dt, folder_path)
                    success_count += 1
                    success_messages.append(f"{name}: {output_path}")
                    
                    # 更新进度显示已完成
                    self.update_export_progress(export_dialog, progress_label, i, total_count)
                    
                except NotImplementedError:
                    self.close_waiting_dialog(export_dialog)
                    messagebox.showwarning(f"导出未实现 - {name}", f"{name}的导出功能尚未实现。")
                    return
                except Exception as e:
                    self.close_waiting_dialog(export_dialog)
                    messagebox.showerror(f"导出失败 - {name}", f"导出过程中发生错误: {str(e)}")
                    return
            
            # 关闭等待对话框
            self.close_waiting_dialog(export_dialog)
            
            # 显示导出成功信息
            if success_count > 0:
                if success_count == 1:
                    messagebox.showinfo("导出完成", f"成功导出 {success_count} 个文件！\n\n{success_messages[0]}")
                else:
                    combined_message = f"成功导出 {success_count} 个文件！\n\n" + "\n".join(success_messages)
                    messagebox.showinfo("导出完成", combined_message)
        
        # 延迟执行导出操作，确保等待对话框能够显示
        self.root.after(100, do_export)

    def toggle_auto_startup(self):
        """切换开机自启动状态"""
        self.config["auto_startup"] = self.auto_startup_var.get()
        self.save_config()
        
        if self.auto_startup_var.get():
            self.add_to_startup()
        else:
            self.remove_from_startup()

    def toggle_close_dialog(self):
        """切换关闭时弹窗提醒状态"""
        # 更新配置：dont_ask_again与show_close_dialog_var是相反的逻辑
        self.config["dont_ask_again"] = not self.show_close_dialog_var.get()
        self.save_config()

    def add_to_startup(self):
        """添加到开机自启动"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 
                               0, winreg.KEY_SET_VALUE)
            
            exe_path = os.path.abspath(sys.argv[0])
            if exe_path.endswith('.py'):
                # 如果是Python脚本，使用python.exe运行
                python_exe = sys.executable
                startup_cmd = f'"{python_exe}" "{exe_path}"'
            else:
                startup_cmd = f'"{exe_path}"'
            
            winreg.SetValueEx(key, "ExcelProcessor", 0, winreg.REG_SZ, startup_cmd)
            winreg.CloseKey(key)
            
        except Exception as e:
            messagebox.showerror("错误", f"设置开机自启动失败: {str(e)}")
            self.auto_startup_var.set(False)

    def remove_from_startup(self):
        """从开机自启动中移除"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 
                               0, winreg.KEY_SET_VALUE)
            
            winreg.DeleteValue(key, "ExcelProcessor")
            winreg.CloseKey(key)
            
        except FileNotFoundError:
            # 如果注册表项不存在，忽略错误
            pass
        except Exception as e:
            messagebox.showerror("错误", f"移除开机自启动失败: {str(e)}")

    def on_window_close(self):
        """窗口关闭事件处理"""
        if self.is_closing:
            return
        
        # 检查是否显示关闭时弹窗提醒（基于设置菜单中的选项）
        if self.show_close_dialog_var.get():
            # 创建自定义对话框询问是否隐藏到后台
            dialog = tk.Toplevel(self.root)
            dialog.title("关闭确认")
            dialog.geometry("300x150")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # 设置对话框图标
            try:
                icon_path = "ico_bin/tubiao.ico"
                if os.path.exists(icon_path):
                    dialog.iconbitmap(icon_path)
            except Exception as e:
                print(f"设置对话框图标失败: {e}")
            
            # 居中显示
            dialog.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50
            ))
            
            tk.Label(dialog, text="是否隐藏到后台运行？").pack(pady=20)
            
            # 添加提示信息
            tip_label = tk.Label(dialog, text="提示：可在设置菜单中关闭此对话框", font=("Microsoft YaHei UI", 8), fg="gray")
            tip_label.pack(pady=(0, 10))
            
            result = {"action": None}
            
            def hide_to_background():
                result["action"] = "hide"
                dialog.destroy()
            
            def close_completely():
                result["action"] = "close"
                dialog.destroy()
            
            button_frame = tk.Frame(dialog)
            button_frame.pack(pady=10)
            
            tk.Button(button_frame, text="隐藏到后台", command=hide_to_background).pack(side=tk.LEFT, padx=5)
            tk.Button(button_frame, text="完全关闭", command=close_completely).pack(side=tk.LEFT, padx=5)
            
            dialog.wait_window()
            
            if result["action"] == "hide":
                self.hide_to_tray()
            elif result["action"] == "close":
                self.quit_application()
        else:
            # 根据保存的设置决定行为
            if self.config.get("minimize_to_tray", True):
                self.hide_to_tray()
            else:
                self.quit_application()

    def hide_to_tray(self):
        """隐藏到系统托盘"""
        if TRAY_AVAILABLE:
            self.root.withdraw()
            self.create_tray_icon()
        else:
            # 系统托盘不可用时，最小化到任务栏并绑定还原事件
            messagebox.showwarning("警告", "系统托盘功能不可用，程序将最小化到任务栏")
            self.root.iconify()
            # 确保任务栏双击能正常还原窗口
            self.root.bind('<FocusIn>', self.on_window_focus)

    def create_tray_icon(self):
        """创建系统托盘图标"""
        if not TRAY_AVAILABLE:
            return
        
        # 使用自定义图标文件
        icon_path = "ico_bin/tubiao.ico"
        try:
            if os.path.exists(icon_path):
                # 加载图标并调整大小
                image = Image.open(icon_path)
                # 将图标调整为适合系统托盘的大小（通常32x32或64x64）
                image = image.resize((32, 32), Image.Resampling.LANCZOS)
            else:
                # 如果图标文件不存在，创建简单的默认图标
                image = Image.new('RGB', (32, 32), color='blue')
        except Exception as e:
            print(f"加载托盘图标失败: {e}")
            # 创建简单的默认图标
            image = Image.new('RGB', (32, 32), color='blue')
        
        # 创建菜单项，首项作为默认双击动作
        show_item = pystray.MenuItem("打开主程序", self.show_window, default=True)
        menu = pystray.Menu(
            show_item,
            pystray.MenuItem("关闭程序", self.quit_application)
        )
        
        # 创建托盘图标
        self.tray_icon = pystray.Icon("ExcelProcessor", image, "Excel数据处理程序", menu)
        
        # 在单独线程中运行托盘图标
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        """显示主窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def on_window_focus(self, event=None):
        """窗口获得焦点时的处理"""
        # 确保窗口正常显示
        if self.root.state() == 'iconic':
            self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def open_monitor(self):
        """打开处理过程监控器"""
        try:
            # 导入监控器模块
            import Monitor
            
            # 使用全局监控器实例，确保与main.py中的日志记录一致
            self.monitor = Monitor.get_monitor()
            
            # 设置父窗口
            if self.monitor.parent is None:
                self.monitor.parent = self.root
            
            # 显示监控器窗口
            self.monitor.show()
            
            # 添加一条欢迎消息
            Monitor.log_message("监控器已打开，等待处理开始...", "SYSTEM")
            
        except Exception as e:
            messagebox.showerror("错误", f"打开监控器失败: {str(e)}")
            print(f"打开监控器失败: {e}")

    def quit_application(self, icon=None, item=None):
        """完全退出应用程序"""
        self.is_closing = True
        
        if self.tray_icon:
            self.tray_icon.stop()
        
        self.root.quit()
        self.root.destroy()

    def run(self):
        """运行应用程序"""
        self.root.mainloop()


def main():
    """主函数"""
    app = ExcelProcessorApp()
    app.run()


if __name__ == "__main__":
    main()
