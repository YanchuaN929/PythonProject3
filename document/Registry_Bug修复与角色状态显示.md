# Registry模块 - Bug修复与基于角色的状态显示

## 📅 更新时间
**2025-11-05**

---

## 🎯 本次修复与新增功能

### ✅ 问题1：Bug修复 - 只有第一行显示状态

**问题描述**：
- 用户有4个11.7号的任务
- 只有第一行显示"📌 待完成"
- 后面3行是空的或只有"⚠️"延期标记

**根本原因**：
`window.py`中的状态查询逻辑错误地使用了 `source_files[idx]` 来映射源文件。但是：
- `source_files` 是一个文件路径列表（如 `['file1.xlsx', 'file2.xlsx', 'file3.xlsx']`）
- `display_df` 可能有100行数据
- 无法通过索引直接映射

**修复方案**：
```python
# 之前的错误逻辑
source_file = source_files[idx] if idx < len(source_files) else ""

# 修复后的正确逻辑
for source_file in source_files:
    # 对每个接口号尝试所有源文件
    task_key = {
        'file_type': file_type,
        'project_id': project_id,
        'interface_id': interface_id,
        'source_file': source_file,
        'row_index': row_index
    }
    task_keys.append((idx, task_key))
```

**修改文件**：
- `window.py` 第528-573行

---

### ✅ 功能2：角色区分显示 - 设计人员 vs 上级

**需求描述**：
- **设计人员** 看到自己的任务：显示 **"📌 待完成"**
- **上级角色**（室主任、接口工程师）看到设计人员的任务：显示 **"📌 待设计人员完成"**

**实现逻辑**：
```python
# registry/service.py 第250-263行
if display_status == '待完成':
    if is_superior and not is_designer:
        # 纯上级角色 → "待设计人员完成"
        display_text = '待设计人员完成'
    elif is_designer and is_superior:
        # 重叠角色 → "待完成"
        display_text = '待完成'
    else:
        # 设计人员或其他角色 → "待完成"
        display_text = '待完成'
```

**角色判断逻辑**：
```python
# registry/service.py 第208-216行
is_designer = False
is_superior = False
if current_user_roles:
    for role in current_user_roles:
        if "设计人员" in role:
            is_designer = True
        if any(keyword in role for keyword in ['所领导', '室主任', '接口工程师']):
            is_superior = True
```

**修改文件**：
- `registry/service.py` 第188-286行（`get_display_status` 函数）
- `registry/hooks.py` 第37-66行（参数改为用户角色列表）
- `window.py` 第557-559行（传递用户角色）

---

### ✅ 功能3：角色重叠处理

**需求描述**：
当一个用户同时是"设计人员"和"1818接口工程师"，且该任务对两个角色都有职责时，显示 **"📌 待完成"** 即可（不显示"待设计人员完成"）。

**实现逻辑**：
```python
# registry/service.py 第258-260行
elif is_designer and is_superior:
    # 重叠角色：显示"待完成"
    display_text = '待完成'
```

**修改文件**：
- `registry/service.py` 第188-286行

---

## 📊 显示状态对照表

### 未完成任务（status=open, display_status='待完成'）

| 用户角色 | 显示文本 | Emoji |
|---------|---------|-------|
| **设计人员** | 待完成 | 📌 |
| **室主任** | 待设计人员完成 | 📌 |
| **接口工程师** | 待设计人员完成 | 📌 |
| **设计人员 + 接口工程师** | 待完成 | 📌 |
| **所领导** | 待设计人员完成 | 📌 |

### 已完成未确认任务（status=completed）

| 任务类型 | 所有角色显示 | Emoji |
|---------|-------------|-------|
| **无指派任务** | 待上级确认 | ⏳ |
| **有指派任务** | 待指派人确认 | ⏳ |

### 已确认任务（status=confirmed）

| 所有角色 | 显示 |
|---------|------|
| **所有角色** | （不显示状态） |

---

## 🔧 技术实现细节

### 1. 源文件查找策略

**问题**：DataFrame中每行数据来自哪个源文件？

**解决方案**：遍历所有源文件，尝试构造task_id并查询

```python
# window.py 第538-550行
for source_file in source_files:
    task_key = {
        'file_type': file_type,
        'project_id': project_id,
        'interface_id': interface_id,
        'source_file': source_file,
        'row_index': row_index
    }
    task_keys.append((idx, task_key))
```

**优化**：
- 使用字典 `registry_status_map[df_idx]` 缓存第一个匹配的状态
- 避免重复覆盖同一行的状态

### 2. 用户角色传递链

```
base.py (user_roles)
    ↓
window_manager.display_excel_data (current_user_roles)
    ↓
registry_hooks.get_display_status (current_user_roles_str: "设计人员,1818接口工程师")
    ↓
registry.service.get_display_status (current_user_roles: ["设计人员", "1818接口工程师"])
    ↓
角色判断逻辑 (is_designer, is_superior)
    ↓
状态文本选择 (待完成 vs 待设计人员完成)
```

### 3. 角色判断关键字

| 角色类型 | 关键字 |
|---------|--------|
| **设计人员** | "设计人员" |
| **上级角色** | "所领导" / "室主任" / "接口工程师" |

**重叠判断**：
```python
if is_designer and is_superior:
    # 用户同时具备两种角色
```

---

## ✅ 测试覆盖

### 新增测试文件

**`tests/test_registry_role_based_status.py`** (5个测试用例)

1. ✅ `test_designer_sees_pending` - 设计人员看到"待完成"
2. ✅ `test_superior_sees_pending_by_designer` - 上级看到"待设计人员完成"
3. ✅ `test_overlapping_role_sees_pending` - 重叠角色看到"待完成"
4. ✅ `test_completed_status_unchanged_by_role` - 待确认状态不受角色影响
5. ✅ `test_multiple_files_status_query` - 多文件查询逻辑测试

### 测试结果

```
28 passed in 5.20s

测试文件：
- tests/test_registry_all_tasks_pending.py (5个测试)
- tests/test_registry_connection.py (7个测试)
- tests/test_registry_status_reminder.py (5个测试)
- tests/test_registry_basic.py (6个测试)
- tests/test_registry_role_based_status.py (5个测试) ⭐ 新增
```

---

## 📋 修改文件清单

| 文件 | 修改内容 | 行数变化 |
|-----|---------|---------|
| `window.py` | Bug修复：遍历源文件查询状态；传递用户角色 | ~30行修改 |
| `registry/hooks.py` | 修改参数为角色列表字符串 | ~15行修改 |
| `registry/service.py` | 实现基于角色的状态显示逻辑 | ~50行修改 |
| `registry/util.py` | 添加display_status初始值 | +1行 |
| `tests/test_registry_role_based_status.py` | 新增测试文件 | +236行新增 |

---

## 🎯 功能验证清单

### ✅ Bug修复验证

- [x] 多行数据都能显示状态（不再只有第一行）
- [x] 4个11.7号任务都显示"待完成"
- [x] 遍历所有源文件正确查找任务

### ✅ 角色区分验证

- [x] 设计人员看到"待完成"
- [x] 室主任看到"待设计人员完成"
- [x] 接口工程师看到"待设计人员完成"
- [x] 待确认状态对所有角色一致

### ✅ 角色重叠验证

- [x] 设计人员+接口工程师看到"待完成"
- [x] 不显示"待设计人员完成"

---

## 🚀 使用指南

### 场景1：设计人员查看任务

```python
# 登录用户：张三（设计人员）
# 看到4个任务：
# - 任务1: 📌 待完成
# - 任务2: 📌 待完成
# - 任务3: 📌 待完成
# - 任务4: 📌 待完成
```

### 场景2：室主任查看任务

```python
# 登录用户：李主任（结构一室主任）
# 看到4个任务：
# - 任务1: 📌 待设计人员完成
# - 任务2: 📌 待设计人员完成
# - 任务3: 📌 待设计人员完成
# - 任务4: 📌 待设计人员完成
```

### 场景3：重叠角色查看任务

```python
# 登录用户：王工（设计人员 + 1818接口工程师）
# 看到4个任务：
# - 任务1: 📌 待完成  # 自己职责内的任务
# - 任务2: 📌 待完成
# - 任务3: 📌 待完成
# - 任务4: 📌 待完成
```

---

## 📝 注意事项

1. **源文件查询性能**：
   - 每行数据会查询N个源文件（N为文件数量）
   - 如果有100行数据、3个源文件，会构造300个task_key
   - 但由于使用批量查询，性能影响可控

2. **角色关键字匹配**：
   - "设计人员" 精确匹配
   - "室主任" / "接口工程师" 模糊匹配（包含关键字即可）
   - 例如："结构一室主任" 会被识别为上级角色

3. **待确认状态不受角色影响**：
   - 无论是设计人员还是上级角色
   - 都看到相同的"⏳ 待上级确认"或"⏳ 待指派人确认"
   - 确保状态一致性

---

## 🔄 向后兼容性

✅ **完全向后兼容**

- 旧数据库会通过`migrate_if_needed`自动添加`display_status`列
- 未传递用户角色时，默认显示原始状态文本
- 所有现有功能保持不变

---

## 📌 后续优化建议

### 性能优化（可选）

如果源文件数量很多（>10个），可以考虑：
1. 在DataFrame中添加"源文件"列，避免遍历
2. 使用文件hash映射，快速定位源文件

### 功能扩展（可选）

1. 支持更多角色关键字配置化
2. 支持自定义状态文本模板
3. 支持角色权限级别（优先级）

---

**文档版本**: v1.0  
**对应代码版本**: Registry阶段1完成 + Bug修复 + 角色状态显示  
**测试覆盖**: 28个测试用例全部通过 ✅

