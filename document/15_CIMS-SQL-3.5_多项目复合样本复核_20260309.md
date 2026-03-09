# CIMS-SQL-3.5 多项目复合样本复核（2026-03-09）

## 输入范围

- Excel 目录：`example/CIMS-SQL-3.5/EXCEL导出数据`
- 参与复核的同类工作簿：
  - 文件1：7 份
  - 文件2：7 份
  - 文件3：7 份
  - 文件4：7 份
- SQL：`example/CIMS-SQL-3.5` + `example/CIMS-sql-3.7`
- 权威业务说明：`example/CIMS系统中各接口号的具体使用路线.docx`
- 机器结果：`tmp/composite_excel_sql_recheck_20260309.json`

## 结论总览

- 文件1：主路径清晰，主键命中接近 100%。
- 文件2：主对象路径已经清晰；责任人链方向清晰，但当前 dump 不支持用分发表闭环；`M/N` 还不能全部定稿。
- 文件3：主路径清晰，主键命中接近 100%；但部分业务文本列和日期列还不能只靠当前直连字段精确复原。
- 文件4：已经确认后台稳定入口不是 `IITF.ITEM_NUMBER`，而是 `SENDRECEIVEDATA`；`AH` 当前最佳工程候选仍是 `IICS.CREATED_BY_ID`；`F/S/V` 仍未全部定稿。

## 文件1

- 复合样本总行数：`34943`
- 主键路径：`A -> IDIACP1000.ITEM_NUMBER`
  - `34942 / 34943 = 99.9971%`
- 说明：这足以再次确认文件1主表仍然是 `IDIACP1000`，路径清晰。
- 责任人文本列 `R -> DEPART_USER` 的直接姓名比对只有 `29033 / 34819 = 83.3826%`
- 解释：这不是主路径问题，而是跨项目历史姓名写法、别名、占位名的清洗问题；不影响“文件1主对象路径已清晰”的结论。

## 文件2

### 1. 主对象路径

- 复合样本总行数：`90177`
- `A -> INTINTERFACEDOC.ITEM_NUMBER`
  - `90169 / 90177 = 99.9911%`
- `(A,D) -> INTINTERFACEDOC.(ITEM_NUMBER, REF_ITEM_NUMBER)`
  - `90169 / 90177 = 99.9911%`
- `R -> INTINTERFACEDOCIDIACP1000 -> IDIACP1000.ITEM_NUMBER`
  - `89979 / 90177 = 99.7804%`

结论：
- 按 Word 文档，文件2的业务对象应以“传递单页 + 回复页”联合理解。
- 后台主入口已经可以定稿为：
  - `A -> INTINTERFACEDOC.ITEM_NUMBER`
  - `R -> INTINTERFACEDOCIDIACP1000 -> IDIACP1000.ITEM_NUMBER`

### 2. 责任人链

- Word 规则：责任人必须从“传递页 -> 分发信息”判断，且应是最终最底层办理人。
- 本轮复核结果：
  - `INT.id -> DISTRIBUTERECORD.SOURCE_OBJECT_ID`：`0 / 80382 = 0.0000%`
  - `INT.id -> WORKFLOWPROCESSESBIND.SOURCE_OBJECT_ID`：`76313 / 80382 = 94.9379%`
  - `INT.id -> USERVOTERECORD.SOURCE_OBJECT_ID`：`39796 / 80382 = 49.5086%`

结论：
- 当前 dump 里，文件2责任人链的“分发表直连”仍然不可用。
- 但流程链本身已经被大样本证明存在，说明 Word 文档说的“从分发/流程链找责任人”方向是对的。
- 现阶段若要工程落地，仍只能保留“流程链解释 + 回退字段”方案，不能声称已恢复最终责任人全量口径。

### 3. `AM` 列再次确认

- 复合样本里 `AM` 非空只有 `6 / 90177`
- 这再次说明：文件2 `AM` 不是稳定原生导出列，不能当成责任人反校基准。

### 4. `M/N` 列

- `M -> INTINTERFACEDOC.REPLY_DEADLINE`
  - `7 / 54544 = 0.0128%`
- `N -> INTINTERFACEDOC.ANSWER_DATE`
  - `27583 / 43031 = 64.1003%`

结论：
- `N` 与 `ANSWER_DATE` 存在明显相关，但还不能直接定稿为 100% 口径。
- `M` 不能直接定稿为 `REPLY_DEADLINE`。
- 按 Word 说明，文件2的回复页时间字段还需要继续做“页面字段 -> SQL 字段”的二次拆解，当前不能硬定。

## 文件3

### 1. 主对象路径

- 复合样本总行数：`23641`
- `C -> ICMACP1000.ITEM_NUMBER`
  - `23638 / 23641 = 99.9873%`
- `I -> ICMACP1000.RELEASE_PARTY`
  - `23622 / 23641 = 99.9196%`

结论：
- 文件3主表仍可确认是 `ICMACP1000`。
- 从“接口编码”和“发布方”两个核心锚点看，路径是清晰的，命中率已经接近 100%。

### 2. 需要保留的保守说明

- `AL -> RESP_DEPART`：`15248 / 23421 = 65.1040%`
- `AP -> DEPART_USER`：`7999 / 10262 = 77.9478%`
- `L -> PRE_FORECAST_DATE`：`1 / 23638`
- `M -> FINAL_FORECAST_DATE`：`1 / 23632`

解释：
- 这说明文件3虽然“对象路径清晰”，但部分业务列不能只靠当前直连字段和简单文本/日期比对来定稿。
- 尤其 `AP` 按 Word 文档是“所内编制人”，空值时还会落到管理员提醒逻辑，这部分本来就不完全在 CIMS 库中。

## 文件4

### 1. 主对象路径

- 复合样本总行数：`77185`
- `E -> IITF.ITEM_NUMBER（直连）`
  - `0 / 77185 = 0.0000%`
- `E -> SENDRECEIVEDATA.LETTER_SEND_NO`
  - `75194 / 77185 = 97.4205%`
- `E -> SENDRECEIVEDATA.CORRESP_LETTER_REC_NO`
  - `34703 / 77185 = 44.9608%`

结论：
- 文件4后台稳定入口可以再次定稿：不是 `E -> IITF.ITEM_NUMBER`。
- 正确方向仍是：`E -> SENDRECEIVEDATA`。
- 这和 Word 文档并不冲突：前端看到的是 IITF/IICS 页面，但后台稳定桥是先到 `SENDRECEIVEDATA`，再到 `IITF/IICS`。

### 2. 二级对象链

- `SEND -> IITF`：`36237 / 77185 = 46.9482%`
- `SEND -> IICS`：`39011 / 77185 = 50.5422%`
- 但一旦落到对象后，流程覆盖极高：
  - `IICS -> WORKFLOWPROCESSESBIND`：`38980 / 38987 = 99.9820%`
  - `IITF -> WORKFLOWPROCESSESBIND`：`36199 / 36221 = 99.9393%`

结论：
- 文件4的流程链是成立的。
- 但当前 dump 下，`SEND -> IICS/IITF` 不是全覆盖，这意味着文件4某些报表行还需要额外的行级判别规则，不能只靠一个简单桥字段全量还原。

### 3. `AH` 责任人

- Word 规则：文件4责任人逻辑与文件2相同，应看“分发信息”。
- 当前复合样本中 `AH` 非空：`41824`
- 候选字段命中：
  - `AH -> IICS.CREATED_BY_ID`：`10475 / 41824 = 25.0454%`
  - `AH -> IICS -> WORKFLOWPROCESSESBIND.CREATED_BY_ID`：`10440 / 41824 = 24.9617%`
  - `AH -> IICS -> USERVOTERECORD.OPERATOR`：`1756 / 41824 = 4.1985%`
  - `AH -> IITF -> DISTRIBUTERECORD.OPERATOR`：`0 / 41824 = 0.0000%`

结论：
- 从“最终责任人”语义看，Word 规则仍指向分发链。
- 但从当前 dump 的可落地工程口径看，最佳候选仍是 `IICS.CREATED_BY_ID`，流程表并没有把它明显抬高。

### 4. `F/S/V/P`

- `F -> SENDRECEIVEDATA.SEND_RECV_LETT_DATE`：`49753 / 77180 = 64.4636%`
- `F -> IITF.RELEASE_DATE`：`35470 / 77180 = 45.9575%`
- `S -> SENDRECEIVEDATA.REPLY_DEADLINE`：`0 / 57856 = 0.0000%`
- `V -> IICS.RELEASE_DATE`：`88 / 51877 = 0.1696%`
- `P` 非空有 `72397` 行，但 Word 文档里也明确说其页面位置仍不清楚。

结论：
- 文件4的“主对象路径”已经清楚。
- 但 `F/S/V` 不能在本轮直接定稿到单一 SQL 字段。
- `P` 继续保持未定状态，不应硬猜。

## 最终回答你的 3 个要求

1. 已经把 `example/CIMS-SQL-3.5/EXCEL导出数据` 下所有同类 Excel 纳入复合样本，并按项目号分组统计。
2. 已经按新的 Word 文档重构文件2、4的业务路径理解：
   - 文件2：`A -> INTINTERFACEDOC`，`R -> 桥表 -> IDIACP1000`，责任人走分发/流程链。
   - 文件4：`E -> SENDRECEIVEDATA`，再分流到 `IITF/IICS`，责任人仍走分发/流程链。
3. 文件1和文件3：
   - 如果说的是“主对象路径是否清晰”，答案是是，且样本命中率已接近 100%。
   - 如果说的是“所有业务列都已接近 100% 定稿”，答案不是；文件3部分文本列和日期列仍需要进一步拆解。
