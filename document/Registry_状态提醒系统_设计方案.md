# Registry状态提醒系统 - 完整设计方案

## 📋 需求分析总结

### 1. 设计人员提醒
- 任务完成后(completed) → 显示"待上级确认"
- 导出结果弹窗不包含"待上级确认"的任务
- 被确认后(confirmed) → 不再提醒

### 2. 上级角色提醒
- 提醒对象：接口工程师 + 室主任（根据接口责任）
- 不提醒所领导
- 任意一人确认即可

### 3. 指派任务跟踪
- 记录：指派人(assigned_by) + 指派时间(assigned_at)
- 跟踪：设计人员完成 → 指派人确认
- 确认后：不再提醒

### 4. UI设计
- 不用GUI弹窗
- 使用状态列（当前：空值/感叹号）

### 5. 状态同步DB
- display_status字段存入数据库

### 6. 角色解耦
- 重叠角色独立处理

---

## 🔍 当前代码状态分析

### Tasks表现有字段
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    file_type INTEGER,
    project_id TEXT,
    interface_id TEXT,
    source_file TEXT,
    row_index INTEGER,
    department TEXT,           -- 科室
    interface_time TEXT,       -- 接口时间
    role TEXT,                 -- 角色（设计人员/接口工程师）
    status TEXT,               -- open/completed/confirmed/archived
    completed_at TEXT,         -- 完成时间
    confirmed_at TEXT,         -- 确认时间
    first_seen_at TEXT,
    last_seen_at TEXT,
    missing_since TEXT,
    archive_reason TEXT
);
```

### Events表
- ASSIGNED事件已定义，但未实际使用

### 指派任务功能
- `distribution.py` 已实现
- `save_assignment()` 将姓名写入Excel
- 但未与Registry集成

---

## ✅ 设计方案

### 一、数据库扩展

#### 1.1 Tasks表新增字段
```sql
ALTER TABLE tasks ADD COLUMN assigned_by TEXT DEFAULT NULL;     -- 指派人姓名
ALTER TABLE tasks ADD COLUMN assigned_at TEXT DEFAULT NULL;     -- 指派时间
ALTER TABLE tasks ADD COLUMN display_status TEXT DEFAULT NULL;  -- 显示状态
ALTER TABLE tasks ADD COLUMN confirmed_by TEXT DEFAULT NULL;    -- 确认人姓名
ALTER TABLE tasks ADD COLUMN responsible_person TEXT DEFAULT NULL; -- 责任人姓名
```

#### 1.2 字段说明

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `assigned_by` | TEXT | 指派人 | "王工（1818接口工程师）" |
| `assigned_at` | TEXT | 指派时间 | "2025-11-03T10:30:00" |
| `display_status` | TEXT | 显示状态 | "待上级确认"/"待设计人员完成"/"待指派人确认" |
| `confirmed_by` | TEXT | 确认人 | "李主任（一室主任）" |
| `responsible_person` | TEXT | 责任人 | "张敬武" |

---

### 二、状态流转逻辑

#### 2.1 任务生命周期

```
1. 任务创建 (on_process_done)
   status: open
   display_status: NULL

2. 指派任务 (on_assigned)
   status: open
   display_status: "待设计人员完成"
   assigned_by: "王工（1818接口工程师）"
   assigned_at: "2025-11-03T10:30:00"
   responsible_person: "张敬武"

3. 设计人员完成 (on_response_written)
   status: completed
   display_status: "待上级确认" 或 "待指派人确认"（如果有指派）
   completed_at: "2025-11-03T11:00:00"

4. 上级确认 (on_confirmed_by_superior)
   status: confirmed
   display_status: NULL（不再提醒）
   confirmed_at: "2025-11-03T14:00:00"
   confirmed_by: "李主任（一室主任）"

5. 归档 (finalize_scan)
   status: archived
   display_status: NULL
```

#### 2.2 状态显示规则

| Registry Status | display_status | 显示条件 | 显示给谁 |
|-----------------|----------------|----------|----------|
| `open` | NULL | 未指派 | 所有人 |
| `open` | "待设计人员完成" | 已指派，设计人员未完成 | 设计人员+指派人 |
| `completed` | "待上级确认" | 已完成，无指派人 | 上级角色（接口工程师+室主任） |
| `completed` | "待指派人确认" | 已完成，有指派人 | 指派人 |
| `confirmed` | NULL | 已确认 | 不提醒 |
| `archived` | NULL | 已归档 | 不显示 |

---

### 三、角色责任判断逻辑

#### 3.1 上级角色判断（需确认任务）

```python
def get_superior_roles_for_task(task):
    """
    获取任务需要哪些上级角色确认
    
    返回: ["2016接口工程师", "一室主任"]
    """
    roles = []
    
    # 1. 项目接口工程师
    project_id = task['project_id']
    if project_id:
        roles.append(f"{project_id}接口工程师")
    
    # 2. 科室主任
    department = task['department']  # 如："结构一室"
    if department:
        if '一室' in department:
            roles.append("一室主任")
        elif '二室' in department:
            roles.append("二室主任")
        elif '建筑总图' in department:
            roles.append("建筑总图室主任")
    
    return roles
```

#### 3.2 当前用户是否负责该任务

```python
def is_user_responsible_for_task(user_roles, task):
    """
    判断当前用户是否负责该任务的确认
    
    规则：
    1. 如果有指派人 → 只有指派人负责
    2. 如果无指派人 → 所有上级角色都负责
    """
    # 情况1：有指派人
    if task['assigned_by']:
        # 提取指派人姓名（去除角色后缀）
        assigned_by_name = extract_name(task['assigned_by'])
        current_user_name = get_current_user_name()
        return assigned_by_name == current_user_name
    
    # 情况2：无指派人 → 检查用户是否在负责角色列表中
    required_roles = get_superior_roles_for_task(task)
    return any(role in user_roles for role in required_roles)
```

---

### 四、集成点修改

#### 4.1 指派任务钩子（新增）

**位置**：`registry/hooks.py`

```python
def on_assigned(
    file_type: int,
    file_path: str,
    row_index: int,
    interface_id: str,
    project_id: str,
    assigned_by: str,    # 指派人（含角色）
    assigned_to: str,    # 责任人姓名
    now: Optional[datetime] = None
) -> None:
    """
    任务指派钩子
    
    当接口工程师/室主任指派任务时调用
    """
    # 更新任务：
    # - display_status = "待设计人员完成"
    # - assigned_by = assigned_by
    # - assigned_at = now
    # - responsible_person = assigned_to
    
    # 写入ASSIGNED事件
```

**调用位置**：`distribution.py` 的 `save_assignment()`

#### 4.2 完成任务钩子（修改）

**位置**：`registry/hooks.py` 的 `on_response_written()`

```python
# 修改逻辑：
if task['assigned_by']:
    display_status = "待指派人确认"
else:
    display_status = "待上级确认"

# 更新任务
upsert_task(..., {
    'display_status': display_status
})
```

#### 4.3 确认任务钩子（修改）

**位置**：`registry/hooks.py` 的 `on_confirmed_by_superior()`

```python
# 修改逻辑：
# - confirmed_by = user_name_with_role
# - display_status = NULL（清除提醒）
```

#### 4.4 显示层集成

**位置**：`base.py` 的数据处理逻辑

```python
# 1. 加载处理结果后，查询display_status
for row in df.iterrows():
    task_id = calculate_task_id(...)
    display_status = registry_hooks.get_display_status(task_id)
    
    # 添加到DataFrame
    df.at[index, '状态'] = display_status or ""

# 2. 导出时过滤
def filter_for_export(df):
    """导出时过滤掉"待确认"状态的任务"""
    if '状态' in df.columns:
        df = df[~df['状态'].str.contains('待.*确认', na=False)]
    return df
```

---

### 五、角色解耦方案

#### 5.1 问题场景

```
用户"张三"的角色：["设计人员", "1818接口工程师"]

任务A：
  - 项目: 1818
  - 责任人: 张三
  - 需要"1818接口工程师"确认

冲突：张三既是责任人又是确认人！
```

#### 5.2 解决方案

**规则**：按角色上下文独立判断

```python
def get_user_context_for_task(user_name, user_roles, task):
    """
    确定用户在该任务中的角色上下文
    
    返回: "designer" | "superior" | "both"
    """
    is_designer = (task['responsible_person'] == user_name)
    is_superior = is_user_responsible_for_task(user_roles, task)
    
    if is_designer and is_superior:
        return "both"  # 特殊处理
    elif is_designer:
        return "designer"
    elif is_superior:
        return "superior"
    else:
        return None

# 显示逻辑
if context == "both":
    # 优先显示设计人员视图
    # 但勾选框同时具有确认功能
    display_status = "待上级确认（您可自行确认）"
elif context == "designer":
    display_status = task['display_status']  # "待上级确认"
elif context == "superior":
    if task['status'] == 'completed':
        display_status = "待您确认"
```

---

### 六、实施步骤

#### 阶段1：数据库扩展（30分钟）
1. ✅ 修改 `registry/db.py`
2. ✅ 添加字段迁移逻辑（向后兼容）
3. ✅ 修改 `registry/service.py` 的upsert逻辑

#### 阶段2：指派集成（1小时）
1. ✅ 实现 `on_assigned()` 钩子
2. ✅ 修改 `distribution.py` 调用钩子
3. ✅ 测试指派流程

#### 阶段3：状态显示（1.5小时）
1. ✅ 修改 `on_response_written()` 设置display_status
2. ✅ 修改 `on_confirmed_by_superior()` 清除display_status
3. ✅ 实现 `get_display_status()` 查询接口
4. ✅ 修改 `base.py` 数据加载，添加状态列

#### 阶段4：导出过滤（30分钟）
1. ✅ 修改导出逻辑，过滤"待确认"任务
2. ✅ 修改汇总TXT生成

#### 阶段5：角色解耦（1小时）
1. ✅ 实现角色上下文判断
2. ✅ 特殊显示逻辑
3. ✅ 测试重叠角色场景

#### 阶段6：测试（1小时）
1. ✅ 单元测试
2. ✅ 集成测试
3. ✅ 多用户协作测试

**总预计时间**：5-6小时
**预计Token**：8-10万

---

### 七、状态列文案设计

| 状态 | 文案 | 颜色 | 显示给谁 |
|------|------|------|----------|
| 未指派 | （空） | - | 所有人 |
| 已指派未完成 | "📌待完成" | 蓝色 | 设计人员+指派人 |
| 已完成待确认 | "⏳待上级确认" | 黄色 | 设计人员+上级 |
| 已完成待指派人确认 | "⏳待确认" | 黄色 | 设计人员+指派人 |
| 重叠角色 | "⏳待确认（可自行确认）" | 橙色 | 设计人员本人 |
| 已确认 | （空） | - | 所有人 |

---

### 八、风险评估

#### 高风险
- ❌ 无

#### 中风险
1. ⚠️ 旧数据迁移：新增字段需要向后兼容
   - 解决：使用 `DEFAULT NULL`，旧数据自动兼容
   
2. ⚠️ 性能影响：每行数据查询DB
   - 解决：批量查询 + 缓存

#### 低风险
1. 角色解耦逻辑复杂
   - 解决：充分测试 + 文档说明

---

### 九、向后兼容性

#### 9.1 数据库兼容
- 新增字段使用 `DEFAULT NULL`
- 旧数据不受影响

#### 9.2 功能兼容
- 未启用指派功能 → 正常显示
- 未启用Registry → 不影响原有流程

#### 9.3 UI兼容
- 状态列原本支持空值
- 扩展文案不影响布局

---

### 十、测试用例

#### 10.1 基础流程
```
用例1：无指派 → 完成 → 确认
  1. 设计人员完成 → 显示"⏳待上级确认"
  2. 室主任确认 → 状态清除
  3. 导出时不包含

用例2：有指派 → 完成 → 确认
  1. 接口工程师指派给张三 → 显示"📌待完成"
  2. 张三完成 → 显示"⏳待确认"
  3. 接口工程师确认 → 状态清除
```

#### 10.2 角色解耦
```
用例3：重叠角色
  用户：张三（设计人员 + 1818接口工程师）
  任务：1818项目，责任人张三
  
  1. 张三完成 → 显示"⏳待确认（可自行确认）"
  2. 张三勾选确认 → 状态清除
```

#### 10.3 多上级
```
用例4：多个上级任意确认
  任务：2016项目 + 结构一室
  
  负责人：["2016接口工程师", "一室主任"]
  
  1. 设计人员完成 → 两个角色都看到"待您确认"
  2. 接口工程师确认 → 状态清除（室主任不再看到）
```

---

## 🎯 总结

### 核心设计
1. **数据库扩展**：5个新字段
2. **状态流转**：6种状态
3. **角色解耦**：上下文判断
4. **UI集成**：状态列显示
5. **导出过滤**：自动排除待确认

### 优势
- ✅ 不用GUI弹窗
- ✅ 基于DB，持久化
- ✅ 多用户实时同步
- ✅ 角色独立处理
- ✅ 向后兼容

### 实施建议
- 分6个阶段
- 每阶段独立测试
- 总时间约5-6小时

---

**您觉得这个设计方案如何？有需要调整的地方吗？**

