#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
窗口管理模块 - 负责GUI界面的创建、布局和数据显示
职责单一：仅处理UI展示，与业务逻辑解耦
"""

import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext
import pandas as pd
import os
import sys
from date_utils import is_date_overdue

# 导入数据库状态显示器
try:
    from db_status import DatabaseStatusIndicator, set_db_status_indicator
except ImportError:
    DatabaseStatusIndicator = None
    set_db_status_indicator = None


def get_resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和打包环境"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


class WindowManager:
    """窗口管理器 - 负责所有GUI相关的创建、布局和显示"""
    
    def __init__(self, root, callbacks=None):
        """
        初始化窗口管理器
        
        参数:
            root: Tkinter根窗口对象
            callbacks: 回调函数字典，用于与业务逻辑交互
                {
                    'on_browse_folder': 浏览文件夹回调,
                    'on_browse_export_folder': 浏览导出文件夹回调,
                    'on_refresh_files': 刷新文件列表回调,
                    'on_start_processing': 开始处理回调,
                    'on_export_results': 导出结果回调,
                    'on_open_folder': 打开文件夹回调,
                    'on_open_monitor': 打开监控器回调,
                    'on_settings_menu': 设置菜单回调,
                }
        """
        self.root = root
        self.callbacks = callbacks or {}
        
        # 存储UI组件引用
        self.path_var = None
        self.export_path_var = None
        self.file_info_text = None
        self.notebook = None
        
        # 存储6个选项卡的viewer引用
        self.viewers = {
            'tab1': None,  # 内部需打开接口
            'tab2': None,  # 内部需回复接口
            'tab3': None,  # 外部需打开接口
            'tab4': None,  # 外部需回复接口
            'tab5': None,  # 三维提资接口
            'tab6': None,  # 收发文函
        }
        
        # 存储选项卡frame引用
        self.tab_frames = {}
        
        # 存储选项卡索引
        self.tabs = {
            'tab1': 0,
            'tab2': 1,
            'tab3': 2,
            'tab4': 3,
            'tab5': 4,
            'tab6': 5,
        }
        
        # 存储勾选框变量
        self.process_vars = {}
        
        # 存储按钮引用（供外部控制状态）
        self.buttons = {}
        
    def setup(self, config_data, process_vars, project_vars=None):
        """
        一键初始化完整窗口
        
        参数:
            config_data: 配置数据字典 {'folder_path': ..., 'export_folder_path': ...}
            process_vars: 处理勾选框变量字典 {'tab1': BooleanVar, ...}
            project_vars: 项目号筛选变量字典 {'1818': BooleanVar, ...}
        """
        self.process_vars = process_vars
        self.project_vars = project_vars or {}
        self.setup_window()
        self.create_widgets(config_data)
        
    def setup_window(self):
        """设置主窗口属性"""
        self.root.title("接口筛选程序")
        self.setup_window_size()
        self.root.minsize(1200, 800)
        
        # 设置窗口图标
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置窗口图标失败: {e}")
    
    def setup_window_size(self):
        """设置窗口大小以适配不同分辨率"""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        print(f"检测到屏幕分辨率: {screen_width}x{screen_height}")
        
        if screen_width >= 1920 and screen_height >= 1080:
            # 1920x1080或更高 - 全屏
            self.root.state('zoomed')
        elif screen_width >= 1600 and screen_height >= 900:
            # 1600x900 - 90%屏幕空间
            width = int(screen_width * 0.9)
            height = int(screen_height * 0.9)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        elif screen_width >= 1366 and screen_height >= 768:
            # 1366x768 - 85%屏幕空间
            width = int(screen_width * 0.85)
            height = int(screen_height * 0.85)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        else:
            # 更小分辨率 - 最小推荐尺寸
            width = min(1200, screen_width - 100)
            height = min(800, screen_height - 100)
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        self.root.update_idletasks()
        self.center_window_if_needed()
    
    def center_window_if_needed(self):
        """如果窗口超出屏幕，则居中显示"""
        try:
            window_width = self.root.winfo_width()
            window_height = self.root.winfo_height()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            if x < 0 or y < 0:
                self.root.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception as e:
            print(f"窗口居中失败: {e}")
    
    def create_widgets(self, config_data):
        """创建所有GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)  # 修正：tabs在row=3（path=0, info=1, project_filter=2, tabs=3）
        
        # 创建各个区域
        self.create_path_section(main_frame, config_data)
        self.create_info_section(main_frame)
        self.create_tabs_section(main_frame)
        self.create_button_section(main_frame)
        
        # 左下角数据库状态显示器
        self.db_status = None
        try:
            if DatabaseStatusIndicator:
                self.db_status = DatabaseStatusIndicator(main_frame, row=5, column=0)
                if set_db_status_indicator:
                    set_db_status_indicator(self.db_status)
        except Exception as e:
            print(f"[数据库状态] 初始化失败: {e}")
        
        # 右下角水印 + 版本号
        try:
            footer_frame = ttk.Frame(main_frame)
            footer_frame.grid(row=5, column=2, sticky=tk.E, padx=(0, 4), pady=(6, 2))
            watermark = ttk.Label(footer_frame, text="——by 建筑结构所,王任超", foreground="gray")
            watermark.pack(anchor=tk.E)
            version_text = ""
            try:
                app_ref = getattr(self, 'app', None)
                if app_ref:
                    version_text = getattr(app_ref, 'current_version', '') or ""
            except Exception:
                version_text = ""
            if not version_text:
                version_text = "版本：未知"
            else:
                version_text = f"版本：{version_text}"
            version_label = ttk.Label(footer_frame, text=version_text, foreground="gray")
            version_label.pack(anchor=tk.E)
        except Exception:
            pass
    
    def create_path_section(self, parent, config_data):
        """创建路径选择区域"""
        path_frame = ttk.Frame(parent)
        path_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        path_frame.columnconfigure(1, weight=1)
        
        # 文件夹路径
        ttk.Label(path_frame, text="文件夹路径:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.path_var = tk.StringVar(value=config_data.get("folder_path", ""))
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        
        browse_btn = ttk.Button(
            path_frame, 
            text="浏览", 
            command=lambda: self._trigger_callback('on_browse_folder')
        )
        browse_btn.grid(row=0, column=2, sticky=tk.W)
        
        # 设置菜单按钮
        settings_btn = ttk.Button(
            path_frame, 
            text="⚙", 
            command=lambda: self._trigger_callback('on_settings_menu')
        )
        settings_btn.grid(row=0, column=3, sticky=tk.E, padx=(20, 0))
        
        # 帮助按钮
        help_btn = ttk.Button(
            path_frame, 
            text="❓", 
            width=3,
            command=lambda: self._trigger_callback('on_show_help')
        )
        help_btn.grid(row=0, column=4, sticky=tk.E, padx=(5, 0))
        
        # 导出结果位置
        ttk.Label(path_frame, text="导出结果位置:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(8, 0)
        )
        
        self.export_path_var = tk.StringVar(value=config_data.get("export_folder_path", ""))
        export_entry = ttk.Entry(path_frame, textvariable=self.export_path_var, width=60)
        export_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(8, 0))
        
        export_browse_btn = ttk.Button(
            path_frame, 
            text="浏览", 
            command=lambda: self._trigger_callback('on_browse_export_folder')
        )
        export_browse_btn.grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
    
    def create_info_section(self, parent):
        """创建文件信息显示区域"""
        info_frame = ttk.LabelFrame(parent, text="Excel文件信息", padding="5")
        info_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 0))
        info_frame.columnconfigure(0, weight=1)
        
        # 根据屏幕高度调整文本区域高度（调整为原来的2倍）
        screen_height = self.root.winfo_screenheight()
        if screen_height >= 1080:
            text_height = 12  # 原6 → 12
        elif screen_height >= 900:
            text_height = 10  # 原5 → 10
        else:
            text_height = 8   # 原4 → 8
        
        self.file_info_text = scrolledtext.ScrolledText(
            info_frame, 
            height=text_height, 
            state='disabled'
        )
        self.file_info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 项目号筛选框（紧凑布局）
        project_filter_frame = ttk.LabelFrame(parent, text="项目号筛选", padding="2")
        project_filter_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 0))
        
        # 获取项目号变量（从回调参数传入）
        project_vars = getattr(self, 'project_vars', {})
        
        # 创建7个项目号复选框，横向排列
        projects = [
            ('1818', project_vars.get('1818')),
            ('1907', project_vars.get('1907')),
            ('1915', project_vars.get('1915')),
            ('1916', project_vars.get('1916')),
            ('2016', project_vars.get('2016')),
            ('2026', project_vars.get('2026')),
            ('2306', project_vars.get('2306'))
        ]
        
        for idx, (project_id, var) in enumerate(projects):
            if var:
                cb = ttk.Checkbutton(
                    project_filter_frame,
                    text=f"项目 {project_id}",
                    variable=var
                )
                cb.grid(row=0, column=idx, padx=5, pady=2, sticky=tk.W)
    
    def create_tabs_section(self, parent):
        """创建选项卡区域"""
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 创建6个选项卡
        self.create_tabs()
    
    def create_tabs(self):
        """创建6个选项卡"""
        tab_configs = [
            ('tab1', "内部需打开接口"),
            ('tab2', "内部需回复接口"),
            ('tab3', "外部需打开接口"),
            ('tab4', "外部需回复接口"),
            ('tab5', "三维提资接口"),
            ('tab6', "收发文函"),
        ]
        
        for tab_id, tab_text in tab_configs:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=tab_text)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
            
            # 添加勾选框
            if tab_id in self.process_vars:
                check = ttk.Checkbutton(
                    frame, 
                    text=f"处理{tab_text}", 
                    variable=self.process_vars[tab_id]
                )
                check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
            
            # 创建Excel预览控件
            self.create_excel_viewer(frame, tab_id, tab_text)
            
            # 保存frame引用
            self.tab_frames[tab_id] = frame
        
        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed_internal)
    
    def create_excel_viewer(self, parent, tab_id, tab_name):
        """
        为选项卡创建Excel预览控件（带滚动条）
        
        功能增强：
        1. 完整显示所有数据（不再限制20行）
        2. 添加垂直和水平滚动条
        3. 支持多选和复制功能（Ctrl+C或右键菜单）
        """
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        
        # 创建Treeview用于Excel预览，设置为extended模式支持多选
        viewer = ttk.Treeview(parent, selectmode='extended')
        viewer.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 添加垂直滚动条
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=viewer.yview)
        v_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        viewer.configure(yscrollcommand=v_scrollbar.set)
        
        # 添加水平滚动条
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=viewer.xview)
        h_scrollbar.grid(row=2, column=0, sticky=(tk.W, tk.E))
        viewer.configure(xscrollcommand=h_scrollbar.set)
        
        # 绑定Ctrl+C快捷键复制选中内容
        viewer.bind('<Control-c>', lambda e: self._copy_selected_rows(viewer))
        viewer.bind('<Control-C>', lambda e: self._copy_selected_rows(viewer))
        
        # 创建右键菜单
        self._create_context_menu(viewer)
        
        # 存储viewer引用
        self.viewers[tab_id] = viewer
        
        # 默认显示提示信息
        self.show_empty_message(viewer, f"等待{tab_name}...")
    
    def create_button_section(self, parent):
        """创建按钮区域"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(10, 0))
        
        # 开始处理按钮
        process_btn = ttk.Button(
            button_frame,
            text="开始处理",
            command=lambda: self._trigger_callback('on_start_processing'),
            style="Accent.TButton"
        )
        process_btn.pack(side=tk.LEFT, padx=(0, 20))
        self.buttons['process'] = process_btn
        
        # 导出结果按钮
        export_btn = ttk.Button(
            button_frame,
            text="导出结果",
            command=lambda: self._trigger_callback('on_export_results'),
            state='disabled'
        )
        export_btn.pack(side=tk.LEFT)
        self.buttons['export'] = export_btn
        
        # 打开文件位置按钮
        open_folder_btn = ttk.Button(
            button_frame,
            text="打开文件位置",
            command=lambda: self._trigger_callback('on_open_folder')
        )
        open_folder_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.buttons['open_folder'] = open_folder_btn
        
        # 刷新文件列表按钮
        refresh_btn = ttk.Button(
            button_frame,
            text="刷新文件列表",
            command=lambda: self._trigger_callback('on_refresh_files')
        )
        refresh_btn.pack(side=tk.LEFT, padx=(20, 0))
        self.buttons['refresh'] = refresh_btn
        
        # 打开监控按钮
        monitor_btn = ttk.Button(
            button_frame,
            text="打开监控",
            command=lambda: self._trigger_callback('on_open_monitor')
        )
        monitor_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.buttons['monitor'] = monitor_btn
        
        # 【新增】指派任务按钮
        assignment_btn = ttk.Button(
            button_frame,
            text="📋 指派任务",
            command=lambda: self._trigger_callback('on_assignment_click')
        )
        assignment_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.buttons['assignment'] = assignment_btn
        
        # 【新增】历史查询按钮
        history_btn = ttk.Button(
            button_frame,
            text="🔍 历史查询",
            command=lambda: self._trigger_callback('on_history_query_click')
        )
        history_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.buttons['history_query'] = history_btn
        
        # 【新增】忽略延期项按钮（仅所领导可见）
        ignore_overdue_btn = ttk.Button(
            button_frame,
            text="🚫 忽略延期项",
            command=lambda: self._trigger_callback('on_ignore_overdue_click')
        )
        ignore_overdue_btn.pack(side=tk.LEFT, padx=(10, 0))
        self.buttons['ignore_overdue'] = ignore_overdue_btn
    
    def show_empty_message(self, viewer, message):
        """在viewer中显示提示信息"""
        # 清空现有内容
        for item in viewer.get_children():
            viewer.delete(item)
        
        # 创建默认列
        default_columns = ["A列", "B列", "H列", "K列", "M列"]
        viewer["columns"] = default_columns
        viewer["show"] = "tree headings"
        
        # 配置序号列
        viewer.column("#0", width=60, minwidth=60, anchor='center')
        viewer.heading("#0", text="行号")
        
        # 配置数据列
        for col in default_columns:
            viewer.heading(col, text=col)
            viewer.column(col, width=120, minwidth=100, anchor='center')
        
        # 插入提示信息
        empty_values = [message] + [""] * (len(default_columns) - 1)
        viewer.insert("", "end", text="", values=empty_values)
    
    def display_excel_data(self, viewer, df, tab_name, show_all=False, original_row_numbers=None, source_files=None, file_manager=None, current_user_roles=None):
        """
        在viewer中显示Excel数据
        
        功能增强：
        1. 支持显示全部数据（show_all=True）
        2. 自动配置滚动条
        3. 支持原始行号显示
        4. 支持勾选框点击事件
        5. 支持按用户角色筛选显示数据
        
        参数:
            viewer: Treeview控件
            df: pandas DataFrame数据
            tab_name: 选项卡名称
            source_files: 源文件路径列表（用于勾选状态管理）
            file_manager: 文件管理器实例（用于勾选状态持久化）
            show_all: 是否显示全部数据（True=全部，False=仅前20行）
            original_row_numbers: 原始Excel行号列表（可选）
            current_user_roles: 当前用户的角色列表（用于筛选显示，如["设计人员", "2016接口工程师"]）
        """
        # 清空现有内容
        for item in viewer.get_children():
            viewer.delete(item)
        
        if df is None or df.empty:
            self.show_empty_message(viewer, f"无{tab_name}数据")
            return
        
        # 【新增】如果提供了用户角色，进行筛选
        filtered_df = df.copy()
        if current_user_roles and "角色来源" in filtered_df.columns:
            # 筛选包含任一用户角色的数据行
            def contains_any_role(role_str):
                if pd.isna(role_str):
                    # 没有角色来源的数据也显示（宽松筛选，避免遗漏）
                    return True
                role_str = str(role_str).strip()
                if not role_str or role_str.lower() == 'nan':
                    return True
                # 检查是否包含任一用户角色
                return any(role in role_str for role in current_user_roles)
            
            mask = filtered_df["角色来源"].apply(contains_any_role)
            filtered_df = filtered_df[mask].copy()
            
            # 同步更新原始行号列表
            if original_row_numbers is not None and "原始行号" in filtered_df.columns:
                original_row_numbers = list(filtered_df["原始行号"])
        
        # 【关键修复】重置索引，确保iloc位置索引与Treeview行索引一致
        # 避免跨项目错误写入！
        filtered_df = filtered_df.reset_index(drop=True)
        
        # 【重大修复】勾选框状态从Registry读取，不再依赖缓存
        # completed_rows_set现在用于存储confirmed_at的task_id
        completed_rows_set = set()  # 暂时保留，后面改为从Registry读取
        
        # 优化显示列（仅显示关键列）
        display_df = self._create_optimized_display(filtered_df, tab_name, completed_rows=completed_rows_set)
        
        # 【Registry状态提醒】批量查询任务状态和确认状态
        registry_status_map = {}
        registry_confirmed_map = {}  # 【新增】存储确认状态 {df_idx: (confirmed_by, current_user_name)}
        try:
            from registry import hooks as registry_hooks
            from registry.util import extract_interface_id, extract_project_id
            from registry.db import get_connection
            from registry.config import load_config
            
            # 根据tab_name确定file_type
            file_type_map = {
                "内部需打开接口": 1,
                "内部需回复接口": 2,
                "外部需打开接口": 3,
                "外部需回复接口": 4,
                "三维提资接口": 5,  # 【修复】应该是"三维提资接口"，不是"待处理文件5"
                "收发文函": 6       # 【修复】应该是"收发文函"，不是"待处理文件6"
            }
            file_type = file_type_map.get(tab_name)
            
            if file_type and source_files:
                # 构造task_keys
                task_keys = []
                for idx in range(len(display_df)):
                    try:
                        row_data = display_df.iloc[idx]
                        interface_id = extract_interface_id(row_data, file_type)
                        project_id = extract_project_id(row_data, file_type)
                        row_index = original_row_numbers[idx] if original_row_numbers and idx < len(original_row_numbers) else idx + 2
                        
                        # 获取接口时间（用于判断是否延期）
                        interface_time = ""
                        if "接口时间" in row_data.index:
                            time_val = row_data["接口时间"]
                            if pd.notna(time_val) and str(time_val).strip():
                                interface_time = str(time_val).strip()
                        
                        # 【修复Bug】遍历所有源文件查找匹配的任务
                        # 因为我们不知道每行数据来自哪个文件，所以尝试所有文件
                        if interface_id and project_id:
                            for source_file in source_files:
                                from registry.util import make_task_id
                                task_key = {
                                    'file_type': file_type,
                                    'project_id': project_id,
                                    'interface_id': interface_id,
                                    'source_file': source_file,
                                    'row_index': row_index,
                                    'interface_time': interface_time  # 新增：传递接口时间
                                }
                                task_keys.append((idx, task_key))
                    except Exception as e:
                        continue
                
                # 批量查询
                if task_keys:
                    task_keys_only = [tk[1] for tk in task_keys]
                    # 【新增】传递当前用户角色列表
                    user_roles_str = ','.join(current_user_roles) if current_user_roles else ''
                    registry_status_map_raw = registry_hooks.get_display_status(task_keys_only, user_roles_str)
                    
                    # 【新增】查询确认状态（confirmed_at, confirmed_by）
                    cfg = load_config()
                    db_path = cfg.get('registry_db_path', 'registry/task_registry.db')
                    wal = cfg.get('registry_use_wal', True)
                    conn = get_connection(db_path, wal)
                    current_user_name = getattr(self.app, 'user_name', '').strip()
                    
                    # 映射回display_df的索引（取第一个匹配的状态）
                    for df_idx, task_key in task_keys:
                        from registry.util import make_task_id
                        tid = make_task_id(
                            task_key['file_type'],
                            task_key['project_id'],
                            task_key['interface_id'],
                            task_key['source_file'],
                            task_key['row_index']
                        )
                        if tid in registry_status_map_raw and df_idx not in registry_status_map:
                            # 只使用第一个匹配的状态（避免重复）
                            registry_status_map[df_idx] = registry_status_map_raw[tid]
                        
                        # 查询confirmed_by
                        if df_idx not in registry_confirmed_map:
                            try:
                                row = conn.execute(
                                    "SELECT confirmed_by FROM tasks WHERE id = ?",
                                    (tid,)
                                ).fetchone()
                                if row and row[0]:
                                    registry_confirmed_map[df_idx] = (row[0], current_user_name)
                            except:
                                pass
        except Exception as e:
            print(f"[Registry] 状态查询失败（不影响主流程）: {e}")
        
        # 【关键修复】根据registry_confirmed_map更新勾选框状态
        if registry_confirmed_map and "是否已完成" in display_df.columns:
            checkbox_col_idx = list(display_df.columns).index("是否已完成")
            for df_idx, (confirmed_by, current_user) in registry_confirmed_map.items():
                if df_idx < len(display_df):
                    # 有confirmed_by说明已确认，显示勾选
                    display_df.iloc[df_idx, checkbox_col_idx] = "☑"
            print(f"[Registry] 已从Registry读取{len(registry_confirmed_map)}个确认状态")
        
        # 【新增】填充"状态"列：优先显示Registry状态，其次显示延期标记
        # 【新增】处理"接口时间"列：空值显示为"-"
        if "接口时间" in display_df.columns:
            # 处理空值
            time_values = []
            status_values = []
            for idx in range(len(display_df)):
                try:
                    time_value = display_df.iloc[idx]["接口时间"]
                    # 空值处理
                    if pd.isna(time_value) or str(time_value).strip() == '':
                        time_str = '-'
                    else:
                        time_str = str(time_value).strip()
                    time_values.append(time_str)
                    
                    # 【修复】状态判断：Registry状态已包含延期信息，直接使用
                    if "状态" in display_df.columns:
                        registry_status = registry_status_map.get(idx, '')
                        is_overdue = time_str != '-' and is_date_overdue(time_str)
                        
                        if registry_status:
                            # Registry状态（已包含延期前缀，如果适用）
                            status_values.append(registry_status)
                        elif is_overdue:
                            # 无Registry状态但延期：显示延期标记
                            status_values.append("⚠️")
                        else:
                            # 正常无标记
                            status_values.append("")
                except Exception:
                    time_values.append('-')
                    if "状态" in display_df.columns:
                        status_values.append("")
            
            display_df["接口时间"] = time_values
            if "状态" in display_df.columns:
                display_df["状态"] = status_values
        
        # 【新增】过滤掉已确认的任务（status_map中值为空字符串''）
        if registry_status_map:
            exclude_indices = []
            for idx, status_text in registry_status_map.items():
                if status_text == '':  # 空字符串表示已确认
                    exclude_indices.append(idx)
            
            if exclude_indices:
                display_df = display_df.drop(display_df.index[exclude_indices]).reset_index(drop=True)
                print(f"[Registry] 过滤掉{len(exclude_indices)}个已确认的任务，剩余{len(display_df)}行")
        
        # 【新增】处理"责任人"列：空值显示为"无"
        if "责任人" in display_df.columns:
            responsible_values = []
            for idx in range(len(display_df)):
                try:
                    responsible_value = display_df.iloc[idx]["责任人"]
                    # 空值处理
                    if pd.isna(responsible_value) or str(responsible_value).strip() == '':
                        resp_str = '无'
                    else:
                        resp_str = str(responsible_value).strip()
                    responsible_values.append(resp_str)
                except Exception:
                    responsible_values.append('无')
            
            display_df["责任人"] = responsible_values
        
        # 【新增】保留"接口时间"列用于GUI显示
        columns = list(display_df.columns)
        
        viewer["columns"] = columns
        viewer["show"] = "tree headings"
        
        # 配置数据列（使用固定列宽方案）
        # 方案C - 平衡布局
        fixed_column_widths = {
            '状态': 140,  # 扩大以容纳Emoji状态文本
            '项目号': 75,
            '接口号': 240,
            '接口时间': 85,
            '责任人': 100,  # 新增责任人列
            '是否已完成': 95
        }
        
        # 其他列自动计算
        column_widths = []
        for col in columns:
            if col in fixed_column_widths:
                column_widths.append(fixed_column_widths[col])
            else:
                # 其他列（如科室、责任人）自动计算
                column_widths.append(self._calculate_single_column_width(display_df, col))
        
        # 配置序号列（宽度与接口号列一致）
        # 如果有项目号列，接口号在第二列(索引1)；否则在第一列(索引0)
        interface_col_idx = 1 if "项目号" in columns else 0
        row_number_width = column_widths[interface_col_idx] if len(column_widths) > interface_col_idx else 60
        viewer.column("#0", width=row_number_width, minwidth=row_number_width)
        viewer.heading("#0", text="行号")
        
        # 配置列对齐方式
        column_alignment = {
            '状态': 'center',
            '项目号': 'center',
            '接口号': 'w',  # 左对齐
            '接口时间': 'center',
            '责任人': 'center',  # 新增责任人列对齐方式
            '是否已完成': 'center'
        }
        
        for i, col in enumerate(columns):
            col_width = column_widths[i] if i < len(column_widths) else 100
            alignment = column_alignment.get(col, 'center')
            
            # 为所有列添加排序功能（点击列头排序）
            # 使用 lambda 的技巧：通过 c=col 固定变量，避免闭包问题
            viewer.heading(col, text=str(col), 
                         command=lambda c=col: self._sort_by_column(viewer, c, tab_name))
            
            viewer.column(col, width=col_width, minwidth=col_width, anchor=alignment)
        
        # 配置延期数据的标签（在插入数据前配置）
        # 【重要】ttk.Treeview在Windows系统主题下的限制：
        #   - background: 通常不生效（被主题锁定）
        #   - foreground: 部分主题支持
        #   - font: 完全支持
        # 策略：使用 深红色前景 + 加粗 + 斜体 的组合来最大化视觉冲击
        try:
            # 方案：深红色 + 加粗 + 斜体
            viewer.tag_configure('overdue', 
                                foreground='#8B0000',         # 深红色/暗红色（DarkRed）
                                font=('', 10, 'bold italic')) # 加粗+斜体，字号稍大
        except Exception as e:
            print(f"[错误] tag配置失败: {e}")
        
        # 【关键】创建item元数据映射字典，存储每行的关键信息（不受排序影响）
        if not hasattr(self, '_item_metadata'):
            self._item_metadata = {}
        
        # 添加数据行
        max_rows = len(display_df) if show_all else min(20, len(display_df))
        
        for index in range(max_rows):
            # 用于显示的行（display_df）
            display_row = display_df.iloc[index]
            
            # 【关键修复】用于元数据的行（filtered_df，包含完整原始数据）
            # display_df可能不包含source_file等列，必须从filtered_df读取
            metadata_row = filtered_df.iloc[index] if index < len(filtered_df) else display_row
            
            # 处理数据显示格式（仅显示过滤后的列，不包括"接口时间"）
            display_values = []
            for col in columns:  # 只遍历要显示的列
                val = display_row[col]
                
                if pd.isna(val):
                    display_values.append("")
                elif isinstance(val, (int, float)):
                    if isinstance(val, float) and val.is_integer():
                        display_values.append(str(int(val)))
                    else:
                        display_values.append(str(val))
                else:
                    display_values.append(str(val))
            
            # 判断是否为延期数据（用于应用tag样式）
            is_overdue_flag = False
            if "接口时间" in display_df.columns and index < len(display_df):
                try:
                    time_value = display_df.iloc[index]["接口时间"]
                    is_overdue_flag = is_date_overdue(str(time_value) if not pd.isna(time_value) else "")
                except Exception:
                    is_overdue_flag = False
            
            # 确定行号显示
            if original_row_numbers and index < len(original_row_numbers):
                row_number_display = original_row_numbers[index]
                display_text = str(row_number_display)
            else:
                display_text = str(index + 1)
            
            # 应用标签
            tags = ('overdue',) if is_overdue_flag else ()
            item_id = viewer.insert("", "end", text=display_text, values=display_values, tags=tags)
            
            # 【关键修复】存储元数据到映射字典，包含原始行信息（不受排序影响）
            # 注意：必须从filtered_df（原始完整数据）读取，而不是display_df（优化显示数据）
            
            # 获取项目号
            project_id_val = ''
            if '项目号' in metadata_row.index:
                project_id_val = str(metadata_row.get('项目号', ''))
            elif '项目号' in display_row.index:
                project_id_val = str(display_row.get('项目号', ''))
            
            # 获取接口号（尝试多个可能的列名）
            interface_id_val = ''
            for col_name in ['接口号', 'interface_id', '接口编号']:
                if col_name in metadata_row.index:
                    interface_id_val = str(metadata_row.get(col_name, ''))
                    break
                elif col_name in display_row.index:
                    interface_id_val = str(display_row.get(col_name, ''))
                    break
            
            metadata = {
                'original_index': index,  # 在filtered_df中的索引
                'original_row': original_row_numbers[index] if original_row_numbers and index < len(original_row_numbers) else index + 2,
                'source_file': metadata_row.get('source_file', '') if 'source_file' in metadata_row.index else '',
                'project_id': project_id_val,
                'interface_id': interface_id_val,
                'source_column': metadata_row.get('_source_column', None) if '_source_column' in metadata_row.index else None,
            }
            self._item_metadata[(viewer, item_id)] = metadata
            
            # 【优化】收集警告，循环结束后汇总输出
            if not interface_id_val:
                _empty_interface_count = getattr(self, '_empty_interface_count', 0) + 1
                setattr(self, '_empty_interface_count', _empty_interface_count)
            if not metadata['source_file']:
                _empty_source_count = getattr(self, '_empty_source_count', 0) + 1
                setattr(self, '_empty_source_count', _empty_source_count)
        
        # 【优化】汇总输出警告
        _empty_interface_count = getattr(self, '_empty_interface_count', 0)
        _empty_source_count = getattr(self, '_empty_source_count', 0)
        if _empty_interface_count > 0 or _empty_source_count > 0:
            warn_parts = []
            if _empty_interface_count > 0:
                warn_parts.append(f"{_empty_interface_count}行接口号为空")
            if _empty_source_count > 0:
                warn_parts.append(f"{_empty_source_count}行source_file为空")
            print(f"[警告] {tab_name}: {', '.join(warn_parts)}")
        # 重置计数器
        self._empty_interface_count = 0
        self._empty_source_count = 0
        
        # 如果有更多行未显示，添加提示
        if not show_all and len(display_df) > 20:
            viewer.insert("", "end", text="...", 
                         values=["...（其他行已省略显示）"] + [""] * (len(columns) - 1))
        
        # 绑定点击事件处理勾选功能
        if file_manager and source_files and "是否已完成" in columns:
            self._bind_checkbox_click_event(viewer, df, display_df, columns, 
                                           original_row_numbers, source_files, 
                                           file_manager, tab_name)
        
        # 【新增】绑定接口号点击事件（用于回文单号输入）
        if "接口号" in columns:
            self._bind_interface_click_event(viewer, df, display_df, columns,
                                            original_row_numbers, tab_name, file_manager)
        
        print(f"{tab_name}数据加载完成：{len(df)} 行，{len(df.columns)} 列 -> 显示：{max_rows} 行，{len(display_df.columns)} 列")
    
    def _bind_checkbox_click_event(self, viewer, original_df, display_df, columns, 
                                    original_row_numbers, source_files, file_manager, tab_name):
        """
        绑定Treeview的点击事件，处理"是否已完成"列的勾选切换
        
        参数:
            viewer: Treeview控件
            original_df: 原始DataFrame（包含"原始行号"列）
            display_df: 显示用DataFrame（优化后的列）
            columns: 显示列名列表
            original_row_numbers: 原始Excel行号列表
            source_files: 源文件路径列表
            file_manager: 文件管理器实例
            tab_name: 选项卡名称
        """
        # 找到"是否已完成"列的索引
        try:
            checkbox_col_idx = columns.index("是否已完成")
        except ValueError:
            return  # 没有"是否已完成"列，不绑定事件
        
        def on_click(event):
            """点击事件处理函数"""
            try:
                # 获取点击位置的信息
                region = viewer.identify_region(event.x, event.y)
                
                if region != "cell":
                    return
                
                # 获取点击的列和行
                column_id = viewer.identify_column(event.x)
                item_id = viewer.identify_row(event.y)
                
                if not item_id:
                    return
                
                # 判断是否点击了"是否已完成"列
                # 列ID格式: "#1", "#2", "#3"...（#0是行号列）
                col_num = int(column_id.replace("#", "")) if column_id != "#0" else 0
                
                # 检查是否点击的是"是否已完成"列（列索引从1开始，因为#0是行号）
                if col_num != (checkbox_col_idx + 1):
                    return
                
                # 【关键修复】从元数据映射字典获取数据，不受排序影响
                metadata = self._item_metadata.get((viewer, item_id))
                if not metadata:
                    # 兜底：使用旧逻辑（位置索引）
                    print(f"[警告] 未找到item元数据（勾选框），使用位置索引（可能不准确）")
                    item_index = viewer.index(item_id)
                    original_row = original_row_numbers[item_index] if original_row_numbers and item_index < len(original_row_numbers) else item_index + 2
                    source_file = source_files[0] if len(source_files) == 1 else self._find_source_file(original_df, item_index, source_files)
                else:
                    # 从元数据提取信息
                    original_row = metadata['original_row']
                    source_file = metadata['source_file']
                
                if not source_files:
                    print("未提供源文件信息")
                    return
                
                if not source_file:
                    print(f"[错误] 无法确定源文件")
                    return
                
                # 【重大修复】勾选框逻辑从Registry读取和写入，不再使用缓存
                user_name = getattr(self.app, 'user_name', '').strip()
                user_roles = getattr(self.app, 'user_roles', [])
                
                # 判断是否为上级角色
                is_superior = any(keyword in ''.join(user_roles) for keyword in ['所领导', '室主任', '接口工程师'])
                
                # 获取当前勾选状态（从UI读取）
                current_values = list(viewer.item(item_id, "values"))
                if checkbox_col_idx >= len(current_values):
                    return
                
                current_checkbox = current_values[checkbox_col_idx]
                is_currently_checked = (current_checkbox == "☑")
                
                # 【核心逻辑】上级角色点击勾选框 = 确认/取消确认
                if is_superior:
                    try:
                        from registry import hooks as registry_hooks
                        
                        # 根据tab_name确定file_type
                        file_type_map = {
                            "内部需打开接口": 1,
                            "内部需回复接口": 2,
                            "外部需打开接口": 3,
                            "外部需回复接口": 4,
                            "三维提资接口": 5,
                            "收发文函": 6
                        }
                        file_type = file_type_map.get(tab_name)
                        
                        if not file_type:
                            print(f"[错误] 无法识别tab_name: {tab_name}")
                            return
                        
                        # 从元数据获取项目号和接口号
                        project_id = metadata.get('project_id', '')
                        interface_id = metadata.get('interface_id', '')
                        
                        if not project_id or not interface_id:
                            print(f"[错误] 无法获取项目号或接口号")
                            return
                        
                        # 【关键修复】去除接口号中的角色后缀（如"(一室主任)"）
                        # 因为Registry中存储的接口号不含角色后缀
                        import re
                        interface_id_clean = re.sub(r'\([^)]*\)$', '', interface_id).strip()
                        print(f"[Registry] 接口号处理: {interface_id} -> {interface_id_clean}")
                        
                        # 构造task_key（使用清理后的接口号）
                        task_key = {
                            'file_type': file_type,
                            'project_id': project_id,
                            'interface_id': interface_id_clean,
                            'source_file': source_file,
                            'row_index': original_row
                        }
                        
                        # 【关键修复】查询任务的当前状态，确保只能确认已完成的任务
                        from registry.util import make_task_id
                        from registry.db import get_connection
                        
                        # 获取Registry配置
                        try:
                            cfg = registry_hooks._cfg()
                            db_path = cfg.get('registry_db_path')
                            wal = bool(cfg.get('registry_wal', True))
                        except:
                            print(f"[Registry] 无法获取数据库配置")
                            return
                        
                        # 查询任务状态
                        tid = make_task_id(
                            file_type, project_id, interface_id_clean,
                            source_file, original_row
                        )
                        
                        conn = get_connection(db_path, wal)
                        cursor = conn.execute(
                            "SELECT status, confirmed_at FROM tasks WHERE id = ?",
                            (tid,)
                        )
                        task_row = cursor.fetchone()
                        
                        if not task_row:
                            print(f"[Registry] 警告：找不到任务记录 {interface_id_clean}")
                            import tkinter.messagebox as messagebox
                            messagebox.showwarning("提示", f"找不到任务记录：{interface_id_clean}")
                            return
                        
                        task_status, confirmed_at = task_row
                        
                        if is_currently_checked:
                            # 当前已勾选 → 取消确认
                            # 只有已确认的任务（status='confirmed'）才能取消确认
                            if task_status != 'confirmed':
                                print(f"[Registry] 错误：任务状态不是已确认，无法取消确认 (status={task_status})")
                                import tkinter.messagebox as messagebox
                                messagebox.showwarning("操作失败", f"该任务状态不是已确认，无法取消确认\n当前状态：{task_status}")
                                return
                            
                            registry_hooks.on_unconfirmed_by_superior(
                                key=task_key,
                                user_name=user_name
                            )
                            print(f"[Registry] 取消确认：{interface_id_clean}")
                            
                            # 更新UI
                            current_values[checkbox_col_idx] = "☐"
                            viewer.item(item_id, values=current_values)
                        else:
                            # 当前未勾选 → 确认
                            # 【严格权限控制】只有已完成的任务（status='completed'）才能被确认
                            if task_status != 'completed':
                                print(f"[Registry] 权限检查失败：任务状态不是待审查，无法确认 (status={task_status})")
                                import tkinter.messagebox as messagebox
                                if task_status == 'open':
                                    messagebox.showwarning(
                                        "操作失败", 
                                        f"该任务尚未完成，无法确认\n\n接口号：{interface_id_clean}\n当前状态：待完成\n\n只有设计人员完成后（状态变为\"待审查\"），上级才能进行确认。"
                                    )
                                elif task_status == 'confirmed':
                                    messagebox.showinfo("提示", f"该任务已经被确认过了\n接口号：{interface_id_clean}")
                                else:
                                    messagebox.showwarning("操作失败", f"该任务状态异常，无法确认\n接口号：{interface_id_clean}\n当前状态：{task_status}")
                                return
                            
                            # 状态检查通过，执行确认
                            registry_hooks.on_confirmed_by_superior(
                                file_type=file_type,
                                file_path=source_file,
                                row_index=original_row,
                                user_name=user_name,
                                project_id=project_id,
                                interface_id=interface_id_clean
                            )
                            print(f"[Registry] 确认成功：{interface_id_clean} (status=completed -> confirmed)")
                            
                            # 更新UI：先标记为已勾选
                            current_values[checkbox_col_idx] = "☑"
                            viewer.item(item_id, values=current_values)
                        
                        # 【关键修复】确认/取消确认后，延迟刷新整个tab显示
                        # 这样已确认的任务会被过滤掉，不再显示
                        if hasattr(self, 'app') and self.app:
                            # 使用after延迟100ms执行，确保Registry操作完成
                            viewer.after(100, self.app.refresh_current_tab_display)
                            print(f"[Registry] 已触发刷新显示")
                        else:
                            # 兜底：至少刷新UI
                            viewer.update_idletasks()
                        
                    except Exception as e:
                        print(f"[Registry] 确认/取消确认失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    # 设计人员角色：不应该通过勾选框操作，应该通过填写回文单号来完成
                    print(f"[提示] 设计人员角色请通过填写回文单号来标记完成，勾选框仅供上级角色使用")
                
            except Exception as e:
                print(f"点击事件处理失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 先解绑旧的事件，避免重复绑定
        # 使用标签化绑定，只绑定我们自己的处理器
        bind_tag = f"checkbox_click_{tab_name}"
        
        # 如果已经绑定过，先解绑
        try:
            viewer.unbind_class(bind_tag, "<Button-1>")
        except:
            pass
        
        # 给viewer添加这个标签
        tags = list(viewer.bindtags())
        if bind_tag not in tags:
            # 插入到第一个位置，确保我们的处理器优先
            tags.insert(0, bind_tag)
            viewer.bindtags(tuple(tags))
        
        # 绑定到这个特定标签，不使用add="+"
        viewer.bind_class(bind_tag, "<Button-1>", on_click)
    
    def _find_source_file(self, original_df, item_index, source_files):
        """
        从多个源文件中找到当前行对应的文件
        
        策略：根据"项目号"列匹配（如果有）
        """
        try:
            if "项目号" in original_df.columns and item_index < len(original_df):
                project_id = str(original_df.iloc[item_index]["项目号"])
                # 从文件名中匹配项目号
                for file_path in source_files:
                    if project_id in file_path:
                        return file_path
            
            # 默认返回第一个文件
            return source_files[0] if source_files else None
        except Exception as e:
            print(f"查找源文件失败: {e}")
            return source_files[0] if source_files else None
    
    def _bind_interface_click_event(self, viewer, original_df, display_df, columns,
                                     original_row_numbers, tab_name, file_manager=None):
        """
        绑定Treeview的点击事件，处理"接口号"列的点击（用于回文单号输入）
        
        参数:
            viewer: Treeview控件
            original_df: 原始DataFrame（包含_source_column、source_file等信息）
            display_df: 显示用DataFrame
            columns: 显示列名列表
            original_row_numbers: 原始Excel行号列表
            tab_name: 选项卡名称
            file_manager: 文件管理器实例（用于自动勾选）
        """
        # 检查是否是处理后的数据（包含source_file列）
        if 'source_file' not in original_df.columns:
            # 原始数据（未处理），不支持回文单号输入功能
            return
        
        # 找到"接口号"列的索引
        try:
            interface_col_idx = columns.index("接口号")
        except ValueError:
            return  # 没有"接口号"列，不绑定事件
        
        def on_interface_click(event):
            """点击接口号列的事件处理函数"""
            try:
                # 获取点击位置的信息
                region = viewer.identify_region(event.x, event.y)
                
                if region != "cell":
                    return
                
                # 获取点击的列和行
                column_id = viewer.identify_column(event.x)
                item_id = viewer.identify_row(event.y)
                
                if not item_id:
                    return
                
                # 判断是否点击了"接口号"列
                # 列ID格式: "#1", "#2", "#3"...（#0是行号列）
                col_num = int(column_id.replace("#", "")) if column_id != "#0" else 0
                
                # 检查是否点击的是"接口号"列（列索引从1开始，因为#0是行号）
                if col_num != (interface_col_idx + 1):
                    return
                
                # 【关键修复】从元数据映射字典获取数据，不受排序影响
                metadata = self._item_metadata.get((viewer, item_id))
                if not metadata:
                    # 兜底：使用旧逻辑（位置索引）
                    print(f"[警告] 未找到item元数据，使用位置索引（可能不准确）")
                    item_index = viewer.index(item_id)
                    metadata = {
                        'original_index': item_index,
                        'original_row': original_row_numbers[item_index] if original_row_numbers and item_index < len(original_row_numbers) else item_index + 2,
                        'source_file': original_df.iloc[item_index]['source_file'] if item_index < len(original_df) and 'source_file' in original_df.columns else '',
                        'project_id': str(original_df.iloc[item_index]['项目号']) if item_index < len(original_df) and '项目号' in original_df.columns else '',
                        'interface_id': '',
                        'source_column': None,
                    }
                
                # 从元数据提取信息
                original_row = metadata['original_row']
                source_file = metadata['source_file']
                project_id = str(metadata['project_id'])
                source_column = metadata['source_column']
                
                # 获取行数据
                item_values = viewer.item(item_id, "values")
                if not item_values or interface_col_idx >= len(item_values):
                    return
                
                # 从UI读取接口号（因为可能带角色后缀）
                interface_id = item_values[interface_col_idx]
                
                # 获取文件类型（根据选项卡名称）
                file_type = self._get_file_type_from_tab(tab_name)
                
                # 【调试】打印详细信息
                print(f"[回文输入] item_id: {item_id}")
                print(f"[回文输入] 接口号(UI): {interface_id}")
                print(f"[回文输入] 源文件: {os.path.basename(source_file) if source_file else 'N/A'}")
                print(f"[回文输入] 项目号: {project_id}")
                print(f"[回文输入] Excel行号: {original_row}")
                
                if not source_file:
                    print(f"[错误] 无法确定源文件")
                    from tkinter import messagebox
                    messagebox.showerror("错误", "无法获取源文件信息，请联系管理员", parent=viewer)
                    return
                
                if not project_id:
                    # 尝试从source_file提取
                    source_file_name = os.path.basename(source_file)
                    import re
                    match = re.search(r'(\d{4})', source_file_name)
                    project_id = match.group(1) if match else ""
                    print(f"[回文输入] 从文件名提取项目号: {project_id}")
                
                # 获取当前用户姓名
                user_name = getattr(self.app, 'user_name', '').strip()
                if not user_name:
                    from tkinter import messagebox
                    messagebox.showwarning("警告", "无法获取当前用户姓名", parent=viewer)
                    return
                
                # 文件3需要获取source_column
                source_column = None
                if file_type == 3 and '_source_column' in original_df.columns:
                    try:
                        if item_index < len(original_df):
                            source_column = original_df.iloc[item_index]['_source_column']
                    except:
                        pass
                
                # 显示输入对话框
                from input_handler import InterfaceInputDialog
                
                dialog = InterfaceInputDialog(
                    viewer,
                    interface_id,
                    file_type,
                    source_file,
                    original_row,
                    user_name,
                    project_id,
                    source_column,
                    file_manager=file_manager,  # 传递file_manager用于自动勾选
                    viewer=viewer,              # 传递viewer用于立即刷新
                    item_id=item_id,            # 传递当前行ID
                    columns=columns             # 传递列名列表
                )
                dialog.wait_window()
                
            except Exception as e:
                print(f"点击接口号处理失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 绑定点击事件（使用Double-1双击）
        # 使用标签化绑定，避免与其他事件冲突
        bind_tag = f"interface_click_{tab_name}"
        
        # 如果已经绑定过，先解绑
        try:
            viewer.unbind_class(bind_tag, "<Double-1>")
        except:
            pass
        
        # 给viewer添加这个标签
        tags = list(viewer.bindtags())
        if bind_tag not in tags:
            tags.insert(1, bind_tag)
            viewer.bindtags(tuple(tags))
        
        # 绑定双击事件
        viewer.bind_class(bind_tag, "<Double-1>", on_interface_click)
    
    def _get_file_type_from_tab(self, tab_name):
        """根据选项卡名称获取文件类型"""
        tab_map = {
            "内部需打开接口": 1,
            "内部需回复接口": 2,
            "外部需打开接口": 3,
            "外部需回复接口": 4,
            "三维提资接口": 5,
            "收发文函": 6
        }
        return tab_map.get(tab_name, 1)
    
    def _calculate_single_column_width(self, df, col_name):
        """
        计算单个列的宽度
        
        参数:
            df: pandas DataFrame
            col_name: 列名
            
        返回:
            int: 列宽度（像素）
        """
        try:
            # 选择用于计算的行
            if len(df) >= 2:
                calc_row = df.iloc[1]
            elif len(df) >= 1:
                calc_row = df.iloc[0]
            else:
                return 100  # 默认宽度
            
            # 获取列数据
            if col_name in df.columns:
                data_value = calc_row[col_name]
            else:
                return 100
            
            # 计算宽度
            content_str = str(data_value) if not pd.isna(data_value) else str(col_name)
            estimated_width = 0
            for char in content_str:
                if '\u4e00' <= char <= '\u9fff':  # 中文字符
                    estimated_width += 16
                else:  # 英文、数字、符号
                    estimated_width += 8
            
            # 加上边距和富余空间（1.2倍）
            final_width = int(estimated_width * 1.2) + 20
            
            # 限制范围
            return max(60, min(final_width, 300))
        except Exception as e:
            print(f"计算列宽失败 {col_name}: {e}")
            return 100
    
    def calculate_column_widths(self, df, columns):
        """
        基于列名和数据计算最佳列宽
        
        特殊处理:
        - "项目号"列: 固定宽度80px
        - "接口号"列: 固定宽度200px
        - 其他列: 动态计算，限制在60-300px
        
        算法:
        1. 选择第2行数据（数据行，非表头）
        2. 遍历每列，计算字符显示宽度
        3. 中文字符按16px，英文字符按8px估算
        4. 乘以1.2倍富余系数
        5. 限制最小60px，最大300px
        """
        column_widths = []
        
        if len(df) >= 2:
            calc_row = df.iloc[1]
        elif len(df) >= 1:
            calc_row = df.iloc[0]
        else:
            return [80] * len(columns)
        
        for i, col in enumerate(columns):
            try:
                # 为特殊列设置固定宽度
                if col == "项目号":
                    column_widths.append(80)
                    continue
                elif col == "接口号":
                    column_widths.append(200)
                    continue
                elif col == "是否已完成":
                    column_widths.append(100)  # 复选框列固定宽度
                    continue
                
                # 其他列动态计算
                header_length = len(str(col))
                
                if i < len(calc_row):
                    data_value = calc_row.iloc[i] if hasattr(calc_row, 'iloc') else calc_row[i]
                    data_length = len(str(data_value)) if not pd.isna(data_value) else 0
                else:
                    data_length = 0
                
                content_str = str(data_value) if i < len(calc_row) and not pd.isna(
                    calc_row.iloc[i] if hasattr(calc_row, 'iloc') else calc_row[i]
                ) else str(col)
                
                # 估算宽度
                estimated_width = 0
                for char in content_str:
                    if ord(char) > 127:  # 中文
                        estimated_width += 16
                    else:  # 英文
                        estimated_width += 8
                
                # 应用系数并限制范围
                col_width = int(estimated_width * 1.2)
                col_width = max(60, min(col_width, 300))
                
                column_widths.append(col_width)
                
            except Exception as e:
                print(f"计算第{i}列宽度时出错: {e}")
                column_widths.append(100)
        
        return column_widths
    
    def _create_optimized_display(self, df, tab_name, completed_rows=None):
        """
        创建优化的显示数据（显示项目号和接口号列，并附加角色标注）
        
        根据不同文件类型选择对应的接口号列：
        - 内部需打开接口：A列
        - 内部需回复接口：R列
        - 外部需打开接口：C列
        - 外部需回复接口：E列
        - 三维提资接口：A列
        - 收发文函：E列
        
        如果DataFrame中存在"角色来源"列，则在接口号后添加角色标注，如：INT-001(设计人员)
        如果DataFrame中存在"项目号"列，则在第一列显示项目号
        添加"是否已完成"列（复选框）在接口号后面
        
        参数:
            df: pandas DataFrame
            tab_name: 选项卡名称
            completed_rows: 已完成行的集合（原始行号）
        """
        try:
            # 定义接口号列映射（使用列索引）
            interface_column_index = {
                "内部需打开接口": 0,   # A列 = 索引0
                "内部需回复接口": 17,  # R列 = 索引17
                "外部需打开接口": 2,   # C列 = 索引2
                "外部需回复接口": 4,   # E列 = 索引4
                "三维提资接口": 0,     # A列 = 索引0
                "收发文函": 4          # E列 = 索引4
            }
            
            # 获取对应文件类型的接口号列索引
            if tab_name in interface_column_index:
                col_idx = interface_column_index[tab_name]
                
                # 检查列索引是否有效
                if col_idx < len(df.columns):
                    # 提取接口号列
                    interface_values = df.iloc[:, col_idx].copy()
                    
                    # 如果存在"角色来源"列，则添加角色标注
                    if "角色来源" in df.columns:
                        role_values = df["角色来源"].astype(str)
                        # 组合接口号和角色：INT-001(设计人员)
                        combined_values = []
                        for interface, role in zip(interface_values, role_values):
                            interface_str = str(interface) if not pd.isna(interface) else ""
                            role_str = str(role).strip() if not pd.isna(role) and str(role).strip() != "" else ""
                            
                            if interface_str and role_str and role_str.lower() != 'nan':
                                combined_values.append(f"{interface_str}({role_str})")
                            else:
                                combined_values.append(interface_str)
                        
                        # 生成"是否已完成"列
                        if completed_rows is None:
                            completed_rows = set()
                        
                        # 获取原始行号（如果有）
                        if "原始行号" in df.columns:
                            original_rows = df["原始行号"].tolist()
                            # 使用更大更清晰的符号：☑ (已完成) 和 ☐ (未完成)
                            completed_status = ["☑" if row in completed_rows else "☐" for row in original_rows]
                        else:
                            # 没有原始行号，使用索引
                            completed_status = ["☐"] * len(combined_values)
                        
                        # 创建新的DataFrame - 如果有项目号列，则项目号在前
                        # 【新增】"接口时间"列在"接口号"和"是否已完成"之间显示
                        # 列顺序: 状态 → 项目号 → 接口号 → 接口时间 → 责任人 → 是否已完成
                        if "项目号" in df.columns and "接口时间" in df.columns:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(combined_values)
                            result = pd.DataFrame({
                                "状态": [""] * len(combined_values),  # 占位，稍后根据延期情况填充
                                "项目号": df["项目号"],
                                "接口号": combined_values,
                                "接口时间": df["接口时间"],  # 在接口号之后显示
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        elif "项目号" in df.columns:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(combined_values)
                            result = pd.DataFrame({
                                "状态": [""] * len(combined_values),
                                "项目号": df["项目号"],
                                "接口号": combined_values,
                                "接口时间": ["-"] * len(combined_values),  # 没有时间数据时显示"-"
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        elif "接口时间" in df.columns:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(combined_values)
                            result = pd.DataFrame({
                                "状态": [""] * len(combined_values),
                                "接口号": combined_values,
                                "接口时间": df["接口时间"],  # 在接口号之后显示
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        else:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(combined_values)
                            result = pd.DataFrame({
                                "状态": [""] * len(combined_values),
                                "接口号": combined_values,
                                "接口时间": ["-"] * len(combined_values),  # 没有时间数据时显示"-"
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        return result
                    else:
                        # 没有角色来源列，直接返回接口号（和项目号）
                        # 生成"是否已完成"列
                        if completed_rows is None:
                            completed_rows = set()
                        
                        # 获取原始行号（如果有）
                        if "原始行号" in df.columns:
                            original_rows = df["原始行号"].tolist()
                            # 使用更大更清晰的符号：☑ (已完成) 和 ☐ (未完成)
                            completed_status = ["☑" if row in completed_rows else "☐" for row in original_rows]
                        else:
                            # 没有原始行号，使用索引
                            completed_status = ["☐"] * len(df)
                        
                        # 【重要】保留"接口时间"列用于延期判断（但不在GUI显示）
                        # 【新增】添加"状态"列用于显示延期警告标记
                        if "项目号" in df.columns and "接口时间" in df.columns:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(df)
                            result = pd.DataFrame({
                                "状态": [""] * len(df),
                                "项目号": df["项目号"],
                                "接口号": df.iloc[:, col_idx],
                                "接口时间": df["接口时间"],  # 保留用于延期判断
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        elif "项目号" in df.columns:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(df)
                            result = pd.DataFrame({
                                "状态": [""] * len(df),
                                "项目号": df["项目号"],
                                "接口号": df.iloc[:, col_idx],
                                "接口时间": ["-"] * len(df),  # 没有时间数据时显示"-"
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        elif "接口时间" in df.columns:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(df)
                            result = pd.DataFrame({
                                "状态": [""] * len(df),
                                "接口号": df.iloc[:, col_idx],
                                "接口时间": df["接口时间"],  # 保留用于延期判断
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        else:
                            # 准备责任人数据
                            responsible_data = df["责任人"] if "责任人" in df.columns else [""] * len(df)
                            result = pd.DataFrame({
                                "状态": [""] * len(df),
                                "接口号": df.iloc[:, col_idx],
                                "接口时间": ["-"] * len(df),  # 没有时间数据时显示"-"
                                "责任人": responsible_data,  # 新增责任人列
                                "是否已完成": completed_status
                            })
                        return result
            
            # 如果没有匹配或出错，返回原始数据
            return df
            
        except Exception as e:
            print(f"创建优化显示数据失败: {e}")
            return df
    
    def _extract_columns(self, df, indices):
        """提取指定索引的列"""
        try:
            original_columns = list(df.columns)
            new_columns = [original_columns[i] for i in indices if i < len(original_columns)]
            
            display_data = []
            for _, row in df.iterrows():
                new_row = [row.iloc[i] if i < len(row) else "" for i in indices]
                display_data.append(new_row)
            
            return pd.DataFrame(display_data, columns=new_columns)
        except Exception as e:
            print(f"提取列失败: {e}")
            return df
    
    def update_file_info(self, info_text):
        """更新文件信息显示"""
        if self.file_info_text:
            self.file_info_text.config(state='normal')
            self.file_info_text.delete('1.0', tk.END)
            self.file_info_text.insert('1.0', info_text)
            self.file_info_text.config(state='disabled')
    
    def enable_export_button(self, enabled=True):
        """启用/禁用导出按钮"""
        if 'export' in self.buttons:
            self.buttons['export'].config(state='normal' if enabled else 'disabled')
    
    def _trigger_callback(self, callback_name):
        """触发回调函数"""
        if callback_name in self.callbacks:
            try:
                self.callbacks[callback_name]()
            except Exception as e:
                print(f"回调执行失败 [{callback_name}]: {e}")
                import traceback
                traceback.print_exc()
    
    def _on_tab_changed_internal(self, event):
        """内部选项卡切换事件（触发外部回调）"""
        self._trigger_callback('on_tab_changed')
    
    def get_selected_tab_index(self):
        """获取当前选中的选项卡索引"""
        if self.notebook:
            return self.notebook.index(self.notebook.select())
        return 0
    
    def get_path_value(self):
        """获取文件夹路径"""
        return self.path_var.get() if self.path_var else ""
    
    def get_export_path_value(self):
        """获取导出路径"""
        return self.export_path_var.get() if self.export_path_var else ""
    
    def set_path_value(self, path):
        """设置文件夹路径"""
        if self.path_var:
            self.path_var.set(path)
    
    def set_export_path_value(self, path):
        """设置导出路径"""
        if self.export_path_var:
            self.export_path_var.set(path)
    
    def _copy_selected_rows(self, viewer):
        """
        复制Treeview中选中的行到剪贴板
        
        【修改】只复制接口号列，去掉角色标注（括号部分）
        多行复制时用换行符分隔
        """
        try:
            selection = viewer.selection()
            if not selection:
                return
            
            # 获取列定义
            columns = viewer["columns"]
            if not columns:
                return
            
            # 【修改】动态查找"接口号"列的位置
            # 支持的列顺序：
            # - 状态、项目号、接口号、是否已完成
            # - 状态、接口号、是否已完成
            # - 项目号、接口号、是否已完成
            # - 接口号、是否已完成
            interface_col_idx = -1
            for idx, col in enumerate(columns):
                if col == "接口号":
                    interface_col_idx = idx
                    break
            
            # 检查接口号列是否存在
            if interface_col_idx == -1:
                print("未找到接口号列")
                return
            
            # 收集接口号数据
            copied_interfaces = []
            for item_id in selection:
                values = viewer.item(item_id)['values']
                if values and len(values) > interface_col_idx:
                    interface_with_role = str(values[interface_col_idx])
                    
                    # 【新增】去掉角色标注（括号部分）
                    # 例如: "INT-001(设计人员)" -> "INT-001"
                    if '(' in interface_with_role:
                        interface_num = interface_with_role.split('(')[0]
                    else:
                        interface_num = interface_with_role
                    
                    # 去除首尾空格
                    interface_num = interface_num.strip()
                    if interface_num:
                        copied_interfaces.append(interface_num)
            
            # 将数据复制到剪贴板（换行分隔）
            if copied_interfaces:
                text_to_copy = '\n'.join(copied_interfaces)
                self.root.clipboard_clear()
                self.root.clipboard_append(text_to_copy)
                print(f"已复制 {len(copied_interfaces)} 个接口号到剪贴板")
        except Exception as e:
            print(f"复制失败: {e}")
    
    def _create_context_menu(self, viewer):
        """
        为Treeview创建右键菜单
        """
        menu = tk.Menu(viewer, tearoff=0)
        menu.add_command(label="复制接口号 (Ctrl+C)", 
                        command=lambda: self._copy_selected_rows(viewer))
        menu.add_separator()
        menu.add_command(label="全选 (Ctrl+A)", 
                        command=lambda: self._select_all_rows(viewer))
        
        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        
        viewer.bind("<Button-3>", show_menu)  # Windows/Linux右键
        viewer.bind("<Button-2>", show_menu)  # Mac右键（备用）
        
        # 绑定Ctrl+A全选
        viewer.bind('<Control-a>', lambda e: self._select_all_rows(viewer))
        viewer.bind('<Control-A>', lambda e: self._select_all_rows(viewer))
    
    def _select_all_rows(self, viewer):
        """选中Treeview中的所有行"""
        try:
            all_items = viewer.get_children()
            if all_items:
                viewer.selection_set(all_items)
        except Exception as e:
            print(f"全选失败: {e}")
    
    def _sort_by_column(self, viewer, column_name, tab_name):
        """
        按指定列对Treeview进行排序
        
        参数:
            viewer: Treeview控件
            column_name: 要排序的列名
            tab_name: 选项卡名称（用于日志）
        """
        try:
            # 获取当前排序状态（如果没有则初始化为升序）
            if not hasattr(self, '_sort_states'):
                self._sort_states = {}
            
            # 切换排序方向
            current_state = self._sort_states.get((viewer, column_name), False)
            reverse = not current_state
            self._sort_states[(viewer, column_name)] = reverse
            
            # 获取所有数据
            data = []
            for item_id in viewer.get_children():
                values = viewer.item(item_id)['values']
                text = viewer.item(item_id)['text']
                
                # 找到要排序的列的索引
                columns = viewer['columns']
                try:
                    col_idx = list(columns).index(column_name)
                    sort_value = values[col_idx] if col_idx < len(values) else ""
                except ValueError:
                    sort_value = ""
                
                # 根据列类型生成排序键
                sort_key = self._generate_sort_key(column_name, sort_value, reverse)
                
                data.append((sort_key, text, values, item_id))
            
            # 按指定列排序
            data.sort(reverse=reverse, key=lambda x: x[0])
            
            # 重新排列Treeview中的项
            for index, (_, text, values, item_id) in enumerate(data):
                viewer.move(item_id, '', index)
            
            # 更新所有列标题（清除其他列的排序符号，只显示当前列的）
            for col in columns:
                if col == column_name:
                    direction_symbol = ' ↓' if reverse else ' ↑'
                    viewer.heading(col, text=f"{col}{direction_symbol}",
                                 command=lambda c=col: self._sort_by_column(viewer, c, tab_name))
                else:
                    viewer.heading(col, text=col,
                                 command=lambda c=col: self._sort_by_column(viewer, c, tab_name))
            
            print(f"{tab_name} - 按{column_name}列排序（{'降序' if reverse else '升序'}）")
            
        except Exception as e:
            print(f"排序失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_sort_key(self, column_name, sort_value, reverse):
        """
        根据列名和值生成排序键
        
        参数:
            column_name: 列名
            sort_value: 列值
            reverse: 是否降序
            
        返回:
            排序键（字符串或元组）
        """
        try:
            # 特殊列：接口时间（日期格式 mm.dd）
            if column_name == '接口时间':
                if sort_value == '-' or sort_value == '' or sort_value is None:
                    # 空值排到最后
                    return '99.99' if not reverse else '00.00'
                else:
                    # 日期格式 mm.dd 可以直接字符串排序
                    return str(sort_value)
            
            # 特殊列：项目号（数字）
            if column_name == '项目号':
                try:
                    return int(str(sort_value)) if sort_value and str(sort_value).strip() else 0
                except:
                    return 0
            
            # 特殊列：是否已完成（☐在前，☑在后）
            if column_name == '是否已完成':
                if str(sort_value) == '☑':
                    return '1'
                else:
                    return '0'
            
            # 特殊列：状态（⚠️在前，空值在后）
            if column_name == '状态':
                if str(sort_value) == '⚠️':
                    return '0'
                else:
                    return '1'
            
            # 其他列：字符串排序（中文按拼音）
            return str(sort_value) if sort_value is not None else ''
            
        except Exception as e:
            print(f"生成排序键失败 [{column_name}={sort_value}]: {e}")
            return str(sort_value) if sort_value is not None else ''

