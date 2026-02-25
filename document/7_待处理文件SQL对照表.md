# 待处理文件 SQL 对照表（阶段1离线版）

## 1. 适用范围

- 本表用于“Excel待处理文件 -> CIMS SQL”平替映射梳理。
- 依据来源：
  - `core/main.py`（现网筛选逻辑与Excel列位）
  - `example/template_spec.json`（文件1/2/3/4/6模板基线）
  - `sql_explorer_output/CIMS-sql/*.sql`（离线快照字段）
- 说明：
  - `col_idx` 为 SQL 表内 0-based 列序号。
  - 责任人多为 32 位 ID，需走 `USER/DEPARTMENT` 映射后转姓名与科室。

## 2. 总览（按文件类型）

| 文件类型 | 文件名规则（简） | 业务名称 | 主SQL表 | 状态 |
|---|---|---|---|---|
| 1 | `xxxx按项目导出IDI手册*.xlsx` | 内部需打开接口 | `innovator.IDIACP1000` | 已验证 |
| 2 | `内部接口信息单报表xxxx*.xlsx` | 内部需回复接口 | `innovator.INTINTERFACEDOC` | 已验证 |
| 3 | `外部接口ICM报表xxxx*.xlsx` | 外部需打开接口 | `innovator.ICMACP1000` | 已验证 |
| 4 | `外部接口单报表xxxx*.xlsx` | 外部需回复接口 | `innovator.ICMACP1000` | 已验证 |
| 5 | `xxxx接口提资清单*.xlsx` | 三维提资接口 | 暂无稳定SQL映射 | 待确认 |
| 6 | `收发文清单*.xlsx` | 收发文函 | `innovator.SENDRECEIVEDATA` + `innovator.TA`（兼容 `INTINTERFACEDOC` 导出版） | 部分已验证 |

## 3. 文件1（内部需打开接口）

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `IDIACP1000.PROJ_NUM` (`col_idx=28`) | 文件名项目号兜底 |
| 接口号 | `A(0)` | `IDIACP1000.ITEM_NUMBER` (`27`) | - |
| 科室 | `H(7)` | `IDIACP1000.RESP_SHEZONG` (`38`) -> `USER.id` -> `DEPARTMENT` | `IDIACP1000.DEPART_USER` (`39`) |
| 接口时间 | `K(10)` | `IDIACP1000.SWAP_START_DATE` (`40`) | `IDIACP1000.ACTUAL_OPEN_DATE` (`44`) |
| 完成标记 | `M(12)` | `IDIACP1000.CLOSE_NUM` (`60`) | `IDIACP1000.LATEST_REPLY` (`57`) |
| 责任人 | `R(17)` | `IDIACP1000.RESP_SHEZONG` (`38`) | `DELAY_OPEN_PERSON` (`63`), `CREATED_BY_ID` (`5`) |

## 4. 文件2（内部需回复接口）

> [原生测试] keep-undo 测试

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
> [测试改动2] 当前可视区域标记（用于验证改动高亮/Keep/Undo 是否出现）
| 项目号 | 文件名4位 | `INTINTERFACEDOC.PROJ_NUM` (`28`) | 文件名项目号兜底 |
| 接口号 | `R(17)` | `INTINTERFACEDOC.ITEM_NUMBER` (`27`) | - |
| 科室 | `I(8)` | `INTINTERFACEDOC.RECEIVE_DEPT` (`39`) | `PROPOSED_DEPT` (`38`) + 责任人部门映射 |
| 接口时间 | `M(12)` | `INTINTERFACEDOC.REPLY_DEADLINE` (`57`) | `ANSWER_DATE` (`58`), `START_DATE` (`47`) |
| 完成标记 | `N(13)` | `INTINTERFACEDOC.ANSWER_DATE` (`58`) | `ANSWER_TYPE` (`59`) |
| 版次 | `E(4)` | `INTINTERFACEDOC.REV` (`56`) | - |
| 责任人 | `AM(38)` | `INTINTERFACEDOC.RESP_SHEZONG` (`55`) | `RE_OPEN_RESP_SHEZONG` (`61`), `RELEVANT_PERSON` (`62`) |

## 5. 文件3（外部需打开接口）

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `ICMACP1000.PROJ_NUM` (`28`) | 文件名项目号兜底 |
| 接口号 | `C(2)` | `ICMACP1000.ITEM_NUMBER` (`27`) | `INTERFACE_IDENT` (`38`) |
| 科室 | `AO(40)` | `ICMACP1000.RESP_DEPART` (`40`) | `RESP_SHEZONG` (`43`) -> `USER/DEPARTMENT` |
| 接口时间 | `M(12)` 或 `L(11)` | `ICMACP1000.PRE_OPEN_DATE` (`57`) | `FINAL_OPEN_DATE` (`60`) |
| 完成标记 | `Q(16)` 或 `T(19)` | `ICMACP1000.FINAL_OPEN_DATE` (`60`) | `PRE_OPEN_DATE` (`57`) |
| 版次 | `AC(28)` | `ICMACP1000.LATEST_IITF_REV` (`78`) | 需与业务确认最终版次口径 |
| 责任人 | `AP(41)` | `ICMACP1000.RESP_SHEZONG` (`43`) | `DELAY_OPEN_PERSON` (`91`) |

## 6. 文件4（外部需回复接口）

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `ICMACP1000.PROJ_NUM` (`28`) | 文件名项目号兜底 |
| 接口号 | `E(4)` | `ICMACP1000.ITEM_NUMBER` (`27`) | - |
| 科室 | `AG(32)` | `ICMACP1000.RESP_DEPART` (`40`) | `RESP_SHEZONG` (`43`) -> `USER/DEPARTMENT` |
| 接口时间 | `S(18)` | `ICMACP1000.PRE_CLOSE_DATE` (`58`) | `FINAL_CLOSE_DATE` (`61`), `CLOSE_DATE` (`46`) |
| 完成标记 | `V(21)` | `ICMACP1000.FINAL_CLOSE_NUM` (`62`) | `PRE_CLOSE_NUM` (`59`) |
| 版次 | `I(8)` | `ICMACP1000.LATEST_IITF_REV` (`78`) | 需与业务确认最终版次口径 |
| 责任人 | `AH(33)` | `ICMACP1000.RESP_SHEZONG` (`43`) | `CHAGE_PERSON` (`89`), `CREATED_BY_ID` (`5`) |

## 7. 文件5（三维提资接口）

| 程序字段 | Excel列（现程序） | SQL映射 |
|---|---|---|
| 接口号 | `A(0)` | 待确认 |
| 科室 | `G(6)` | 待确认 |
| 接口时间 | `L(11)` | 待确认 |
| 完成标记 | `N(13)` | 待确认 |
| 责任人 | `K(10)` | 待确认 |

说明：文件5当前未纳入 `sql_explorer` 模板与离线验证范围，建议先补一份文件5样本并单独做字段定位。

## 8. 文件6（收发文函）

### 8.1 主映射（文函口径）

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `TA.PROJ_NUM` (`23`) | 文件名项目号兜底 |
| 收发文编号/接口号 | `E(4)` | `SENDRECEIVEDATA.CORRESP_LETTER_REC_NO` (`27`) | `LETTER_SEND_NO` (`35`), `TA.ITEM_NUMBER` (`28`) |
| 接口时间（要求回文期限） | `I(8)` | `SENDRECEIVEDATA.REPLY_DEADLINE` (`30`) | `TA.NEED_REPLY_DATE` (`47`) |
| 完成时间（我方回文日期） | `J(9)` | `SENDRECEIVEDATA.ANSWER_DATE` (`32`) | `SEND_DATE` (`36`) / `RECEIVE_DATE` (`37`) |
| 回文状态 | `M(12)` | `SENDRECEIVEDATA.IS_ANSWERED` (`31`) | `NEED_REPLY` (`29`) + 日期规则推导 |
| 主办部门（所） | `V(21)` | `SENDRECEIVEDATA.AUTHOR_UNIT` (`23`) / `RECEIVE_UNIT` (`24`) | 需按组织映射字典归一化 |
| 主办室 | `W(22)` | （通常由组织映射衍生） | - |
| 责任人 | `X(23)` | `SENDRECEIVEDATA.CREATED_BY_ID` (`4`) -> `USER/DEPARTMENT` | `MODIFIED_BY_ID` (`8`) |
| 版次 | `AC(28)` | 文函主表无稳定版次字段 | 需业务定义 |

### 8.2 兼容映射（接口单口径的“收发文清单”导出版）

在 `example/收发文清单1818.xlsx` 中，`E` 列值形态与 `INTINTERFACEDOC.ITEM_NUMBER` 一致（如 `1818-5-...`），因此需保留兼容方案：

- 接口号：`INTINTERFACEDOC.ITEM_NUMBER` (`27`)
- 项目号：`INTINTERFACEDOC.PROJ_NUM` (`28`)
- 期限：`INTINTERFACEDOC.REPLY_DEADLINE` (`57`)
- 回文日期：`INTINTERFACEDOC.ANSWER_DATE` (`58`)
- 责任人：`INTINTERFACEDOC.RESP_SHEZONG` (`55`) / `RE_OPEN_RESP_SHEZONG` (`61`)

## 9. 责任人ID统一解析（所有文件通用）

当责任人字段为 32 位 ID 时，统一解析链路如下：

1. 取责任人列中的 ID（可多值）
2. 关联 `USER.id`
3. 姓名优先级：`LAST_NAME + FIRST_NAME` > `KEYED_NAME` > `LOGIN_NAME`
4. 科室关联：`USER.DEPARTMENT` -> `DEPARTMENT.id`
5. 输出字段：姓名、登录名、科室名称、科室编码（`DEPT_NUMBER`）

---

如果你需要，我可以在下一步把这份对照表再导出成一份 `CSV`（每行一条“文件类型+字段”的映射），方便你直接给开发或DBA落配置。

> [测试改动] 用于验证 Agent 的改动高亮/Keep/Undo 面板，测试后可直接删除。

