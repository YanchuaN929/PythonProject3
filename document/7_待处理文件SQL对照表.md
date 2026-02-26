# 待处理文件 SQL 对照表（阶段1离线版）

## 1. 适用范围

- 本表用于“Excel待处理文件 -> CIMS SQL”平替映射梳理。
- 依据来源：
  - `core/main.py`（现网筛选逻辑与Excel列位）
  - `example/template_spec.json`（文件1/2/3/4/6模板基线）
  - `example/CIMS-sql/*.sql`（离线快照）
- 说明：
  - `col_idx` 为 SQL 表内 0-based 列序号。
  - 人员字段多为 32 位 ID，需经 `USER/DEPARTMENT` 解析成“姓名@login”。

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

> 以下“角色列/责任人列”依据 `example/1818按项目导出IDI手册2026-01-28-15_11_50.xlsx` 与 `example/CIMS-sql/IDIACP1000.sql` 实测校验。

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `IDIACP1000.PROJ_NUM` (`col_idx=28`) | 文件名项目号兜底 |
| 接口号 | `A(0)` | `IDIACP1000.ITEM_NUMBER` (`27`) | - |
| 科室 | `H(7)` | `IDIACP1000.RELEASE_PARTY` (`36`) | - |
| 接口时间 | `K(10)` | `IDIACP1000.SWAP_START_DATE` (`40`) | `IDIACP1000.ACTUAL_OPEN_DATE` (`44`) |
| 完成标记（当前程序口径） | `M(12)` | `IDIACP1000.ACTUAL_OPEN_DATE` (`44`) | `IDIACP1000.ACTUAL_CLOSE_DATE` (`45`) |
| 责任人列（所编制人） | `R(17)` | `IDIACP1000.DEPART_USER` (`39`) -> `USER/DEPARTMENT` | `DELAY_OPEN_PERSON` (`63`), `CREATED_BY_ID` (`5`) |

### 3.1 文件1实测匹配率（6299/6299 行可对齐）

- `发布方(H)` -> `RELEASE_PARTY`：`100%`
- `首发时间(K)` -> `SWAP_START_DATE`：`99.7777%`
- `完成标记(M)` -> `ACTUAL_OPEN_DATE`：`99.7120%`
- `角色列(设总Q，可选校验)` -> `RESP_SHEZONG`：
  - 当前记录口径（`IS_CURRENT`优先）=`99.9524%`
  - 全版本口径（同接口号任一版本可命中）=`100%`
- `责任人列(所编制人R)` -> `DEPART_USER`：
  - 原值直比=`84.95%`
  - 去除姓名尾部字母（a/b/d）后=`99.8095%`
  - 未命中的 7 条为占位账号差异（如 `111@1112311` vs `weicc111@1112311`）

### 3.2 责任人还需要“别名对照表”

结论：是的，需要。仅靠 `USER` 表无法覆盖少量历史/占位写法，建议增加一份“责任人别名对照表”（本地配置）：

| excel值 | 规范值 | 用途 |
|---|---|---|
| `111@1112311` | `weicc111@1112311` | 修正占位账号 |
| `张海波a@zhanghba` | `张海波@zhanghba` | 去尾字母规范化 |
| `杨健d@yangjiand` | `杨健@yangjiand` | 去尾字母规范化 |

### 3.3 文件1人员一致性判定规则（新增，按你的要求）

用于判定类似 `刘婧d@liujingd` 与 `刘婧@liujingd` 是否同一人。

1. **规则A（优先）**：`@` 后登录名一致即判定为同一人  
   - 例：`刘婧d@liujingd` == `刘婧@liujingd`
2. **规则B（补充）**：若登录名缺失或不稳定，中文姓名一致即判定为同一人  
   - 因 `姓名角色表.xlsx` 主要是中文姓名，这一规则必须保留
3. **规范化步骤**：姓名尾部字母标记（`a/b/d` 等）在比较前去除

按以上规则重算后（仅看最新版本）：

- 文件1责任人列 `R(17) -> DEPART_USER`：`6169 / 6173 = 99.9352%`
- 剩余未命中 4 条（确认为真实人员不一致，不是别名问题）：
  - `S-VAB---1NY-01-25A3-25B3`：`张烨@zhangyea` vs `卢艳超@luycd`
  - `S-VMO---1ND-01-25A3-25B1`：`韩旭亮@hanxl` vs `赵若愚@l-zhaory`
  - `B-FNP-BA-1GH-01-22Q8-22D3`：`张进@zhangjinc` vs `柏慧@baihui`
  - `B-WAI-BA-1GH-02-22Q8-22D1`：`刘桂林@liugl` vs `薛佳@xuejia`

### 3.4 文件1版本口径（仅最新版本，不看旧版本）

你要求“只关注最新版本”，在 `IDIACP1000` 中建议按以下顺序判定：

1. **主条件**：`IS_CURRENT = '1'` 视为当前版本  
2. **版本族**：`CONFIG_ID` 标识同一对象的版本链  
3. **版本号字段**：`MAJOR_REV` / `MINOR_REV`（可作辅助展示）  
4. **并列处理**：若同一 `ITEM_NUMBER` 出现多条 `IS_CURRENT='1'`（样本里有 3 个），取 `MODIFIED_ON` 最大者

离线快照统计（项目 1818）：

- `ITEM_NUMBER` 总数：`7333`
- 有多版本记录的接口：`5615`
- 出现多条 `IS_CURRENT='1'` 的接口：`3`

因此：`document/8_文件1未命中明细.json` 中“历史版本命中”这一类，在你当前口径下应统一按“当前版本不一致”处理，不再作为命中。

## 4. 文件2（内部需回复接口）

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
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

说明：文件5当前未纳入 `sql_explorer` 模板与离线验证范围，建议补样本后单独定位。

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

### 8.2 兼容映射（接口单口径“收发文清单”导出版）

在 `example/收发文清单1818.xlsx` 中，`E` 列值形态与 `INTINTERFACEDOC.ITEM_NUMBER` 一致（如 `1818-5-...`），需保留兼容方案：

- 接口号：`INTINTERFACEDOC.ITEM_NUMBER` (`27`)
- 项目号：`INTINTERFACEDOC.PROJ_NUM` (`28`)
- 期限：`INTINTERFACEDOC.REPLY_DEADLINE` (`57`)
- 回文日期：`INTINTERFACEDOC.ANSWER_DATE` (`58`)
- 责任人：`INTINTERFACEDOC.RESP_SHEZONG` (`55`) / `RE_OPEN_RESP_SHEZONG` (`61`)

## 9. 责任人ID统一解析（通用）

1. 提取责任人列中的 32 位 ID（支持多值）
2. 关联 `USER.id`
3. 姓名优先级：`LAST_NAME + FIRST_NAME` > `KEYED_NAME` > `LOGIN_NAME`
4. 科室关联：`USER.DEPARTMENT` -> `DEPARTMENT.id`
5. 输出：姓名、登录名、科室名称、科室编码（`DEPT_NUMBER`）

