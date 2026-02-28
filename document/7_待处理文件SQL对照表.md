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

> 以下按“先优化映射、再做离线全量验证”执行。  
> 数据源：`example/CIMS-sql/INTINTERFACEDOC.sql`（配套 `USER.sql`、`DEPARTMENT.sql`）。  
> 统计口径：`IS_CURRENT in ('1', '')`，并同时输出 `current全量` 与 `1818项目` 结果。  
> 验证产物：`document/file2_sql_mapping_metrics_v3.json`、`document/file2_owner_metrics_v2.json`。

| 程序字段 | Excel列 | SQL主映射（优化后） | SQL回退/补充 |
|---|---|---|---|
| 项目号 | 文件名4位 | `INTINTERFACEDOC.PROJ_NUM` (`28`) | 文件名项目号兜底 |
| 接口号（程序口径） | `R(17)` | `IDIACP1000.ITEM_NUMBER`（经 `INTINTERFACEDOCIDIACP1000` 关联） | `INTINTERFACEDOC.ITEM_NUMBER` 仅对应 A 列信息单编号，不作为程序 interface_id |
| 科室 | `I(8)` | `INTINTERFACEDOC.PROPOSED_DEPT` (`38`) | `RECEIVE_DEPT` (`39`) + 责任人部门映射 |
| 接口时间 | `M(12)` | `INTINTERFACEDOC.START_DATE` (`47`) | `ANSWER_DATE` (`58`), `REPLY_DEADLINE` (`57`) |
| 完成标记 | `N(13)` | `INTINTERFACEDOC.ANSWER_DATE` (`58`) | `ANSWER_TYPE` (`59`) |
| 版次 | `E(4)` | `INTINTERFACEDOC.REV` (`56`) | - |
| 责任人（完成人口径） | （Excel无原生列，程序人工补充） | `INTINTERFACEDOC.MODIFIED_BY_ID` (`9`) -> `USER` | `IDIACP1000.DEPART_USER` (`39`) -> `USER`, `IDIACP1000.MODIFIED_BY_ID` (`9`), `INTINTERFACEDOC.CREATED_BY_ID` (`5`) |
| 责任角色（设总口径，非完成人） | `AM(38)` | `INTINTERFACEDOC.RESP_SHEZONG` (`55`) | `RE_OPEN_RESP_SHEZONG` (`61`), `RELEVANT_PERSON` (`62`) |

### 4.1 文件2逐项对照结果（优化后）

- 项目号 `PROJ_NUM`：非空率 `100%`（`current全量` 与 `1818项目` 均为 `100%`）。
- 接口号 `ITEM_NUMBER`：非空率 `100%`（`current全量` 与 `1818项目` 均为 `100%`）。
- 科室候选：
  - `PROPOSED_DEPT` 命中组织/科室编码率：`8.9336%`（全量）、`13.5853%`（1818）
  - `RECEIVE_DEPT` 命中组织/科室编码率：`8.4492%`（全量）、`13.1451%`（1818）
  - 结论：`PROPOSED_DEPT` 略优，作为主映射。
- 接口时间候选：
  - `START_DATE` 可解析率：`31.8189%`（全量）、`41.0470%`（1818）
  - `ANSWER_DATE` 可解析率：`27.3145%`（全量）、`29.5476%`（1818）
  - `REPLY_DEADLINE` 可解析率：`0.5345%`（全量）、`0.1016%`（1818）
  - 结论：`START_DATE` 显著优于 `REPLY_DEADLINE`，调整为主映射。
- 完成标记 `ANSWER_DATE`：可解析率 `27.3145%`（全量）、`29.5476%`（1818），可作为“已回文完成时间”主口径。
- 版次 `REV`：非空率 `99.9568%`（全量）、`99.4514%`（1818），稳定可用。
- 责任人（完成人）候选（按 `ANSWER_DATE` 非空“已完成接口”复测）：
  - `INTINTERFACEDOC.MODIFIED_BY_ID`：`100%`（`4377/4377`）可解析到 `USER`
  - `INTINTERFACEDOC.CREATED_BY_ID`：`100%`（`4377/4377`）可解析到 `USER`，但语义偏“创建人”
  - `IDIACP1000.MODIFIED_BY_ID`：`99.6801%`
  - `IDIACP1000.DEPART_USER`：`97.6925%`
  - `INTINTERFACEDOC.RESP_SHEZONG`：`96.7101%`（设总角色，不作为“完成人”主口径）
  - 结论：文件2责任人主映射应采用 `INTINTERFACEDOC.MODIFIED_BY_ID -> USER`（不是设总列）。

### 4.2 文件2当前风险提示（仅记录，不改变映射结论）

- 在“科室命中且未完成（`ANSWER_DATE` 为空）”子集中：
  - `START_DATE` 可解析率：`5.1419%`（全量）、`4.1357%`（1818）
  - `REPLY_DEADLINE` 可解析率：`0.0551%`（全量）、`0.0530%`（1818）
- 说明：文件2的“待办记录”本身日期字段填充较低，后续进入在线库联调时建议增加“空日期兜底策略”（允许无日期记录按其他条件进入待处理池）。

### 4.3 文件2（1818模板）多表联动实测（仅按模块说明 69 行业务列）

> 本节仅针对 `document/2_模块功能说明.md:69` 的业务列：`A/F/I/M/N/AB`。  
> 样本：`example/内部接口信息单报表181820260128.xlsx`（15776 行）。  
> 联动链路：`INTINTERFACEDOC` -> `INTINTERFACEDOCIDIACP1000` -> `IDIACP1000` + `DEPARTMENT`。  
> 验证产物：`document/file2_multitable_alignment_1818_v6.json`、`document/file2_final_mismatch_8rows.json`。

| 业务列 | Excel含义 | SQL联动映射（1818） | 实测一致率 |
|---|---|---|---|
| A | 信息单编号 | `INTINTERFACEDOC.ITEM_NUMBER`（去横杠） | `99.9937%` |
| F | 传递/回复标记 | `INTINTERFACEDOC.RECEIVE_SEND_FLAG`（`1->传递`, `2->回复`） | `99.9937%` |
| I | 收文部门 | `INTINTERFACEDOC.RECEIVE_DEPT` -> `DEPARTMENT` 父子链拼接全路径 | `73.3646%`（文本逐字） |
| M | 回文期限 | `INTINTERFACEDOC.REPLY_DEADLINE` | `0.0317%`（文本逐字） |
| N | 回文日期 | `INTINTERFACEDOC.ANSWER_DATE` | `79.5322%`（文本逐字） |
| AB | 交换关闭时间 | `IDIACP1000.SWAP_CLOSE_DATE`（经桥表关联） | `96.5200%` |

说明：

- `I/M/N` 的“逐字一致率”受模板报表的派生展示影响明显（尤其 `M`），不能直接代表业务规则可对齐度。
- `A+E` 在 `INTINTERFACEDOC` 非唯一（同信息单可拆到多接收对象），需用 `R`（IDI 编号）经桥表辅助消歧，`R` 辅助匹配率 `88.4381%`。
- 本节表中 `A -> INTINTERFACEDOC.ITEM_NUMBER` 指“信息单编号口径”；程序内 `interface_id`（Registry / 版次筛选口径）仍是 `R` 列。

### 4.4 1818 业务规则一致率（按 69 行逻辑）

按 `P1/P2/P3/P4` 逐项对齐（日期窗口按模板日期 `2026-01-28` 校验）：

- `P1`（I 列科室条件）一致率：`96.9004%`
- `P2`（M 列日期范围）一致率：`96.8940%`
- `P3`（AB 以 4444 开头且 F=传递）一致率：`99.9810%`
- `P4`（N 空且 A 非空）全量一致率：`88.7931%`
- `P4` 在 `P1&P2` 业务作用域内一致率：`91.1504%`（>90%）

最终组合逻辑（1818 扩展逻辑）整体一致率：`99.9493%`。  
当前剩余未对齐 `8` 行（见 `document/file2_final_mismatch_8rows.json`），共性是：

- Excel 显示：`F=传递`、`N为空`、`M有期限`
- SQL 显示：`ANSWER_DATE` 已写入时间戳、`REPLY_DEADLINE` 为空（该 8 行在离线库中未找到可直接还原 Excel `M` 的稳定字段）

若要求该模板达到 `100%` 对齐，需增加一层“1818-文件2特例对照表”（8 条）作为最终兜底。  
已生成兜底样例：`document/file2_1818_special_overrides.json`。

### 4.5 文件2（1818）全量逐行复测（本轮：接口号 + 业务列 + 责任人）

> 验证产物：`document/file2_1818_full_validation_latest.json`。  
> 样本：`example/内部接口信息单报表181820260128.xlsx`（15776 行）。

- 接口号（程序口径，`R` 列）在数据库存在性：`15776/15776 = 100%`（`IDIACP1000.ITEM_NUMBER`）。
- `R` 经桥表联动到 `INTINTERFACEDOC`：`15775/15776 = 99.9937%`（唯一未联动样本：`A=18185CSPZL25A2S648, E=A, R=S-CSP-NLS-2LX-01-25A2-25A5`）。
- 业务列“逐字一致率”（含兜底后）：
  - `A=99.9937%`，`F=99.9937%`，`R=99.9937%`
  - `AB=96.5137%`，`N=79.5766%`
  - `I=11.2513%`，`M=0.2028%`
- 说明：`I/M` 在模板中存在明显“展示派生/人工加工”痕迹，按“逐字完全一致”口径难以达到 100%；业务筛选一致性仍以 `4.4`（`99.9493%`）作为判定口径。
- 责任人（已完成接口）复测结论（排除设总）：
  - 主列：`INTINTERFACEDOC.MODIFIED_BY_ID -> USER`，覆盖率 `100%`（`4377/4377`）
  - 证据：在已完成样本中，`CREATED_BY_ID` 与 `MODIFIED_BY_ID` 差异率 `4362/4363 = 99.9771%`，二者语义不可混用。
  - 推荐回退链：`INT.MODIFIED_BY_ID -> IDI.DEPART_USER -> IDI.MODIFIED_BY_ID -> INT.CREATED_BY_ID`（不使用 `RESP_SHEZONG` 作为完成人主口径）。

### 4.6 文件2/4“责任人分发链路”补充探针（备份版）

> 验证产物：`document/file2_4_distribution_chain_probe.json`。

本轮按你的思路，重点验证“文件2 D列（对方文号）/文件4 E列（接口单号）是否可作为分发记录主键”。

- 文件2（`D` 列）：
  - `D` 唯一键 `5415`，与 `INTINTERFACEDOC.ITEM_NUMBER` 唯一集合命中率 `100%`。
  - 与 `INTINTERFACEDOC.REF_ITEM_NUMBER` 唯一集合命中率也为 `100%`。
  - 行级 `(A,D)` 对在 `INT (ITEM_NUMBER, REF_ITEM_NUMBER)` 复核命中 `7238/7238 = 100%`。
  - 结论：`D` 可稳定作为 INT 侧“对方文号”键参与后续链路。

- 文件4（`E` 列）：
  - `E` 唯一键 `17822`，与 `SENDRECEIVEDATA.LETTER_SEND_NO` 命中率 `100%`。
  - 与 `CORRESP_LETTER_REC_NO` 命中率 `48.21%`（可作为辅键，不可替代主键）。
  - 结论：文件4责任人若走“分发链路”，`E -> SENDRECEIVEDATA.LETTER_SEND_NO` 是最稳定入口。

- 当前备份缺口（关键）：
  - 在 `innovator.sql` 结构中可见分发表：`DISTRIBUTERECORD`、`OBJECTREPLYLINK`、`FILETRANSMISSION`、`CRREPLY/DCRREPLY/FCRREPLY/NCRREPLY/TCRREPLY/TAREPLY` 等。
  - 但这些表在当前离线包中仅有 schema，无独立数据导出；可直接用的数据表仅 `INTINTERFACEDOC / SENDRECEIVEDATA / TA` 等 10 张。
  - 例如文件4 `E -> SEND.id` 后，落到 `TA.SEND_RECEIVE_DATA` 的覆盖率在该样本为 `0%`，说明责任人分发信息很可能落在尚未导出的其它业务表（而非 TA）。

- 建议的后续联表路径（待补数后验证）：
  1. 文件2：`(A,D)` -> `INTINTERFACEDOC(ITEM_NUMBER, REF_ITEM_NUMBER)` -> `INT.id`
     -> `DISTRIBUTERECORD.SOURCE_OBJECT_ID` / `OBJECTREPLYLINK.SOURCE_OBJECT_NUMBER`
     -> 分发操作人字段（如 `OPERATOR/SENDER`） -> `USER`。
  2. 文件4：`E` -> `SENDRECEIVEDATA.LETTER_SEND_NO` -> `SEND.id`
     -> `*_REPLY / FILETRANSMISSION / ...`（`SEND_RECEIVE_DATA`）
     -> `DISTRIBUTERECORD/OBJECTREPLYLINK`
     -> 分发责任人 -> `USER`。

### 4.7 文件2 I列（4所）专项结论 + 冲突样本独立清单

> 4所配置来源：`config.json`。  
> 全量复核报告：`document/file2_i_4profiles_check_latest.json`。  
> 冲突样本独立文件：`document/file2_i_conflict_samples.json`（仅保留 `sql_code_conflict` 全量行并追加原因诊断字段）。

| 所（profile） | Excel作用域行数 | `INT.RECEIVE_DEPT` 匹配率 | 结论 |
|---|---:|---:|---|
| 建筑结构所 | 1474 | 95.5902% | 非100%，主要受跨所代码/冲突编码影响 |
| 核工程研究设计所 | 1211 | 98.1833% | 非100%，主要为 SQL 未出现该所代码 |
| 电力工程研究设计所 | 111 | 100.0000% | 已达到100% |
| 电气自动化所 | 1928 | 99.3776% | 接近100%，存在少量冲突编码 |

对应未命中原因计数（`INT.RECEIVE_DEPT`）：

- 建筑结构所：`sql_no_profile_code=31`，`sql_code_conflict=21`，`excel_no_code_text_mismatch=13`
- 核工程研究设计所：`sql_no_profile_code=11`，`sql_code_conflict=0`，`excel_no_code_text_mismatch=11`
- 电力工程研究设计所：全部为 `0`
- 电气自动化所：`sql_no_profile_code=9`，`sql_code_conflict=3`，`excel_no_code_text_mismatch=0`

“冲突样本独立清单”（`document/file2_i_conflict_samples.json`）结论：

- 全量冲突样本数：`24`（建筑结构所 `21`，电气自动化所 `3`）。
- 冲突成因诊断：
  - `21` 条：库内当前收文代码与Excel目标科室不同，需业务确认（`库内已变更为其他所/其他代码`）。
  - `2` 条：SQL收文字段未出现该所可识别代码（`SQL收文部门未出现该所代码`）。
  - `1` 条：同 `R` 链路存在可命中记录，疑似桥表关联行选择差异（样本：`row=10348`，`A=18185CSPZL25E5S008`）。

关于“是否存在接口版本不一致”专项检查（已做）：

- 在上述 `24` 条冲突样本中：
  - `same_item_other_rev_has_excel_code = 0/24`
  - `same_item_same_rev_has_excel_code = 0/24`
- 结论：当前冲突样本**未发现“同接口其他版次可直接命中目标科室”的证据**；主因更偏向“当前库科室编码与模板显示口径不一致”而非版次切换。

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

