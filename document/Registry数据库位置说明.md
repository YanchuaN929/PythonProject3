# Registry数据库位置说明

## 📋 问题说明

目前测试脚本创建的数据库在**本地**的`result_cache\registry.db`，而不是在**数据文件夹（公共盘）**中。

这是因为测试脚本直接调用配置，没有通过主程序的初始化流程。

---

## ✅ 正确的数据库位置

### 单用户模式
```
本地路径: result_cache\registry.db
适用场景: 仅自己使用，不需要多人协作
```

### 多用户模式（推荐）⭐
```
公共盘路径: [数据文件夹]\.registry\registry.db

例如:
D:/Programs/筛选任务/基层材料文件/.registry/registry.db

适用场景: 多人协作，共享任务状态
```

---

## 🔧 配置说明

### 1. 数据库位置由`config.json`中的`folder_path`决定

```json
{
  "folder_path": "D:/Programs/筛选任务/基层材料文件"
}
```

**如果设置了`folder_path`**：
- ✅ 主程序运行时，数据库会自动创建在：`[folder_path]\.registry\registry.db`
- ✅ 所有访问该数据文件夹的用户共享同一个数据库
- ✅ 支持多用户协作

**如果没有设置`folder_path`**：
- ⚠️ 数据库会创建在本地：`result_cache\registry.db`
- ⚠️ 每个用户有自己的数据库，无法协作

---

## 🚀 迁移数据库到公共盘

### 方法1：自动迁移脚本（推荐）

```bash
python migrate_db_to_data_folder.py
```

**功能**：
- 自动检测本地数据库
- 复制到数据文件夹
- 保留本地副本作为备份

**输出示例**：
```
[SUCCESS] Migration completed!

[INFO] Local database kept as backup at: result_cache\registry.db

[NEXT STEPS]
1. Restart the program
2. All users accessing the same data folder will share this database
3. You can manually delete the local backup if migration works well
```

### 方法2：手动迁移

1. **创建目标目录**：
   ```
   [数据文件夹]\.registry\
   ```

2. **复制数据库文件**：
   ```
   从: result_cache\registry.db
   到: [数据文件夹]\.registry\registry.db
   ```

3. **重启程序**

---

## 🔍 验证数据库位置

### 运行检查脚本

```bash
python check_and_fix_db_location.py
```

**输出示例**：
```
[INFO] Data folder (from config.json):
  D:/Programs/筛选任务/基层材料文件

[INFO] Correct database location (multi-user):
  D:/Programs/筛选任务/基层材料文件/.registry/registry.db

[CHECK] Local DB exists: True
[CHECK] Correct DB exists: True

[OK] Database is in correct location!
```

---

## 📊 数据库路径优先级

主程序运行时，数据库路径按以下优先级确定：

1. **最高优先级**：`config.json`中的`registry_db_path`（如果明确指定）
   ```json
   {
     "registry_db_path": "Z:/SharedDrive/registry.db"
   }
   ```

2. **自动确定**：如果`registry_db_path`为空，且设置了`folder_path`
   ```
   数据库路径 = [folder_path]\.registry\registry.db
   ```

3. **默认路径**：如果都没有设置
   ```
   数据库路径 = result_cache\registry.db
   ```

---

## ⚠️ 注意事项

### 1. 测试脚本vs主程序

| | 测试脚本 | 主程序 |
|---|---|---|
| 数据库位置 | 总是本地`result_cache\` | 根据`folder_path`自动选择 |
| 用途 | 开发测试 | 正式使用 |
| 多用户 | ❌ 不支持 | ✅ 支持 |

**建议**：
- ✅ 正式使用时运行主程序
- ✅ 测试时运行测试脚本
- ⚠️ 不要混用两个数据库

### 2. 数据文件夹必须是网络盘

如果要实现多用户协作：
- ✅ `folder_path`应该指向**网络共享盘**（如`Z:\SharedDrive\...`）
- ✅ 所有用户都能访问该路径
- ❌ 不能是本地路径（如`C:\Users\...`）

### 3. 权限问题

确保所有用户对`.registry`目录有：
- ✅ 读权限（读取任务状态）
- ✅ 写权限（更新任务状态）

---

## 🎯 最佳实践

### 多用户协作场景（推荐）

1. **配置数据文件夹**：
   ```json
   {
     "folder_path": "Z:/SharedDrive/ProjectData"
   }
   ```

2. **首次使用**：
   - 运行主程序
   - 点击"开始处理"
   - 数据库自动创建在`Z:/SharedDrive/ProjectData/.registry/registry.db`

3. **其他用户**：
   - 使用相同的`folder_path`配置
   - 运行主程序
   - 自动连接到共享数据库

### 单用户场景

1. **不设置`folder_path`**（或设置为空）

2. **数据库自动使用本地路径**：
   ```
   result_cache\registry.db
   ```

---

## 🐛 常见问题

### Q1: 我有两个数据库文件怎么办？

**症状**：
```
result_cache\registry.db            (49KB)
D:/..../基层材料文件/.registry/registry.db  (0KB)
```

**原因**：测试脚本创建了本地数据库，主程序创建了公共盘数据库

**解决**：
1. 运行迁移脚本：`python migrate_db_to_data_folder.py`
2. 或手动删除本地数据库：`del result_cache\registry.db`

### Q2: 为什么指派后状态不显示？

**可能原因**：
1. 数据库位置不对（使用了本地数据库，但主程序读取公共盘数据库）
2. 数据库未初始化

**解决**：
1. 运行检查脚本确认数据库位置
2. 确保所有操作都在主程序中进行

### Q3: 多用户如何协作？

**要求**：
1. ✅ 所有用户的`folder_path`指向同一个网络盘目录
2. ✅ 所有用户都有该目录的读写权限
3. ✅ 数据库只有一个副本

**验证**：
- 用户A指派任务给张三
- 用户B打开程序，应该能看到这个指派记录
- 如果看不到，说明使用的不是同一个数据库

---

## 📝 总结

### 现在的情况

- ✅ config.json已正确配置folder_path
- ✅ 主程序会使用公共盘数据库
- ⚠️ 测试脚本创建的本地数据库需要迁移或删除

### 下一步行动

1. **运行迁移脚本**（如果本地数据库有重要数据）：
   ```bash
   python migrate_db_to_data_folder.py
   ```

2. **或直接删除本地数据库**（如果是测试数据）：
   ```bash
   del result_cache\registry.db
   ```

3. **重启主程序**，数据库会自动使用公共盘路径

4. **验证**：
   - 指派一个任务
   - 关闭程序
   - 重新打开
   - 检查指派状态是否正确显示

---

**最后更新**：2025-11-05  
**文档版本**：v1.0  
**相关脚本**：
- `check_and_fix_db_location.py` - 检查数据库位置
- `migrate_db_to_data_folder.py` - 自动迁移数据库

