"""
历史查询UI模块

提供历史查询对话框和历史显示窗口。
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd

# 文件类型映射
FILE_TYPE_MAP = {
    1: '内部需打开接口',
    2: '内部需回复接口',
    3: '外部需打开接口',
    4: '外部需回复接口',
    5: '三维提资接口',
    6: '收发文函',
}

# 状态映射（与数据库中的status字段对应）
STATUS_DISPLAY_MAP = {
    'open': '待完成',           # Status.OPEN
    'completed': '已完成',      # Status.COMPLETED
    'confirmed': '已确认',      # Status.CONFIRMED
    'archived': '已归档',       # Status.ARCHIVED
    # 以下为旧状态，保留兼容
    'pending': '待完成',
    'assigned': '待指派人审查',
    'in_review': '待审查',
}


def format_time(time_str):
    """格式化时间显示"""
    if not time_str or time_str == '-' or time_str == 'None':
        return '-'
    
    try:
        # 尝试解析ISO格式
        dt = datetime.fromisoformat(str(time_str))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        # 如果失败，返回原始字符串
        return str(time_str) if time_str else '-'


class HistoryQueryDialog(tk.Toplevel):
    """历史查询对话框"""
    
    def __init__(self, parent, db_path: str, wal: bool):
        super().__init__(parent)
        self.db_path = db_path
        self.wal = wal
        
        self.title("历史查询")
        self.geometry("450x280")
        self.resizable(False, False)
        
        self._create_widgets()
        
        # 绑定Enter键到查询按钮
        self.bind('<Return>', lambda e: self._on_query())
        self.bind('<Escape>', lambda e: self._on_cancel())
        
    def _create_widgets(self):
        """创建控件"""
        # 主框架
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="请输入查询条件", font=('微软雅黑', 11, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 15))
        
        # 项目号
        ttk.Label(main_frame, text="项目号：", font=('微软雅黑', 10)).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.project_entry = ttk.Entry(main_frame, width=30, font=('微软雅黑', 10))
        self.project_entry.grid(row=1, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        ttk.Label(main_frame, text="(必填，如：2016)", font=('微软雅黑', 8), foreground='gray').grid(row=2, column=1, sticky=tk.W, padx=(10, 0))
        
        # 接口号
        ttk.Label(main_frame, text="接口号：", font=('微软雅黑', 10)).grid(row=3, column=0, sticky=tk.W, pady=8)
        self.interface_entry = ttk.Entry(main_frame, width=30, font=('微软雅黑', 10))
        self.interface_entry.grid(row=3, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        ttk.Label(main_frame, text="(必填，如：S-SA---1JT-01-25C1-25E6)", font=('微软雅黑', 8), foreground='gray').grid(row=4, column=1, sticky=tk.W, padx=(10, 0))
        
        # 文件类型
        ttk.Label(main_frame, text="文件类型：", font=('微软雅黑', 10)).grid(row=5, column=0, sticky=tk.W, pady=8)
        self.file_type_var = tk.StringVar(value="全部")
        file_type_combo = ttk.Combobox(
            main_frame, 
            textvariable=self.file_type_var, 
            width=27,
            font=('微软雅黑', 10),
            state='readonly'
        )
        file_type_combo['values'] = ['全部', '内部需打开接口', '内部需回复接口', '外部需打开接口', '外部需回复接口', '三维提资接口', '收发文函']
        file_type_combo.grid(row=5, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))
        
        # 查询按钮
        query_btn = ttk.Button(button_frame, text="查询", command=self._on_query, width=12)
        query_btn.pack(side=tk.LEFT, padx=5)
        
        # 取消按钮
        cancel_btn = ttk.Button(button_frame, text="取消", command=self._on_cancel, width=12)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # 焦点到项目号输入框
        self.project_entry.focus()
        
    def _on_query(self):
        """查询按钮点击"""
        # 验证输入
        project_id = self.project_entry.get().strip()
        interface_id = self.interface_entry.get().strip()
        
        if not project_id:
            messagebox.showwarning("输入错误", "请输入项目号", parent=self)
            self.project_entry.focus()
            return
        
        if not interface_id:
            messagebox.showwarning("输入错误", "请输入接口号", parent=self)
            self.interface_entry.focus()
            return
        
        # 获取文件类型
        file_type_str = self.file_type_var.get()
        file_type = None
        if file_type_str != "全部":
            # 反向查找文件类型编号
            for ft, name in FILE_TYPE_MAP.items():
                if name == file_type_str:
                    file_type = ft
                    break
        
        # 查询数据库
        try:
            from .service import query_task_history
            
            history_data = query_task_history(
                self.db_path,
                self.wal,
                project_id,
                interface_id,
                file_type
            )
            
            if not history_data:
                messagebox.showinfo(
                    "查询结果", 
                    f"未找到项目{project_id}的接口{interface_id}的历史记录",
                    parent=self
                )
                return
            
            # 打开显示窗口
            HistoryDisplayWindow(
                self.master,
                history_data,
                project_id,
                interface_id,
                self.db_path,
                self.wal,
                file_type
            )
            
            # 关闭查询对话框
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("查询失败", f"查询历史记录失败：{e}", parent=self)
            import traceback
            traceback.print_exc()
    
    def _on_cancel(self):
        """取消按钮点击"""
        self.destroy()


class HistoryDisplayWindow(tk.Toplevel):
    """历史显示窗口"""
    
    def __init__(self, parent, history_data: List[Dict[str, Any]], 
                 project_id: str, interface_id: str,
                 db_path: str, wal: bool, file_type: Optional[int]):
        super().__init__(parent)
        
        self.history_data = history_data
        self.project_id = project_id
        self.interface_id = interface_id
        self.db_path = db_path
        self.wal = wal
        self.file_type = file_type
        
        self.title(f"历史查询结果 - 项目{project_id} - 接口{interface_id}")
        self.geometry("1400x700")
        
        self._create_widgets()
        self._populate_table()
        
    def _create_widgets(self):
        """创建控件"""
        # 顶部信息框架
        info_frame = ttk.Frame(self)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        info_label = ttk.Label(
            info_frame, 
            text=f"共找到 {len(self.history_data)} 条历史记录",
            font=('微软雅黑', 10)
        )
        info_label.pack(side=tk.LEFT)
        
        # 表格框架
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # 创建Treeview
        columns = (
            '序号', '文件类型', '状态', '首次发现', '完成时间', 
            '确认时间', '归档时间', '指派人', '设计人员', '上级人员',
            '回文单号', '接口时间', '最后出现', '消失时间'
        )
        
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=25)
        
        # 定义列
        column_widths = {
            '序号': 50,
            '文件类型': 110,
            '状态': 100,
            '首次发现': 135,  # 修复：列名改为"首次发现"
            '完成时间': 135,
            '确认时间': 135,
            '归档时间': 135,
            '指派人': 130,
            '设计人员': 90,
            '上级人员': 90,
            '回文单号': 150,  # 【新增】回文单号列
            '接口时间': 110,
            '最后出现': 135,
            '消失时间': 135,
        }
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=column_widths.get(col, 100), anchor=tk.CENTER)
        
        # 滚动条
        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # 按钮框架
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 导出Excel按钮
        export_btn = ttk.Button(button_frame, text="导出Excel", command=self._export_excel, width=15)
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # 刷新按钮
        refresh_btn = ttk.Button(button_frame, text="刷新", command=self._refresh, width=15)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # 关闭按钮
        close_btn = ttk.Button(button_frame, text="关闭", command=self._close, width=15)
        close_btn.pack(side=tk.RIGHT, padx=5)
        
    def _populate_table(self):
        """填充表格数据"""
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 插入数据
        for idx, task in enumerate(self.history_data, 1):
            # 文件类型
            file_type_name = FILE_TYPE_MAP.get(task.get('file_type', 0), '未知')
            
            # 状态
            display_status = task.get('display_status', '')
            if not display_status:
                status = task.get('status', 'pending')
                display_status = STATUS_DISPLAY_MAP.get(status, status)
            
            # 指派人信息（按用户要求处理）
            assigned_by = task.get('assigned_by', '')
            if assigned_by:
                assignor_display = assigned_by
            else:
                # 检查是否有responsible_person（源文件中的责任人）
                responsible_person = task.get('responsible_person', '')
                if responsible_person:
                    assignor_display = "系统已分派，无须指派"
                else:
                    assignor_display = "-"
            
            # 设计人员
            assignee_name = task.get('assignee_name') or task.get('responsible_person') or '-'
            
            # 【修复】上级人员：使用confirmed_by字段
            superior_name = task.get('confirmed_by') or '-'
            
            # 【新增】回文单号
            response_number = task.get('response_number') or '-'
            
            values = (
                idx,
                file_type_name,
                display_status,
                format_time(task.get('first_seen_at')),  # 修复：使用first_seen_at
                format_time(task.get('completed_at')),
                format_time(task.get('confirmed_at')),
                format_time(task.get('archived_at')) if task.get('archive_reason') else '-',  # 只有归档原因存在时才显示归档时间
                assignor_display,
                assignee_name,
                superior_name,
                response_number,  # 【新增】回文单号
                task.get('interface_time') or '-',
                format_time(task.get('last_seen_at')),
                format_time(task.get('missing_since')),
            )
            
            self.tree.insert('', tk.END, values=values)
    
    def _export_excel(self):
        """导出到Excel"""
        try:
            # 准备数据
            export_data = []
            for idx, task in enumerate(self.history_data, 1):
                # 文件类型
                file_type_name = FILE_TYPE_MAP.get(task.get('file_type', 0), '未知')
                
                # 状态
                display_status = task.get('display_status', '')
                if not display_status:
                    status = task.get('status', 'pending')
                    display_status = STATUS_DISPLAY_MAP.get(status, status)
                
                # 指派人信息
                assigned_by = task.get('assigned_by', '')
                if assigned_by:
                    assignor_display = assigned_by
                else:
                    responsible_person = task.get('responsible_person', '')
                    if responsible_person:
                        assignor_display = "系统已分派，无须指派"
                    else:
                        assignor_display = "-"
                
                # 设计人员
                assignee_name = task.get('assignee_name') or task.get('responsible_person') or '-'
                
                # 【修复】上级人员：使用confirmed_by字段
                superior_name = task.get('confirmed_by') or '-'
                
                # 【新增】回文单号
                response_number = task.get('response_number') or '-'
                
                export_data.append({
                    '序号': idx,
                    '文件类型': file_type_name,
                    '项目号': task.get('project_id', ''),
                    '接口号': task.get('interface_id', ''),
                    '状态': display_status,
                    '首次发现': format_time(task.get('first_seen_at')),  # 修复：使用first_seen_at
                    '完成时间': format_time(task.get('completed_at')),
                    '确认时间': format_time(task.get('confirmed_at')),
                    '归档时间': format_time(task.get('archived_at')) if task.get('archive_reason') else '-',
                    '归档原因': task.get('archive_reason') or '-',
                    '指派人': assignor_display,
                    '设计人员': assignee_name,
                    '上级人员': superior_name,
                    '回文单号': response_number,  # 【新增】回文单号
                    '接口时间': task.get('interface_time') or '-',
                    '最后出现': format_time(task.get('last_seen_at')),
                    '消失时间': format_time(task.get('missing_since')),
                })
            
            # 转换为DataFrame
            df = pd.DataFrame(export_data)
            
            # 选择保存路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_filename = f"历史查询_{self.project_id}_{self.interface_id}_{timestamp}.xlsx"
            
            filepath = filedialog.asksaveasfilename(
                parent=self,
                title="保存历史记录",
                defaultextension=".xlsx",
                initialfile=default_filename,
                filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
            )
            
            if not filepath:
                return
            
            # 保存Excel
            df.to_excel(filepath, index=False, engine='openpyxl')
            
            messagebox.showinfo("导出成功", f"历史记录已导出到：\n{filepath}", parent=self)
            
        except Exception as e:
            messagebox.showerror("导出失败", f"导出Excel失败：{e}", parent=self)
            import traceback
            traceback.print_exc()
    
    def _refresh(self):
        """刷新数据"""
        try:
            from .service import query_task_history
            
            self.history_data = query_task_history(
                self.db_path,
                self.wal,
                self.project_id,
                self.interface_id,
                self.file_type
            )
            
            self._populate_table()
            
            # 更新标题中的记录数
            for widget in self.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Label) and "共找到" in child['text']:
                            child.config(text=f"共找到 {len(self.history_data)} 条历史记录")
                            break
                    break
            
            messagebox.showinfo("刷新完成", "历史记录已刷新", parent=self)
            
        except Exception as e:
            messagebox.showerror("刷新失败", f"刷新历史记录失败：{e}", parent=self)
            import traceback
            traceback.print_exc()
    
    def _close(self):
        """关闭窗口"""
        self.destroy()

