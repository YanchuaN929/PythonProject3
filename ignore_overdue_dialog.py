#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量忽略延期任务对话框
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Any
from datetime import datetime


class IgnoreOverdueDialog(tk.Toplevel):
    """批量忽略延期任务对话框"""
    
    def __init__(self, parent, overdue_tasks: List[Dict[str, Any]], user_name: str):
        """
        初始化对话框
        
        参数:
            parent: 父窗口
            overdue_tasks: 延期任务列表，每个任务包含:
                {
                    'file_type': int,
                    'project_id': str,
                    'interface_id': str,
                    'source_file': str,
                    'row_index': int,
                    'interface_time': str,
                    'status': str,  # 状态文本（如"（已延期）待完成"）
                }
            user_name: 当前用户姓名
        """
        super().__init__(parent)
        
        self.overdue_tasks = overdue_tasks
        self.user_name = user_name
        self.selected_indices = set()  # 选中的任务索引
        self.ignore_reason_var = tk.StringVar()  # 忽略原因
        self.ignore_successful = False  # 标记是否成功忽略
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面"""
        self.title("批量忽略延期任务")
        self.geometry("1300x750")  # 增加宽度以适应新增列
        
        # 居中显示
        self.transient(self.master)
        self.grab_set()
        
        # 标题
        title_label = ttk.Label(
            self,
            text=f"批量忽略延期任务（共{len(self.overdue_tasks)}个已延期任务）",
            font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=10)
        
        # 说明文字
        info_label = ttk.Label(
            self,
            text="说明：被忽略的任务将不再在主显示、状态提醒和导出结果中出现\n"
                 "当任务的预期时间发生变化时，忽略标记会自动取消",
            font=('Arial', 10),
            foreground='gray'
        )
        info_label.pack(pady=5)
        
        # 创建任务列表区域
        self._create_task_list_frame()
        
        # 创建操作栏
        self._create_action_frame()
        
        # 创建按钮栏
        self._create_button_frame()
    
    def _create_task_list_frame(self):
        """创建任务列表区域"""
        list_frame = ttk.Frame(self)
        list_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 创建Treeview（增加更多列）
        columns = ('选择', '项目号', '接口号', '预期时间', '文件类型', '责任人', '所属科室', '显示状态')
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show='headings',
            selectmode='extended'
        )
        
        # 设置列标题（添加排序绑定）
        self.tree.heading('选择', text='☐ 全选', command=self._toggle_select_all)
        self.tree.heading('项目号', text='项目号', command=lambda: self._sort_by_column('项目号'))
        self.tree.heading('接口号', text='接口号', command=lambda: self._sort_by_column('接口号'))
        self.tree.heading('预期时间', text='预期时间', command=lambda: self._sort_by_column('预期时间'))
        self.tree.heading('文件类型', text='文件类型', command=lambda: self._sort_by_column('文件类型'))
        self.tree.heading('责任人', text='责任人', command=lambda: self._sort_by_column('责任人'))
        self.tree.heading('所属科室', text='所属科室', command=lambda: self._sort_by_column('所属科室'))
        self.tree.heading('显示状态', text='显示状态', command=lambda: self._sort_by_column('显示状态'))
        
        # 设置列宽
        self.tree.column('选择', width=60, anchor='center')
        self.tree.column('项目号', width=80, anchor='center')
        self.tree.column('接口号', width=250, anchor='w')
        self.tree.column('预期时间', width=100, anchor='center')
        self.tree.column('文件类型', width=120, anchor='center')
        self.tree.column('责任人', width=100, anchor='center')
        self.tree.column('所属科室', width=100, anchor='center')
        self.tree.column('显示状态', width=100, anchor='center')
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # 文件类型映射
        file_type_names = {
            1: '内部需打开',
            2: '内部需回复',
            3: '外部需打开',
            4: '外部需回复',
            5: '三维提资',
            6: '收发文函'
        }
        
        # 【关键】创建item到任务索引的映射字典（用于排序后定位原始任务）
        self.item_to_task_index = {}
        
        # 填充数据
        for idx, task in enumerate(self.overdue_tasks):
            # 生成唯一的item_id
            item_id = f"task_{idx}"
            
            # 获取显示状态（优先使用display_status，否则用status）
            display_status = task.get('display_status', '')
            if not display_status:
                # 如果没有display_status，根据status转换
                status = task.get('status', '')
                if status == 'open':
                    display_status = '待完成'
                elif status == 'completed':
                    display_status = '待审查'
                elif status == 'confirmed':
                    display_status = '已审查'
                else:
                    display_status = status
            
            self.tree.insert('', 'end', iid=item_id, values=(
                '☐',  # 默认未选中
                task['project_id'],
                task['interface_id'],
                task['interface_time'],
                file_type_names.get(task.get('file_type', 0), '未知'),
                task.get('responsible_person', ''),
                task.get('department', ''),
                display_status
            ))
            
            # 存储item_id到任务索引的映射
            self.item_to_task_index[item_id] = idx
        
        # 初始化排序状态
        self._sort_states = {}
        
        # 绑定点击事件（切换选中状态）
        self.tree.bind('<Button-1>', self._on_tree_click)
    
    def _on_tree_click(self, event):
        """点击任务行，切换选中状态"""
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        
        # 【关键修复】通过item_id获取任务索引，不受排序影响
        idx = self.item_to_task_index.get(item_id)
        if idx is None:
            return
        
        # 切换选中状态
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
            self.tree.set(item_id, '选择', '☐')
        else:
            self.selected_indices.add(idx)
            self.tree.set(item_id, '选择', '☑')
    
    def _toggle_select_all(self):
        """切换全选/全不选"""
        if len(self.selected_indices) == len(self.overdue_tasks):
            # 全部取消选中
            self.selected_indices.clear()
            for item_id in self.tree.get_children():
                self.tree.set(item_id, '选择', '☐')
            self.tree.heading('选择', text='☐ 全选', command=self._toggle_select_all)
        else:
            # 全部选中
            self.selected_indices = set(range(len(self.overdue_tasks)))
            for item_id in self.tree.get_children():
                self.tree.set(item_id, '选择', '☑')
            self.tree.heading('选择', text='☑ 全选', command=self._toggle_select_all)
    
    def _sort_by_column(self, column_name):
        """
        按指定列排序
        
        【关键】排序时保持勾选状态标记，因为使用item_id作为唯一标识
        """
        try:
            # 切换排序方向
            current_state = self._sort_states.get(column_name, False)
            reverse = not current_state
            self._sort_states[column_name] = reverse
            
            # 获取所有数据
            data = []
            for item_id in self.tree.get_children():
                values = list(self.tree.item(item_id)['values'])
                
                # 找到要排序的列的索引
                columns = self.tree['columns']
                try:
                    col_idx = list(columns).index(column_name)
                    sort_value = values[col_idx] if col_idx < len(values) else ""
                except ValueError:
                    sort_value = ""
                
                # 根据列类型生成排序键
                sort_key = self._generate_sort_key(column_name, sort_value, reverse)
                
                data.append((sort_key, item_id, values))
            
            # 按指定列排序
            data.sort(reverse=reverse, key=lambda x: x[0])
            
            # 重新排列Treeview中的项（保持item_id不变，只改变顺序）
            for index, (_, item_id, values) in enumerate(data):
                self.tree.move(item_id, '', index)
                
                # 【关键】根据selected_indices更新显示的勾选状态
                task_idx = self.item_to_task_index.get(item_id)
                if task_idx in self.selected_indices:
                    self.tree.set(item_id, '选择', '☑')
                else:
                    self.tree.set(item_id, '选择', '☐')
            
            # 更新所有列标题（清除其他列的排序符号，只显示当前列的）
            for col in columns:
                if col == '选择':
                    # 全选列保持原有的command
                    continue
                elif col == column_name:
                    direction_symbol = ' ↓' if reverse else ' ↑'
                    self.tree.heading(col, text=f"{col}{direction_symbol}",
                                    command=lambda c=col: self._sort_by_column(c))
                else:
                    self.tree.heading(col, text=col,
                                    command=lambda c=col: self._sort_by_column(c))
            
            print(f"忽略窗口 - 按{column_name}列排序（{'降序' if reverse else '升序'}）")
            
        except Exception as e:
            print(f"排序失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_sort_key(self, column_name, sort_value, reverse):
        """
        根据列名和值生成排序键
        """
        try:
            # 预期时间列
            if column_name == '预期时间':
                if not sort_value or sort_value == '-':
                    return '99.99' if not reverse else '00.00'
                return str(sort_value)
            
            # 项目号列（数字）
            if column_name == '项目号':
                try:
                    return int(str(sort_value)) if sort_value and str(sort_value).strip() else 0
                except:
                    return 0
            
            # 显示状态列（按优先级：待完成 > 待审查 > 已审查）
            if column_name == '显示状态':
                status_priority = {
                    '待完成': 1,
                    '待审查': 2,
                    '已审查': 3,
                    '': 999
                }
                return status_priority.get(str(sort_value), 500)
            
            # 文件类型列（按顺序）
            if column_name == '文件类型':
                type_priority = {
                    '内部需打开': 1,
                    '内部需回复': 2,
                    '外部需打开': 3,
                    '外部需回复': 4,
                    '三维提资': 5,
                    '收发文函': 6,
                    '': 999
                }
                return type_priority.get(str(sort_value), 500)
            
            # 其他列：字符串排序
            return str(sort_value)
            
        except Exception as e:
            print(f"生成排序键失败: {e}")
            return str(sort_value)
    
    def _create_action_frame(self):
        """创建操作栏（忽略原因输入）"""
        action_frame = ttk.LabelFrame(self, text="忽略原因（可选）", padding=10)
        action_frame.pack(fill='x', padx=10, pady=10)
        
        # 预设原因按钮
        preset_frame = ttk.Frame(action_frame)
        preset_frame.pack(fill='x', pady=5)
        
        ttk.Label(preset_frame, text="快速选择：").pack(side='left', padx=5)
        
        preset_reasons = [
            "长期拖延",
            "优先级低",
            "暂不处理",
            "等待外部条件",
            "不再需要"
        ]
        
        for reason in preset_reasons:
            btn = ttk.Button(
                preset_frame,
                text=reason,
                command=lambda r=reason: self.ignore_reason_var.set(r),
                width=12
            )
            btn.pack(side='left', padx=3)
        
        # 自定义输入框
        input_frame = ttk.Frame(action_frame)
        input_frame.pack(fill='x', pady=5)
        
        ttk.Label(input_frame, text="或自定义：").pack(side='left', padx=5)
        
        reason_entry = ttk.Entry(
            input_frame,
            textvariable=self.ignore_reason_var,
            font=('Arial', 10),
            width=50
        )
        reason_entry.pack(side='left', padx=5, fill='x', expand=True)
    
    def _create_button_frame(self):
        """创建按钮栏"""
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=10, pady=10)
        
        # 确认按钮
        confirm_btn = ttk.Button(
            button_frame,
            text="确认忽略选中任务",
            command=self._on_confirm,
            style='Action.TButton'
        )
        confirm_btn.pack(side='left', padx=5)
        
        # 取消按钮
        cancel_btn = ttk.Button(
            button_frame,
            text="取消",
            command=self.destroy
        )
        cancel_btn.pack(side='left', padx=5)
        
        # 统计信息
        self.info_label = ttk.Label(
            button_frame,
            text="已选中 0 个任务",
            font=('Arial', 10),
            foreground='blue'
        )
        self.info_label.pack(side='right', padx=10)
        
        # 定时更新统计
        self._update_selection_info()
    
    def _update_selection_info(self):
        """更新选中任务统计"""
        count = len(self.selected_indices)
        self.info_label.config(text=f"已选中 {count} 个任务")
        self.after(500, self._update_selection_info)
    
    def _on_confirm(self):
        """确认按钮回调"""
        if not self.selected_indices:
            messagebox.showwarning("提示", "请至少选择一个任务进行忽略", parent=self)
            return
        
        # 二次确认
        count = len(self.selected_indices)
        reason = self.ignore_reason_var.get().strip()
        
        msg = f"确认要忽略选中的 {count} 个延期任务吗？\n\n"
        msg += "被忽略的任务将不再显示，直到其预期时间发生变化。"
        if reason:
            msg += f"\n\n忽略原因：{reason}"
        
        if not messagebox.askyesno("确认忽略", msg, parent=self):
            return
        
        # 显示处理中提示
        processing_label = ttk.Label(
            self,
            text="正在批量忽略，请稍候...",
            font=('Arial', 12)
        )
        processing_label.pack(pady=10)
        self.update()
        
        # 执行批量忽略
        try:
            # 准备任务列表
            selected_tasks = [
                self.overdue_tasks[idx] for idx in self.selected_indices
            ]
            
            # 调用Registry服务
            from registry import service as registry_service
            from registry.config import get_config
            
            cfg = get_config()
            db_path = cfg['db_path']
            wal = cfg.get('wal', True)
            
            task_keys = []
            for task in selected_tasks:
                task_keys.append({
                    'file_type': task['file_type'],
                    'project_id': task['project_id'],
                    'interface_id': task['interface_id'],
                    'source_file': task['source_file'],
                    'row_index': task['row_index'],
                    'interface_time': task['interface_time']
                })
            
            result = registry_service.mark_ignored_batch(
                db_path=db_path,
                wal=wal,
                task_keys=task_keys,
                ignored_by=self.user_name,
                ignored_reason=reason
            )
            
            # 隐藏处理中提示
            processing_label.destroy()
            
            # 显示结果
            success_count = result['success_count']
            failed_tasks = result['failed_tasks']
            
            if success_count > 0:
                msg = f"成功忽略 {success_count} 个延期任务"
                if failed_tasks:
                    msg += f"\n\n失败 {len(failed_tasks)} 个任务：\n"
                    msg += "\n".join([
                        f"- {t['interface_id']}: {t['reason']}" 
                        for t in failed_tasks[:5]
                    ])
                    if len(failed_tasks) > 5:
                        msg += f"\n... 等共{len(failed_tasks)}个失败"
                
                messagebox.showinfo("忽略结果", msg, parent=self)
                
                if not failed_tasks:
                    self.ignore_successful = True
                    self.destroy()
            else:
                messagebox.showerror("失败", "所有任务忽略失败，请查看控制台日志", parent=self)
                
        except Exception as e:
            processing_label.destroy()
            messagebox.showerror("错误", f"忽略过程中发生错误：\n{str(e)}", parent=self)
            import traceback
            traceback.print_exc()

