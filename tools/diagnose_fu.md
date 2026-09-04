# FU 实机诊断探针

只需将 `diagnose_fu.ps1` 放在 `接口筛选.exe` 同级目录，不需要 Python、Excel 或管理员权限。适用于 Windows PowerShell 2.0 及以上；已执行的系统版本测试范围以测试报告为准。

1. 先在实机程序中点击“开始处理”，复现 FU 空白，保留该界面。
2. 在 EXE 目录打开 PowerShell，执行：

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnose_fu.ps1
   ```

   `Bypass` 仅作用于这次子进程，不改变系统执行策略。如单位策略禁止脚本，请联系管理员，不要修改组策略或安全软件。

3. 等待完成，将生成的 `FU_Diagnostic_时间_随机号` 文件夹中的 `report.json` 发回。有 `TIMEOUT.txt` 或 `fatal.txt` 时也一并提供。目录不可写时，报告会生成在当前用户临时目录；控制台会显示位置。
4. 建议在本机正常版本旁也运行一次，提供两份报告作对照。如果程序已打开“监控”窗口，请通过“保存日志”另存复现时的日志，一并提供。

若探针推断的数据目录与 GUI 显示不一致，可明确指定：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnose_fu.ps1 -DataFolder "实际业务文件夹路径"
```

## 收集范围与边界

- 系统、PowerShell/CLR 版本、时区、区域设置、EXE 与关键依赖校验值及实际运行路径。
- 相关配置白名单、当前账号在选定角色表中的 A/B 列匹配情况；不解码或导出密码列。
- FU 文件识别、首工作表真实 XML 路径、声明范围与物理单元格范围、A:F 列类型及数量、公式缺少缓存值、特殊 Unicode 字符位置。不输出业务单元格正文。
- 已有崩溃、退出及 Registry 诊断日志的有限尾部；疑似凭据行被删除。报告仍含姓名和内部路径，外发前请审阅。
- Registry 文件及旁文件元数据。仅把受大小限制的副本放入私有临时目录，再使用程序自带 SQLite DLL 只读查询状态汇总；不直接连接源数据库，不收集任务正文，副本在结束或超时后清理。
- 缓存只统计文件名、大小和时间，不反序列化 pickle，不读取写入任务载荷。

探针不会写入或修复 Excel、Registry、角色表、配置，不启动业务 EXE，也不读取正在运行的 Python/Tk 内存。源码中已被吞掉的 GUI 异常无法事后恢复；`crash.log` 为空不代表没有绘制异常。

`rows_with_plan_and_blank_actual` 是结构计数，不是最终 GUI 应显示数；它未套用日期窗口、角色、归档和待审查规则。Registry 副本不是事务级备份；检测到复制期间变化或回滚日志时，停止汇总并明确提示。`.xls`、ZIP64 或超过大小/时间限制的内容会明确标记未检查，不据此判定业务程序有错。

默认总时限 180 秒，每个 FU 文件最多检查 45 秒，最多检查 30 个 FU 文件，Registry 单文件上限 128 MiB。需要时可用 `-TimeoutSeconds 300`、`-MaxFuFiles 50` 或 `-SkipRegistry`。探针不提交 Git、不更新版本、不重新打包应用。
