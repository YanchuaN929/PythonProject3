# CIMS-SQL-3.5 / 3.7 SQL运行链统一汇总（2026-03-11）

## 1. 适用范围

- 核心探测范围固定为：
  - `E:\program\PythonProject3\example\CIMS-SQL-3.5`
  - `E:\program\PythonProject3\example\CIMS-sql-3.7`
- Excel 模板一律以整合版为准：
  - `E:\program\PythonProject3\example\CIMS-SQL-3.5\EXCEL导出数据`

## 2. 证据优先级

当不同文档之间出现冲突时，统一按以下优先级收敛：

1. `example/CIMS系统中各接口号的具体使用路线.docx`
2. `example/CIMS-SQL-3.5/EXCEL导出数据` 整合版样本
3. `example/CIMS-SQL-3.5` 基础业务表
4. `example/CIMS-sql-3.7` 流程增量表

## 3. 最终统一运行链

### 3.1 文件1：内部需打开接口

运行链：

1. Excel `A(接口号)` -> `IDIACP1000.ITEM_NUMBER`
2. 业务字段：
   - `H -> RELEASE_PARTY`
   - `K -> SWAP_START_DATE`
   - `M -> ACTUAL_OPEN_DATE`
   - `R -> DEPART_USER -> USER/DEPARTMENT`

结论：

- 文件1主对象链已稳定
- 责任人只剩少量别名/占位账号清洗问题，不影响 SQL 主链

### 3.2 文件2：内部需回复接口

文件2必须拆成 3 层对象理解：

1. 接口主对象：
   - `R -> INTINTERFACEDOCIDIACP1000 -> IDIACP1000.ITEM_NUMBER`
2. 传递页对象：
   - `A/D -> current INTINTERFACEDOC`
   - `B -> current INTINTERFACEDOC.SUBMIT_DATE`
   - `M -> B + 14天`
3. 回复页对象：
   - `P -> reply INTINTERFACEDOC`
   - `N -> reply INTINTERFACEDOC.RELEASE_DATE`

责任人链：

- 业务真值方向：
  - `传递页 -> 分发信息 -> 最终最底层办理人`
- 当前 SQL 现状：
  - `INT -> WORKFLOWPROCESSESBIND` 覆盖高
  - `INT -> USERVOTERECORD` 覆盖中等
  - `INT -> DISTRIBUTERECORD` 在当前快照中为 `0`
- 当前工程回退：
  - `INTINTERFACEDOC.MODIFIED_BY_ID -> USER`

结论：

- 文件2现在只剩责任人链未闭环
- `B/M/N` 时间链已可定稿

### 3.3 文件3：外部需打开接口

运行链：

1. Excel `C(接口编码)` -> `ICMACP1000.ITEM_NUMBER`
2. 主页面字段：
   - `I -> RELEASE_PARTY`
   - `AL -> RESP_DEPART`
   - `L -> PRE_FORECAST_DATE`
   - `M -> FINAL_FORECAST_DATE`
3. 交换信息字段：
   - `Q -> PRE_OPEN_DATE`
   - `T -> FINAL_OPEN_DATE`
4. 责任人语义：
   - `AP` 为所内编制人
   - 若 `AP` 为空，则走管理员提醒逻辑，该逻辑不完全留存在 CIMS 库中

结论：

- 文件3主对象链清晰
- `L/M/Q/T` 的业务语义已按 Word 与样本表头锁定
- 但 `AP` 仍不能宣称已全量 SQL 闭环

### 3.4 文件4：外部需回复接口

文件4必须拆成“收发文桥 + 二级对象 + 分发表/派生值”三层：

1. 主入口桥：
   - `E -> SENDRECEIVEDATA.LETTER_SEND_NO`
   - `CORRESP_LETTER_REC_NO` 仅作辅助命中
2. 二级对象：
   - `SEND -> IICS`
   - `SEND -> IITF`
3. 业务字段：
   - `F`：
     - 业务语义来自 `IITF/IICS` 页面发布/提交事件
     - 当前稳定工程字段为 `A分支 -> IICS/IITF.MODIFIED_ON`
     - `RELEASE_DATE` 为近似备选
   - `S = F + 20天`
   - `V -> SENDRECEIVEDATA.ANSWER_DATE`
   - `P`：
     - `A = IICS -> AB(发布方)`
     - `A = IITF -> AC(接收方)`
4. 责任人 `AH`：
   - 业务真值：
     - `项目号 + W(接口编码路由码) -> DISTRIBUTERECORD.BO_TITLE`
     - 在 `IITF/IICS` 分发表中取最末级办理人
     - 叶子多人时任一命中即算命中
   - 当前工程实现：
     1. `IITF leaf`
     2. 否则 `IICS leaf`
     3. 否则 `IICS.CREATED_BY_ID`

结论：

- 文件4主桥已经稳定定稿为 `SENDRECEIVEDATA`
- `AH` 的业务真值与工程回退已经分层定稿
- 当前最大硬缺口仍是部分路由没有分发表记录，尤其 `1915`

### 3.5 文件5：三维提资接口

- 当前没有稳定 SQL 主链
- 不纳入本轮统一定稿范围

### 3.6 文件6：收发文函

文件6当前统一按 Word 版说明、7 项目整合样本、`CIMS-SQL-3.5 / 3.7` SQL 快照，以及已合并后的 `document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md` 收口：

1. 总路由：
   - `E` 含 `-ZL-` 的接口单样式，走 `INTINTERFACEDOC`
   - 常规文函号与 `BW` 特殊号，走 `SENDRECEIVEDATA`
   - 当前总覆盖 `4001 / 4178 = 95.7635%`
2. `INT` 分支：
   - `E -> INTINTERFACEDOC.ITEM_NUMBER`
   - `I -> INTINTERFACEDOC.REPLY_DEADLINE`
   - `J -> INTINTERFACEDOC.ANSWER_DATE`
   - `M -> ANSWER_DATE / REPLY_DEADLINE` 派生状态
3. `SEND` 分支：
   - `E -> SENDRECEIVEDATA.(CORRESP_LETTER_REC_NO / LETTER_SEND_NO)`
   - `I -> SENDRECEIVEDATA.REPLY_DEADLINE`
   - `J -> SENDRECEIVEDATA.ANSWER_DATE`
   - `M -> ANSWER_DATE / REPLY_DEADLINE / IS_ANSWERED` 派生状态
4. 本轮修正后的分发表语义：
   - `X` 不是“最末级单人责任人”，而是 Excel 中记录的“分发全过程办理人并集”
   - `V/W` 也不是单点落位值，而是这些办理人对应的单位/科室并集
   - 命中规则统一为：Excel 多值与 SQL 分发表全链多值之间，只要任一交集命中即算命中
5. 分发表与流程表探针结论：
   - `DISTRIBUTERECORD` 侧：
     - 已新增 `INTINTERFACEDOC` 全链展开、紧凑标题码提取、`SOURCE_OBJECT_ID + BO_TITLE` 双桥探测
     - `DISTRIBUTERECORD.statement_count = 2372886`
     - `matched_count = 582`
     - `group_count = 116`
     - 旧的“文件6分发表完全 0 命中”已经被推翻，但命中仍几乎只落在 `INT` 分支：
       - `INT X = 2 / 1055 = 0.1896%`
       - `INT V = 14 / 1055 = 1.3270%`
       - `INT W = 3 / 999 = 0.3003%`
       - `SEND X/V/W = 0`
   - `WORKFLOWPROCESSESBIND / USERVOTERECORD` 侧：
     - 已确认 `SEND` 分支不能再只追 `DISTRIBUTERECORD`
     - 对版本最佳 `SEND` 样本 `2958` 行，已有 `1413` 行能落到 workflow/vote
     - 基于 workflow/vote 的并集命中：
       - `X = 409 / 2958 = 13.8310%`
       - `V = 1098 / 2958 = 37.1021%`
       - `W = 560 / 2958 = 18.9542%`
6. 类型级主链：
   - `备忘录 / 图文传真`：`OBJECTREPLYLINK -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
   - `文件传递单 / TA / CR / NCR`：`主对象(FILETRANSMISSION / TA / CR / NCR) -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
   - `DISTRIBUTERECORD` 对文件6发送侧只保留为补充链，不再作为主链
7. 当前收口：
   - 文件6 `A` 列确实是对象族信号，不同文函类型存在不同存储逻辑
   - 当前主缺口已经收窄到尚未导出的主表类型：
     - `MEMORANDUM`
     - `TELEFAX`
     - `INTERNALMINUTES`
     - `EXTERNALMINUTES`
     - `FUNOTIFY`
     - `CANCELNOTIFY`
     - `DESIGNREVIEWOPNION`
     - `DESIGNREVIEWREPLY`
     - `FCR`
   - `H` 本轮暂不继续追
8. 最新专题见：
   - `document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md`

## 4. 与我当前完整运行链的自检结果

对照本轮重新整理后的完整链路，当前已收敛到以下一致状态：

- 文件1：一致
- 文件2：一致
- 文件4：一致
- 文件6：一致

唯一发现并修正的冲突是：

- 文件3在 `7` 号文件里曾把 `L/M` 误写成打开日期链
- 最新统一口径已改正为：
  - `L/M -> PRE_FORECAST_DATE / FINAL_FORECAST_DATE`
  - `Q/T -> PRE_OPEN_DATE / FINAL_OPEN_DATE`

## 5. 最终结论

- 本文件作为当前统一收口版本
- 后续若再出现旧文档与新结论冲突，应优先以本文件和 `7` 号总表的最新版本为准
- 当前剩余未闭环的核心问题只有：
  - 文件2责任人最终链
  - 文件3 `AP` 的库内完全闭环
  - 文件4缺失路由样本的真实下游对象
  - 文件6 `X/V/W/AC/H` 的剩余未闭环项
