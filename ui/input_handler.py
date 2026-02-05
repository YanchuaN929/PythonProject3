#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回文单号输入处理模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
from openpyxl import load_workbook
from datetime import date
import os

from write_tasks import get_write_task_manager, get_pending_cache

# 导入Registry模块
try:
    from registry import hooks as registry_hooks
except ImportError:
    print("警告: 未找到registry模块")
    registry_hooks = None


def get_excel_lock_owner(file_path: str) -> str:
    """
    获取Excel文件的占用者用户名
    
    Excel打开文件时会创建 ~$文件名 的临时锁定文件，
    其中包含打开文件的用户名信息。
    
    参数:
        file_path: Excel文件的完整路径
        
    返回:
        占用者用户名，如果无法获取则返回空字符串
    """
    try:
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # Excel临时文件格式: ~$文件名
        # 对于长文件名，Excel会截取前面部分
        lock_file_name = "~$" + file_name
        lock_file_path = os.path.join(dir_path, lock_file_name)
        
        # 如果标准锁定文件不存在，尝试查找以 ~$ 开头的文件
        if not os.path.exists(lock_file_path):
            # 搜索目录中所有以 ~$ 开头的文件
            for f in os.listdir(dir_path):
                if f.startswith("~$"):
                    # 检查是否与目标文件相关（去掉 ~$ 后是否匹配）
                    potential_name = f[2:]  # 去掉 ~$
                    if file_name.startswith(potential_name) or potential_name in file_name:
                        lock_file_path = os.path.join(dir_path, f)
                        break
        
        if not os.path.exists(lock_file_path):
            return ""
        
        # 读取锁定文件内容获取用户名
        # Excel锁定文件是二进制格式，用户名通常在文件开头以Unicode编码存储
        with open(lock_file_path, 'rb') as f:
            content = f.read()
        
        # 尝试解码用户名
        # 方法1: 直接解码 UTF-16-LE（Windows常用编码）
        try:
            # 跳过前面可能的字节，用户名通常在前128字节内
            # 查找连续的可打印Unicode字符
            decoded = content[:128].decode('utf-16-le', errors='ignore')
            # 过滤出有效字符（字母、数字、中文等）
            user_name = ""
            for char in decoded:
                if char.isprintable() and char not in '\x00\x01\x02\x03\x04\x05\x06\x07\x08':
                    user_name += char
                elif user_name:  # 遇到非法字符且已有用户名，停止
                    break
            
            if user_name and len(user_name) >= 2:
                return user_name.strip()
        except Exception:
            pass
        
        # 方法2: 尝试 GBK 解码（中文Windows系统）
        try:
            decoded = content[:64].decode('gbk', errors='ignore')
            user_name = ""
            for char in decoded:
                if char.isprintable() and ord(char) > 31:
                    user_name += char
                elif user_name:
                    break
            
            if user_name and len(user_name) >= 2:
                return user_name.strip()
        except Exception:
            pass
        
        return ""
        
    except Exception as e:
        print(f"[文件锁定] 获取占用者信息失败: {e}")
        return ""


class InterfaceInputDialog(tk.Toplevel):
    """回文单号输入弹窗"""
    
    def __init__(self, parent, interface_id, file_type, file_path, row_index, 
                 user_name, project_id, source_column=None, file_manager=None, 
                 viewer=None, item_id=None, columns=None, on_success=None, has_assignor=False,
                 user_roles=None):
        """
        参数:
            parent: 父窗口
            interface_id: 接口号
            file_type: 文件类型(1-6)
            file_path: 原始Excel文件路径
            row_index: Excel行号
            user_name: 当前用户姓名
            project_id: 项目号
            source_column: 文件3专用，'M'或'L'，表示筛选来源
            file_manager: 文件管理器实例（用于自动勾选）
            viewer: Treeview控件（用于立即刷新显示）
            item_id: Treeview中的行ID（用于立即刷新显示）
            columns: 列名列表（用于查找"是否已完成"列索引）
        """
        super().__init__(parent)
        
        self.interface_id = interface_id
        self.file_type = file_type
        self.file_path = file_path
        self.row_index = row_index
        self.user_name = user_name
        self.user_roles = user_roles or []
        self.project_id = project_id
        self.source_column = source_column
        self.file_manager = file_manager
        self.viewer = viewer  # 保存Treeview引用
        self.item_id = item_id  # 保存行ID
        self.columns = columns  # 保存列名
        self.on_success = on_success
        self.has_assignor = has_assignor
        
        # 【新增】存储已填写的回文单号信息
        self.existing_response = None  # 存储已填写的回文单号
        self.completed_info = None     # 存储完成信息

        # 优先从主程序配置中获取 data_folder，并同步到 registry hooks
        data_folder = self._resolve_data_folder_from_app()
        if data_folder:
            try:
                from registry import hooks as registry_hooks
                registry_hooks.set_data_folder(data_folder)
            except Exception:
                pass
        else:
            # 兜底：从当前文件路径推导（寻找 .registry）
            try:
                from registry import hooks as registry_hooks
                registry_hooks._ensure_data_folder_from_path(self.file_path)
            except Exception:
                pass
        
        # 查询Registry中是否已填写回文单号
        self._load_existing_response()
        
        self.setup_ui()

    def _resolve_data_folder_from_app(self) -> str:
        """从主程序配置中解析数据文件夹路径。"""
        # 优先从顶层窗口获取 app 引用
        try:
            top = self.winfo_toplevel()
            app = getattr(top, "app", None)
            if app and isinstance(getattr(app, "config", None), dict):
                folder = str(app.config.get("folder_path", "") or "").strip()
                if folder:
                    return folder
        except Exception:
            pass

        # 兜底：沿 master 链查找 app 引用
        try:
            node = self
            for _ in range(10):
                app = getattr(node, "app", None)
                if app and isinstance(getattr(app, "config", None), dict):
                    folder = str(app.config.get("folder_path", "") or "").strip()
                    if folder:
                        return folder
                node = getattr(node, "master", None)
                if node is None:
                    break
        except Exception:
            pass
        return ""
    
    def _load_existing_response(self):
        """从Registry查询已填写的回文单号"""
        try:
            from registry.hooks import _cfg
            from registry.db import get_connection, close_connection_after_use
            from registry.util import make_task_id
            
            cfg = _cfg()
            if not cfg.get('registry_enabled'):
                return
            
            db_path = cfg.get('registry_db_path')
            if not db_path or not os.path.exists(db_path):
                return
            
            # 【修复】去除接口号的角色后缀，与extract_interface_id保持一致
            # 例如 "S-YA---1ZJ-02-25C3-25C3(建筑总图室主任)" -> "S-YA---1ZJ-02-25C3-25C3"
            import re
            clean_interface_id = re.sub(r'\([^)]*\)$', '', self.interface_id).strip() if self.interface_id else self.interface_id
            
            task_id = make_task_id(
                self.file_type,
                self.project_id,
                clean_interface_id,  # 使用清理后的接口号
                os.path.basename(self.file_path),
                self.row_index
            )
            
            conn = get_connection(db_path, bool(cfg.get('registry_wal', False)))
            try:
                cursor = conn.execute("""
                    SELECT response_number, completed_at, completed_by
                    FROM tasks
                    WHERE id = ? AND status IN ('completed', 'confirmed')
                """, (task_id,))
                
                row = cursor.fetchone()
                if row and row[0]:  # 确保response_number不为空
                    self.existing_response = row[0]
                    self.completed_info = {
                        'completed_at': row[1],
                        'completed_by': row[2]
                    }
            finally:
                close_connection_after_use()
        except Exception as e:
            print(f"[Registry] 查询已填写回文单号失败: {e}")
    
    def setup_ui(self):
        """设置界面"""
        # 居中显示
        self.transient(self.master)
        self.grab_set()
        
        if self.existing_response:
            # 【已填写回文单号】显示只读信息
            self.title("回文单号（已填写）")
            self.geometry("450x280")
            self.resizable(False, False)
            
            # 标题
            title_label = ttk.Label(self, text=f"接口号: {self.interface_id}",
                                    font=('Arial', 12, 'bold'))
            title_label.pack(pady=10)
            
            # 显示已填写的回文单号（只读）
            info_frame = ttk.LabelFrame(self, text="已填写信息", padding=15)
            info_frame.pack(pady=10, padx=20, fill='both', expand=True)
            
            ttk.Label(info_frame, text="回文单号:").grid(row=0, column=0, sticky='w', padx=5, pady=8)
            response_label = ttk.Label(info_frame, text=self.existing_response,
                                       font=('Arial', 11, 'bold'), foreground='blue')
            response_label.grid(row=0, column=1, sticky='w', padx=5, pady=8)
            
            if self.completed_info:
                if self.completed_info.get('completed_by'):
                    ttk.Label(info_frame, text="填写人:").grid(row=1, column=0, sticky='w', padx=5, pady=8)
                    ttk.Label(info_frame, text=self.completed_info['completed_by']).grid(row=1, column=1, sticky='w', padx=5, pady=8)
                
                if self.completed_info.get('completed_at'):
                    ttk.Label(info_frame, text="填写时间:").grid(row=2, column=0, sticky='w', padx=5, pady=8)
                    completed_time = str(self.completed_info['completed_at'])[:19]  # 截断到秒
                    ttk.Label(info_frame, text=completed_time).grid(row=2, column=1, sticky='w', padx=5, pady=8)
            
            # 关闭按钮（优化样式）
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=15)
            close_btn = ttk.Button(button_frame, text="关闭", command=self.destroy, width=12)
            close_btn.pack()
            
        else:
            # 【未填写回文单号】显示输入界面（原有逻辑）
            self.title("回文单号输入")
            self.geometry("400x200")
            self.resizable(False, False)
            
            # 标题
            title_label = ttk.Label(self, text=f"接口号: {self.interface_id}", 
                                    font=('Arial', 12, 'bold'))
            title_label.pack(pady=10)
            
            # 输入框
            input_frame = ttk.Frame(self)
            input_frame.pack(pady=10, padx=20, fill='x')
            
            ttk.Label(input_frame, text="回文单号:").pack(side='left', padx=5)
            
            self.entry = ttk.Entry(input_frame, width=30)
            self.entry.pack(side='left', padx=5, fill='x', expand=True)
            self.entry.focus_set()
            
            # 按钮
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=20)
            
            ttk.Button(button_frame, text="确认", command=self.on_confirm).pack(side='left', padx=10)
            ttk.Button(button_frame, text="取消", command=self.destroy).pack(side='left', padx=10)
            
            # 绑定Enter键
            self.entry.bind('<Return>', lambda e: self.on_confirm())
    
    def on_confirm(self):
        """确认按钮回调"""
        response_number = self.entry.get().strip()
        
        if not response_number:
            messagebox.showwarning("警告", "请输入回文单号", parent=self)
            return
        
        try:
            manager = get_write_task_manager()
            role = ""
            try:
                if isinstance(self.user_roles, (list, tuple)) and self.user_roles:
                    role = " ".join(str(x) for x in self.user_roles if x)
                elif self.user_roles:
                    role = str(self.user_roles)
            except Exception:
                role = ""
            data_folder = self._resolve_data_folder_from_app() or None
            if not data_folder:
                try:
                    from registry import hooks as registry_hooks
                    data_folder = registry_hooks.get_data_folder()
                except Exception:
                    data_folder = None
            task = manager.submit_response_task(
                file_path=self.file_path,
                file_type=self.file_type,
                row_index=self.row_index,
                interface_id=self.interface_id,
                response_number=response_number,
                user_name=self.user_name,
                project_id=self.project_id,
                source_column=self.source_column,
                role=role,
                data_folder=data_folder,
                description=f"{self.user_name} 填写回文单号 {self.interface_id}",
            )
            try:
                cache = get_pending_cache()
                cache.add_response_entry(
                    task.task_id,
                    {
                        "file_path": self.file_path,
                        "file_type": self.file_type,
                        "row_index": self.row_index,
                        "response_number": response_number,
                        "user_name": self.user_name,
                        "project_id": self.project_id,
                        "has_assignor": self.has_assignor,
                    },
                )
            except Exception as cache_error:
                print(f"[PendingCache] 记录回文单号任务失败: {cache_error}")
            messagebox.showinfo("已提交", "回文单号写入任务已提交，后台将自动执行。", parent=self)
            if callable(self.on_success):
                try:
                    self.on_success(self.file_path, self.row_index, self.file_type)
                except Exception as cb_error:
                    print(f"[PendingCache] 回调失败: {cb_error}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"提交写入任务失败: {str(e)}", parent=self)


def write_response_to_excel(file_path, file_type, row_index, response_number, 
                             user_name, project_id, source_column=None):
    """
    写入回文单号到Excel文件
    
    参数:
        file_path: Excel文件路径
        file_type: 文件类型(1-6)
        row_index: Excel行号（从2开始，因为第1行是标题）
        response_number: 回文单号
        user_name: 用户姓名
        project_id: 项目号
        source_column: 文件3专用，'M'或'L'
    
    返回:
        bool: 成功返回True，失败返回False
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            return False
        
        # 文件锁定检测
        try:
            # 尝试以独占模式打开
            with open(file_path, 'r+b'):
                pass
        except PermissionError:
            # 尝试获取占用者信息
            lock_owner = get_excel_lock_owner(file_path)
            if lock_owner:
                messagebox.showerror("文件占用", f"文件正被 【{lock_owner}】 占用，请稍后再试")
            else:
                messagebox.showerror("文件占用", "有其他用户占用该文件，请稍后再试")
            return False
        
        # 使用openpyxl打开
        wb = load_workbook(file_path)
        ws = wb.active
        
        # 获取写入列位置
        columns = get_write_columns(file_type, row_index, ws, source_column)
        
        if not columns:
            print(f"无法确定写入列位置: file_type={file_type}")
            return False
        
        # 写入数据
        response_col = columns['response_col']
        time_col = columns['time_col']
        name_col = columns['name_col']
        
        ws[f"{response_col}{row_index}"] = response_number
        ws[f"{time_col}{row_index}"] = date.today().strftime('%Y-%m-%d')
        ws[f"{name_col}{row_index}"] = user_name
        
         # 【新增】文件6特殊逻辑：自动更新M列（回复状态列）
        if file_type == 6:
            try:
                # I列（索引8）是预期时间列
                expected_time_cell = ws.cell(row_index, 9)  # I列是第9列（A=1）
                expected_time = expected_time_cell.value
                
                # 比较当前日期和预期时间
                from datetime import datetime
                today = date.today()
                
                # 解析预期时间
                if expected_time:
                    try:
                        # 尝试解析为日期对象
                        if isinstance(expected_time, datetime):
                            expected_date = expected_time.date()
                        elif isinstance(expected_time, date):
                            expected_date = expected_time
                        else:
                            # 尝试字符串解析
                            import pandas as pd
                            parsed = pd.to_datetime(expected_time, errors='coerce')
                            if pd.notna(parsed):
                                expected_date = parsed.date()
                            else:
                                expected_date = None
                        
                        # 根据对比结果写入M列（第13列）
                        if expected_date:
                            if today <= expected_date:
                                reply_status = "按时回复"
                            else:
                                reply_status = "延期回复"
                            
                            ws.cell(row_index, 13, reply_status)  # M列是第13列
                            print(f"[文件6] 自动更新M列: {reply_status} (预期:{expected_date}, 实际:{today})")
                        else:
                            print("[文件6] 无法解析预期时间，跳过M列更新")
                    except Exception as parse_error:
                        print(f"[文件6] 解析预期时间失败: {parse_error}")
                else:
                    print("[文件6] I列预期时间为空，跳过M列更新")
            except Exception as e:
                print(f"[文件6] 更新M列失败: {e}")
                # 即使M列更新失败，也不影响回文单号写入
        
        # 保存
        try:
            wb.save(file_path)
            wb.close()
            
            # 【关键】验证写入是否成功：重新打开文件检查
            print("[验证] 开始验证Excel写入...")
            verify_wb = load_workbook(file_path, read_only=True)
            verify_ws = verify_wb.active
            
            # 验证回文单号列
            verify_response = verify_ws[f"{response_col}{row_index}"].value
            if str(verify_response).strip() != str(response_number).strip():
                verify_wb.close()
                raise Exception(f"验证失败：回文单号列写入不匹配。期望:{response_number}, 实际:{verify_response}")
            
            verify_wb.close()
            print("[验证] ✓ Excel写入验证成功")
            print(f"成功写入: {file_path}, 行{row_index}, 回文单号={response_number}")
            return True
            
        except Exception as save_error:
            print(f"[ERROR] Excel保存或验证失败: {save_error}")
            raise  # 重新抛出异常，让上层处理
        
    except Exception as e:
        print("[ERROR] 写入回文单号失败!")
        print(f"  文件路径: {file_path}")
        print(f"  文件类型: {file_type}")
        print(f"  行号: {row_index}")
        print(f"  回文单号: {response_number}")
        print(f"  错误信息: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("写入失败", f"无法写入回文单号到Excel文件\n\n错误：{str(e)}")
        return False


def get_write_columns(file_type, row_index, worksheet, source_column=None):
    """
    获取各文件类型的写入列位置
    
    参数:
        file_type: 文件类型(1-6)
        row_index: Excel行号
        worksheet: openpyxl工作表对象
        source_column: 文件3专用，'M'或'L'
    
    返回:
        dict: {'response_col': 'S', 'time_col': 'N', 'name_col': 'V'}
        或 None（如果无法确定）
    """
    # 文件类型1-2, 4-6的固定列位置
    column_map = {
        1: {'response_col': 'S', 'time_col': 'M', 'name_col': 'V'},  
        2: {'response_col': 'P', 'time_col': 'N', 'name_col': 'AL'},
        4: {'response_col': 'U', 'time_col': 'V', 'name_col': 'AT'},
        5: {'response_col': 'V', 'time_col': 'N', 'name_col': 'W'},
        6: {'response_col': 'L', 'time_col': 'J', 'name_col': 'N'},
    }
    
    if file_type in column_map:
        return column_map[file_type]
    
    # 文件3特殊逻辑：根据source_column判断
    if file_type == 3:
        if source_column == 'M':
            # M列筛选：V/T/BM
            return {'response_col': 'V', 'time_col': 'T', 'name_col': 'BM'}
        elif source_column == 'L':
            # L列筛选：S/Q/BM
            return {'response_col': 'S', 'time_col': 'Q', 'name_col': 'BM'}
        else:
            # 如果未指定，尝试自动判断
            return determine_file3_source_and_columns(row_index, worksheet)
    
    return None


def determine_file3_source_and_columns(row_index, worksheet):
    """
    判断文件3某行是因M列还是L列被筛选出
    
    参数:
        row_index: Excel行号
        worksheet: openpyxl工作表对象
    
    返回:
        dict: 写入列位置
    """
    try:
        # 读取M列和L列的值
        m_val = worksheet[f"M{row_index}"].value
        l_val = worksheet[f"L{row_index}"].value
        
        # 读取T列和Q列的值（回复时间列）
        t_val = worksheet[f"T{row_index}"].value
        q_val = worksheet[f"Q{row_index}"].value
        
        # 简化判断逻辑：
        # 如果M列有时间数据且T列为空，判断为M列来源
        # 如果L列有时间数据且Q列为空，判断为L列来源
        # 优先M列
        
        m_has_time = m_val is not None and str(m_val).strip() != ''
        t_is_empty = t_val is None or str(t_val).strip() == ''
        
        l_has_time = l_val is not None and str(l_val).strip() != ''
        q_is_empty = q_val is None or str(q_val).strip() == ''
        
        if m_has_time and t_is_empty:
            # M列来源
            return {'response_col': 'V', 'time_col': 'T', 'name_col': 'BM'}
        elif l_has_time and q_is_empty:
            # L列来源
            return {'response_col': 'S', 'time_col': 'Q', 'name_col': 'BM'}
        else:
            # 默认M列
            return {'response_col': 'V', 'time_col': 'T', 'name_col': 'BM'}
    
    except Exception as e:
        print(f"判断文件3来源失败: {e}")
        # 默认返回M列
        return {'response_col': 'V', 'time_col': 'T', 'name_col': 'BM'}


# 测试代码
if __name__ == "__main__":
    # 测试get_write_columns
    columns_1 = get_write_columns(1, 5, None)
    print(f"文件1写入列: {columns_1}")
    
    columns_3_m = get_write_columns(3, 5, None, 'M')
    print(f"文件3(M列)写入列: {columns_3_m}")
    
    columns_3_l = get_write_columns(3, 5, None, 'L')
    print(f"文件3(L列)写入列: {columns_3_l}")

