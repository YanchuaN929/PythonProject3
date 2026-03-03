# `sql_explorer_onefile` 实机 SQL 完整探索任务书（文件2/4责任人分发链路）

## 0. 任务背景

你是负责 `sql_explorer_onefile.spec` 的助手。  
本次目标不是离线推断，而是到**实机 CIMS SQL**里把“文件2 / 文件4 的责任人分发链路”一次性探明。

当前离线证据已确认：

- 文件2 `D` 列（对方文号）可稳定映射到 `INTINTERFACEDOC`：
  - `D` 唯一键数 `5415`
  - `D -> INT.ITEM_NUMBER` 唯一命中 `100%`
  - `D -> INT.REF_ITEM_NUMBER` 唯一命中 `100%`
  - `(A,D)` 对在 `INT(ITEM_NUMBER, REF_ITEM_NUMBER)` 行级命中 `7238/7238 = 100%`
- 文件4 `E` 列（接口单号）可稳定映射到 `SENDRECEIVEDATA`：
  - `E` 唯一键数 `17822`
  - `E -> SENDRECEIVEDATA.LETTER_SEND_NO` 唯一命中 `100%`
  - `E -> SENDRECEIVEDATA.CORRESP_LETTER_REC_NO` 命中 `48.21%`（辅键）
- 离线包缺口：分发表只有 schema，缺数据导出，导致责任人链路无法闭环。

离线证据文件：`document/file2_4_distribution_chain_probe.json`

---

## 1. 本次必须回答的问题（最终报告要有明确结论）

1. 文件2责任人是否需要通过“对方文号链路（`A/D -> INT -> 分发表`）”而非单表字段得到？
2. 文件4责任人是否需要通过“接口单号链路（`E -> SEND -> 分发表`）”而非单表字段得到？
3. 若需要分发表，**哪一张表 / 哪个字段**是责任人最优来源（覆盖率 + 业务语义最佳）？
4. 是否存在“关键表无权限或无数据”导致责任人无法还原？

---

## 2. 优先探索表（必须覆盖）

### P0（必须）

- `innovator.DISTRIBUTERECORD`
- `innovator.OBJECTREPLYLINK`
- `innovator.FILETRANSMISSION`
- `innovator.SENDRECEIVEDATA`
- `innovator.INTINTERFACEDOC`

### P1（强烈建议）

- `innovator.CRREPLY`
- `innovator.DCRREPLY`
- `innovator.FCRREPLY`
- `innovator.NCRREPLY`
- `innovator.TCRREPLY`
- `innovator.TAREPLY`
- `innovator.TA`
- `innovator.MEMORANDUM`
- `innovator.TELEFAX`

---

## 3. 关键字段字典（重点核验）

- 分发主链：
  - `DISTRIBUTERECORD.SOURCE_OBJECT_ID`
  - `DISTRIBUTERECORD.OPERATOR`
  - `DISTRIBUTERECORD.SENDER`
  - `DISTRIBUTERECORD.DISTRIBUTE_TYPE`
- 对象映射链：
  - `OBJECTREPLYLINK.SOURCE_OBJECT_ID / SOURCE_OBJECT_NUMBER`
  - `OBJECTREPLYLINK.REPLY_OBJECT_ID / REPLY_OBJECT_NUMBER`
- 文函链：
  - `SENDRECEIVEDATA.id`
  - `SENDRECEIVEDATA.LETTER_SEND_NO`
  - `SENDRECEIVEDATA.CORRESP_LETTER_REC_NO`
  - `SENDRECEIVEDATA.CREATED_BY_ID / MODIFIED_BY_ID`
- 接口链：
  - `INTINTERFACEDOC.id`
  - `INTINTERFACEDOC.ITEM_NUMBER`
  - `INTINTERFACEDOC.REF_ITEM_NUMBER`
  - `INTINTERFACEDOC.CREATED_BY_ID / MODIFIED_BY_ID`
- 关联补充：
  - `FILETRANSMISSION.SEND_RECEIVE_DATA`
  - `FILETRANSMISSION.FILE_RECEIVER`
  - `*_REPLY.SEND_RECEIVE_DATA`

---

## 4. 执行步骤（必须按顺序）

## 4.1 重新构建 onefile 可执行程序

在仓库根目录：

```powershell
cd "E:\program\PythonProject3"
python -m PyInstaller --noconfirm "sql_explorer_onefile.spec"
```

确认产物存在（通常为 `dist\sql_explorer_onefile.exe`）。

## 4.2 实机跑全量探索（先拿总览）

```powershell
.\sql_explorer_onefile.exe run --host <HOST> --port 1433 --database CIMS --username <USER> --password <PWD> --schema innovator --table-limit 300 --top 800 --candidate-top 20 --save-profile --pause-on-error
```

说明：

- `--table-limit 300`：避免分发表被截断。
- `--top 800`：增加候选字段可见性。
- 如果已有保存连接，可改用 `--use-saved-profile`。

## 4.3 对关键表做单表深采样（每表独立输出目录）

```powershell
$tables = @(
  "innovator.DISTRIBUTERECORD",
  "innovator.OBJECTREPLYLINK",
  "innovator.FILETRANSMISSION",
  "innovator.SENDRECEIVEDATA",
  "innovator.INTINTERFACEDOC",
  "innovator.CRREPLY",
  "innovator.DCRREPLY",
  "innovator.FCRREPLY",
  "innovator.NCRREPLY",
  "innovator.TCRREPLY",
  "innovator.TAREPLY",
  "innovator.TA",
  "innovator.MEMORANDUM",
  "innovator.TELEFAX"
)

foreach ($t in $tables) {
  $dirName = $t.Replace(".", "_")
  .\sql_explorer_onefile.exe sample --use-saved-profile --table $t --top 2000 --where "IS_CURRENT='1'" --output-root ".\sql_explorer_output\distribution_probe\$dirName"
}
```

如果某表无 `IS_CURRENT` 字段，重跑该表并去掉 `--where`。

---

## 5. 必做验证（输出量化指标）

## 5.1 文件2链路验证（对方文号链）

目标链路：

`Excel 文件2: (A, D)`  
`-> INTINTERFACEDOC.(ITEM_NUMBER, REF_ITEM_NUMBER)`  
`-> INT.id`  
`-> DISTRIBUTERECORD.SOURCE_OBJECT_ID / OBJECTREPLYLINK.SOURCE_OBJECT_ID`  
`-> 分发责任人字段(OPERATOR/SENDER/...)`

必须输出：

1. `A/D -> INT` 覆盖率
2. `INT.id -> DISTRIBUTERECORD` 覆盖率
3. `INT.id -> OBJECTREPLYLINK` 覆盖率
4. 每个候选责任人字段的：
   - 非空率
   - 可映射 USER 比例（若是32位ID）
   - 与 Excel 责任人列（文件2 `AM`）匹配率

## 5.2 文件4链路验证（接口单号链）

目标链路：

`Excel 文件4: E`  
`-> SENDRECEIVEDATA.LETTER_SEND_NO`  
`-> SEND.id`  
`-> DISTRIBUTERECORD / OBJECTREPLYLINK / FILETRANSMISSION / *_REPLY`  
`-> 分发责任人字段`

必须输出：

1. `E -> SEND.LETTER_SEND_NO` 覆盖率
2. `SEND.id -> DISTRIBUTERECORD` 覆盖率
3. `SEND.id -> OBJECTREPLYLINK` 覆盖率
4. `SEND.id -> FILETRANSMISSION.SEND_RECEIVE_DATA` 覆盖率
5. `SEND.id -> *_REPLY.SEND_RECEIVE_DATA` 覆盖率（分表输出）
6. 候选责任人字段与 Excel 责任人列（文件4 `AH`）匹配率

---

## 6. 回传物（必须齐全）

放到单独目录（建议：`sql_explorer_output/real_distribution_chain_<timestamp>/`）并回传：

1. `real_distribution_chain_report.md`（最终结论）
2. `real_distribution_chain_report.json`（机器可读）
3. `table_rowcount_and_coverage.csv`（各链路覆盖率）
4. `owner_candidate_scores.csv`（候选责任人字段评分）
5. `run_diagnostics.txt`（错误与权限信息）
6. `sample_*.json`（关键表采样结果）

---

## 7. 验收标准

- 能明确给出：
  - 文件2责任人主链路（含主字段 + 回退字段）
  - 文件4责任人主链路（含主字段 + 回退字段）
- 对每条链路有可复核的覆盖率和样例证据。
- 若因权限/缺表/空表失败，必须给出“失败点 + 影响范围 + 需要补数的最小清单”。

---

## 8. 失败兜底（如果实机仍拿不到分发表数据）

若实机依然无法读取 `DISTRIBUTERECORD/OBJECTREPLYLINK/FILETRANSMISSION/*_REPLY`：

1. 输出可访问对象清单（包含 schema/table/行数）。
2. 输出 SQL 权限错误原文（截断敏感信息）。
3. 给出最小补数需求：
   - 表名
   - 必须字段
   - 时间范围建议（近 3~5 年）
4. 暂时回退策略：
   - 文件2：`INT.MODIFIED_BY_ID` 系列
   - 文件4：`SEND.CREATED_BY_ID/MODIFIED_BY_ID` 系列
   - 并标注“非最终口径”。

---

## 9. 双机协作标准流程（本机开发 -> 实机运行 -> 结果回传）

> 本节为新增执行规范。目标是避免“开发机无数据库”的客观限制导致误判。

### 9.1 角色分工（必须遵守）

- 开发机（本机）只做：
  - 修改源码（`scripts/db_tools/sql_explorer/*`）
  - 本地静态检查与离线校验
  - 打包 `dist/sql_explorer_onefile.exe`
- 实机（内网可连 CIMS）只做：
  - 执行 `sql_explorer_onefile.exe` 连库探测
  - 产出 `sql_explorer_output/...` 目录
  - 把完整输出目录回拷给开发机分析

### 9.2 标准闭环（每轮都按此顺序）

1. 本机改动后重打包：
   ```powershell
   cd "E:\program\PythonProject3"
   python -m PyInstaller --noconfirm "sql_explorer_onefile.spec"
   ```
2. 确认新包信息（时间/大小）并交付实机：
   - `dist\sql_explorer_onefile.exe`
3. 实机执行分发链闭环命令（优先）：
   - 已保存连接：
   ```powershell
   .\sql_explorer_onefile.exe distribution-chain --use-saved-profile --schema innovator --sample-top 2000 --file2-excel ".\example\内部接口信息单报表181820260128.xlsx" --file4-excel ".\example\外部接口单报表181820260128.xlsx" --output-root ".\sql_explorer_output\real_distribution_chain_$(Get-Date -Format yyyyMMdd_HHmmss)" --pause-on-exit
   ```
   - 首次运行（无保存连接）：
   ```powershell
   .\sql_explorer_onefile.exe distribution-chain --host <HOST> --port 1433 --database CIMS --username <USER> --password <PWD> --save-profile --schema innovator --sample-top 2000 --file2-excel ".\example\内部接口信息单报表181820260128.xlsx" --file4-excel ".\example\外部接口单报表181820260128.xlsx" --output-root ".\sql_explorer_output\real_distribution_chain_$(Get-Date -Format yyyyMMdd_HHmmss)" --pause-on-exit
   ```
4. 实机回拷完整输出目录（整目录，不挑文件）。
5. 开发机基于回拷结果做结论与下一轮修复。

### 9.3 返回码与终端文案判读（避免误判）

- `exit_code = 0`：闭环成功（程序执行完成）
- `exit_code = 3`：程序执行完成但存在业务阻塞（不是崩溃）
  - 终端提示应为：`程序执行完成（存在阻塞，请查看报告）`
- 其他非 0：执行失败，需要优先看 `run_diagnostics.txt` 的异常栈

---

## 10. 分发链执行优先级（相对 run/sample 的关系）

- `distribution-chain` 是文件2/4闭环专用总控流程，应作为首选入口。
- `run` 与 `sample` 保留为补充探针：
  - `run`：看全局候选趋势和 schema 侧全览
  - `sample`：针对单表追加取证
- 当 `distribution-chain` 与 `run` 结论冲突时，优先按 `distribution-chain` 的链路覆盖率与阻塞点判定。

---

## 11. 已知高频失败点（来自实机回传）与处理

### 11.1 样本 Excel 路径找不到

- 典型报错：`No such file or directory: 'example\\内部接口信息单报表181820260128.xlsx'`
- 处理要点：
  - onefile 模式下优先走 `_MEIPASS` 资源路径回退
  - 命令行可显式给绝对路径覆盖 `--file2-excel/--file4-excel`

### 11.2 JSON 序列化 datetime 失败

- 典型报错：`Object of type datetime is not JSON serializable`
- 处理要点：
  - 分发链输出 `sample_*.json` 时使用日期安全序列化（datetime -> ISO 字符串）

### 11.3 “程序执行失败”与“阻塞态”混淆

- 业务阻塞（如空表、链路命中为 0）应返回 `3`，不是崩溃失败。
- 验收以报告文件和覆盖率为准，不以终端一句文案单独判定。

---

## 12. 回拷清单（实机必须原样返回）

- 根目录：
  - `run_diagnostics.txt`
  - `real_distribution_chain_report.md`
  - `real_distribution_chain_report.json`
  - `table_rowcount_and_coverage.csv`
  - `owner_candidate_scores.csv`
- 明细目录：
  - `distribution_probe/*/sample_result.json`
  - `raw_runs/overview/*`（含 `mapping_report.*`、`candidate_columns.csv`、`quality_report.csv`、`schema_snapshot.json`、`discovery_result.json`）

> 缺任一关键文件，默认该轮“不可验收”，需补跑或补回拷。

