# 待处理文件 SQL 对照表（阶段1离线版）

## 1. 适用范围

- 本表用于“Excel待处理文件 -> CIMS SQL”平替映射梳理。
- 依据来源：
  - `core/main.py`（现网筛选逻辑与Excel列位）
  - `example/template_spec.json`（文件1/2/3/4/6模板基线）
  - `example/CIMS-SQL-3.5/*.sql`（基础业务快照）
  - `example/CIMS-sql-3.7/*.sql`（流程增量快照）
  - `example/CIMS-SQL-3.5/EXCEL导出数据/*.xlsx`（整合版模板样本）
- 说明：
  - `col_idx` 为 SQL 表内 0-based 列序号。
  - 人员字段多为 32 位 ID，需经 `USER/DEPARTMENT` 解析成“姓名@login”。

## 2. 总览（按文件类型）

| 文件类型 | 文件名规则（简） | 业务名称 | 主SQL表 | 状态 |
|---|---|---|---|---|
| 1 | `xxxx按项目导出IDI手册*.xlsx` | 内部需打开接口 | `innovator.IDIACP1000` | 已验证 |
| 2 | `内部接口信息单报表xxxx*.xlsx` | 内部需回复接口 | `innovator.INTINTERFACEDOC` + `innovator.INTINTERFACEDOCIDIACP1000` | 部分已定稿 |
| 3 | `外部接口ICM报表xxxx*.xlsx` | 外部需打开接口 | `innovator.ICMACP1000` | 已验证 |
| 4 | `外部接口单报表xxxx*.xlsx` | 外部需回复接口 | `innovator.SENDRECEIVEDATA` + `innovator.IICS/IITF` | 部分已定稿 |
| 5 | `xxxx接口提资清单*.xlsx` | 三维提资接口 | 暂无稳定SQL映射 | 待确认 |
| 6 | `收发文清单*.xlsx` | 收发文函 | `innovator.INTINTERFACEDOC` + `innovator.SENDRECEIVEDATA`（对象层含 `FILETRANSMISSION / TA / CR / NCR ...`） | 部分已定稿 |

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

> 当前以 `example/CIMS-SQL-3.5/EXCEL导出数据` 7 个项目复合样本、`example/CIMS-SQL-3.5` SQL，以及 Word 权威路径说明为准。  
> 最新收口结论见 `document/12_CIMS-SQL-3.5_3.7_SQL运行链统一汇总_20260311.md`。

| 程序字段 | Excel列 | SQL主映射（当前口径） | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `INTINTERFACEDOC.PROJ_NUM` | 文件名项目号兜底 |
| 信息单编号 | `A(0)` | `INTINTERFACEDOC.ITEM_NUMBER` | - |
| 日期 | `B(1)` | `current INTINTERFACEDOC.SUBMIT_DATE` | `RELEASE_DATE`, `MODIFIED_ON` |
| 对方文号 | `D(3)` | `INTINTERFACEDOC.REF_ITEM_NUMBER` | - |
| 接口号（程序口径） | `R(17)` | `IDIACP1000.ITEM_NUMBER`（经 `INTINTERFACEDOCIDIACP1000` 关联） | `A` 仅对应信息单页编号，不作为程序 `interface_id` |
| 回复页编号 | `P(15)` | `reply INTINTERFACEDOC.ITEM_NUMBER` | - |
| 科室 | `I(8)` | `INTINTERFACEDOC.PROPOSED_DEPT` | `RECEIVE_DEPT` |
| 回文期限 | `M(12)` | 报表派生 `B + 14天` | 不再使用 `REPLY_DEADLINE` |
| 回文日期 / 完成标记 | `N(13)` | `reply INTINTERFACEDOC.RELEASE_DATE` | `reply MODIFIED_ON`, `reply SUBMIT_DATE` |
| 版次 | `E(4)` | `INTINTERFACEDOC.REV` | - |
| 责任人 | （Excel无稳定原生列） | 流程/分发链方向成立，但当前 dump 未闭环 | 工程回退 `INTINTERFACEDOC.MODIFIED_BY_ID -> USER` |
| 责任角色 | `AM(38)` | 非稳定导出列 | 不作为映射依据 |

### 4.1 当前已定稿部分

- 主对象路径：
  - `A -> INTINTERFACEDOC.ITEM_NUMBER = 90169 / 90177 = 99.9911%`
  - `(A,D) -> INTINTERFACEDOC.(ITEM_NUMBER, REF_ITEM_NUMBER) = 90169 / 90177 = 99.9911%`
  - `R -> INTINTERFACEDOCIDIACP1000 -> IDIACP1000.ITEM_NUMBER = 89979 / 90177 = 99.7804%`
- `B` 列：
  - Word 示例 `1915-X-CSP-ZL-22D1-B-006` 的“提出日期 2025-10-23 09:14:04”与 `current INTINTERFACEDOC.SUBMIT_DATE` 精确对齐
  - 跨项目抽样也稳定落在当前传递页时间字段，不再走回复页
- 回复页路径：
  - `P -> reply INTINTERFACEDOC.ITEM_NUMBER = 43028 / 43031 = 99.9930%`
- `M` 列：
  - `M = B + 14天 = 54539 / 54544 = 99.9908%`
  - 已确认是 Excel 派生列，不再继续直连 SQL 日期字段
- `N` 列：
  - `reply RELEASE_DATE = 42742 / 43031 = 99.3284%`
  - `reply MODIFIED_ON = 42597 / 43031 = 98.9914%`
  - `reply SUBMIT_DATE = 41211 / 43031 = 95.7705%`

### 4.2 当前未定稿部分

- 责任人链：
  - `INT -> WORKFLOWPROCESSESBIND = 76313 / 80382 = 94.9379%`
  - `INT -> USERVOTERECORD = 39796 / 80382 = 49.5086%`
  - `INT -> DISTRIBUTERECORD = 0 / 80382 = 0.0000%`
- `AM` 非空仅 `6 / 90177`，确认不是稳定原生导出列。

### 4.3 当前工程口径

- 程序内主对象仍以 `R -> IDIACP1000` 为 `interface_id` 口径。
- 文件2时间判断需拆成“传递页对象 + 回复页对象”两层。
- 若当前必须落代码：
  - `B` 用 `current INTINTERFACEDOC.SUBMIT_DATE`
  - `M` 直接按 `B + 14天` 派生
  - `N` 先用 `reply INTINTERFACEDOC.RELEASE_DATE`
  - 责任人先保留 `INTINTERFACEDOC.MODIFIED_BY_ID -> USER` 回退口径

## 5. 文件3（外部需打开接口）

| 程序字段 | Excel列 | SQL主映射 | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `ICMACP1000.PROJ_NUM` (`28`) | 文件名项目号兜底 |
| 接口号 | `C(2)` | `ICMACP1000.ITEM_NUMBER` (`27`) | `INTERFACE_IDENT` (`38`) |
| 发布方 | `I(8)` | `ICMACP1000.RELEASE_PARTY` (`35`) | - |
| 主办所 | `AL(37)` | `ICMACP1000.RESP_DEPART` (`40`) | 前缀比对优先 |
| 预报日期 | `L(11)` / `M(12)` | `ICMACP1000.PRE_FORECAST_DATE` (`44`) / `FINAL_FORECAST_DATE` (`45`) | - |
| 实际打开日期 | `Q(16)` / `T(19)` | `ICMACP1000.PRE_OPEN_DATE` (`57`) / `FINAL_OPEN_DATE` (`60`) | - |
| 版次 | `AC(28)` | `ICMACP1000.LATEST_IITF_REV` (`78`) | 需与业务确认最终版次口径 |
| 责任人 | `AP(41)` | 页面语义为所内编制人；空值时走管理员提醒逻辑 | 当前库内最近字段 `RESP_SHEZONG` (`43`)，但不作全量定稿 |

### 5.1 当前结论

- `C -> ICMACP1000.ITEM_NUMBER = 23638 / 23641 = 99.9873%`
- `I -> RELEASE_PARTY = 23622 / 23641 = 99.9196%`
- Word 与样本表头已确认：
  - `L/M` 是初版/终版预报日期
  - `Q/T` 是初版/终版实际打开日期
- 文件3主对象路径已清晰，但 `AP` 因存在“空值时管理员提醒逻辑在 CIMS 外”的情况，仍不能宣称已 100% SQL 闭环

## 6. 文件4（外部需回复接口）

> 当前以 `example/CIMS-SQL-3.5/EXCEL导出数据` 7 个项目复合样本、`example/CIMS-SQL-3.5` SQL，以及 Word 权威路径说明为准。  
> 最新收口结论见 `document/12_CIMS-SQL-3.5_3.7_SQL运行链统一汇总_20260311.md`。

| 程序字段 | Excel列 | SQL主映射（当前口径） | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | 文件名项目号兜底 | - |
| 对象类型 | `A(0)` | `IICS / IITF` 分流标记 | - |
| 接口单号 | `E(4)` | `SENDRECEIVEDATA.LETTER_SEND_NO` | `CORRESP_LETTER_REC_NO` 仅作辅助命中 |
| 接口时间 | `F(5)` | 分支口径：`A=IICS -> IICS.MODIFIED_ON`，`A=IITF -> IITF.MODIFIED_ON` | 对应 `RELEASE_DATE` 也非常接近 |
| 处理方 | `P(15)` | 报表派生：`A=IICS -> AB(发布方)`；`A=IITF -> AC(接收方)` | 不是稳定 SQL 直连列 |
| 回文期限 | `S(18)` | 报表派生：`F + 20天` | 不是 `SENDRECEIVEDATA.REPLY_DEADLINE` |
| 回文日期 | `V(21)` | `SENDRECEIVEDATA.ANSWER_DATE` | `SENDRECEIVEDATA.MODIFIED_ON` |
| 科室 | `AG(32)` | 待进一步核实 | 旧 `ICMACP1000.RESP_DEPART` 口径不再作为主结论 |
| 责任人 | `AH(33)` | `DISTRIBUTERECORD` 分发表最末级办理人（按 `项目号 + 接口编码` 路由码匹配） | 当前工程回退 `IITF无路由 -> IICS leaf；IITF/IICS都无路由 -> IICS.CREATED_BY_ID` |
| 版次 | `I(8)` | 待与业务确认最终显示口径 | `IICS/IITF.REV` 待核实 |

### 6.1 当前已定稿部分

- 主入口：
  - `E -> SENDRECEIVEDATA.LETTER_SEND_NO = 75194 / 77185 = 97.4205%`
  - `E -> IITF.ITEM_NUMBER（直连） = 0 / 77185`
- `F` 为双分支对象日期：
  - `A = IICS -> IICS.MODIFIED_ON = 37540 / 40013 = 93.8195%`
  - `A = IITF -> IITF.MODIFIED_ON = 35487 / 37167 = 95.4799%`
- `S` 为 Excel 派生：
  - `S = F + 20天 = 57855 / 57856 = 99.9983%`
- `V`：
  - `SENDRECEIVEDATA.ANSWER_DATE = 49700 / 51877 = 95.8035%`
- `P`：
  - `A = IICS -> AB`，`A = IITF -> AC = 65360 / 72397 = 90.2800%`

### 6.2 当前未定稿部分

- 基于 Word 版业务规则与当前统一运行链，`AH` 的真实业务口径已修正为：
  - 先用 Excel `W(22)` `接口编码` 作为路由码
  - 再按 `项目号 + 路由码` 去 `DISTRIBUTERECORD.BO_TITLE`
  - 在 `IITF/IICS` 分发表里取“办理人继续分发则下沉，否则停留为叶子”的最末级办理人
  - 若叶子办理人有多人，只要其中任一人与 Excel `AH` 名称匹配，即算命中
- 这条链已经证明方向正确，但当前 dump 仍不能全量闭环。`AH` 非空 `41814` 行时：
  - `按 A 分支取分发表 latest leaf any-match = 4873 / 41814 = 11.6540%`
  - `按 A 分支取分发表 union leaf any-match = 5323 / 41814 = 12.7302%`
  - `固定取 IITF 分发表 latest leaf any-match = 6425 / 41814 = 15.3657%`
  - `固定取 IITF 分发表 union leaf any-match = 6968 / 41814 = 16.6643%`
  - `IITF + IICS 分发表 union leaf any-match = 9716 / 41814 = 23.2362%`
- 这说明：
  - Word 口径“责任人看分发信息最末级办理人”是对的，且优于旧的 `CREATED_BY_ID` / `USERVOTERECORD.OPERATOR`
  - 文件4责任人更接近 `IITF` 分发表，而不是当前对象创建人或最后投票人
  - 但 `DISTRIBUTERECORD` 只覆盖了 `3790` 个 `项目号 + 类型 + 路由码` 键，而 Excel 中有 `17033` 个 `项目号 + A类型 + 路由码` 组合，因此大部分缺口来自“分发表本身无对应路由”，不是叶子匹配规则错误
  - `1915` 项目在当前 `DISTRIBUTERECORD` 中 `externalInterface.ExtIITF/IICS` 行数为 `0`，因此该项目责任人命中必然为 `0`
- 缺失路由子集再次确认：
  - `无 IITF 路由 -> IICS.CREATED_BY_ID = 19273 / 29509 = 65.3123%`
  - `IITF/IICS 都无路由 -> IICS.CREATED_BY_ID = 18232 / 25241 = 72.2317%`
- 因此可推导的工程综合规则为：
  - `IITF leaf -> 否则 IICS.CREATED_BY_ID = 26241 / 41814 = 62.7565%`
  - `IITF leaf -> 否则 IICS leaf -> 否则 IICS.CREATED_BY_ID = 27948 / 41814 = 66.8389%`
- 因此，`AH` 的业务真值方向已经定稿，但现有 SQL 快照仍未覆盖全部待处理文件4责任人链路

### 6.3 当前工程口径

- 文件4主入口固定为 `E -> SENDRECEIVEDATA`，不再使用 `ICMACP1000` 作为主表结论。
- 若当前必须落代码：
  - `F` 按 `A(IICS/IITF)` 分支到对象日期字段
  - `S` 直接按 `F + 20天` 派生
  - `V` 优先落 `SENDRECEIVEDATA.ANSWER_DATE`
  - `P` 按 `A = IICS -> AB`、`A = IITF -> AC` 复原
  - `AH` 先尝试 `项目号 + 接口编码 -> IITF 分发表 -> 最末级办理人(多人任一命中)`
  - 若 `IITF` 无路由记录，再尝试 `IICS 分发表 -> 最末级办理人`
  - 若 `IITF/IICS` 都无路由记录，再回退 `IICS.CREATED_BY_ID`
  - 当前这条三段式工程规则的派生命中为 `27948 / 41814 = 66.8389%`
  - 对外说明时不得宣称文件4 `AH` 已全量闭环

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

> 最新统一口径以 `document/12_CIMS-SQL-3.5_3.7_SQL运行链统一汇总_20260311.md`、`document/13_CIMS-SQL-3.5_文件6_SQL深挖复核_20260311.md` 为准。

### 8.1 总路由

| 程序字段 | Excel列 | 当前SQL口径 | 状态 |
|---|---|---|---|
| 收发文编号 | `E(4)` | `-ZL-` 样式走 `INTINTERFACEDOC.ITEM_NUMBER`；其余文函号走 `SENDRECEIVEDATA.(CORRESP_LETTER_REC_NO / LETTER_SEND_NO)` | 已定稿 |
| 接口时间 / 要求回文期限 | `I(8)` | `INT -> REPLY_DEADLINE`；`SEND -> REPLY_DEADLINE` | 部分已定稿 |
| 我方回文日期 | `J(9)` | `INT -> ANSWER_DATE`；`SEND -> ANSWER_DATE` | 已定稿 |
| 回文状态 | `M(12)` | `INT -> ANSWER_DATE / REPLY_DEADLINE` 派生；`SEND -> ANSWER_DATE / REPLY_DEADLINE / IS_ANSWERED` 派生 | 已定稿 |
| 主办部门（所） | `V(21)` | 业务真值应取“分发全过程办理人对应单位并集”；当前 SQL 仅能做弱恢复 | 未闭环 |
| 主办室 | `W(22)` | 业务真值应取“分发全过程办理人对应科室并集”；当前 SQL 仅能做弱恢复 | 未闭环 |
| 主办人 | `X(23)` | 业务真值应取“分发全过程办理人并集”；Excel/SQL 多值任一交集命中即算命中 | 业务真值已定，SQL未闭环 |
| 版次 | `AC(28)` | `INT` 分支可弱映射 `REV`；`SEND` 分支暂无稳定字段 | 未闭环 |
| 是否回文 | `H(7)` | 本轮按用户要求暂不继续追，保留旧结论 | 暂缓 |

### 8.2 当前命中率

- 总体路由：`4001 / 4178 = 95.7635%`
- `INT` 分支：`1056`
  - `E -> ITEM_NUMBER = 100.0000%`
  - `I -> REPLY_DEADLINE = 100.0000%`
  - `J -> ANSWER_DATE = 81.9129%`
  - `M` 派生 = `92.7083%`
  - `AC -> REV = 60.8902%`
- `SEND` 分支：`2945`
  - `E -> CORRESP/LETTER_SEND = 100.0000%`
  - `I -> REPLY_DEADLINE = 58.6078%`
  - `J -> ANSWER_DATE = 94.3633%`
  - `M` 派生：
    - 按 `2026-03-04` 复算 = `75.1783%`
    - 按 `2026-03-11` 复算 = `71.3413%`
- 对象族信号：
  - `FILETRANSMISSION` 直连信号 `635` 行
  - `TA = 81` 行
  - `CR = 50` 行
  - `NCR = 6` 行

### 8.3 分发表、主办人、单位、科室结论

- 本轮已按用户修正规则重算：
  - `X` 看分发全过程办理人并集
  - `V/W` 看这些办理人对应的单位/科室并集
  - Excel 多值与 SQL 多值只要任一交集命中，即算命中
- 新增探针：`scripts/db_tools/sql_explorer/file6_distribution_chain_probe.py`
- 结果文件：`tmp/file6_distribution_chain_probe_20260312.json`
- 本轮 `DISTRIBUTERECORD` 全表扫描结果：
  - `statement_count = 2372886`
  - `matched_count = 582`
  - `matched_by_title_count = 582`
  - `group_count = 116`
- 这说明旧的“文件6分发表整体 0 命中”结论已经失效；至少 `INT` 分支存在真实分发表链，之前漏掉了：
  - `INTINTERFACEDOC` 同链扩展
  - 紧凑内部接口号标题码提取
  - `SOURCE_OBJECT_ID + BO_TITLE` 双桥反查
- 但当前命中仍然很低，且几乎全部集中在 `INT` 分支：
  - `INT X_all = 2 / 1055 = 0.1896%`
  - `INT V_all = 14 / 1055 = 1.3270%`
  - `INT W_all = 3 / 999 = 0.3003%`
  - `SEND X_all = 0 / 911 = 0.0000%`
  - `SEND V_all = 0 / 911 = 0.0000%`
  - `SEND W_all = 0 / 459 = 0.0000%`
- 版本最佳样本总体命中同样很低：
  - `X_all = 2 / 1966 = 0.1017%`
  - `V_all = 14 / 1966 = 0.7121%`
  - `W_all = 3 / 1458 = 0.2058%`
- 但这不是文件6发送侧“完全无链”，而是主链类型判断错了。新增流程探针：
  - 脚本：`scripts/db_tools/sql_explorer/file6_send_workflow_probe.py`
  - 结果：`tmp/file6_send_workflow_probe_20260312.json`
  - 对 `SEND` 版本最佳样本 `2958` 行，已有 `1413` 行能落到 `WORKFLOWPROCESSESBIND / USERVOTERECORD`
  - workflow/vote 并集命中：
    - `X_all = 409 / 2958 = 13.8310%`
    - `V_all = 1098 / 2958 = 37.1021%`
    - `W_all = 560 / 2958 = 18.9542%`
- 分类型看，文件6 `A` 列确实对应不同存储逻辑：
  - `备忘录 / 图文传真`：当前主桥是 `OBJECTREPLYLINK -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
  - `文件传递单 / TA / CR / NCR`：当前主桥是 `主对象(FILETRANSMISSION / TA / CR / NCR) -> WORKFLOWPROCESSESBIND / USERVOTERECORD`
  - `DISTRIBUTERECORD` 对文件6发送侧只保留为补充链，不再作为主链
- 这轮还确认了两个反证样本：
  - `TA: EHMC-420045-ECZS-0077`
  - `文件传递单: ECZB-770687-EDMB`
  - 两者都能在主对象表和 workflow/vote 中找到，但在当前 `DISTRIBUTERECORD` 中找不到对应文号和对象 ID
- 已命中的代表性样本证明规则方向正确，但覆盖不足：
  - `2016-X-RVD-ZL-25A6-S-092`：`X` 可由分发表全链命中 `于婷`，`W` 可命中 `工艺系统室`
  - `2016-X-FNP-ZL-25A5-S-137`：`V` 可命中 `河北分公司.核电工艺所`
- 当前主矛盾已经收口为：
  - `INT` 分支存在真实 `DISTRIBUTERECORD` 链，但覆盖极低
  - `SEND` 分支的主链应转到 workflow/vote，而不是继续强压 `DISTRIBUTERECORD`
  - 仍为 `0` 的发送侧类型，本质上是主对象表还没导出齐
    - `EXTERNALMINUTES`
    - `FUNOTIFY`
    - `CANCELNOTIFY`
    - `DESIGNREVIEWOPNION`
    - `DESIGNREVIEWREPLY`
- 因此当前不能把 `X/V/W` 写成任何单一 SQL 直字段，但已经可以按类型拆成稳定主链，而不是继续写成“整体未闭环”。

### 8.4 现阶段工程判断

- 文件6已定稿的部分：`路由 / I / J / M`
- 文件6当前重点未闭环的部分：`X / V / W / AC`
- 文件6发送侧 `X/V/W` 的最终实现必须纳入 `WORKFLOWPROCESSESBIND / USERVOTERECORD`
- `H` 本轮按要求暂不继续追
- `core/main.py` 当前文件6最终筛选结果，用 SQL 规则回放后的最终集合一致率约 `99.5751%`，但这不等于字段已经全部闭环，只能说明当前筛选逻辑可近似复算

## 9. 责任人ID统一解析（通用）

1. 提取责任人列中的 32 位 ID（支持多值）
2. 关联 `USER.id`
3. 姓名优先级：`LAST_NAME + FIRST_NAME` > `KEYED_NAME` > `LOGIN_NAME`
4. 科室关联：`USER.DEPARTMENT` -> `DEPARTMENT.id`
5. 输出：姓名、登录名、科室名称、科室编码（`DEPT_NUMBER`）

