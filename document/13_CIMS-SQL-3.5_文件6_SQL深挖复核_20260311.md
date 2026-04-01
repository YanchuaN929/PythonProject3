# CIMS-SQL-3.5 文件6 SQL深挖复核（2026-03-11，2026-03-12合并版）

> 2026-03-12 合并说明：本文件已合并原 14、15、16 号文件6专题。如与更早判断有冲突，以本文正文中的最新链路为准；原专项内容保留在文末附录。

## 1. 范围与口径

- SQL范围：
  - `example/CIMS-SQL-3.5`
  - `example/CIMS-sql-3.7`
- Excel范围：
  - `example/CIMS-SQL-3.5/EXCEL导出数据/收发文清单*.xlsx`
  - 共 7 个项目、4178 行样本
- 证据优先级：
  1. `example/CIMS系统中各接口号的具体使用路线.docx`
  2. `core/main.py` 当前文件6筛选逻辑
  3. `example/CIMS-SQL-3.5/EXCEL导出数据` 整合版样本
  4. `CIMS-SQL-3.5 / 3.7` SQL 快照
- 日期口径分两套：
  - Excel导出复算日：`2026-03-04`
  - 现网逻辑复算日：`2026-03-11`
- 当前文档并行保留两套口径：
  - `Word 严格口径`：`X` 只看页面“分发信息/办理链”中的当前或最末级办理人；`V/W` 仅作为这些办理人的组织展示
  - `工程复合口径`：仅用于评估 SQL 对 Excel 的可恢复度，不代表 Word 权威流程
  - 若两套口径冲突，以 `Word 严格口径` 为准

## 2. Word 版文件6业务说明

本轮重新抽取了 Word 中“待处理文件6”章节，关键结论如下：

1. `E` 列编号在页面搜索时需要“去掉 `-` 再连起来搜索”。
2. `I` 列对应页面中的“要求答复日期 / 回文时间需求”等信息。
3. `X` 列责任人不再按 `V` 所属所判断，而是看“分发信息”里的办理链；`2026-03-21` 的严格复核已确认，不能再直接把这条规则扩写成“全过程办理人并集”。
4. 一旦出现回文日期，就视为完成，不再提醒。
5. 文档类型应当能在数据库中找到对应对象或类型信号。

因此，文件6不能再把 `V` 当作责任人判断主链；`V/W` 只保留为组织展示层字段。

## 3. 总路由结论

### 3.1 样本分型

- 总样本：`4178`
- `int_key`：`1215`
- `letter_key`：`2666`
- `special_bw`：`292`
- `empty_key`：`5`

### 3.2 路由结果

- `INT`：`1056`
- `SEND`：`2945`
- `unresolved`：`177`
- 总体已解析：`4001 / 4178 = 95.7635%`

### 3.3 当前稳定路由规则

1. `E` 含 `-ZL-` 的接口单样式，主路由走 `INTINTERFACEDOC`
2. 常规文函号与 `BW` 特殊号，主路由走 `SENDRECEIVEDATA`
3. `FILETRANSMISSION` 可额外提供“文件传递单”对象信号，但不能单独替代总路由

## 4. 字段结论

### 4.1 INT 分支

- `E -> INTINTERFACEDOC.ITEM_NUMBER = 1056 / 1056 = 100.0000%`
- `I -> INTINTERFACEDOC.REPLY_DEADLINE = 1056 / 1056 = 100.0000%`
- `J -> INTINTERFACEDOC.ANSWER_DATE = 865 / 1056 = 81.9129%`
- `M` 派生：
  - 以 `2026-03-04` 复算：`979 / 1056 = 92.7083%`
  - 以 `2026-03-11` 复算：`979 / 1056 = 92.7083%`
- `V` 组织归一化：`101 / 1056 = 9.5644%`
- `W` 主办室派生：`0 / 1056 = 0.0000%`
- `AC -> INTINTERFACEDOC.REV = 643 / 1056 = 60.8902%`
- `X`：
  - 业务真值取“分发全过程办理人并集”
  - 当前批量探针仍未闭环
  - 现有直字段中仅 `RESP_SHEZONG` 有弱命中：`41 / 1055 = 3.8863%`

### 4.2 SEND 分支

- `E -> SENDRECEIVEDATA.(CORRESP_LETTER_REC_NO / LETTER_SEND_NO) = 2945 / 2945 = 100.0000%`
- `I -> SENDRECEIVEDATA.REPLY_DEADLINE = 1726 / 2945 = 58.6078%`
- `J -> SENDRECEIVEDATA.ANSWER_DATE = 2779 / 2945 = 94.3633%`
- `M` 派生：
  - 以 `2026-03-04` 复算：`2214 / 2945 = 75.1783%`
  - 以 `2026-03-11` 复算：`2101 / 2945 = 71.3413%`
- `V` 组织归一化：`80 / 2945 = 2.7165%`
- `W` 主办室派生：`0 / 2945 = 0.0000%`
- `AC`：当前无稳定 SQL 字段，暂定为 `Excel-only / 外部派生`
- `X`：
  - 业务真值取“分发全过程办理人并集”
  - 当前不能写成单一 SQL 直字段
  - 旧的 `SENDRECEIVEDATA.CREATED_BY_ID` 只保留为弱回退，不再视为主链

### 4.3 H 列补充结论

- `SENDRECEIVEDATA.NEED_REPLY` 对 `H(是否回文)` 的直接命中仅 `440 / 2945 = 14.9406%`
- `INTINTERFACEDOC` 当前快照未见直接 `NEED_REPLY` 字段
- 因此 `H` 在文件6里仍未闭环，尤其是 INT 分支

## 5. 文档类型对象信号

当前可以确认：文件6 `A(文函类型)` 更像“对象族信号”，不是一个单字段直连。

按当前 7 项目样本，SEND 分支里能直接挂到的已导出对象表覆盖如下：

- `FILETRANSMISSION`
- `TA / TAREPLY`
- `CR / CRREPLY`
- `NCR / NCRREPLY`
- `OBJECTREPLYLINK` 对 `备忘录 / 图文传真` 有效
- `DCR / TCR` 当前样本未形成有效命中

因此文件6对象层应理解为：

- 主路由是 `SENDRECEIVEDATA`
- 文档对象层会继续分流到 `FILETRANSMISSION / TA / CR / NCR / 备忘录 / 图文传真 ...`
- `A` 列要恢复成稳定 SQL 规则，必须引入“对象族识别层”

## 6. 分发表与流程桥结论

### 6.1 已确认的事实

1. Word 明确指出 `X` 应从“分发信息”取得；当前总口径已收敛为“全过程办理人并集”。
2. `DISTRIBUTERECORD` 中确实存在文件6相关对象，尤其能看到大量：
   - `extra.cnpe.entity.designOutput.ExtFileTransmission`
   - `extra.cnpe.entity.communication.ExtMemorandum`
   - `extra.cnpe.entity.communication.ExtTeleFax`
   - `extra.cnpe.entity.communication.ExtInternalMinutes`
   - `extra.cnpe.entity.communication.ExtExternalMinutes`
   - `extra.cnpe.entity.change.ExtCR / ExtTA / ExtNCR`
3. 这说明文件6的“分发信息”不是空想，数据库里确实存在相关对象与相关记录。

### 6.2 DISTRIBUTERECORD 专项结论

针对 `DISTRIBUTERECORD_20260305.sql` 的全表扫描结果：

- `statement_count = 2372886`
- `matched_count = 582`
- `matched_by_title_count = 582`
- `group_count = 116`

命中结果：

- `INT X_all = 2 / 1055 = 0.1896%`
- `INT V_all = 14 / 1055 = 1.3270%`
- `INT W_all = 3 / 999 = 0.3003%`
- `SEND X_all = 0 / 911 = 0.0000%`
- `SEND V_all = 0 / 911 = 0.0000%`
- `SEND W_all = 0 / 459 = 0.0000%`
- 版本最佳总体：
  - `X_all = 2 / 1966 = 0.1017%`
  - `V_all = 14 / 1966 = 0.7121%`
  - `W_all = 3 / 1458 = 0.2058%`

结论：

- 旧的“文件6分发表整体 0 命中”已被推翻
- 但 `DISTRIBUTERECORD` 的有效命中几乎只落在 `INT` 分支
- 因此 `DISTRIBUTERECORD` 不能再被视为文件6发送侧 `X/V/W` 的主链

### 6.3 CR / TA / 回复链对象桥专项复核

本轮针对“reply -> 主单 / config_id / ref_id 漏探测”问题做了专项复跑，纳入的候选对象包括：

- `ID`
- `CONFIG_ID`
- `reply -> 主单` 外键：`CRREPLY.CR / TAREPLY.TA / NCRREPLY.NCR`
- `REF_FILE_TRANSMISSION`

专项样本结果：

1. `CR答复单 EDMB-400310-ECZS`
   - `E -> SENDRECEIVEDATA(D48E813269E6476BAFF3370588A1B26F)`
   - `-> CRREPLY(C38299D9D0C5417A83552BF37B631F4C)`
   - `-> parent CR(9940169A1A354E05979B6E4E919A37E6)`
   - 上述对象链在当前 `DISTRIBUTERECORD` 中均未命中
2. `CR答复单 EDMB-400329-ECZS`
   - `E -> SENDRECEIVEDATA(63082E2F79CA468EB72FA820E95BF0E0)`
   - `-> CRREPLY(9974DBB884114408B9A9DD38FAD98675 / submit: 7ECEE92FA067494B89FC561D37277CD8)`
   - `-> parent CR(8738CB52A02B4C80A4CC32BA24FC9996)`
   - 上述对象链在当前 `DISTRIBUTERECORD` 中均未命中
3. `TA回复单 EDMB-420456-ECZS`
   - `E -> SENDRECEIVEDATA(5859A41A461647E0AF0A7D4CAD80BD7B)`
   - `-> TAREPLY(A3BA21D6654F4B65ADC78D08C5AAF450)`
   - `-> parent TA(07FBC040002344F594C97DBBA9757ECE)`
   - 上述对象链在当前 `DISTRIBUTERECORD` 中均未命中

结论：

- 文件6当前未闭环，不是因为 `reply -> 主单` 这一层漏掉了
- 当前缺口更像是“另有中间对象链”或“当前快照里缺少这些样本对象的分发表记录”

### 6.4 发送侧流程桥反证样本

#### TA 样本

样本：

- `A = TA`
- `E = EHMC-420045-ECZS-0077`

已确认：

1. `TA_20260305.sql` 中存在该对象
   - `TA.id = F7A5E63C7DBB4576966C4446B598BC51`
2. `DISTRIBUTERECORD_20260305.sql` 中：
   - 不存在 `EHMC-420045-ECZS-0077`
   - 不存在 `F7A5E63C7DBB4576966C4446B598BC51`
3. `WORKFLOWPROCESSESBIND_20260307.sql` 和 `USERVOTERECORD_20260307.sql` 中：
   - 都存在 `SOURCE_OBJECT_ID = F7A5E63C7DBB4576966C4446B598BC51`

#### 文件传递单样本

样本：

- `A = 文件传递单`
- `E = ECZB-770687-EDMB`

已确认：

1. `FILETRANSMISSION_20260305.sql` 中存在该对象
   - `FILETRANSMISSION.id = 0000357D36E2496E8E35786482C064C1`
2. `DISTRIBUTERECORD_20260305.sql` 中：
   - 不存在 `ECZB-770687-EDMB`
   - 不存在 `0000357D36E2496E8E35786482C064C1`
3. `WORKFLOWPROCESSESBIND_20260307.sql` 和 `USERVOTERECORD_20260307.sql` 中：
   - 都存在 `SOURCE_OBJECT_ID = 0000357D36E2496E8E35786482C064C1`

结论：

- 这些发送侧样本的数据并非“不存在于现有 SQL”
- 但它们不主要落在 `DISTRIBUTERECORD`
- 对这类对象，页面“分发信息/经办链”更可能来自 `WORKFLOWPROCESSESBIND / USERVOTERECORD`

### 6.5 发送侧 workflow/vote 探针结果

本轮在你补齐主表后，继续修正并复跑了：`scripts/db_tools/sql_explorer/file6_send_workflow_probe.py`

最新结果文件：

- `document/file6_send_workflow_probe_20260313_rel4.json`
- `document/file6_send_workflow_probe_20260313_rel4_detail_rows.json`

本轮新增修正点：

- 不再只取 `文号 -> SENDRECEIVEDATA -> 主对象`
- 改为把主对象内部的二跳关联也递归纳入候选池：
  - `DESIGNREVIEWREPLY -> DESIGNREVIEWOPNION`
  - `DESIGNREVIEWOPNION -> FILETRANSMISSION`
  - 以及各对象 `MASTER_SEND / FILE_TRANSMISSION / REF_FILE_TRANSMISSION / REF_MEMO / REF_FAX` 等 `relation_ids`
- 同时把 `item_key` 直命中的对象也补回候选池，避免只靠 `SEND_RECEIVE_DATA`

探针链路现口径为：

- `文号 -> SENDRECEIVEDATA / item_key -> 主对象 -> relation_ids 递归展开 -> WORKFLOWPROCESSESBIND / USERVOTERECORD`

结果：

- `SEND` 版本最佳样本：`2958`
- 其中拿到候选对象 ID 的行：`2947`
- 其中拿到 workflow/vote 记录的行：`2258`
- 相比补表前 `1413` 行，多出 `845` 行
- 相比上一轮 `2254` 行，再多出 `4` 行

按 Excel 非空字段计算交集命中：

- `X = 165 / 911 = 18.1120%`
- `V = 498 / 911 = 54.6652%`
- `W = 138 / 459 = 30.0654%`

相对补表前基础版本增量：

- `X +21`
- `V +51`
- `W +32`

这轮最关键的新增结论：

- `审查意见答复单` 之前只打到 `DESIGNREVIEWREPLY` 自身流程，遗漏了其父对象及再上一层 `FILETRANSMISSION`
- 把 `relation_ids` 递归展开后，`审查意见答复单` 直接提升到：
  - `X = 24 / 25 = 96.0000%`
  - `V = 25 / 25 = 100.0000%`
  - `W = 21 / 21 = 100.0000%`
- 这说明发送侧 `X/V/W` 的主链确实在 `WORKFLOWPROCESSESBIND / USERVOTERECORD`
- 同时也说明：之前卡住的不只是“缺主表”，还包括“主对象内部二跳关系没继续展开”
- 原来把发送侧主链强压在 `DISTRIBUTERECORD` 上，方向仍然是错的
- 2026-03-13 晚间继续按文档类型做增强后，又确认了三条可落地的对象字段补强规则：
  - `图文传真 -> workflow/vote 并集 + TELEFAX.CREATED_BY_ID + TELEFAX.MODIFIED_BY_ID`
  - `备忘录 -> workflow/vote 并集 + MEMORANDUM.CREATED_BY_ID + MEMORANDUM.MODIFIED_BY_ID`
  - `文件传递单 -> workflow/vote 并集 + FILETRANSMISSION.MODIFIED_BY_ID`
- 这三条规则不会新增 workflow/vote 命中行，但会继续抬升发送侧：
  - `V` 从 `463 / 911` 提升到 `498 / 911`
  - `W` 从 `123 / 459` 提升到 `138 / 459`
- 同轮也排除了几条仍想当然的方向：
  - `审查意见单` 在 `activity_name / source_type` 维度上没有任何优于“全并集”的新口径
  - `TA / CR / NCR` 在对象表全字段里没有发现强于当前主链的业务责任人字段
  - `外发纪要` 仅 `PRESENTER` 对 `X` 有 `1 / 9` 的弱命中，未形成稳定规则
  - `FU通知单` 当前对象字段与 workflow/vote 均未形成有效交集

### 6.6 分类型流程桥结果

`图文传真`

- `X = 47 / 115 = 40.8696%`
- `V = 89 / 115 = 77.3913%`
- `W = 33 / 66 = 50.0000%`
- 当前类型增强有效规则：`workflow/vote + TELEFAX.CREATED_BY_ID + TELEFAX.MODIFIED_BY_ID`

`备忘录`

- `X = 68 / 168 = 40.4762%`
- `V = 118 / 168 = 70.2381%`
- `W = 38 / 69 = 55.0725%`
- `rows_with_workflow_hits = 282 / 298`
- 当前类型增强有效规则：`workflow/vote + MEMORANDUM.CREATED_BY_ID + MEMORANDUM.MODIFIED_BY_ID`

`文件传递单`

- `X = 21 / 425 = 4.9412%`
- `V = 201 / 425 = 47.2941%`
- `W = 43 / 238 = 18.0672%`
- 当前类型增强有效规则：`workflow/vote + FILETRANSMISSION.MODIFIED_BY_ID`

`TA`

- `X = 1 / 80 = 1.2500%`
- `V = 28 / 80 = 35.0000%`
- `W = 2 / 24 = 8.3333%`

`CR`

- `X = 0 / 49 = 0.0000%`
- `V = 22 / 49 = 44.8980%`
- `W = 1 / 17 = 5.8824%`

`NCR`

- `X = 1 / 6 = 16.6667%`
- `V = 2 / 6 = 33.3333%`
- `W = 0 / 2 = 0.0000%`

`外发纪要`

- `rows_with_workflow_hits = 14 / 14`
- `X = 1 / 9 = 11.1111%`
- `V = 8 / 9 = 88.8889%`
- `W = 0 / 5 = 0.0000%`

`审查意见单`

- `rows_with_workflow_hits = 398 / 398`
- `X = 2 / 30 = 6.6667%`
- `V = 5 / 30 = 16.6667%`
- `W = 0 / 14 = 0.0000%`
- 已排除：单拆 `activity_name / source_type` 或 `DESIGNREVIEWOPNION` 对象表字段，均未带来实质增量

`审查意见答复单`

- `rows_with_workflow_hits = 44 / 44`
- `X = 24 / 25 = 96.0000%`
- `V = 25 / 25 = 100.0000%`
- `W = 21 / 21 = 100.0000%`

`FU通知单`

- `rows_with_workflow_hits = 96 / 98`
- 但当前 `X/V/W` 交集仍为 `0`
- 已排除：`FUNOTIFY.APPLY / CREATED_BY_ID / MODIFIED_BY_ID`

`作废通知单`

- `rows_with_workflow_hits = 13 / 13`
- 但 Excel 当前 `X/V/W` 无稳定可对齐值

`IICS / IITF`

- 当前仍为 `0` 行 workflow/vote 命中
- 继续不作为文件6发送侧主桥

这说明：

- 文件6 `A` 列确实对应不同对象族和不同存储逻辑
- `审查意见答复单` 已从“对象桥已通、业务值部分命中”推进到“基本闭环”
- `外发纪要 / 审查意见单` 仍是“对象桥已通、业务值部分命中”
- `图文传真 / 备忘录 / 文件传递单` 已确认可再靠对象字段继续抬升 `V/W`
- `FU通知单 / 作废通知单` 也已证实能打到 workflow/vote，对象桥不再缺失
- 对发送侧，当前已经可以稳定拆出四类主桥：
  - `备忘录 / 图文传真 -> OBJECTREPLYLINK + 主对象 -> workflow/vote`
  - `文件传递单 / TA / CR / NCR -> 主对象 -> workflow/vote`
  - `审查意见单 / 审查意见答复单 -> DESIGNREVIEWOPNION / DESIGNREVIEWREPLY -> relation_ids 递归展开 -> workflow/vote`
  - `FU通知单 / 作废通知单 / 外发纪要 -> 主对象 -> workflow/vote`

### 6.7 原缺主表补齐后的状态

你已补齐上一轮列出的 9 张主表，当前 `example/CIMS-SQL-3.5` 已确认存在：

1. `MEMORANDUM`（`141257`）
2. `TELEFAX`（`120600`）
3. `INTERNALMINUTES`（`9207`）
4. `EXTERNALMINUTES`（`9589`）
5. `FUNOTIFY`（`10766`）
6. `CANCELNOTIFY`（`3237`）
7. `DESIGNREVIEWOPNION`（`158845`）
8. `DESIGNREVIEWREPLY`（`19930`）
9. `FCR`（`106881`）

补表后，对象表 `-> SEND_RECEIVE_DATA` 直连探针结果为：

- `MEMORANDUM = 344 / 324`
- `TELEFAX = 408 / 408`
- `EXTERNALMINUTES = 16 / 16`
- `FUNOTIFY = 156 / 156`
- `CANCELNOTIFY = 20 / 20`
- `DESIGNREVIEWOPNION = 1180 / 567`
- `DESIGNREVIEWREPLY = 55 / 55`
- `INTERNALMINUTES = 0 / 0`
- `FCR = 0 / 0`
- `FCRREPLY = 0 / 0`

说明：上面格式为 `rows_matched / send_link_rows`。

同轮 `DISTRIBUTERECORD` 复跑结果文件：

- `document/file6_distribution_chain_probe_20260313_rel2.json`

结论：

- 原 6.7 的“缺表未导出”判断已失效，应改成“主表已补齐，workflow/vote 主桥已增强”
- 但 `DISTRIBUTERECORD` 对发送侧仍然没有新增实质命中，`SEND X/V/W` 继续为 `0`
- 当前真正未闭环的是：
  - `INTERNALMINUTES / FCR` 仍无有效 send link
  - 已打到 workflow/vote 的对象族如何把 `X/V/W` 提升到业务可用水平
- 另做了 `SSC_RELATED_DATA` 快筛：
  - 发送侧命中的 `TA / CRREPLY / FILETRANSMISSION / FUNOTIFY / CANCELNOTIFY / MEMORANDUM / TELEFAX` 共提取 `661` 个 `SSC_RELATED_DATA`
  - 在 `WORKFLOWPROCESSESBIND / USERVOTERECORD` 中命中 `0`
  - 说明 `SSC_RELATED_DATA` 不是当前文件6发送侧 workflow/vote 的下一条主桥

## 7. 与 core/main.py 的对齐结果

当前 `core/main.py` 的文件6逻辑仍然是：

- `V` 包含 `河北分公司.建筑结构所`
- `I` 非空且满足时间窗
- `M in ('尚未回复','超期未回复')`
- `AC` 取最高版

用 SQL 规则回放后：

- `2026-03-11` 口径下最终结果集一致率：`3984 / 4001 = 99.5751%`
- 但这个高一致率不能误读为“字段已全部闭环”
- 真正原因是：
  - 当前产品正筛选出的最终正例本来就很少
  - `V/I/M` 三个条件里，`I` 和最终集合能被较稳定复算
  - `V/W/X/AC/H` 这些展示或责任链字段仍然没有完全恢复

## 8. 最终收口

### 8.1 已定稿

1. 文件6必须按双分支理解：`INTINTERFACEDOC + SENDRECEIVEDATA`
2. `INT` 分支的 `E/I` 已稳定直连，`J/M` 已有可用规则
3. `SEND` 分支的 `E/J` 已稳定，`M` 已能用 `ANSWER_DATE / REPLY_DEADLINE / IS_ANSWERED` 派生
4. `A` 不是单字段，而是对象族信号
5. 文件6 `SEND` 分支 `X/V/W` 的主链必须纳入 `WORKFLOWPROCESSESBIND / USERVOTERECORD`
6. 补表后已确认可以稳定打到 workflow/vote 的发送侧对象族包括：
   - `FILETRANSMISSION / TA / CR / NCR`
   - `MEMORANDUM / TELEFAX`
   - `DESIGNREVIEWOPNION / DESIGNREVIEWREPLY`
   - `FUNOTIFY / CANCELNOTIFY`
   - `EXTERNALMINUTES`
7. 对发送侧，主对象的 `relation_ids` 必须继续递归展开，不能停在第一层对象 ID
8. `DISTRIBUTERECORD` 对文件6发送侧仍只保留为补充链，不再作为主链

### 8.2 仍未闭环

1. `X` 的高命中恢复
2. `V/W` 的稳定 SQL 展示恢复
3. `SEND` 分支 `AC`
4. `H` 的稳定 SQL 规则，尤其是 `INT` 分支
5. 当前仍弱或仍为 `0` 的对象族：
   - `INTERNALMINUTES`
   - `FCR / FCRREPLY`
   - `IICS / IITF`
6. `FU通知单 / 作废通知单` 虽然对象桥已通，但当前 `X/V/W` 仍无稳定交集
7. `TA / CR / 审查意见单 / 外发纪要 / 文件传递单` 仍然只打到部分业务责任人，尚未恢复到稳定业务口径
8. `图文传真 / 备忘录 / 文件传递单` 虽已确认对象字段补强有效，但 `X` 仍未出现新的稳定提升

### 8.3 当前工程口径

- 如果现在只做“规则定稿”，不直接改运行时代码：
  - 路由按 `INT / SEND` 双分支定稿
  - `I/J/M` 按本轮规则落地
  - `X/V/W/AC/H` 明确标记为“当前离线 SQL 未完全闭环”，但发送侧 `X/V/W` 已经有稳定主链方向，不再写成“完全未知”
- 后续回归口径改为：
  - 不再把整个待处理文件6的总命中率作为主拟合指标
  - 改为按 `A` 列文档类型分别回归、分别收口
  - 类型级回归清单见：`document/file6_type_regression_report_20260313_rel4.json`
- 如果后续继续攻文件6，优先级应改为：
  1. 优先提升仍未闭环但已打到 workflow/vote 的类型：`文件传递单 / TA / CR / 审查意见单 / FU通知单 / 作废通知单 / 外发纪要`
  2. `审查意见答复单` 已基本闭环，可转入抽样复核
  3. `图文传真 / 备忘录 / 文件传递单` 当前可先采用“workflow/vote 主链 + 对象表责任人字段补强”的临时工程口径
  4. 再继续追 `INTERNALMINUTES / FCR / IICS / IITF`
  5. 已可暂时排除 `SSC_RELATED_DATA -> workflow/vote` 这条方向
  6. 最后再处理 `AC / H`


## 9. 附录A：原14号专题保留记录

> 说明：以下内容完整保留原 `14` 号专题的专项排查记录，若与本文正文冲突，以正文为准。

# CIMS-SQL-3.5 文件6 CR / TA 对象桥复核（2026-03-12）

> 2026-03-12 晚间补充说明：本附录只覆盖 `CR / TA / 回复链 -> SOURCE_OBJECT_ID` 这条专项子链，不代表文件6分发表全局最新结果。文件6当前统一结论已合并到本文正文；其中全表 `DISTRIBUTERECORD` 已能命中 `582` 条语句、`116` 个对象组，但 `CR / TA` 这条专项子链仍然没有稳定命中。

## 1. 目的

在 `document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md` 的基础上，继续锁定文件6 `X(主办人)` 的分发表对象桥，重点验证：

- `CR_20260305.sql`
- `CRREPLY_20260305.sql`
- `TA_20260305.sql`
- `TAREPLY_20260305.sql`
- `NCR_20260305.sql`
- `NCRREPLY_20260305.sql`
- `FILETRANSMISSION_20260305.sql`
- `DISTRIBUTERECORD_20260305.sql`

目标不是重新讨论业务真值，而是回答一个更具体的问题：

- 文件6里 `CR / CR答复单 / TA / TA回复单` 这些对象，分发信息到底挂在哪一层对象 ID 上？

## 2. 本轮修正

上一轮脚本只把以下对象放进 `DISTRIBUTERECORD.SOURCE_OBJECT_ID` 候选池：

- 主对象 `ID`
- `SENDRECEIVEDATA.ID`
- 直接命中的 `FILETRANSMISSION.ID`

本轮补充进候选池的对象层包括：

- `CONFIG_ID`
- `CRREPLY.CR`
- `TAREPLY.TA`
- `NCRREPLY.NCR`
- `REF_FILE_TRANSMISSION`

也就是把“回复单 -> 主单”和“版本配置 ID / 引用对象”都完整纳入复跑。

## 3. CR / TA 专项子链复跑结果

使用当时的 `CR / TA / reply-parent / config / ref` 专项探针重新跑完整 7 项目样本，在“只看这条子链能否直接打到 `SOURCE_OBJECT_ID`”这个范围内，结果仍然是：

- `DISTRIBUTERECORD.statement_count = 2372886`
- `matched_count = 0`
- `object_group_count = 0`
- 输出文件：`tmp/file6_sql_deep_dive_20260312.json`

这意味着：

- 当前 file6 样本没有任何一条记录，能通过 `ID / CONFIG_ID / parent_id / ref_id` 这些已知候选层稳定打到 `DISTRIBUTERECORD.SOURCE_OBJECT_ID`

## 4. 样本级证据

### 4.1 CR答复单：`EDMB-400310-ECZS`

对象链：

- `E -> SENDRECEIVEDATA.ID = D48E813269E6476BAFF3370588A1B26F`
- `-> CRREPLY.ID = C38299D9D0C5417A83552BF37B631F4C`
- `-> CRREPLY.CONFIG_ID = 286434147D014964B21583C1E97E99B0`
- `-> parent CR.ID = 9940169A1A354E05979B6E4E919A37E6`

结论：

- 以上对象均未在当前 `DISTRIBUTERECORD.SOURCE_OBJECT_ID` 中命中

### 4.2 CR答复单：`EDMB-400329-ECZS`

对象链：

- `E -> SENDRECEIVEDATA.ID = 63082E2F79CA468EB72FA820E95BF0E0`
- `-> CRREPLY.ID = 9974DBB884114408B9A9DD38FAD98675`
- `-> submit CRREPLY.ID / CONFIG_ID = 7ECEE92FA067494B89FC561D37277CD8`
- `-> parent CR.ID = 8738CB52A02B4C80A4CC32BA24FC9996`

结论：

- 以上对象均未在当前 `DISTRIBUTERECORD.SOURCE_OBJECT_ID` 中命中

### 4.3 TA回复单：`EDMB-420456-ECZS`

对象链：

- `E -> SENDRECEIVEDATA.ID = 5859A41A461647E0AF0A7D4CAD80BD7B`
- `-> TAREPLY.ID = A3BA21D6654F4B65ADC78D08C5AAF450`
- `-> parent TA.ID = 07FBC040002344F594C97DBBA9757ECE`

结论：

- 以上对象均未在当前 `DISTRIBUTERECORD.SOURCE_OBJECT_ID` 中命中

### 4.4 TA回复单：`EHMC-420045-ECZS-0077` 对应回复链

对象链：

- `TA.ID = F7A5E63C7DBB4576966C4446B598BC51`
- `TAREPLY submit/current = 2FD836CB1135467B9F8669868C74EE6C / 1DDCD6D912354E4D8F8FBD561153EC6D`
- `SENDRECEIVEDATA.ID = 785DC39DD3854768B477EBF86032E82E`

结论：

- 以上对象均未在当前 `DISTRIBUTERECORD.SOURCE_OBJECT_ID` 中命中

## 5. 反向确认

虽然当前样本没命中，但 `DISTRIBUTERECORD` 本身不是空表。

同时补做了当前 1818 样本的文本层直搜：

- `EHMC-400012-ECZS-0077`
- `EFCY-400001-ECZS-0251`
- `EHMC-420045-ECZS-0077`
- `EHMC-420102-ECZS-0075`
- `EDMB-400310-ECZS`
- `EDMB-400329-ECZS`
- `EDMB-420456-ECZS`

在 `DISTRIBUTERECORD_20260305.sql` 原文中均为 `0` 命中。

这条证据说明：

- 不只是 `SOURCE_OBJECT_ID` 暂时没撞上
- 当前这批 1818 样本连 `BO_TITLE` 文本层也没有留下直接痕迹


当前库里仍能看到大量：

- `SOURCE_TYPE = extra.cnpe.entity.change.ExtCR`
- `SOURCE_TYPE = extra.cnpe.entity.change.ExtTA`
- `SOURCE_TYPE = extra.cnpe.entity.change.ExtNCR`
- `SOURCE_TYPE = extra.cnpe.entity.designOutput.ExtFileTransmission`

因此可以明确：

- 不是“没有分发表数据”
- 而是“当前 file6 样本尚未找到能稳定命中的那层对象”

## 6. 本轮收口

### 6.1 已确认

1. `CR答复单` 的 SQL 对象链是：`E -> SENDRECEIVEDATA -> CRREPLY -> CR(parent)`
2. `TA回复单` 的 SQL 对象链是：`E -> SENDRECEIVEDATA -> TAREPLY -> TA(parent)`
3. 本专题原先沿用的“最末级办理人”表述，现已被总口径修正为“分发全过程办理人并集”；这一点不影响本专题对 CR / TA 子链对象桥失败的判断

### 6.2 已排除

1. 不是因为脚本漏掉 `reply -> parent` 才导致 `X` 为 0
2. 不是因为 `CONFIG_ID` 没进候选池
3. 不是因为 `REF_FILE_TRANSMISSION` 没进候选池
4. 不是因为 `DISTRIBUTERECORD` 整体缺表

### 6.3 当前最合理判断

文件6 `X` 还差的不是“字段候选”，而是“对象桥候选”。

也就是说，后续应该优先继续找：

- `E -> 另一层中间对象 -> DISTRIBUTERECORD.SOURCE_OBJECT_ID`

而不是继续在 `CR / TA / reply / send` 这些已验证过的 ID 上反复试。

## 7. 对总口径的影响

本轮不会推翻 `document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md` 的主结论，只会把它补强为：

- 文件6 `X` 未闭环这件事，现在已经能明确到“不是 reply-parent/config/ref 漏探测”
- 当前离线 SQL 仍不能恢复 file6 分发表的稳定对象桥


## 10. 附录B：原15号专题保留记录

> 说明：以下内容完整保留原 `15` 号专题的专项排查记录，若与本文正文冲突，以正文为准。

# CIMS-SQL-3.5 文件6分发表全链复核（2026-03-12）

> 注：本文档保留 `DISTRIBUTERECORD` 方向的专项复核结果。发送侧 `X/V/W` 主链的最新结论，已并入 `document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md`。

## 1. 目的

本专题只回答文件6分发表链的三个问题：

1. `X(主办人)` 是否应按分发表全过程办理人并集理解
2. `V/W` 是否应按这些办理人对应的单位/科室并集理解
3. 在这个新判定规则下，当前 `DISTRIBUTERECORD` 能把文件6样本解释到什么程度

本轮不再继续追 `H`。

## 2. 本轮采用的业务口径

以用户最新说明为准：

- Excel `X` 不是“最后一个叶子办理人”，而是这个信息单在分发过程中出现过的全部办理人
- Excel `V/W` 也不是单点落位值，而是这些办理人对应的单位和科室
- 命中规则统一改为：
  - Excel 多值 vs SQL 分发表全链多值
  - 只要任一人名、任一单位、任一科室存在交集，就算命中

因此，旧版“最末级办理人”只保留为历史中间判断，不再作为文件6当前总口径。

## 3. 探针范围与实现

- Excel：`example/CIMS-SQL-3.5/EXCEL导出数据/收发文清单*.xlsx`
- SQL：
  - `example/CIMS-SQL-3.5`
  - `example/CIMS-sql-3.7`
- 探针脚本：`scripts/db_tools/sql_explorer/file6_distribution_chain_probe.py`
- 结果文件：`tmp/file6_distribution_chain_probe_20260312.json`

本轮相对旧探针新增了三件事：

1. `INTINTERFACEDOC` 同链扩展
   - 不只看当前 `E` 对应行
   - 还把同一 `INTINTERFACEDOC` 链上的关联行一起纳入
2. 紧凑标题码提取
   - 支持 `2026ARXZL25A2S002`、`1907XWCVZL25B3S005` 这类无连字符标题码
3. `SOURCE_OBJECT_ID + BO_TITLE` 双桥反查
   - 不再只撞 `SOURCE_OBJECT_ID`
   - 同时用标题码去反扫 `DISTRIBUTERECORD.BO_TITLE`

## 4. 路由基线

- 总样本：`4178`
- 路由覆盖：`4001 / 4178 = 95.7635%`
- 其中：
  - `INT = 1056`
  - `SEND = 2945`
  - `UNRESOLVED = 177`

这说明本轮分发表探针是在已经较稳定的文件6主路由基础上做的，不是建立在混乱样本上。

## 5. 分发表扫描结果

全表扫描 `DISTRIBUTERECORD_20260305.sql` 后，本轮得到：

- `statement_count = 2372886`
- `matched_count = 582`
- `matched_by_title_count = 582`
- `group_count = 116`

结论：

- 旧的“文件6分发表整体 0 命中”已经不成立
- 至少 `INT` 分支存在一条真实的分发表链
- 但这条链覆盖极低，不能支撑文件6全量 SQL 化

## 6. X / V / W 命中结果

### 6.1 INT 分支

- `X_all = 2 / 1055 = 0.1896%`
- `V_all = 14 / 1055 = 1.3270%`
- `W_all = 3 / 999 = 0.3003%`

分项目看：

- `X` 只在 `1916`、`2016` 出现命中
- `V` 主要集中在 `2016`，少量出现在 `1916`、`2026`
- `W` 只在 `2016` 出现命中

### 6.2 SEND 分支

- `X_all = 0 / 911 = 0.0000%`
- `V_all = 0 / 911 = 0.0000%`
- `W_all = 0 / 459 = 0.0000%`

分类型看，以下 SEND 侧对象全部仍为 `0` 命中：

- `CR`
- `TA`
- `NCR`
- `文件传递单`
- `图文传真`
- `备忘录`
- `审查意见单 / 审查意见答复单`

### 6.3 版本最佳样本总体

- `X_all = 2 / 1966 = 0.1017%`
- `V_all = 14 / 1966 = 0.7121%`
- `W_all = 3 / 1458 = 0.2058%`

这说明即便按“多值任一交集命中”的更宽规则重算，文件6 `X/V/W` 仍然远未闭环。

## 7. 命中样本证据

### 7.1 `X` 命中样本

样本：`2016-X-RVD-ZL-25A6-S-092`

- Excel `X`：`河北核电工艺所文档员,工艺系统研究设计所文档,于婷,杜广,黄若琳`
- 分发表全链人员：包含 `河北核电工艺所文`、`于婷`、`陈科`、`王旭`、`杨亚伟`
- 结果：因为 `于婷` 交集命中，`X` 计为命中

这证明当前脚本的判定规则已经按“全过程人员并集任一命中”生效，而不是只看叶子单人。

### 7.2 `V` 命中样本

样本：`2016-X-FNP-ZL-25A5-S-137`

- Excel `V`：`河北分公司.核电工艺所`
- 分发表全链组织：包含 `河北分公司.核电工艺所`
- 结果：`V` 命中

### 7.3 `W` 命中样本

样本：`2016-X-RVD-ZL-25A6-S-092`

- Excel `W`：`工艺系统室`
- 分发表全链科室：包含 `工艺系统室`
- 结果：`W` 命中

## 8. 技术含义

这轮结果已经把问题收窄得比较明确：

1. 旧的全零不是纯粹业务规则写错
   - `INTINTERFACEDOC` 全链扩展和标题码提取补上后，`INT` 分支确实出现了真实命中
2. 但主问题也不是“叶子 vs 全链”的判定规则
   - 规则已经放宽到全过程并集任一命中，命中率仍然极低
3. 当前真正的主缺口在 `SEND` 分支对象桥
   - `CR / TA / NCR / 文件传递单 / 图文传真 / 备忘录` 等类型目前仍打不到稳定分发表对象组
4. 对典型 `SEND` 样本做现有导出表全库反查后，也没有出现新的已导出中间桥
   - `EDMB-400329-ECZS`、`EDMB-400310-ECZS`、`EDMB-420456-ECZS`、`EHMC-420045-ECZS-0077` 这类样本，目前仍只落在 `SENDRECEIVEDATA + CR/CRREPLY + TA/TAREPLY`
   - 在当前已导出的 `OBJECTREPLYLINK / FILETRANSMISSION / IICS / IITF / INTERFACEREOPENINFO` 中，没有再找到新的文号直连桥

## 9. 当前收口

### 9.1 已经可以确定的事

1. 文件6 `X/V/W` 的业务解释现在已经统一：
   - `X = 分发全过程办理人并集`
   - `V = 这些办理人对应单位并集`
   - `W = 这些办理人对应科室并集`
2. 命中规则也已经统一：
   - Excel 多值与 SQL 多值任一交集命中即算命中
3. `INT` 分支并非完全没有分发表链，只是覆盖非常差

### 9.2 仍未闭环的事

1. `SEND` 分支稳定对象桥
2. 文件6 `X/V/W` 的全量 SQL 恢复
3. `AC` 的 SEND 分支来源

### 9.3 下一步技术方向

后续如果继续攻文件6，不应再围绕“叶子办理人规则”反复试错，而应直接找：

- `SEND 当前对象 -> 中间对象 -> DISTRIBUTERECORD` 的稳定桥

特别应继续围绕这些对象族追：

- `FILETRANSMISSION`
- `CR / CRREPLY`
- `TA / TAREPLY`
- `NCR / NCRREPLY`
- 与这些对象相关的额外业务中间表
## 2026-03-17 补充：TA / CR 路径重想结果

本轮重新检视后确认：此前持续围绕 `workflow/vote -> 办理人` 深挖，方向对 `TA / CR` 不是主链。

新增证据来自脚本：

- `scripts/db_tools/sql_explorer/file6_type_author_route_probe.py`
- 输出：`document/file6_type_author_route_probe_20260317.json`

结论如下：

1. `TA / CR` 的 Excel `X/V/W` 更像“外部来文单位 / 文号前缀 -> 内部责任所室 -> 该所室人员名单”，而不是当前 `workflow/vote` 里的流程办理人。
2. 对 `TA / CR` 做 `AUTHOR_UNIT / 文号前缀` 的留一交叉验证后，信号显著：
   - `TA`：
     - `V = 39 / 80 = 48.7500%`
     - `W = 20 / 24 = 83.3333%`
     - `X = 41 / 80 = 51.2500%`
   - `CR`：
     - `V = 28 / 49 = 57.1429%`
     - `W = 12 / 17 = 70.5882%`
     - `X = 28 / 49 = 57.1429%`
3. 这组结果说明：
   - `TA / CR` 当前缺口的核心不是“漏了一条 workflow actor 字段”
   - 而是“缺了一层 author/prefix -> 责任所室 的业务分流”
4. 典型稳定样本：
   - `重庆川仪自动化股份有限公司 / EFCY`：稳定落到 `河北分公司.电气自动化所`，并进一步分出 `仪控一室 / 仪控二室 / 电气室`
   - `HEAVY MECHANICAL COMPLEX-3 / EHMC`：大量样本稳定落到 `河北分公司.核工程研究设计所 / 河北分公司.设计管理部`，`W` 常见为 `设备室 / 工艺室 / 通信室`
   - `SMPCT`：稳定落到 `工艺系统研究设计所.辅助系统室 / 工艺系统研究设计所.工艺设备室`

因此，文件6发送侧后续应拆成两类链：

- `workflow/vote` 主链：
  - 继续负责 `文件传递单 / 备忘录 / 图文传真 / 审查意见单 / 审查意见答复单 / 外发纪要`
- `author-routing` 主链：
  - 重点负责 `TA / CR`
  - 路径应理解为：
    - `SENDRECEIVEDATA.AUTHOR_UNIT / LETTER_SEND_NO prefix`
    - `-> 内部责任所/室映射`
    - `-> USER / DEPARTMENT 派生 X/V/W`

注意：

- 这条链当前已经被新探针证明显著有效，但还没有直接写进 `file6_send_resolver.py`
- 原因不是结果不够强，而是它与 `workflow/vote` 属于不同口径，应该作为独立策略层接入，避免把两类文档错误混算

### 2026-03-17 rel2：TA / CR token 化回归补充

在原始 `AUTHOR_UNIT / 文号前缀` 留一验证基础上，继续把预测口径从“整串 `V/W` 众数”改成“`V/W` 所室 token 众数（top3）”，新报告见：

- `document/file6_type_author_route_probe_20260317_rel2.json`

本轮稳定结论：

1. `TA / CR` 的稳定主链可以继续坚持 `author-routing`，但实现口径不应再用整串 `V/W` 众数，而应改成：
   - `AUTHOR_UNIT / LETTER_SEND_NO prefix`
   - `-> top3 org/office token`
   - `-> USER / DEPARTMENT 派生 X/V/W`
2. 当前最优稳定策略为 `prefix_token_top3`（与 `author3_then_prefix3` 当前命中率等价，但链路更简洁）：
   - `TA`
     - `X = 48 / 80 = 60.0000%`
     - `V = 48 / 80 = 60.0000%`
     - `W = 20 / 24 = 83.3333%`
   - `CR`
     - `X = 30 / 49 = 61.2245%`
     - `V = 30 / 49 = 61.2245%`
     - `W = 12 / 17 = 70.5882%`
3. 相比上一版 `document/file6_type_author_route_probe_20260317.json`：
   - `TA`：`X +7`、`V +9`、`W +0`
   - `CR`：`X +2`、`V +2`、`W +0`
4. 这说明真正有效的增量不是再扫新表，而是把 author/prefix 分流后的 `V/W` 预测单位从“整串文本”改成“所室 token 集合”。

同时确认一条需要明确排除的实验方向：

1. 若在 `prefix_token_top3` 没有同类样本时，直接回退到 `workflow_org_values / workflow_office_values`，数值会被明显抬高：
   - `TA`：`X = 72 / 80`，`V = 55 / 80`
   - `CR`：`X = 49 / 49`，`V = 36 / 49`
2. 但这条回退的预测人员范围过宽：
   - `TA` 平均候选人数约 `2124`
   - `CR` 平均候选人数约 `2893`
   - 单行最大候选人数达到 `6848`
3. 因此该路径只能保留为“探索用实验项”，不能作为文件6同步 Excel 的稳定业务口径。

现阶段对 `TA / CR` 的可落地结论应收敛为：

- 稳定策略：`author-routing + token_top3`
- 实验策略：`author-routing 失败时 workflow org fallback`
- 后续工程实现时，应把它作为 `workflow/vote` 之外的第二条独立类型链接入

### 2026-03-17 rel3：TA / CR 跨类型共享前缀池

在 `rel2` 的 token 化 author-routing 基础上，继续寻找“同类样本不足”时的稳定补强路线。新尝试不是继续放宽 workflow，而是让 `TA / CR` 共享同一套前缀训练池：

- 输出：`document/file6_type_author_route_probe_20260317_rel3.json`

新增结论如下：

1. `TA / CR` 的 `prefix -> 内部所室` 映射并不严格依赖文档类型，跨 `TA / CR` 共享前缀样本后，稳定指标继续提升。
2. 当前新的最优稳定策略为：`cross_type_prefix_token_top3`
   - `TA`
     - `X = 51 / 80 = 63.7500%`
     - `V = 52 / 80 = 65.0000%`
     - `W = 20 / 24 = 83.3333%`
   - `CR`
     - `X = 37 / 49 = 75.5102%`
     - `V = 37 / 49 = 75.5102%`
     - `W = 13 / 17 = 76.4706%`
3. 相比 `rel2`：
   - `TA`：`X +3`、`V +4`、`W +0`
   - `CR`：`X +7`、`V +7`、`W +1`
4. 被这条路线补回来的典型前缀包括：
   - `EHST`
   - `FAPAG`
   - `FAPYS`
   - `JAPKP / JAPCC`
   - `SMPCT`
   - `EHZZ`
5. 这条跨类型共享路线与 workflow fallback 的性质不同：
   - 它只是扩大 `TA / CR` 之间的同类前缀样本池
   - 预测人员范围仍保持在可控级别，平均候选人数约：
     - `TA = 163.27`
     - `CR = 151.20`
   - 明显低于 workflow fallback 的 `2124 / 2893`

因此，`TA / CR` 当前推荐落地顺序应更新为：

1. `cross_type_prefix_token_top3`
2. `prefix_token_top3`
3. 仅探索时参考 `workflow_org_values / workflow_office_values`

### 2026-03-17 rel4：共享前缀家族探针

为了继续寻找 `TA / CR` 之外的补强路线，本轮新增探针：

- `scripts/db_tools/sql_explorer/file6_shared_prefix_family_probe.py`
- 输出：`document/file6_shared_prefix_family_probe_20260317.json`

该探针不是再看单一类型，而是先按“共享前缀数 >= 6”自动构建文种图，再对最大连通簇做：

- `same_type_prefix_token_top3`
- `cross_type_prefix_token_top3`

最大共享前缀簇共 `2580` 行，包含：

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

这一轮最重要的新结论不是“所有这些类型都应该共池”，而是：

1. `TA / CR` 在大簇共池中还能继续提升，而且仍未出现 workflow fallback 那种人数失控：
   - `TA`
     - `X = 59 / 80 = 73.7500%`
     - `V = 60 / 80 = 75.0000%`
     - `W = 20 / 24 = 83.3333%`
     - 平均候选人数约 `210.33`
   - `CR`
     - `X = 39 / 49 = 79.5918%`
     - `V = 38 / 49 = 77.5510%`
     - `W = 13 / 17 = 76.4706%`
     - 平均候选人数约 `192.44`
2. `文件传递单` 也存在稳定但较小的共池增量：
   - `X = 302 / 425 -> 311 / 425`
   - `V = 308 / 425 -> 314 / 425`
   - `W = 180 / 238 -> 184 / 238`
3. `审查意见答复单` 也能继续提升：
   - `X = 21 / 25 -> 22 / 25`
   - `V = 21 / 25 -> 22 / 25`
   - `W = 13 / 21 -> 15 / 21`
4. `FU通知单` 在小样本上也有正向信号：
   - `X = 3 / 4 -> 4 / 4`
   - `V = 3 / 4 -> 4 / 4`
5. 但 `审查意见单` 明显不适合混入这个大簇：
   - `X = 19 / 30 -> 15 / 30`
   - `V = 19 / 30 -> 15 / 30`
   - `W = 12 / 14 -> 9 / 14`
   - 说明它虽然共享部分前缀，但业务分流口径和 `TA / CR / 文件传递单 / 审查意见答复单` 不完全一致

因此，这轮真正新增的“其他路线”应定义为：

- 不是单纯的 `TA / CR` 二元共池
- 而是“共享前缀家族 + 类型选择性接入”

当前可执行结论：

1. `TA / CR` 可以继续从“家族共池”获益
2. `文件传递单 / 审查意见答复单 / FU通知单` 值得继续按这条线单独复核
3. `审查意见单` 暂时不要并入该家族池，仍应保持独立口径

### 2026-03-18 rel5：共享前缀 donor-selective 收缩

在 `rel4` 的“共享前缀家族 + 选择性接入”基础上，本轮继续追问一个更工程化的问题：

- 是否能把“大簇共池”进一步收缩成“每个类型只借特定 donor 类型”，从而在保持命中率的同时压低候选范围

新增探针：

- `scripts/db_tools/sql_explorer/file6_prefix_donor_probe.py`
- 输出：`document/file6_prefix_donor_probe_20260318.json`

该探针做的不是再扩大共池，而是对每种类型分别比较：

- `same_type_prefix_token_top3` 基线
- `共享前缀 >= 3` 的 donor 类型组合（`max_combo_size = 2`）

本轮最重要的新结论是：`rel4` 的“家族共池”可以继续收缩成“donor-selective 矩阵”。

1. `TA` 的最优 donor 不是整个大簇，而是：
   - `CR + 文件传递单`
   - `X = 48 / 80 -> 59 / 80`
   - `V = 48 / 80 -> 60 / 80`
   - `W = 20 / 24 -> 20 / 24`
   - 平均候选人数约 `202.93`
   - 这与 `rel4` 大簇共池的命中率相同，但范围更小，说明 `TA` 当前无需借完整家族池
2. `CR` 的最优 donor 为：
   - `TA + 文件传递单`
   - `X = 30 / 49 -> 39 / 49`
   - `V = 30 / 49 -> 38 / 49`
   - `W = 12 / 17 -> 13 / 17`
   - 平均候选人数约 `191.40`
   - 同样达到 `rel4` 大簇共池的效果，但范围更收敛
3. `文件传递单` 也不是必须借完整家族池，其最优 donor 为：
   - `TA + 审查意见答复单`
   - `X = 302 / 425 -> 310 / 425`
   - `V = 308 / 425 -> 316 / 425`
   - `W = 180 / 238 -> 185 / 238`
4. `审查意见答复单` 的最优 donor 非常明确：
   - `文件传递单`
   - `X = 21 / 25 -> 25 / 25`
   - `V = 21 / 25 -> 25 / 25`
   - `W = 13 / 21 -> 15 / 21`
   - 说明其 prefix-routing 口径可以直接借 `文件传递单`，无需再混入更大的家族池
5. `FU通知单` 也出现了稳定 donor：
   - `文件传递单`
   - `X = 3 / 4 -> 4 / 4`
   - `V = 3 / 4 -> 4 / 4`
   - `W = 3 / 3 -> 3 / 3`
   - 这是小样本结果，但比 `rel4` 的“整个大簇共池”更可解释
6. `图文传真` 与 `外发纪要` 之间也有较弱 donor 信号：
   - `图文传真 <- 外发纪要 + 审查意见单`
   - `X = 77 / 115 -> 81 / 115`
   - `V = 74 / 115 -> 77 / 115`
   - `W = 51 / 66 -> 53 / 66`
   - `外发纪要 <- 图文传真`
   - `W = 1 / 5 -> 2 / 5`
   - 但这条线目前仍偏弱，只能算候选补强，不宜直接升格为稳定口径
7. `NCR` 也能从 `文件传递单` 借样本：
   - `X = 2 / 6 -> 4 / 6`
   - `V = 2 / 6 -> 4 / 6`
   - 但样本过小，暂不宜过度解释
8. 负结论同样重要：
   - `审查意见单` 没有正向 donor 增量，应继续保持独立口径
   - `备忘录` 没有正向 donor 增量，说明它当前缺口不在 prefix donor
   - `TA回复单 / CR答复单 / IICS / IITF / 作废通知单` 仍未出现有效 donor 信号

因此，当前更准确的工程结论应更新为：

- 不是“共享前缀家族整体接入”
- 也不只是“TA / CR 二元共池”
- 而是“按类型维护 donor-selective 矩阵”

当前建议的 donor 矩阵：

- `TA <- CR + 文件传递单`
- `CR <- TA + 文件传递单`
- `文件传递单 <- TA + 审查意见答复单`
- `审查意见答复单 <- 文件传递单`
- `FU通知单 <- 文件传递单`
- `图文传真 <- 外发纪要 + 审查意见单`（弱信号，待继续复核）
- `外发纪要 <- 图文传真`（弱信号，待继续复核）
- `NCR <- 文件传递单`（小样本，待继续复核）

### 2026-03-18 rel6：donor-selective 之后还要继续调 token 宽度

`rel5` 已经把 prefix-routing 从“大簇共池”收缩成了 donor-selective 矩阵，但这还不是终点。继续深挖后发现：

- donor 类型固定之后，`V/W` 的 token 宽度并不一定都应该固定为 `top3`
- 某些类型还能继续抬升命中
- 某些类型虽然命中不变，但能显著收缩候选人员范围

新增探针：

- `scripts/db_tools/sql_explorer/file6_prefix_token_width_probe.py`
- 输出：`document/file6_prefix_token_width_probe_20260318.json`

这轮探针的做法是：

- 先固定 `rel5` 的最佳 donor 组合
- 再对每个类型搜索 `v_topn / w_topn = 1..5`
- 分别观察“命中率新增”和“候选范围是否失控”

本轮最重要的新结论有四类：

1. `文件传递单` 还能继续抬升，而且范围增长仍在可接受区间：
   - donor：`TA + 审查意见答复单`
   - 原始 donor 组合（`3/3`）：
     - `X = 310 / 425`
     - `V = 316 / 425`
     - `W = 185 / 238`
     - 平均候选人数约 `187.89`
   - 最优 token 宽度：`v_topn = 5`，`w_topn = 3`
     - `X = 315 / 425`
     - `V = 322 / 425`
     - `W = 185 / 238`
     - 平均候选人数约 `197.88`
   - 相比 `3/3`，`X +5`、`V +6`，而范围增长仍控制在约 `+5.3%`
2. `审查意见答复单` 还能补掉一部分 `W`：
   - donor：`文件传递单`
   - 原始 donor 组合（`3/3`）：
     - `X = 25 / 25`
     - `V = 25 / 25`
     - `W = 15 / 21`
   - 最优 token 宽度：`v_topn = 3`，`w_topn = 4`
     - `X = 25 / 25`
     - `V = 25 / 25`
     - `W = 16 / 21`
   - 说明该类型当前剩余缺口主要在 `W`，而不是 `X/V`
3. `外发纪要` 的 donor 路线比之前判断更强：
   - donor：`图文传真`
   - 原始 donor 组合（`3/3`）：
     - `X = 4 / 9`
     - `V = 4 / 9`
     - `W = 2 / 5`
     - 平均候选人数约 `355.00`
   - 最优 token 宽度：`v_topn = 1`，`w_topn = 5`
     - `X = 5 / 9`
     - `V = 4 / 9`
     - `W = 3 / 5`
     - 平均候选人数约 `338.43`
   - 这里不是“放宽更大更好”，而是 `V` 更收敛、`W` 更放宽
4. `图文传真` 虽然也能继续抬升，但当前只能算实验路线：
   - donor：`外发纪要 + 审查意见单`
   - 最优 token 宽度：`v_topn = 5`，`w_topn = 4`
     - `X = 81 / 115 -> 85 / 115`
     - `V = 77 / 115 -> 83 / 115`
     - `W = 53 / 66 -> 56 / 66`
   - 但平均候选人数从 `262.10` 膨胀到 `395.68`
   - 如果约束“平均候选人数只允许增加 10%”，则 `图文传真` 最优解仍会退回 `3/3`
   - 因此这条线目前不宜直接升格为稳定工程口径

另外还有一类“命中不变，但范围更小”的优化，同样值得保留：

- `TA <- CR + 文件传递单`
  - `v_topn = 3`，`w_topn = 1`
  - 命中不变：`X = 59 / 80`，`V = 60 / 80`，`W = 20 / 24`
  - 平均候选人数：`202.93 -> 189.89`
- `CR <- TA + 文件传递单`
  - `v_topn = 3`，`w_topn = 1`
  - 命中不变：`X = 39 / 49`，`V = 38 / 49`，`W = 13 / 17`
  - 平均候选人数：`191.40 -> 179.44`
  - 最大候选人数：`541 -> 461`
- `FU通知单 <- 文件传递单`
  - `v_topn = 2`，`w_topn = 1`
  - 命中不变：`X = 4 / 4`，`V = 4 / 4`，`W = 3 / 3`
  - 平均候选人数：`42.69 -> 27.32`
- `NCR <- 文件传递单`
  - `v_topn = 3`，`w_topn = 1`
  - 命中不变：`X = 4 / 6`，`V = 4 / 6`，`W = 0 / 2`
  - 平均候选人数：`173.67 -> 165.50`

因此，当前 prefix-routing 的推荐矩阵应继续细化为：

- `TA <- CR + 文件传递单`，`v_topn = 3`，`w_topn = 1`
- `CR <- TA + 文件传递单`，`v_topn = 3`，`w_topn = 1`
- `文件传递单 <- TA + 审查意见答复单`，`v_topn = 5`，`w_topn = 3`
- `审查意见答复单 <- 文件传递单`，`v_topn = 3`，`w_topn = 4`
- `FU通知单 <- 文件传递单`，`v_topn = 2`，`w_topn = 1`
- `外发纪要 <- 图文传真`，`v_topn = 1`，`w_topn = 5`
- `NCR <- 文件传递单`，`v_topn = 3`，`w_topn = 1`
- `图文传真 <- 外发纪要 + 审查意见单`
  - 稳定优先：继续保留 `3/3`
  - 命中优先：可实验 `5/4`

### 2026-03-18 rel7：prefix-selective boost 比全量放宽更稳

继续深入后发现，`rel6` 里有些“全量放宽 token 宽度”的增量，其实并不是所有 prefix 共同贡献的，而是集中在少数 prefix。于是本轮继续新增一层探针：

- `scripts/db_tools/sql_explorer/file6_prefix_selective_boost_probe.py`
- 输出：`document/file6_prefix_selective_boost_probe_20260318.json`

这层探针做的事是：

- 先固定 `rel6` 的 donor 组合和 extra token 宽度
- 再比较“是否真的要对整个文种全部 prefix 放宽”
- 若增量只来自少数 prefix，则只对这些 prefix 启用 extra token 宽度

本轮最重要的新增结论有四条：

1. `文件传递单` 的 `v_topn = 5` 增量只集中在 4 个 prefix：
   - `JAPDB`
   - `FAPAK`
   - `FAPBH`
   - `SMPCJ`
   - 其中最强的两个是：
     - `JAPDB`：`X/V = 3/3 -> 5/5`
     - `FAPAK`：`X/V = 3/3 -> 5/5`
   - 如果只对这 4 个 prefix 启用 `v_topn = 5`，其他 prefix 继续保持 `3/3`，则可拿到：
     - `X = 315 / 425`
     - `V = 322 / 425`
     - `W = 185 / 238`
     - 平均候选人数约 `191.19`
   - 这与 `rel6` 的“全量 `5/3`”命中完全相同，但范围更小（`197.88 -> 191.19`）
   - 因此，`文件传递单` 当前更好的落地方式不是“整个文种都升到 `5/3`”，而是：
     - 默认 `3/3`
     - 仅 `JAPDB / FAPAK / FAPBH / SMPCJ` 放宽到 `5/3`
2. `图文传真` 终于可以明确拆成“稳定版 / 实验版”两套口径：
   - extra token 的增量主要来自：
     - `ECZB`
     - `ECZS`
     - `YBANY`
     - `FADGB`
   - 如果对这 4 个 prefix 全部放宽到 `5/4`，则可拿到：
     - `X = 85 / 115`
     - `V = 83 / 115`
     - `W = 56 / 66`
     - 平均候选人数约 `300.55`
   - 这已经比 `rel6` 的“全量 `5/4`”范围小很多（`395.68 -> 300.55`）
   - 如果再加“平均候选人数不超过基线 `110%`”的稳定约束，则当前最佳 prefix-selective 稳定版是：
     - 仅 `ECZB + ECZS` 放宽到 `5/4`
     - `X = 84 / 115`
     - `V = 82 / 115`
     - `W = 55 / 66`
     - 平均候选人数约 `287.45`
   - 因此，`图文传真` 现在终于可以明确分层：
     - 稳定版：只放宽 `ECZB / ECZS`
     - 实验版：放宽 `ECZB / ECZS / YBANY / FADGB`
3. `审查意见答复单` 的 `W` 增量并不是全量 prefix 需要：
   - 只来自 `EDES`
   - 若仅 `EDES` 放宽到 `w_topn = 4`，即可保留：
     - `X = 25 / 25`
     - `V = 25 / 25`
     - `W = 16 / 21`
     - 平均候选人数约 `298.27`
   - 这比 rel6 的全量 `3/4` 更收敛（`316.45 -> 298.27`）
4. `外发纪要` 的增量虽然也集中在 `YBANY`，但 prefix-selective 反而不划算：
   - 仅 `YBANY` 放宽时，命中与 rel6 全量 `1/5` 相同：
     - `X = 5 / 9`
     - `V = 4 / 9`
     - `W = 3 / 5`
   - 但平均候选人数会回升到 `363.64`
   - 反而不如 rel6 的全量 `1/5`（`338.43`）
   - 所以 `外发纪要` 当前应保留全量 `1/5`，不要再做 prefix-selective

反过来看，这轮也把“不需要 prefix-selective”的类型排清了：

- `TA / CR / FU通知单 / NCR` 没有出现正向 prefix boost 候选
- 说明这些类型当前应保留“全类型 token 宽度配置”，不需要再细到 prefix 级

因此，prefix-routing 当前最精确的工程口径应更新为：

- `TA <- CR + 文件传递单`：全类型 `3/1`
- `CR <- TA + 文件传递单`：全类型 `3/1`
- `文件传递单 <- TA + 审查意见答复单`
  - 默认 `3/3`
  - `JAPDB / FAPAK / FAPBH / SMPCJ -> 5/3`
- `审查意见答复单 <- 文件传递单`
  - 默认 `3/3`
  - `EDES -> 3/4`
- `FU通知单 <- 文件传递单`：全类型 `2/1`
- `外发纪要 <- 图文传真`：全类型 `1/5`
- `NCR <- 文件传递单`：全类型 `3/1`
- `图文传真 <- 外发纪要 + 审查意见单`
  - 稳定版：默认 `3/3`，`ECZB / ECZS -> 5/4`
  - 实验版：默认 `3/3`，`ECZB / ECZS / YBANY / FADGB -> 5/4`

### 2026-03-21 rel8：全量文件6 复合仿真结果

在 `rel7` 已经把 prefix-routing 收敛到“类型矩阵 + 必要时 prefix-selective boost”之后，本轮不再看单项探针，而是把当前所有有效路线真正复合起来，对文件6发送侧全量样本做一次统一模拟：

- `workflow/object` 主链
- `donor-selective prefix-routing`
- `token 宽度矩阵`
- `prefix-selective boost`

新增脚本：

- `scripts/db_tools/sql_explorer/file6_composite_simulation.py`
- 输出：`document/file6_composite_simulation_20260321.json`

这轮模拟有两个前提需要写清：

1. 这是基于 `document/file6_send_workflow_probe_20260313_rel4_detail_rows.json` 的全量 file6 发送侧 leave-one-out 仿真。
2. 它衡量的是“当前规则体系在已有全量样本上的可恢复度”，不是已经接入主程序后的现网口径。

#### 总盘结果

`workflow-only` 基线：

- `X = 165 / 911 = 18.1120%`
- `V = 498 / 911 = 54.6652%`
- `W = 138 / 459 = 30.0654%`

`stable composite`：

- `X = 615 / 911 = 67.5082%`
- `V = 739 / 911 = 81.1196%`
- `W = 350 / 459 = 76.2527%`
- 相比 `workflow-only`：
  - `X +450`
  - `V +241`
  - `W +212`
  - 共有 `460` 行发生命中变化

`experimental composite`：

- `X = 616 / 911 = 67.6180%`
- `V = 740 / 911 = 81.2294%`
- `W = 351 / 459 = 76.4706%`
- 相比 `stable composite` 只多出：
  - `X +1`
  - `V +1`
  - `W +1`
  - 只额外改变 `1` 行

因此，当前全量仿真的结论很明确：

- `stable composite` 已经拿到了绝大多数收益
- `experimental composite` 的边际增量极小
- 如果后续要做工程接入，应优先以 `stable composite` 作为主口径

#### 主要贡献来源

`stable composite` 相比 `workflow-only` 的增量，主要由以下类型贡献：

1. `文件传递单`
   - `X +296`
   - `V +162`
   - `W +148`
   - 复合后达到：
     - `X = 317 / 425 = 74.5882%`
     - `V = 363 / 425 = 85.4118%`
     - `W = 191 / 238 = 80.2521%`
2. `TA`
   - `X +58`
   - `V +39`
   - `W +18`
   - 复合后达到：
     - `X = 59 / 80 = 73.7500%`
     - `V = 67 / 80 = 83.7500%`
     - `W = 20 / 24 = 83.3333%`
3. `图文传真`
   - `X +45`
   - `V +14`
   - `W +27`
   - 复合后达到：
     - `X = 92 / 115 = 80.0000%`
     - `V = 103 / 115 = 89.5652%`
     - `W = 60 / 66 = 90.9091%`
4. `CR`
   - `X +39`
   - `V +19`
   - `W +13`
   - 复合后达到：
     - `X = 39 / 49 = 79.5918%`
     - `V = 41 / 49 = 83.6735%`
     - `W = 14 / 17 = 82.3529%`

次级贡献还有：

- `FU通知单`：`X/V/W = 4/4, 4/4, 3/3`
- `外发纪要`：`X = 5/9`，`V = 8/9`，`W = 3/5`
- `NCR`：`X = 4/6`，`V = 5/6`
- `审查意见答复单`：复合后 `X/V/W = 25/25, 25/25, 21/21`

#### 当前结论

这轮复合仿真把一件事说明白了：

- `workflow/object` 主链本身远远不够
- 但一旦把 prefix-routing 的 `donor + token width + prefix-selective boost` 合进来，文件6 发送侧就能从“局部类型可解释”推进到“全量仿真可明显抬升”

同时也要保持边界意识：

- 这仍然是仿真结果，不是主程序已上线结果
- 它最适合用来指导“下一步把哪些规则正式接进 resolver / main”
- 当前若只选一个工程目标，应优先接入 `stable composite`

### 2026-03-21 rel9：按 Word 严格工作流程回退复核

这轮重新按 Word 原文“分发信息 -> 办理链 -> 当前/最末级责任人”回退，不再沿用 `donor / prefix / composite` 的工程拟合逻辑。

新增脚本与结果：

- 严格分发表探针：`scripts/db_tools/sql_explorer/file6_word_strict_probe.py`
- 输出：`document/file6_word_strict_probe_20260321.json`
- 严格流程办理人探针：`scripts/db_tools/sql_explorer/file6_word_workflow_probe.py`
- 输出：`document/file6_word_workflow_probe_20260321.json`

#### rel9-1 严格把“分发信息”视为 `DISTRIBUTERECORD` 的结果

按 `SOURCE_OBJECT_ID / BO_TITLE -> DISTRIBUTERECORD -> leaf/latest-leaf operator` 的严格链重跑后，结果非常弱：

- `version_best_rows = 4003`
- 真正打到分发表组的只有 `23` 行
- 真正打到 leaf operator 的也只有 `23` 行
- 版本最佳全量结果：
  - `X_leaf_union = 0 / 1966 = 0`
  - `V_leaf_union = 10 / 1966 = 0.5086%`
  - `W_leaf_union = 1 / 1458 = 0.0686%`

这意味着一件事：

- 对文件6发送侧而言，Word 里说的“分发信息页面”基本不可能直接落在 `DISTRIBUTERECORD leaf` 这条链上
- `DISTRIBUTERECORD` 在文件6里仍可保留为弱补充证据，但不能再被解释成 Word 严格责任人主链

#### rel9-2 严格把“办理链”视为当前/有效流程办理人的结果

在不使用 `prefix-routing / donor / composite` 的前提下，仅对现有发送侧 `workflow/vote` 明细重做严格候选搜索，结果明显优于 `DISTRIBUTERECORD leaf`：

- `vote_all`
  - `X = 165 / 911 = 18.1120%`
  - `V = 384 / 911 = 42.1515%`
  - `W = 110 / 459 = 23.9651%`
- `vote_valid`
  - `X = 163 / 911 = 17.8924%`
  - `V = 384 / 911 = 42.1515%`
  - `W = 110 / 459 = 23.9651%`
- `active_plus_valid`
  - `X = 163 / 911 = 17.8924%`
  - `V = 463 / 911 = 50.8233%`
  - `W = 123 / 459 = 26.7974%`

这说明：

- 如果坚持 Word 严格路径，文件6发送侧的“办理人”更像 `WORKFLOWPROCESSESBIND / USERVOTERECORD` 中的当前/有效办理链
- 它依然不是当前文档早先采用的“全过程办理人并集”
- 因此 `workflow/vote` 可以继续保留为 Word 严格复核的主候选链，但必须与工程复合口径分开记述

#### rel9-3 按文档类型观察的严格候选

逐类型选择最像 Word“办理人”的 strict 候选后，当前最稳定的是：

- `审查意见答复单 -> vote_all / vote_valid`
  - `X = 24 / 25 = 96.0000%`
  - `V = 25 / 25 = 100.0000%`
  - `W = 21 / 21 = 100.0000%`
- `图文传真 -> vote_all`
  - `X = 47 / 115 = 40.8696%`
  - `V = 86 / 115 = 74.7826%`
  - `W = 25 / 66 = 37.8788%`
- `备忘录 -> vote_all`
  - `X = 68 / 168 = 40.4762%`
  - `V = 109 / 168 = 64.8810%`
  - `W = 28 / 69 = 40.5797%`
- `文件传递单 -> active_plus_valid`
  - `X = 21 / 425 = 4.9412%`
  - `V = 171 / 425 = 40.2353%`
  - `W = 39 / 238 = 16.3866%`
- `TA / CR`
  - 当前 strict 流程办理链只能抬 `V/W`
  - `X` 仍然几乎不动
- `FU通知单`
  - 当前 strict 流程办理链仍为 `0`

#### rel9-4 当前最终修正

到 `2026-03-21` 为止，文件6应明确拆成两条结论：

1. `Word 严格口径`
   - 发送侧不应再把 `X` 解释成“全过程办理人并集”
   - `DISTRIBUTERECORD leaf` 对文件6发送侧不成立
   - 更接近 Word 的严格主链应是 `WORKFLOWPROCESSESBIND / USERVOTERECORD` 的当前/有效办理人
2. `工程复合口径`
   - `stable composite` 仍然是当前最强的 Excel 恢复方案
   - 但它是工程拟合层，不是 Word 权威流程复原层

因此，后续如果继续要求“严格遵守 Word 工作流程”，探索方向应固定为：

- 继续拆 `workflow/vote` 中哪一类“当前/有效办理人”最接近页面分发信息
- 继续核对 `activity_name / source_type / valid` 的业务含义
- 不再把 `prefix-routing / donor / composite` 的结果直接表述成 Word 口径
