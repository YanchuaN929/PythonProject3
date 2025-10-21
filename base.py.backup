#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接口处理程序
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

def get_resource_path(relative_path):
    """获取资源文件的绝对路径，兼容开发环境和打包环境"""
    if hasattr(sys, '_MEIPASS'):
        # 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

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
    
    def __init__(self, auto_mode: bool = False):
        self.auto_mode = auto_mode
        self.root = tk.Tk()
        self.setup_window()
        self.load_config()
        # 四个勾选框变量
        self.process_file1_var = tk.BooleanVar(value=True)
        self.process_file2_var = tk.BooleanVar(value=True)
        self.process_file3_var = tk.BooleanVar(value=True)
        self.process_file4_var = tk.BooleanVar(value=True)
        self.process_file5_var = tk.BooleanVar(value=True)
        self.process_file6_var = tk.BooleanVar(value=True)
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
        
        # 四类文件及项目号（单文件兼容性保留）
        self.target_file1 = None
        self.target_file1_project_id = None
        self.target_file2 = None
        self.target_file2_project_id = None
        self.target_file3 = None
        self.target_file3_project_id = None
        self.target_file4 = None
        self.target_file4_project_id = None
        
        # 多文件存储结构：[(文件路径, 项目号), ...]
        self.target_files1 = []  # 待处理文件1列表
        self.target_files2 = []  # 待处理文件2列表  
        self.target_files3 = []  # 待处理文件3列表
        self.target_files4 = []  # 待处理文件4列表
        self.target_files5 = []  # 待处理文件5列表
        self.target_files6 = []  # 待处理文件6列表
        
        # 文件数据存储（单文件兼容性保留）
        self.file1_data = None
        self.file2_data = None
        self.file3_data = None
        self.file4_data = None
        self.file5_data = None
        self.file6_data = None
        
        # 多文件数据存储：{项目号: DataFrame, ...}
        self.files1_data = {}  # 待处理文件1的数据字典
        self.files2_data = {}  # 待处理文件2的数据字典
        self.files3_data = {}  # 待处理文件3的数据字典
        self.files4_data = {}  # 待处理文件4的数据字典
        self.files5_data = {}  # 待处理文件5的数据字典
        self.files6_data = {}  # 待处理文件6的数据字典
        
        # 处理结果（单文件兼容性保留）
        self.processing_results = None
        self.processing_results2 = None
        self.processing_results3 = None
        self.processing_results4 = None
        self.processing_results5 = None
        self.processing_results6 = None
        
        # 多文件处理结果：{项目号: DataFrame, ...}
        self.processing_results_multi1 = {}  # 待处理文件1的处理结果字典
        self.processing_results_multi2 = {}  # 待处理文件2的处理结果字典
        self.processing_results_multi3 = {}  # 待处理文件3的处理结果字典
        self.processing_results_multi4 = {}  # 待处理文件4的处理结果字典
        self.processing_results_multi5 = {}  # 待处理文件5的处理结果字典
        self.processing_results_multi6 = {}  # 待处理文件6的处理结果字典
        
        # 处理结果状态标记 - 用于判断是否显示处理后的结果
        self.has_processed_results1 = False
        self.has_processed_results2 = False
        self.has_processed_results3 = False
        self.has_processed_results4 = False
        self.has_processed_results5 = False
        self.has_processed_results6 = False
        # 监控器
        self.monitor = None
        
        # 勾选框变量
        

        # 启动时检查“姓名”是否已填写，未填写则提醒并禁用按钮
        try:
            self._enforce_user_name_gate(show_popup=True)
        except Exception:
            pass

        # 自动模式：启动后自动执行刷新→处理→导出
        if self.auto_mode:
            try:
                self.root.after(300, self._run_auto_flow)
            except Exception:
                pass

    def setup_window(self):
        """设置主窗口属性"""
        self.root.title("接口筛选程序")
        
        # 获取屏幕分辨率并适配
        self.setup_window_size()
        
        # 设置最小窗口大小
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
        # 配置文件放在用户目录，避免打包后权限问题
        user_config_dir = os.path.expanduser("~/.excel_processor")
        if not os.path.exists(user_config_dir):
            os.makedirs(user_config_dir, exist_ok=True)
        self.config_file = os.path.join(user_config_dir, "config.json")
        self.yaml_config_file = os.path.join(user_config_dir, "config.yaml")
        self.default_config = {
            "folder_path": "",
            "export_folder_path": "",
            "user_name": "",
            "auto_startup": False,
            "minimize_to_tray": True,
            "dont_ask_again": False,
            "hide_previous_months": False,
            # 自动运行导出日期窗口（按角色）。含义：截止日期与今天的天数差 <= 指定天数 才导出；允许为负（已超期）
            "role_export_days": {
                "一室主任": 7,
                "二室主任": 7,
                "建筑总图室主任": 7,
                "所长": 2,
                "管理员": None,
                "设计人员": None
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = self.default_config.copy()
        except:
            self.config = self.default_config.copy()

        # 填充缺省的 role_export_days（向后兼容旧配置）
        try:
            if "role_export_days" not in self.config or not isinstance(self.config.get("role_export_days"), dict):
                self.config["role_export_days"] = self.default_config["role_export_days"].copy()
            else:
                # 合并缺失的角色键，但不覆盖已有值
                for k, v in self.default_config["role_export_days"].items():
                    if k not in self.config["role_export_days"]:
                        self.config["role_export_days"][k] = v
        except Exception:
            pass

        # 载入 YAML 新参数（timer/cache/general），无依赖第三方库的简易解析
        self.timer_enabled = True
        self.timer_require_24h = True
        self.timer_times = "10:00,16:00"
        self.timer_grace_minutes = 10
        self._load_yaml_settings()

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
        # 同步保存 YAML（包含迁移后的通用参数）
        try:
            self._save_yaml_all()
        except Exception:
            pass

    def _load_yaml_settings(self):
        """从 config.yaml 读取 timer/cache/general 参数（无则使用默认）"""
        try:
            if not os.path.exists(self.yaml_config_file):
                return
            current_section = None
            with open(self.yaml_config_file, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.endswith(':') and not ':' in line[:-1]:
                        current_section = line[:-1].strip()
                        continue
                    if ':' in line and current_section in ('timer','cache','general'):
                        key, val = line.split(':', 1)
                        key = key.strip()
                        val = val.strip().strip('"')
                        if current_section == 'timer':
                            if key == 'enabled':
                                self.timer_enabled = (val.lower() == 'true')
                            elif key == 'require_24h':
                                self.timer_require_24h = (val.lower() == 'true')
                            elif key == 'times':
                                self.timer_times = val
                            elif key == 'grace_minutes':
                                try:
                                    self.timer_grace_minutes = int(val)
                                except Exception:
                                    pass
                        
                        elif current_section == 'general':
                            # 将旧参数迁移到 self.config
                            if key in ("folder_path","export_folder_path","user_name"):
                                self.config[key] = val
                            elif key in ("auto_startup","minimize_to_tray","dont_ask_again","hide_previous_months"):
                                self.config[key] = (val.lower() == 'true')
        except Exception as e:
            print(f"加载YAML配置失败: {e}")

    def _save_yaml_all(self):
        """将 general/timer/cache 参数保存到 config.yaml"""
        try:
            lines = []
            # general 区域：写入旧有参数
            lines.append("general:")
            lines.append(f"  folder_path: \"{self.config.get('folder_path','')}\"")
            lines.append(f"  export_folder_path: \"{self.config.get('export_folder_path','')}\"")
            lines.append(f"  user_name: \"{self.config.get('user_name','')}\"")
            lines.append(f"  auto_startup: {'true' if self.config.get('auto_startup', False) else 'false'}")
            lines.append(f"  minimize_to_tray: {'true' if self.config.get('minimize_to_tray', True) else 'false'}")
            lines.append(f"  dont_ask_again: {'true' if self.config.get('dont_ask_again', False) else 'false'}")
            lines.append(f"  hide_previous_months: {'true' if self.config.get('hide_previous_months', False) else 'false'}")
            lines.append("")
            lines.append("timer:")
            lines.append(f"  enabled: {'true' if self.timer_enabled else 'false'}")
            lines.append(f"  require_24h: {'true' if self.timer_require_24h else 'false'}")
            # times 使用逗号分隔字符串，避免实现列表解析
            lines.append(f"  times: \"{self.timer_times}\"")
            lines.append(f"  grace_minutes: {int(self.timer_grace_minutes)}")
            
            os.makedirs(os.path.dirname(self.yaml_config_file), exist_ok=True)
            with open(self.yaml_config_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
        except Exception as e:
            print(f"保存YAML配置失败: {e}")

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

        # 新增：第二行 导出结果位置（可选，默认沿用文件夹路径）
        ttk.Label(path_frame, text="导出结果位置:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(8, 0))
        self.export_path_var = tk.StringVar(value=self.config.get("export_folder_path", ""))
        self.export_path_entry = ttk.Entry(path_frame, textvariable=self.export_path_var, width=60)
        self.export_path_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=(8, 0))
        self.browse_export_button = ttk.Button(path_frame, text="浏览", command=self.browse_export_folder)
        self.browse_export_button.grid(row=1, column=2, sticky=tk.W, pady=(8, 0))
        
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

        # 新增：打开文件位置按钮
        self.open_folder_button = ttk.Button(
            button_frame,
            text="打开文件位置",
            command=self.open_selected_folder
        )
        self.open_folder_button.pack(side=tk.LEFT, padx=(10, 0))
        
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

        # 初始根据姓名配置禁用/启用按钮
        try:
            self._enforce_user_name_gate(show_popup=False)
        except Exception:
            pass

        # 右下角水印
        try:
            watermark = ttk.Label(main_frame, text="——by 建筑结构所，王任超", foreground="gray")
            watermark.grid(row=4, column=2, sticky=tk.E, padx=(0, 4), pady=(6, 2))
        except Exception:
            pass

    def create_tabs(self):
        """创建选项卡"""
        # 选项卡1：内部需打开接口
        self.tab1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1_frame, text="内部需打开接口")
        self.tab1_frame.columnconfigure(0, weight=1)
        self.tab1_frame.rowconfigure(1, weight=1)
        self.tab1_check = ttk.Checkbutton(self.tab1_frame, text="处理内部需打开接口", variable=self.process_file1_var)
        self.tab1_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡2：内部需回复接口
        self.tab2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2_frame, text="内部需回复接口")
        self.tab2_frame.columnconfigure(0, weight=1)
        self.tab2_frame.rowconfigure(1, weight=1)
        self.tab2_check = ttk.Checkbutton(self.tab2_frame, text="处理内部需回复接口", variable=self.process_file2_var)
        self.tab2_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡3：外部需打开接口
        self.tab3_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3_frame, text="外部需打开接口")
        self.tab3_frame.columnconfigure(0, weight=1)
        self.tab3_frame.rowconfigure(1, weight=1)
        self.tab3_check = ttk.Checkbutton(self.tab3_frame, text="处理外部需打开接口", variable=self.process_file3_var)
        self.tab3_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡4：外部需回复接口
        self.tab4_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab4_frame, text="外部需回复接口")
        self.tab4_frame.columnconfigure(0, weight=1)
        self.tab4_frame.rowconfigure(1, weight=1)
        self.tab4_check = ttk.Checkbutton(self.tab4_frame, text="处理外部需回复接口", variable=self.process_file4_var)
        self.tab4_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡5：三维提资接口
        self.tab5_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab5_frame, text="三维提资接口")
        self.tab5_frame.columnconfigure(0, weight=1)
        self.tab5_frame.rowconfigure(1, weight=1)
        self.tab5_check = ttk.Checkbutton(self.tab5_frame, text="处理三维提资接口", variable=self.process_file5_var)
        self.tab5_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 选项卡6：收发文函
        self.tab6_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tab6_frame, text="收发文函")
        self.tab6_frame.columnconfigure(0, weight=1)
        self.tab6_frame.rowconfigure(1, weight=1)
        self.tab6_check = ttk.Checkbutton(self.tab6_frame, text="处理收发文函", variable=self.process_file6_var)
        self.tab6_check.grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        # 为每个选项卡创建Excel预览控件
        self.create_excel_viewer(self.tab1_frame, "tab1")
        self.create_excel_viewer(self.tab2_frame, "tab2")
        self.create_excel_viewer(self.tab3_frame, "tab3")
        self.create_excel_viewer(self.tab4_frame, "tab4")
        self.create_excel_viewer(self.tab5_frame, "tab5")
        self.create_excel_viewer(self.tab6_frame, "tab6")
        # 绑定选项卡切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        # 存储选项卡引用以便后续修改状态
        self.tabs = {
            'tab1': 0,  # 内部需打开接口
            'tab2': 1,  # 内部需回复接口
            'tab3': 2,  # 外部需打开接口
            'tab4': 3,  # 外部需回复接口
            'tab5': 4,  # 三维提资接口
            'tab6': 5   # 收发文函
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
        if selected_tab == 0 and self.target_file1:  # 内部需打开接口
            # 如果有处理结果，显示过滤后的数据；否则显示原始数据
            if self.has_processed_results1 and self.processing_results is not None and not self.processing_results.empty:
                print("显示处理后的过滤结果")
                self.filter_and_display_results(self.processing_results)
            elif self.has_processed_results1:
                print("显示无数据结果")
                self.show_empty_message(self.tab1_viewer, "无内部需打开接口")
            elif self.file1_data is not None:
                print("显示原始文件数据")
                self.display_excel_data(self.tab1_viewer, self.file1_data, "内部需打开接口")
            else:
                self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
        elif selected_tab == 1 and self.target_file2:  # 内部需回复接口
            if self.has_processed_results2 and self.processing_results2 is not None and not self.processing_results2.empty:
                display_df = self.processing_results2.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results2['原始行号'])
                self.display_excel_data_with_original_rows(self.tab2_viewer, display_df, "内部需回复接口", excel_row_numbers)
            elif self.has_processed_results2:
                self.show_empty_message(self.tab2_viewer, "无内部需回复接口")
            elif self.file2_data is not None:
                self.display_excel_data(self.tab2_viewer, self.file2_data, "内部需回复接口")
            else:
                self.load_file_to_viewer(self.target_file2, self.tab2_viewer, "内部需回复接口")
        elif selected_tab == 2 and self.target_file3:  # 外部需打开接口
            if self.has_processed_results3 and self.processing_results3 is not None and not self.processing_results3.empty:
                display_df = self.processing_results3.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results3['原始行号'])
                self.display_excel_data_with_original_rows(self.tab3_viewer, display_df, "外部需打开接口", excel_row_numbers)
            elif self.has_processed_results3:
                self.show_empty_message(self.tab3_viewer, "无外部需打开接口")
            elif self.file3_data is not None:
                self.display_excel_data(self.tab3_viewer, self.file3_data, "外部需打开接口")
            else:
                self.load_file_to_viewer(self.target_file3, self.tab3_viewer, "外部需打开接口")
        elif selected_tab == 3 and self.target_file4:  # 外部需回复接口
            if self.has_processed_results4 and self.processing_results4 is not None and not self.processing_results4.empty:
                display_df = self.processing_results4.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results4['原始行号'])
                self.display_excel_data_with_original_rows(self.tab4_viewer, display_df, "外部需回复接口", excel_row_numbers)
            elif self.has_processed_results4:
                self.show_empty_message(self.tab4_viewer, "无外部需回复接口")
            elif self.file4_data is not None:
                self.display_excel_data(self.tab4_viewer, self.file4_data, "外部需回复接口")
            else:
                self.load_file_to_viewer(self.target_file4, self.tab4_viewer, "外部需回复接口")
        elif selected_tab == 4 and getattr(self, 'target_files5', None):  # 三维提资接口
            if self.has_processed_results5 and self.processing_results5 is not None and not self.processing_results5.empty:
                display_df = self.processing_results5.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results5['原始行号'])
                self.display_excel_data_with_original_rows(self.tab5_viewer, display_df, "三维提资接口", excel_row_numbers)
            elif self.has_processed_results5:
                self.show_empty_message(self.tab5_viewer, "无三维提资接口")
            elif self.file5_data is not None:
                self.display_excel_data(self.tab5_viewer, self.file5_data, "三维提资接口")
        elif selected_tab == 5 and getattr(self, 'target_files6', None):  # 收发文函
            # 若视图已有内容，则不重绘，保持当前显示
            try:
                if len(self.tab6_viewer.get_children()) > 0:
                    return
            except Exception:
                pass
            if self.has_processed_results6 and self.processing_results6 is not None and not self.processing_results6.empty:
                display_df = self.processing_results6.drop(columns=['原始行号'], errors='ignore')
                excel_row_numbers = list(self.processing_results6['原始行号'])
                self.display_excel_data_with_original_rows(self.tab6_viewer, display_df, "收发文函", excel_row_numbers)
            elif self.has_processed_results6:
                self.show_empty_message(self.tab6_viewer, "无收发文函")
            elif self.file6_data is not None:
                self.display_excel_data(self.tab6_viewer, self.file6_data, "收发文函")

    def load_file_to_viewer(self, file_path, viewer, tab_name):
        """加载Excel文件到预览器"""
        import os
        
        try:
            print(f"正在加载 {tab_name} 文件: {os.path.basename(file_path)}")
            
            # 读取Excel文件的第一个工作表（不强制Sheet1）
            if file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
            else:
                df = pd.read_excel(file_path, sheet_name=0, engine='xlrd')
            
            if df.empty:
                self.show_empty_message(viewer, f"{tab_name}文件为空")
                return
            
            # 存储数据
            if tab_name == "内部需打开接口":
                self.file1_data = df
            elif tab_name == "内部需回复接口":
                self.file2_data = df
            elif tab_name == "外部需打开接口":
                self.file3_data = df
            elif tab_name == "外部需回复接口":
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
        if tab_name == "内部需打开接口" and len(df.columns) >= 13:
            # 创建优化后的显示数据
            display_df = self.create_optimized_display_data(df)
            columns = list(display_df.columns)
        elif tab_name == "内部需回复接口" and len(df.columns) >= 28:
            # 待处理文件2优化显示
            display_df = self.create_optimized_display_data_file2(df)
            columns = list(display_df.columns)
        elif tab_name == "外部需打开接口" and len(df.columns) >= 38:
            # 待处理文件3优化显示
            display_df = self.create_optimized_display_data_file3(df)
            columns = list(display_df.columns)
        elif tab_name == "外部需回复接口" and len(df.columns) >= 32:
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
        
        # 添加数据行，限制显示前20行
        row_count = 0
        for index, row in display_df.iterrows():
            if row_count >= 20:  # 限制显示前20行
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
        if len(display_df) > 20:
            viewer.insert("", "end", text="...", values=["...（其他行已省略显示）"] + [""] * (len(columns) - 1))
        
        print(f"{tab_name}数据加载完成：{len(df)} 行，{len(df.columns)} 列 -> 显示：{len(display_df.columns)} 列")

    def display_excel_data_with_original_rows(self, viewer, df, tab_name, original_row_numbers):
        """在viewer中显示Excel数据，使用原始Excel行号"""
        # 清空现有内容
        for item in viewer.get_children():
            viewer.delete(item)
        
        # 对不同的文件类型进行优化显示（仅显示关键列）
        if tab_name == "内部需打开接口" and len(df.columns) >= 13:
            # 创建优化后的显示数据
            display_df = self.create_optimized_display_data(df)
            columns = list(display_df.columns)
        elif tab_name == "内部需回复接口" and len(df.columns) >= 28:
            # 待处理文件2优化显示
            display_df = self.create_optimized_display_data_file2(df)
            columns = list(display_df.columns)
        elif tab_name == "外部需打开接口" and len(df.columns) >= 38:
            # 待处理文件3优化显示
            display_df = self.create_optimized_display_data_file3(df)
            columns = list(display_df.columns)
        elif tab_name == "外部需回复接口" and len(df.columns) >= 32:
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
        
        # 添加数据行，使用原始Excel行号，限制显示前20行
        row_count = 0
        for index, row in display_df.iterrows():
            if row_count >= 20:  # 限制显示前20行
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
        if len(display_df) > 20:
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
        """为待处理文件3创建优化的显示数据（仅显示C、L、Q、M、T、I、AF、N列）"""
        try:
            # 确保有足够的列（C=2, L=11, Q=16, M=12, T=19, I=8, AF=31, N=13）
            required_cols = max(2, 11, 16, 12, 19, 8, 31, 13)
            if len(df.columns) <= required_cols:
                return df
            
            # 获取列名（转换为列表以支持索引）
            original_columns = list(df.columns)
            
            # 定义要显示的列，按新顺序：C列（接口编码）之后是L、Q、M、T、I、AF、N列
            key_column_indices = [2, 11, 16, 12, 19, 8, 31, 13]  # C, L, Q, M, T, I, AF, N列的索引
            
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
            
            print(f"优化显示文件3：原始{len(original_columns)}列 -> 显示关键列C,L,Q,M,T,I,AF,N")
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

        # 启动后加载用户角色
        try:
            self.load_user_role()
        except Exception:
            pass

    def show_initial_welcome_message(self):
        """显示初始欢迎信息"""
        welcome_text = "欢迎使用本程序，请点击刷新文件列表按钮加载内容。"
        self.update_file_info(welcome_text)
        
        # 为所有选项卡显示欢迎信息
        self.show_empty_message(self.tab1_viewer, "等待加载内部需打开接口数据")
        self.show_empty_message(self.tab2_viewer, "等待加载内部需回复接口数据")
        self.show_empty_message(self.tab3_viewer, "等待加载外部需打开接口数据")
        self.show_empty_message(self.tab4_viewer, "等待加载外部需回复接口数据")
        self.show_empty_message(self.tab5_viewer, "等待加载三维提资接口数据")
        self.show_empty_message(self.tab6_viewer, "等待加载收发文函数据")

    def apply_role_based_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """根据姓名与角色对结果进行过滤。
        依赖列：'科室'、'责任人'。缺列时安全回退为原df。
        角色映射：
          - 设计人员：责任人 == 姓名
          - 一室主任：科室 ∈ {结构一室, 请室主任确认}
          - 二室主任：科室 ∈ {结构二室, 请室主任确认}
          - 建筑总图室主任：科室 ∈ {建筑总图室, 请室主任确认}
          - 管理员或空角色/姓名：不过滤
        """
        try:
            user_name = getattr(self, 'user_name', '').strip()
            user_role = getattr(self, 'user_role', '').strip()
            if not user_role or not user_name:
                return df
            safe_df = df.copy()
            if user_role == '设计人员':
                if '责任人' in safe_df.columns:
                    return safe_df[safe_df['责任人'].astype(str).str.strip() == user_name]
                return safe_df
            if user_role == '一室主任':
                if '科室' in safe_df.columns:
                    return safe_df[safe_df['科室'].isin(['结构一室', '请室主任确认'])]
                return safe_df
            if user_role == '二室主任':
                if '科室' in safe_df.columns:
                    return safe_df[safe_df['科室'].isin(['结构二室', '请室主任确认'])]
                return safe_df
            if user_role == '建筑总图室主任':
                if '科室' in safe_df.columns:
                    return safe_df[safe_df['科室'].isin(['建筑总图室', '请室主任确认'])]
                return safe_df
            # 管理员/其他：不过滤
            return safe_df
        except Exception:
            return df

    def apply_auto_role_date_window(self, df: pd.DataFrame) -> pd.DataFrame:
        """自动运行模式下，按角色限定导出的日期窗口。
        依据列：'接口时间'（格式 mm.dd）。
        规则：仅当 auto_mode=True 且 用户角色在 role_export_days 映射中时生效；
             仅保留 (due_date - today).days <= 指定天数 的记录（支持负值，即已超期亦保留）。
        解析失败或无'接口时间'的记录将被排除。
        """
        try:
            if not getattr(self, 'auto_mode', False):
                return df
            user_role = getattr(self, 'user_role', '').strip()
            if not user_role:
                return df
            role_days_map = self.config.get("role_export_days", {}) or {}
            if user_role not in role_days_map:
                return df
            raw_days = role_days_map.get(user_role, None)
            if raw_days is None or (isinstance(raw_days, str) and raw_days.strip() == ""):
                return df
            try:
                max_days = int(raw_days)
            except Exception:
                return df
            if "接口时间" not in df.columns:
                return df.iloc[0:0]
            from datetime import date
            today = date.today()
            kept_idx = []
            for idx, val in df["接口时间"].items():
                try:
                    s = str(val).strip()
                    if not s or s == "未知":
                        continue
                    parts = s.split('.')
                    if len(parts) != 2:
                        continue
                    m = int(parts[0])
                    d = int(parts[1])
                    due = date(today.year, m, d)
                    delta = (due - today).days
                    if delta <= max_days:
                        kept_idx.append(idx)
                except Exception:
                    continue
            if not kept_idx:
                return df.iloc[0:0]
            return df.loc[kept_idx]
        except Exception:
            return df

    def load_user_role(self):
        """加载用户角色：从 excel_bin/姓名角色表.xlsx 中读取 A列=姓名，B列=角色"""
        self.user_name = self.config.get("user_name", "").strip()
        self.user_role = ""
        if not self.user_name:
            return
        try:
            xls_path = get_resource_path("excel_bin/姓名角色表.xlsx")
            if not os.path.exists(xls_path):
                return
            df = pd.read_excel(xls_path, engine='openpyxl') if xls_path.endswith('.xlsx') else pd.read_excel(xls_path, engine='xlrd')
            # 兼容无表头/不同表头
            cols = list(df.columns)
            name_col = None
            role_col = None
            for i, c in enumerate(cols):
                cs = str(c)
                if name_col is None and (cs.find('姓名') != -1):
                    name_col = i
                if role_col is None and (cs.find('角色') != -1):
                    role_col = i
            if name_col is None:
                name_col = 0 if len(cols) >= 1 else None
            if role_col is None:
                role_col = 1 if len(cols) >= 2 else None
            if name_col is None or role_col is None:
                return
            for _, row in df.iterrows():
                try:
                    name_val = str(row.iloc[name_col]).strip()
                    role_val = str(row.iloc[role_col]).strip()
                    if name_val == self.user_name:
                        self.user_role = role_val
                        break
                except Exception:
                    continue
        except Exception:
            pass

    def adjust_font_sizes(self):
        """根据屏幕分辨率调整字体大小，并兼容Win7字体"""
        screen_width = self.root.winfo_screenwidth()
        if screen_width >= 1920:
            font_size = 10
        elif screen_width >= 1600:
            font_size = 9
        elif screen_width >= 1366:
            font_size = 9
        else:
            font_size = 8

        # 字体降级兼容
        font_candidates = ["Microsoft YaHei UI", "Microsoft YaHei", "SimSun"]
        for font_name in font_candidates:
            try:
                self.root.option_add("*Font", (font_name, font_size))
                default_font = (font_name, font_size)
                # 测试能否正常设置字体
                test_label = tk.Label(self.root, text="test", font=default_font)
                test_label.destroy()
                break
            except Exception:
                continue
        else:
            # 如果都失败，使用Tk默认字体
            default_font = ("TkDefaultFont", font_size)

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

    def browse_export_folder(self):
        """选择导出结果生成位置（可为空，表示沿用文件夹路径）"""
        folder_path = filedialog.askdirectory(
            title="选择导出结果位置",
            initialdir=self.export_path_var.get() or self.path_var.get() or os.path.expanduser("~")
        )
        if folder_path:
            self.export_path_var.set(folder_path)
            self.config["export_folder_path"] = folder_path
            self.save_config()

    def show_settings_menu(self):
        """显示设置菜单"""
        # 创建设置菜单窗口
        settings_menu = tk.Toplevel(self.root)
        settings_menu.title("设置")
        settings_menu.geometry("560x420")
        settings_menu.transient(self.root)
        settings_menu.grab_set()
        settings_menu.resizable(False, False)
        
        # 设置窗口图标
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
            if os.path.exists(icon_path):
                settings_menu.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置菜单图标失败: {e}")
        
        # 居中显示
        try:
            settings_menu.update_idletasks()
            win_w = settings_menu.winfo_width() or 380
            x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (win_w // 2)
            y = self.root.winfo_rooty() + 50
            settings_menu.geometry(f"+{x}+{y}")
        except Exception:
            pass
        
        # 设置框架
        frame = ttk.Frame(settings_menu, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 姓名输入
        name_frame = ttk.Frame(frame)
        name_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(name_frame, text="姓名:").pack(side=tk.LEFT)
        self.user_name_var = tk.StringVar(value=self.config.get("user_name", ""))
        name_entry = ttk.Entry(name_frame, textvariable=self.user_name_var, width=20)
        name_entry.pack(side=tk.LEFT, padx=(8, 0))
        try:
            ttk.Label(name_frame, text="例:王任超", foreground="gray").pack(side=tk.LEFT, padx=(8,0))
        except Exception:
            pass

        def on_name_change(*_):
            self.config["user_name"] = self.user_name_var.get().strip()
            self.save_config()
            try:
                self.load_user_role()
            except Exception:
                pass
            # 根据姓名更新按钮可用性
            try:
                self._enforce_user_name_gate(show_popup=False)
            except Exception:
                pass
        self.user_name_var.trace_add('write', on_name_change)
        
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

        # 不显示前月数据（影响日期筛选逻辑开关）
        self.hide_previous_months_var = tk.BooleanVar(value=self.config.get("hide_previous_months", False))
        def on_toggle_hide_prev():
            self.config["hide_previous_months"] = self.hide_previous_months_var.get()
            self.save_config()
        hide_prev_check = ttk.Checkbutton(
            frame,
            text="不显示前月数据",
            variable=self.hide_previous_months_var,
            command=on_toggle_hide_prev
        )
        hide_prev_check.pack(anchor=tk.W, pady=(0, 10))

        # 定时器设置
        timer_frame = ttk.LabelFrame(frame, text="定时自动运行", padding="10")
        timer_frame.pack(fill=tk.X, pady=(5, 10))

        self.timer_enabled_var = tk.BooleanVar(value=self.timer_enabled)
        def on_timer_enabled():
            self.timer_enabled = self.timer_enabled_var.get()
            self._save_yaml_all()
        ttk.Checkbutton(timer_frame, text="启用定时自动运行", variable=self.timer_enabled_var, command=on_timer_enabled).pack(anchor=tk.W)

        self.timer_require_24h_var = tk.BooleanVar(value=self.timer_require_24h)
        def on_timer_require_24h():
            self.timer_require_24h = self.timer_require_24h_var.get()
            self._save_yaml_all()
        ttk.Checkbutton(timer_frame, text="仅当运行满24小时后才触发", variable=self.timer_require_24h_var, command=on_timer_require_24h).pack(anchor=tk.W, pady=(4,0))

        times_row = ttk.Frame(timer_frame)
        times_row.pack(fill=tk.X, pady=(6,0))
        ttk.Label(times_row, text="触发时间(逗号分隔):").pack(side=tk.LEFT)
        self.timer_times_var = tk.StringVar(value=self.timer_times)
        def on_times_change(*_):
            self.timer_times = self.timer_times_var.get().strip() or "10:00,16:00"
            self._save_yaml_all()
        ttk.Entry(times_row, textvariable=self.timer_times_var, width=22).pack(side=tk.LEFT, padx=(8,0))
        self.timer_times_var.trace_add('write', on_times_change)

        grace_row = ttk.Frame(timer_frame)
        grace_row.pack(fill=tk.X, pady=(6,0))
        ttk.Label(grace_row, text="容错分钟:").pack(side=tk.LEFT)
        self.timer_grace_var = tk.StringVar(value=str(self.timer_grace_minutes))
        def on_grace_change(*_):
            try:
                gm = int(self.timer_grace_var.get().strip())
                if gm < 0:
                    gm = 0
                self.timer_grace_minutes = gm
                self._save_yaml_all()
            except Exception:
                pass
        ttk.Entry(grace_row, textvariable=self.timer_grace_var, width=8).pack(side=tk.LEFT, padx=(8,0))
        try:
            ttk.Label(grace_row, text="说明：上面是您希望的弹窗时间，左侧10分钟不建议调整", foreground="gray").pack(side=tk.LEFT, padx=(8,0))
        except Exception:
            pass
        self.timer_grace_var.trace_add('write', on_grace_change)

        # （已移除缓存设置）
        
        # 关闭按钮
        close_button = ttk.Button(frame, text="确定", command=settings_menu.destroy, width=14)
        close_button.pack(pady=(10, 0))

    def show_waiting_dialog(self, title, message):
        """显示等待对话框"""
        if getattr(self, 'auto_mode', False):
            return None, None
        waiting_dialog = tk.Toplevel(self.root)
        waiting_dialog.title(title)
        waiting_dialog.geometry("280x100")
        waiting_dialog.transient(self.root)
        waiting_dialog.grab_set()
        waiting_dialog.resizable(False, False)
        
        # 设置窗口图标
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
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
        if getattr(self, 'auto_mode', False):
            return None, None
        waiting_dialog = tk.Toplevel(self.root)
        waiting_dialog.title(title)
        waiting_dialog.geometry("320x120")
        waiting_dialog.transient(self.root)
        waiting_dialog.grab_set()
        waiting_dialog.resizable(False, False)
        
        # 设置窗口图标
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
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
        import os
        
        folder_path = self.path_var.get().strip()
        if not folder_path or not os.path.exists(folder_path):
            self.update_file_info("请选择有效的文件夹路径")
            return
        
        # 显示等待对话框（自动模式下不显示）
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
                    
                    # 统计所有识别到的文件
                    total_identified_files = 0
                    project_summary = {}  # {项目号: 文件数量}
                    
                    # 显示待处理文件1信息（批量）
                    if self.target_files1:
                        file_info += f"✓ 待处理文件1 (内部需打开接口): {len(self.target_files1)} 个文件\n"
                        for file_path, project_id in self.target_files1:
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  - {disp_pid}: {os.path.basename(file_path)}\n"
                            project_summary[disp_pid] = project_summary.get(disp_pid, 0) + 1
                        total_identified_files += len(self.target_files1)
                    
                    # 显示待处理文件2信息（批量）
                    if self.target_files2:
                        file_info += f"✓ 待处理文件2 (内部需回复接口): {len(self.target_files2)} 个文件\n"
                        for file_path, project_id in self.target_files2:
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  - {disp_pid}: {os.path.basename(file_path)}\n"
                            project_summary[disp_pid] = project_summary.get(disp_pid, 0) + 1
                        total_identified_files += len(self.target_files2)
                    
                    # 显示待处理文件3信息（批量）
                    if self.target_files3:
                        file_info += f"✓ 待处理文件3 (外部需打开接口): {len(self.target_files3)} 个文件\n"
                        for file_path, project_id in self.target_files3:
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  - {disp_pid}: {os.path.basename(file_path)}\n"
                            project_summary[disp_pid] = project_summary.get(disp_pid, 0) + 1
                        total_identified_files += len(self.target_files3)
                    
                    # 显示待处理文件4信息（批量）
                    if self.target_files4:
                        file_info += f"✓ 待处理文件4 (外部需回复接口): {len(self.target_files4)} 个文件\n"
                        for file_path, project_id in self.target_files4:
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  - {disp_pid}: {os.path.basename(file_path)}\n"
                            project_summary[disp_pid] = project_summary.get(disp_pid, 0) + 1
                        total_identified_files += len(self.target_files4)

                    # 显示待处理文件5信息（批量）
                    if self.target_files5:
                        file_info += f"✓ 待处理文件5 (三维提资接口): {len(self.target_files5)} 个文件\n"
                        for file_path, project_id in self.target_files5:
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  - {disp_pid}: {os.path.basename(file_path)}\n"
                            project_summary[disp_pid] = project_summary.get(disp_pid, 0) + 1
                        total_identified_files += len(self.target_files5)

                    # 显示待处理文件6信息（批量）
                    if self.target_files6:
                        file_info += f"✓ 待处理文件6 (收发文函): {len(self.target_files6)} 个文件\n"
                        for file_path, project_id in self.target_files6:
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  - {disp_pid}: {os.path.basename(file_path)}\n"
                            project_summary[disp_pid] = project_summary.get(disp_pid, 0) + 1
                        total_identified_files += len(self.target_files6)
                    
                    # 项目汇总信息
                    if project_summary:
                        file_info += f"\n📊 项目汇总:\n"
                        for project_id, count in sorted(project_summary.items()):
                            disp_pid = project_id if project_id else "未知项目"
                            file_info += f"  项目 {disp_pid}: {count} 个文件\n"
                        file_info += f"  总计: {len(project_summary)} 个项目, {total_identified_files} 个待处理文件\n"
                    
                    # 显示示例文件（主界面显示第一个文件作为示例）
                    file_info += f"\n📋 主界面显示示例:\n"
                    if self.target_file1:
                        file_info += f"  内部需打开接口: {os.path.basename(self.target_file1)} (项目{self.target_file1_project_id})\n"
                    if self.target_file2:
                        file_info += f"  内部需回复接口: {os.path.basename(self.target_file2)} (项目{self.target_file2_project_id})\n"
                    if self.target_file3:
                        file_info += f"  外部需打开接口: {os.path.basename(self.target_file3)} (项目{self.target_file3_project_id})\n"
                    if self.target_file4:
                        file_info += f"  外部需回复接口: {os.path.basename(self.target_file4)} (项目{self.target_file4_project_id})\n"
                    
                    file_info += f"\n📁 全部Excel文件列表:\n"
                    for i, file_path in enumerate(self.excel_files, 1):
                        file_name = os.path.basename(file_path)
                        file_size = os.path.getsize(file_path)
                        file_info += f"{i}. {file_name} ({file_size} 字节)\n"
                        
                    # 准备弹窗信息
                    popup_message = self._generate_popup_message(project_summary, total_identified_files)
                    
                else:
                    file_info = "在指定路径下未找到Excel文件"
                    popup_message = "未找到任何Excel文件"
                
                self.update_file_info(file_info)
                
            except Exception as e:
                self.update_file_info(f"读取文件列表时发生错误: {str(e)}")
                popup_message = f"读取文件列表时发生错误: {str(e)}"
            
            # 刷新完成后，更新当前选项卡的显示
            self.refresh_current_tab_display()
            
            # 关闭等待对话框
            self.close_waiting_dialog(waiting_dialog)
            
            # 仅在手动刷新时显示弹窗（包含识别结果）。自动模式禁用
            if show_popup and not getattr(self, 'auto_mode', False):
                messagebox.showinfo("文件识别完成", popup_message)
        
        # 延迟执行刷新操作，确保等待对话框能够显示
        self.root.after(100, do_refresh)

    def _generate_popup_message(self, project_summary, total_identified_files):
        """生成弹窗显示的识别结果信息"""
        if not project_summary:
            return "未识别到任何待处理文件"
        
        message = f"🎉 文件识别成功！\n\n"
        message += f"📊 识别结果汇总:\n"
        message += f"• 发现 {len(project_summary)} 个项目\n"
        message += f"• 共计 {total_identified_files} 个待处理文件\n\n"
        
        message += f"📋 各项目详情:\n"
        for project_id in sorted(project_summary.keys()):
            count = project_summary[project_id]
            message += f"• 项目 {project_id}: {count} 个文件\n"
        
        message += f"\n💡 提示:\n"
        message += f"• 主界面显示第一个项目的文件作为示例\n"
        message += f"• 勾选文件类型将处理所有相应的项目文件\n"
        message += f"• 导出结果将按项目号自动分文件夹存放"
        
        return message

    def refresh_current_tab_display(self):
        """刷新当前选项卡的显示内容"""
        try:
            # 获取当前选中的选项卡索引
            current_tab = self.notebook.index(self.notebook.select())
            
            # 根据当前选项卡刷新对应的显示内容
            if current_tab == 0 and self.target_file1:  # 应打开接口
                self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
            elif current_tab == 1 and self.target_file2:  # 需回复接口
                self.load_file_to_viewer(self.target_file2, self.tab2_viewer, "内部需回复接口")
            elif current_tab == 2 and self.target_file3:  # 外部接口ICM
                self.load_file_to_viewer(self.target_file3, self.tab3_viewer, "外部需打开接口")
            elif current_tab == 3 and self.target_file4:  # 外部接口单
                self.load_file_to_viewer(self.target_file4, self.tab4_viewer, "外部需回复接口")
            elif current_tab == 4 and getattr(self, 'target_files5', None):  # 三维提资接口
                if self.has_processed_results5 and self.processing_results5 is not None and not self.processing_results5.empty:
                    display_df = self.processing_results5.drop(columns=['原始行号'], errors='ignore')
                    excel_row_numbers = list(self.processing_results5['原始行号'])
                    self.display_excel_data_with_original_rows(self.tab5_viewer, display_df, "三维提资接口", excel_row_numbers)
                elif self.has_processed_results5:
                    self.show_empty_message(self.tab5_viewer, "无三维提资接口")
                elif self.file5_data is not None:
                    self.display_excel_data(self.tab5_viewer, self.file5_data, "三维提资接口")
            elif current_tab == 5 and getattr(self, 'target_files6', None):  # 收发文函
                # 若视图已有内容，则不重绘，保持当前显示
                try:
                    if len(self.tab6_viewer.get_children()) > 0:
                        return
                except Exception:
                    pass
                if self.has_processed_results6 and self.processing_results6 is not None and not self.processing_results6.empty:
                    display_df = self.processing_results6.drop(columns=['原始行号'], errors='ignore')
                    excel_row_numbers = list(self.processing_results6['原始行号'])
                    self.display_excel_data_with_original_rows(self.tab6_viewer, display_df, "收发文函", excel_row_numbers)
                elif self.has_processed_results6:
                    self.show_empty_message(self.tab6_viewer, "无收发文函")
                elif self.file6_data is not None:
                    self.display_excel_data(self.tab6_viewer, self.file6_data, "收发文函")
            else:
                # 如果当前选项卡没有对应的文件，显示空提示
                tab_names = ["内部需打开接口", "内部需回复接口", "外部需打开接口", "外部需回复接口"]
                viewers = [self.tab1_viewer, self.tab2_viewer, self.tab3_viewer, self.tab4_viewer]
                if 0 <= current_tab < len(tab_names):
                    self.show_empty_message(viewers[current_tab], f"等待加载{tab_names[current_tab]}数据")
        except Exception as e:
            print(f"刷新当前选项卡显示失败: {e}")

    def identify_target_files(self):
        """识别特定格式的目标文件"""
        # 重置单文件状态（兼容性保留）
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
        
        # 重置多文件状态
        self.target_files1 = []
        self.target_files2 = []
        self.target_files3 = []
        self.target_files4 = []
        self.target_files5 = []
        self.target_files6 = []
        self.files1_data = {}
        self.files2_data = {}
        self.files3_data = {}
        self.files4_data = {}
        self.files5_data = {}
        self.files6_data = {}
        self.processing_results_multi1 = {}
        self.processing_results_multi2 = {}
        self.processing_results_multi3 = {}
        self.processing_results_multi4 = {}
        self.processing_results_multi5 = {}
        self.processing_results_multi6 = {}
        
        # 重置处理结果状态标记
        self.has_processed_results1 = False
        self.has_processed_results2 = False
        self.has_processed_results3 = False
        self.has_processed_results4 = False
        self.has_processed_results5 = False
        self.has_processed_results6 = False
        # 重置选项卡状态
        self.update_tab_color(0, "normal")
        self.update_tab_color(1, "normal")
        self.update_tab_color(2, "normal")
        self.update_tab_color(3, "normal")
        if not self.excel_files:
            return
        try:
            # 安全导入main模块（不依赖文件系统检查）
            try:
                import main
            except ImportError:
                import sys
                import os
                # 如果是打包环境，添加当前目录到路径
                if hasattr(sys, '_MEIPASS'):
                    sys.path.insert(0, sys._MEIPASS)
                else:
                    sys.path.insert(0, os.path.dirname(__file__))
                import main
            
            # 识别待处理文件1（批量 + 兼容性）
            if hasattr(main, 'find_all_target_files1'):
                # 批量识别所有待处理文件1
                self.target_files1 = main.find_all_target_files1(self.excel_files)
                if self.target_files1:
                    # 兼容性：设置第一个文件为单文件变量
                    self.target_file1, self.target_file1_project_id = self.target_files1[0]
                    self.update_tab_color(0, "green")
                    self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
            elif hasattr(main, 'find_target_file'):
                # 兼容旧版本
                self.target_file1, self.target_file1_project_id = main.find_target_file(self.excel_files)
                if self.target_file1:
                    self.target_files1 = [(self.target_file1, self.target_file1_project_id)]
                    self.update_tab_color(0, "green")
                    self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
            
            # 识别待处理文件2（批量 + 兼容性）
            if hasattr(main, 'find_all_target_files2'):
                # 批量识别所有待处理文件2
                self.target_files2 = main.find_all_target_files2(self.excel_files)
                if self.target_files2:
                    # 兼容性：设置第一个文件为单文件变量
                    self.target_file2, self.target_file2_project_id = self.target_files2[0]
                    self.update_tab_color(1, "green")
                    try:
                        if self.target_file2.endswith('.xlsx'):
                            self.file2_data = pd.read_excel(self.target_file2, sheet_name=0, engine='openpyxl')
                        else:
                            self.file2_data = pd.read_excel(self.target_file2, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件2失败: {e}")
            elif hasattr(main, 'find_target_file2'):
                # 兼容旧版本
                self.target_file2, self.target_file2_project_id = main.find_target_file2(self.excel_files)
                if self.target_file2:
                    self.target_files2 = [(self.target_file2, self.target_file2_project_id)]
                    self.update_tab_color(1, "green")
                    try:
                        if self.target_file2.endswith('.xlsx'):
                            self.file2_data = pd.read_excel(self.target_file2, sheet_name=0, engine='openpyxl')
                        else:
                            self.file2_data = pd.read_excel(self.target_file2, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件2失败: {e}")
            
            # 识别待处理文件3（批量 + 兼容性）
            if hasattr(main, 'find_all_target_files3'):
                # 批量识别所有待处理文件3
                self.target_files3 = main.find_all_target_files3(self.excel_files)
                if self.target_files3:
                    # 兼容性：设置第一个文件为单文件变量
                    self.target_file3, self.target_file3_project_id = self.target_files3[0]
                    self.update_tab_color(2, "green")
                    try:
                        if self.target_file3.endswith('.xlsx'):
                            self.file3_data = pd.read_excel(self.target_file3, sheet_name=0, engine='openpyxl')
                        else:
                            self.file3_data = pd.read_excel(self.target_file3, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件3失败: {e}")
            elif hasattr(main, 'find_target_file3'):
                # 兼容旧版本
                self.target_file3, self.target_file3_project_id = main.find_target_file3(self.excel_files)
                if self.target_file3:
                    self.target_files3 = [(self.target_file3, self.target_file3_project_id)]
                    self.update_tab_color(2, "green")
                    try:
                        if self.target_file3.endswith('.xlsx'):
                            self.file3_data = pd.read_excel(self.target_file3, sheet_name=0, engine='openpyxl')
                        else:
                            self.file3_data = pd.read_excel(self.target_file3, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件3失败: {e}")
            
            # 识别待处理文件4（批量 + 兼容性）
            if hasattr(main, 'find_all_target_files4'):
                # 批量识别所有待处理文件4
                self.target_files4 = main.find_all_target_files4(self.excel_files)
                if self.target_files4:
                    # 兼容性：设置第一个文件为单文件变量
                    self.target_file4, self.target_file4_project_id = self.target_files4[0]
                    self.update_tab_color(3, "green")
                    try:
                        if self.target_file4.endswith('.xlsx'):
                            self.file4_data = pd.read_excel(self.target_file4, sheet_name=0, engine='openpyxl')
                        else:
                            self.file4_data = pd.read_excel(self.target_file4, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件4失败: {e}")
            elif hasattr(main, 'find_target_file4'):
                # 兼容旧版本
                self.target_file4, self.target_file4_project_id = main.find_target_file4(self.excel_files)
                if self.target_file4:
                    self.target_files4 = [(self.target_file4, self.target_file4_project_id)]
                    self.update_tab_color(3, "green")
                    try:
                        if self.target_file4.endswith('.xlsx'):
                            self.file4_data = pd.read_excel(self.target_file4, sheet_name=0, engine='openpyxl')
                        else:
                            self.file4_data = pd.read_excel(self.target_file4, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件4失败: {e}")

            # 识别待处理文件5（批量）
            if hasattr(main, 'find_all_target_files5'):
                self.target_files5 = main.find_all_target_files5(self.excel_files)
                if self.target_files5:
                    self.update_tab_color(4, "green")
                    try:
                        file5, _pid5 = self.target_files5[0]
                        if file5.endswith('.xlsx'):
                            self.file5_data = pd.read_excel(file5, sheet_name=0, engine='openpyxl')
                        else:
                            self.file5_data = pd.read_excel(file5, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件5失败: {e}")

            # 识别待处理文件6（批量）
            if hasattr(main, 'find_all_target_files6'):
                self.target_files6 = main.find_all_target_files6(self.excel_files)
                if self.target_files6:
                    self.update_tab_color(5, "green")
                    try:
                        file6, _pid6 = self.target_files6[0]
                        if file6.endswith('.xlsx'):
                            self.file6_data = pd.read_excel(file6, sheet_name=0, engine='openpyxl')
                        else:
                            self.file6_data = pd.read_excel(file6, sheet_name=0, engine='xlrd')
                    except Exception as e:
                        print(f"预加载待处理文件6失败: {e}")
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
        
        # 姓名必填校验
        try:
            if (not self.config.get("user_name", "").strip()) and (not getattr(self, 'auto_mode', False)):
                message = "请先在设置中填写‘姓名’，否则无法开始处理。"
                try:
                    from tkinter import messagebox as _mb
                    _mb.showwarning("提示", message)
                except Exception:
                    pass
                return
        except Exception:
            pass
        
        # 检查勾选状态
        process_file1 = self.process_file1_var.get()
        process_file2 = self.process_file2_var.get()
        process_file3 = self.process_file3_var.get()
        process_file4 = self.process_file4_var.get()
        process_file5 = self.process_file5_var.get()
        process_file6 = self.process_file6_var.get()
        if not (process_file1 or process_file2 or process_file3 or process_file4 or process_file5 or process_file6):
            if not getattr(self, 'auto_mode', False):
                messagebox.showwarning("警告", "请至少勾选一个需要处理的接口类型！")
            return
        
        # 显示等待对话框（自动模式下不显示）
        processing_dialog, _ = self.show_waiting_dialog("开始处理", "正在处理中，请稍后。。。 。。。")
            
        self.process_button.config(state='disabled', text="处理中...")
        
        def process_files():
            try:
                # 导入必要的模块
                import pandas as pd
                import os
                import sys
                # 读取日期逻辑开关
                hide_prev = False
                try:
                    hide_prev = bool(self.config.get("hide_previous_months", False))
                except Exception:
                    hide_prev = False
                
                # 安全导入main模块
                try:
                    import main
                except ImportError:
                    # 如果是打包环境，添加当前目录到路径
                    if hasattr(sys, '_MEIPASS'):
                        sys.path.insert(0, sys._MEIPASS)
                    else:
                        sys.path.insert(0, os.path.dirname(__file__))
                    import main
                # 将设置中的日期逻辑开关传递给 main 模块
                try:
                    main.USE_OLD_DATE_LOGIC = hide_prev
                except Exception:
                    pass

                # （已移除缓存模块）
                # 初始化处理结果变量
                results1 = None
                results2 = None
                results3 = None
                results4 = None
                
                # 处理待处理文件1（批量）
                if process_file1 and self.target_files1:
                    if hasattr(main, 'process_target_file'):
                        print(f"开始批量处理文件1类型，共 {len(self.target_files1)} 个文件")
                        try:
                            import Monitor
                            project_ids = list(set([pid for _, pid in self.target_files1]))
                            Monitor.log_process(f"开始批量处理待处理文件1: {len(self.target_files1)}个文件，涉及{len(project_ids)}个项目({', '.join(sorted(project_ids))})")
                        except:
                            pass
                        
                        self.processing_results_multi1 = {}
                        combined_results = []
                        
                        for file_path, project_id in self.target_files1:
                            try:
                                print(f"处理项目{project_id}的文件1: {os.path.basename(file_path)}")
                                try:
                                    import Monitor
                                    Monitor.log_process(f"处理项目{project_id}的待处理文件1: {os.path.basename(file_path)}")
                                except:
                                    pass

                                # 直接处理（缓存已移除）
                                result = main.process_target_file(file_path, self.current_datetime)
                                if result is not None and not result.empty:
                                    self.processing_results_multi1[project_id] = result
                                    combined_results.append(result)
                                    print(f"项目{project_id}文件1处理完成: {len(result)} 行")
                                    try:
                                        import Monitor
                                        Monitor.log_success(f"项目{project_id}文件1处理完成: {len(result)} 行数据")
                                    except:
                                        pass
                                else:
                                    print(f"项目{project_id}文件1处理结果为空")
                                    try:
                                        import Monitor
                                        Monitor.log_warning(f"项目{project_id}文件1处理结果为空")
                                    except:
                                        pass
                            except Exception as e:
                                print(f"项目{project_id}文件1处理失败: {e}")
                                try:
                                    import Monitor
                                    Monitor.log_error(f"项目{project_id}文件1处理失败: {e}")
                                except:
                                    pass
                        
                        # 合并所有结果（兼容性）
                        if combined_results:
                            results1 = pd.concat(combined_results, ignore_index=True)
                            print(f"文件1批量处理完成，总计: {len(results1)} 行")
                            try:
                                import Monitor
                                Monitor.log_success(f"待处理文件1批量处理完成: 总计{len(results1)}行数据，来自{len(combined_results)}个项目")
                            except:
                                pass
                        else:
                            # 所有项目都没有结果，创建空DataFrame以确保显示"无数据"
                            results1 = pd.DataFrame()
                            print(f"文件1批量处理完成，所有项目都无符合条件的数据")
                            try:
                                import Monitor
                                Monitor.log_warning(f"待处理文件1批量处理完成: 所有项目都无符合条件的数据")
                            except:
                                pass
                
                # 处理待处理文件2（批量）
                if process_file2 and self.target_files2:
                    if hasattr(main, 'process_target_file2'):
                        print(f"开始批量处理文件2类型，共 {len(self.target_files2)} 个文件")
                        try:
                            import Monitor
                            project_ids = list(set([pid for _, pid in self.target_files2]))
                            Monitor.log_process(f"开始批量处理待处理文件2: {len(self.target_files2)}个文件，涉及{len(project_ids)}个项目({', '.join(sorted(project_ids))})")
                        except:
                            pass
                        
                        self.processing_results_multi2 = {}
                        combined_results = []
                        
                        for file_path, project_id in self.target_files2:
                            try:
                                print(f"处理项目{project_id}的文件2: {os.path.basename(file_path)}")
                                result = main.process_target_file2(file_path, self.current_datetime)
                                if result is not None and not result.empty:
                                    self.processing_results_multi2[project_id] = result
                                    combined_results.append(result)
                                    print(f"项目{project_id}文件2处理完成: {len(result)} 行")
                                else:
                                    print(f"项目{project_id}文件2处理结果为空")
                            except Exception as e:
                                print(f"项目{project_id}文件2处理失败: {e}")
                        
                        # 合并所有结果（兼容性）
                        if combined_results:
                            results2 = pd.concat(combined_results, ignore_index=True)
                            print(f"文件2批量处理完成，总计: {len(results2)} 行")
                        else:
                            # 所有项目都没有结果，创建空DataFrame以确保显示"无数据"
                            results2 = pd.DataFrame()
                            print(f"文件2批量处理完成，所有项目都无符合条件的数据")
                            try:
                                import Monitor
                                Monitor.log_warning(f"待处理文件2批量处理完成: 所有项目都无符合条件的数据")
                            except:
                                pass
                
                # 处理待处理文件3（批量）
                if process_file3 and self.target_files3:
                    if hasattr(main, 'process_target_file3'):
                        print(f"开始批量处理文件3类型，共 {len(self.target_files3)} 个文件")
                        self.processing_results_multi3 = {}
                        combined_results = []
                        
                        for file_path, project_id in self.target_files3:
                            try:
                                print(f"处理项目{project_id}的文件3: {os.path.basename(file_path)}")
                                result = main.process_target_file3(file_path, self.current_datetime)
                                if result is not None and not result.empty:
                                    self.processing_results_multi3[project_id] = result
                                    combined_results.append(result)
                                    print(f"项目{project_id}文件3处理完成: {len(result)} 行")
                                else:
                                    print(f"项目{project_id}文件3处理结果为空")
                            except Exception as e:
                                print(f"项目{project_id}文件3处理失败: {e}")
                        
                        # 合并所有结果（兼容性）
                        if combined_results:
                            results3 = pd.concat(combined_results, ignore_index=True)
                            print(f"文件3批量处理完成，总计: {len(results3)} 行")
                        else:
                            # 所有项目都没有结果，创建空DataFrame以确保显示"无数据"
                            results3 = pd.DataFrame()
                            print(f"文件3批量处理完成，所有项目都无符合条件的数据")
                            try:
                                import Monitor
                                Monitor.log_warning(f"待处理文件3批量处理完成: 所有项目都无符合条件的数据")
                            except:
                                pass
                
                # 处理待处理文件4（批量）
                if process_file4 and self.target_files4:
                    if hasattr(main, 'process_target_file4'):
                        print(f"开始批量处理文件4类型，共 {len(self.target_files4)} 个文件")
                        self.processing_results_multi4 = {}
                        combined_results = []
                        
                        for file_path, project_id in self.target_files4:
                            try:
                                print(f"处理项目{project_id}的文件4: {os.path.basename(file_path)}")
                                result = main.process_target_file4(file_path, self.current_datetime)
                                if result is not None and not result.empty:
                                    self.processing_results_multi4[project_id] = result
                                    combined_results.append(result)
                                    print(f"项目{project_id}文件4处理完成: {len(result)} 行")
                                else:
                                    print(f"项目{project_id}文件4处理结果为空")
                            except Exception as e:
                                print(f"项目{project_id}文件4处理失败: {e}")
                        
                        # 合并所有结果（兼容性）
                        if combined_results:
                            results4 = pd.concat(combined_results, ignore_index=True)
                            print(f"文件4批量处理完成，总计: {len(results4)} 行")
                        else:
                            # 所有项目都没有结果，创建空DataFrame以确保显示"无数据"
                            results4 = pd.DataFrame()
                            print(f"文件4批量处理完成，所有项目都无符合条件的数据")
                            try:
                                import Monitor
                                Monitor.log_warning(f"待处理文件4批量处理完成: 所有项目都无符合条件的数据")
                            except:
                                pass
                
                def update_display():
                    # 统一处理结果显示和弹窗（批量处理版本）
                    processed_count = 0
                    completion_messages = []
                    active_tab = 0  # 默认显示第一个选项卡
                    
                    # 统计批量处理信息
                    total_projects = set()
                    total_files_processed = 0
                    
                    if process_file1 and results1 is not None:
                        self.display_results(results1, show_popup=False)
                        active_tab = 0  # 内部需打开接口
                        project_count = len(self.processing_results_multi1)
                        file_count = len(self.target_files1) if self.target_files1 else 1
                        total_projects.update(self.processing_results_multi1.keys())
                        total_files_processed += file_count
                        
                        if not results1.empty:
                            processed_count += 1
                            if project_count > 1:
                                completion_messages.append(f"内部需打开接口：{len(results1)} 行数据 ({project_count}个项目)")
                            else:
                                completion_messages.append(f"内部需打开接口：{len(results1)} 行数据")
                        else:
                            completion_messages.append("内部需打开接口：无符合条件的数据")
                    
                    if process_file2 and results2 is not None:
                        self.display_results2(results2, show_popup=False)
                        if not process_file1:  # 如果file1没处理，显示file2
                            active_tab = 1
                        project_count = len(self.processing_results_multi2)
                        file_count = len(self.target_files2) if self.target_files2 else 1
                        total_projects.update(self.processing_results_multi2.keys())
                        total_files_processed += file_count
                        
                        if not results2.empty:
                            processed_count += 1
                            if project_count > 1:
                                completion_messages.append(f"内部需回复接口：{len(results2)} 行数据 ({project_count}个项目)")
                            else:
                                completion_messages.append(f"内部需回复接口：{len(results2)} 行数据")
                        else:
                            completion_messages.append("内部需回复接口：无符合条件的数据")
                    
                    if process_file3 and results3 is not None:
                        self.display_results3(results3, show_popup=False)
                        if not process_file1 and not process_file2:  # 显示优先级
                            active_tab = 2
                        project_count = len(self.processing_results_multi3)
                        file_count = len(self.target_files3) if self.target_files3 else 1
                        total_projects.update(self.processing_results_multi3.keys())
                        total_files_processed += file_count
                        
                        if not results3.empty:
                            processed_count += 1
                            if project_count > 1:
                                completion_messages.append(f"外部需打开接口：{len(results3)} 行数据 ({project_count}个项目)")
                            else:
                                completion_messages.append(f"外部需打开接口：{len(results3)} 行数据")
                        else:
                            completion_messages.append("外部需打开接口：无符合条件的数据")
                    
                    if process_file4 and results4 is not None:
                        self.display_results4(results4, show_popup=False)
                        if not process_file1 and not process_file2 and not process_file3:
                            active_tab = 3
                        project_count = len(self.processing_results_multi4)
                        file_count = len(self.target_files4) if self.target_files4 else 1
                        total_projects.update(self.processing_results_multi4.keys())
                        total_files_processed += file_count
                        
                        if not results4.empty:
                            processed_count += 1
                            if project_count > 1:
                                completion_messages.append(f"外部需回复接口：{len(results4)} 行数据 ({project_count}个项目)")
                            else:
                                completion_messages.append(f"外部需回复接口：{len(results4)} 行数据")
                        else:
                            completion_messages.append("外部需回复接口：无符合条件的数据")
                    
                    # 处理待处理文件5（批量）
                    process_file5 = getattr(self, 'process_file5_var', tk.BooleanVar(value=False)).get()
                    results5 = None
                    if process_file5 and getattr(self, 'target_files5', None):
                        if hasattr(main, 'process_target_file5'):
                            try:
                                import Monitor
                                pids = list(set([pid for _, pid in self.target_files5]))
                                Monitor.log_process(f"开始批量处理待处理文件5: {len(self.target_files5)}个文件，涉及{len(pids)}个项目({', '.join(sorted(pids))})")
                            except:
                                pass
                            self.processing_results_multi5 = {}
                            combined_results = []
                            for file_path, project_id in self.target_files5:
                                try:
                                    print(f"处理项目{project_id}的文件5: {os.path.basename(file_path)}")
                                    result = main.process_target_file5(file_path, self.current_datetime)
                                    if result is not None and not result.empty:
                                        self.processing_results_multi5[project_id] = result
                                        combined_results.append(result)
                                except Exception as e:
                                    print(f"处理文件5失败: {file_path} - {e}")
                            if combined_results:
                                results5 = pd.concat(combined_results, ignore_index=True)
                                try:
                                    self.display_results5(results5, show_popup=False)
                                except Exception:
                                    pass
                                if not process_file1 and not process_file2 and not process_file3 and not process_file4:
                                    active_tab = 4
                                project_count = len(self.processing_results_multi5)
                                file_count = len(self.target_files5) if self.target_files5 else 1
                                total_projects.update(self.processing_results_multi5.keys())
                                total_files_processed += file_count
                                if not results5.empty:
                                    processed_count += 1
                                    if project_count > 1:
                                        completion_messages.append(f"三维提资接口：{len(results5)} 行数据 ({project_count}个项目)")
                                    else:
                                        completion_messages.append(f"三维提资接口：{len(results5)} 行数据")
                                else:
                                    completion_messages.append("三维提资接口：无符合条件的数据")

                    # 处理待处理文件6（批量）
                    process_file6 = getattr(self, 'process_file6_var', tk.BooleanVar(value=False)).get()
                    results6 = None
                    if process_file6 and getattr(self, 'target_files6', None):
                        if hasattr(main, 'process_target_file6'):
                            try:
                                import Monitor
                                pids = list(set([pid for _, pid in self.target_files6]))
                                Monitor.log_process(f"开始批量处理待处理文件6: {len(self.target_files6)}个文件，涉及{len(pids)}个项目")
                            except:
                                pass
                            self.processing_results_multi6 = {}
                            combined_results = []
                            for file_path, project_id in self.target_files6:
                                try:
                                    print(f"处理文件6: {os.path.basename(file_path)}")
                                    result = main.process_target_file6(file_path, self.current_datetime)
                                    if result is not None and not result.empty:
                                        self.processing_results_multi6[project_id] = result
                                        combined_results.append(result)
                                except Exception as e:
                                    print(f"处理文件6失败: {file_path} - {e}")
                            if combined_results:
                                results6 = pd.concat(combined_results, ignore_index=True)
                                try:
                                    self.display_results6(results6, show_popup=False)
                                except Exception:
                                    pass
                                if not process_file1 and not process_file2 and not process_file3 and not process_file4 and not process_file5:
                                    active_tab = 5
                                project_count = len(self.processing_results_multi6)
                                file_count = len(self.target_files6) if self.target_files6 else 1
                                total_projects.update(self.processing_results_multi6.keys())
                                total_files_processed += file_count
                                if not results6.empty:
                                    processed_count += 1
                                    completion_messages.append(f"收发文函：{len(results6)} 行数据")
                                else:
                                    completion_messages.append("收发文函：无符合条件的数据")

                    # 选择显示的选项卡（优先级：file1 > file2 > file3 > file4 > file5 > file6）
                    self.notebook.select(active_tab)
                    
                    # 关闭等待对话框
                    self.close_waiting_dialog(processing_dialog)
                    
                    # 统一弹窗显示处理结果（批量处理版本，自动模式下不显示）
                    if completion_messages and not getattr(self, 'auto_mode', False):
                        combined_message = "🎉 批量数据处理完成！\n\n"
                        if len(total_projects) > 1:
                            combined_message += f"📊 处理统计:\n"
                            combined_message += f"• 共处理 {len(total_projects)} 个项目\n"
                            combined_message += f"• 共处理 {total_files_processed} 个文件\n"
                            combined_message += f"• 项目号: {', '.join(sorted(total_projects))}\n\n"
                        combined_message += "📋 处理结果:\n"
                        combined_message += "\n".join([f"• {msg}" for msg in completion_messages])
                        if len(total_projects) > 1:
                            combined_message += "\n\n💡 提示:\n"
                            combined_message += "• 导出结果将按项目号自动分文件夹存放\n"
                            combined_message += "• 主界面显示的是所有项目的合并数据"
                        messagebox.showinfo("批量处理完成", combined_message)

                    # 自动模式下，处理完成后自动导出
                    if getattr(self, 'auto_mode', False):
                        # 直接调用导出
                        try:
                            # 清除上次的汇总路径，避免误用历史文件
                            self.last_summary_written_path = None
                        except Exception:
                            pass
                        self.export_results()
                        # 在导出任务队列启动后，仅在本次确有新汇总时才弹出TXT
                        def after_export_summary():
                            try:
                                import os
                                txt_path = getattr(self, 'last_summary_written_path', None)
                                if txt_path and os.path.exists(txt_path):
                                    self._show_summary_popup(txt_path)
                            except Exception:
                                pass
                        self.root.after(2500, after_export_summary)
                    
                    self.process_button.config(state='normal', text="开始处理")
                
                self.root.after(0, update_display)
                
            except Exception as e:
                self.root.after(0, lambda: self.close_waiting_dialog(processing_dialog))
                if not (getattr(self, 'auto_mode', False) and getattr(self, '_auto_context', True)):
                   self.root.after(0, lambda: messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}"))
                   self.root.after(0, lambda: self.process_button.config(state='normal', text="开始处理"))
        
        thread = threading.Thread(target=process_files, daemon=True)
        thread.start()

    def display_results(self, results, show_popup=True):
        """显示处理结果"""
        # 检查处理结果
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results1 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab1_viewer, "无内部需打开接口")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        
        # 检查结果是否为空（所有行都被剔除）
        if len(results) == 0:
            self.has_processed_results1 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab1_viewer, "无内部需打开接口")
            self.update_export_button_state()  # 更新导出按钮状态
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
            messagebox.showinfo("处理完成", f"数据处理完成！\n经过四步筛选后，共剩余 {row_count} 行符合条件的数据\n结果已在【内部需打开接口】选项卡中更新显示。")

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
        # 检查待处理文件5的结果
        if (self.has_processed_results5 and 
            self.processing_results5 is not None and 
            not self.processing_results5.empty):
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
                self.show_empty_message(self.tab1_viewer, "无内部需打开接口")
                return

            # 只取最终结果的所有数据行
            display_df = results.drop(columns=['原始行号'], errors='ignore')
            excel_row_numbers = list(results['原始行号'])

            # 只显示数据行，不显示表头
            self.display_excel_data_with_original_rows(self.tab1_viewer, display_df, "内部需打开接口", excel_row_numbers)
        except Exception as e:
            print(f"显示最终筛选数据时发生错误: {e}")
            self.show_empty_message(self.tab1_viewer, "数据过滤失败")
            # 处理失败时也需要更新导出按钮状态
            self.update_export_button_state()

    def display_results2(self, results, show_popup=True):
        """显示需回复接口处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results2 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab2_viewer, "无内部需回复接口")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        self.processing_results2 = results
        self.has_processed_results2 = True  # 标记已有处理结果
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab2_viewer, display_df, "内部需回复接口", excel_row_numbers)
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", f"内部需回复接口数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【内部需回复接口】选项卡中更新显示。")

    def display_results3(self, results, show_popup=True):
        """显示外部接口ICM处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results3 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab3_viewer, "无外部需打开接口")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        self.processing_results3 = results
        self.has_processed_results3 = True  # 标记已有处理结果
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab3_viewer, display_df, "外部需打开接口", excel_row_numbers)
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", f"外部需打开接口数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【外部需打开接口】选项卡中更新显示。")

    def display_results4(self, results, show_popup=True):
        """显示外部接口单处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results4 = True  # 标记已处理，即使结果为空
            self.show_empty_message(self.tab4_viewer, "无外部需回复接口")
            self.update_export_button_state()  # 更新导出按钮状态
            return
        self.processing_results4 = results
        self.has_processed_results4 = True  # 标记已有处理结果
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab4_viewer, display_df, "外部需回复接口", excel_row_numbers)
        self.update_export_button_state()
        
        # 显示处理完成信息（仅在旧版调用时显示）
        if show_popup:
            messagebox.showinfo("处理完成", f"外部需回复接口数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【外部需回复接口】选项卡中更新显示。")

    def display_results5(self, results, show_popup=True):
        """显示三维提资接口处理结果"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results5 = True
            self.show_empty_message(self.tab5_viewer, "无三维提资接口")
            self.update_export_button_state()
            return
        self.processing_results5 = results
        self.has_processed_results5 = True
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab5_viewer, display_df, "三维提资接口", excel_row_numbers)
        self.update_export_button_state()
        if show_popup:
            messagebox.showinfo("处理完成", f"三维提资接口数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【三维提资接口】选项卡中更新显示。")

    def display_results6(self, results, show_popup=True):
        """显示收发文函处理结果（与其他类型保持一致）"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results6 = True
            self.show_empty_message(self.tab6_viewer, "无收发文函")
            self.update_export_button_state()
            return
        self.processing_results6 = results
        self.has_processed_results6 = True
        display_df = results.drop(columns=['原始行号'], errors='ignore')
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab6_viewer, display_df, "收发文函", excel_row_numbers)
        self.update_export_button_state()
        if show_popup and not getattr(self, 'auto_mode', False):
            messagebox.showinfo("处理完成", f"收发文函数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【收发文函】选项卡中更新显示。")

    def export_results(self):
        current_tab = self.notebook.index(self.notebook.select())
        # 姓名必填校验
        try:
            if (not self.config.get("user_name", "").strip()) and (not getattr(self, 'auto_mode', False)):
                message = "请先在设置中填写‘姓名’，否则无法导出结果。"
                try:
                    from tkinter import messagebox as _mb
                    _mb.showwarning("提示", message)
                except Exception:
                    pass
                return
        except Exception:
            pass
        
        # 导入必要的模块
        import sys
        import os
        
        # 安全导入main模块
        try:
            import main
        except ImportError:
            # 如果是打包环境，添加当前目录到路径
            if hasattr(sys, '_MEIPASS'):
                sys.path.insert(0, sys._MEIPASS)
            else:
                sys.path.insert(0, os.path.dirname(__file__))
            import main
        export_tasks = []
        # 预备过滤后结果字典
        self.filtered_results_multi1 = {}
        self.filtered_results_multi2 = {}
        self.filtered_results_multi3 = {}
        self.filtered_results_multi4 = {}
        
        # 批量导出所有项目的处理结果
        # 导出待处理文件1的所有项目结果
        if self.process_file1_var.get() and self.processing_results_multi1:
            for project_id, results in self.processing_results_multi1.items():
                if isinstance(results, pd.DataFrame) and not results.empty:
                    # 角色过滤
                    results = self.apply_role_based_filter(results)
                    # 自动模式角色日期窗口限制
                    results = self.apply_auto_role_date_window(results)
                    self.filtered_results_multi1[project_id] = results
                    # 找到对应项目的原始文件路径
                    original_file = None
                    for file_path, pid in self.target_files1:
                        if pid == project_id:
                            original_file = file_path
                            break
                    if original_file:
                        pid_for_export = project_id if project_id else "未知项目"
                        export_tasks.append(('应打开接口', main.export_result_to_excel, results, original_file, self.current_datetime, pid_for_export))
        
        # 导出待处理文件2的所有项目结果
        if self.process_file2_var.get() and self.processing_results_multi2:
            for project_id, results in self.processing_results_multi2.items():
                if isinstance(results, pd.DataFrame) and not results.empty:
                    results = self.apply_role_based_filter(results)
                    results = self.apply_auto_role_date_window(results)
                    self.filtered_results_multi2[project_id] = results
                    # 找到对应项目的原始文件路径
                    original_file = None
                    for file_path, pid in self.target_files2:
                        if pid == project_id:
                            original_file = file_path
                            break
                    if original_file:
                        pid_for_export = project_id if project_id else "未知项目"
                        export_tasks.append(('需打开接口', main.export_result_to_excel2, results, original_file, self.current_datetime, pid_for_export))
        
        # 导出待处理文件3的所有项目结果
        if self.process_file3_var.get() and self.processing_results_multi3:
            if hasattr(main, 'export_result_to_excel3'):
                for project_id, results in self.processing_results_multi3.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results)
                        results = self.apply_auto_role_date_window(results)
                        self.filtered_results_multi3[project_id] = results
                        # 找到对应项目的原始文件路径
                        original_file = None
                        for file_path, pid in self.target_files3:
                            if pid == project_id:
                                original_file = file_path
                                break
                        if original_file:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('外部接口ICM', main.export_result_to_excel3, results, original_file, self.current_datetime, pid_for_export))
        
        # 导出待处理文件4的所有项目结果
        if self.process_file4_var.get() and self.processing_results_multi4:
            if hasattr(main, 'export_result_to_excel4'):
                for project_id, results in self.processing_results_multi4.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results)
                        results = self.apply_auto_role_date_window(results)
                        self.filtered_results_multi4[project_id] = results
                        # 找到对应项目的原始文件路径
                        original_file = None
                        for file_path, pid in self.target_files4:
                            if pid == project_id:
                                original_file = file_path
                                break
                        if original_file:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('外部接口单', main.export_result_to_excel4, results, original_file, self.current_datetime, pid_for_export))
        # 导出待处理文件5的所有项目结果
        if self.process_file5_var.get() and self.processing_results_multi5:
            if hasattr(main, 'export_result_to_excel5'):
                for project_id, results in self.processing_results_multi5.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results)
                        results = self.apply_auto_role_date_window(results)
                        if not hasattr(self, 'filtered_results_multi5'):
                            self.filtered_results_multi5 = {}
                        self.filtered_results_multi5[project_id] = results
                        original_file = None
                        for file_path, pid in getattr(self, 'target_files5', []):
                            if pid == project_id:
                                original_file = file_path
                                break
                        if original_file:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('三维提资接口', main.export_result_to_excel5, results, original_file, self.current_datetime, pid_for_export))
        # 导出待处理文件6的所有项目结果
        if self.process_file6_var.get() and self.processing_results_multi6:
            if hasattr(main, 'export_result_to_excel6'):
                for project_id, results in self.processing_results_multi6.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results)
                        results = self.apply_auto_role_date_window(results)
                        if not hasattr(self, 'filtered_results_multi6'):
                            self.filtered_results_multi6 = {}
                        self.filtered_results_multi6[project_id] = results
                        original_file = None
                        for file_path, pid in getattr(self, 'target_files6', []):
                            if pid == project_id:
                                original_file = file_path
                                break
                        if original_file:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('收发文函', main.export_result_to_excel6, results, original_file, self.current_datetime, pid_for_export))
        if not export_tasks:
            if not getattr(self, 'auto_mode', False):
               messagebox.showinfo("导出提示", "无可导出的数据")
            return
        
        # 显示导出等待对话框（自动模式下不显示）
        total_count = len(export_tasks)
        export_dialog, progress_label = self.show_export_waiting_dialog("导出结果", "正在导出中，请稍后。。。 。。。", total_count)
        
        # 使用after方法延迟执行导出操作，确保等待对话框能正确显示
        def do_export():
            # 优先使用导出结果位置；为空则回退到文件夹路径
            export_root = (self.export_path_var.get().strip() if hasattr(self, 'export_path_var') else '')
            folder_path = export_root or self.path_var.get().strip()
            success_count = 0
            success_messages = []
            project_stats = {}  # 统计各项目的导出文件数
            
            for i, (name, func, results, original_file, dt, project_id) in enumerate(export_tasks, 1):
                # 更新进度
                self.update_export_progress(export_dialog, progress_label, i-1, total_count)
                
                try:
                    output_path = func(results, original_file, dt, folder_path, project_id)
                    reused = False
                    success_count += 1
                    suffix = "(复用)" if reused else ""
                    success_messages.append(f"{name}(项目{project_id}): {os.path.basename(output_path)}{suffix}")
                    
                    # 统计项目导出数量
                    if project_id not in project_stats:
                        project_stats[project_id] = 0
                    project_stats[project_id] += 1
                    
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
            
            # 显示批量导出成功信息（包含各类型有无导出情况）
            if success_count > 0:
                combined_message = f"🎉 批量导出完成！\n\n"

                # 统计各类型导出条目数
                from collections import defaultdict
                done_counts = defaultdict(int)
                for msg in success_messages:
                    try:
                        type_name = msg.split('(项目', 1)[0]
                        done_counts[type_name] += 1
                    except Exception:
                        continue

                # 类型显示映射（用于用户可读名称统一）
                display_map = {
                    '应打开接口': '内部需打开接口',
                    '需打开接口': '内部需回复接口',
                    '外部接口ICM': '外部需打开接口',
                    '外部接口单': '外部需回复接口',
                    '三维提资接口': '三维提资接口',
                    '收发文函': '收发文函',
                }
                all_types = ['应打开接口', '需打开接口', '外部接口ICM', '外部接口单', '三维提资接口', '收发文函']

                # 添加统计信息
                if len(project_stats) > 1:
                    combined_message += f"📊 导出统计:\n"
                    combined_message += f"• 共导出 {len(project_stats)} 个项目\n"
                    combined_message += f"• 共导出 {success_count} 个文件\n\n"
                else:
                    combined_message += f"📊 导出统计:\n"
                    combined_message += f"• 共导出 {success_count} 个文件\n\n"

                # 各类型导出结果（无则显示“无”）
                combined_message += "📂 各类型导出结果:\n"
                for t in all_types:
                    dn = display_map.get(t, t)
                    cnt = done_counts.get(t, 0)
                    if cnt > 0:
                        combined_message += f"• {dn}：{cnt} 个文件\n"
                    else:
                        combined_message += f"• {dn}：无\n"

                # 详细文件清单
                combined_message += f"\n📋 导出详情:\n"
                combined_message += "\n".join([f"• {msg}" for msg in success_messages])

                if len(project_stats) > 1:
                    combined_message += f"\n\n💡 提示:\n"
                    combined_message += f"• 文件已按项目号自动分文件夹存放\n"
                    combined_message += f"• 各项目的结果文件在对应的\"项目号结果文件\"文件夹中"

                if not getattr(self, 'auto_mode', False):
                   messagebox.showinfo("批量导出完成", combined_message)
        
        # 延迟执行导出操作，确保等待对话框能够显示
        self.root.after(100, do_export)

        # 导出完成后生成结果汇总（放在异步导出流程中完成后执行）
        def write_summary_after_export():
            try:
                import sys, os
                # 安全导入 main2 模块
                try:
                    import main2
                except ImportError:
                    if hasattr(sys, '_MEIPASS'):
                        sys.path.insert(0, sys._MEIPASS)
                    else:
                        sys.path.insert(0, os.path.dirname(__file__))
                    import main2

                # TXT 汇总写入位置：优先使用导出结果位置，其次使用文件夹路径
                export_root = (self.export_path_var.get().strip() if hasattr(self, 'export_path_var') else '')
                summary_folder = export_root or self.path_var.get().strip()
                if summary_folder:
                    # 使用过滤后的结果进行汇总（若无则回退原结果）
                    results_multi1 = getattr(self, 'filtered_results_multi1', getattr(self, 'processing_results_multi1', None))
                    results_multi2 = getattr(self, 'filtered_results_multi2', getattr(self, 'processing_results_multi2', None))
                    results_multi3 = getattr(self, 'filtered_results_multi3', getattr(self, 'processing_results_multi3', None))
                    results_multi4 = getattr(self, 'filtered_results_multi4', getattr(self, 'processing_results_multi4', None))
                    results_multi5 = getattr(self, 'filtered_results_multi5', getattr(self, 'processing_results_multi5', None))
                    results_multi6 = getattr(self, 'filtered_results_multi6', getattr(self, 'processing_results_multi6', None))
                   # 计算总条目数，用于自动模式下是否弹窗
                    def _count_total(multi):
                        try:
                            if not multi:
                                return 0
                            return sum((len(df) if hasattr(df, 'empty') and not df.empty else 0) for df in multi.values())
                        except Exception:
                            return 0
                    
                    total_count = (_count_total(results_multi1)
                                   + _count_total(results_multi2)
                                   + _count_total(results_multi3)
                                   + _count_total(results_multi4)
                                   + _count_total(results_multi5)
                                   + _count_total(results_multi6))
                    txt_path = main2.write_export_summary(
                        folder_path=summary_folder,
                        current_datetime=self.current_datetime,
                        results_multi1=results_multi1,
                        results_multi2=results_multi2,
                        results_multi3=results_multi3,
                        results_multi4=results_multi4,
                        results_multi5=results_multi5,
                        results_multi6=results_multi6,
                    )
                    # 记录本次新生成的汇总文件路径
                    try:
                        if total_count > 0:
                            self.last_summary_written_path = txt_path
                        else:
                            # 无任何结果时，不设置路径，自动模式不弹窗
                            self.last_summary_written_path = None
                    except Exception:
                        pass
            except Exception as _:
                # 汇总失败不影响主流程
                pass

        # 延迟较长时间写汇总，确保导出完成
        self.root.after(1000, write_summary_after_export)

    def open_selected_folder(self):
        """在资源管理器中打开导出结果位置（若未设置则打开选择的文件夹路径）"""
        try:
            import os
            import subprocess
            from tkinter import messagebox

            # 优先导出结果位置；为空则回退到文件夹路径
            export_root = self.export_path_var.get().strip() if hasattr(self, 'export_path_var') else ''
            folder_path = export_root or (self.path_var.get().strip() if hasattr(self, 'path_var') else '')
            if not folder_path:
                messagebox.showwarning("提示", "请先设置导出结果位置或选择文件夹后再尝试打开。")
                return
            if not os.path.exists(folder_path):
                messagebox.showerror("错误", f"目录不存在：\n{folder_path}")
                return

            try:
                # 优先使用 Windows 的原生方式
                os.startfile(folder_path)
            except Exception:
                # 回退到调用 explorer
                try:
                    subprocess.run(["explorer", folder_path], check=False)
                except Exception as e:
                    messagebox.showerror("错误", f"打开目录失败：{e}")
        except Exception as e:
            try:
                from tkinter import messagebox
                messagebox.showerror("错误", f"打开目录时出现问题：{e}")
            except Exception:
                print(f"打开目录时出现问题：{e}")

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

    def _enforce_user_name_gate(self, show_popup: bool = False):
        """当未填写姓名时，禁用“开始处理/导出结果”按钮并提示。"""
        has_name = bool(self.config.get("user_name", "").strip())
        # 控制按钮可用性
        try:
            if (not has_name) and (not getattr(self, 'auto_mode', False)):
                self.process_button.config(state='disabled')
                self.export_button.config(state='disabled')
            else:
                self.process_button.config(state='normal')
                # 导出按钮仍由处理结果决定，保持当前状态
        except Exception:
            pass
        if (show_popup and not getattr(self, 'auto_mode', False)) and not has_name:
            try:
                messagebox.showwarning("提示", "请先在设置中填写‘姓名’，否则无法开始处理或导出结果。")
            except Exception:
                pass

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
                # 自动模式参数 --auto 确保登录后后台自动运行
                startup_cmd = f'"{python_exe}" "{exe_path}" --auto'
            else:
                # 可执行文件同样附加 --auto 参数
                startup_cmd = f'"{exe_path}" --auto'
            
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
                icon_path = get_resource_path("ico_bin/tubiao.ico")
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
        icon_path = get_resource_path("ico_bin/tubiao.ico")
        try:
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                # 兼容Pillow 8.x和9.x+的LANCZOS写法
                try:
                    resample_method = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.LANCZOS)
                except Exception:
                    resample_method = Image.LANCZOS
                image = image.resize((32, 32), resample_method)
            else:
                image = Image.new('RGB', (32, 32), color='blue')
        except Exception as e:
            print(f"加载托盘图标失败: {e}")
            image = Image.new('RGB', (32, 32), color='blue')
        show_item = pystray.MenuItem("打开主程序", self.show_window, default=True)
        menu = pystray.Menu(
            show_item,
            pystray.MenuItem("关闭程序", self.quit_application)
        )
        self.tray_icon = pystray.Icon("ExcelProcessor", image, "Excel数据处理程序", menu)
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
            # 安全导入Monitor模块
            try:
                import Monitor
            except ImportError:
                import sys
                import os
                # 如果是打包环境，添加当前目录到路径
                if hasattr(sys, '_MEIPASS'):
                    sys.path.insert(0, sys._MEIPASS)
                else:
                    sys.path.insert(0, os.path.dirname(__file__))
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
        # 启动定时器（按需）
        try:
            if getattr(self, 'timer_enabled', True):
                # 延迟导入，避免未用时报错
                from time import time as _t
                import threading as _th
                # 内部轻量定时器线程（简化版，不依赖外部文件）
                def _timer_loop(app_ref):
                    import datetime as _dt
                    import time as _sleep
                    started_at = _dt.datetime.now()
                    last_fired = set()
                    while True:
                        try:
                            # 简单退出条件
                            if getattr(app_ref, 'is_closing', False):
                                break
                            now = _dt.datetime.now()
                            # 24h门槛
                            if self.timer_require_24h:
                                if (now - started_at).total_seconds() < 24*3600:
                                    _sleep.sleep(60)
                                    continue
                            # 时间点
                            times_str = (self.timer_times or "10:00,16:00")
                            grace = max(int(self.timer_grace_minutes), 0)
                            for t in [s.strip() for s in times_str.split(',') if s.strip()]:
                                try:
                                    hh, mm = t.split(':')
                                    target = now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
                                except Exception:
                                    continue
                                window_start = target - _dt.timedelta(minutes=grace)
                                window_end = target + _dt.timedelta(minutes=grace)
                                key = now.strftime('%Y-%m-%d') + ' ' + t
                                if window_start <= now <= window_end and key not in last_fired:
                                    last_fired.add(key)
                                    try:
                                        app_ref.root.after(0, app_ref._run_auto_flow)
                                    except Exception:
                                        pass
                            _sleep.sleep(60)
                        except Exception:
                            try:
                                _sleep.sleep(60)
                            except Exception:
                                break
                _th.Thread(target=_timer_loop, args=(self,), daemon=True).start()
        except Exception:
            pass

        if getattr(self, 'auto_mode', False):
            # 自动模式：隐藏窗口
            try:
                self.root.withdraw()
            except Exception:
                pass
            # 自动模式：创建托盘图标，指示程序在后台运行
            try:
                self.create_tray_icon()
            except Exception:
                pass
        self.root.mainloop()

    def _run_auto_flow(self):
        """自动模式流程：校验路径→刷新→开始处理（导出与汇总弹窗由处理完成逻辑触发）"""
        try:
            # 路径判定：导出结果位置优先，其次文件夹路径
            export_root = (self.export_path_var.get().strip() if hasattr(self, 'export_path_var') else '')
            folder_path = self.path_var.get().strip() if hasattr(self, 'path_var') else ''
            export_dir = export_root or folder_path
            if not folder_path:
                # 自动模式下仍提示一次路径缺失
                try:
                    messagebox.showwarning("路径缺失", "默认文件夹路径为空，请先在界面中设置路径后再使用自动模式。")
                except Exception:
                    pass
                return
            # 刷新文件列表（静默）
            self.refresh_file_list(show_popup=False)
            # 延迟以等待刷新完成后开始处理（导出与汇总弹窗在 start_processing 内部触发）
            def after_refresh():
                try:
                    self.process_file1_var.set(True)
                    self.process_file2_var.set(True)
                    self.process_file3_var.set(True)
                    self.process_file4_var.set(True)
                except Exception:
                    pass
                self.start_processing()
            self.root.after(500, after_refresh)
        except Exception as e:
            print(f"自动模式执行失败: {e}")

    def _show_summary_popup(self, txt_path: str):
        """显示汇总TXT内容（自动模式唯一弹窗）"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            content = f"无法读取汇总文件: {e}"
        # 弹窗
        dialog = tk.Toplevel(self.root)
        dialog.title("导出结果汇总")
        dialog.geometry("720x520")
        dialog.transient(self.root)
        dialog.grab_set()
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
            if os.path.exists(icon_path):
                dialog.iconbitmap(icon_path)
        except Exception:
            pass
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        text = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert('1.0', content)
        text.config(state='disabled')
        btn = ttk.Button(frame, text="关闭", command=dialog.destroy)
        btn.pack(pady=(8, 0))


def main():
    """主函数"""
    # 识别 --auto 参数
    auto_mode = False
    try:
        auto_mode = any(arg == "--auto" for arg in sys.argv[1:])
    except Exception:
        auto_mode = False
    app = ExcelProcessorApp(auto_mode=auto_mode)
    app.run()


if __name__ == "__main__":
    main()
