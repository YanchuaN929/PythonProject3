# 接口筛选程序

接口筛选程序是一套面向工程项目接口协同的 Windows 桌面工具。程序从项目 Excel 中识别七类待办，结合姓名角色表和 Registry 状态，为设计人员、接口工程师、室主任、所领导及管理员提供筛选、指派、回复、FU 完成、确认、历史查询和结果导出能力。

程序以业务 Excel 的实际内容为首要事实来源，同时使用 Registry 保存跨文件、跨轮次的任务状态。回复、FU 完成和指派通过写入任务队列执行，避免界面线程直接访问公共盘。

## 当前状态

- 当前版本以 [`version.json`](version.json) 为准。
- 运行平台：Windows 7、Windows 10、Windows 11。
- 开发与打包基线：Python 3.8.5。
- 依赖版本固定在 [`requirements.txt`](requirements.txt) 和 [`requirements-dev.txt`](requirements-dev.txt)。
- 应用入口：[`base.py`](base.py)。
- PyInstaller 配置：[`excel_processor.spec`](excel_processor.spec)。

## 核心功能

- 自动发现并合并多个项目的七类接口文件。
- 根据当前账户、角色、项目和科室配置筛选可见任务。
- 支持任务指派、重新指派及指派记忆。
- 支持文件 1～6 的单项和批量回文单号填写。
- 支持设计人员直接或批量标记 FU 完成。
- 支持上级角色确认完成、忽略延期项和历史查询。
- Excel 写入成功但 Registry 同步失败时，进入仅同步 Registry 的补偿队列，不重复写 Excel。
- 支持公共盘文件锁、原子写入、写后重新读取校验和本地待处理记录。
- 支持结果缓存、选项卡预加载、后台刷新、自动导出和自动更新。

## 七类业务文件

| 类型 | 界面名称 | 主要文件名特征 |
|---|---|---|
| 1 | 内部需打开接口 | `项目号+按项目导出IDI手册+时间` |
| 2 | 内部需回复接口 | `内部接口信息单报表+项目号+日期` |
| 3 | 外部需打开接口 | `外部接口ICM报表+项目号+日期` |
| 4 | 外部需回复接口 | `外部接口单报表+项目号+日期` |
| 5 | 三维提资接口 | 文件名包含 `接口提资清单` |
| 6 | 收发文函 | 文件名包含 `收发文清单` |
| 7 | FU | `项目号+项目标准表格` |

支持 `.xlsx`、`.xlsm` 和兼容的 `.xls` 文件。具体列位、表头兼容和筛选条件以 [`core/main.py`](core/main.py) 中的识别函数及 `STREAM_FILE_SPECS` 为准，不应只根据文档中的历史示例推断。

## 用户快速开始

### 使用发布包

1. 解压完整发布包，不要只复制主程序 EXE。
2. 运行 `接口筛选.exe`。
3. 在设置中选择所属科室和业务文件夹。
4. 切换到本人账户并完成密码验证。
5. 勾选需要处理的文件类型，点击“开始处理”。
6. 在对应选项卡中完成指派、回复、FU 完成或确认。
7. 在“写入任务记录”中确认 Excel 写入及 Registry 同步结果。

更完整的角色操作说明见[使用说明](document/4_使用说明.md)。

### 使用时的安全提示

- Excel 被他人打开时，不要强制覆盖或绕过文件锁。
- “写入失败”与“Registry 同步失败”含义不同，应先查看写入任务记录。
- Excel 已写入而 Registry 未同步时，应重试 Registry 补偿任务，不要重复提交 Excel 写入。
- 修改姓名角色表前应确认当前科室配置；密码位于角色表的受保护业务列，不应出现在截图、日志或问题报告中。
- 不要手工删除公共 Registry 数据库来解决显示问题。

## 开发环境

### 1. 创建虚拟环境

在项目根目录使用 Python 3.8：

```powershell
py -3.8 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

不要未经兼容性验证升级 pandas、NumPy、openpyxl、Pillow 或 PyInstaller。该项目需要继续兼容 Python 3.8 和 Windows 7。

### 2. 启动程序

```powershell
.venv\Scripts\python.exe base.py
```

自动模式：

```powershell
.venv\Scripts\python.exe base.py --auto
```

### 3. 运行测试

完整回归：

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_all -q
```

与 Excel 写入、Registry、回复、确认或指派有关的修改不能只做启动测试，必须运行对应测试后再运行完整回归。详细测试矩阵见 [`AGENTS.md`](AGENTS.md)。

## 架构概览

```text
业务 Excel / 姓名角色表
          │
          ▼
  core/main.py ── 识别、精简读取、业务筛选
          │
          ├──► base.py / ui/window.py ── 角色过滤、界面和导出
          │
          └──► registry/ ── 状态继承、确认、归档、历史

界面操作
   │
   ▼
write_tasks/ ── 后台任务、共享日志、失败重试
   │
   ├──► ui/input_handler.py / services/batch_response.py ── Excel 原子写入
   └──► registry/hooks.py ── 状态同步或 Registry-only 补偿
```

### 主要目录

| 路径 | 职责 |
|---|---|
| `base.py` | 应用控制器、刷新与处理编排、缓存复用、角色和界面协调 |
| `core/` | 文件识别、Excel 精简读取、七类业务筛选、汇总导出 |
| `ui/` | 主窗口、选项卡、帮助、回复输入、批量操作和延期处理 |
| `services/` | 指派、账户、批量写入、缓存和数据库状态服务 |
| `registry/` | SQLite Registry、任务状态机、事件、恢复、迁移和历史查询 |
| `write_tasks/` | Excel 写入任务队列、执行器、共享记录和 Registry 补偿 |
| `utils/` | Excel 安全读写、日期、科室配置、角色表和项目调整 |
| `update/` | 版本比较、更新检查和独立更新程序 |
| `debug_tools/` | 任务可见性分析工具 |
| `scripts/` | 诊断、迁移、SQL 探索和兼容包工具 |
| `tests/` | 业务、并发、写入安全、Registry、GUI 和性能回归测试 |
| `document/` | 架构、模块、使用、技术专题和 CIMS 研究资料 |

## 配置与数据

[`config.json`](config.json) 保存默认配置和多个科室参数族。主要配置包括：

- 业务文件夹与导出目录。
- 当前用户和界面偏好。
- 自动启动、托盘和逾期隐藏设置。
- 当前 `department_profile` 及 `department_profiles`。
- Registry 网络模式和写入模式。

运行时的用户配置、结果缓存、任务队列状态和 Registry 数据不应作为源代码提交。仓库中的配置是默认模板；部署后的本机配置和公共盘数据可能不同。

姓名、角色和账户密码由 `excel_bin/姓名角色表*.xlsx` 管理。不同科室使用不同角色表，读取规则集中在 [`utils/role_table.py`](utils/role_table.py) 和 [`services/account_service.py`](services/account_service.py)。

## 构建与发布

### 打包前检查

```powershell
.venv\Scripts\python.exe verify_package.py --pre
```

### 构建

推荐使用：

```powershell
build.bat
```

也可以直接执行：

```powershell
.venv\Scripts\pyinstaller.exe excel_processor.spec --noconfirm --clean
```

### 打包后检查

```powershell
.venv\Scripts\python.exe verify_package.py --post
```

发布前必须：

1. 更新 `version.json`；格式固定为 `YYYY.MM.DD.N`，日期必须是实际发布日期，日期变化时 `N` 从1开始，同日再次发布才递增 `N`。
2. 运行相关测试和完整回归。
3. 完成打包前、打包后检查。
4. 验证 EXE 能正常启动。
5. 验证压缩包可以完整解压。
6. 发布包按 `接口筛选_<version>.rar` 命名；打包前后校验会拒绝旧日期或格式错误的版本号。

`build/`、`dist/`、运行日志、数据库和缓存均为生成物，不提交 Git。

## 文档导航

- [程序框架](document/1_程序框架.md)
- [模块功能说明](document/2_模块功能说明.md)
- [Registry、更新、写入队列与性能专题](document/3_技术专题.md)
- [完整使用说明](document/4_使用说明.md)
- [CIMS 数据库直连升级需求与规划](document/5_工作流程.md)
- [阶段 1 CIMS SQL 分析结果](document/6_阶段1_CIMS-sql分析结果.md)
- [待处理文件与 SQL 对照表](document/7_待处理文件SQL对照表.md)
- [诊断脚本说明](scripts/README.md)
- [SQL 探索模板说明](example/README.md)

文档可能包含阶段性设计或历史统计。发生冲突时，当前代码、测试、`version.json` 和配置文件优先；发现文档陈旧时，应在同一变更中进行最小同步。

## 问题排查

提交问题时请提供：

- `version.json` 中的版本号。
- 当前科室、角色和项目号。
- 文件类型及脱敏后的文件名。
- 操作步骤、预期结果和实际结果。
- 写入任务记录中的状态与错误信息。
- Excel 是否已经产生实际写入。
- 必要的脱敏截图。

不要上传未脱敏的生产 Excel、姓名角色表、Registry 数据库、密码、公共盘凭据或包含个人信息的日志。

## 后续开发约定

自动化开发工具和维护人员在修改项目前应先阅读 [`AGENTS.md`](AGENTS.md)。涉及 Excel 写入、Registry、回复、FU、确认、指派、角色权限或公共盘并发的改动属于高风险变更，必须保留原业务闭环并增加回归测试。
