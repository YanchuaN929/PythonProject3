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

当前保留双分支口径：

1. 接口单型键：
   - `E` 为 `1818-5-...` 类时，走 `INTINTERFACEDOC`
2. 文函型键：
   - `E` 为 `EDMB/ECZB/EFZX/...` 类时，走 `SENDRECEIVEDATA`

说明：

- 文件6不在本轮主攻范围内
- 但其双分支路径与 `7` 号文件现口径一致，可继续保留

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
