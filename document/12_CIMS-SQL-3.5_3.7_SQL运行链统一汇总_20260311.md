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
4. `2026-03-21` 起，文件6必须并行保留两套口径：
   - `Word 严格口径`：`X` 只看页面“分发信息/办理链”中的当前或最末级办理人；`V/W` 仅作为这些办理人的组织展示
   - `工程复合口径`：仅用于评估 SQL 对 Excel 的可恢复度，不代表 Word 权威流程
   - 若两套口径冲突，以 `Word 严格口径` 为准
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
     - `2026-03-21` 按 Word 严格口径重跑 `leaf/latest-leaf` 后，版本最佳 `4003` 行里只有 `23` 行真正打到 leaf operator：
       - `X_leaf_union = 0 / 1966 = 0`
       - `V_leaf_union = 10 / 1966 = 0.5086%`
       - `W_leaf_union = 1 / 1458 = 0.0686%`
     - 这说明文件6发送侧不能把 Word 里的“分发信息页面”机械等同成 `DISTRIBUTERECORD leaf`
   - `WORKFLOWPROCESSESBIND / USERVOTERECORD` 侧：
     - 已确认 `SEND` 分支不能再只追 `DISTRIBUTERECORD`
      - 在补齐 `MEMORANDUM / TELEFAX / EXTERNALMINUTES / FUNOTIFY / CANCELNOTIFY / DESIGNREVIEWOPNION / DESIGNREVIEWREPLY` 等主表后，对版本最佳 `SEND` 样本 `2958` 行，已有 `2254` 行能落到 workflow/vote
      - 按 Excel 非空字段计算交集命中：
        - `X = 144 / 911 = 15.8068%`
        - `V = 447 / 911 = 49.0670%`
        - `W = 106 / 459 = 23.0937%`
     - `2026-03-21` 按 Word 严格口径只在当前/有效办理链中重算时，发送侧基线为：
       - `vote_all`: `X = 165 / 911 = 18.1120%`，`V = 384 / 911 = 42.1515%`，`W = 110 / 459 = 23.9651%`
       - `vote_valid`: `X = 163 / 911 = 17.8924%`，`V = 384 / 911 = 42.1515%`，`W = 110 / 459 = 23.9651%`
       - `active_plus_valid`: `X = 163 / 911 = 17.8924%`，`V = 463 / 911 = 50.8233%`，`W = 123 / 459 = 26.7974%`
     - 这比 `DISTRIBUTERECORD leaf` 明显更像 Word 所说的“办理链”
6. 类型级主链：
   - `备忘录 / 图文传真`：`OBJECTREPLYLINK + 主对象(MEMORANDUM / TELEFAX) -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
   - `文件传递单 / TA / CR / NCR`：`主对象(FILETRANSMISSION / TA / CR / NCR) -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
   - `审查意见单 / 审查意见答复单`：`DESIGNREVIEWOPNION / DESIGNREVIEWREPLY -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
   - `FU通知单 / 作废通知单 / 外发纪要`：`主对象(FUNOTIFY / CANCELNOTIFY / EXTERNALMINUTES) -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
   - `DISTRIBUTERECORD` 对文件6发送侧只保留为补充链，不再作为主链
7. 当前收口：
   - 文件6 `A` 列确实是对象族信号，不同文函类型存在不同存储逻辑
   - 原缺主表已补齐，当前主缺口改为：
     - `INTERNALMINUTES / FCR` 仍无有效 send link
     - `FU通知单 / 作废通知单` 虽已打到 workflow/vote，但 `X/V/W` 仍无稳定交集
     - `审查意见单 / 审查意见答复单 / 外发纪要` 已部分命中，但 `X/V/W` 仍未到可上线口径
   - `H` 本轮暂不继续追
8. 最新专题见：
   - `document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md`

### 3.7 2026-03-13 文件6补充

- 在补齐主表之后，文件6发送侧又补上了“主对象内部 `relation_ids` 递归展开”这一步
- 最新结果文件：
  - `document/file6_send_workflow_probe_20260313_rel4.json`
  - `document/file6_distribution_chain_probe_20260313_rel2.json`
- `WORKFLOWPROCESSESBIND / USERVOTERECORD` 最新命中：
  - `rows_with_workflow_hits = 2258 / 2958`
  - `X = 165 / 911 = 18.1120%`
  - `V = 498 / 911 = 54.6652%`
  - `W = 138 / 459 = 30.0654%`
- 本轮最大增量来自：
  - `审查意见答复单 -> DESIGNREVIEWREPLY -> DESIGNREVIEWOPNION -> FILETRANSMISSION -> workflow/vote`
  - 该类型已提升到 `X = 24 / 25`、`V = 25 / 25`、`W = 21 / 21`
- 同日类型增强补充：
  - `图文传真 -> workflow/vote + TELEFAX.CREATED_BY_ID + TELEFAX.MODIFIED_BY_ID`
  - `备忘录 -> workflow/vote + MEMORANDUM.CREATED_BY_ID + MEMORANDUM.MODIFIED_BY_ID`
  - `文件传递单 -> workflow/vote + FILETRANSMISSION.MODIFIED_BY_ID`
  - 三类合计把发送侧 `V` 再抬升 `+35`、`W` 再抬升 `+15`
- `DISTRIBUTERECORD` 复跑后发送侧仍为 `SEND X/V/W = 0`
- `SSC_RELATED_DATA` 已快筛排除：
  - 发送侧抽出 `661` 个 `SSC_RELATED_DATA`
  - 在 `WORKFLOWPROCESSESBIND / USERVOTERECORD` 中命中 `0`

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
## 2026-03-17 补充：文件6 `TA / CR` 新主链判断

本轮补充探针 `scripts/db_tools/sql_explorer/file6_type_author_route_probe.py` 表明，文件6发送侧 `TA / CR` 不宜继续按 `workflow/vote -> 办理人` 作为主链理解。

更合理的链路是：

- `SENDRECEIVEDATA.AUTHOR_UNIT / LETTER_SEND_NO prefix`
- `-> 内部责任所室分流`
- `-> USER / DEPARTMENT 派生 Excel X/V/W`

留一交叉验证结果见 `document/file6_type_author_route_probe_20260317.json`：

- `TA`：`X 41/80`，`V 39/80`，`W 20/24`
- `CR`：`X 28/49`，`V 28/49`，`W 12/17`

因此，文件6发送侧后续不应再追求“所有类型都塞进同一条 workflow 链”，而应至少拆分出：

- `workflow/vote` 类型链
- `author-routing` 类型链

### 2026-03-17 rel2 补充：TA / CR 稳定策略细化

在 `document/file6_type_author_route_probe_20260317.json` 的基础上，继续将 `TA / CR` 的 author-routing 预测口径从“整串 `V/W` 众数”改成“`V/W` token 众数（top3）”，输出见：

- `document/file6_type_author_route_probe_20260317_rel2.json`

这轮得到的更稳结论是：

- 推荐稳定策略：`prefix_token_top3`
- `TA`：`X 48/80`，`V 48/80`，`W 20/24`
- `CR`：`X 30/49`，`V 30/49`，`W 12/17`

相对上一版 author/prefix 留一验证：

- `TA`：`X +7`、`V +9`
- `CR`：`X +2`、`V +2`

同时确认一条不能直接产品化的实验回退：

- 当 `prefix_token_top3` 无同类样本时，若直接回退 `workflow_org_values / workflow_office_values`，指标会被进一步抬高
- 但预测人员范围会膨胀到 `TA` 平均约 `2124` 人、`CR` 平均约 `2893` 人，最大达到 `6848` 人
- 因此该路径只能作为探索信号，不能作为文件6同步 Excel 的稳定业务口径

### 2026-03-17 rel3 补充：TA / CR 跨类型共享前缀池

继续寻找稳定补强路线后，确认 `TA / CR` 可以共享同一套前缀样本池，而不必各自孤立拟合。新报告见：

- `document/file6_type_author_route_probe_20260317_rel3.json`

这条新路线的推荐稳定策略为：`cross_type_prefix_token_top3`

- `TA`：`X 51/80`，`V 52/80`，`W 20/24`
- `CR`：`X 37/49`，`V 37/49`，`W 13/17`

相对 `rel2`：

- `TA`：`X +3`、`V +4`
- `CR`：`X +7`、`V +7`、`W +1`

这说明对 `TA / CR` 来说，除了单类型 author-routing，还应增加一层“跨类型共享前缀映射”的稳定策略；它比 workflow fallback 更可信，因为候选人员范围仍保持在 `TA 163.27 / CR 151.20` 的量级，没有出现数千人的范围膨胀。

### 2026-03-17 rel4 补充：共享前缀家族不是全量共池，而是选择性接入

补充探针 [file6_shared_prefix_family_probe.py](e:/program/PythonProject3/scripts/db_tools/sql_explorer/file6_shared_prefix_family_probe.py) 的输出见：

- `document/file6_shared_prefix_family_probe_20260317.json`

该探针按“共享前缀数 >= 6”自动构建文种图，最大连通簇包含：

- `CR`
- `TA`
- `文件传递单`
- `IITF`
- `FU通知单`
- `IICS`
- `TA回复单`
- `图文传真`
- `审查意见单`
- `审查意见答复单`

它带来的关键结论是：

- `TA / CR` 在大簇共池下还能继续提升
  - `TA`：`X 59/80`，`V 60/80`，`W 20/24`
  - `CR`：`X 39/49`，`V 38/49`，`W 13/17`
- `文件传递单`、`审查意见答复单`、`FU通知单` 也有不同程度正向增量
- `审查意见单` 反而明显下降，因此不能被简单并入该共池

所以这条路线不能被理解成“共享前缀的大簇全部一起跑”，而应理解成：

- 先找共享前缀家族
- 再按类型逐个验证是否适合接入该家族池

### 2026-03-18 rel5 补充：共享前缀家族应继续收缩为 donor-selective 矩阵

补充探针 [file6_prefix_donor_probe.py](e:/program/PythonProject3/scripts/db_tools/sql_explorer/file6_prefix_donor_probe.py) 的输出见：

- `document/file6_prefix_donor_probe_20260318.json`

这轮不是再扩大“共享前缀家族”，而是反过来问：

- 对每个文种来说，是否只需要借少数 donor 类型，就能达到甚至逼近 rel4 大簇共池的效果

结果是肯定的，而且比“大簇统一共池”更适合落地：

- `TA <- CR + 文件传递单`
  - `X 48/80 -> 59/80`
  - `V 48/80 -> 60/80`
  - `W 20/24 -> 20/24`
  - 命中率与 rel4 大簇共池一致，但平均候选范围收敛到 `202.93`
- `CR <- TA + 文件传递单`
  - `X 30/49 -> 39/49`
  - `V 30/49 -> 38/49`
  - `W 12/17 -> 13/17`
  - 同样达到 rel4 大簇共池效果，平均候选范围约 `191.40`
- `文件传递单 <- TA + 审查意见答复单`
  - `X 302/425 -> 310/425`
  - `V 308/425 -> 316/425`
  - `W 180/238 -> 185/238`
- `审查意见答复单 <- 文件传递单`
  - `X 21/25 -> 25/25`
  - `V 21/25 -> 25/25`
  - `W 13/21 -> 15/21`
- `FU通知单 <- 文件传递单`
  - `X 3/4 -> 4/4`
  - `V 3/4 -> 4/4`
  - `W 3/3 -> 3/3`

同时也确认了几条边界：

- `审查意见单` 没有正向 donor 增量，应继续保持独立口径
- `备忘录` 没有正向 donor 增量，当前缺口不在 prefix donor
- `图文传真 / 外发纪要 / NCR` 虽有正向 donor 信号，但仍偏弱或样本偏小，暂列候选补强

因此，文件6 发送侧的 prefix-routing 思路应继续从“共享前缀家族”收敛为“按类型维护 donor-selective 矩阵”，而不是把整个家族池一起接入生产口径。

### 2026-03-18 rel6 补充：donor 矩阵还要继续细化到 token 宽度

补充探针 [file6_prefix_token_width_probe.py](e:/program/PythonProject3/scripts/db_tools/sql_explorer/file6_prefix_token_width_probe.py) 的输出见：

- `document/file6_prefix_token_width_probe_20260318.json`

这轮是在 rel5 的 donor 矩阵上继续搜索 `v_topn / w_topn = 1..5`。结果说明：

- donor 类型确定之后，`top3/top3` 仍然不是所有类型的最优口径
- 有些类型能继续增加命中
- 有些类型虽然命中不变，但能明显收缩候选范围

当前最值得直接吸收的结果是：

- `文件传递单 <- TA + 审查意见答复单`
  - `v_topn = 5`，`w_topn = 3`
  - `X 310/425 -> 315/425`
  - `V 316/425 -> 322/425`
  - `W 185/238 -> 185/238`
- `审查意见答复单 <- 文件传递单`
  - `v_topn = 3`，`w_topn = 4`
  - `X 25/25 -> 25/25`
  - `V 25/25 -> 25/25`
  - `W 15/21 -> 16/21`
- `外发纪要 <- 图文传真`
  - `v_topn = 1`，`w_topn = 5`
  - `X 4/9 -> 5/9`
  - `V 4/9 -> 4/9`
  - `W 2/5 -> 3/5`
  - 同时平均候选范围还从 `355.00` 降到 `338.43`

另外，以下类型虽然命中不再上涨，但范围能继续收缩：

- `TA <- CR + 文件传递单`：`3/1`
- `CR <- TA + 文件传递单`：`3/1`
- `FU通知单 <- 文件传递单`：`2/1`
- `NCR <- 文件传递单`：`3/1`

边界也更清楚了：

- `图文传真 <- 外发纪要 + 审查意见单` 在 `5/4` 下确实能继续提升，但平均候选范围会明显膨胀，因此目前只宜保留为实验策略
- 文件6 发送侧的 prefix-routing 已不应再写成固定 `top3/top3`，而应改成“类型 donor 矩阵 + 类型 token 宽度矩阵”

### 2026-03-18 rel7 补充：进一步收敛到 prefix-selective boost

补充探针 [file6_prefix_selective_boost_probe.py](e:/program/PythonProject3/scripts/db_tools/sql_explorer/file6_prefix_selective_boost_probe.py) 的输出见：

- `document/file6_prefix_selective_boost_probe_20260318.json`

这轮继续问的不是“哪个类型该用什么 donor / topn”，而是：

- 是否真的要把整类文种都一起放宽
- 还是只需要对少数 prefix 单独放宽

结果很明确：

- `文件传递单` 的 `5/3` 增量只集中在 `JAPDB / FAPAK / FAPBH / SMPCJ`
  - 仅这 4 个 prefix 放宽到 `5/3`，其他 prefix 保持 `3/3`
  - 就能保留 `X 315/425, V 322/425, W 185/238`
  - 且平均候选范围从 rel6 的 `197.88` 再降到 `191.19`
- `审查意见答复单` 的 `3/4` 增量只集中在 `EDES`
  - 仅 `EDES -> 3/4`
  - 即可保留 `X 25/25, V 25/25, W 16/21`
  - 平均候选范围从 `316.45` 再降到 `298.27`
- `图文传真` 终于可以拆成“稳定版 / 实验版”
  - 实验版：`ECZB / ECZS / YBANY / FADGB -> 5/4`
    - `X 85/115, V 83/115, W 56/66`
    - 平均候选范围 `300.55`
  - 稳定版：在 `110%` scope 约束下，仅 `ECZB / ECZS -> 5/4`
    - `X 84/115, V 82/115, W 55/66`
    - 平均候选范围 `287.45`
- `外发纪要` 虽然增量集中在 `YBANY`，但 prefix-selective 反而不如 rel6 的全量 `1/5` 收敛
  - 所以该类型当前应保留全量 `1/5`，不要再细到 prefix

同时也确认：

- `TA / CR / FU通知单 / NCR` 当前不需要继续细到 prefix 级，保留全类型 token 宽度即可

因此，文件6 发送侧的 prefix-routing 已经从“donor 矩阵 + token 宽度矩阵”进一步收敛到“类型矩阵 + 必要时的 prefix-selective boost”。这已经比最早的统一 `workflow/vote` 思路精细得多，也更接近可工程化同步 Excel 的形态。

### 2026-03-21 rel8 补充：文件6 发送侧全量复合仿真

补充脚本 [file6_composite_simulation.py](e:/program/PythonProject3/scripts/db_tools/sql_explorer/file6_composite_simulation.py) 的输出见：

- `document/file6_composite_simulation_20260321.json`

这轮不是再看单项探针，而是把当前有效规则全部复合后，对文件6发送侧全量样本做 leave-one-out 仿真。

总盘结果是：

- `workflow-only`
  - `X = 165 / 911 = 18.1120%`
  - `V = 498 / 911 = 54.6652%`
  - `W = 138 / 459 = 30.0654%`
- `stable composite`
  - `X = 615 / 911 = 67.5082%`
  - `V = 739 / 911 = 81.1196%`
  - `W = 350 / 459 = 76.2527%`
- `experimental composite`
  - `X = 616 / 911 = 67.6180%`
  - `V = 740 / 911 = 81.2294%`
  - `W = 351 / 459 = 76.4706%`

这说明：

- 当前复合规则体系相比纯 `workflow/object` 主链，已经有数量级上的提升
- `stable composite` 已经拿到绝大多数收益
- `experimental composite` 相比 `stable` 只多出 `X/V/W = +1/+1/+1`，边际增量很小

主要贡献类型是：

- `文件传递单`
  - 复合后到 `X 317/425, V 363/425, W 191/238`
- `TA`
  - 复合后到 `X 59/80, V 67/80, W 20/24`
- `图文传真`
  - 复合后到 `X 92/115, V 103/115, W 60/66`
- `CR`
  - 复合后到 `X 39/49, V 41/49, W 14/17`

因此，当前最值得推进的工程方向已经很明确：

- 把 `stable composite` 作为文件6 发送侧的首选工程口径
- 继续把 `experimental composite` 仅保留为对比验证口径

### 2026-03-21 rel9 补充：Word 严格口径复核

这轮新增两份专门的 strict 探针：

- `scripts/db_tools/sql_explorer/file6_word_strict_probe.py`
  - 输出：`document/file6_word_strict_probe_20260321.json`
- `scripts/db_tools/sql_explorer/file6_word_workflow_probe.py`
  - 输出：`document/file6_word_workflow_probe_20260321.json`

它们的用途不是继续抬高 Excel 拟合率，而是验证：当前链路到底有没有背离 Word 权威流程。

结论已经很清楚：

1. 如果把 Word 的“分发信息”严格等同成 `DISTRIBUTERECORD leaf/latest-leaf`：
   - 版本最佳 `4003` 行里，只有 `23` 行真正打到 leaf operator
   - `X = 0 / 1966 = 0`
   - `V = 10 / 1966 = 0.5086%`
   - `W = 1 / 1458 = 0.0686%`
   - 因此这条链不能代表文件6发送侧的 Word 严格责任人主链
2. 如果把 Word 的“办理链”理解成页面里的当前/有效流程办理人：
   - `vote_all`: `X = 165 / 911 = 18.1120%`
   - `vote_valid`: `X = 163 / 911 = 17.8924%`
   - `active_plus_valid`: `X = 163 / 911 = 17.8924%`
   - 同时 `V/W` 也明显高于 `DISTRIBUTERECORD leaf`
   - 这说明 `WORKFLOWPROCESSESBIND / USERVOTERECORD` 比 `DISTRIBUTERECORD` 更接近 Word 所说的“办理链”
3. 按文档类型看，当前最稳定的 Word strict 候选是：
   - `审查意见答复单 -> vote_all / vote_valid`
   - `图文传真 -> vote_all`
   - `备忘录 -> vote_all`
   - `文件传递单 -> active_plus_valid`
   - `TA / CR` 在 strict 流程办理链下仍然只有弱 `X`

因此，文件6现在必须分清：

- `Word 严格口径`
  - 发送侧优先沿 `workflow/vote` 的当前/有效办理人继续深挖
  - 不再把 `DISTRIBUTERECORD leaf` 当成主链
- `工程复合口径`
  - `stable composite` 仍然是当前最强的 Excel 同步方案
  - 但它是工程拟合层，不是 Word 权威流程复原层
