# 阶段1（离线）CIMS-sql 分析结果

## 1. 执行信息

- 执行时间：`2026-02-13 10:25~10:31`
- 核心命令：
  - `python -m scripts.db_tools.sql_explorer.validate_cims_sql_dump --dump-dir "sql_explorer_output/CIMS-sql" --sample-target 60000`
- 输入目录：`sql_explorer_output/CIMS-sql`
- 模板基线：`example/template_spec.json`
- 新生成产物：
  - `sql_explorer_output/CIMS-sql/validation_output/offline_validation_20260213_103143.json`
  - `sql_explorer_output/CIMS-sql/validation_output/offline_validation_20260213_103143.md`

## 2. 阶段1结论（是否可平替）

- `USER`/`DEPARTMENT` 映射有效：`USER=7491`，`DEPARTMENT=333`，`USER带部门占比=1.0`
- 关键业务表责任人列的 `id_resolved_rate` 与 `resolved_dept_rate` 在主候选列上基本达到 `1.0`，满足离线定位阶段的技术门槛
- `name_in_roster_rate` 普遍较低（0~2%），与名单覆盖范围有限一致，按离线说明该指标仅作参考
- 结论：阶段1的“结构定位 + 32位ID->USER->姓名/部门映射链路验证”已可判定通过

## 3. 按模板文件类型的离线映射建议（1/2/3/4/6）

> 说明：时间列优先按字段语义与现有模板含义对齐；责任人列优先选择业务语义字段，其次回退到 `*_BY_ID`。

| 文件类型 | 模板语义 | 建议主表 | 时间列候选（优先顺序） | 责任人列候选（优先顺序） | 结论 |
|---|---|---|---|---|---|
| 1 | 内部需打开接口 | `IDIACP1000` | `SWAP_START_DATE` -> `ACTUAL_OPEN_DATE` -> `FIRST_ACTUAL_CLOSE_DATE` | `RESP_SHEZONG` -> `DELAY_OPEN_PERSON` -> `CREATED_BY_ID` | 可落地 |
| 2 | 内部需回复接口 | `INTINTERFACEDOC` | `REPLY_DEADLINE` -> `ANSWER_DATE` -> `START_DATE` | `RESP_SHEZONG` -> `RE_OPEN_RESP_SHEZONG` -> `RELEVANT_PERSON` | 可落地 |
| 3 | 外部需打开接口 | `ICMACP1000` | `PRE_OPEN_DATE` -> `FINAL_OPEN_DATE` | `RESP_SHEZONG` -> `DELAY_OPEN_PERSON` | 可落地 |
| 4 | 外部需回复接口 | `ICMACP1000` | `PRE_CLOSE_DATE` -> `FINAL_CLOSE_DATE` -> `CLOSE_DATE` | `RESP_SHEZONG` -> `CHAGE_PERSON` -> `CREATED_BY_ID` | 可落地 |
| 6 | 收发文函 | `SENDRECEIVEDATA`（辅表 `TA`） | `REPLY_DEADLINE` -> `ANSWER_DATE` -> `SEND_DATE`/`RECEIVE_DATE`（`TA.NEED_REPLY_DATE` 作为补充） | `CREATED_BY_ID`（主）-> `MODIFIED_BY_ID`（回退） | 基本可落地，需业务确认“责任人定义” |

## 4. 关键证据摘录（离线验证）

- `IDIACP1000.RESP_SHEZONG`：`id解析率=1.0`，`部门解析率=1.0`
- `ICMACP1000.RESP_SHEZONG`：`id解析率=1.0`，`部门解析率=1.0`
- `INTINTERFACEDOC.RESP_SHEZONG`：`id解析率=1.0`，`部门解析率=1.0`
- `SENDRECEIVEDATA.CREATED_BY_ID`：`id解析率=0.999739`，`部门解析率=1.0`

## 5. 阶段2前的最小确认项

1. 文件2是否以 `ANSWER_DATE` 还是 `REPLY_DEADLINE` 作为“接口时间”主口径
2. 文件6“责任人”是否接受 `CREATED_BY_ID`（若不接受，需要补充关联表/规则）
3. 文件3/4是否按“预期时间（PRE_*）优先，实际时间（FINAL_*）回退”固化

确认以上 3 点后，可直接进入内网在线库终验（阶段2）。

