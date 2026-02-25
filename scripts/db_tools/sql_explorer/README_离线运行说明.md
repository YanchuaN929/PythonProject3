# SQL Explorer 离线运行说明（内网电脑）

本工具交付为独立 `sql_explorer.exe`。拷贝到内网电脑后，双击即可运行。

## 0. 推荐推进策略（先平替定位，再内网终验）

为保证“平替”可靠落地，建议采用两阶段：

1. **阶段A：基于 `CIMS-sql/` 离线定位**
   - 目标：先把文件1/2/3/4/6的结构位置（时间列、责任人列）和映射规则固化。
   - 验证重点：`32位ID -> USER -> 姓名` + `DEPARTMENT` 关联是否稳定。
2. **阶段B：内网机 `sql_explorer.exe` 最终验证**
   - 目标：用真实在线库跑最终报告，确认离线定位规则可直接复用。

说明：如果名单仅覆盖某个所（如建筑结构所），`name_in_roster_rate` 偏低是预期现象；该指标作为参考，不作为否决条件。

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

### 1.1 本地离线结构定位（基于 CIMS-sql 快照）

在开发机执行（源码环境）：

`python -m scripts.db_tools.sql_explorer.validate_cims_sql_dump --dump-dir "sql_explorer_output/CIMS-sql" --sample-target 60000`

输出目录：

- `sql_explorer_output/CIMS-sql/validation_output/`

核心产物：

- `offline_validation_*.json`
- `offline_validation_*.md`

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

## 3.1 平替阶段验收建议（结构定位通过标准）

建议关注以下指标（用于“能否平替”的技术判定）：

- 责任人ID解析率：`id_resolved_rate >= 0.99`
- 责任人部门解析率：`resolved_dept_rate >= 0.99`
- 责任人候选字段语义正确（主责/次责/抄送分层）
- 时间列候选在文件1/2/3/4/6中稳定且可解释

说明：`name_in_roster_rate` 受名单覆盖范围影响很大，不应单独作为“失败”判据。

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
- （如果有）`validation_output/offline_validation_*.json`
