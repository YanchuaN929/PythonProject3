#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel数据处理监控器
用于显示main.py中的处理过程提示和调试信息
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import queue
import datetime
import os

class ProcessMonitor:
    """处理过程监控器"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.window = None
        self.message_queue = queue.Queue()
        self.is_running = False
        
        # 存储所有消息
        self.messages = []
        
    def create_window(self):
        """创建监控窗口"""
        if self.window and self.window.winfo_exists():
            # 如果窗口已存在，直接显示并聚焦
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
            return
        
        # 创建新窗口
        if self.parent:
            self.window = tk.Toplevel(self.parent)
        else:
            self.window = tk.Tk()
            
        self.window.title("Excel数据处理监控器")
        self.window.geometry("800x600")
        
        # 设置窗口图标（如果存在）
        try:
            icon_path = "ico_bin/tubiao.ico"
            if os.path.exists(icon_path):
                self.window.iconbitmap(icon_path)
        except Exception as e:
            print(f"设置监控窗口图标失败: {e}")
        
        # 创建界面
        self.create_widgets()
        
        # 绑定关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_window_close)
        
        # 开始监控
        self.start_monitoring()
        
    def create_widgets(self):
        """创建监控界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # 标题
        title_label = ttk.Label(main_frame, text="Excel数据处理监控器", font=('Microsoft YaHei UI', 12, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # 消息显示区域
        text_frame = ttk.LabelFrame(main_frame, text="处理过程监控", padding="5")
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # 文本显示控件
        self.text_display = scrolledtext.ScrolledText(
            text_frame, 
            width=80, 
            height=30,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.text_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=(10, 0))
        
        # 清空按钮
        self.clear_button = ttk.Button(
            button_frame, 
            text="清空日志", 
            command=self.clear_messages
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 保存按钮
        self.save_button = ttk.Button(
            button_frame, 
            text="保存日志", 
            command=self.save_messages
        )
        self.save_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 状态标签
        self.status_label = ttk.Label(button_frame, text="监控已启动", foreground="green")
        self.status_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # 显示初始消息
        self.add_message("监控器已启动", "SYSTEM")
        
    def start_monitoring(self):
        """开始监控"""
        self.is_running = True
        self.status_label.config(text="监控已启动", foreground="green")
        
        # 启动消息处理线程
        threading.Thread(target=self.process_messages, daemon=True).start()
        
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        self.status_label.config(text="监控已停止", foreground="red")
        
    def process_messages(self):
        """处理消息队列"""
        while self.is_running:
            try:
                # 从队列中获取消息（阻塞等待，超时1秒）
                message, msg_type = self.message_queue.get(timeout=1.0)
                
                # 在主线程中更新界面
                if self.window and self.window.winfo_exists():
                    self.window.after(0, lambda m=message, t=msg_type: self.display_message(m, t))
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理监控消息时发生错误: {e}")
                
    def add_message(self, message, msg_type="INFO"):
        """添加消息到队列"""
        try:
            self.message_queue.put((message, msg_type), block=False)
        except queue.Full:
            # 如果队列满了，丢弃最旧的消息
            try:
                self.message_queue.get_nowait()
                self.message_queue.put((message, msg_type), block=False)
            except queue.Empty:
                pass
                
    def display_message(self, message, msg_type="INFO"):
        """在界面上显示消息"""
        if not self.window or not self.window.winfo_exists():
            return
            
        # 生成时间戳
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 根据消息类型设置颜色和前缀
        color_map = {
            "INFO": "black",
            "SUCCESS": "green",
            "WARNING": "orange", 
            "ERROR": "red",
            "PROCESS": "blue",
            "SYSTEM": "purple"
        }
        
        prefix_map = {
            "INFO": "[信息]",
            "SUCCESS": "[成功]",
            "WARNING": "[警告]",
            "ERROR": "[错误]",
            "PROCESS": "[处理]",
            "SYSTEM": "[系统]"
        }
        
        color = color_map.get(msg_type, "black")
        prefix = prefix_map.get(msg_type, "[信息]")
        
        # 格式化消息
        formatted_message = f"[{timestamp}] {prefix} {message}\n"
        
        # 存储消息
        self.messages.append(formatted_message)
        
        # 显示消息
        self.text_display.config(state='normal')
        self.text_display.insert(tk.END, formatted_message)
        
        # 设置颜色标签
        try:
            # 为新插入的文本设置颜色
            line_start = self.text_display.index(tk.END + "-2 lines linestart")
            line_end = self.text_display.index(tk.END + "-2 lines lineend")
            
            tag_name = f"{msg_type}_{len(self.messages)}"
            self.text_display.tag_add(tag_name, line_start, line_end)
            self.text_display.tag_config(tag_name, foreground=color)
        except:
            pass
        
        self.text_display.config(state='disabled')
        
        # 自动滚动到底部
        self.text_display.see(tk.END)
        
        # 限制消息数量（保留最近1000条）
        if len(self.messages) > 1000:
            self.messages = self.messages[-1000:]
            self.refresh_display()
            
    def refresh_display(self):
        """刷新显示所有消息"""
        if not self.window or not self.window.winfo_exists():
            return
            
        self.text_display.config(state='normal')
        self.text_display.delete('1.0', tk.END)
        
        for message in self.messages[-500:]:  # 只显示最近500条
            self.text_display.insert(tk.END, message)
            
        self.text_display.config(state='disabled')
        self.text_display.see(tk.END)
        
    def clear_messages(self):
        """清空所有消息"""
        self.messages.clear()
        if self.window and self.window.winfo_exists():
            self.text_display.config(state='normal')
            self.text_display.delete('1.0', tk.END)
            self.text_display.config(state='disabled')
            
        self.add_message("日志已清空", "SYSTEM")
        
    def save_messages(self):
        """保存消息到文件"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                title="保存监控日志",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("Excel数据处理监控日志\n")
                    f.write("=" * 50 + "\n\n")
                    for message in self.messages:
                        f.write(message)
                        
                self.add_message(f"日志已保存到: {filename}", "SUCCESS")
                
        except Exception as e:
            self.add_message(f"保存日志失败: {e}", "ERROR")
            
    def on_window_close(self):
        """窗口关闭事件"""
        self.stop_monitoring()
        if self.window:
            self.window.destroy()
            self.window = None
            
    def show(self):
        """显示监控窗口"""
        self.create_window()
        

# 全局监控器实例
_global_monitor = None

def get_monitor():
    """获取全局监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ProcessMonitor()
    return _global_monitor

def log_message(message, msg_type="INFO"):
    """记录消息到监控器"""
    monitor = get_monitor()
    monitor.add_message(message, msg_type)
    
    # 同时打印到控制台
    print(f"[{msg_type}] {message}")

def log_info(message):
    """记录信息消息"""
    log_message(message, "INFO")

def log_success(message):
    """记录成功消息"""
    log_message(message, "SUCCESS")

def log_warning(message):
    """记录警告消息"""
    log_message(message, "WARNING")

def log_error(message):
    """记录错误消息"""
    log_message(message, "ERROR")

def log_process(message):
    """记录处理过程消息"""
    log_message(message, "PROCESS")

def show_monitor():
    """显示监控窗口"""
    monitor = get_monitor()
    monitor.show()

if __name__ == "__main__":
    # 测试监控器
    import time
    
    monitor = ProcessMonitor()
    monitor.show()
    
    # 模拟一些测试消息
    def test_messages():
        time.sleep(1)
        monitor.add_message("开始处理Excel文件...", "INFO")
        time.sleep(1)
        monitor.add_message("找到待处理文件1", "SUCCESS")
        time.sleep(1)
        monitor.add_message("开始执行处理1：筛选H列数据", "PROCESS")
        time.sleep(1)
        monitor.add_message("处理1完成：找到125行数据", "SUCCESS")
        time.sleep(1)
        monitor.add_message("开始执行处理2：筛选K列日期数据", "PROCESS")
        time.sleep(1)
        monitor.add_message("处理2完成：找到89行数据", "SUCCESS")
        time.sleep(1)
        monitor.add_message("开始执行处理3：筛选M列空值数据", "PROCESS")
        time.sleep(1)
        monitor.add_message("处理3完成：找到67行数据", "SUCCESS")
        time.sleep(1)
        monitor.add_message("开始执行处理4：筛选B列作废数据", "PROCESS")
        time.sleep(1)
        monitor.add_message("处理4完成：找到3行作废数据", "WARNING")
        time.sleep(1)
        monitor.add_message("最终结果：64行符合条件的数据", "SUCCESS")
    
    threading.Thread(target=test_messages, daemon=True).start()
    
    if monitor.window:
        monitor.window.mainloop()