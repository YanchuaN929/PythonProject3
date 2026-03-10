# CIMS-SQL-3.7 文件4 AH 责任人链复核（2026-03-10）

## 输入范围

- Excel：`example/CIMS-SQL-3.5/EXCEL导出数据` 下文件4全部 7 份工作簿
- SQL：`example/CIMS-SQL-3.5` + `example/CIMS-sql-3.7`
- 权威业务说明：`example/CIMS系统中各接口号的具体使用路线.docx`
- 机器结果：`tmp/file4_ah_owner_chain_probe_20260310.json`
- 探针脚本：`scripts/db_tools/sql_explorer/file4_ah_owner_chain_probe.py`

## 目标

验证文件4 `AH` 是否能沿着下面链路闭环到“最终最底层办理人”：

- `E -> SENDRECEIVEDATA`
- `SEND -> IICS / IITF`
- `IICS / IITF -> WORKFLOWPROCESSESBIND / USERVOTERECORD / 分发候选`

## 样本规模

- 文件4总行数：`77185`
- `AH` 非空：`41824`
- `E -> SENDRECEIVEDATA` 命中：`75194`
- `A = IICS` 且成功落到 `IICS` 对象：`38984`
- `A = IITF` 且成功落到 `IITF` 对象：`36207`

## 新探针方法

旧探针的问题是：对流程表只取“第一条非空记录”。

本轮改成：

- 按 Excel `A(IICS/IITF)` 选择正确对象分支
- 对 `WORKFLOWPROCESSESBIND` 取：
  - 最新 `MODIFIED_BY_ID`
  - 最新/激活记录 `remark.flowUser.userName`
  - 最新/激活记录 `remark.flowUser.transactorName`
- 对 `USERVOTERECORD` 取：
  - 最早操作人
  - 最后操作人
  - 最后有效操作人
  - 最后接收人

## 结果

### 1. 最强候选已经从 25% 提升到 32.6%

对 `AH` 非空的 `41824` 行：

- `按 A 分支取 IICS/IITF.CREATED_BY_ID`
  - `13642 / 41824 = 32.6176%`
- `按 A 分支取 WORKFLOWPROCESSESBIND.latest_modified_by`
  - `13589 / 41824 = 32.4909%`
- `按 A 分支取 WORKFLOWPROCESSESBIND.active remark user/transactor`
  - `13577 / 41824 = 32.4622%`
- `按 A 分支取 USERVOTERECORD.earliest_operator`
  - `5480 / 41824 = 13.1025%`
- `按 A 分支取 USERVOTERECORD.latest_operator`
  - `394 / 41824 = 0.9420%`

结论：

- `AH` 明显不像“最后投票操作人”。
- 它更像“对象创建人 / 流程发起经办人”这一层语义。

### 2. `IICS` 与 `IITF` 两支差异很大

`按 A 分支取对象 CREATED_BY_ID` 后：

- `A = IICS`
  - `10475 / 22794 = 45.9551%`
- `A = IITF`
  - `3167 / 19030 = 16.6421%`

结论：

- `IICS` 分支已经出现中等强度候选。
- `IITF` 分支明显更弱，说明它的责任人更可能不落在 `IITF` 自身对象里。

### 3. `USERVOTERECORD` 的活动维度也没把命中率抬起来

活动名最高频的是：

- `编制`
- `校对`
- `审查`
- `发送`
- `批准`
- `绑签`
- `修改`

但即便按活动拆解，最佳结果也只有：

- `first_编制 = 9635 / 41824 = 23.0370%`

说明：

- `AH` 也不像单纯对应“编制节点操作者”或某一个固定审批节点。

## 当前判断

- 文件4 `AH` 的链路确实能走到 `IICS/IITF -> WORKFLOWPROCESSESBIND / USERVOTERECORD`。
- 但当前已导出的流程表，只能把候选抬到 `32.6176%`，还达不到“闭环到最终最底层办理人”的程度。
- 从现有证据看，`AH` 最接近的临时工程口径是：
  - `按 A 分支取 IICS/IITF.CREATED_BY_ID`
- 但这仍然只是回退，不是最终业务真值。

## 对下一步的影响

如果要继续提高 `AH` 命中率，下一轮优先级应是：

1. 补导真正的分发/文档下游表，例如 `FILETRANSMISSION`、`OBJECTREPLYLINK`、更完整的 `DISTRIBUTERECORD`
2. 或直接回到 CIMS 页面/API，确认“分发信息”页面后端到底读的是哪张对象表
3. `WORKFLOWPROCESSESBIND` 和 `USERVOTERECORD` 这两张表，继续深挖的收益已经明显变小
