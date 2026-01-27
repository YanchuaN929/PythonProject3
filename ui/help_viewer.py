#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帮助文档查看器模块
负责解析并显示Markdown格式的使用说明，支持目录导航和文本复制
"""

import tkinter as tk
from tkinter import ttk
import os
import sys
import re
from typing import Optional, List, Tuple, Dict


def get_resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径（支持打包后的exe）"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class HelpViewer:
    """帮助文档查看窗口"""
    
    # 角色到章节ID的映射
    ROLE_SECTION_MAP = {
        '设计人员': '2-设计人员使用指南',
        '一室主任': '3-室主任使用指南',
        '二室主任': '3-室主任使用指南',
        '建筑总图室主任': '3-室主任使用指南',
        '所领导': '4-所领导使用指南',
        '管理员': '5-管理员使用指南',
    }
    
    def __init__(self, parent: tk.Tk, user_role: str = None):
        """
        初始化帮助查看器
        
        参数:
            parent: 父窗口
            user_role: 当前用户角色，用于自动定位到对应章节
        """
        self.parent = parent
        self.user_role = user_role
        self.window: Optional[tk.Toplevel] = None
        self.content_text: Optional[tk.Text] = None
        self.toc_tree: Optional[ttk.Treeview] = None
        
        # 存储章节位置信息
        self.section_positions: Dict[str, str] = {}  # section_id -> text index
        self.toc_items: List[Tuple[str, str, int]] = []  # (section_id, title, level)
        
        # 内容导航栏相关
        self.content_nav_frame: Optional[ttk.Frame] = None
        self.nav_buttons: Dict[str, ttk.Button] = {}
        self.current_section_label: Optional[ttk.Label] = None
        self.nav_btn_container: Optional[ttk.Frame] = None
        self.content_scrollbar: Optional[ttk.Scrollbar] = None
        
        # 防抖标志
        self._scroll_update_pending = False
        self._user_clicking_toc = False  # 用户是否正在点击目录
        
    def show(self):
        """显示帮助窗口"""
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return
            
        self._create_window()
        self._load_and_display_content()
        self._auto_navigate_to_role_section()
        
    def _create_window(self):
        """创建帮助窗口"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("使用说明")
        self.window.geometry("900x650")
        self.window.minsize(700, 500)
        
        # 设置窗口图标
        try:
            icon_path = get_resource_path("ico_bin/tubiao.ico")
            if os.path.exists(icon_path):
                self.window.iconbitmap(icon_path)
        except Exception:
            pass
        
        # 居中显示
        self._center_window()
        
        # 创建主框架
        main_frame = ttk.Frame(self.window, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建分隔窗格
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧目录面板
        toc_frame = ttk.Frame(paned, width=200)
        self._create_toc_panel(toc_frame)
        paned.add(toc_frame, weight=0)
        
        # 右侧内容面板
        content_frame = ttk.Frame(paned)
        self._create_content_panel(content_frame)
        paned.add(content_frame, weight=1)
        
    def _center_window(self):
        """居中显示窗口"""
        self.window.update_idletasks()
        width = 1400
        height = 900
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 2
        
        # 确保不超出屏幕
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = max(0, min(x, screen_width - width))
        y = max(0, min(y, screen_height - height))
        
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        
    def _create_toc_panel(self, parent: ttk.Frame):
        """创建目录面板"""
        # 标题
        title_label = ttk.Label(parent, text="📖 目录", font=("Microsoft YaHei", 12, "bold"))
        title_label.pack(pady=(5, 10), anchor=tk.W, padx=5)
        
        # 目录树
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))
        
        self.toc_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.toc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        toc_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.toc_tree.yview)
        toc_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.toc_tree.configure(yscrollcommand=toc_scrollbar.set)
        
        # 绑定点击事件
        self.toc_tree.bind("<<TreeviewSelect>>", self._on_toc_select)
        
        # 配置目录树样式
        style = ttk.Style()
        style.configure("Treeview", font=("Microsoft YaHei", 11), rowheight=28)
        
    def _create_content_panel(self, parent: ttk.Frame):
        """创建内容面板"""
        # 顶部导航栏
        self._create_content_nav_bar(parent)
        
        # 内容文本框
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 创建文本框 - 支持选中复制
        self.content_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 13),
            spacing1=8,      # 段前间距
            spacing2=4,      # 行间距
            spacing3=10,     # 段后间距
            padx=20,
            pady=15,
            cursor="arrow",
            selectbackground="#0078D4",
            selectforeground="white",
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        content_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._on_scrollbar)
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_text.configure(yscrollcommand=self._on_content_scroll)
        self.content_scrollbar = content_scrollbar
        
        # 配置文本标签样式
        self._configure_text_tags()
        
        # 绑定右键菜单
        self.content_text.bind("<Button-3>", self._show_context_menu)
        
        # 允许选中但禁止编辑（除了复制快捷键）
        self.content_text.bind("<Key>", self._on_key_press)
        
        # 绑定鼠标滚轮事件
        self.content_text.bind("<MouseWheel>", self._on_mousewheel)
        self.content_text.bind("<Button-4>", self._on_mousewheel)  # Linux
        self.content_text.bind("<Button-5>", self._on_mousewheel)  # Linux
    
    def _create_content_nav_bar(self, parent: ttk.Frame):
        """创建内容区域顶部导航栏"""
        self.content_nav_frame = ttk.Frame(parent)
        self.content_nav_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        # 当前章节显示
        self.current_section_label = ttk.Label(
            self.content_nav_frame,
            text="📍 使用说明",
            font=("Microsoft YaHei", 11),
            foreground="#666666"
        )
        self.current_section_label.pack(side=tk.LEFT, padx=(5, 15))
        
        # 分隔符
        ttk.Separator(self.content_nav_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # 快速导航按钮容器
        nav_btn_frame = ttk.Frame(self.content_nav_frame)
        nav_btn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 主要章节快速跳转按钮（将在解析文档后填充）
        self.nav_btn_container = nav_btn_frame
    
    def _populate_nav_buttons(self):
        """填充导航按钮（仅显示一级和二级标题）"""
        # 清空现有按钮
        for widget in self.nav_btn_container.winfo_children():
            widget.destroy()
        self.nav_buttons.clear()
        
        # 只添加二级标题的快速导航
        for section_id, title, level in self.toc_items:
            if level == 2:
                # 提取简短标题（数字 + 前几个字）
                short_title = title
                match = re.match(r'^(\d+)\.\s*(.+)$', title)
                if match:
                    num, text = match.groups()
                    # 截取前10个字符，显示更完整
                    short_title = f"{num}. {text[:10]}" + ("..." if len(text) > 10 else "")
                
                btn = ttk.Button(
                    self.nav_btn_container,
                    text=short_title,
                    width=16,  # 加宽按钮
                    command=lambda sid=section_id: self._navigate_to_section(sid)
                )
                btn.pack(side=tk.LEFT, padx=3)
                self.nav_buttons[section_id] = btn
    
    def _navigate_to_section(self, section_id: str):
        """导航到指定章节"""
        position = self.section_positions.get(section_id)
        if position:
            self.content_text.configure(state=tk.NORMAL)
            self.content_text.see(position)
            self.content_text.configure(state=tk.DISABLED)
            
            # 同步左侧目录选择
            try:
                self.toc_tree.selection_set(section_id)
                self.toc_tree.see(section_id)
            except tk.TclError:
                pass
            
            # 更新当前章节显示
            self._update_current_section_display(section_id)
    
    def _on_scrollbar(self, *args):
        """滚动条事件处理"""
        self.content_text.yview(*args)
        self._schedule_scroll_update()
    
    def _on_content_scroll(self, first, last):
        """内容滚动时的回调"""
        self.content_scrollbar.set(first, last)
        self._schedule_scroll_update()
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件"""
        # 延迟更新，避免频繁刷新
        self._schedule_scroll_update()
    
    def _schedule_scroll_update(self):
        """调度滚动更新（防抖）"""
        if self._scroll_update_pending:
            return
        self._scroll_update_pending = True
        self.window.after(100, self._do_scroll_update)
    
    def _do_scroll_update(self):
        """执行滚动更新"""
        self._scroll_update_pending = False
        self._sync_toc_with_content()
    
    def _sync_toc_with_content(self):
        """根据内容滚动位置同步左侧目录高亮"""
        if not self.section_positions or not self.content_text:
            return
        
        # 如果用户正在点击目录，跳过同步
        if self._user_clicking_toc:
            return
        
        try:
            # 获取当前可见区域的第一行
            visible_index = self.content_text.index("@0,0")
            visible_line = int(visible_index.split('.')[0])
            
            # 查找当前可见的章节
            current_section = None
            current_section_line = 0
            
            for section_id, position in self.section_positions.items():
                section_line = int(position.split('.')[0])
                # 找到最接近但不超过当前可见行的章节
                if section_line <= visible_line + 3:  # 允许3行的偏移
                    if section_line > current_section_line:
                        current_section = section_id
                        current_section_line = section_line
            
            if current_section:
                # 更新左侧目录选择（不触发滚动事件）
                try:
                    current_selection = self.toc_tree.selection()
                    if not current_selection or current_selection[0] != current_section:
                        self.toc_tree.selection_set(current_section)
                        self.toc_tree.see(current_section)
                except tk.TclError:
                    pass
                
                # 更新顶部导航栏显示
                self._update_current_section_display(current_section)
                
        except Exception:
            pass
    
    def _update_current_section_display(self, section_id: str):
        """更新当前章节显示"""
        if not self.current_section_label:
            return
        
        # 查找章节标题
        for sid, title, level in self.toc_items:
            if sid == section_id:
                display_text = f"📍 {title}"
                # 截取显示，避免过长
                if len(display_text) > 35:
                    display_text = display_text[:32] + "..."
                self.current_section_label.configure(text=display_text)
                break
        
    def _configure_text_tags(self):
        """配置文本样式标签"""
        # 一级标题
        self.content_text.tag_configure(
            "h1",
            font=("Microsoft YaHei", 20, "bold"),
            spacing1=20,
            spacing3=15,
            foreground="#1a1a1a"
        )
        
        # 二级标题
        self.content_text.tag_configure(
            "h2",
            font=("Microsoft YaHei", 17, "bold"),
            spacing1=18,
            spacing3=12,
            foreground="#2d2d2d"
        )
        
        # 三级标题
        self.content_text.tag_configure(
            "h3",
            font=("Microsoft YaHei", 15, "bold"),
            spacing1=14,
            spacing3=8,
            foreground="#404040"
        )
        
        # 正文
        self.content_text.tag_configure(
            "body",
            font=("Microsoft YaHei", 13),
            spacing1=6,
            spacing3=6,
        )
        
        # 代码块
        self.content_text.tag_configure(
            "code",
            font=("Consolas", 11),
            background="#f5f5f5",
            spacing1=8,
            spacing3=8,
        )
        
        # 表格
        self.content_text.tag_configure(
            "table",
            font=("Microsoft YaHei", 12),
            spacing1=4,
            spacing3=4,
        )
        
        # 列表项
        self.content_text.tag_configure(
            "list",
            font=("Microsoft YaHei", 13),
            lmargin1=30,
            lmargin2=45,
            spacing1=4,
            spacing3=4,
        )
        
        # 引用块
        self.content_text.tag_configure(
            "quote",
            font=("Microsoft YaHei", 12, "italic"),
            foreground="#666666",
            lmargin1=20,
            lmargin2=20,
            spacing1=8,
            spacing3=8,
        )
        
        # 分隔线
        self.content_text.tag_configure(
            "hr",
            font=("Microsoft YaHei", 6),
            foreground="#cccccc",
            spacing1=10,
            spacing3=10,
        )
        
        # 加粗
        self.content_text.tag_configure(
            "bold",
            font=("Microsoft YaHei", 13, "bold"),
        )
        
    def _on_key_press(self, event):
        """处理按键事件 - 只允许复制操作"""
        # 允许 Ctrl+C 和 Ctrl+A
        if event.state & 0x4:  # Ctrl键被按下
            if event.keysym.lower() in ('c', 'a'):
                return  # 允许复制和全选
        return "break"  # 阻止其他输入
        
    def _show_context_menu(self, event):
        """显示右键菜单"""
        menu = tk.Menu(self.window, tearoff=0)
        menu.add_command(label="复制", command=self._copy_selection)
        menu.add_command(label="全选", command=self._select_all)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            
    def _copy_selection(self):
        """复制选中的文本"""
        try:
            selected_text = self.content_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.window.clipboard_clear()
            self.window.clipboard_append(selected_text)
        except tk.TclError:
            pass  # 没有选中文本
            
    def _select_all(self):
        """全选文本"""
        self.content_text.tag_add(tk.SEL, "1.0", tk.END)
        self.content_text.mark_set(tk.INSERT, "1.0")
        self.content_text.see(tk.INSERT)
        
    def _load_and_display_content(self):
        """加载并显示帮助文档内容"""
        content = self._load_markdown()
        if not content:
            self.content_text.insert(tk.END, "无法加载帮助文档。\n\n请确保 document/4_使用说明.md 文件存在。")
            return
            
        self._parse_and_display(content)
        
    def _load_markdown(self) -> str:
        """加载Markdown文件内容"""
        # 尝试多个可能的路径
        possible_paths = [
            get_resource_path("document/4_使用说明.md"),
            os.path.join(os.path.dirname(__file__), "document", "4_使用说明.md"),
            "document/4_使用说明.md",
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        return f.read()
            except Exception:
                continue
                
        return ""
        
    def _parse_and_display(self, content: str):
        """解析Markdown并显示"""
        lines = content.split('\n')
        in_code_block = False
        code_buffer = []
        in_table = False
        table_buffer = []
        
        self.content_text.configure(state=tk.NORMAL)
        self.content_text.delete("1.0", tk.END)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 代码块处理
            if line.strip().startswith('```'):
                if in_code_block:
                    # 结束代码块
                    code_text = '\n'.join(code_buffer)
                    self.content_text.insert(tk.END, code_text + '\n\n', "code")
                    code_buffer = []
                    in_code_block = False
                else:
                    # 开始代码块
                    in_code_block = True
                i += 1
                continue
                
            if in_code_block:
                code_buffer.append(line)
                i += 1
                continue
                
            # 表格处理
            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    in_table = True
                table_buffer.append(line)
                i += 1
                continue
            elif in_table:
                # 表格结束
                self._render_table(table_buffer)
                table_buffer = []
                in_table = False
                
            # 分隔线
            if line.strip() == '---':
                self.content_text.insert(tk.END, "─" * 60 + '\n', "hr")
                i += 1
                continue
                
            # 标题处理
            if line.startswith('# '):
                title = line[2:].strip()
                section_id = self._generate_section_id(title, 1)
                self.section_positions[section_id] = self.content_text.index(tk.END)
                self.toc_items.append((section_id, title, 1))
                self.content_text.insert(tk.END, title + '\n', "h1")
                i += 1
                continue
                
            if line.startswith('## '):
                title = line[3:].strip()
                section_id = self._generate_section_id(title, 2)
                self.section_positions[section_id] = self.content_text.index(tk.END)
                self.toc_items.append((section_id, title, 2))
                self.content_text.insert(tk.END, title + '\n', "h2")
                i += 1
                continue
                
            if line.startswith('### '):
                title = line[4:].strip()
                section_id = self._generate_section_id(title, 3)
                self.section_positions[section_id] = self.content_text.index(tk.END)
                self.toc_items.append((section_id, title, 3))
                self.content_text.insert(tk.END, title + '\n', "h3")
                i += 1
                continue
                
            # 引用块
            if line.startswith('> '):
                self.content_text.insert(tk.END, line[2:] + '\n', "quote")
                i += 1
                continue
                
            # 列表项
            if line.strip().startswith('- ') or line.strip().startswith('* '):
                text = line.strip()[2:]
                self.content_text.insert(tk.END, "• " + text + '\n', "list")
                i += 1
                continue
                
            # 数字列表
            match = re.match(r'^(\d+)\.\s+(.+)$', line.strip())
            if match:
                num, text = match.groups()
                self.content_text.insert(tk.END, f"{num}. {text}\n", "list")
                i += 1
                continue
                
            # 普通段落
            if line.strip():
                # 处理加粗文本
                self._insert_formatted_text(line + '\n')
            else:
                self.content_text.insert(tk.END, '\n')
                
            i += 1
            
        # 处理剩余的表格
        if table_buffer:
            self._render_table(table_buffer)
            
        # 更新目录树
        self._populate_toc_tree()
        
        # 填充顶部导航按钮
        self._populate_nav_buttons()
        
        self.content_text.configure(state=tk.DISABLED)
        
    def _generate_section_id(self, title: str, level: int) -> str:
        """生成章节ID"""
        # 提取数字前缀作为ID
        match = re.match(r'^(\d+(?:\.\d+)?)', title)
        if match:
            return f"{level}-{match.group(1)}-{title[:20]}"
        return f"{level}-{title[:30]}"
        
    def _insert_formatted_text(self, text: str):
        """插入格式化文本（处理加粗等）"""
        # 简单处理：查找 **text** 或 __text__ 模式
        pattern = r'\*\*(.+?)\*\*|__(.+?)__'
        last_end = 0
        
        for match in re.finditer(pattern, text):
            # 插入匹配前的普通文本
            if match.start() > last_end:
                self.content_text.insert(tk.END, text[last_end:match.start()], "body")
            
            # 插入加粗文本
            bold_text = match.group(1) or match.group(2)
            self.content_text.insert(tk.END, bold_text, "bold")
            
            last_end = match.end()
            
        # 插入剩余文本
        if last_end < len(text):
            self.content_text.insert(tk.END, text[last_end:], "body")
            
    def _render_table(self, table_lines: List[str]):
        """渲染表格"""
        if len(table_lines) < 2:
            return
            
        # 解析表格
        rows = []
        for line in table_lines:
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            # 跳过分隔行
            if all(set(cell) <= set('-| :') for cell in cells):
                continue
            rows.append(cells)
            
        if not rows:
            return
            
        # 简单文本表格输出
        self.content_text.insert(tk.END, '\n', "body")
        for row in rows:
            row_text = '  |  '.join(row)
            self.content_text.insert(tk.END, row_text + '\n', "table")
        self.content_text.insert(tk.END, '\n', "body")
        
    def _populate_toc_tree(self):
        """填充目录树"""
        # 清空现有项
        for item in self.toc_tree.get_children():
            self.toc_tree.delete(item)
            
        # 用于跟踪父节点
        parent_stack = {1: '', 2: '', 3: ''}
        
        for section_id, title, level in self.toc_items:
            # 确定父节点
            parent = ''
            if level == 2:
                parent = parent_stack.get(1, '')
            elif level == 3:
                parent = parent_stack.get(2, '') or parent_stack.get(1, '')
                
            # 插入节点
            try:
                item_id = self.toc_tree.insert(parent, tk.END, iid=section_id, text=title, open=(level <= 2))
                parent_stack[level] = item_id
            except tk.TclError:
                # ID已存在，添加后缀
                item_id = self.toc_tree.insert(parent, tk.END, text=title, open=(level <= 2))
                self.section_positions[item_id] = self.section_positions.get(section_id, "1.0")
                
    def _on_toc_select(self, event):
        """目录项选中事件"""
        selection = self.toc_tree.selection()
        if not selection:
            return
            
        item_id = selection[0]
        
        # 设置标志，避免滚动同步时重复触发
        self._user_clicking_toc = True
        
        # 获取对应的文本位置
        position = self.section_positions.get(item_id)
        if position:
            self.content_text.configure(state=tk.NORMAL)
            self.content_text.see(position)
            self.content_text.configure(state=tk.DISABLED)
            
            # 更新顶部导航栏显示
            self._update_current_section_display(item_id)
        
        # 延迟重置标志
        if self.window:
            self.window.after(200, self._reset_toc_click_flag)
        else:
            self._user_clicking_toc = False
    
    def _reset_toc_click_flag(self):
        """重置目录点击标志"""
        self._user_clicking_toc = False
            
    def _auto_navigate_to_role_section(self):
        """根据用户角色自动导航到对应章节"""
        if not self.user_role:
            return
            
        # 处理多角色情况（取第一个角色）
        role = self.user_role.split(',')[0].strip() if ',' in self.user_role else self.user_role.strip()
        
        # 检查是否是接口工程师角色
        if '接口工程师' in role:
            role = '管理员'  # 接口工程师使用管理员章节
            
        # 查找对应章节
        target_section_name = self.ROLE_SECTION_MAP.get(role)
        if not target_section_name:
            return
            
        # 在目录项中查找匹配的章节
        for section_id, title, level in self.toc_items:
            if target_section_name in title or title in target_section_name:
                # 选中目录项
                try:
                    self.toc_tree.selection_set(section_id)
                    self.toc_tree.see(section_id)
                    
                    # 滚动到对应位置
                    position = self.section_positions.get(section_id)
                    if position:
                        self.content_text.configure(state=tk.NORMAL)
                        self.content_text.see(position)
                        self.content_text.configure(state=tk.DISABLED)
                except tk.TclError:
                    pass
                break


def show_help(parent: tk.Tk, user_role: str = None):
    """
    便捷函数：显示帮助窗口
    
    参数:
        parent: 父窗口
        user_role: 用户角色
    """
    viewer = HelpViewer(parent, user_role)
    viewer.show()
    return viewer

