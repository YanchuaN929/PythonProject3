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
from concurrent.futures import ThreadPoolExecutor
from openpyxl import load_workbook

# 导入窗口管理器
from window import WindowManager

# 导入任务指派模块
try:
    import distribution
except ImportError:
    print("警告: 未找到distribution模块")
    distribution = None

# 导入Registry模块
try:
    from registry import hooks as registry_hooks
except ImportError:
    print("警告: 未找到registry模块")
    registry_hooks = None

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


# ============================================================================
# Excel读取优化工具函数（方案1+3：只读模式 + 并发读取）
# ============================================================================

def optimized_read_excel(file_path, use_openpyxl_readonly=True):
    """
    优化的Excel读取方法（方案1：openpyxl只读模式）
    
    参数:
        file_path: Excel文件路径
        use_openpyxl_readonly: 是否使用只读模式（默认True，提升30-50%速度）
    
    返回:
        pandas.DataFrame
    
    性能提升:
        - 速度: 提升30-50%
        - 内存: 减少40-60%
    """
    try:
        if file_path.endswith('.xlsx') and use_openpyxl_readonly:
            # 方案1: 使用openpyxl只读模式（速度提升30-50%）
            wb = load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            
            # 快速读取为DataFrame
            data = ws.values
            columns = next(data)  # 第一行作为列名
            df = pd.DataFrame(data, columns=columns)
            wb.close()
            
            return df
        elif file_path.endswith('.xlsx'):
            # 回退到标准方法（如果禁用只读模式）
            return pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
        else:
            # .xls文件使用xlrd引擎
            return pd.read_excel(file_path, sheet_name=0, engine='xlrd')
    except Exception as e:
        print(f"优化读取失败，回退到标准方法: {e}")
        # 失败时回退到原始方法
        if file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
        else:
            return pd.read_excel(file_path, sheet_name=0, engine='xlrd')


def concurrent_read_excel_files(file_paths, max_workers=4):
    """
    并发读取多个Excel文件（方案3：并发读取）
    
    参数:
        file_paths: 文件路径列表 [(file_path, file_id), ...]
        max_workers: 最大并发线程数（默认4）
    
    返回:
        dict: {file_id: DataFrame}
    
    性能提升:
        - 6个文件：从50秒降至18秒（提升64%）
    """
    def read_single_file(file_info):
        """读取单个文件的辅助函数"""
        file_path, file_id = file_info
        try:
            df = optimized_read_excel(file_path)
            print(f"✓ 并发读取完成: {os.path.basename(file_path)}")
            return file_id, df
        except Exception as e:
            print(f"✗ 并发读取失败 {os.path.basename(file_path)}: {e}")
            return file_id, None
    
    # 使用线程池并发读取
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = dict(executor.map(
            lambda x: read_single_file(x),
            file_paths
        ))
    
    return results


class ExcelProcessorApp:
    """主应用程序类"""
    
    def __init__(self, auto_mode: bool = False):
        self.auto_mode = auto_mode
        self._manual_operation = False  # 标记当前操作是否为手动触发（用于弹窗控制）
        self.root = tk.Tk()
        self.load_config()
        
        # 【多用户协作】如果配置中已有数据文件夹路径，立即设置
        folder_path = self.config.get('folder_path', '').strip()
        if folder_path:
            try:
                from registry import hooks as registry_hooks
                registry_hooks.set_data_folder(folder_path)
            except Exception as e:
                print(f"[Registry] 设置数据文件夹失败: {e}")
        
        # 【修复】加载用户角色（必须在load_config之后，确保能读取默认姓名）
        try:
            self.load_user_role()
        except Exception as e:
            print(f"初始化加载角色失败: {e}")
            # 初始化空角色变量，避免后续出错
            self.user_name = self.config.get("user_name", "").strip()
            self.user_role = ""
            self.user_roles = []
        
        # 初始化文件管理器（用于勾选状态管理）
        from file_manager import get_file_manager
        self.file_manager = get_file_manager()
        
        # 项目号筛选变量（6个项目号，默认全选）
        self.project_1818_var = tk.BooleanVar(master=self.root, value=True)
        self.project_1907_var = tk.BooleanVar(master=self.root, value=True)
        self.project_1916_var = tk.BooleanVar(master=self.root, value=True)
        self.project_2016_var = tk.BooleanVar(master=self.root, value=True)
        self.project_2026_var = tk.BooleanVar(master=self.root, value=True)
        self.project_2306_var = tk.BooleanVar(master=self.root, value=True)
        
        # 六个勾选框变量（指定root作为master）
        self.process_file1_var = tk.BooleanVar(master=self.root, value=True)
        self.process_file2_var = tk.BooleanVar(master=self.root, value=True)
        self.process_file3_var = tk.BooleanVar(master=self.root, value=True)
        self.process_file4_var = tk.BooleanVar(master=self.root, value=True)
        self.process_file5_var = tk.BooleanVar(master=self.root, value=True)
        self.process_file6_var = tk.BooleanVar(master=self.root, value=True)
        
        # 初始化设置相关变量（必须在WindowManager之前）
        self.auto_startup_var = tk.BooleanVar(master=self.root, value=self.config.get("auto_startup", False))
        self.show_close_dialog_var = tk.BooleanVar(master=self.root, value=not self.config.get("dont_ask_again", False))
        
        # 准备WindowManager需要的参数
        process_vars = {
            'tab1': self.process_file1_var,
            'tab2': self.process_file2_var,
            'tab3': self.process_file3_var,
            'tab4': self.process_file4_var,
            'tab5': self.process_file5_var,
            'tab6': self.process_file6_var,
        }
        
        callbacks = {
            'on_browse_folder': self.browse_folder,
            'on_browse_export_folder': self.browse_export_folder,
            'on_refresh_files': self.refresh_file_list,
            'on_start_processing': self._on_manual_start_processing,  # 使用手动操作包装器
            'on_export_results': self._on_manual_export_results,      # 使用手动操作包装器
            'on_open_folder': self.open_selected_folder,
            'on_open_monitor': self.open_monitor,
            'on_settings_menu': self.show_settings_menu,
            'on_tab_changed': lambda: self.on_tab_changed(None),  # 包装函数，传递None作为event
            'on_assignment_click': self._on_assignment_button_click,  # 【新增】指派任务回调
        }
        
        config_data = {
            'folder_path': self.config.get('folder_path', ''),
            'export_folder_path': self.config.get('export_folder_path', ''),
        }
        
        project_vars = {
            '1818': self.project_1818_var,
            '1907': self.project_1907_var,
            '1916': self.project_1916_var,
            '2016': self.project_2016_var,
            '2026': self.project_2026_var,
            '2306': self.project_2306_var,
        }
        
        # 使用WindowManager创建界面
        self.window_manager = WindowManager(self.root, callbacks)
        # 设置app引用，供WindowManager中需要访问用户信息的方法使用
        self.window_manager.app = self
        self.window_manager.setup(config_data, process_vars, project_vars)
        
        # 保存UI组件引用（向后兼容）
        self.path_var = self.window_manager.path_var
        self.export_path_var = self.window_manager.export_path_var
        self.file_info_text = self.window_manager.file_info_text
        self.notebook = self.window_manager.notebook
        self.export_button = self.window_manager.buttons.get('export')
        self.process_button = self.window_manager.buttons.get('process')
        self.assignment_button = self.window_manager.buttons.get('assignment')  # 【新增】指派任务按钮引用
        
        # 保存tab viewers引用
        self.tab1_viewer = self.window_manager.viewers['tab1']
        self.tab2_viewer = self.window_manager.viewers['tab2']
        self.tab3_viewer = self.window_manager.viewers['tab3']
        self.tab4_viewer = self.window_manager.viewers['tab4']
        self.tab5_viewer = self.window_manager.viewers['tab5']
        self.tab6_viewer = self.window_manager.viewers['tab6']
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
    
    def _should_show_popup(self):
        """
        判断当前操作是否应该显示弹窗
        逻辑：手动操作时显示弹窗，自动运行且非手动操作时不显示
        """
        # 如果标记为手动操作，则显示弹窗（即使程序是以auto模式启动的）
        if self._manual_operation:
            return True
        # 如果不是auto模式，则显示弹窗
        if not self.auto_mode:
            return True
        # 否则（auto模式且非手动操作），不显示弹窗
        return False
    
    def get_enabled_projects(self):
        """
        获取用户勾选的项目号列表
        返回: 勾选的项目号列表，如 ['1818', '1907', ...]
        """
        enabled_projects = []
        if self.project_1818_var.get():
            enabled_projects.append('1818')
        if self.project_1907_var.get():
            enabled_projects.append('1907')
        if self.project_1916_var.get():
            enabled_projects.append('1916')
        if self.project_2016_var.get():
            enabled_projects.append('2016')
        if self.project_2026_var.get():
            enabled_projects.append('2026')
        if self.project_2306_var.get():
            enabled_projects.append('2306')
        return enabled_projects
    
    def _filter_files_by_project(self, file_list, enabled_projects, file_type_name):
        """
        根据项目号筛选文件列表
        
        参数:
            file_list: 文件列表 [(文件路径, 项目号), ...]
            enabled_projects: 用户勾选的项目号列表
            file_type_name: 文件类型名称（用于日志）
        
        返回:
            (filtered_files, ignored_files): 
                - filtered_files: 筛选后的文件列表
                - ignored_files: 被忽略的文件列表 [(文件路径, 项目号, 文件类型), ...]
        """
        if not file_list:
            return [], []
        
        filtered = []
        ignored = []
        
        for file_path, project_id in file_list:
            if project_id in enabled_projects:
                filtered.append((file_path, project_id))
            else:
                ignored.append((file_path, project_id, file_type_name))
                print(f"项目号筛选: 忽略项目{project_id}的{file_type_name} - {os.path.basename(file_path)}")
        
        return filtered, ignored
    
    def _on_manual_start_processing(self):
        """手动点击"开始处理"按钮的包装器"""
        self._manual_operation = True
        self.start_processing()
    
    def _on_manual_export_results(self):
        """手动点击"导出结果"按钮的包装器"""
        self._manual_operation = True
        self.export_results()

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
            "simple_export_mode": False,  # 简洁导出模式（仅管理员可用，导出时只显示个数不显示接口号）
            # 自动运行导出日期窗口（按角色）。含义：截止日期与今天的天数差 <= 指定天数 才导出；允许为负（已超期）
            "role_export_days": {
                "一室主任": 7,
                "二室主任": 7,
                "建筑总图室主任": 7,
                "所领导": 2,
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
                            elif key in ("auto_startup","minimize_to_tray","dont_ask_again","hide_previous_months","simple_export_mode"):
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
            lines.append(f"  simple_export_mode: {'true' if self.config.get('simple_export_mode', False) else 'false'}")
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
        # 使用WindowManager的show_empty_message方法
        self.window_manager.show_empty_message(viewer, message)

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
                # 不要drop原始行号列，因为需要它来加载勾选状态
                excel_row_numbers = list(self.processing_results2['原始行号'])
                self.display_excel_data_with_original_rows(self.tab2_viewer, self.processing_results2, "内部需回复接口", excel_row_numbers)
            elif self.has_processed_results2:
                self.show_empty_message(self.tab2_viewer, "无内部需回复接口")
            elif self.file2_data is not None:
                self.display_excel_data(self.tab2_viewer, self.file2_data, "内部需回复接口")
            else:
                self.load_file_to_viewer(self.target_file2, self.tab2_viewer, "内部需回复接口")
        elif selected_tab == 2 and self.target_file3:  # 外部需打开接口
            if self.has_processed_results3 and self.processing_results3 is not None and not self.processing_results3.empty:
                # 不要drop原始行号列，因为需要它来加载勾选状态
                excel_row_numbers = list(self.processing_results3['原始行号'])
                self.display_excel_data_with_original_rows(self.tab3_viewer, self.processing_results3, "外部需打开接口", excel_row_numbers)
            elif self.has_processed_results3:
                self.show_empty_message(self.tab3_viewer, "无外部需打开接口")
            elif self.file3_data is not None:
                self.display_excel_data(self.tab3_viewer, self.file3_data, "外部需打开接口")
            else:
                self.load_file_to_viewer(self.target_file3, self.tab3_viewer, "外部需打开接口")
        elif selected_tab == 3 and self.target_file4:  # 外部需回复接口
            if self.has_processed_results4 and self.processing_results4 is not None and not self.processing_results4.empty:
                # 不要drop原始行号列，因为需要它来加载勾选状态
                excel_row_numbers = list(self.processing_results4['原始行号'])
                self.display_excel_data_with_original_rows(self.tab4_viewer, self.processing_results4, "外部需回复接口", excel_row_numbers)
            elif self.has_processed_results4:
                self.show_empty_message(self.tab4_viewer, "无外部需回复接口")
            elif self.file4_data is not None:
                self.display_excel_data(self.tab4_viewer, self.file4_data, "外部需回复接口")
            else:
                self.load_file_to_viewer(self.target_file4, self.tab4_viewer, "外部需回复接口")
        elif selected_tab == 4 and getattr(self, 'target_files5', None):  # 三维提资接口
            if self.has_processed_results5 and self.processing_results5 is not None and not self.processing_results5.empty:
                # 不要drop原始行号列，因为需要它来加载勾选状态
                excel_row_numbers = list(self.processing_results5['原始行号'])
                self.display_excel_data_with_original_rows(self.tab5_viewer, self.processing_results5, "三维提资接口", excel_row_numbers)
            elif self.has_processed_results5:
                # 【修复】处理后无数据，显示空提示，不显示原始数据
                self.show_empty_message(self.tab5_viewer, "无三维提资接口")
        elif selected_tab == 5 and getattr(self, 'target_files6', None):  # 收发文函
            if self.has_processed_results6 and self.processing_results6 is not None and not self.processing_results6.empty:
                # 不要drop原始行号列，因为需要它来加载勾选状态
                excel_row_numbers = list(self.processing_results6['原始行号'])
                self.display_excel_data_with_original_rows(self.tab6_viewer, self.processing_results6, "收发文函", excel_row_numbers)
            elif self.has_processed_results6:
                self.show_empty_message(self.tab6_viewer, "无需要回复的文函")
            elif self.file6_data is not None:
                self.display_excel_data(self.tab6_viewer, self.file6_data, "收发文函")

    def load_file_to_viewer(self, file_path, viewer, tab_name):
        """加载Excel文件到预览器（优化版：使用只读模式）"""
        import os
        
        try:
            print(f"正在加载 {tab_name} 文件: {os.path.basename(file_path)}")
            
            # 使用优化的读取方法（方案1：只读模式，速度提升30-50%）
            df = optimized_read_excel(file_path)
            
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
        """在viewer中显示Excel数据（初始加载-预览前20行）"""
        # 使用WindowManager的display_excel_data方法，仅显示前20行
        self.window_manager.display_excel_data(
            viewer=viewer,
            df=df,
            tab_name=tab_name,
            show_all=False,  # 初始加载时仅显示前20行
            original_row_numbers=None
        )
        print(f"{tab_name}数据预览已加载：显示前20行")

    def display_excel_data_with_original_rows(self, viewer, df, tab_name, original_row_numbers, source_files=None):
        """
        在viewer中显示Excel数据，使用原始Excel行号（处理结果-显示全部数据）
        
        参数:
            source_files: 源文件路径列表（用于勾选功能），可选
        """
        # 如果没有提供source_files，尝试从当前处理的文件中获取
        if source_files is None:
            source_files = self._get_source_files_for_tab(tab_name)
        
        # 【新增】获取当前用户的角色列表
        user_roles = getattr(self, 'user_roles', [])
        if not user_roles:
            # 兼容：如果没有user_roles，尝试从user_role获取
            user_role = getattr(self, 'user_role', '').strip()
            if user_role:
                user_roles = [user_role]
        
        # 使用WindowManager的display_excel_data方法，显示全部数据
        self.window_manager.display_excel_data(
            viewer=viewer,
            df=df,
            tab_name=tab_name,
            show_all=True,  # 处理完成后显示全部数据
            original_row_numbers=original_row_numbers,
            source_files=source_files,
            file_manager=self.file_manager,
            current_user_roles=user_roles  # 【新增】传递用户角色列表
        )
        print(f"{tab_name}处理结果已显示：{len(df)} 行（全部数据，支持滚动）")

    def _exclude_completed_rows(self, df, source_file):
        """
        从DataFrame中排除已勾选（已完成）的行
        
        参数:
            df: pandas DataFrame（必须包含"原始行号"列）
            source_file: 源文件路径
            
        返回:
            过滤后的DataFrame
        """
        try:
            if df is None or df.empty:
                return df
            
            # 检查是否有"原始行号"列
            if "原始行号" not in df.columns:
                print(f"警告：DataFrame中没有'原始行号'列，无法排除已完成行")
                return df
            
            # 【修复】获取已完成的行号集合，传入用户姓名
            user_name = getattr(self, 'user_name', '').strip()
            completed_rows = self.file_manager.get_completed_rows(source_file, user_name)
            
            if not completed_rows:
                # 没有已完成的行，直接返回
                return df
            
            # 过滤掉已完成的行
            original_count = len(df)
            df_filtered = df[~df['原始行号'].isin(completed_rows)].copy()
            filtered_count = original_count - len(df_filtered)
            
            if filtered_count > 0:
                print(f"导出时排除了{filtered_count}行已完成的数据（文件：{source_file}）")
            
            return df_filtered
            
        except Exception as e:
            print(f"排除已完成行时出错: {e}")
            import traceback
            traceback.print_exc()
            return df  # 出错时返回原始数据，确保导出不受影响
    
    def _exclude_pending_confirmation_rows(self, df, source_file, file_type, project_id):
        """
        从DataFrame中排除待确认的任务行（用于导出）
        
        参数:
            df: pandas DataFrame（必须包含"原始行号"、"接口号"列）
            source_file: 源文件路径
            file_type: 文件类型（1-6）
            project_id: 项目号
            
        返回:
            过滤后的DataFrame
        """
        try:
            if df is None or df.empty:
                return df
            
            # 检查必要列
            if "原始行号" not in df.columns:
                print(f"[Registry] 警告：DataFrame中没有'原始行号'列，无法过滤待确认行")
                return df
            
            # 【Registry】查询所有待确认的任务
            from registry import hooks as registry_hooks
            from registry.util import extract_interface_id, extract_project_id, make_task_id
            
            print(f"\n========== [Registry导出] 开始过滤 文件类型{file_type} ==========")
            print(f"[Registry导出] 输入DataFrame: {len(df)}行")
            
            # 构造task_keys
            task_keys = []
            df_index_map = {}  # task_id -> df_index映射
            for idx in range(len(df)):
                try:
                    row_data = df.iloc[idx]
                    interface_id = extract_interface_id(row_data, file_type)
                    proj_id = extract_project_id(row_data, file_type) or project_id
                    row_index = row_data.get("原始行号", idx + 2)
                    
                    if interface_id and proj_id:
                        task_key = {
                            'file_type': file_type,
                            'project_id': proj_id,
                            'interface_id': interface_id,
                            'source_file': source_file,
                            'row_index': row_index
                        }
                        task_keys.append(task_key)
                        
                        # 记录映射关系
                        tid = make_task_id(
                            file_type, proj_id, interface_id,
                            source_file, row_index
                        )
                        df_index_map[tid] = idx
                except Exception as e:
                    continue
            
            if not task_keys:
                return df
            
            # 批量查询状态
            status_map = registry_hooks.get_display_status(task_keys)
            
            # 【修复】根据用户角色决定过滤逻辑
            user_roles = getattr(self, 'user_roles', [])
            if not user_roles:
                user_role = getattr(self, 'user_role', '').strip()
                if user_role:
                    user_roles = [user_role]
            
            # 判断是否为设计人员
            is_designer = '设计人员' in user_roles
            is_superior = any(keyword in ' '.join(user_roles) for keyword in ['所领导', '室主任', '接口工程师'])
            
            exclude_indices = []
            
            if is_designer and not is_superior:
                # 设计人员：过滤掉"待审查"和"待指派人审查"的任务
                for tid, status_text in status_map.items():
                    # 去除emoji和延期前缀
                    clean_status = status_text.replace('⏳', '').replace('📌', '').replace('❗', '').replace('（已延期）', '').strip()
                    if clean_status in ['待审查', '待指派人审查', '待上级确认', '待指派人确认'] and tid in df_index_map:
                        exclude_indices.append(df_index_map[tid])
                        print(f"[Registry导出调试] 设计人员过滤：{clean_status}, 接口={tid[:20]}...")
                    # 也过滤已确认的任务
                    elif not status_text and tid in df_index_map:
                        exclude_indices.append(df_index_map[tid])
                        print(f"[Registry导出调试] 过滤已确认任务: 接口={tid[:20]}...")
            else:
                # 上级角色：只过滤已确认的任务
                for tid, status_text in status_map.items():
                    # 如果status_text为空，说明任务已确认或已归档，不导出
                    if not status_text and tid in df_index_map:
                        exclude_indices.append(df_index_map[tid])
                        print(f"[Registry导出调试] 上级过滤已确认任务: 接口={tid[:20]}...")
            
            if not exclude_indices:
                return df
            
            # 过滤掉指定的行
            original_count = len(df)
            df_filtered = df.drop(df.index[exclude_indices]).reset_index(drop=True)
            filtered_count = len(exclude_indices)
            
            if filtered_count > 0:
                role_desc = "设计人员" if (is_designer and not is_superior) else "上级角色"
                print(f"[Registry导出] {role_desc}过滤: 排除 {filtered_count} 条")
                print(f"[Registry导出] 输出DataFrame: {len(df_filtered)}行")
            else:
                print(f"[Registry导出] 无需过滤")
            
            print(f"========== [Registry导出] 过滤完成 ==========\n")
            
            return df_filtered
            
        except Exception as e:
            print(f"[Registry] 排除待确认行时出错（不影响主流程）: {e}")
            return df
    
    def _get_source_files_for_tab(self, tab_name):
        """
        根据tab名称获取对应的源文件路径列表
        
        参数:
            tab_name: 选项卡名称
            
        返回:
            源文件路径列表
        """
        try:
            # 根据tab名称映射到对应的target_files属性
            tab_file_mapping = {
                "内部需打开接口": "target_files1",
                "内部需回复接口": "target_files2",
                "外部需打开接口": "target_files3",
                "外部需回复接口": "target_files4",
                "三维提资接口": "target_files5",
                "收发文函": "target_files6"
            }
            
            attr_name = tab_file_mapping.get(tab_name)
            if not attr_name:
                return []
            
            target_files = getattr(self, attr_name, None)
            if not target_files:
                return []
            
            # target_files格式: [(file_path, project_id), ...]
            # 提取所有文件路径
            file_paths = [f[0] for f in target_files if isinstance(f, tuple) and len(f) >= 1]
            return file_paths
            
        except Exception as e:
            print(f"获取源文件列表失败: {e}")
            return []

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

    def _parse_interface_engineer_role(self, role: str):
        """
        解析接口工程师角色，提取项目号
        例如："2016接口工程师" -> "2016"
        返回：项目号字符串，如果不是接口工程师角色则返回None
        """
        import re
        match = re.match(r'^(\d{4})接口工程师$', role.strip())
        if match:
            return match.group(1)
        return None
    
    def _filter_by_single_role(self, df: pd.DataFrame, role: str, project_id: str = None) -> pd.DataFrame:
        """
        根据单个角色过滤数据
        
        参数:
            df: 原始数据
            role: 单个角色（如"设计人员"、"2016接口工程师"等）
            project_id: 当前数据的项目号（用于接口工程师筛选）
        
        返回:
            过滤后的DataFrame
        """
        try:
            user_name = getattr(self, 'user_name', '').strip()
            if not role or not user_name:
                return df.iloc[0:0]  # 返回空DataFrame
            
            safe_df = df.copy()
            
            # 1. 接口工程师：按项目号筛选所有数据
            engineer_project = self._parse_interface_engineer_role(role)
            if engineer_project:
                # 如果当前数据的项目号与接口工程师负责的项目号匹配，则返回全部数据
                if project_id == engineer_project:
                    return safe_df
                else:
                    return safe_df.iloc[0:0]  # 项目号不匹配，返回空
            
            # 2. 设计人员：责任人 == 姓名
            if role == '设计人员':
                if '责任人' in safe_df.columns:
                    return safe_df[safe_df['责任人'].astype(str).str.strip() == user_name]
                return safe_df
            
            # 3. 一室主任：科室 ∈ {结构一室, 请室主任确认}
            if role == '一室主任':
                if '科室' in safe_df.columns:
                    return safe_df[safe_df['科室'].isin(['结构一室', '请室主任确认'])]
                return safe_df
            
            # 4. 二室主任：科室 ∈ {结构二室, 请室主任确认}
            if role == '二室主任':
                if '科室' in safe_df.columns:
                    return safe_df[safe_df['科室'].isin(['结构二室', '请室主任确认'])]
                return safe_df
            
            # 5. 建筑总图室主任：科室 ∈ {建筑总图室, 请室主任确认}
            if role == '建筑总图室主任':
                if '科室' in safe_df.columns:
                    return safe_df[safe_df['科室'].isin(['建筑总图室', '请室主任确认'])]
                return safe_df
            
            # 6. 所领导：不区分科室，但需应用2个工作日的时间窗口
            #    时间窗口定义：所有已延期数据 + 未来2个工作日内到期的数据
            if role == '所领导':
                # 检查是否有"接口时间"列
                if '接口时间' not in safe_df.columns:
                    return safe_df
                
                # 应用2个工作日的时间窗口过滤
                from datetime import date
                from date_utils import get_workday_difference, parse_mmdd_to_date
                
                today = date.today()
                max_workdays = 2  # 所领导：未来2个工作日
                
                kept_idx = []
                for idx, time_val in safe_df["接口时间"].items():
                    if pd.isna(time_val) or str(time_val).strip() in ['', '-']:
                        # 空值不保留
                        continue
                    
                    try:
                        # 使用统一的日期解析函数（正确处理跨年和跨月）
                        due_date = parse_mmdd_to_date(str(time_val).strip(), today)
                        if due_date is None:
                            continue
                        
                        # 使用工作日计算（参数：目标日期，参考日期）
                        workday_diff = get_workday_difference(due_date, today)
                        
                        # 保留条件：
                        # 1. 已延期（workday_diff < 0）：全部保留
                        # 2. 今天到期（workday_diff == 0）：保留
                        # 3. 未来2个工作日内（0 < workday_diff <= 2）：保留
                        # 4. 超过2个工作日（workday_diff > 2）：不保留
                        if workday_diff <= max_workdays:
                            kept_idx.append(idx)
                    except Exception as e:
                        # 解析失败，不保留（调试时可打印错误）
                        # print(f"日期解析失败 [{time_val}]: {e}")
                        continue
                
                if not kept_idx:
                    return safe_df.iloc[0:0]  # 返回空DataFrame
                
                return safe_df.loc[kept_idx]
            
            # 7. 管理员或其他未知角色：不过滤
            return safe_df
        except Exception as e:
            print(f"单角色过滤失败 [{role}]: {e}")
            return df.iloc[0:0]
    
    def apply_role_based_filter(self, df: pd.DataFrame, project_id: str = None) -> pd.DataFrame:
        """
        根据姓名与角色对结果进行过滤（支持多角色）
        
        依赖列：'科室'、'责任人'、'原始行号'。缺列时安全回退为原df。
        
        角色映射：
          - 设计人员：责任人 == 姓名
          - 接口工程师（如"2016接口工程师"）：处理对应项目的所有数据
          - 一室主任：科室 ∈ {结构一室, 请室主任确认}
          - 二室主任：科室 ∈ {结构二室, 请室主任确认}
          - 建筑总图室主任：科室 ∈ {建筑总图室, 请室主任确认}
          - 所领导：不区分科室，查看所有数据
          - 管理员或空角色/姓名：不过滤
        
        多角色处理：
          - 分别按每个角色筛选
          - 合并结果（去重）
          - 为每条数据添加"角色来源"列
        
        参数:
            df: 原始数据
            project_id: 项目号（用于接口工程师筛选）
        
        返回:
            过滤后的DataFrame，包含"角色来源"列
        """
        try:
            user_name = getattr(self, 'user_name', '').strip()
            user_roles = getattr(self, 'user_roles', [])
            
            # 兼容旧逻辑：如果没有user_roles，尝试从user_role解析
            if not user_roles:
                user_role = getattr(self, 'user_role', '').strip()
                if user_role:
                    user_roles = [user_role]
            
            # 【调试】打印角色筛选信息
            print(f"🔍 角色筛选: user_name={user_name}, user_roles={user_roles}, project_id={project_id}")
            
            if not user_roles or not user_name:
                print(f"⚠️ 角色筛选跳过: 用户名或角色为空，返回原始数据（{len(df)}行）")
                return df
            
            safe_df = df.copy()
            
            # 如果只有一个角色且不是接口工程师，使用旧逻辑（向后兼容）
            if len(user_roles) == 1 and not self._parse_interface_engineer_role(user_roles[0]):
                filtered = self._filter_by_single_role(safe_df, user_roles[0], project_id)
                # 添加角色来源列
                if not filtered.empty and '角色来源' not in filtered.columns:
                    filtered['角色来源'] = user_roles[0]
                print(f"✅ 单角色筛选完成: 输入{len(safe_df)}行，输出{len(filtered)}行，角色来源列={'已添加' if '角色来源' in filtered.columns else '未添加'}")
                return filtered
            
            # 多角色处理：分别筛选，然后合并
            all_results = []
            role_map = {}  # {原始行号: [角色列表]}
            
            for role in user_roles:
                filtered = self._filter_by_single_role(safe_df, role, project_id)
                if not filtered.empty:
                    all_results.append(filtered)
                    # 记录每个原始行号对应的角色
                    for idx in filtered.index:
                        original_row = filtered.loc[idx, '原始行号'] if '原始行号' in filtered.columns else idx
                        if original_row not in role_map:
                            role_map[original_row] = []
                        role_map[original_row].append(role)
            
            if not all_results:
                return safe_df.iloc[0:0]
            
            # 合并所有结果（按原始行号去重）
            merged = pd.concat(all_results, ignore_index=False)
            if '原始行号' in merged.columns:
                merged = merged.drop_duplicates(subset=['原始行号'], keep='first')
            else:
                merged = merged.drop_duplicates(keep='first')
            
            # 添加角色来源列
            if '原始行号' in merged.columns:
                merged['角色来源'] = merged['原始行号'].apply(
                    lambda x: '、'.join(role_map.get(x, []))
                )
            else:
                # 如果没有原始行号，只能用第一个角色
                merged['角色来源'] = user_roles[0] if user_roles else ''
            
            print(f"✅ 角色筛选完成: 输入{len(safe_df)}行，输出{len(merged)}行，角色来源列={'已添加' if '角色来源' in merged.columns else '未添加'}")
            
            return merged
        except Exception as e:
            print(f"角色过滤失败: {e}")
            return df

    def apply_auto_role_date_window(self, df: pd.DataFrame) -> pd.DataFrame:
        """自动运行模式下，按角色限定导出的日期窗口。
        依据列：'接口时间'（格式 mm.dd）。
        规则：仅当 auto_mode=True 且 用户角色在 role_export_days 映射中时生效；
             仅保留 (due_date - today).days <= 指定天数 的记录（支持负值，即已超期亦保留）。
             对于"所领导"、"一室主任"、"二室主任"、"建筑总图室主任"，使用工作日计算（排除周六周日）。
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
            from date_utils import get_workday_difference, parse_mmdd_to_date
            
            today = date.today()
            # 判断是否使用工作日计算（所领导、室主任使用工作日）
            # 管理员、设计人员无天数限制；接口工程师不在此配置中
            use_workdays = (user_role in ["所领导", "一室主任", "二室主任", "建筑总图室主任"])
            
            kept_idx = []
            for idx, val in df["接口时间"].items():
                try:
                    s = str(val).strip()
                    if not s or s == "未知":
                        continue
                    
                    # 使用统一的日期解析函数（正确处理跨年和跨月）
                    due = parse_mmdd_to_date(s, today)
                    if due is None:
                        continue
                    
                    # 根据角色选择计算方式
                    if use_workdays:
                        delta = get_workday_difference(due, today)
                    else:
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
        """
        加载用户角色：从 excel_bin/姓名角色表.xlsx 中读取 A列=姓名，B列=角色
        支持多重角色（用顿号、分隔），识别接口工程师角色
        """
        self.user_name = self.config.get("user_name", "").strip()
        self.user_role = ""
        self.user_roles = []  # 新增：角色列表
        if not self.user_name:
            return
        try:
            xls_path = get_resource_path("excel_bin/姓名角色表.xlsx")
            if not os.path.exists(xls_path):
                return
            # 使用优化的读取方法
            df = optimized_read_excel(xls_path)
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
                        self.user_role = role_val  # 保留原始字符串（兼容性）
                        # 解析多重角色（用顿号、分隔）
                        self.user_roles = [r.strip() for r in role_val.split('、') if r.strip()]
                        print(f"加载角色成功: 用户={self.user_name}, 角色={self.user_roles}")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"加载角色表失败: {e}")
            pass
    
    def get_valid_names_from_role_table(self):
        """
        从姓名角色表中获取所有有效姓名列表
        
        返回:
            set: 有效姓名集合（去除空值和无效值）
        """
        valid_names = set()
        try:
            xls_path = get_resource_path("excel_bin/姓名角色表.xlsx")
            if not os.path.exists(xls_path):
                print("姓名角色表不存在")
                return valid_names
            
            # 使用优化的读取方法
            df = optimized_read_excel(xls_path)
            
            # 兼容无表头/不同表头
            cols = list(df.columns)
            name_col = None
            for i, c in enumerate(cols):
                cs = str(c)
                if name_col is None and (cs.find('姓名') != -1):
                    name_col = i
            if name_col is None:
                name_col = 0 if len(cols) >= 1 else None
            
            if name_col is None:
                return valid_names
            
            # 收集所有有效姓名
            for _, row in df.iterrows():
                try:
                    name_val = str(row.iloc[name_col]).strip()
                    if name_val and name_val not in ['nan', 'None', '']:
                        valid_names.add(name_val)
                except Exception:
                    continue
            
            print(f"从姓名角色表加载了 {len(valid_names)} 个有效姓名")
            return valid_names
            
        except Exception as e:
            print(f"加载姓名角色表失败: {e}")
            return valid_names

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
            
            # 【多用户协作】设置数据文件夹路径，数据库将创建在该文件夹下
            try:
                from registry import hooks as registry_hooks
                registry_hooks.set_data_folder(folder_path)
            except Exception as e:
                print(f"[Registry] 设置数据文件夹失败: {e}")
            
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
        settings_menu.geometry("560x460")  # 增加高度以适应新增的"简洁显示模式"选项
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
            # 【新增】角色改变后，重新筛选和显示所有已处理的数据
            try:
                self.refresh_all_processed_results()
            except Exception as e:
                print(f"刷新已处理结果失败: {e}")
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

        # 简洁显示模式（仅管理员可见）
        self.simple_export_mode_var = tk.BooleanVar(value=self.config.get("simple_export_mode", False))
        def on_toggle_simple_export():
            self.config["simple_export_mode"] = self.simple_export_mode_var.get()
            self.save_config()
        
        simple_export_check = ttk.Checkbutton(
            frame,
            text="简洁显示模式（导出时只显示个数）",
            variable=self.simple_export_mode_var,
            command=on_toggle_simple_export
        )
        
        # 仅当用户角色为管理员时显示
        if "管理员" in self.user_roles:
            simple_export_check.pack(anchor=tk.W, pady=(0, 10))

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

        # 清除缓存按钮
        def on_clear_cache():
            """清除所有缓存"""
            try:
                # 弹窗确认
                from tkinter import messagebox as _mb
                result = _mb.askyesno("确认清除", 
                    "确定要清除所有缓存吗？\n\n"
                    "这将删除：\n"
                    "• 所有处理结果缓存\n"
                    "• 所有勾选状态\n"
                    "• 文件标识信息\n\n"
                    "清除后需要重新处理文件。",
                    parent=settings_menu)
                
                if result:
                    # 清除缓存
                    success = self.file_manager.clear_all_caches()
                    if success:
                        _mb.showinfo("成功", "所有缓存已清除！", parent=settings_menu)
                    else:
                        _mb.showerror("失败", "清除缓存时发生错误，请查看控制台输出。", parent=settings_menu)
            except Exception as e:
                print(f"清除缓存失败: {e}")
                try:
                    from tkinter import messagebox as _mb
                    _mb.showerror("错误", f"清除缓存失败：{e}", parent=settings_menu)
                except:
                    pass
        
        cache_button = ttk.Button(frame, text="清除缓存", command=on_clear_cache, width=14)
        cache_button.pack(pady=(10, 0))
        
        # 关闭按钮
        close_button = ttk.Button(frame, text="确定", command=settings_menu.destroy, width=14)
        close_button.pack(pady=(5, 0))

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
        
        # 标记为手动操作（用于弹窗控制）
        self._manual_operation = True
        
        folder_path = self.path_var.get().strip()
        if not folder_path or not os.path.exists(folder_path):
            self.update_file_info("请选择有效的文件夹路径")
            self._manual_operation = False
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
                
                # 检查文件标识并加载缓存
                self._check_and_load_cache()
                
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
                    
                    # 显示被忽略的文件（项目号筛选）
                    if hasattr(self, 'ignored_files') and self.ignored_files:
                        file_info += f"\n⚠️ 已忽略的文件（项目号未勾选）:\n"
                        ignored_by_project = {}
                        for file_path, project_id, file_type in self.ignored_files:
                            if project_id not in ignored_by_project:
                                ignored_by_project[project_id] = []
                            ignored_by_project[project_id].append((os.path.basename(file_path), file_type))
                        
                        for project_id in sorted(ignored_by_project.keys()):
                            file_info += f"  项目 {project_id}:\n"
                            for filename, file_type in ignored_by_project[project_id]:
                                file_info += f"    - {file_type}: {filename}\n"
                        file_info += f"  总计: {len(ignored_by_project)} 个项目, {len(self.ignored_files)} 个文件被忽略\n"
                    
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
            
            # 仅在手动刷新时显示弹窗（包含识别结果）
            if show_popup and self._should_show_popup():
                messagebox.showinfo("文件识别完成", popup_message)
            
            # 重置手动操作标志
            self._manual_operation = False
        
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

    def refresh_all_processed_results(self):
        """
        当用户名或角色改变时，重新筛选并显示所有已处理的数据
        
        功能：
        1. 对所有 processing_results_multiX 中的缓存数据重新应用角色筛选
        2. 更新所有 processing_resultsX 单文件结果
        3. 重新显示当前选项卡的内容
        4. 正确处理"无数据"的情况
        """
        try:
            print("🔄 角色改变，重新筛选所有已处理数据...")
            
            # 处理文件1（内部需打开接口）
            if hasattr(self, 'processing_results_multi1'):
                if self.processing_results_multi1:  # 有缓存数据
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi1.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results1 = True
                    else:
                        self.processing_results = pd.DataFrame()
                        self.has_processed_results1 = True
                else:  # 空字典，但仍需设置标志
                    self.processing_results = pd.DataFrame()
                    self.has_processed_results1 = True
            
            # 处理文件2（内部需回复接口）
            if hasattr(self, 'processing_results_multi2'):
                if self.processing_results_multi2:  # 有缓存数据
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi2.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results2 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results2 = True
                    else:
                        self.processing_results2 = pd.DataFrame()
                        self.has_processed_results2 = True
                else:  # 空字典，但仍需设置标志
                    self.processing_results2 = pd.DataFrame()
                    self.has_processed_results2 = True
            
            # 处理文件3（外部需打开接口）
            if hasattr(self, 'processing_results_multi3'):
                if self.processing_results_multi3:  # 有缓存数据
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi3.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results3 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results3 = True
                    else:
                        self.processing_results3 = pd.DataFrame()
                        self.has_processed_results3 = True
                else:  # 空字典，但仍需设置标志
                    self.processing_results3 = pd.DataFrame()
                    self.has_processed_results3 = True
            
            # 处理文件4（外部需回复接口）
            if hasattr(self, 'processing_results_multi4'):
                if self.processing_results_multi4:  # 有缓存数据
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi4.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results4 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results4 = True
                    else:
                        self.processing_results4 = pd.DataFrame()
                        self.has_processed_results4 = True
                else:  # 空字典，但仍需设置标志
                    self.processing_results4 = pd.DataFrame()
                    self.has_processed_results4 = True
            
            # 处理文件5（三维提资接口）
            if hasattr(self, 'processing_results_multi5'):
                if self.processing_results_multi5:  # 有缓存数据
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi5.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results5 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results5 = True
                    else:
                        self.processing_results5 = pd.DataFrame()
                        self.has_processed_results5 = True
                else:  # 空字典，但仍需设置标志
                    self.processing_results5 = pd.DataFrame()
                    self.has_processed_results5 = True
            
            # 处理文件6（收发文函）
            if hasattr(self, 'processing_results_multi6'):
                if self.processing_results_multi6:  # 有缓存数据
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi6.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results6 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results6 = True
                    else:
                        self.processing_results6 = pd.DataFrame()
                        self.has_processed_results6 = True
                else:  # 空字典，但仍需设置标志
                    self.processing_results6 = pd.DataFrame()
                    self.has_processed_results6 = True
            
            # 刷新当前选项卡的显示
            self.refresh_current_tab_display()
            
            # 更新导出按钮状态
            self.update_export_button_state()
            
            print("✅ 角色筛选刷新完成")
            
        except Exception as e:
            print(f"刷新已处理结果失败: {e}")
            import traceback
            traceback.print_exc()

    def refresh_current_tab_display(self):
        """刷新当前选项卡的显示内容"""
        try:
            # 获取当前选中的选项卡索引
            current_tab = self.notebook.index(self.notebook.select())
            
            # 根据当前选项卡刷新对应的显示内容
            if current_tab == 0:  # 内部需打开接口
                # 【修复】区分"已处理"和"未处理"状态
                if self.has_processed_results1:
                    # 已处理：显示处理结果或"无数据"
                    if self.processing_results is not None and not self.processing_results.empty:
                        excel_row_numbers = list(self.processing_results['原始行号'])
                        self.display_excel_data_with_original_rows(self.tab1_viewer, self.processing_results, "内部需打开接口", excel_row_numbers)
                    else:
                        # 处理后无数据
                        self.show_empty_message(self.tab1_viewer, "无内部需打开接口")
                elif self.target_file1:
                    # 未处理：加载原始文件
                    self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
            elif current_tab == 1:  # 内部需回复接口
                # 【修复】区分"已处理"和"未处理"状态
                if self.has_processed_results2:
                    # 已处理：显示处理结果或"无数据"
                    if self.processing_results2 is not None and not self.processing_results2.empty:
                        excel_row_numbers = list(self.processing_results2['原始行号'])
                        self.display_excel_data_with_original_rows(self.tab2_viewer, self.processing_results2, "内部需回复接口", excel_row_numbers)
                    else:
                        # 处理后无数据
                        self.show_empty_message(self.tab2_viewer, "无内部需回复接口")
                elif self.target_file2:
                    # 未处理：加载原始文件
                    self.load_file_to_viewer(self.target_file2, self.tab2_viewer, "内部需回复接口")
            elif current_tab == 2:  # 外部需打开接口
                # 【修复】区分"已处理"和"未处理"状态
                if self.has_processed_results3:
                    # 已处理：显示处理结果或"无数据"
                    if self.processing_results3 is not None and not self.processing_results3.empty:
                        excel_row_numbers = list(self.processing_results3['原始行号'])
                        self.display_excel_data_with_original_rows(self.tab3_viewer, self.processing_results3, "外部需打开接口", excel_row_numbers)
                    else:
                        # 处理后无数据
                        self.show_empty_message(self.tab3_viewer, "无外部需打开接口")
                elif self.target_file3:
                    # 未处理：加载原始文件
                    self.load_file_to_viewer(self.target_file3, self.tab3_viewer, "外部需打开接口")
            elif current_tab == 3:  # 外部需回复接口
                # 【修复】区分"已处理"和"未处理"状态
                if self.has_processed_results4:
                    # 已处理：显示处理结果或"无数据"
                    if self.processing_results4 is not None and not self.processing_results4.empty:
                        excel_row_numbers = list(self.processing_results4['原始行号'])
                        self.display_excel_data_with_original_rows(self.tab4_viewer, self.processing_results4, "外部需回复接口", excel_row_numbers)
                    else:
                        # 处理后无数据
                        self.show_empty_message(self.tab4_viewer, "无外部需回复接口")
                elif self.target_file4:
                    # 未处理：加载原始文件
                    self.load_file_to_viewer(self.target_file4, self.tab4_viewer, "外部需回复接口")
            elif current_tab == 4 and getattr(self, 'target_files5', None):  # 三维提资接口
                # 【修复】区分"已处理"和"未处理"状态
                if self.has_processed_results5:
                    # 已处理：显示处理结果或"无数据"
                    if self.processing_results5 is not None and not self.processing_results5.empty:
                        excel_row_numbers = list(self.processing_results5['原始行号'])
                        self.display_excel_data_with_original_rows(self.tab5_viewer, self.processing_results5, "三维提资接口", excel_row_numbers)
                    else:
                        # 处理后无数据
                        self.show_empty_message(self.tab5_viewer, "无三维提资接口")
                # 【修复】删除else分支，未处理时不显示任何内容，等待用户点击"开始处理"
            elif current_tab == 5 and getattr(self, 'target_files6', None):  # 收发文函
                # 【修复】区分"已处理"和"未处理"状态
                if self.has_processed_results6:
                    # 已处理：显示处理结果或"无数据"
                    if self.processing_results6 is not None and not self.processing_results6.empty:
                        excel_row_numbers = list(self.processing_results6['原始行号'])
                        self.display_excel_data_with_original_rows(self.tab6_viewer, self.processing_results6, "收发文函", excel_row_numbers)
                    else:
                        # 处理后无数据
                        self.show_empty_message(self.tab6_viewer, "无需要回复的文函")
                elif self.file6_data is not None:
                    # 未处理：显示原始数据
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
        
        # 重置被忽略的文件记录（用于显示）
        self.ignored_files = []  # [(文件路径, 项目号, 文件类型), ...]
        
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
        
        # 获取用户勾选的项目号
        enabled_projects = self.get_enabled_projects()
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
                all_files = main.find_all_target_files1(self.excel_files)
                # 项目号筛选
                self.target_files1, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件1")
                self.ignored_files.extend(ignored)
                if self.target_files1:
                    # 兼容性：设置第一个文件为单文件变量
                    self.target_file1, self.target_file1_project_id = self.target_files1[0]
                    self.update_tab_color(0, "green")
                    # 【修复】不再在识别文件时立即显示原始数据，避免覆盖后续的处理结果
                    # self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
            elif hasattr(main, 'find_target_file'):
                # 兼容旧版本
                self.target_file1, self.target_file1_project_id = main.find_target_file(self.excel_files)
                if self.target_file1:
                    all_files = [(self.target_file1, self.target_file1_project_id)]
                    self.target_files1, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件1")
                    self.ignored_files.extend(ignored)
                    if self.target_files1:
                        self.update_tab_color(0, "green")
                        # 【修复】不再在识别文件时立即显示原始数据，避免覆盖后续的处理结果
                        # self.load_file_to_viewer(self.target_file1, self.tab1_viewer, "内部需打开接口")
                    else:
                        self.target_file1 = None
                        self.target_file1_project_id = None
            
            # 识别所有待处理文件
            if hasattr(main, 'find_all_target_files2'):
                all_files = main.find_all_target_files2(self.excel_files)
                self.target_files2, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件2")
                self.ignored_files.extend(ignored)
                if self.target_files2:
                    self.target_file2, self.target_file2_project_id = self.target_files2[0]
                    self.update_tab_color(1, "green")
            elif hasattr(main, 'find_target_file2'):
                self.target_file2, self.target_file2_project_id = main.find_target_file2(self.excel_files)
                if self.target_file2:
                    all_files = [(self.target_file2, self.target_file2_project_id)]
                    self.target_files2, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件2")
                    self.ignored_files.extend(ignored)
                    if not self.target_files2:
                        self.target_file2 = None
                        self.target_file2_project_id = None
                    else:
                        self.update_tab_color(1, "green")
            
            if hasattr(main, 'find_all_target_files3'):
                all_files = main.find_all_target_files3(self.excel_files)
                self.target_files3, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件3")
                self.ignored_files.extend(ignored)
                if self.target_files3:
                    self.target_file3, self.target_file3_project_id = self.target_files3[0]
                    self.update_tab_color(2, "green")
            elif hasattr(main, 'find_target_file3'):
                self.target_file3, self.target_file3_project_id = main.find_target_file3(self.excel_files)
                if self.target_file3:
                    all_files = [(self.target_file3, self.target_file3_project_id)]
                    self.target_files3, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件3")
                    self.ignored_files.extend(ignored)
                    if not self.target_files3:
                        self.target_file3 = None
                        self.target_file3_project_id = None
                    else:
                        self.update_tab_color(2, "green")
            
            if hasattr(main, 'find_all_target_files4'):
                all_files = main.find_all_target_files4(self.excel_files)
                self.target_files4, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件4")
                self.ignored_files.extend(ignored)
                if self.target_files4:
                    self.target_file4, self.target_file4_project_id = self.target_files4[0]
                    self.update_tab_color(3, "green")
            elif hasattr(main, 'find_target_file4'):
                self.target_file4, self.target_file4_project_id = main.find_target_file4(self.excel_files)
                if self.target_file4:
                    all_files = [(self.target_file4, self.target_file4_project_id)]
                    self.target_files4, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件4")
                    self.ignored_files.extend(ignored)
                    if not self.target_files4:
                        self.target_file4 = None
                        self.target_file4_project_id = None
                    else:
                        self.update_tab_color(3, "green")

            if hasattr(main, 'find_all_target_files5'):
                all_files = main.find_all_target_files5(self.excel_files)
                self.target_files5, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件5")
                self.ignored_files.extend(ignored)
                if self.target_files5:
                    self.update_tab_color(4, "green")

            if hasattr(main, 'find_all_target_files6'):
                all_files = main.find_all_target_files6(self.excel_files)
                self.target_files6, ignored = self._filter_files_by_project(all_files, enabled_projects, "待处理文件6")
                self.ignored_files.extend(ignored)
                if self.target_files6:
                    self.update_tab_color(5, "green")
            
            # ========== 方案3：并发预加载所有文件（速度提升60%+）==========
            print("\n🚀 开始并发预加载Excel文件...")
            files_to_load = []
            
            # 收集需要预加载的文件
            if hasattr(self, 'target_file2') and self.target_file2:
                files_to_load.append((self.target_file2, 'file2'))
            if hasattr(self, 'target_file3') and self.target_file3:
                files_to_load.append((self.target_file3, 'file3'))
            if hasattr(self, 'target_file4') and self.target_file4:
                files_to_load.append((self.target_file4, 'file4'))
            if hasattr(self, 'target_files5') and self.target_files5:
                file5, _pid5 = self.target_files5[0]
                files_to_load.append((file5, 'file5'))
            if hasattr(self, 'target_files6') and self.target_files6:
                file6, _pid6 = self.target_files6[0]
                files_to_load.append((file6, 'file6'))
            
            # 并发读取所有文件（方案3）
            if files_to_load:
                import time
                start_time = time.time()
                
                try:
                    results = concurrent_read_excel_files(files_to_load, max_workers=4)
                    
                    # 存储结果
                    self.file2_data = results.get('file2')
                    self.file3_data = results.get('file3')
                    self.file4_data = results.get('file4')
                    self.file5_data = results.get('file5')
                    self.file6_data = results.get('file6')
                    
                    elapsed = time.time() - start_time
                    print(f"✅ 并发预加载完成！耗时: {elapsed:.2f}秒 (传统方法约需 {elapsed*2.5:.1f}秒)")
                except Exception as e:
                    print(f"⚠️ 并发加载失败，回退到顺序加载: {e}")
                    # 回退到顺序加载
                    for file_path, file_id in files_to_load:
                        try:
                            df = optimized_read_excel(file_path)
                            if file_id == 'file2':
                                self.file2_data = df
                            elif file_id == 'file3':
                                self.file3_data = df
                            elif file_id == 'file4':
                                self.file4_data = df
                            elif file_id == 'file5':
                                self.file5_data = df
                            elif file_id == 'file6':
                                self.file6_data = df
                        except Exception as e2:
                            print(f"加载{file_id}失败: {e2}")
        except Exception as e:
            print(f"识别目标文件时发生错误: {e}")
    
    def _process_with_cache(self, file_path, project_id, file_type, process_func, *args):
        """
        带缓存的处理方法
        
        参数:
            file_path: 源文件路径
            project_id: 项目号
            file_type: 文件类型（file1-file6）
            process_func: 处理函数
            *args: 传递给处理函数的额外参数
            
        返回:
            处理结果DataFrame，如果失败返回None
        """
        try:
            # 1. 尝试加载缓存
            cached_result = self.file_manager.load_cached_result(file_path, project_id, file_type)
            
            if cached_result is not None:
                # 缓存命中
                print(f"  ✅ 使用缓存: 项目{project_id}{file_type} ({len(cached_result)}行)")
                return cached_result
            
            # 2. 缓存未命中，进行处理
            result = process_func(file_path, *args)
            
            # 3. 保存缓存
            if result is not None and not result.empty:
                save_success = self.file_manager.save_cached_result(file_path, project_id, file_type, result)
                if not save_success:
                    # 缓存保存失败，弹窗提醒（仅在手动操作时）
                    if self._should_show_popup():
                        try:
                            from tkinter import messagebox as _mb
                            _mb.showwarning("缓存保存失败", 
                                f"项目{project_id}{file_type}的缓存保存失败。\n"
                                f"数据已正常处理，但下次可能需要重新处理。")
                        except:
                            pass
            
            return result
            
        except Exception as e:
            print(f"处理{file_type}失败 [项目{project_id}]: {e}")
            return None
    
    def _check_and_load_cache(self):
        """
        检查文件标识并加载缓存
        
        在刷新文件列表后调用，检查文件是否变化，如果未变化则加载缓存结果
        """
        try:
            print("\n🔍 检查文件标识和缓存...")
            
            # 1. 收集所有待处理文件的路径
            all_file_paths = []
            if hasattr(self, 'target_files1') and self.target_files1:
                all_file_paths.extend([f[0] for f in self.target_files1])
            if hasattr(self, 'target_files2') and self.target_files2:
                all_file_paths.extend([f[0] for f in self.target_files2])
            if hasattr(self, 'target_files3') and self.target_files3:
                all_file_paths.extend([f[0] for f in self.target_files3])
            if hasattr(self, 'target_files4') and self.target_files4:
                all_file_paths.extend([f[0] for f in self.target_files4])
            if hasattr(self, 'target_files5') and self.target_files5:
                all_file_paths.extend([f[0] for f in self.target_files5])
            if hasattr(self, 'target_files6') and self.target_files6:
                all_file_paths.extend([f[0] for f in self.target_files6])
            
            # 去重
            all_file_paths = list(set(all_file_paths))
            
            if not all_file_paths:
                print("  未发现待处理文件，跳过缓存检查")
                return
            
            # 2. 检查文件是否变化
            files_changed = self.file_manager.check_files_changed(all_file_paths)
            
            if files_changed:
                print("  ⚠️ 检测到文件变化，清空所有缓存和勾选状态")
                self.file_manager.clear_all_completed_rows()
                # 【修复】先清除结果缓存
                for file_path in all_file_paths:
                    self.file_manager.clear_file_cache(file_path)
                # 【修复】然后更新文件标识
                self.file_manager.update_file_identities(all_file_paths)
                # 清空内存中的处理结果
                self.processing_results_multi1 = {}
                self.processing_results_multi2 = {}
                self.processing_results_multi3 = {}
                self.processing_results_multi4 = {}
                self.processing_results_multi5 = {}
                self.processing_results_multi6 = {}
                return
            
            # 3. 文件未变化，尝试加载缓存
            print("  ✅ 文件未变化，尝试加载缓存...")
            cache_loaded_count = 0
            
            # 加载file1缓存
            if hasattr(self, 'target_files1') and self.target_files1:
                for file_path, project_id in self.target_files1:
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file1')
                    if cached_df is not None:
                        # 【修复】对缓存数据应用角色筛选，添加"角色来源"列
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '项目号' not in filtered_df.columns:
                                filtered_df['项目号'] = project_id
                            self.processing_results_multi1[project_id] = filtered_df
                            cache_loaded_count += 1
                if self.processing_results_multi1:
                    self.has_processed_results1 = True
            
            # 加载file2缓存
            if hasattr(self, 'target_files2') and self.target_files2:
                for file_path, project_id in self.target_files2:
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file2')
                    if cached_df is not None:
                        # 【修复】对缓存数据应用角色筛选，添加"角色来源"列
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '项目号' not in filtered_df.columns:
                                filtered_df['项目号'] = project_id
                            self.processing_results_multi2[project_id] = filtered_df
                            cache_loaded_count += 1
                if self.processing_results_multi2:
                    self.has_processed_results2 = True
            
            # 加载file3缓存
            if hasattr(self, 'target_files3') and self.target_files3:
                for file_path, project_id in self.target_files3:
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file3')
                    if cached_df is not None:
                        # 【修复】对缓存数据应用角色筛选，添加"角色来源"列
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '项目号' not in filtered_df.columns:
                                filtered_df['项目号'] = project_id
                            self.processing_results_multi3[project_id] = filtered_df
                            cache_loaded_count += 1
                if self.processing_results_multi3:
                    self.has_processed_results3 = True
            
            # 加载file4缓存
            if hasattr(self, 'target_files4') and self.target_files4:
                for file_path, project_id in self.target_files4:
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file4')
                    if cached_df is not None:
                        # 【修复】对缓存数据应用角色筛选，添加"角色来源"列
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '项目号' not in filtered_df.columns:
                                filtered_df['项目号'] = project_id
                            self.processing_results_multi4[project_id] = filtered_df
                            cache_loaded_count += 1
                if self.processing_results_multi4:
                    self.has_processed_results4 = True
            
            # 加载file5缓存
            if hasattr(self, 'target_files5') and self.target_files5:
                for file_path, project_id in self.target_files5:
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file5')
                    if cached_df is not None:
                        # 【修复】对缓存数据应用角色筛选，添加"角色来源"列
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '项目号' not in filtered_df.columns:
                                filtered_df['项目号'] = project_id
                            self.processing_results_multi5[project_id] = filtered_df
                            cache_loaded_count += 1
                if self.processing_results_multi5:
                    self.has_processed_results5 = True
            
            # 加载file6缓存
            if hasattr(self, 'target_files6') and self.target_files6:
                for file_path, project_id in self.target_files6:
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file6')
                    if cached_df is not None:
                        # 【修复】对缓存数据应用角色筛选，添加"角色来源"列
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '项目号' not in filtered_df.columns:
                                filtered_df['项目号'] = project_id
                            self.processing_results_multi6[project_id] = filtered_df
                            cache_loaded_count += 1
                if self.processing_results_multi6:
                    self.has_processed_results6 = True
            
            # 4. 更新文件标识（如果之前没有）
            self.file_manager.update_file_identities(all_file_paths)
            
            if cache_loaded_count > 0:
                print(f"  ✅ 成功加载 {cache_loaded_count} 个缓存结果")
            else:
                print("  ℹ️ 未找到可用缓存，需要重新处理")
            
        except Exception as e:
            print(f"检查和加载缓存时发生错误: {e}")
            import traceback
            traceback.print_exc()

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
            if (not self.config.get("user_name", "").strip()) and self._should_show_popup():
                message = "请先在设置中填写'姓名'，否则无法开始处理。"
                try:
                    from tkinter import messagebox as _mb
                    _mb.showwarning("提示", message)
                except Exception:
                    pass
                self._manual_operation = False
                return
        except Exception:
            pass
        
        # 检查文件变化并清空勾选状态（如需要）
        try:
            all_file_paths = []
            # 收集所有待处理文件路径
            if hasattr(self, 'target_files1') and self.target_files1:
                all_file_paths.extend([f[0] for f in self.target_files1])
            if hasattr(self, 'target_files2') and self.target_files2:
                all_file_paths.extend([f[0] for f in self.target_files2])
            if hasattr(self, 'target_files3') and self.target_files3:
                all_file_paths.extend([f[0] for f in self.target_files3])
            if hasattr(self, 'target_files4') and self.target_files4:
                all_file_paths.extend([f[0] for f in self.target_files4])
            if hasattr(self, 'target_files5') and self.target_files5:
                all_file_paths.extend([f[0] for f in self.target_files5])
            if hasattr(self, 'target_files6') and self.target_files6:
                all_file_paths.extend([f[0] for f in self.target_files6])
            
            # 检查文件是否变化
            if all_file_paths and self.file_manager.check_files_changed(all_file_paths):
                # 清空所有勾选状态
                self.file_manager.clear_all_completed_rows()
                # 【修复】清除所有缓存文件（关键！）
                for file_path in all_file_paths:
                    self.file_manager.clear_file_cache(file_path)
                print("检测到文件变化，已清空所有缓存和勾选状态")
                # 【修复】更新文件标识
                self.file_manager.update_file_identities(all_file_paths)
            elif all_file_paths:
                # 文件未变化，也需要更新标识（为新文件记录标识）
                self.file_manager.update_file_identities(all_file_paths)
        except Exception as e:
            print(f"文件变化检测失败: {e}")
        
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

                                # 使用缓存处理
                                result = self._process_with_cache(file_path, project_id, 'file1', 
                                                                 main.process_target_file, self.current_datetime)
                                
                                if result is not None and not result.empty:
                                    # 【新增】应用角色筛选（传递项目号）
                                    result = self.apply_role_based_filter(result, project_id=project_id)
                                    if result is not None and not result.empty:
                                        # 添加项目号列
                                        result['项目号'] = project_id
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
                            
                            # 【Registry】调用on_process_done钩子
                            if registry_hooks:
                                try:
                                    for project_id, df in self.processing_results_multi1.items():
                                        if df is not None and not df.empty:
                                            # 找到对应的源文件
                                            source_file = next((fp for fp, pid in self.target_files1 if pid == project_id), "")
                                            registry_hooks.on_process_done(
                                                file_type=1,
                                                project_id=project_id,
                                                source_file=source_file,
                                                result_df=df,
                                                now=self.current_datetime
                                            )
                                except Exception as e:
                                    print(f"[Registry] 文件1钩子调用失败: {e}")
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
                                # 使用缓存处理
                                result = self._process_with_cache(file_path, project_id, 'file2', 
                                                                 main.process_target_file2, self.current_datetime, project_id)
                                if result is not None and not result.empty:
                                    # 【新增】应用角色筛选（传递项目号）
                                    result = self.apply_role_based_filter(result, project_id=project_id)
                                    if result is not None and not result.empty:
                                        # 添加项目号列
                                        result['项目号'] = project_id
                                        self.processing_results_multi2[project_id] = result
                                        combined_results.append(result)
                                        print(f"项目{project_id}文件2处理完成: {len(result)} 行")
                                    else:
                                        print(f"项目{project_id}文件2处理结果为空")
                                else:
                                    print(f"项目{project_id}文件2处理结果为空")
                            except Exception as e:
                                print(f"项目{project_id}文件2处理失败: {e}")
                        
                        # 合并所有结果（兼容性）
                        if combined_results:
                            results2 = pd.concat(combined_results, ignore_index=True)
                            print(f"文件2批量处理完成，总计: {len(results2)} 行")
                            
                            # 【Registry】调用on_process_done钩子
                            if registry_hooks:
                                try:
                                    for project_id, df in self.processing_results_multi2.items():
                                        if df is not None and not df.empty:
                                            source_file = next((fp for fp, pid in self.target_files2 if pid == project_id), "")
                                            registry_hooks.on_process_done(
                                                file_type=2,
                                                project_id=project_id,
                                                source_file=source_file,
                                                result_df=df,
                                                now=self.current_datetime
                                            )
                                except Exception as e:
                                    print(f"[Registry] 文件2钩子调用失败: {e}")
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
                                # 使用缓存处理
                                result = self._process_with_cache(file_path, project_id, 'file3', 
                                                                 main.process_target_file3, self.current_datetime)
                                if result is not None and not result.empty:
                                    # 【新增】应用角色筛选（传递项目号）
                                    result = self.apply_role_based_filter(result, project_id=project_id)
                                    if result is not None and not result.empty:
                                        # 添加项目号列
                                        result['项目号'] = project_id
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
                            
                            # 【Registry】调用on_process_done钩子
                            if registry_hooks:
                                try:
                                    for project_id, df in self.processing_results_multi3.items():
                                        if df is not None and not df.empty:
                                            source_file = next((fp for fp, pid in self.target_files3 if pid == project_id), "")
                                            registry_hooks.on_process_done(
                                                file_type=3,
                                                project_id=project_id,
                                                source_file=source_file,
                                                result_df=df,
                                                now=self.current_datetime
                                            )
                                except Exception as e:
                                    print(f"[Registry] 文件3钩子调用失败: {e}")
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
                                # 使用缓存处理
                                result = self._process_with_cache(file_path, project_id, 'file4', 
                                                                 main.process_target_file4, self.current_datetime)
                                if result is not None and not result.empty:
                                    # 【新增】应用角色筛选（传递项目号）
                                    result = self.apply_role_based_filter(result, project_id=project_id)
                                    if result is not None and not result.empty:
                                        # 添加项目号列
                                        result['项目号'] = project_id
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
                            
                            # 【Registry】调用on_process_done钩子
                            if registry_hooks:
                                try:
                                    for project_id, df in self.processing_results_multi4.items():
                                        if df is not None and not df.empty:
                                            source_file = next((fp for fp, pid in self.target_files4 if pid == project_id), "")
                                            registry_hooks.on_process_done(
                                                file_type=4,
                                                project_id=project_id,
                                                source_file=source_file,
                                                result_df=df,
                                                now=self.current_datetime
                                            )
                                except Exception as e:
                                    print(f"[Registry] 文件4钩子调用失败: {e}")
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
                    # 【新增】执行归档逻辑（标记消失任务，归档超期任务）
                    try:
                        from registry import hooks as registry_hooks
                        batch_tag = self.current_datetime.strftime('%Y%m%d_%H%M%S')
                        registry_hooks.on_scan_finalize(batch_tag=batch_tag)
                    except Exception as e:
                        print(f"[Registry] 归档逻辑执行失败（不影响主流程）: {e}")
                    
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
                                    # 使用缓存处理
                                    result = self._process_with_cache(file_path, project_id, 'file5', 
                                                                     main.process_target_file5, self.current_datetime)
                                    if result is not None and not result.empty:
                                        # 【新增】应用角色筛选（传递项目号）
                                        result = self.apply_role_based_filter(result, project_id=project_id)
                                        if result is not None and not result.empty:
                                            # 添加项目号列
                                            result['项目号'] = project_id
                                            self.processing_results_multi5[project_id] = result
                                            combined_results.append(result)
                                except Exception as e:
                                    print(f"处理文件5失败: {file_path} - {e}")
                            if combined_results:
                                results5 = pd.concat(combined_results, ignore_index=True)
                                
                                # 【Registry】调用on_process_done钩子
                                if registry_hooks:
                                    try:
                                        for project_id, df in self.processing_results_multi5.items():
                                            if df is not None and not df.empty:
                                                source_file = next((fp for fp, pid in self.target_files5 if pid == project_id), "")
                                                registry_hooks.on_process_done(
                                                    file_type=5,
                                                    project_id=project_id,
                                                    source_file=source_file,
                                                    result_df=df,
                                                    now=self.current_datetime
                                                )
                                    except Exception as e:
                                        print(f"[Registry] 文件5钩子调用失败: {e}")
                                
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
                            # 【新增】加载姓名角色表中的有效姓名列表（用于过滤责任人）
                            valid_names_set = self.get_valid_names_from_role_table()
                            
                            self.processing_results_multi6 = {}
                            combined_results = []
                            for file_path, project_id in self.target_files6:
                                try:
                                    print(f"处理文件6: {os.path.basename(file_path)}")
                                    # 判断是否为管理员或所领导，决定是否跳过日期筛选
                                    # 管理员和所领导都不受时间限制
                                    skip_date_filter = ("管理员" in self.user_roles) or ("所领导" in self.user_roles)
                                    # 使用缓存处理，传入valid_names_set
                                    result = self._process_with_cache(file_path, project_id, 'file6', 
                                                                     main.process_target_file6, self.current_datetime, skip_date_filter, valid_names_set)
                                    if result is not None and not result.empty:
                                        # 【新增】应用角色筛选（传递项目号）
                                        result = self.apply_role_based_filter(result, project_id=project_id)
                                        if result is not None and not result.empty:
                                            # 添加项目号列
                                            result['项目号'] = project_id
                                            self.processing_results_multi6[project_id] = result
                                            combined_results.append(result)
                                except Exception as e:
                                    print(f"处理文件6失败: {file_path} - {e}")
                            if combined_results:
                                results6 = pd.concat(combined_results, ignore_index=True)
                                
                                # 【Registry】调用on_process_done钩子
                                if registry_hooks:
                                    try:
                                        for project_id, df in self.processing_results_multi6.items():
                                            if df is not None and not df.empty:
                                                source_file = next((fp for fp, pid in self.target_files6 if pid == project_id), "")
                                                registry_hooks.on_process_done(
                                                    file_type=6,
                                                    project_id=project_id,
                                                    source_file=source_file,
                                                    result_df=df,
                                                    now=self.current_datetime
                                                )
                                    except Exception as e:
                                        print(f"[Registry] 文件6钩子调用失败: {e}")
                                
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
                            else:
                                # 【修复】所有文件处理结果都为空时，也需要调用display_results6
                                # 确保设置has_processed_results6标志，防止显示原始文件数据
                                results6 = pd.DataFrame()
                                print(f"文件6批量处理完成，所有项目都无符合条件的数据")
                                try:
                                    import Monitor
                                    Monitor.log_warning(f"待处理文件6批量处理完成: 所有项目都无符合条件的数据")
                                except:
                                    pass
                                try:
                                    self.display_results6(results6, show_popup=False)
                                except Exception:
                                    pass
                                completion_messages.append("收发文函：无符合条件的数据")

                    # 选择显示的选项卡（优先级：file1 > file2 > file3 > file4 > file5 > file6）
                    self.notebook.select(active_tab)
                    
                    # 关闭等待对话框
                    self.close_waiting_dialog(processing_dialog)
                    
                    # 统一弹窗显示处理结果（批量处理版本）
                    # 只有手动操作时才显示"处理完成"弹窗
                    if completion_messages and self._should_show_popup():
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

                    # 自动模式下，仅当非手动操作时才自动导出（避免手动操作被联动）
                    if getattr(self, 'auto_mode', False) and not self._manual_operation:
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
                    
                    # 【新增】检测是否需要指派任务（仅接口工程师和室主任）
                    if distribution and self._should_show_assignment_reminder():
                        self.root.after(500, self._show_assignment_reminder)
                    
                    # 重置手动操作标志
                    self._manual_operation = False
                
                self.root.after(0, update_display)
                
            except Exception as e:
                self.root.after(0, lambda: self.close_waiting_dialog(processing_dialog))
                if self._should_show_popup() or not getattr(self, '_auto_context', True):
                   self.root.after(0, lambda: messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}"))
                   self.root.after(0, lambda: self.process_button.config(state='normal', text="开始处理"))
                # 重置手动操作标志
                self._manual_operation = False
        
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
            # 不要drop原始行号列，因为需要它来加载勾选状态
            excel_row_numbers = list(results['原始行号'])

            # 只显示数据行，不显示表头
            self.display_excel_data_with_original_rows(self.tab1_viewer, results, "内部需打开接口", excel_row_numbers)
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
        # 不要drop原始行号列，因为需要它来加载勾选状态
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab2_viewer, results, "内部需回复接口", excel_row_numbers)
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
        # 不要drop原始行号列，因为需要它来加载勾选状态
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab3_viewer, results, "外部需打开接口", excel_row_numbers)
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
        # 不要drop原始行号列，因为需要它来加载勾选状态
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab4_viewer, results, "外部需回复接口", excel_row_numbers)
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
        # 不要drop原始行号列，因为需要它来加载勾选状态
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab5_viewer, results, "三维提资接口", excel_row_numbers)
        self.update_export_button_state()
        if show_popup:
            messagebox.showinfo("处理完成", f"三维提资接口数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【三维提资接口】选项卡中更新显示。")

    def display_results6(self, results, show_popup=True):
        """显示收发文函处理结果（与其他类型保持一致）"""
        if not isinstance(results, pd.DataFrame) or results.empty or '原始行号' not in results.columns:
            self.has_processed_results6 = True
            self.show_empty_message(self.tab6_viewer, "无需要回复的文函")
            self.update_export_button_state()
            return
        self.processing_results6 = results
        self.has_processed_results6 = True
        # 不要drop原始行号列，因为需要它来加载勾选状态
        excel_row_numbers = list(results['原始行号'])
        self.display_excel_data_with_original_rows(self.tab6_viewer, results, "收发文函", excel_row_numbers)
        self.update_export_button_state()
        if show_popup and self._should_show_popup():
            messagebox.showinfo("处理完成", f"收发文函数据处理完成！\n共剩余 {len(results)} 行符合条件的数据\n结果已在【收发文函】选项卡中更新显示。")

    def export_results(self):
        current_tab = self.notebook.index(self.notebook.select())
        # 姓名必填校验
        try:
            if (not self.config.get("user_name", "").strip()) and self._should_show_popup():
                message = "请先在设置中填写'姓名'，否则无法导出结果。"
                try:
                    from tkinter import messagebox as _mb
                    _mb.showwarning("提示", message)
                except Exception:
                    pass
                self._manual_operation = False
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
                    # 角色过滤（传递项目号）
                    results = self.apply_role_based_filter(results, project_id=project_id)
                    # 自动模式角色日期窗口限制
                    results = self.apply_auto_role_date_window(results)
                    # 找到对应项目的原始文件路径
                    original_file = None
                    for file_path, pid in self.target_files1:
                        if pid == project_id:
                            original_file = file_path
                            break
                    # 排除已勾选（已完成）的行
                    if original_file:
                        results = self._exclude_completed_rows(results, original_file)
                        # 【Registry】排除待确认的任务行
                        results = self._exclude_pending_confirmation_rows(results, original_file, 1, project_id)
                    # 保存过滤后的结果
                    self.filtered_results_multi1[project_id] = results
                    if original_file and not results.empty:
                        pid_for_export = project_id if project_id else "未知项目"
                        export_tasks.append(('应打开接口', main.export_result_to_excel, results, original_file, self.current_datetime, pid_for_export))
        
        # 导出待处理文件2的所有项目结果
        if self.process_file2_var.get() and self.processing_results_multi2:
            for project_id, results in self.processing_results_multi2.items():
                if isinstance(results, pd.DataFrame) and not results.empty:
                    results = self.apply_role_based_filter(results, project_id=project_id)
                    results = self.apply_auto_role_date_window(results)
                    # 找到对应项目的原始文件路径
                    original_file = None
                    for file_path, pid in self.target_files2:
                        if pid == project_id:
                            original_file = file_path
                            break
                    # 排除已勾选（已完成）的行
                    if original_file:
                        results = self._exclude_completed_rows(results, original_file)
                        # 【Registry】排除待确认的任务行
                        results = self._exclude_pending_confirmation_rows(results, original_file, 2, project_id)
                    # 保存过滤后的结果
                    self.filtered_results_multi2[project_id] = results
                    if original_file and not results.empty:
                        pid_for_export = project_id if project_id else "未知项目"
                        export_tasks.append(('需打开接口', main.export_result_to_excel2, results, original_file, self.current_datetime, pid_for_export))
        
        # 导出待处理文件3的所有项目结果
        if self.process_file3_var.get() and self.processing_results_multi3:
            if hasattr(main, 'export_result_to_excel3'):
                for project_id, results in self.processing_results_multi3.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results, project_id=project_id)
                        results = self.apply_auto_role_date_window(results)
                        # 找到对应项目的原始文件路径
                        original_file = None
                        for file_path, pid in self.target_files3:
                            if pid == project_id:
                                original_file = file_path
                                break
                        # 排除已勾选（已完成）的行
                        if original_file:
                            results = self._exclude_completed_rows(results, original_file)
                            # 【Registry】排除待确认的任务行
                            results = self._exclude_pending_confirmation_rows(results, original_file, 3, project_id)
                        # 保存过滤后的结果
                        self.filtered_results_multi3[project_id] = results
                        if original_file and not results.empty:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('外部接口ICM', main.export_result_to_excel3, results, original_file, self.current_datetime, pid_for_export))
        
        # 导出待处理文件4的所有项目结果
        if self.process_file4_var.get() and self.processing_results_multi4:
            if hasattr(main, 'export_result_to_excel4'):
                for project_id, results in self.processing_results_multi4.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results, project_id=project_id)
                        results = self.apply_auto_role_date_window(results)
                        # 找到对应项目的原始文件路径
                        original_file = None
                        for file_path, pid in self.target_files4:
                            if pid == project_id:
                                original_file = file_path
                                break
                        # 排除已勾选（已完成）的行
                        if original_file:
                            results = self._exclude_completed_rows(results, original_file)
                            # 【Registry】排除待确认的任务行
                            results = self._exclude_pending_confirmation_rows(results, original_file, 4, project_id)
                        # 保存过滤后的结果
                        self.filtered_results_multi4[project_id] = results
                        if original_file and not results.empty:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('外部接口单', main.export_result_to_excel4, results, original_file, self.current_datetime, pid_for_export))
        # 导出待处理文件5的所有项目结果
        if self.process_file5_var.get() and self.processing_results_multi5:
            if hasattr(main, 'export_result_to_excel5'):
                for project_id, results in self.processing_results_multi5.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results, project_id=project_id)
                        results = self.apply_auto_role_date_window(results)
                        # 找到对应项目的原始文件路径
                        original_file = None
                        for file_path, pid in getattr(self, 'target_files5', []):
                            if pid == project_id:
                                original_file = file_path
                                break
                        # 排除已勾选（已完成）的行
                        if original_file:
                            results = self._exclude_completed_rows(results, original_file)
                            # 【Registry】排除待确认的任务行
                            results = self._exclude_pending_confirmation_rows(results, original_file, 5, project_id)
                        # 保存过滤后的结果
                        if not hasattr(self, 'filtered_results_multi5'):
                            self.filtered_results_multi5 = {}
                        self.filtered_results_multi5[project_id] = results
                        if original_file and not results.empty:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('三维提资接口', main.export_result_to_excel5, results, original_file, self.current_datetime, pid_for_export))
        # 导出待处理文件6的所有项目结果
        if self.process_file6_var.get() and self.processing_results_multi6:
            if hasattr(main, 'export_result_to_excel6'):
                for project_id, results in self.processing_results_multi6.items():
                    if isinstance(results, pd.DataFrame) and not results.empty:
                        results = self.apply_role_based_filter(results, project_id=project_id)
                        results = self.apply_auto_role_date_window(results)
                        # 找到对应项目的原始文件路径
                        original_file = None
                        for file_path, pid in getattr(self, 'target_files6', []):
                            if pid == project_id:
                                original_file = file_path
                                break
                        # 排除已勾选（已完成）的行
                        if original_file:
                            results = self._exclude_completed_rows(results, original_file)
                            # 【Registry】排除待确认的任务行
                            results = self._exclude_pending_confirmation_rows(results, original_file, 6, project_id)
                        # 保存过滤后的结果
                        if not hasattr(self, 'filtered_results_multi6'):
                            self.filtered_results_multi6 = {}
                        self.filtered_results_multi6[project_id] = results
                        if original_file and not results.empty:
                            pid_for_export = project_id if project_id else "未知项目"
                            export_tasks.append(('收发文函', main.export_result_to_excel6, results, original_file, self.current_datetime, pid_for_export))
        if not export_tasks:
            if self._should_show_popup():
               messagebox.showinfo("导出提示", "无可导出的数据")
            self._manual_operation = False
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
                    
                    # 【Registry】调用on_export_done钩子
                    if registry_hooks:
                        try:
                            # 从导出任务名称推断file_type
                            file_type_map = {
                                '待处理文件1': 1, '待处理文件2': 2, '待处理文件3': 3,
                                '待处理文件4': 4, '待处理文件5': 5, '待处理文件6': 6,
                                '三维提资接口': 5, '收发文函': 6
                            }
                            file_type = file_type_map.get(name, 0)
                            if file_type > 0:
                                registry_hooks.on_export_done(
                                    file_type=file_type,
                                    project_id=project_id,
                                    export_path=output_path,
                                    count=len(results) if results is not None else 0,
                                    now=self.current_datetime
                                )
                        except Exception as e:
                            print(f"[Registry] 导出钩子调用失败: {e}")
                    
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

                # 手动导出时也使用汇总弹窗显示结果
                if self._should_show_popup():
                    # 等待txt文件生成后显示汇总弹窗
                    def show_summary_after_export():
                        try:
                            txt_path = getattr(self, 'last_summary_written_path', None)
                            if txt_path and os.path.exists(txt_path):
                                self._show_summary_popup(txt_path)
                            else:
                                # 如果txt文件未生成，使用传统弹窗
                                messagebox.showinfo("批量导出完成", combined_message)
                        except Exception:
                            messagebox.showinfo("批量导出完成", combined_message)
                    self.root.after(1500, show_summary_after_export)
            
            # 重置手动操作标志
            self._manual_operation = False
        
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
                    # 检查是否启用简洁导出模式
                    # 1. 管理员且勾选了简洁模式
                    # 2. 所领导角色（默认使用简洁模式）
                    simple_mode = (
                        (("管理员" in self.user_roles) and self.config.get("simple_export_mode", False)) or
                        ("所领导" in self.user_roles)
                    )
                    
                    txt_path = main2.write_export_summary(
                        folder_path=summary_folder,
                        current_datetime=self.current_datetime,
                        results_multi1=results_multi1,
                        results_multi2=results_multi2,
                        results_multi3=results_multi3,
                        results_multi4=results_multi4,
                        results_multi5=results_multi5,
                        results_multi6=results_multi6,
                        simple_export_mode=simple_mode,
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
        """当未填写姓名时，禁用"开始处理/导出结果"按钮并提示。"""
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
        if (show_popup and self._should_show_popup()) and not has_name:
            try:
                messagebox.showwarning("提示", "请先在设置中填写'姓名'，否则无法开始处理或导出结果。")
            except Exception:
                pass

    def add_to_startup(self):
        """添加到开机自启动（增强版）"""
        try:
            # 1. 获取可执行文件路径
            exe_path = os.path.abspath(sys.argv[0])
            
            # 2. 规范化路径（处理空格和特殊字符）
            if exe_path.endswith('.py'):
                # Python脚本模式
                python_exe = sys.executable
                # 确保路径用双引号包裹
                startup_cmd = f'"{python_exe}" "{exe_path}" --auto'
            else:
                # 可执行文件模式
                startup_cmd = f'"{exe_path}" --auto'
            
            # 3. 尝试写入注册表
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 
                    0, 
                    winreg.KEY_WRITE | winreg.KEY_READ  # 确保有读写权限
                )
                winreg.SetValueEx(key, "ExcelProcessor", 0, winreg.REG_SZ, startup_cmd)
                winreg.CloseKey(key)
                
                # 4. 验证写入是否成功
                verify_key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 
                    0, 
                    winreg.KEY_READ
                )
                try:
                    stored_value, _ = winreg.QueryValueEx(verify_key, "ExcelProcessor")
                    winreg.CloseKey(verify_key)
                    
                    if stored_value != startup_cmd:
                        raise ValueError("注册表值验证失败：写入的值与读取的值不一致")
                    
                    # 成功提示
                    if self._should_show_popup():
                        messagebox.showinfo("成功", f"开机自启动设置成功\n\n路径：{exe_path}\n命令：{startup_cmd}")
                    
                except Exception as verify_error:
                    raise ValueError(f"验证失败: {verify_error}")
                    
            except PermissionError:
                raise PermissionError("权限不足，无法写入注册表。请以管理员身份运行程序。")
            except OSError as os_error:
                raise OSError(f"注册表操作失败: {os_error}")
            
        except Exception as e:
            error_msg = f"设置开机自启动失败:\n\n{str(e)}\n\n可能原因:\n1. 权限不足（需要管理员权限）\n2. 注册表被安全软件保护\n3. 系统策略限制\n\n建议：请以管理员身份运行程序重试"
            if self._should_show_popup():
                messagebox.showerror("错误", error_msg)
            self.auto_startup_var.set(False)
            # 记录到日志
            print(f"[开机自启动] 设置失败: {e}")

    def remove_from_startup(self):
        """从开机自启动中移除（增强版）"""
        try:
            # 1. 尝试删除注册表值
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 
                    0, 
                    winreg.KEY_WRITE | winreg.KEY_READ
                )
                winreg.DeleteValue(key, "ExcelProcessor")
                winreg.CloseKey(key)
                
                # 2. 验证删除是否成功
                verify_key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 
                    0, 
                    winreg.KEY_READ
                )
                try:
                    # 如果还能读取到值，说明删除失败
                    _, _ = winreg.QueryValueEx(verify_key, "ExcelProcessor")
                    winreg.CloseKey(verify_key)
                    raise ValueError("删除验证失败：注册表值仍然存在")
                except FileNotFoundError:
                    # 正常情况：值不存在了
                    winreg.CloseKey(verify_key)
                    if self._should_show_popup():
                        messagebox.showinfo("成功", "开机自启动已成功移除")
                    
            except FileNotFoundError:
                # 如果注册表项不存在，视为成功（已经不存在）
                pass
            except PermissionError:
                raise PermissionError("权限不足，无法修改注册表。请以管理员身份运行程序。")
            except OSError as os_error:
                raise OSError(f"注册表操作失败: {os_error}")
                
        except Exception as e:
            error_msg = f"移除开机自启动失败:\n\n{str(e)}\n\n可能原因:\n1. 权限不足（需要管理员权限）\n2. 注册表被安全软件保护\n\n建议：请以管理员身份运行程序重试"
            if self._should_show_popup():
                messagebox.showerror("错误", error_msg)
            # 回滚状态
            self.auto_startup_var.set(True)
            # 记录到日志
            print(f"[开机自启动] 移除失败: {e}")

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
        """显示汇总TXT内容（自动模式唯一弹窗）- 支持选中复制"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            content = f"无法读取汇总文件: {e}"
        
        # 创建弹窗
        dialog = tk.Toplevel(self.root)
        dialog.title("导出结果汇总")
        dialog.geometry("800x600")  # 增大窗口以便更好地显示内容
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 设置图标
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
            if os.path.exists(icon_path):
                dialog.iconbitmap(icon_path)
        except Exception:
            pass
        
        # 主框架
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 提示标签
        tip_label = ttk.Label(
            frame, 
            text="💡 提示：可以选中文本并复制（Ctrl+C），接口号信息在各时间节点下方",
            foreground="gray"
        )
        tip_label.pack(anchor=tk.W, pady=(0, 5))
        
        # 文本显示区域（使用Text而非ScrolledText以便更好地控制）
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建文本框和滚动条
        text = tk.Text(
            text_frame, 
            wrap=tk.WORD,
            font=("Microsoft YaHei UI", 10),  # 使用更清晰的字体
            padx=10,
            pady=10
        )
        scrollbar_y = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        scrollbar_x = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text.xview)
        
        text.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        # 布局
        text.grid(row=0, column=0, sticky='nsew')
        scrollbar_y.grid(row=0, column=1, sticky='ns')
        scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # 插入内容
        text.insert('1.0', content)
        
        # ⭐ 关键：使用 NORMAL 状态但禁用编辑功能，保留选中和复制
        # 通过绑定事件来阻止修改，而不是使用disabled状态
        def block_edit(event=None):
            """阻止编辑但允许选中和复制"""
            # 允许的操作：Ctrl+C（复制）、Ctrl+A（全选）、方向键、鼠标选择
            allowed_keys = ['c', 'a', 'C', 'A']  # Ctrl+C 和 Ctrl+A
            if event and event.state & 0x4:  # Ctrl键被按下
                if event.keysym in allowed_keys:
                    return  # 允许执行
            # 其他情况阻止修改
            return "break"
        
        # 绑定事件阻止编辑
        text.bind('<Key>', block_edit)
        # 允许鼠标选择
        text.bind('<Button-1>', lambda e: None)
        # 添加右键菜单支持复制
        context_menu = tk.Menu(text, tearoff=0)
        context_menu.add_command(
            label="复制 (Ctrl+C)",
            command=lambda: self.root.clipboard_append(text.selection_get()) if text.tag_ranges('sel') else None
        )
        context_menu.add_command(
            label="全选 (Ctrl+A)",
            command=lambda: text.tag_add('sel', '1.0', 'end')
        )
        
        def show_context_menu(event):
            try:
                context_menu.post(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()
        
        text.bind('<Button-3>', show_context_menu)
        
        # 设置文本为可选择但不可编辑的样式
        text.config(
            bg='#f5f5f5',  # 浅灰色背景，提示为只读
            cursor='arrow',  # 箭头光标（但仍可选择文本）
            selectbackground='#0078d7',  # 选中背景色
            selectforeground='white'  # 选中文字颜色
        )
        
        # 按钮框架
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(8, 0), fill=tk.X)
        
        # 添加复制全部按钮
        copy_all_btn = ttk.Button(
            btn_frame, 
            text="📋 复制全部",
            command=lambda: [
                self.root.clipboard_clear(),
                self.root.clipboard_append(content),
                messagebox.showinfo("提示", "已复制全部内容到剪贴板", parent=dialog)
            ]
        )
        copy_all_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 关闭按钮
        close_btn = ttk.Button(btn_frame, text="关闭", command=dialog.destroy)
        close_btn.pack(side=tk.RIGHT)

    # ============================================================================
    # 任务指派相关方法
    # ============================================================================
    
    def _should_show_assignment_reminder(self):
        """判断是否需要显示指派提醒"""
        try:
            # 检查角色
            user_roles = getattr(self, 'user_roles', [])
            
            # 只有接口工程师和室主任需要指派
            has_assignment_role = distribution.is_interface_engineer(user_roles) or \
                                distribution.is_director(user_roles)
            
            if not has_assignment_role:
                return False
            
            # 检查是否有未指派任务
            unassigned = self._check_unassigned_tasks()
            return len(unassigned) > 0
            
        except Exception as e:
            print(f"检查指派提醒失败: {e}")
            return False
    
    def _check_unassigned_tasks(self):
        """检测未指派任务"""
        try:
            if not distribution:
                return []
            
            # 收集所有处理结果
            processed_results = {}
            for i in range(1, 7):
                result_attr = f'processing_results{i}'
                if hasattr(self, result_attr):
                    df = getattr(self, result_attr)
                    if df is not None and not df.empty:
                        processed_results[i] = df
            
            # 检测未指派任务
            user_roles = getattr(self, 'user_roles', [])
            project_id = self._get_my_project_id()
            
            unassigned = distribution.check_unassigned(processed_results, user_roles, project_id)
            return unassigned
            
        except Exception as e:
            print(f"检测未指派任务失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_my_project_id(self):
        """获取接口工程师负责的项目号"""
        try:
            if not distribution:
                return None
            
            user_roles = getattr(self, 'user_roles', [])
            return distribution.parse_interface_engineer_project(user_roles)
            
        except Exception as e:
            print(f"获取项目号失败: {e}")
            return None
    
    def _show_assignment_reminder(self):
        """显示指派提醒弹窗"""
        try:
            if not distribution:
                return
            
            unassigned = self._check_unassigned_tasks()
            count = len(unassigned)
            
            if count == 0:
                return
            
            # 提醒弹窗
            result = messagebox.askyesno(
                "任务指派提醒",
                f"您有 {count} 个需要指派的接口任务\n请注意\n\n是否现在指派？",
                parent=self.root
            )
            
            if result:
                # 现在指派
                name_list = distribution.get_name_list()
                if not name_list:
                    messagebox.showwarning("警告", "无法读取姓名列表，请检查姓名角色表.xlsx", parent=self.root)
                    return
                
                dialog = distribution.AssignmentDialog(
                    self.root,
                    unassigned,
                    name_list
                )
                
                # 等待对话框关闭
                dialog.wait_window()
                
                # 【修复】只有在成功指派后才刷新
                # 检查对话框的结果（需要在AssignmentDialog中添加标记）
                if hasattr(dialog, 'assignment_successful') and dialog.assignment_successful:
                    # 指派完成后清除缓存并重新处理
                    try:
                        print("[指派] 开始刷新显示...")
                        # 清除文件缓存（但不清除Registry数据库）
                        self.file_manager.clear_file_caches_only()
                        # 重新处理数据
                        self.start_processing()
                        print("[指派] 刷新完成")
                    except Exception as e:
                        print(f"[指派] 刷新显示失败: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print("[指派] 用户取消或未完成指派，不刷新")
            else:
                # 用户在提醒弹窗点击"否" - 不打开指派对话框
                print("[指派] 用户选择暂不指派")
                
        except Exception as e:
            print(f"❌ 显示指派提醒失败: {e}")
            import traceback
            traceback.print_exc()
    
    
    def _on_assignment_button_click(self):
        """指派任务按钮点击"""
        try:
            if not distribution:
                return
            
            unassigned = self._check_unassigned_tasks()
            if not unassigned:
                messagebox.showinfo("提示", "当前没有需要指派的任务", parent=self.root)
                return
            
            name_list = distribution.get_name_list()
            if not name_list:
                messagebox.showwarning("警告", "无法读取姓名列表，请检查姓名角色表.xlsx", parent=self.root)
                return
            
            dialog = distribution.AssignmentDialog(
                self.root,
                unassigned,
                name_list
            )
            dialog.wait_window()
            
            # 指派完成后清除缓存并重新处理
            try:
                print("[指派] 开始刷新显示...")
                # 清除文件缓存（但不清除Registry数据库）
                self.file_manager.clear_file_caches_only()
                # 重新处理数据
                self.start_processing()
                print("[指派] 刷新完成")
            except Exception as e:
                print(f"[指派] 刷新显示失败: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"指派任务失败: {e}")
            import traceback
            traceback.print_exc()


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
