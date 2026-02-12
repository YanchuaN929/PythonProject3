# SQL Explorer 开发说明

`sql_explorer` 是用于 SQL Server 字段探索的独立工具模块，目标是帮助识别待处理文件 1/2/3/4/6 的时间列与责任人列，并输出可用于后续数据库驱动迁移的证据报告。

## 目录结构

- `cli.py`：入口（向导 + CLI）
- `connect.py`：SQL Server 连接（`pymssql` 优先，`pyodbc` 回退）
- `schema.py`：Schema 扫描
- `sampling.py`：表采样
- `profiling.py`：字段画像
- `discovery.py`：候选列发现与评分
- `roster.py`：姓名角色表读取与匹配校验
- `report.py`：报告写出
- `generate_example_templates.py`：生成 `example/` 模板

## 本地开发运行

在仓库根目录执行：

```bash
python "scripts/db_tools/sql_explorer_main.py" --help
```

完整探索：

```bash
python "scripts/db_tools/sql_explorer_main.py" run --host 10.27.14.216 --database master --username hbgs --password "******"
```

仅连接测试：

```bash
python "scripts/db_tools/sql_explorer_main.py" connect-test --host 10.27.14.216 --database master --username hbgs --password "******"
```

## 输出文件

默认输出目录：`./sql_explorer_output/<timestamp>/`

- `mapping_report.json`
- `mapping_report.md`
- `schema_snapshot.json`
- `discovery_result.json`
- `candidate_columns.csv`
- `quality_report.csv`
- `run_diagnostics.txt`

## 模板文件生成

```bash
python "scripts/db_tools/sql_explorer/generate_example_templates.py"
```

会生成：

- `example/待处理文件1_模板.xlsx`
- `example/待处理文件2_模板.xlsx`
- `example/待处理文件3_模板.xlsx`
- `example/待处理文件4_模板.xlsx`
- `example/待处理文件6_模板.xlsx`

## 打包 EXE

```bash
scripts\db_tools\sql_explorer\build_sql_explorer.bat
```

打包脚本策略：

- 先尝试 `onefile`（便于拷贝）
- 如失败自动回退 `onedir`

## 说明

- 连接配置保存到当前用户目录（`APPDATA/sql_explorer/connection_profile.json`）。
- 报告中责任人匹配依赖姓名角色表；默认从当前参数族 `role_table_file` 路径读取。
- 若未安装 `pymssql`/`pyodbc`，连接测试会失败并给出明确错误信息。
- 验收项清单见 `ACCEPTANCE_CHECKLIST.md`。
