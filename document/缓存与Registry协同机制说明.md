# 缓存与Registry协同机制说明

## 📋 问题分析

### 为什么没有看到`main.py`中的Registry查询调试输出？

**原因**：程序使用了缓存！

从日志可以看到：
```
✅ 缓存已加载: 60bd57d7_2016_file1.pkl (17行)
✅ 使用缓存: 项目2016file1 (17行)
```

**流程说明**：
```
点击"开始处理"
    ↓
检查文件是否变化
    ↓
文件未变化 → 使用缓存 ✓
    ↓
跳过main.py的process_target_file函数 ← 所以看不到调试输出！
    ↓
直接使用缓存的DataFrame（processing_results）
    ↓
应用角色筛选
    ↓
显示数据
```

**关键点**：
- ✅ 使用缓存时，`main.py`的处理函数**根本不会被调用**
- ✅ 因此我在`main.py`中添加的Registry查询逻辑**不会执行**
- ❌ 这就是为什么没有看到调试输出的原因

---

## 🔧 正确的修复位置

### 方案A：在缓存加载后添加Registry查询（推荐）✅

**位置**：`base.py`中使用缓存的地方

**代码位置**：
- `_process_with_cache`函数（第2615行）
- 或者在显示数据前合并Registry任务

**优点**：
- ✅ 不论是否使用缓存，都会执行Registry查询
- ✅ 保证数据一致性

---

### 方案B：清除缓存，强制重新处理

**方法**：写回文单号后，清除该文件的缓存

**缺点**：
- ❌ 性能下降
- ❌ 失去缓存的意义

---

## ✅ 已修复的导出逻辑

### 修改位置

`base.py::_exclude_pending_confirmation_rows`（第1082-1093行）

### 修复内容

**修复前**（错误）：
```python
if clean_status in ['待上级确认', '待指派人确认']:  # 旧状态文字
    exclude_indices.append(...)
```

**修复后**（正确）：
```python
if clean_status in ['待审查', '待指派人审查', '待上级确认', '待指派人确认']:
    exclude_indices.append(...)
    print(f"[Registry导出调试] 设计人员过滤：{clean_status}...")
```

**说明**：
- ✅ 同时支持新旧状态文字（向后兼容）
- ✅ 添加调试输出
- ✅ 设计人员导出时，"待审查"任务会被过滤

---

## 📊 缓存机制详解

### 缓存文件

**位置**：用户本地的`result_cache/`目录

**文件类型**：
1. **`.pkl`文件**：存储处理结果DataFrame
   - 格式：`{文件hash}_{项目号}_{文件类型}.pkl`
   - 例如：`60bd57d7_2016_file1.pkl`
   - 内容：`processing_results`的DataFrame

2. **`file_cache.json`**：存储用户勾选状态
   - 格式：`{文件路径: {用户名: [已完成行号列表]}}`
   - 例如：`{"D:/.../.../file.xlsx": {"张三": [5, 10, 15]}}`
   - 特点：按用户维度隔离

---

### Registry数据库

**位置**：公共盘的`数据文件夹/.registry/registry.db`

**内容**：
- 任务状态（open/completed/confirmed/archived）
- 指派信息（assigned_by, assigned_at, responsible_person）
- 审查记录（confirmed_by, confirmed_at）
- 显示状态（display_status）

**特点**：
- ✅ 所有用户共享
- ✅ 支持多用户协作

---

## 🔄 缓存与Registry的协同逻辑

### 正常流程

```
[首次处理]
    ↓
main.py::process_target_file 处理Excel
    ↓
Registry::on_process_done 记录任务（display_status='待完成'）
    ↓
结果保存到缓存（.pkl文件）
    ↓
显示数据

[设计人员写回文单号]
    ↓
Excel文件更新（M列填充时间）
    ↓
Registry::on_response_written 更新任务（display_status='待审查'）
    ↓
清除.pkl缓存（file_manager.clear_file_caches_only）← 关键！
    ↓
重新处理Excel

[再次点击"开始处理"]
    ↓
检查文件变化
    ↓
Excel文件已变化（M列被填充）→ 清除缓存
    ↓
重新调用main.py::process_target_file
    ↓
原始筛选：M列已填充 → 不满足条件（4行）
    ↓
Registry查询：M列已填充但有display_status → 找到待审查任务（1行）
    ↓
合并结果（4+1=5行）
    ↓
保存新缓存
    ↓
显示数据（包含待审查任务）
```

---

## 🚨 关键问题

### 问题：写回文单号后应该清除缓存

**当前代码**（`input_handler.py`）：
- 写入回文单号后，**有调用Registry钩子**
- **但没有清除缓存**！

**后果**：
- 下次"开始处理"时，仍然使用旧缓存
- `main.py`的处理函数不会被调用
- Registry查询逻辑不会执行
- 待审查任务不会被添加到结果

**解决方案**：
在`input_handler.py`的`on_confirm`方法中，写回文单号成功后，清除该文件的缓存：

```python
if success:
    # 【Registry】调用on_response_written钩子
    ...
    
    # 【新增】清除该文件的缓存，强制下次重新处理
    if self.file_manager:
        self.file_manager.clear_file_cache(self.file_path)
```

---

## ✅ 立即修复

让我修改`input_handler.py`，在写回文单号成功后清除缓存：

**修改位置**：`input_handler.py::on_confirm`方法

