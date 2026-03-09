# CIMS-SQL-3.5 待处理文件2/4链路核对

## 1. 数据范围

- SQL目录：`example/CIMS-SQL-3.5`
- Excel目录：`example/CIMS-SQL-3.5/EXCEL导出数据`
- 本次重点样本：
  - 文件2：`内部接口信息单报表181820260304.xlsx`
  - 文件4：`外部接口单报表181820260304.xlsx`
- 人员名单匹配范围：`excel_bin` 下全部 4 份名单表合并，合计 `333` 个姓名。

## 2. 工具层修正

- 已修复 [validate_cims_sql_dump.py](/e:/program/PythonProject3/scripts/db_tools/sql_explorer/validate_cims_sql_dump.py)：
  - `parse_create_columns()` 现在支持“纯 INSERT 导出”格式，不再强依赖 `CREATE TABLE`。
- 已增强 [roster.py](/e:/program/PythonProject3/scripts/db_tools/sql_explorer/roster.py)：
  - 新增 `load_all_roster_names()`，可直接合并 `excel_bin/*.xlsx` 全部名单。

## 3. 文件2结论

- 结论一：PDF 对文件2的关键入口判断是对的。
  - `A列(传递单号) -> INTINTERFACEDOC.ITEM_NUMBER`
  - 命中率：`16476 / 16477 = 99.9939%`
- 结论二：新导出的文件2中 `AM` 列依然是空的。
  - 非空数：`0`
  - 这再次证明文件2责任人列不是原生导出列，不能指望从 Excel 反核责任人。
- 结论三：责任人主链仍应定义为“传递单 -> 分发记录”。
  - 主链：`A -> INTINTERFACEDOC.id -> DISTRIBUTERECORD.SOURCE_OBJECT_ID`
  - 但当前 `3.5` 导出包中真正落到 `DISTRIBUTERECORD` 的只有：
  - `465 / 16477 = 2.8221%`
- 结论四：因此文件2现在可以 100%确认“链路方向”正确，但不能宣称“当前 dump 已足够还原全部责任人”。

## 4. 文件4结论

### 4.1 E列不是直接对 IITF.ITEM_NUMBER

- `E -> IITF.ITEM_NUMBER`：`0 / 18385`
- `E -> ICMACP1000.LATEST_FORM_NO`：部分命中
- `E -> ICMACP1000.FINAL_OPEN_NUM / FINAL_CLOSE_NUM`：部分命中
- 直接扫描 `IITF` 全列后，说明 `E` 更像“收发文号入口”，而不是 `IITF` 主编号字段本身。

### 4.2 当前最合理主桥接

- `E -> SENDRECEIVEDATA.(LETTER_SEND_NO / CORRESP_LETTER_REC_NO)`
  - 命中率：`16876 / 18385 = 91.7922%`
- `SEND -> IITF.SEND_RECEIVE_DATA`
  - 命中率：`8270 / 18385 = 44.9823%`
- `SEND -> IICS.SEND_RECEIVE_DATA`
  - 命中率：`15632 / 18385 = 85.0258%`

这说明文件4真正稳定的桥，不是 `E -> IITF.ITEM_NUMBER`，而是：

- `E -> SENDRECEIVEDATA -> IITF`
- `E -> SENDRECEIVEDATA -> IICS`

### 4.3 责任人链

- 按 PDF 语义，责任人主链仍应优先定义为：
  - `E -> SEND -> IITF -> DISTRIBUTERECORD`
- 但当前 dump 中真正落到分发表的只有：
  - `242 / 18385 = 1.3163%`
- 细看对象覆盖：
  - 匹配到的 `IITF` 唯一对象：`8128`
  - 其中在 `DISTRIBUTERECORD` 中出现的唯一对象：`239`

因此：

- 旧结论“文件4分发表命中 0%”已经被新数据推翻；
- 但新结论也很明确：当前 `3.5` 包里，`DISTRIBUTERECORD` 只覆盖了文件4责任人链中的极少数 `IITF` 对象；
- 所以文件4责任人不能只靠分发表恢复全量。

### 4.4 文件4 AH 列最佳回退字段

在“非空 AH 行”上，当前最强的 SQL 直字段候选是：

- `IICS.CREATED_BY_ID`
  - 命中：`3787 / 9086 = 41.6795%`

其他候选明显更弱：

- `ICMACP1000.DEPART_USER`（经 `LATEST_FORM_NO / FINAL_*_NUM` 桥接）约 `18.3% ~ 18.9%`
- `IITF.CREATED_BY_ID`：`809 / 9086 = 8.9038%`
- `DISTRIBUTERECORD` 上的 `last OPERATOR`：`62 / 9086 = 0.6824%`

因此当前文件4责任人建议口径是：

- 主链：`E -> SEND -> IITF -> DISTRIBUTERECORD.OPERATOR`
- 主链仅在少量样本可用；
- 回退链：`E -> SEND -> IICS.CREATED_BY_ID`

这条回退链虽然还不够最终版，但已经显著优于旧的 0% 方案。

### 4.5 文件4 V 列完成判定

PDF 说：

- `V` 来源于 `IICS` 页的“发布日期”

新数据验证后，这个方向是成立的，且强相关：

- `E -> SEND -> IICS.RELEASE_DATE`
  - 与 Excel 非空 `V` 重合：`11793 / 13063 = 90.2779%`
- `E -> SEND -> IICS.CREATED_ON`
  - 与 Excel 非空 `V` 重合：`11810 / 13063 = 90.4080%`
- `E -> SEND -> IICS.ICM_DATE`
  - 与 Excel 非空 `V` 重合：`11253 / 13063 = 86.1441%`

结论：

- 文件4的完成判定主链，已经基本可以落到：
  - `E -> SEND -> IICS.RELEASE_DATE`
- 若以“覆盖率优先”作为工程实现口径，则 `IICS.CREATED_ON` 目前略高于 `RELEASE_DATE`。
- 若以“字段语义与 PDF 页面标签一致”为优先，则 `RELEASE_DATE` 更符合“发布日期”表述。

## 5. 当前可执行结论

### 文件2

- 入口主键：`A -> INTINTERFACEDOC.ITEM_NUMBER`
- 责任人主链定义：`A -> INT -> DISTRIBUTERECORD`
- 但当前 dump 仅能覆盖极少数分发记录，不能全量恢复责任人。

### 文件4

- `E` 的正确桥接入口不是 `IITF.ITEM_NUMBER`
- 当前最稳桥接：
  - `E -> SENDRECEIVEDATA`
  - 再分别到 `IITF` / `IICS`
- 完成判定：
  - 优先考虑 `E -> SEND -> IICS.RELEASE_DATE`
  - 工程上也可记录 `IICS.CREATED_ON` 作为高覆盖备选
- 责任人：
  - 主链仍是 `E -> SEND -> IITF -> DISTRIBUTERECORD`
  - 当前 dump 不足以全量恢复
  - 回退链当前最佳是 `E -> SEND -> IICS.CREATED_BY_ID`

## 6. 仍缺的关键信息

- 如果目标是把文件4 `AH` 责任人列做成高覆盖、稳定可落地口径，当前还缺至少其一：
  - 更完整的 `DISTRIBUTERECORD` 历史/全量导出
  - 或者其它承载“当前办理人/分发末级办理人”的业务表
  - 或者页面对应的工作流/任务表导出

在现有 `3.5` 数据包下，可以明确把“0%命中”修正为“链路已找到，但分发表覆盖不足”，这是本轮最重要结论。
