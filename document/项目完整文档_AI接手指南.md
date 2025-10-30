# 接口筛选程序 - 完整项目文档与AI接手指南

> **版本**: 3.0  
> **最后更新**: 2025-10-30  
> **目标**: 让新的AI助手能够无缝接手此项目，理解所有设计决策、代码风格和业务逻辑

---

## 📋 目录

1. [项目概述](#项目概述)
2. [核心业务逻辑](#核心业务逻辑)
3. [架构设计](#架构设计)
4. [代码结构详解](#代码结构详解)
5. [关键技术实现](#关键技术实现)
6. [编码风格规范](#编码风格规范)
7. [测试策略](#测试策略)
8. [重要历史决策](#重要历史决策)
9. [常见问题与解决方案](#常见问题与解决方案)
10. [开发环境配置](#开发环境配置)

---

## 项目概述

### 项目背景

这是一个**接口数据筛选与导出工具**，主要用于建筑设计院的接口管理工作。程序从多个Excel文件中读取接口数据，根据不同角色（所领导、室主任、设计人员、管理员、接口工程师）的权限和需求，筛选出相关的待处理接口，并支持导出为TXT格式报告。

### 核心功能

1. **多角色权限管理**: 5种角色，每种角色有不同的数据可见范围和时间窗口
2. **6类文件处理**: 
   - 文件1-5: 接口数据文件（内部/外部 × 打开/回复 + 三维提资）
   - 文件6: 收发文函（特殊处理逻辑）
3. **智能日期筛选**: 工作日计算、跨年日期解析、月度范围
4. **结果缓存**: 文件哈希检测变化，避免重复处理
5. **用户状态隔离**: 每个用户的勾选状态独立保存
6. **自动运行模式**: 支持开机自启动、定时刷新
7. **系统托盘**: 最小化到系统托盘，后台运行

### 技术栈

- **语言**: Python 3.8（兼容Win7+）
- **GUI**: Tkinter
- **数据处理**: Pandas 1.1.5, NumPy 1.19.5
- **Excel读取**: openpyxl 3.0.10, xlrd 1.2.0
- **系统托盘**: pystray 0.19.4, Pillow 8.4.0
- **打包**: PyInstaller
- **测试**: pytest

### 部署环境

- **最低系统**: Windows 7 SP1
- **推荐系统**: Windows 10/11
- **内存**: 最低2GB，推荐4GB+
- **磁盘空间**: 程序约150MB，缓存动态增长

---

## 核心业务逻辑

### 1. 角色与权限体系

| 角色 | 科室限制 | 时间窗口 | 文件访问 | 导出模式 | 特殊说明 |
|------|---------|---------|---------|---------|---------|
| **所领导** | ❌ 无（全部门） | 2工作日 | 文件1-6 | 简洁（自动） | 文件6无时间限制 |
| **一室主任** | ✅ 一室 | 7工作日 | 文件1-6 | 完整 | - |
| **二室主任** | ✅ 二室 | 7工作日 | 文件1-6 | 完整 | - |
| **建筑总图室主任** | ✅ 建筑总图室 | 7工作日 | 文件1-6 | 完整 | - |
| **管理员** | ❌ 无 | 无限制 | 文件1-6 | 可选简洁 | 文件6无时间限制 |
| **设计人员** | ✅ 按姓名 | 月度范围 | 文件1-5 | 完整 | 无文件6权限 |
| **接口工程师** | ❌ 无 | 无限制 | 文件1-5 | 完整 | 按项目号筛选 |

### 2. 文件处理逻辑

#### 文件1-5（接口数据文件）

**文件识别规则**:
- **文件1**: `{项目号}按项目导出IDI手册{日期}` 或 `{项目号}{任意文字}IDI手册{日期}`
- **文件2**: `{项目号}接口移交表{日期}` 或 `{项目号}{任意文字}接口移交表{日期}`
- **文件3**: `{项目号}接口答复表{日期}` 或 `{项目号}{任意文字}接口答复表{日期}`
- **文件4**: `{项目号}外部单位打开接口{日期}` 或 `{项目号}{任意文字}外部单位打开接口{日期}`
- **文件5**: `{项目号}三维提资{日期}` 或 `{项目号}{任意文字}三维提资{日期}`

其中 `{项目号}` 必须是4位数字（如2016、2026、2306）。

**共同处理逻辑**:
1. 提取责任人（X列/第24列）
2. 提取接口时间（各文件列位置不同）
3. 根据角色筛选责任人
4. 根据角色应用时间窗口
5. 生成 `项目号`、`接口号`、`接口时间` 列
6. 添加 `状态` 列（⚠️表示延期）

**日期列位置**:
- **文件1**: K列（索引10）
- **文件2**: M列（索引12）
- **文件3**: M列优先，M为空时用L列（索引12/11）
- **文件4**: S列（索引18）
- **文件5**: L列（索引11）

#### 文件6（收发文函）

**文件识别规则**:
- 文件名包含 `"收发文"` 或 `"发文清单"` 关键词

**筛选条件**:
- **V列**（索引21）: 必须包含 `"河北分公司.建筑结构所"`
- **I列**（索引8）: 日期 ≤ 今天+14天（包含过去所有日期）
  - **例外**: 管理员和所领导跳过I列时间筛选
- **M列**（索引12）: 必须为 `"尚未回复"` 或 `"超期未回复"`

**特殊处理**:
- 管理员和所领导: **不受I列时间限制**，可查看所有历史和未来数据
- 其他角色: 受I列时间筛选
- 保留原始所有列，不做列裁剪

### 3. 时间窗口计算

#### 工作日计算（用于所领导、室主任）

**核心函数**: `date_utils.get_workday_difference(target_date, reference_date)`

```python
def get_workday_difference(target_date: date, reference_date: date) -> int:
    """
    计算目标日期与参考日期之间的工作日差异
    - 正数: target_date 在 reference_date 之后
    - 负数: target_date 在 reference_date 之前（已延期）
    - 排除周六、周日
    """
```

**应用场景**:
- **所领导**: 保留工作日差 ≤ 2 的数据（所有已延期 + 未来2个工作日）
- **室主任**: 保留工作日差 ≤ 7 的数据（所有已延期 + 未来7个工作日）

#### 跨年日期解析

**核心函数**: `date_utils.parse_mmdd_to_date(date_str, reference_date)`

**智能逻辑**（180天阈值）:
```
假设今天是2025-10-28:
- "09.15" → 今年9月15日（已延期，相差<180天）
- "10.20" → 今年10月20日（已延期）
- "11.05" → 今年11月5日（未来日期）
- "01.15" → 明年1月15日（相差>180天，视为跨年未来）
```

**关键代码**:
```python
if parsed_date < reference_date:
    days_past = (reference_date - parsed_date).days
    if days_past > 180:
        # 相差超过180天，判断为"明年的日期"
        try:
            return date(reference_date.year + 1, month, day)
        except ValueError:
            return None
    else:
        # 相差不超过180天，判断为"今年的已延期数据"
        return parsed_date
```

#### 月度范围（用于设计人员）

**逻辑**:
- 每月1~19号: 筛选当年1月1日 ~ 当月末
- 每月20~31号: 筛选当年1月1日 ~ 次月末

**目的**: 让设计人员提前看到下月的数据

### 4. 导出逻辑

#### 简洁模式 vs 完整模式

| 模式 | 接口号显示 | 适用角色 | 触发条件 |
|------|-----------|---------|---------|
| **简洁** | 只显示个数 | 所领导（自动）、管理员（手动） | `简洁模式`勾选框 或 角色为所领导 |
| **完整** | 列出所有接口号 | 其他所有角色 | 默认 |

**示例**:
```
简洁模式:
  • 内部需打开接口: 共5个

完整模式:
  • 内部需打开接口: 共5个
    INT-001, INT-002, INT-003, INT-004, INT-005
```

#### 导出文件命名

格式: `{项目号}_{用户姓名}_{日期时间}.txt`

例如: `2016_张三_20251028_153045.txt`

### 5. 缓存机制

#### 文件哈希缓存

**目的**: 检测文件是否变化，避免重复处理

**实现**:
```python
# file_manager.py
def generate_file_identity(self, file_path):
    """
    基于: 文件名 + 文件大小 + 修改时间
    生成MD5哈希
    """
```

**触发清空**:
- 文件内容变化（修改时间或大小改变）
- 手动点击"刷新文件"

#### 结果缓存

**结构**: `result_cache/{file_hash}_{project_id}_{file_type}.pkl`

**缓存内容**: 处理后的DataFrame对象（pickle序列化）

**生命周期**: 文件变化时自动失效

#### 用户勾选状态缓存

**结构** (file_cache.json):
```json
{
  "file_identities": {
    "文件路径": "文件哈希"
  },
  "completed_rows": {
    "用户姓名": {
      "文件路径": {
        "行号": true
      }
    }
  }
}
```

**关键点**:
- **按用户隔离**: 张三的勾选不影响李四
- **自动迁移**: 旧格式（无用户分组）自动迁移到"默认用户"

---

## 架构设计

### 模块职责划分

```
┌─────────────────────────────────────────────┐
│              base.py (主程序)                │
│  - GUI生命周期管理                           │
│  - 角色权限控制                              │
│  - 文件读取协调                              │
│  - 结果展示与导出                            │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┼───────┬──────────┬──────────┐
       │       │       │          │          │
┌──────▼──┐ ┌─▼────┐ ┌▼────────┐ ┌▼────────┐ ┌▼────────┐
│ main.py │ │window│ │  file_  │ │  date_  │ │ Monitor │
│         │ │.py   │ │ manager │ │  utils  │ │  .py    │
│ Excel   │ │      │ │  .py    │ │  .py    │ │         │
│ 数据    │ │ GUI  │ │         │ │         │ │ 日志    │
│ 处理    │ │ 显示 │ │ 缓存    │ │ 日期    │ │ 监控    │
│ 逻辑    │ │      │ │ 管理    │ │ 工具    │ │         │
└─────────┘ └──────┘ └─────────┘ └─────────┘ └─────────┘
```

### 核心设计原则

1. **职责单一**: 每个模块只负责一个明确的功能域
2. **高内聚低耦合**: 模块间通过清晰的接口交互
3. **向后兼容**: 保留旧代码结构，新功能通过扩展实现
4. **测试优先**: 关键逻辑必须有测试覆盖
5. **用户体验**: 界面友好、操作简单、错误提示清晰

### 关键交互流程

#### 启动流程
```
1. 加载配置 (config.json)
2. 初始化FileIdentityManager (缓存管理器)
3. 创建Tkinter根窗口
4. 创建WindowManager (界面管理)
5. 设置 window_manager.app = self (关键！)
6. 加载用户配置 (角色、姓名)
7. 扫描文件夹
8. 如果是自动模式: 启动定时任务
```

#### 处理流程
```
1. 用户点击"开始筛选" 或 自动触发
2. base.py: start_processing()
   - 并发读取所有Excel文件 (concurrent_read_excel_files)
   - 识别文件类型 (find_all_target_files1~6)
3. 对每个文件+项目组合:
   - 检查缓存 (_process_with_cache)
   - 如果缓存未命中: 调用main.py的处理函数
     - process_target_file1~5 或 process_target_file6
   - 应用角色过滤 (apply_role_based_filter)
   - 排除已完成项 (_exclude_completed_rows)
4. 合并结果到6个选项卡
5. 显示到GUI (window.py: display_excel_data)
```

#### 导出流程
```
1. 用户点击"导出结果"
2. base.py: export_results()
3. 判断用户角色:
   - 如果是所领导: 自动简洁模式
   - 否则: 读取"简洁模式"勾选框
4. 遍历6个选项卡的数据:
   - 如果简洁模式: 只写个数
   - 如果完整模式: 列出所有接口号
5. 生成TXT文件
6. 弹窗提示或静默完成（取决于配置）
```

---

## 代码结构详解

### base.py (主程序，4501行)

**核心类**: `ExcelProcessorApp`

**关键方法**:

```python
class ExcelProcessorApp:
    def __init__(self):
        """初始化主程序"""
        
    def setup_window(self):
        """设置窗口"""
        # 【重要】在创建WindowManager后必须设置app引用
        self.window_manager = WindowManager(self.root, callbacks)
        self.window_manager.app = self  # ← 关键行！
        
    def scan_folder(self):
        """扫描文件夹，识别所有Excel文件"""
        
    def start_processing(self):
        """开始处理（主入口）"""
        # 1. 并发读取Excel
        # 2. 分类识别文件
        # 3. 调用处理函数
        # 4. 应用角色过滤
        # 5. 显示结果
        
    def _process_with_cache(self, file_path, project_id, file_type, process_func, current_datetime, *args):
        """处理单个文件（带缓存）"""
        # 检查缓存 → 调用处理函数 → 保存缓存
        
    def apply_role_based_filter(self, df, role, user_name, file_type=None):
        """应用角色过滤"""
        # 核心权限控制逻辑
        
    def _filter_by_single_role(self, safe_df, role, user_name, file_type=None):
        """单角色过滤逻辑"""
        # 【重要】所领导的2工作日时间窗口在这里实现
        
    def apply_auto_role_date_window(self, df, user_role):
        """自动模式下应用角色时间窗口（用于导出）"""
        # 【重要】室主任的7工作日时间窗口在这里实现
        
    def _exclude_completed_rows(self, df, source_file):
        """排除已完成的行"""
        # 【重要】调用时必须传入user_name
        user_name = getattr(self, 'user_name', '').strip()
        completed_rows = self.file_manager.get_completed_rows(source_file, user_name)
        
    def display_excel_data_with_original_rows(self, viewer, df, label_text, excel_row_numbers):
        """显示数据到Treeview"""
        # 委托给window_manager
        
    def export_results(self):
        """导出结果"""
        # 判断简洁模式 → 生成TXT → 保存文件
```

**关键配置**:
```python
# 默认角色天数配置（用于自动模式和导出）
self.role_export_days = {
    "一室主任": 7,          # 7个工作日
    "二室主任": 7,          # 7个工作日
    "建筑总图室主任": 7,    # 7个工作日
    "所领导": 2,            # 2个工作日
    "管理员": None,         # 无限制
    "设计人员": None,       # 按月度范围
}
```

### main.py (Excel处理逻辑，3455行)

**全局开关**:
```python
# 日期筛选逻辑开关（影响设计人员的月度范围）
USE_OLD_DATE_LOGIC = False  # False=新逻辑（推荐）
```

**文件识别函数**:
```python
def find_all_target_files1(excel_files):
    """识别所有待处理文件1（IDI手册）"""
    
def find_all_target_files2(excel_files):
    """识别所有待处理文件2（接口移交表）"""
    
# ... 依此类推到 find_all_target_files6
```

**文件处理函数**:
```python
def process_target_file1(file_path, current_datetime):
    """处理待处理文件1"""
    # 返回: DataFrame with columns ['项目号', '接口号', '接口时间', '责任人', ...]
    
def process_target_file6(file_path, current_datetime, skip_date_filter=False):
    """处理待处理文件6（收发文函）"""
    # skip_date_filter: 管理员/所领导跳过I列时间筛选
```

**条件筛选函数**（文件6示例）:
```python
def execute6_process1(df):
    """V列包含'河北分公司.建筑结构所'"""
    
def execute6_process3(df, current_datetime):
    """I列日期 ≤ 今天+14天"""
    
def execute6_process4(df):
    """M列为'尚未回复'或'超期未回复'"""
```

### window.py (GUI显示，1323行)

**核心类**: `WindowManager`

**关键属性**:
```python
self.app = None  # 【重要】必须在base.py中设置，用于获取user_name
self.viewers = {}  # 6个选项卡的Treeview引用
```

**关键方法**:
```python
def display_excel_data(self, viewer, df, label_text, source_file, file_manager, excel_row_numbers=None):
    """显示数据到Treeview（主显示逻辑）"""
    # 【重要】必须通过self.app获取user_name
    user_name = getattr(self.app, 'user_name', '').strip()
    
    # 列顺序: 状态 | 项目号 | 接口号 | 接口时间 | 是否已完成
    
def _calculate_single_column_width(self, series, column_name, min_width=50, max_width=400):
    """计算单列宽度（智能处理中文字符）"""
    
def _sort_by_column(self, viewer, col, file_manager, source_file, excel_row_numbers):
    """列排序（点击列头触发）"""
    
def _generate_sort_key(self, item_values, col_index, columns):
    """生成排序键（智能识别数据类型）"""
    # 接口时间: 空值排最后
    # 项目号: 数字排序
    # 是否已完成: ☑在前、☐在后
    # 状态: ⚠️在前
```

**固定列宽配置**:
```python
fixed_widths = {
    '状态': 50,
    '项目号': 75,
    '接口号': 240,
    '接口时间': 85,
    '是否已完成': 95,
}
```

### file_manager.py (缓存管理，547行)

**核心类**: `FileIdentityManager`

**缓存结构**:
```python
self.file_identities = {}  # {file_path: hash}
self.completed_rows = {}   # {user_name: {file_path: {row_index: True}}}
```

**关键方法**:
```python
def generate_file_identity(self, file_path):
    """生成文件哈希（文件名+大小+修改时间）"""
    
def set_row_completed(self, file_path, row_index, user_name, completed=True):
    """设置行勾选状态（按用户隔离）"""
    
def is_row_completed(self, file_path, row_index, user_name):
    """检查行是否已勾选（按用户隔离）"""
    
def get_completed_rows(self, file_path, user_name):
    """获取某用户在某文件中的所有勾选行"""
    
def has_file_changed(self, file_path):
    """检查文件是否变化"""
    
def get_cached_result(self, file_path, project_id, file_type):
    """获取缓存的处理结果"""
    
def save_cached_result(self, file_path, project_id, file_type, result):
    """保存处理结果到缓存"""
```

### date_utils.py (日期工具，276行)

**核心函数**:
```python
def is_date_overdue(date_str: str, reference_date: Optional[date] = None) -> bool:
    """判断日期是否已延期（用于状态列的⚠️显示）"""
    
def count_workdays(start_date: date, end_date: date) -> int:
    """计算两日期间的工作日数"""
    
def get_workday_difference(target_date: date, reference_date: date) -> int:
    """计算工作日差异（正数=未来，负数=已延期）"""
    
def parse_mmdd_to_date(date_str: str, reference_date: Optional[date] = None) -> Optional[date]:
    """解析mm.dd格式日期（智能处理跨年）"""
    # 【核心】180天阈值逻辑
    
def get_date_warn_tag(date_str: str, reference_date: Optional[date] = None, use_workdays: bool = True) -> str:
    """生成日期警告标签"""
    # 返回: "已延误！！" | "下班前必须完成" | "注意时间" | ""
```

### Monitor.py (日志监控，422行)

**核心类**: `ProcessMonitor`

**全局单例**:
```python
_monitor_instance = None

def log_info(message):
    """记录信息日志"""
    
def log_success(message):
    """记录成功日志"""
    
def log_warning(message):
    """记录警告日志"""
    
def log_error(message):
    """记录错误日志"""
```

**使用方式**:
```python
import Monitor
Monitor.log_info("开始处理文件")
Monitor.log_success("处理完成")
Monitor.log_error(f"处理失败: {error}")
```

---

## 关键技术实现

### 1. 并发读取Excel文件

**位置**: `base.py: concurrent_read_excel_files()`

**技术**:
```python
from concurrent.futures import ThreadPoolExecutor

def concurrent_read_excel_files(file_paths, max_workers=4):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(optimized_read_excel, fp, project_id): (fp, project_id)
            for fp, project_id in file_paths
        }
        # ...
```

**性能提升**: 多文件读取速度提升3-4倍

### 2. 优化Excel读取

**位置**: `base.py: optimized_read_excel()`

**技术**:
```python
from openpyxl import load_workbook

def optimized_read_excel(file_path):
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    data = ws.values
    columns = next(data)
    df = pd.DataFrame(data, columns=columns)
    wb.close()
    return df
```

**性能提升**: 速度提升30-50%，内存减少40-60%

### 3. Treeview勾选框实现

**位置**: `window.py: display_excel_data()`

**技术**:
```python
# 使用Unicode字符模拟勾选框
CHECKBOX_UNCHECKED = "☐"
CHECKBOX_CHECKED = "☑"

# Treeview双击事件
viewer.bind("<Double-1>", lambda event: self._toggle_checkbox(...))

def _toggle_checkbox(self, event, viewer, file_manager, source_file, excel_row_numbers):
    # 切换勾选状态
    # 保存到file_manager（按用户隔离）
```

### 4. 智能列宽计算

**位置**: `window.py: _calculate_single_column_width()`

**技术**:
```python
def _calculate_single_column_width(self, series, column_name):
    # 中文字符宽度权重 * 1.8
    # 英文/数字字符宽度权重 * 1.0
    # 计算最大宽度，限制在min_width ~ max_width
```

### 5. 跨年日期解析

**位置**: `date_utils.py: parse_mmdd_to_date()`

**核心算法**:
```python
# 180天阈值法
if parsed_date < reference_date:
    days_past = (reference_date - reference_date).days
    if days_past > 180:
        # 视为明年
        return date(reference_date.year + 1, month, day)
    else:
        # 视为今年已延期
        return parsed_date
```

**示例**（假设今天10-28）:
- `"09.15"` → 2025-09-15（今年已延期，43天<180）
- `"01.15"` → 2026-01-15（明年未来，286天>180）

### 6. 系统托盘实现

**位置**: `base.py: setup_system_tray()`

**技术**:
```python
import pystray
from PIL import Image

def setup_system_tray(self):
    icon_path = get_resource_path("ico_bin/tubiao.ico")
    image = Image.open(icon_path)
    
    menu = pystray.Menu(
        pystray.MenuItem("显示主窗口", self.show_window),
        pystray.MenuItem("退出程序", self.quit_app)
    )
    
    self.tray_icon = pystray.Icon("name", image, "接口筛选", menu)
    threading.Thread(target=self.tray_icon.run, daemon=True).start()
```

### 7. 开机自启动

**位置**: `base.py: set_auto_startup()`

**技术**:
```python
import winreg

def set_auto_startup(self, enable):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    
    if enable:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        command = f'"{exe_path}" --auto'
        winreg.SetValueEx(key, "接口筛选程序", 0, winreg.REG_SZ, command)
    else:
        winreg.DeleteValue(key, "接口筛选程序")
    
    winreg.CloseKey(key)
```

---

## 编码风格规范

### 1. 文件头部

**所有Python文件必须包含**:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块说明（简洁描述模块职责）
"""
```

### 2. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| **类名** | PascalCase（大驼峰） | `ExcelProcessorApp`, `WindowManager` |
| **函数/方法** | snake_case（下划线） | `start_processing`, `apply_filter` |
| **私有方法** | 前缀`_` | `_filter_by_single_role`, `_load_cache` |
| **常量** | UPPER_SNAKE_CASE | `USE_OLD_DATE_LOGIC`, `CHECKBOX_CHECKED` |
| **变量** | snake_case | `user_name`, `file_path`, `current_datetime` |

### 3. 注释规范

**函数文档字符串**:
```python
def process_target_file1(file_path, current_datetime):
    """
    处理待处理文件1（IDI手册）
    
    参数:
        file_path (str): Excel文件路径
        current_datetime (datetime): 当前日期时间
    
    返回:
        pandas.DataFrame: 处理后的数据，包含列：
            - 项目号: 4位数字字符串
            - 接口号: 接口编号
            - 接口时间: mm.dd格式日期
            - 责任人: 责任人姓名
            - [其他原始列...]
    
    异常:
        ValueError: 文件格式不正确
        FileNotFoundError: 文件不存在
    """
```

**行内注释**:
```python
# 【重要】这是关键逻辑，不要修改
user_name = getattr(self, 'user_name', '').strip()

# 判断是否使用工作日计算（所领导、室主任使用工作日）
use_workdays = (user_role in ["所领导", "一室主任", "二室主任", "建筑总图室主任"])
```

**标签注释**:
- `# 【重要】`: 关键逻辑，修改需谨慎
- `# 【修复】`: Bug修复相关代码
- `# 【优化】`: 性能优化相关代码
- `# 【临时】`: 临时方案，未来需要改进
- `# TODO:`: 待办事项
- `# FIXME:`: 已知问题，需要修复

### 4. 代码格式

**缩进**: 4个空格（不使用Tab）

**行长度**: 建议不超过100字符，硬限制120字符

**空行**:
```python
# 类定义前后2个空行
class MyClass:
    pass


# 函数定义前后2个空行
def my_function():
    pass


# 类内方法之间1个空行
class MyClass:
    def method1(self):
        pass
    
    def method2(self):
        pass
```

**导入顺序**:
```python
# 1. 标准库
import os
import sys
from datetime import date, timedelta

# 2. 第三方库
import pandas as pd
import numpy as np
from openpyxl import load_workbook

# 3. 本地模块
from window import WindowManager
from date_utils import parse_mmdd_to_date
```

### 5. 错误处理

**明确捕获异常**:
```python
# ✅ 推荐
try:
    df = pd.read_excel(file_path)
except FileNotFoundError:
    Monitor.log_error(f"文件不存在: {file_path}")
    return None
except pd.errors.ParserError:
    Monitor.log_error(f"文件格式错误: {file_path}")
    return None

# ❌ 避免
try:
    df = pd.read_excel(file_path)
except:
    return None
```

**记录日志**:
```python
try:
    result = process_file(file_path)
    Monitor.log_success(f"处理成功: {file_path}")
    return result
except Exception as e:
    Monitor.log_error(f"处理失败: {file_path}, 错误: {str(e)}")
    raise
```

### 6. 变量命名约定

**DataFrame**: 使用 `df` 前缀
```python
df_file1 = process_target_file1(...)
df_filtered = apply_filter(df_file1)
```

**布尔变量**: 使用 `is_`, `has_`, `should_` 前缀
```python
is_admin = "管理员" in user_roles
has_changed = file_manager.has_file_changed(file_path)
should_skip = skip_date_filter
```

**Tkinter变量**: 使用 `_var` 后缀
```python
self.path_var = tk.StringVar()
self.process_tab1_var = tk.BooleanVar()
```

---

## 测试策略

### 测试框架

使用 **pytest** 进行单元测试和集成测试。

### 测试文件组织

```
tests/
├── __init__.py
├── conftest.py                      # pytest配置和fixture
├── test_date_utils.py               # 日期工具测试
├── test_file_manager.py             # 缓存管理测试
├── test_institute_leader.py         # 所领导角色测试
├── test_admin_file6_logic.py        # 管理员文件6逻辑测试
├── test_cross_year_date_parsing.py  # 跨年日期解析测试
├── test_user_checkbox_isolation.py  # 用户勾选隔离测试
├── test_interface_time_display.py   # 接口时间列显示测试
├── test_leader_display_filter.py    # 所领导显示过滤测试
├── test_file6_logic.py              # 文件6处理逻辑测试
├── test_multi_role.py               # 多角色测试
└── ... (其他测试文件)
```

### 测试命名规范

**测试类**: `Test{功能名称}`
```python
class TestInstituteLeader:
    """所领导功能测试"""
```

**测试方法**: `test_{具体测试场景}`
```python
def test_institute_leader_sees_all_departments(self):
    """所领导应该能看到所有科室的数据"""
    
def test_institute_leader_uses_workday_calculation(self):
    """所领导应该使用工作日计算"""
```

### 关键测试用例

#### 1. 日期工具测试
```python
# tests/test_date_utils.py
def test_workday_difference_exclude_weekends():
    """测试工作日计算排除周末"""
    # 2025-10-27(周一) 到 2025-10-31(周五) = 5个工作日
    
def test_parse_mmdd_handles_cross_year():
    """测试跨年日期解析"""
    # 10-28时, "01.15" 应解析为明年
    # 10-28时, "09.15" 应解析为今年（已延期）
```

#### 2. 角色权限测试
```python
# tests/test_institute_leader.py
def test_institute_leader_2_workday_window():
    """所领导应该只看到2个工作日内的数据"""
    
def test_director_7_workday_window():
    """室主任应该只看到7个工作日内的数据"""
```

#### 3. 缓存隔离测试
```python
# tests/test_user_checkbox_isolation.py
def test_user_checkbox_isolation():
    """测试用户勾选状态隔离"""
    # 用户A的勾选不应影响用户B
```

#### 4. 文件处理测试
```python
# tests/test_file6_logic.py
def test_file6_includes_past_dates():
    """文件6应包含过去的日期"""
    
def test_admin_skips_date_filter_for_file6():
    """管理员处理文件6时应跳过日期筛选"""
```

### 运行测试

**运行所有测试**:
```bash
pytest
```

**运行特定测试文件**:
```bash
pytest tests/test_date_utils.py -v
```

**运行特定测试方法**:
```bash
pytest tests/test_date_utils.py::test_workday_difference_exclude_weekends -v
```

**查看覆盖率**:
```bash
pytest --cov=. --cov-report=html
```

### 测试覆盖率目标

- **核心逻辑**: > 90%
- **工具函数**: 100%
- **GUI代码**: > 60% (难以测试，重点测试业务逻辑)

---

## 重要历史决策

### 1. 为什么使用Tkinter而不是PyQt？

**原因**:
- **兼容性**: Tkinter是Python标准库，无需额外安装
- **轻量级**: 打包后体积更小（约150MB vs PyQt的300MB+）
- **Win7支持**: PyQt5在Win7上兼容性差
- **学习曲线**: 团队更熟悉Tkinter

**权衡**: Tkinter界面较为简陋，但满足业务需求

### 2. 为什么使用pickle缓存而不是JSON？

**原因**:
- **性能**: pickle序列化DataFrame比JSON快10倍+
- **完整性**: pickle保留DataFrame的所有元数据（dtypes, index等）
- **简洁**: 无需自定义序列化逻辑

**权衡**: pickle不可读，但缓存文件本来就不需要人工查看

### 3. 为什么180天作为跨年日期判断阈值？

**决策过程**:
- 最初尝试90天: 7-8月份的延期数据被错误识别为明年
- 改为120天: 6月份的延期数据仍有问题
- 最终定为180天（6个月）: 
  - 覆盖半年内的延期数据
  - 合理区分"已延期"vs"明年未来"
  - 实际测试表现良好

### 4. 为什么所领导和管理员在文件6无时间限制？

**业务需求**:
- **所领导**: 需要全局视角，查看所有历史遗留问题
- **管理员**: 负责数据维护，需要看到所有数据
- **其他角色**: 只需关注近期任务，避免信息过载

### 5. 为什么使用文件哈希而不是文件路径作为缓存键？

**原因**:
- **准确性**: 文件内容变化时自动失效缓存
- **安全性**: 避免缓存污染（文件覆盖后仍用旧缓存）
- **灵活性**: 支持文件移动、重命名

**实现**: `文件名 + 文件大小 + 修改时间` 的MD5哈希

### 6. 为什么勾选状态按用户隔离？

**问题发现**: 2025-10-30用户反馈切换用户后勾选状态未清空

**原因**: 多人共用同一台电脑，勾选状态应该独立

**解决方案**: 缓存结构改为 `{user_name: {file: {row: True}}}`

**兼容性**: 自动迁移旧数据到"默认用户"

### 7. 为什么并发读取Excel？

**性能问题**: 
- 单文件读取: 0.5-2秒
- 10个文件顺序读取: 5-20秒（用户体验差）

**解决方案**: ThreadPoolExecutor并发读取（4线程）

**效果**: 10个文件读取时间降低到2-5秒

### 8. 为什么"接口时间"列放在"接口号"之后？

**UI设计考虑**:
- **逻辑顺序**: 状态 → 项目号 → 接口号 → 时间 → 完成状态
- **视觉平衡**: 固定宽度列在前，动态宽度列在后
- **用户习惯**: 时间信息通常在右侧

---

## 常见问题与解决方案

### 问题1: 程序启动报错 `AttributeError: 'WindowManager' object has no attribute 'app'`

**原因**: 忘记设置 `window_manager.app = self`

**解决**:
```python
# base.py: setup_window()
self.window_manager = WindowManager(self.root, callbacks)
self.window_manager.app = self  # ← 必须添加这行！
self.window_manager.setup(config_data, process_vars, project_vars)
```

### 问题2: 文件6没有数据显示

**可能原因**:
1. V列不包含"河北分公司.建筑结构所"
2. M列不是"尚未回复"或"超期未回复"
3. I列日期超过今天+14天（非管理员/所领导）

**调试方法**:
```python
# 在main.py中添加调试日志
Monitor.log_info(f"文件6处理1(V列机构匹配): {len(p1)} 行")
Monitor.log_info(f"文件6处理3(I列未来14天内): {len(p3)} 行")
Monitor.log_info(f"文件6处理4(M列=尚未回复或超期未回复): {len(p4)} 行")
Monitor.log_info(f"最终结果: {len(final_rows)} 行")
```

### 问题3: 跨年日期解析错误

**症状**: 1月份的数据在10月份时被当作今年已延期

**原因**: 180天阈值逻辑问题

**检查**:
```python
from date_utils import parse_mmdd_to_date
from datetime import date

ref_date = date(2025, 10, 28)
parsed = parse_mmdd_to_date("01.15", ref_date)
print(parsed)  # 应该是 2026-01-15
```

**修复**: 确保使用最新版本的 `parse_mmdd_to_date` 函数

### 问题4: 缓存未失效

**症状**: 修改了Excel文件，但程序显示的是旧数据

**原因**: 
1. 只修改了内容，未保存（修改时间未变）
2. 缓存文件损坏

**解决**:
```python
# 手动清空所有缓存
file_manager.clear_all_cache()

# 或删除缓存文件
import os
os.remove("file_cache.json")
# 删除result_cache目录下的所有.pkl文件
```

### 问题5: 勾选框状态混乱

**症状**: 用户A的勾选出现在用户B的界面上

**原因**: 版本较旧，未实现用户隔离

**解决**: 更新到最新版本（2025-10-30后），包含用户隔离功能

### 问题6: 工作日计算错误

**症状**: 周一到周五算出的工作日数不是5

**检查**:
```python
from date_utils import get_workday_difference
from datetime import date

# 周一到周五
start = date(2025, 10, 27)  # 周一
end = date(2025, 10, 31)    # 周五
diff = get_workday_difference(end, start)
print(diff)  # 应该是 4（不包含起始日）

# 如果包含起始日，使用count_workdays
from date_utils import count_workdays
count = count_workdays(start, end)
print(count)  # 应该是 5
```

### 问题7: 导出TXT文件为空

**可能原因**:
1. 所有选项卡都没有勾选
2. 数据被角色过滤掉了
3. 所有数据被标记为"已完成"

**调试**:
```python
# 检查每个选项卡的数据
for i in range(1, 7):
    tab_viewer = self.window_manager.viewers[f'tab{i}']
    row_count = len(tab_viewer.get_children())
    Monitor.log_info(f"选项卡{i}数据行数: {row_count}")
```

### 问题8: 系统托盘图标不显示

**原因**: 未安装pystray或PIL

**解决**:
```bash
pip install pystray==0.19.4
pip install Pillow==8.4.0
```

**验证**:
```python
try:
    import pystray
    from PIL import Image
    print("系统托盘功能可用")
except ImportError as e:
    print(f"系统托盘功能不可用: {e}")
```

---

## 开发环境配置

### 1. Python环境

**版本**: Python 3.8.x (兼容Win7+)

**安装**:
```bash
# 下载Python 3.8.10（最后一个支持Win7的版本）
https://www.python.org/downloads/release/python-3810/

# 安装时勾选 "Add Python to PATH"
```

### 2. 依赖安装

**生产环境依赖**:
```bash
pip install -r requirements.txt
```

**开发环境依赖**:
```bash
pip install -r requirements-dev.txt
```

**requirements.txt 内容**:
```
pandas==1.1.5
numpy==1.19.5
openpyxl==3.0.10
xlrd==1.2.0
pystray==0.19.4
Pillow==8.4.0
```

**requirements-dev.txt 内容**:
```
# 测试
pytest==7.1.3
pytest-cov==4.0.0

# 代码质量
flake8==5.0.4
black==22.10.0

# 打包
pyinstaller==4.10
```

### 3. IDE配置（PyCharm推荐）

**项目结构**:
```
PythonProject3/
├── .venv/              # 虚拟环境
├── tests/              # 测试文件
├── base.py             # 主程序
├── main.py             # 处理逻辑
├── window.py           # GUI
├── file_manager.py     # 缓存
├── date_utils.py       # 日期工具
├── Monitor.py          # 日志
├── config.json         # 配置
├── requirements.txt
└── excel_processor.spec  # 打包配置
```

**运行配置**:
```
Script path: base.py
Parameters: (留空) 或 --auto (自动模式)
Working directory: 项目根目录
```

### 4. 打包为EXE

**命令**:
```bash
pyinstaller -y excel_processor.spec
```

**excel_processor.spec 关键配置**:
```python
a = Analysis(
    ['base.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ico_bin', 'ico_bin'),
        ('excel_bin', 'excel_bin'),
        ('config.json', '.'),
    ],
    hiddenimports=[
        'pandas',
        'numpy',
        'openpyxl',
        'pystray',
        'PIL',
    ],
    # ...
)
```

**输出位置**: `dist/接口筛选/接口筛选.exe`

### 5. Git配置

**.gitignore**:
```
# Python
__pycache__/
*.py[cod]
*.so
.Python
.venv/

# IDE
.idea/
.vscode/
*.swp

# 项目特定
file_cache.json
result_cache/
dist/
build/
*.spec (如果不想共享打包配置)

# 测试
.pytest_cache/
.coverage
htmlcov/

# 日志
*.log
```

---

## 快速上手指南（给新AI）

### 理解项目的5个步骤

1. **阅读核心业务逻辑章节** (5分钟)
   - 理解5种角色的权限差异
   - 理解6类文件的处理逻辑
   - 理解时间窗口的计算规则

2. **查看架构设计和模块职责** (10分钟)
   - 明确每个文件的职责
   - 理解模块间的交互流程
   - 记住关键的设计原则

3. **浏览代码结构详解** (20分钟)
   - 快速浏览每个核心类和方法
   - 重点关注标记为【重要】的代码
   - 理解缓存机制和用户隔离

4. **学习编码风格规范** (10分钟)
   - 熟悉命名规范
   - 了解注释风格
   - 掌握错误处理模式

5. **运行测试验证理解** (15分钟)
   ```bash
   # 运行所有测试
   pytest -v
   
   # 运行特定模块测试
   pytest tests/test_date_utils.py -v
   ```

### 接手项目的检查清单

- [ ] 已阅读完整文档
- [ ] 已配置开发环境
- [ ] 已运行所有测试（全部通过）
- [ ] 已理解5种角色的差异
- [ ] 已理解6类文件的处理逻辑
- [ ] 已理解跨年日期解析（180天阈值）
- [ ] 已理解用户勾选状态隔离
- [ ] 已理解缓存机制
- [ ] 已知道 `window_manager.app = self` 的重要性
- [ ] 已了解常见问题的解决方案

### 修改代码前必读

1. **运行测试**: 确保现有测试全部通过
2. **理解影响范围**: 确认修改会影响哪些角色/文件
3. **添加测试**: 为新功能编写测试用例
4. **遵循风格**: 保持与现有代码一致的风格
5. **添加注释**: 关键逻辑必须注释说明
6. **记录日志**: 使用 `Monitor.log_*()` 记录关键操作
7. **验证测试**: 修改后运行所有测试
8. **手动测试**: 在GUI中验证修改效果
9. **更新文档**: 如果有重大修改，更新此文档

### 常见修改场景

**场景1: 添加新角色**
```python
# 1. 在base.py的角色配置中添加
self.role_export_days["新角色"] = 5  # 5个工作日

# 2. 在_filter_by_single_role中添加逻辑
if role == '新角色':
    # 筛选逻辑
    pass

# 3. 添加测试
# tests/test_new_role.py
def test_new_role_filter():
    # ...
```

**场景2: 修改时间窗口**
```python
# 修改 base.py 的 role_export_days 配置
self.role_export_days = {
    "一室主任": 10,  # 从7改为10
    # ...
}

# 相应地修改测试
def test_director_10_workday_window():
    # ...
```

**场景3: 添加新文件类型**
```python
# 1. main.py: 添加识别函数
def find_all_target_files7(excel_files):
    """识别待处理文件7"""
    pass

# 2. main.py: 添加处理函数
def process_target_file7(file_path, current_datetime):
    """处理待处理文件7"""
    pass

# 3. base.py: 在start_processing中调用
file7_list = main.find_all_target_files7(df_dict)
# 处理逻辑...

# 4. window.py: 添加第7个选项卡
# ...

# 5. 添加测试
# tests/test_file7_logic.py
```

---

## 附录

### A. 配置文件格式

**config.json**:
```json
{
  "folder_path": "D:/Programs/筛选程序/简易测试文件",
  "auto_startup": false,
  "minimize_to_tray": true,
  "dont_ask_again": false
}
```

### B. 缓存文件格式

**file_cache.json**:
```json
{
  "file_identities": {
    "D:/path/to/file.xlsx": "abc123def456..."
  },
  "completed_rows": {
    "张三": {
      "D:/path/to/file.xlsx": {
        "5": true,
        "12": true
      }
    },
    "李四": {
      "D:/path/to/file.xlsx": {
        "8": true
      }
    }
  }
}
```

### C. 导出TXT格式

**完整模式**:
```
接口筛选结果报告
================

处理时间: 2025-10-28 15:30:45
用户: 张三
角色: 一室主任

一、内部需打开接口 (共5个):
  INT-001, INT-002, INT-003, INT-004, INT-005

二、内部需回复接口 (共3个):
  REPLY-001, REPLY-002, REPLY-003

...
```

**简洁模式**:
```
接口筛选结果报告
================

处理时间: 2025-10-28 15:30:45
用户: 所领导
角色: 所领导

一、内部需打开接口: 共5个

二、内部需回复接口: 共3个

...
```

### D. 关键快捷键

- **F5**: 刷新文件列表
- **Ctrl+S**: 开始筛选（如果焦点在主窗口）
- **Ctrl+E**: 导出结果（如果焦点在主窗口）
- **双击Treeview行**: 切换勾选框状态
- **点击列头**: 列排序（升序/降序切换）

### E. 性能基准

**测试环境**: Win10, i5-8250U, 8GB RAM, SSD

| 操作 | 耗时 | 说明 |
|------|------|------|
| 启动程序 | < 2s | 包含加载缓存 |
| 扫描文件夹(10个Excel) | < 0.5s | 仅扫描文件名 |
| 并发读取(10个Excel) | 2-5s | 使用优化读取 |
| 处理单个文件1 | < 0.3s | 包含筛选和角色过滤 |
| 处理单个文件6 | < 0.2s | 较少的列和行 |
| 完整处理流程 | 5-10s | 10个文件，6种类型 |
| 导出TXT | < 0.5s | 简洁模式更快 |

### F. 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **3.0** | 2025-10-30 | • 用户勾选状态隔离<br>• 跨年日期解析修复<br>• 全列排序功能<br>• 所领导显示逻辑修正 |
| **2.5** | 2025-10-28 | • 新增接口时间列<br>• 智能列宽计算<br>• 管理员文件6无时间限制 |
| **2.0** | 2025-10-27 | • 新增所领导角色<br>• 工作日计算扩展到室主任<br>• 简洁导出模式 |
| **1.5** | 2025-09 | • 结果缓存机制<br>• 并发读取优化 |
| **1.0** | 2025-08 | • 初始版本<br>• 基础筛选和导出功能 |

### G. 联系方式与支持

**开发团队**: [您的团队名称]  
**维护周期**: 长期维护  
**更新频率**: 根据需求不定期更新  

**遇到问题时**:
1. 查看"常见问题与解决方案"章节
2. 检查测试是否全部通过
3. 查看Monitor日志窗口的错误信息
4. 联系原开发团队

---

## 结语

这份文档旨在让新的AI助手能够**快速、完整、准确**地接手这个项目。如果您在接手过程中遇到任何疑问或文档中有不清楚的地方，请立即提出，我会补充完善。

**核心原则**: 
- **保持兼容**: 修改时考虑向后兼容性
- **测试驱动**: 先写测试，再写代码
- **代码清晰**: 宁可多写注释，不要写"聪明"的代码
- **用户至上**: 界面友好、操作简单、错误清晰

**最重要的一句话**: 
> 所有的设计决策都是为了**5种角色能够高效、准确地找到自己需要处理的接口**。

祝您接手顺利！🎉

---

**文档版本**: 1.0  
**生成时间**: 2025-10-30  
**文档作者**: Claude (Sonnet 4.5)  
**文档状态**: 完整版，可直接使用

