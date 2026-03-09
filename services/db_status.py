#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库状态显示器模块

提供一个可嵌入主界面的数据库连接状态显示组件。
支持显示连接状态、同步进度等信息。
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
from datetime import datetime
import threading
import time


class DatabaseStatus:
    """数据库状态枚举"""
    NOT_CONFIGURED = "not_configured"  # 未配置
    DEFERRED = "deferred"              # 已配置但延迟连接（待刷新）
    CONNECTED = "connected"            # 已连接
    SYNCING = "syncing"                # 同步中
    WAITING = "waiting"                # 等待锁定
    ERROR = "error"                    # 连接失败
    MAINTENANCE = "maintenance"        # 维护模式


class DatabaseStatusIndicator:
    """
    数据库状态显示器
    
    在主界面左下角显示数据库连接状态，包括：
    - 连接状态（已连接/未配置/同步中/等待锁定/连接失败）
    - 同步进度（可选）
    - 鼠标悬停显示详细信息
    """
    
    # 状态配置：(图标, 文字, 颜色)
    STATUS_CONFIG = {
        DatabaseStatus.NOT_CONFIGURED: ("⚠️", "未配置", "#888888"),
        DatabaseStatus.DEFERRED: ("🕘", "待刷新", "#4169E1"),
        DatabaseStatus.CONNECTED: ("✅", "已连接", "#228B22"),
        DatabaseStatus.SYNCING: ("🔄", "同步中...", "#4169E1"),
        DatabaseStatus.WAITING: ("⏳", "等待锁定...", "#FF8C00"),
        DatabaseStatus.ERROR: ("❌", "连接失败", "#DC143C"),
        DatabaseStatus.MAINTENANCE: ("🛠️", "当前处于维护模式", "#B22222"),
    }
    
    def __init__(self, parent_frame: ttk.Frame, row: int = 4, column: int = 0):
        """
        初始化状态显示器
        
        参数:
            parent_frame: 父容器（通常是main_frame）
            row: 网格行号
            column: 网格列号
        """
        self.parent = parent_frame
        self._current_status = DatabaseStatus.NOT_CONFIGURED
        self._detail_info = {}
        self._last_sync_time: Optional[datetime] = None
        self._error_message: Optional[str] = None
        self._last_dialog_message: Optional[str] = None
        self._last_dialog_ts: float = 0.0
        self._dialog_cooldown_seconds: float = 20.0
        self._lock = threading.Lock()
        
        # 创建UI组件
        self._create_widgets(row, column)
        
        # 初始状态
        self.set_not_configured()
    
    def _create_widgets(self, row: int, column: int):
        """创建UI组件"""
        # 状态框架
        self.frame = ttk.Frame(self.parent)
        self.frame.grid(row=row, column=column, sticky=tk.W, padx=(4, 0), pady=(6, 2))
        
        # 数据库图标
        self.icon_label = tk.Label(
            self.frame, 
            text="🗄️", 
            font=("Segoe UI Emoji", 10)
        )
        self.icon_label.pack(side=tk.LEFT)
        
        # 状态文本标签
        self.status_label = tk.Label(
            self.frame,
            text="数据库: ⚠️ 未配置",
            fg="#888888",
            font=("Microsoft YaHei UI", 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=(2, 0))
        
        # 进度标签（可选，用于显示同步进度）
        self.progress_label = tk.Label(
            self.frame,
            text="",
            fg="#4169E1",
            font=("Microsoft YaHei UI", 9)
        )
        self.progress_label.pack(side=tk.LEFT, padx=(4, 0))
        
        # 绑定鼠标悬停事件
        self._bind_tooltip()
    
    def _bind_tooltip(self):
        """绑定鼠标悬停提示"""
        self.tooltip = None
        
        def show_tooltip(event):
            if self.tooltip:
                return
            
            # 创建提示窗口
            x, y, _, _ = self.frame.bbox("insert") if hasattr(self.frame, 'bbox') else (0, 0, 0, 0)
            x += self.frame.winfo_rootx() + 25
            y += self.frame.winfo_rooty() + 25
            
            self.tooltip = tk.Toplevel(self.frame)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            
            # 提示内容
            tip_text = self._get_tooltip_text()
            label = tk.Label(
                self.tooltip,
                text=tip_text,
                justify=tk.LEFT,
                background="#FFFFD0",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Microsoft YaHei UI", 9),
                padx=6,
                pady=4
            )
            label.pack()
        
        def hide_tooltip(event):
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None
        
        self.frame.bind("<Enter>", show_tooltip)
        self.frame.bind("<Leave>", hide_tooltip)
        self.status_label.bind("<Enter>", show_tooltip)
        self.status_label.bind("<Leave>", hide_tooltip)
    
    def _get_tooltip_text(self) -> str:
        """获取提示文本"""
        lines = []
        
        # 状态
        icon, text, _ = self.STATUS_CONFIG.get(
            self._current_status, 
            self.STATUS_CONFIG[DatabaseStatus.NOT_CONFIGURED]
        )
        lines.append(f"状态: {icon} {text}")
        
        # 数据库路径
        db_path = self._detail_info.get('db_path', '未配置')
        if db_path and len(db_path) > 50:
            db_path = "..." + db_path[-47:]
        lines.append(f"路径: {db_path}")
        
        # 最后同步时间
        if self._last_sync_time:
            lines.append(f"最后同步: {self._last_sync_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 任务数量
        task_count = self._detail_info.get('task_count')
        if task_count is not None:
            lines.append(f"任务总数: {task_count}")
        
        # 错误信息
        if self._error_message:
            lines.append(f"错误: {self._error_message}")

        # 维护标志路径
        maintenance_flag = self._detail_info.get("maintenance_flag")
        if maintenance_flag:
            if len(maintenance_flag) > 50:
                maintenance_flag = "..." + maintenance_flag[-47:]
            lines.append(f"维护标志: {maintenance_flag}")
        
        return "\n".join(lines)
    
    def _update_display(self):
        """更新显示（线程安全）"""
        def do_update():
            with self._lock:
                icon, text, color = self.STATUS_CONFIG.get(
                    self._current_status,
                    self.STATUS_CONFIG[DatabaseStatus.NOT_CONFIGURED]
                )
                self.status_label.config(
                    text=f"数据库: {icon} {text}",
                    fg=color
                )
        
        # 确保在主线程中更新UI
        try:
            self.frame.after(0, do_update)
        except Exception:
            pass
    
    def set_not_configured(self):
        """设置为未配置状态"""
        self._current_status = DatabaseStatus.NOT_CONFIGURED
        self._error_message = None
        self.progress_label.config(text="")
        self._update_display()
    
    def set_connected(self, db_path: Optional[str] = None, task_count: Optional[int] = None):
        """
        设置为已连接状态
        
        参数:
            db_path: 数据库路径
            task_count: 任务总数
        """
        self._current_status = DatabaseStatus.CONNECTED
        self._error_message = None
        self._last_sync_time = datetime.now()
        self.progress_label.config(text="")
        
        if db_path:
            self._detail_info['db_path'] = db_path
        if task_count is not None:
            self._detail_info['task_count'] = task_count
        
        self._update_display()

    def set_deferred(self, db_path: Optional[str] = None):
        """
        设置为“待刷新/延迟连接”状态（用于启动阶段不触网）

        参数:
            db_path: 计划使用的数据库路径（可选，仅用于提示展示）
        """
        self._current_status = DatabaseStatus.DEFERRED
        self._error_message = None
        self.progress_label.config(text="")
        if db_path:
            self._detail_info['db_path'] = db_path
        self._update_display()
    
    def set_syncing(self, current: Optional[int] = None, total: Optional[int] = None):
        """
        设置为同步中状态
        
        参数:
            current: 当前进度
            total: 总数
        """
        self._current_status = DatabaseStatus.SYNCING
        self._error_message = None
        
        # 显示进度
        if current is not None and total is not None:
            self.progress_label.config(text=f"({current}/{total})")
        else:
            self.progress_label.config(text="")
        
        self._update_display()
    
    def set_waiting(self):
        """设置为等待锁定状态"""
        self._current_status = DatabaseStatus.WAITING
        self._error_message = None
        self.progress_label.config(text="")
        self._update_display()
    
    def set_error(self, message: str = "连接失败", show_dialog: bool = True):
        """
        设置为错误状态
        
        参数:
            message: 错误信息
            show_dialog: 是否弹窗提醒
        """
        self._current_status = DatabaseStatus.ERROR
        self._error_message = message
        self.progress_label.config(text="")
        self._update_display()
        
        # 弹窗提醒
        if show_dialog:
            self._show_error_dialog(message)

    def set_maintenance(self, flag_path: Optional[str] = None, db_path: Optional[str] = None):
        """设置为维护模式状态（不弹窗）"""
        self._current_status = DatabaseStatus.MAINTENANCE
        self._error_message = None
        self.progress_label.config(text="")
        if db_path:
            self._detail_info['db_path'] = db_path
        if flag_path:
            self._detail_info['maintenance_flag'] = flag_path
        self._update_display()
    
    def _show_error_dialog(self, message: str):
        """显示错误弹窗"""
        now_ts = time.time()
        with self._lock:
            if (
                self._last_dialog_message == message
                and (now_ts - self._last_dialog_ts) < self._dialog_cooldown_seconds
            ):
                return
            self._last_dialog_message = message
            self._last_dialog_ts = now_ts

        def show():
            messagebox.showerror(
                "数据库连接失败",
                f"数据库操作失败：{message}\n\n"
                "可能的原因：\n"
                "• 数据库文件被其他程序占用\n"
                "• 网络连接不稳定\n"
                "• 磁盘空间不足\n\n"
                "建议操作：\n"
                "1. 稍后重试当前操作\n"
                "2. 检查网络连接\n"
                "3. 联系管理员"
            )
        
        # 确保在主线程中显示弹窗
        try:
            self.frame.after(0, show)
        except Exception:
            pass
    
    def update_db_path(self, db_path: str):
        """更新数据库路径信息"""
        self._detail_info['db_path'] = db_path
    
    def update_task_count(self, count: int):
        """更新任务数量"""
        self._detail_info['task_count'] = count
    
    @property
    def current_status(self) -> str:
        """获取当前状态"""
        return self._current_status
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._current_status == DatabaseStatus.CONNECTED
    
    @property
    def is_error(self) -> bool:
        """是否错误状态"""
        return self._current_status == DatabaseStatus.ERROR


# 全局实例（可选，方便其他模块访问）
_global_indicator: Optional[DatabaseStatusIndicator] = None


def get_db_status_indicator() -> Optional[DatabaseStatusIndicator]:
    """获取全局状态显示器实例"""
    return _global_indicator


def set_db_status_indicator(indicator: DatabaseStatusIndicator):
    """设置全局状态显示器实例"""
    global _global_indicator
    _global_indicator = indicator


# 便捷函数（供其他模块调用）
def notify_syncing(current: Optional[int] = None, total: Optional[int] = None):
    """通知：开始同步"""
    if _global_indicator:
        _global_indicator.set_syncing(current, total)


def notify_connected(db_path: Optional[str] = None, task_count: Optional[int] = None):
    """通知：已连接"""
    if _global_indicator:
        _global_indicator.set_connected(db_path, task_count)


def notify_waiting():
    """通知：等待锁定"""
    if _global_indicator:
        _global_indicator.set_waiting()


def notify_error(message: str = "连接失败", show_dialog: bool = True):
    """通知：连接失败"""
    if _global_indicator:
        _global_indicator.set_error(message, show_dialog)

def notify_maintenance(flag_path: Optional[str] = None, db_path: Optional[str] = None):
    """通知：维护模式"""
    if _global_indicator:
        _global_indicator.set_maintenance(flag_path=flag_path, db_path=db_path)


def notify_not_configured():
    """通知：未配置"""
    if _global_indicator:
        _global_indicator.set_not_configured()

