# SQL Explorer 离线运行说明（内网电脑）

本工具交付为独立 `sql_explorer.exe`。拷贝到内网电脑后，双击即可运行。

## 1. 使用步骤

1. 将以下文件整体拷贝到内网电脑同一目录：
   - `sql_explorer.exe`
   - `example/`（模板参考）
   - `README_离线运行说明.md`
2. 双击 `sql_explorer.exe`。
3. 首次运行按提示输入：
   - 主机/IP
   - 数据库名
   - 用户名
   - 密码
4. 程序自动开始扫描并在当前目录创建：
   - `sql_explorer_output/<时间戳>/`
5. 将该目录回传用于后续映射确认。

## 2. 首次输入保存位置

连接信息保存在当前 Windows 用户目录：

- `%APPDATA%\\sql_explorer\\connection_profile.json`

后续运行默认复用该配置。

## 3. 结果文件说明

在 `sql_explorer_output/<时间戳>/` 内会生成：

- `mapping_report.md`：人可读报告（优先查看）
- `mapping_report.json`：完整机器可读结果
- `candidate_columns.csv`：候选列清单
- `quality_report.csv`：责任人匹配质量
- `run_diagnostics.txt`：运行日志与错误

## 4. 常见问题

- 连接失败，提示无驱动：
  - 若日志中显示 `No module named 'pymssql'` 或 `No module named 'pyodbc'`，说明打包环境未包含对应驱动依赖，需要重新打包。
- 登录失败：
  - 检查账号密码和数据库权限。
- 扫描中断：
  - 查看 `run_diagnostics.txt`，定位失败表和错误原因。

## 5. 建议回传内容

请回传以下内容用于迁移评估：

- `mapping_report.md`
- `candidate_columns.csv`
- `quality_report.csv`
- `run_diagnostics.txt`
