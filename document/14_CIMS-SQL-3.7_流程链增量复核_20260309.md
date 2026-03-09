# CIMS-SQL-3.7 流程链增量复核（2026-03-09）

## 1. 数据范围

- 基础 SQL：`example/CIMS-SQL-3.5`
- 增量 SQL：`example/CIMS-sql-3.7`
- 合并工作目录：`tmp/cims_sql_merged_20260309`
- Excel 样本：
  - 文件2：`example/CIMS-SQL-3.5/EXCEL导出数据/内部接口信息单报表181820260304.xlsx`
  - 文件4：`example/CIMS-SQL-3.5/EXCEL导出数据/外部接口单报表181820260304.xlsx`
- 本轮原始输出：
  - 基线旧链路：`tmp/distribution_chain_real_probe_20260309`
  - 新表增量：`tmp/distribution_chain_v37_increment_20260309.json`

## 2. 方法说明

- 先用旧离线探针在合并目录上重跑，确认 `3.5 + 3.7` 的无后缀表名目录可正常工作。
- 再从基础表提取文件2/4相关对象 ID / CONFIG_ID，生成 `34432` 个精确匹配 token。
- 使用 `rg -F -f` 对两张超大流程表做预筛：
  - `WORKFLOWPROCESSESBIND` 过滤后剩 `23409` 行
  - `USERVOTERECORD` 过滤后剩 `74775` 行
- 在过滤结果上做增量解析，避免全量重复扫描 8G 级大表。

## 3. 文件2结论

### 3.1 链路覆盖

- `Excel(A,D) -> INTINTERFACEDOC`：`7586 / 7586 = 100.0000%`
- `INT -> WORKFLOWPROCESSESBIND`：`6195 / 7586 = 81.6636%`
- `INT -> USERVOTERECORD`：`3993 / 7586 = 52.6364%`

### 3.2 语义判断

- `WORKFLOWPROCESSESBIND` 的来源类型单一落在：`extra.cnpe.entity.internalInterface.ExtIntInterfaceDoc`
- `USERVOTERECORD` 中活动名主要是：`编制 / 校对 / 审核 / 审定 / 批准`
- 这说明文件2的“内部接口单 -> 流程实例 / 投票记录”链路已经被确认，不再只是猜测。

### 3.3 责任人口径

- 由于文件2 `AM` 本轮仍为空，无法用 Excel 反校责任人。
- 当前更稳的工程口径仍是：`INTINTERFACEDOC.MODIFIED_BY_ID`
- `USERVOTERECORD.OPERATOR` 已经证明流程链存在，但现阶段不能宣称它就是报表责任人最终口径。

## 4. 文件4结论

### 4.1 入口桥接

- `SEND -> IICS`：`15632 / 18385 = 85.0258%`
- `IICS -> WORKFLOWPROCESSESBIND`：`15631 / 15632 = 99.9936%`
- `IICS -> USERVOTERECORD`：`13837 / 15632 = 88.5171%`

- `SEND -> IITF`：`8270 / 18385 = 44.9823%`
- `IITF -> WORKFLOWPROCESSESBIND`：`8270 / 8270 = 100.0000%`
- `IITF -> USERVOTERECORD`：`7121 / 8270 = 86.1064%`

### 4.2 被排除的链路

- `SEND -> FILETRANSMISSION`：`0 / 18385 = 0.0000%`
- 因此本轮样本中，`FILETRANSMISSION` 不是文件4责任人主链的有效桥。
- `FILETRANSMISSIONDESIGNDOC` 预筛结果为 `0` 行，也排除了它作为当前文件4责任人直接来源的可能性。

### 4.3 责任人候选强度

以文件4 `AH` 为对照，当前主要候选结果如下：

- `IICS.CREATED_BY_ID`：`3869 / 9086 = 42.5820%`
- `IICS -> WORKFLOWPROCESSESBIND.CREATED_BY_ID`：`3863 / 9086 = 42.5160%`
- `IICS -> WORKFLOWPROCESSESBIND.MODIFIED_BY_ID`：`3865 / 9086 = 42.5380%`
- `IITF.CREATED_BY_ID`：`809 / 9086 = 8.9038%`
- `union(IICS,IITF,FT) -> USERVOTERECORD.OPERATOR`：`218 / 9086 = 2.3993%`
- `IICS -> USERVOTERECORD.OPERATOR`：`202 / 9086 = 2.2232%`

### 4.4 语义判断

- 新流程表已经把“文件4对象确实挂在流程里”这件事证明清楚了。
- 但它们没有把责任人命中率抬高到超过 `IICS.CREATED_BY_ID`。
- 这意味着：
  - `WORKFLOWPROCESSESBIND` / `USERVOTERECORD` 更像“流程连续性证据”
  - 文件4 `AH` 的报表语义，当前更接近 `IICS` 对象层的创建/归属口径，而不是“最新流程操作人”

## 5. 当前定稿建议

### 文件2

- 主入口：`(A,D) -> INTINTERFACEDOC`
- 链路证据：`INT -> WORKFLOWPROCESSESBIND / USERVOTERECORD` 已成立
- 当前责任人口径：仍保留 `INTINTERFACEDOC.MODIFIED_BY_ID` 作为稳定工程口径

### 文件4

- 主入口：`E -> SENDRECEIVEDATA -> IICS`
- `IITF` 是次级补充桥，不是主桥
- `FILETRANSMISSION` 在当前样本中可排除
- 当前责任人口径：`IICS.CREATED_BY_ID`
- 流程表结论：可用于证明链路和解释流程状态，但不能替代 `IICS.CREATED_BY_ID` 成为更强责任人字段

## 6. 本轮最重要的新信息

- 旧问题“是不是缺流程链”已经有答案：**不缺，链已经找到，而且覆盖很高。**
- 真正剩下的问题不是“找不到流程”，而是：**报表 `AH` 的业务语义并不等于最新流程操作人。**
- 因此后续如果还要继续抬高文件4 `AH` 命中率，优先级应转向：
  - 页面/API 上真正用于生成责任人列的对象归属逻辑
  - 或其它显式“承办/主办/责任人”字段来源
  - 而不是继续深挖 `USERVOTERECORD.OPERATOR`
