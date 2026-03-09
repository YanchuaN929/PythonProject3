# CIMS-SQL-3.5 文件2/4 深挖复核（2026-03-09）

## 输入范围

- Excel 目录：`example/CIMS-SQL-3.5/EXCEL导出数据`
- 文件2复核样本：7 份工作簿，`90177` 行
- 文件4复核样本：7 份工作簿，`77185` 行
- SQL：`example/CIMS-SQL-3.5`
- 权威业务说明：`example/CIMS系统中各接口号的具体使用路线.docx`
- 文件2机器结果：`tmp/file2_file4_deep_dive_20260309.json`
- 文件4 Excel 规则结果：`tmp/file4_excel_rules_20260309.json`

## 结论总览

- 文件1、文件3本轮结论不变，主对象路径仍然清晰，命中率接近 100%。
- 文件2本轮最大的推进，不是责任人，而是把“回文页对象”和 `N` 列时间落点基本锁定了。
- 文件4本轮最大的推进，是把 `F/S/V/P` 四列拆成了三种不同性质：
  - `F`：双分支对象日期，不应再按单字段硬匹配。
  - `S`：Excel 派生列，本质上是 `F + 20 天`。
  - `V`：后台稳定落点更接近 `SENDRECEIVEDATA.ANSWER_DATE`。
  - `P`：高概率是由同表其它业务列派生，不像直接 SQL 字段。

## 文件1、文件3再次确认

沿用上一轮多项目复合样本复核结论：

- 文件1：`A -> IDIACP1000.ITEM_NUMBER = 34942 / 34943 = 99.9971%`
- 文件3：`C -> ICMACP1000.ITEM_NUMBER = 23638 / 23641 = 99.9873%`
- 文件3：`I -> ICMACP1000.RELEASE_PARTY = 23622 / 23641 = 99.9196%`

结论：

- 文件1主路径清晰，可继续视为已稳定。
- 文件3主路径清晰，核心锚点命中接近 100%。
- 文件3仍有部分业务列未完全定稿，但这不影响“对象路径已经清楚”的判断。

## 文件2

### 1. 回文页对象路径已基本锁定

- `P -> 回复页 INTINTERFACEDOC.ITEM_NUMBER`
  - `43028 / 43031 = 99.9930%`

结论：

- 文件2不能只看“传递页”。
- Excel `P` 列几乎可以直接作为“回文页对象”的锚点。
- 这意味着文件2的时间判断应拆成两层：
  - `A/D` 对应传递页 `INTINTERFACEDOC`
  - `P` 对应回复页 `INTINTERFACEDOC`

### 2. `N` 列已接近定稿

对 `N` 非空的 `43031` 行，按“回复页对象”做候选字段扫描：

- `N -> reply INTINTERFACEDOC.RELEASE_DATE`
  - `42742 / 43031 = 99.3284%`
- `N -> reply INTINTERFACEDOC.MODIFIED_ON`
  - `42597 / 43031 = 98.9914%`
- `N -> reply INTINTERFACEDOC.SUBMIT_DATE`
  - `41211 / 43031 = 95.7705%`

结论：

- 从数据库精确落点看，`N` 的最佳字段是“回复页对象”的 `RELEASE_DATE`。
- 从业务语义看，Word 文档写的是“回文页提交日期”。
- 因此当前最稳妥的工程表达应是：
  - 前端语义：回文页提交日期
  - SQL 落点：回复页 `INTINTERFACEDOC.RELEASE_DATE`
  - 备选近似：回复页 `MODIFIED_ON`、`SUBMIT_DATE`

### 3. `M` 列仍未找到正确落点

对 `M` 非空的 `54544` 行，分别扫描当前传递页和回复页常见日期字段：

当前传递页最佳候选：

- `M -> current INTINTERFACEDOC.ANSWER_DATE`
  - `2370 / 54544 = 4.3451%`

回复页最佳候选：

- `M -> reply INTINTERFACEDOC.MODIFIED_ON`
  - `1992 / 54544 = 3.6521%`

结论：

- `M` 不是当前页或回复页的简单直连日期字段。
- 它大概率来自更深一层的页面逻辑、流程衍生值或其它业务对象。
- 现阶段不能再把 `M` 误写成 `REPLY_DEADLINE`。

## 文件4

### 1. `F` 列不是单字段，而是双分支对象日期

之前把 `F` 当成单一 SQL 字段，整体命中一直不高。按 Word 文档和 Excel `A(IITF/IICS)` 分流后，结论明显收敛：

当 `A = IICS`：

- `F -> IICS.MODIFIED_ON = 37540 / 40013 = 93.8195%`
- `F -> IICS.RELEASE_DATE = 37409 / 40013 = 93.4921%`

当 `A = IITF`：

- `F -> IITF.MODIFIED_ON = 35487 / 37167 = 95.4799%`
- `F -> IITF.RELEASE_DATE = 35468 / 37167 = 95.4287%`

结论：

- `F` 不应再被建模成“一个固定 SQL 列”。
- 正确口径应是分支规则：
  - `A = IICS` 时，从 `IICS` 对象取日期
  - `A = IITF` 时，从 `IITF` 对象取日期
- 在两组候选里，`MODIFIED_ON` 与 `RELEASE_DATE` 都非常接近；若只保留一个工程字段，优先级可先放 `MODIFIED_ON`。

### 2. `S` 列已确认是 Excel 派生列

- `S` 非空：`57856`
- `S = F + 20 天`
  - `57855 / 57856 = 99.9983%`
- `S -> SENDRECEIVEDATA.REPLY_DEADLINE`
  - `0 / 57856 = 0.0000%`

结论：

- `S` 不是当前 SQL dump 里的直接业务字段。
- 文件4应把 `S` 视为报表派生值：`F + 20 天`。

### 3. `V` 列的后台稳定落点更像 `SENDRECEIVEDATA.ANSWER_DATE`

之前按 Word 语义，倾向把 `V` 看成 `IICS` 页面“发布日期”。但广泛扫描后，最强 SQL 命中并不在 `IICS` 自身日期字段，而在 `SENDRECEIVEDATA`：

- `V -> SENDRECEIVEDATA.ANSWER_DATE`
  - `49700 / 51877 = 95.8035%`
- `V -> SENDRECEIVEDATA.MODIFIED_ON`
  - `47180 / 51877 = 90.9594%`
- `V -> IICS.RELEASE_DATE`
  - `88 / 51877 = 0.1696%`

结论：

- 若目标是“后台稳定落点”，`V` 当前应优先落到 `SENDRECEIVEDATA.ANSWER_DATE`。
- 这说明前端页面展示语义和数据库真正承载该日期的字段，不一定是同一层对象。

### 4. `P` 列高概率不是直接 SQL 字段，而是同表派生结果

先看文件4原表头：

- `P`：处理方
- `AB`：发布方
- `AC`：接收方

对 `P` 非空的 `72397` 行做同表对比：

- `P = AB`
  - `39215 / 72397 = 54.1666%`
- `P = AC`
  - `33182 / 72397 = 45.8334%`

直接看整体并不稳定，但按 `A(IITF/IICS)` 分流后，规则非常明显：

- 若 `A = IICS`，`P` 更接近 `AB(发布方)`
- 若 `A = IITF`，`P` 更接近 `AC(接收方)`
- 组合规则命中：
  - `65360 / 72397 = 90.2800%`

分组细看：

- `IICS + 发文`：`P = AB` 占 `92.7874%`
- `IICS + 收文`：`P = AB` 占 `85.5700%`
- `IITF + 发文`：`P = AC` 占 `99.9693%`
- `IITF + 收文`：`P = AC` 占 `87.0342%`

结论：

- `P` 更像报表层的派生字段，不像稳定直连某一个 SQL 列。
- 当前可接受的工程规则是：
  - `A = IICS` 时，`P = AB(发布方)`
  - `A = IITF` 时，`P = AC(接收方)`
- 但这仍然不是“直接 SQL 路径定稿”，而是“报表复原规则定稿”。

## 本轮后，文件2/4还剩什么没收口

- 文件2：`M` 仍未定稿；责任人仍缺“最终最底层办理人”的闭环数据。
- 文件4：`AH` 责任人仍缺最终分发链闭环；`F` 虽然已确定是双分支，但 `RELEASE_DATE` 和 `MODIFIED_ON` 的最终取舍还可再收一轮。

## 现阶段建议的口径

- 文件2：
  - 主对象：`A/D -> 传递页 INTINTERFACEDOC`
  - 回复页：`P -> 回复页 INTINTERFACEDOC`
  - `N`：优先落 `reply INTINTERFACEDOC.RELEASE_DATE`
  - `M`：继续保持未定
- 文件4：
  - 主入口：`E -> SENDRECEIVEDATA`
  - `F`：按 `A(IICS/IITF)` 分支，到对应对象日期字段
  - `S`：直接用 `F + 20 天`
  - `V`：优先落 `SENDRECEIVEDATA.ANSWER_DATE`
  - `P`：按 `A` 分支，在报表层由 `AB/AC` 派生
