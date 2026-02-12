# SQL Explorer 验收清单

## A. 本地构建验收

- [ ] 执行 `scripts\db_tools\sql_explorer\build_sql_explorer.bat`
- [ ] 输出目录存在：`dist/sql_explorer/`
- [ ] `dist/sql_explorer/sql_explorer.exe` 存在
- [ ] `dist/sql_explorer/README_离线运行说明.md` 存在
- [ ] `dist/sql_explorer/example/` 模板目录存在

## B. EXE 启动验收

- [ ] 双击或命令行启动 `sql_explorer.exe --no-wizard` 能显示帮助
- [ ] `connect-test` 命令可运行并返回 JSON 结构结果
- [ ] 连接失败时错误信息可读（不会崩溃退出）

## C. 诊断输出验收

- [ ] 执行 `run` 命令后自动创建输出目录 `sql_explorer_output/<timestamp>/`
- [ ] 失败时至少产出 `run_diagnostics.txt`
- [ ] 成功时产出：
  - `mapping_report.md`
  - `mapping_report.json`
  - `candidate_columns.csv`
  - `quality_report.csv`
  - `schema_snapshot.json`

## D. 模板验收

- [ ] `example/待处理文件1_模板.xlsx` 存在
- [ ] `example/待处理文件2_模板.xlsx` 存在
- [ ] `example/待处理文件3_模板.xlsx` 存在
- [ ] `example/待处理文件4_模板.xlsx` 存在
- [ ] `example/待处理文件6_模板.xlsx` 存在
- [ ] `example/template_spec.json` 与模板文件保持一致

## E. 内网实机验收（交付后）

- [ ] 拷贝 `dist/sql_explorer/` 整个目录到内网机
- [ ] 双击 `sql_explorer.exe`，可输入连接信息并保存
- [ ] 执行完成后产出 `sql_explorer_output` 结果目录
- [ ] 回传结果文件进行字段映射确认
