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
- 统一业务口径：
  - `X` 取分发全过程办理人并集
  - `V/W` 取这些办理人对应单位/科室并集
  - Excel 多值与 SQL 多值只要任一交集命中即算命中

## 2. Word 版文件6业务说明

本轮重新抽取了 Word 中“待处理文件6”章节，关键结论如下：

1. `E` 列编号在页面搜索时需要“去掉 `-` 再连起来搜索”。
2. `I` 列对应页面中的“要求答复日期 / 回文时间需求”等信息。
3. `X` 列责任人不再按 `V` 所属所判断，而是看“分发信息”里的办理链；当前总口径进一步收敛为“全过程办理人并集”。
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

本轮新增脚本：`scripts/db_tools/sql_explorer/file6_send_workflow_probe.py`

探针链路：

- `文号 -> SENDRECEIVEDATA -> 主对象(FILETRANSMISSION / TA / CR / NCR ... 或 OBJECTREPLYLINK 桥出的对象) -> WORKFLOWPROCESSESBIND / USERVOTERECORD`

结果：

- `SEND` 版本最佳样本：`2958`
- 其中拿到候选对象 ID 的行：`2946`
- 其中拿到 workflow/vote 记录的行：`1413`

命中率：

- `X = 409 / 2958 = 13.8310%`
- `V = 1098 / 2958 = 37.1021%`
- `W = 560 / 2958 = 18.9542%`

这说明：

- 发送侧 `X/V/W` 并不是完全无 SQL 链
- 原来把发送侧主链强压在 `DISTRIBUTERECORD` 上，方向错了

### 6.6 分类型流程桥结果

`图文传真`

- `X = 45 / 115 = 39.1304%`
- `V = 53 / 115 = 46.0870%`
- `W = 25 / 66 = 37.8788%`

`备忘录`

- `X = 60 / 168 = 35.7143%`
- `V = 64 / 168 = 38.0952%`
- `W = 22 / 69 = 31.8841%`

`文件传递单`

- `X = 19 / 425 = 4.4706%`
- `V = 169 / 425 = 39.7647%`
- `W = 37 / 238 = 15.5462%`

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

仍为 `0` 的类型：

- `外发纪要`
- `审查意见单`
- `审查意见答复单`
- `FU通知单`

这说明：

- 文件6 `A` 列确实对应不同对象族和不同存储逻辑
- 对发送侧，至少已经可以稳定拆出两条主桥：
  - `备忘录 / 图文传真 -> OBJECTREPLYLINK -> workflow/vote`
  - `文件传递单 / TA / CR / NCR -> 主对象 -> workflow/vote`

### 6.7 当前仍缺的主表

从 `innovator.sql` 与当前 0 命中类型对照看，下一批最值得补的表是：

1. `MEMORANDUM`
2. `TELEFAX`
3. `INTERNALMINUTES`
4. `EXTERNALMINUTES`
5. `FUNOTIFY`
6. `CANCELNOTIFY`
7. `DESIGNREVIEWOPNION`
8. `DESIGNREVIEWREPLY`
9. `FCR`

用途分别是：

- `MEMORANDUM / TELEFAX`
  - 把当前 `OBJECTREPLYLINK` 的弱桥补成稳定对象主链
- `INTERNALMINUTES / EXTERNALMINUTES`
  - 对应 `内部会议纪要 / 外发纪要`
- `FUNOTIFY / CANCELNOTIFY`
  - 对应 `FU通知单 / 作废通知单`
- `DESIGNREVIEWOPNION / DESIGNREVIEWREPLY`
  - 对应 `审查意见单 / 审查意见答复单`
- `FCR`
  - 补齐当前 `FCRREPLY` 单边导出缺口

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
6. `备忘录 / 图文传真` 当前主桥是 `OBJECTREPLYLINK -> workflow/vote`
7. `文件传递单 / TA / CR / NCR` 当前主桥是 `主对象 -> workflow/vote`
8. `DISTRIBUTERECORD` 对文件6发送侧只保留为补充链，不再作为主链

### 8.2 仍未闭环

1. `X` 的高命中恢复
2. `V/W` 的稳定 SQL 展示恢复
3. `SEND` 分支 `AC`
4. `H` 的稳定 SQL 规则，尤其是 `INT` 分支
5. 尚未导出主表的发送侧类型：
   - `外发纪要`
   - `审查意见单`
   - `审查意见答复单`
   - `FU通知单`
   - `作废通知单`

### 8.3 当前工程口径

- 如果现在只做“规则定稿”，不直接改运行时代码：
  - 路由按 `INT / SEND` 双分支定稿
  - `I/J/M` 按本轮规则落地
  - `X/V/W/AC/H` 明确标记为“当前离线 SQL 未完全闭环”，但发送侧 `X/V/W` 已经有稳定主链方向，不再写成“完全未知”
- 如果后续继续攻文件6，优先级应改为：
  1. 补导缺失主表：`MEMORANDUM / TELEFAX / INTERNALMINUTES / EXTERNALMINUTES / FUNOTIFY / CANCELNOTIFY / DESIGNREVIEWOPNION / DESIGNREVIEWREPLY / FCR`
  2. 按 `A` 列类型继续补齐对象桥
  3. 提升 `X`
  4. 最后再处理 `AC / H`


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
