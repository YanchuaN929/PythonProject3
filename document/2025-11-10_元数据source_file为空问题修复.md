# 元数据source_file为空问题修复

**日期**: 2025-11-10  
**问题严重度**: 🔴 严重  
**影响**: 排序后点击接口号报错"无法获取源文件信息"

---

## 🐛 问题描述

### 用户报告

排序后点击接口号，弹窗报错："无法获取源文件信息，请联系管理员"

**控制台输出**：
```
[回文输入] item_id: I003
[回文输入] 接口号(UI): S-SA---1JT-01-25C1-25E6(设计人员)
[回文输入] 源文件: N/A
[回文输入] 项目号: 2016
[回文输入] Excel行号: 87
[错误] 无法确定源文件
```

**关键问题**：
- 项目号有值：2016
- Excel行号有值：87
- **源文件为空：N/A** ❌

---

## 🔍 根本原因分析

### 问题链路

#### 1. 元数据从display_df读取

```python
# window.py 第738行（修改前）
for index in range(max_rows):
    row = display_df.iloc[index]  # ← 使用display_df
    
    # ...
    
    # 第780行（修改前）
    metadata = {
        'source_file': row.get('source_file', '') if 'source_file' in row.index else '',
        # ← 从display_df的row读取source_file
    }
```

#### 2. display_df不包含source_file列

```python
# window.py 第515行
display_df = self._create_optimized_display(filtered_df, tab_name, completed_rows=completed_rows_set)
```

**`_create_optimized_display`函数**：
- 目的：创建**优化的显示数据**
- 只保留需要显示的列：项目号、接口号、状态、接口时间等
- **不包含**：`source_file`, `_source_column`等内部列

#### 3. 元数据中source_file为空

```python
'source_file': row.get('source_file', '')  # row来自display_df
# display_df中没有'source_file'列
# → row.get('source_file', '') 返回 ''
# → metadata['source_file'] = ''
```

#### 4. 点击时报错

```python
# window.py 第1046行
source_file = metadata['source_file']  # = ''

# 第1068行
if not source_file:
    print(f"[错误] 无法确定源文件")
    messagebox.showerror("错误", "无法获取源文件信息，请联系管理员")
    return  # ← 报错退出
```

---

## 🔧 修复方案

### 核心修复：分离显示数据和元数据来源

**文件**: `window.py` 第737-794行

```python
for index in range(max_rows):
    # 【修复】用于显示的行（display_df）
    display_row = display_df.iloc[index]
    
    # 【关键修复】用于元数据的行（filtered_df，包含完整原始数据）
    # display_df可能不包含source_file等列，必须从filtered_df读取
    metadata_row = filtered_df.iloc[index] if index < len(filtered_df) else display_row
    
    # 处理数据显示格式（从display_row读取）
    display_values = []
    for col in columns:
        val = display_row[col]  # ← 显示数据从display_row
        # ...
    
    item_id = viewer.insert("", "end", text=display_text, values=display_values, tags=tags)
    
    # 【关键修复】存储元数据（从metadata_row读取）
    metadata = {
        'original_index': index,
        'original_row': original_row_numbers[index] if ... else index + 2,
        'source_file': metadata_row.get('source_file', '') if 'source_file' in metadata_row.index else '',
        'project_id': str(metadata_row.get('项目号', '')) if '项目号' in metadata_row.index else '',
        'interface_id': metadata_row.get('接口号', '') if '接口号' in metadata_row.index else '',
        'source_column': metadata_row.get('_source_column', None) if '_source_column' in metadata_row.index else None,
    }
    self._item_metadata[(viewer, item_id)] = metadata
    
    # 【调试】如果source_file为空，打印警告
    if not metadata['source_file']:
        print(f"[警告] 第{index}行元数据source_file为空，项目号: {metadata['project_id']}, 接口号: {metadata['interface_id']}")
```

---

## 📊 数据流对比

### 修改前（错误）

```
filtered_df（包含source_file）
    ↓
display_df = _create_optimized_display(filtered_df)
    ↓ (优化，删除不需要显示的列)
display_df（不包含source_file）❌
    ↓
for index in range(max_rows):
    row = display_df.iloc[index]
    metadata['source_file'] = row.get('source_file', '')  # = ''
    ↓
metadata['source_file'] = '' ❌
```

### 修改后（正确）

```
filtered_df（包含source_file）
    ↓
display_df = _create_optimized_display(filtered_df)
    ↓ (优化，删除不需要显示的列)
display_df（不包含source_file）
    ↓
for index in range(max_rows):
    display_row = display_df.iloc[index]     ← 用于显示
    metadata_row = filtered_df.iloc[index]   ← 用于元数据 ✓
    
    metadata['source_file'] = metadata_row.get('source_file', '')  # ✓
    ↓
metadata['source_file'] = 'D:\Programs\...\收发文清单2016.xlsx' ✓
```

---

## ✅ 修复效果

### 修改前（错误）
```
排序后点击接口号
    ↓
metadata['source_file'] = ''（从display_df读取，为空）
    ↓
❌ 报错："无法获取源文件信息，请联系管理员"
```

### 修改后（正确）
```
排序后点击接口号
    ↓
metadata['source_file'] = 'D:\Programs\...\收发文清单2016.xlsx'（从filtered_df读取）
    ↓
✅ 正常弹出回文单号输入框
✅ 数据正确写入2016项目文件
```

---

## 🧪 测试建议

### 测试场景

1. **排序后填写回文单号**：
   - 点击任意表头排序
   - 点击排序后的任意行的接口号
   - **预期**：正常弹出输入框，不报错
   - **检查控制台**：
     ```
     [回文输入] item_id: IXXXX
     [回文输入] 源文件: 收发文清单2016.xlsx  ← 有值！
     [回文输入] 项目号: 2016
     [回文输入] Excel行号: 87
     ```

2. **多次排序后测试**：
   - 按时间排序 → 点击接口号 → 应该正常
   - 按项目号排序 → 点击接口号 → 应该正常
   - 按接口号排序 → 点击接口号 → 应该正常

3. **验证数据写入**：
   - 确认Excel文件被正确修改
   - 确认历史记录关联到正确的项目

---

## 🔗 与其他修复的关联

### 修复时间线

1. **DataFrame索引重置**（第一次修复）：
   - 问题：筛选后索引不连续
   - 修复：`filtered_df.reset_index(drop=True)`

2. **元数据映射**（第二次修复）：
   - 问题：排序后位置索引错乱
   - 修复：存储元数据，不依赖位置

3. **元数据来源修正**（本次修复）：
   - 问题：元数据从display_df读取，source_file为空
   - 修复：元数据从filtered_df读取

### 三者关系

```
原始数据（df）
    ↓
筛选（角色）
    ↓
filtered_df.reset_index(drop=True)  ← 修复1：索引连续
    ↓
display_df = _create_optimized_display(filtered_df)  ← 优化显示
    ↓
插入Treeview时：
    display_row = display_df.iloc[index]     ← 用于显示
    metadata_row = filtered_df.iloc[index]   ← 修复3：元数据来源
    metadata = {...}
    self._item_metadata[(viewer, item_id)] = metadata  ← 修复2：存储元数据
    ↓
排序（用户点击表头）
    ↓
点击接口号：
    metadata = self._item_metadata.get((viewer, item_id))  ← 修复2：读取元数据
    source_file = metadata['source_file']  ← 修复3：有值！
```

---

## 📋 涉及文件

| 文件 | 修改内容 | 行数 |
|-----|---------|------|
| `window.py` | 分离display_row和metadata_row | 第738-743行 |
| `window.py` | 从filtered_df读取元数据 | 第782-794行 |
| `document/2025-11-10_元数据source_file为空问题修复.md` | 新建报告 | - |

---

## 🎓 关键教训

### 1. 数据职责分离

**教训**：
- 显示数据（display_df）：优化后的列，仅用于UI展示
- 元数据（filtered_df）：完整原始列，用于业务逻辑
- **两者不能混用**

### 2. DataFrame优化的副作用

**问题**：
```python
display_df = _create_optimized_display(filtered_df)
# 为了优化显示，删除了source_file等不需要显示的列
# 但元数据仍然需要这些列！
```

**解决**：
- 明确区分数据来源
- 显示用`display_df`
- 元数据用`filtered_df`

### 3. 防御性编程

**添加警告日志**：
```python
if not metadata['source_file']:
    print(f"[警告] 第{index}行元数据source_file为空，项目号: {metadata['project_id']}, 接口号: {metadata['interface_id']}")
```

**作用**：
- 及早发现问题
- 便于调试
- 避免静默失败

---

## ✅ 完成状态

**修复时间**：2025-11-10  
**测试状态**：⏳ 待用户验证  
**预期效果**：
- ✅ 排序后点击接口号，正常弹出输入框
- ✅ 控制台显示正确的源文件路径
- ✅ 数据正确写入对应项目文件
- ✅ 不再报错"无法获取源文件信息"

---

**报告完成时间**：2025-11-10

**关键修复点**：
- 第738-743行：分离`display_row`和`metadata_row`
- 第785-789行：从`metadata_row`（filtered_df）读取元数据
- 第792-794行：添加空值警告

**影响范围**：
- 所有文件类型（1-6）
- 所有排序操作
- 所有回文单号输入操作
- 所有勾选框操作

**风险等级**：🔴 高（已修复）
**修复优先级**：P0（立即测试）

