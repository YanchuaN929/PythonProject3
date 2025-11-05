# Excel列与数据库字段映射关系说明

## 📋 概述

本文档详细说明了Excel文件中读取的关键数据与Registry数据库字段之间的映射关系。

---

## 1️⃣ Excel -> 数据库：已实现的映射

### 核心标识字段

| Excel列 | 数据库字段 | 说明 | 代码位置 |
|---------|-----------|------|----------|
| **原始行号** | `row_index` | 用于唯一标识Excel行 | `registry/util.py::build_task_key_from_row` |
| **项目号** | `project_id` | 项目标识（1818/1907/1916等） | `registry/util.py::build_task_key_from_row` |
| **接口号** | `interface_id` | 接口唯一标识 | `registry/util.py::build_task_key_from_row` |

### 业务数据字段

| Excel列 | 数据库字段 | 说明 | 代码位置 |
|---------|-----------|------|----------|
| **部门** | `department` | 科室/部门信息 | `registry/util.py::build_task_fields_from_row` |
| **接口时间** | `interface_time` | 接口截止时间 | `registry/util.py::build_task_fields_from_row` |
| **角色来源** | `role` | 角色标识 | `registry/util.py::build_task_fields_from_row` |
| **责任人** | `responsible_person` | **【本次新增】**任务负责人 | `registry/util.py::build_task_fields_from_row` |

### 状态相关字段

| Excel列 | 数据库字段 | 说明 | 代码位置 |
|---------|-----------|------|----------|
| **状态** | `display_status` | Registry计算的显示状态 | `registry/service.py::get_display_status` |

---

## 2️⃣ 数据库独有字段（非Excel直接来源）

这些字段由程序自动生成和管理：

| 数据库字段 | 类型 | 说明 | 来源 |
|-----------|------|------|------|
| `id` | TEXT | 任务唯一ID | 由`file_type+project_id+interface_id+source_file+row_index`生成 |
| `file_type` | INTEGER | 文件类型（1-6） | 文件处理时自动识别 |
| `source_file` | TEXT | 源文件路径 | 文件处理时记录 |
| `status` | TEXT | 任务状态 | open/assigned/completed/confirmed/archived |
| `completed_at` | TEXT | 完成时间 | 设计人员写回文单号时记录 |
| `confirmed_at` | TEXT | 确认时间 | 上级角色确认时记录 |
| `assigned_at` | TEXT | 指派时间 | 指派功能触发时记录 |
| `assigned_by` | TEXT | 指派人 | 指派功能记录 |
| `confirmed_by` | TEXT | 确认人 | 上级确认功能记录 |
| `first_seen_at` | TEXT | 首次扫描时间 | 任务首次被处理时 |
| `last_seen_at` | TEXT | 最后扫描时间 | 每次重新扫描时更新 |
| `missing_since` | TEXT | 消失标记时间 | 归档功能使用（未来实现） |
| `archive_reason` | TEXT | 归档原因 | 归档功能使用（未来实现） |

---

## 3️⃣ 数据库 -> Excel：回写路径

某些数据库字段会回写到Excel：

| 数据库字段 | Excel效果 | 说明 | 代码位置 |
|-----------|-----------|------|----------|
| `responsible_person` | **责任人**列 | 指派任务时写入 | `distribution.py::save_assignments_batch` |
| `completed_at` | 触发**已完成**勾选 | 写回文单号时触发 | `input_handler.py::write_response_to_excel` |

---

## 4️⃣ 不需要映射的Excel数据

### 回文单号列

- **Excel列**：回文单号（仅file1/2/3/4有此列）
- **数据库**：无对应字段
- **原因**：仅用于触发任务完成事件，不存储单号内容本身
- **效果**：写入回文单号 → 触发 `status='completed'` + 记录 `completed_at`

### 已完成勾选框

- **Excel列**：UI勾选框（不在Excel实际列中）
- **数据库**：无对应字段
- **原因**：这是UI状态，按用户维度存储在`file_cache.json`中
- **说明**：
  - 不同用户看到的勾选状态不同（按用户姓名隔离）
  - Registry通过`completed_at`间接反映完成状态

---

## 5️⃣ 责任人字段的重要性【本次新增】

### 修复前的问题

```
Excel: 责任人="张三"（手动填写）
数据库: responsible_person=NULL（未同步）
上级角色看到: "❗ 请指派"（错误！）
```

### 修复后的行为

```
Excel: 责任人="张三"（手动填写或指派功能写入）
数据库: responsible_person="张三"（自动同步）
上级角色看到: "📌 待设计人员完成"（正确！）
```

### 智能同步逻辑

```sql
responsible_person = CASE
    WHEN assigned_by IS NOT NULL THEN responsible_person  -- 保留指派的值
    ELSE COALESCE(excluded.responsible_person, responsible_person)  -- 使用Excel的值
END
```

**保护机制**：
- ✅ 通过指派功能设置的责任人（有`assigned_by`）→ 永久保留，不被Excel覆盖
- ✅ Excel中手动填写的责任人（无`assigned_by`）→ 自动同步到数据库

---

## 6️⃣ 数据流图

```
┌─────────────────────────────────────────────────────────────┐
│                     Excel文件（源数据）                        │
│  ┌───────────┬──────────┬──────────┬────────┬──────────┐   │
│  │ 原始行号  │  项目号   │  接口号   │  部门  │  责任人   │   │
│  │    100   │   1818   │ ABC-001  │ 一室   │  张三     │   │
│  └───────────┴──────────┴──────────┴────────┴──────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓ 读取
┌─────────────────────────────────────────────────────────────┐
│              registry/util.py（数据提取）                     │
│  • build_task_key_from_row()   - 提取标识字段               │
│  • build_task_fields_from_row() - 提取业务字段【含责任人】   │
└─────────────────────────────────────────────────────────────┘
                           ↓ 批量写入
┌─────────────────────────────────────────────────────────────┐
│           registry.db（Registry数据库）                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ id, file_type, project_id, interface_id, ...       │   │
│  │ row_index, department, interface_time, role,       │   │
│  │ responsible_person【新增】, display_status, ...      │   │
│  │ assigned_by, assigned_at, status, completed_at     │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓ 状态计算
┌─────────────────────────────────────────────────────────────┐
│          registry/service.py（状态逻辑）                      │
│  • get_display_status() - 根据角色和任务状态计算显示文本     │
│    - 检查responsible_person：                               │
│      • 有值 → "📌 待设计人员完成"（上级）/"📌 待完成"（设计）│
│      • 无值 → "❗ 请指派"（上级）                            │
└─────────────────────────────────────────────────────────────┘
                           ↓ 回写
┌─────────────────────────────────────────────────────────────┐
│              distribution.py（指派功能）                      │
│  • save_assignments_batch() - 写入Excel责任人列             │
│  • 同时更新数据库：assigned_by + responsible_person          │
└─────────────────────────────────────────────────────────────┘
                           ↓ 显示
┌─────────────────────────────────────────────────────────────┐
│                window.py（主显示界面）                        │
│  ┌───────┬─────────┬──────────┬──────┬──────────────────┐ │
│  │ 项目  │ 接口号  │  责任人  │ 部门 │      状态        │ │
│  │ 1818 │ ABC-001 │  张三    │ 一室 │ 📌 待设计人员完成│ │
│  └───────┴─────────┴──────────┴──────┴──────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 7️⃣ 完整的数据库Schema

```sql
CREATE TABLE tasks (
    -- 核心标识（来自Excel）
    id TEXT PRIMARY KEY,              -- 生成的唯一ID
    file_type INTEGER NOT NULL,       -- 文件类型（1-6）
    project_id TEXT NOT NULL,         -- Excel: 项目号
    interface_id TEXT NOT NULL,       -- Excel: 接口号
    source_file TEXT NOT NULL,        -- 源文件路径
    row_index INTEGER NOT NULL,       -- Excel: 原始行号
    
    -- 业务数据（来自Excel）
    department TEXT DEFAULT '',       -- Excel: 部门
    interface_time TEXT DEFAULT '',   -- Excel: 接口时间
    role TEXT DEFAULT '',             -- Excel: 角色来源
    responsible_person TEXT DEFAULT NULL,  -- Excel: 责任人【新增】
    
    -- 任务状态（程序管理）
    status TEXT NOT NULL DEFAULT 'open',  -- open/assigned/completed/confirmed/archived
    display_status TEXT DEFAULT NULL,     -- 显示状态（待完成/待上级确认等）
    
    -- 时间戳（程序记录）
    completed_at TEXT NULL,           -- 完成时间
    confirmed_at TEXT NULL,           -- 确认时间
    assigned_at TEXT NULL,            -- 指派时间
    first_seen_at TEXT NOT NULL,      -- 首次扫描
    last_seen_at TEXT NOT NULL,       -- 最后扫描
    missing_since TEXT NULL,          -- 消失标记（归档用）
    
    -- 协作信息（程序记录）
    assigned_by TEXT DEFAULT NULL,    -- 指派人
    confirmed_by TEXT DEFAULT NULL,   -- 确认人
    
    -- 归档信息（归档功能用）
    archive_reason TEXT NULL,         -- 归档原因
    
    -- 唯一约束
    UNIQUE(file_type, project_id, interface_id, source_file, row_index)
);
```

---

## 8️⃣ 验证结论

### ✅ 已实现的映射（7个核心字段）

1. ✅ **原始行号** → `row_index`
2. ✅ **项目号** → `project_id`
3. ✅ **接口号** → `interface_id`
4. ✅ **部门** → `department`
5. ✅ **接口时间** → `interface_time`
6. ✅ **角色来源** → `role`
7. ✅ **责任人** → `responsible_person` **【本次新增】**

### ⭕ 不需要映射的数据

- **回文单号**：触发状态变化，不存储内容
- **已完成勾选框**：UI状态，存储在`file_cache.json`

### 📊 数据覆盖率

- **核心业务数据**：100%映射 ✅
- **状态提醒功能**：完全支持 ✅
- **协作工作流**：完全支持 ✅
- **历史追溯**：完全支持 ✅

---

## 9️⃣ 建议

### 当前状态

当前映射已覆盖所有核心业务数据，满足：
- ✅ 任务跟踪
- ✅ 状态提醒
- ✅ 角色解耦
- ✅ 指派功能
- ✅ 确认功能

### 未来扩展

如果Excel中有以下列，可以考虑添加映射：
- **备注/说明**：添加`notes`字段
- **优先级**：添加`priority`字段
- **截止日期**：已有`interface_time`，可扩展为标准日期类型
- **附件路径**：添加`attachments`字段

但目前这些不是必需的，现有映射已完全满足业务需求。

---

## 🔟 测试验证

### 测试脚本

- ✅ `test_excel_responsible_sync.py` - 验证Excel责任人同步
- ✅ `check_excel_db_mapping.py` - 验证映射关系
- ✅ `tests/test_registry_*.py` - 35个Registry单元测试

### 验证结果

```
[TEST 1] Excel responsible_person synced to DB: ✅ PASSED
[TEST 2] Assigned tasks not overwritten: ✅ PASSED
[Integration] All 35 Registry tests: ✅ PASSED
```

---

**文档创建时间**：2025-11-05  
**最后更新**：修复责任人字段映射，解决"请指派"显示问题  
**相关文档**：
- `document/指派功能优化与问题修复总结.md`
- `document/Registry数据库位置说明.md`
- `document/Registry_下一阶段任务清单.md`

