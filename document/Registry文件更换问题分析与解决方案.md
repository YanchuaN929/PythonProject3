# Registry文件更换问题分析与解决方案

## 📋 问题描述

### 真实使用场景

用户描述的实际使用情况：
- **每周更新**：6个项目 × 6个文件类型 = 36个源文件
- **文件名变化**：包含日期信息
  - 旧：`2016按项目导出IDI手册2025-08-01.xlsx`
  - 新：`2016按项目导出IDI手册2025-08-08.xlsx`
- **数据变化**：
  - 有些接口完成了
  - 有些接口新增了
  - 有些接口信息更新了

### 当前问题

**表现**：
- 用户手动更换了源文件
- 主显示窗口仍然显示旧的Registry记录
- 新的文件数据无法匹配旧的Registry记录

**根本原因**：

```
任务ID = hash(file_type + project_id + interface_id + source_file + row_index)
```

关键字段`source_file`：
- 存储的是文件名（basename）
- 文件名变化 → 任务ID变化
- 旧任务ID无法匹配新文件

---

## 🔍 深入分析

### 任务ID构造逻辑

**位置**：`registry/util.py::make_task_id`

```python
def make_task_id(file_type, project_id, interface_id, source_file, row_index):
    source_basename = os.path.basename(source_file)
    key_str = f"{file_type}|{project_id}|{interface_id}|{source_basename}|{row_index}"
    return hashlib.sha1(key_str.encode()).hexdigest()
```

**示例**：
```
旧文件：2016按项目导出IDI手册2025-08-01.xlsx
任务ID：hash(1|2016|S-SA-001|2016按项目导出IDI手册2025-08-01.xlsx|89)
      = abc123...

新文件：2016按项目导出IDI手册2025-08-08.xlsx
任务ID：hash(1|2016|S-SA-001|2016按项目导出IDI手册2025-08-08.xlsx|89)
      = def456...  ← 完全不同的ID！
```

**问题**：
- 即使是同一个接口（项目号+接口号相同）
- 只要文件名或行号变化，任务ID就完全不同
- 无法将旧任务的状态（待审查、已指派等）迁移到新任务

---

## ✅ 解决方案

### 方案A：手动清理旧任务（短期，立即可用）⭐

**实现**：提供清理工具，清除不再存在于源文件的任务

**工具1**：清除指定源文件的所有任务
```python
def clean_tasks_by_source_file(source_file_pattern):
    """清除指定源文件的所有任务"""
    conn = get_connection(db_path, wal)
    conn.execute(
        "DELETE FROM tasks WHERE source_file LIKE ?",
        (f"%{source_file_pattern}%",)
    )
    conn.commit()
```

**工具2**：清除超过N天未见的任务
```python
def clean_old_tasks(days=7):
    """清除超过N天未见的任务"""
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    conn = get_connection(db_path, wal)
    conn.execute(
        "DELETE FROM tasks WHERE last_seen_at < ? AND status != 'confirmed'",
        (cutoff_date,)
    )
    conn.commit()
```

**使用方法**：
```bash
# 每周更新文件前，清除旧任务
python scripts/db_tools/clean_old_tasks.py --days 7
```

---

### 方案B：实现归档逻辑（中期，推荐）✅

**核心思想**：
- 每次扫描时，标记`last_seen_at`
- 如果任务连续7天未见 → 自动归档
- 归档的任务不再显示，但保留记录

**实现**：完善`finalize_scan`函数（已有骨架）

**流程**：
```
每次处理完成后
    ↓
调用finalize_scan()
    ↓
查询所有last_seen_at不是今天的任务
    ↓
如果missing_since为空，标记missing_since=今天
    ↓
如果missing_since > 7天，归档任务
```

**优点**：
- ✅ 自动化，无需手动清理
- ✅ 保留历史记录（归档而非删除）
- ✅ 可配置天数阈值

**预计工作量**：2-3小时

---

### 方案C：改进任务ID设计（长期，复杂）

**思路**：任务ID不依赖`source_file`和`row_index`

**新的任务ID**：
```
任务ID = hash(file_type + project_id + interface_id)
```

**优点**：
- ✅ 文件名变化不影响任务ID
- ✅ 行号变化不影响任务ID
- ✅ 任务状态可以跨文件保留

**缺点**：
- ❌ 同一个接口在不同文件中会冲突
- ❌ 同一个接口在同一文件的不同行会冲突
- ❌ 需要大量重构现有代码

**结论**：不推荐（破坏性太大）

---

### 方案D：智能匹配机制（中长期，理想）

**思路**：
1. 主键仍然是完整的任务ID（含文件名）
2. 添加辅助匹配逻辑：
   - 如果完整ID匹配不上
   - 尝试匹配`file_type + project_id + interface_id`
   - 如果只有一个匹配，迁移状态

**伪代码**：
```python
def find_task_smart(file_type, project_id, interface_id, source_file, row_index):
    # 1. 精确匹配
    tid = make_task_id(file_type, project_id, interface_id, source_file, row_index)
    task = db.query("SELECT * FROM tasks WHERE id = ?", tid)
    if task:
        return task
    
    # 2. 模糊匹配（忽略source_file和row_index）
    similar_tasks = db.query(
        "SELECT * FROM tasks WHERE file_type = ? AND project_id = ? AND interface_id = ?",
        (file_type, project_id, interface_id)
    )
    
    if len(similar_tasks) == 1:
        # 只有一个匹配，可能是同一个接口，迁移状态
        old_task = similar_tasks[0]
        # 迁移状态到新任务...
```

**优点**：
- ✅ 兼容文件名变化
- ✅ 保留任务状态
- ✅ 向后兼容

**缺点**：
- ❌ 逻辑复杂
- ❌ 可能出现误匹配

---

## 🎯 推荐方案

### 立即执行（本次对话）：

**方案A-1：提供手动清理工具**

创建脚本：`scripts/db_tools/clean_registry_tasks.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry数据库清理工具

功能：
1. 清除超过N天未见的任务
2. 清除指定源文件的所有任务
3. 显示统计信息
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from registry.db import get_connection
from registry.config import load_config
from datetime import datetime, timedelta
import sqlite3

def clean_old_tasks(days=7):
    """清除超过N天未见的任务"""
    cfg = load_config()
    db_path = cfg.get('registry_db_path')
    
    if not db_path:
        print("[错误] 未配置数据库路径")
        return
    
    if not os.path.exists(db_path):
        print(f"[错误] 数据库不存在: {db_path}")
        return
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    conn = get_connection(db_path, True)
    
    # 查询将被清除的任务数量
    cursor = conn.execute("""
        SELECT COUNT(*) FROM tasks 
        WHERE last_seen_at < ? 
          AND status != 'confirmed'
    """, (cutoff_date,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(f"[信息] 没有超过{days}天未见的任务")
        return
    
    print(f"[警告] 将清除{count}个超过{days}天未见的任务")
    confirm = input("确认清除？(yes/no): ")
    
    if confirm.lower() == 'yes':
        conn.execute("""
            DELETE FROM tasks 
            WHERE last_seen_at < ? 
              AND status != 'confirmed'
        """, (cutoff_date,))
        conn.commit()
        print(f"[成功] 已清除{count}个任务")
    else:
        print("[取消] 操作已取消")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='清理Registry数据库中的旧任务')
    parser.add_argument('--days', type=int, default=7, help='清除超过N天未见的任务（默认7天）')
    args = parser.parse_args()
    
    clean_old_tasks(args.days)
```

**使用方法**：
```bash
# 清除超过7天未见的任务
python scripts/db_tools/clean_registry_tasks.py --days 7

# 清除超过30天未见的任务
python scripts/db_tools/clean_registry_tasks.py --days 30
```

---

### 下一阶段实施：

**方案B：实现自动归档逻辑**

这是`document/Registry_下一阶段任务清单.md`中的**优先级2任务**。

**实现步骤**：
1. 完善`finalize_scan`函数
2. 在处理完成后调用
3. 自动标记和归档旧任务

**预计工作量**：4-5万Token

---

## 🔧 临时解决方案

### 当前您可以做的

**选项1：点击"清除缓存"**
- 会清除所有缓存和勾选状态
- 但**不会清除**Registry数据库
- 旧的Registry记录仍然存在

**选项2：手动删除Registry数据库**
```bash
del "D:/Programs/接口筛选/测试文件/.registry/registry.db"
```
- 会删除所有Registry数据
- 下次运行时重新创建
- **警告**：会丢失所有历史记录

**选项3：等待自动归档功能**
- 我可以立即实现`finalize_scan`
- 每次处理时自动清理7天未见的任务
- 预计30-40分钟完成

---

## ✅ 已修复的问题

1. ✅ Registry查询失败（pending_rows未定义）
2. ✅ 删除"4444数据转换"输出
3. ✅ 删除"处理3：第XX行符合条件"输出
4. ✅ 简化处理步骤输出（从5行减少为1行）
5. ✅ 删除pandas索引调试输出

---

## ❓ 您的选择

关于问题4（Registry文件更换适应），您希望：

**选项A**：立即实现自动归档逻辑（`finalize_scan`）
- 优点：一劳永逸，自动化
- 预计时间：30-40分钟

**选项B**：使用手动清理工具
- 优点：快速简单
- 缺点：每周需要手动执行一次

**选项C**：暂时不处理，先验证当前功能
- 先确保写回文单号后任务正确显示
- 再处理文件更换问题

**请告诉我您的选择！** 🙏

---

**报告时间**：2025-11-05  
**Token使用**：约97K/1000K  
**当前状态**：等待用户决策

