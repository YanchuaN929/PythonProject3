# Scripts 目录说明

本目录包含各种工具脚本和调试脚本。

## 📂 目录结构

```
scripts/
├── db_tools/        # 数据库相关工具
│   ├── check_and_fix_db_location.py      # 检查并修复数据库位置
│   ├── migrate_db_to_data_folder.py      # 迁移数据库到数据文件夹
│   └── check_excel_db_mapping.py         # 检查Excel与数据库字段映射
│
└── debug/           # 调试脚本
    ├── debug_assigned_simple.py          # 简单的指派任务调试
    ├── debug_assigned_tasks.py           # 详细的指派任务调试
    └── debug_status_display.py           # 状态显示调试
```

---

## 🛠️ 数据库工具 (db_tools/)

### check_and_fix_db_location.py
**功能**：检查Registry数据库的位置是否正确

**使用场景**：
- 多用户协作环境中，数据库应该在共享数据文件夹中
- 如果发现本地有数据库，会提示迁移

**使用方法**：
```bash
python scripts/db_tools/check_and_fix_db_location.py
```

---

### migrate_db_to_data_folder.py
**功能**：自动迁移本地数据库到共享数据文件夹

**使用场景**：
- 从单用户环境迁移到多用户协作环境
- 数据库位置需要变更

**使用方法**：
```bash
python scripts/db_tools/migrate_db_to_data_folder.py
```

---

### check_excel_db_mapping.py
**功能**：验证Excel列与数据库字段的映射关系

**使用场景**：
- 检查数据完整性
- 验证新增字段是否正确映射
- 开发调试

**使用方法**：
```bash
python scripts/db_tools/check_excel_db_mapping.py
```

**输出内容**：
- Excel列与DB字段对应关系
- 数据流向分析
- 映射完整性报告

---

## 🐛 调试脚本 (debug/)

### debug_assigned_simple.py
**功能**：简单检查数据库文件是否存在

**使用场景**：
- 快速验证数据库连接
- 最基础的数据库健康检查

**使用方法**：
```bash
python scripts/debug/debug_assigned_simple.py
```

---

### debug_assigned_tasks.py
**功能**：查询指定任务的指派信息

**使用场景**：
- 调试指派功能
- 查看任务的assigned_by和responsible_person

**使用方法**：
```bash
python scripts/debug/debug_assigned_tasks.py
```

**输出示例**：
```
Task: abc123...
  assigned_by: Manager Wang
  responsible_person: Zhang San
  display_status: 待完成
```

---

### debug_status_display.py
**功能**：全面调试状态显示问题

**使用场景**：
- 排查"请指派"显示错误
- 验证responsible_person字段同步
- 检查状态计算逻辑

**使用方法**：
```bash
python scripts/debug/debug_status_display.py
```

**检查内容**：
1. 所有待完成任务的responsible_person字段
2. 是否有异常任务（有assigned_by但无responsible_person）
3. get_display_status函数测试
4. 最近扫描的任务状态

---

## 📋 使用建议

### 问题排查流程

1. **数据库位置问题**：
   ```bash
   python scripts/db_tools/check_and_fix_db_location.py
   ```

2. **数据映射问题**：
   ```bash
   python scripts/db_tools/check_excel_db_mapping.py
   ```

3. **状态显示问题**：
   ```bash
   python scripts/debug/debug_status_display.py
   ```

4. **指派任务问题**：
   ```bash
   python scripts/debug/debug_assigned_tasks.py
   ```

---

## ⚠️ 注意事项

1. **运行环境**：所有脚本都应该在项目根目录运行
2. **数据库访问**：某些脚本需要访问Registry数据库
3. **配置文件**：需要正确的`config.json`配置

---

**最后更新**：2025-11-05  
**维护者**：AI Assistant

