
========== [Registry] 开始查询待审查任务 ==========
[Registry] 总行数: 5455, 原始筛选结果: 0行
[Registry] 已启用强制网络模式（本地测试用）
[Registry] ❌ 查询待审查任务失败（不影响主流程）: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 399, in process_target_file
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
========== [Registry] 查询完成 ==========

[INFO] 处理1符合条件: 45 行
[INFO] 处理2符合条件: 399 行
[INFO] 处理3符合条件: 173 行
[INFO] 处理4需排除: 210 行
[WARNING] 经过四步筛选后，无符合条件的数据
[调试] 文件1处理返回: result=<class 'pandas.core.frame.DataFrame'>, 行数=0
项目1916文件1处理结果为空
[WARNING] 项目1916文件1处理结果为空
处理项目2016的文件1: 2016按项目导出IDI手册2025-11-26-09_21_05.xlsx
[PROCESS] 处理项目2016的待处理文件1: 2016按项目导出IDI手册2025-11-26-09_21_05.xlsx
✅ 缓存已加载: 6a96934e_2016_file1.pkl (58行)
  ✅ 使用缓存: 项目2016file1 (58行)
[调试] 文件1处理返回: result=<class 'pandas.core.frame.DataFrame'>, 行数=58
[调试] 已保存原始结果到raw_results_for_registry: 项目2016, 58行
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2016
✅ 单角色筛选完成: 输入58行，输出15行，角色来源列=已添加
项目2016文件1处理完成: 原始58行，角色筛选后15行
[SUCCESS] 项目2016文件1处理完成: 原始58行，显示15行
处理项目2026的文件1: 2026按项目导出IDI手册2025-11-26-09_23_02.xlsx
[PROCESS] 处理项目2026的待处理文件1: 2026按项目导出IDI手册2025-11-26-09_23_02.xlsx
✅ 缓存已加载: 7de09c85_2026_file1.pkl (9行)
  ✅ 使用缓存: 项目2026file1 (9行)
[调试] 文件1处理返回: result=<class 'pandas.core.frame.DataFrame'>, 行数=9
[调试] 已保存原始结果到raw_results_for_registry: 项目2026, 9行
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2026
✅ 单角色筛选完成: 输入9行，输出9行，角色来源列=已添加
项目2026文件1处理完成: 原始9行，角色筛选后9行
[SUCCESS] 项目2026文件1处理完成: 原始9行，显示9行
处理项目2306的文件1: 2306按项目导出IDI手册2025-11-26-09_23_57.xlsx
[PROCESS] 处理项目2306的待处理文件1: 2306按项目导出IDI手册2025-11-26-09_23_57.xlsx
开始处理待处理文件1: 2306按项目导出IDI手册2025-11-26-09_23_57.xlsx
[PROCESS] 开始处理待处理文件1: 2306按项目导出IDI手册2025-11-26-09_23_57.xlsx
读取到数据：2159 行，22 列
[INFO] 读取到数据：2159 行，22 列
数据概览（前3行）：
第1行（表头）: ['S-WCD-BA-1HB-01-25E5-25D1', '编制', 'S', 'WCD', 'BA']...
第2行（数据）: ['S-WND-BA-1HB-01-25E5-25D1', '编制', 'S', 'WND', 'BA']...
第3行（数据）: ['S-WQB-PO-1GH-02-25A1-25A6', '编制', 'S', 'WQB', 'PO']...
[PROCESS] 开始执行处理1：筛选H列数据（25C1、25C2、25C3）
处理1完成：共找到 33 行符合H列筛选条件
[SUCCESS] 处理1完成：共找到 33 行符合H列筛选条件
[PROCESS] 开始执行处理2：筛选K列日期数据
当前日期：2025-12-01，今天是1号
当日为1号，筛选范围：2025-01-01 至 2025-12-31
处理2完成：共找到 500 行符合K列日期筛选条件
[SUCCESS] 处理2完成：共找到 500 行符合K列日期筛选条件
[PROCESS] 开始执行处理3：筛选M列空值且A列非空数据
处理3完成（原始筛选）：共找到 928 行符合M列空值且A列非空条件
[SUCCESS] 处理3完成：共找到 928 行符合M列空值且A列非空条件
[PROCESS] 开始执行处理4：筛选B列作废数据
处理4完成：共找到 72 行B列包含作废标记（需要排除）
[WARNING] 处理4完成：共找到 72 行B列包含作废标记（需要排除）
筛选统计 - P1:33行 P2:500行 P3:928行 P4(排除):72行 → 结果:0行

========== [Registry] 开始查询待审查任务 ==========
[Registry] 总行数: 2159, 原始筛选结果: 0行
[Registry] 已启用强制网络模式（本地测试用）
[Registry] ❌ 查询待审查任务失败（不影响主流程）: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 399, in process_target_file
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
========== [Registry] 查询完成 ==========

[INFO] 处理1符合条件: 33 行
[INFO] 处理2符合条件: 500 行
[INFO] 处理3符合条件: 928 行
[INFO] 处理4需排除: 72 行
[WARNING] 经过四步筛选后，无符合条件的数据
[调试] 文件1处理返回: result=<class 'pandas.core.frame.DataFrame'>, 行数=0
项目2306文件1处理结果为空
[WARNING] 项目2306文件1处理结果为空
[调试] 准备写入Registry: registry_hooks=True, raw_results_for_registry有5个项目
[调试] 处理项目1818: raw_df=True, 行数=12
[Registry] 正在调用on_process_done: file_type=1, project_id=1818, rows=12
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件1项目1818: 写入12个任务
[INFO] Registry: 文件1项目1818写入12个任务
[调试] 处理项目1907: raw_df=True, 行数=44
[Registry] 正在调用on_process_done: file_type=1, project_id=1907, rows=44
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件1项目1907: 写入44个任务
[INFO] Registry: 文件1项目1907写入44个任务
[调试] 处理项目1915: raw_df=True, 行数=1
[Registry] 正在调用on_process_done: file_type=1, project_id=1915, rows=1
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件1项目1915: 写入1个任务
[INFO] Registry: 文件1项目1915写入1个任务
[调试] 处理项目2016: raw_df=True, 行数=58
[Registry] 正在调用on_process_done: file_type=1, project_id=2016, rows=58
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件1项目2016: 写入58个任务
[INFO] Registry: 文件1项目2016写入58个任务
[调试] 处理项目2026: raw_df=True, 行数=9
[Registry] 正在调用on_process_done: file_type=1, project_id=2026, rows=9
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件1项目2026: 写入9个任务
[INFO] Registry: 文件1项目2026写入9个任务
文件1批量处理完成，显示: 43 行
[SUCCESS] 待处理文件1批量处理完成: 显示43行数据
开始批量处理文件2类型，共 7 个文件
[PROCESS] 开始批量处理待处理文件2: 7个文件，涉及7个项目(1818, 1907, 1915, 1916, 2016, 2026, 2306)
处理项目1818的文件2: 内部接口信息单报表181820251126.xlsx
✅ 缓存已加载: ba810a53_1818_file2.pkl (14行)
  ✅ 使用缓存: 项目1818file2 (14行)
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1818
✅ 单角色筛选完成: 输入14行，输出6行，角色来源列=已添加
项目1818文件2处理完成: 原始14行，显示6行
处理项目1907的文件2: 内部接口信息单报表190720251126.xlsx
✅ 缓存已加载: 3d1f033f_1907_file2.pkl (111行)
  ✅ 使用缓存: 项目1907file2 (111行)
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1907
✅ 单角色筛选完成: 输入111行，输出103行，角色来源列=已添加
项目1907文件2处理完成: 原始111行，显示103行
处理项目1915的文件2: 内部接口信息单报表191520251126.xlsx
✅ 缓存已加载: df4b0b88_1915_file2.pkl (2行)
  ✅ 使用缓存: 项目1915file2 (2行)
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1915
✅ 单角色筛选完成: 输入2行，输出1行，角色来源列=已添加
项目1915文件2处理完成: 原始2行，显示1行
处理项目1916的文件2: 内部接口信息单报表191620251126.xlsx
开始处理待处理文件2: 内部接口信息单报表191620251126.xlsx
[PROCESS] 开始处理待处理文件2: 内部接口信息单报表191620251126.xlsx
项目1916使用扩展逻辑（排除process3：1942行）
最终完成处理数据（原始筛选）: 0 行

========== [Registry] 开始查询待审查任务（文件类型2） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待确认任务失败（不影响主流程）: database disk image is malformed
最终完成处理数据（含待确认）: 0 行
[INFO] 处理1符合条件: 880 行
[INFO] 处理2符合条件: 2597 行
[INFO] 处理3(排除项)符合条件: 1942 行
[INFO] 处理4符合条件: 8486 行
[WARNING] 经过筛选后，无符合条件的数据
项目1916文件2处理结果为空
处理项目2016的文件2: 内部接口信息单报表201620251126.xlsx
✅ 缓存已加载: 88924c27_2016_file2.pkl (218行)
  ✅ 使用缓存: 项目2016file2 (218行)
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2016
✅ 单角色筛选完成: 输入218行，输出191行，角色来源列=已添加
项目2016文件2处理完成: 原始218行，显示191行
处理项目2026的文件2: 内部接口信息单报表202620251126.xlsx
开始处理待处理文件2: 内部接口信息单报表202620251126.xlsx
[PROCESS] 开始处理待处理文件2: 内部接口信息单报表202620251126.xlsx
项目2026使用扩展逻辑（排除process3：2374行）
最终完成处理数据（原始筛选）: 0 行

========== [Registry] 开始查询待审查任务（文件类型2） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待确认任务失败（不影响主流程）: database disk image is malformed
最终完成处理数据（含待确认）: 0 行
[INFO] 处理1符合条件: 672 行
[INFO] 处理2符合条件: 3830 行
[INFO] 处理3(排除项)符合条件: 2374 行
[INFO] 处理4符合条件: 6146 行
[WARNING] 经过筛选后，无符合条件的数据
项目2026文件2处理结果为空
处理项目2306的文件2: 内部接口信息单报表230620251126.xlsx
开始处理待处理文件2: 内部接口信息单报表230620251126.xlsx
[PROCESS] 开始处理待处理文件2: 内部接口信息单报表230620251126.xlsx
项目2306使用扩展逻辑（排除process3：52行）
最终完成处理数据（原始筛选）: 1 行

========== [Registry] 开始查询待审查任务（文件类型2） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待确认任务失败（不影响主流程）: database disk image is malformed
最终完成处理数据（含待确认）: 1 行
[INFO] 处理1符合条件: 124 行
[INFO] 处理2符合条件: 741 行
[INFO] 处理3(排除项)符合条件: 52 行
[INFO] 处理4符合条件: 1475 行
[SUCCESS] 最终完成处理数据: 1 行
✅ 缓存已保存: 6abd46a6_2306_file2.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2306
✅ 单角色筛选完成: 输入1行，输出1行，角色来源列=已添加
项目2306文件2处理完成: 原始1行，显示1行
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件2项目1818: 写入14个任务
[INFO] Registry: 文件2项目1818写入14个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件2项目1907: 写入111个任务
[INFO] Registry: 文件2项目1907写入111个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件2项目1915: 写入2个任务
[INFO] Registry: 文件2项目1915写入2个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件2项目2016: 写入218个任务
[INFO] Registry: 文件2项目2016写入218个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件2项目2306: 写入1个任务
[INFO] Registry: 文件2项目2306写入1个任务
文件2批量处理完成，显示: 302 行
开始批量处理文件3类型，共 7 个文件
处理项目1818的文件3: 外部接口ICM报表181820251126.xlsx
开始处理待处理文件3: 外部接口ICM报表181820251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表181820251126.xlsx
读取到数据：4578 行，65 列
[INFO] 读取到数据：4578 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 927 行符合条件
[INFO] 处理1完成：找到 927 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 34 行符合条件
[INFO] 处理2完成：找到 34 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 2786 行符合条件
[INFO] 处理3完成：找到 2786 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 3742 行符合条件
[INFO] 处理4完成：找到 3742 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 3921 行符合条件
[INFO] 处理5完成：找到 3921 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 1071 行符合条件
[INFO] 处理6完成：找到 1071 行符合条件
最终完成处理数据（原始筛选）: 9 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 9 行
[INFO] 处理1(I列为B): 927 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 34 行
[INFO] 处理3(M列时间筛选): 2786 行
[INFO] 处理4(L列时间筛选): 3742 行
[INFO] 处理5(Q列为空): 3921 行
[INFO] 处理6(T列为空): 1071 行
[INFO] 组1(1&2&3-6): 3 行
[INFO] 组2(1&2&4-5): 9 行
[SUCCESS] 最终完成处理数据: 9 行
✅ 缓存已保存: c87c1249_1818_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1818
✅ 单角色筛选完成: 输入9行，输出9行，角色来源列=已添加
项目1818文件3处理完成: 原始9行，显示9行
处理项目1907的文件3: 外部接口ICM报表190720251126.xlsx
开始处理待处理文件3: 外部接口ICM报表190720251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表190720251126.xlsx
读取到数据：2695 行，65 列
[INFO] 读取到数据：2695 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 348 行符合条件
[INFO] 处理1完成：找到 348 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 38 行符合条件
[INFO] 处理2完成：找到 38 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 920 行符合条件
[INFO] 处理3完成：找到 920 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 2227 行符合条件
[INFO] 处理4完成：找到 2227 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 2252 行符合条件
[INFO] 处理5完成：找到 2252 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 912 行符合条件
[INFO] 处理6完成：找到 912 行符合条件
最终完成处理数据（原始筛选）: 4 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 4 行
[INFO] 处理1(I列为B): 348 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 38 行
[INFO] 处理3(M列时间筛选): 920 行
[INFO] 处理4(L列时间筛选): 2227 行
[INFO] 处理5(Q列为空): 2252 行
[INFO] 处理6(T列为空): 912 行
[INFO] 组1(1&2&3-6): 0 行
[INFO] 组2(1&2&4-5): 4 行
[SUCCESS] 最终完成处理数据: 4 行
✅ 缓存已保存: 6ec6340f_1907_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1907
✅ 单角色筛选完成: 输入4行，输出4行，角色来源列=已添加
项目1907文件3处理完成: 原始4行，显示4行
处理项目1915的文件3: 外部接口ICM报表191520251126.xlsx
开始处理待处理文件3: 外部接口ICM报表191520251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表191520251126.xlsx
读取到数据：675 行，65 列
[INFO] 读取到数据：675 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 121 行符合条件
[INFO] 处理1完成：找到 121 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 3 行符合条件
[INFO] 处理2完成：找到 3 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 183 行符合条件
[INFO] 处理3完成：找到 183 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 634 行符合条件
[INFO] 处理4完成：找到 634 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 636 行符合条件
[INFO] 处理5完成：找到 636 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 571 行符合条件
[INFO] 处理6完成：找到 571 行符合条件
最终完成处理数据（原始筛选）: 3 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 3 行
[INFO] 处理1(I列为B): 121 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 3 行
[INFO] 处理3(M列时间筛选): 183 行
[INFO] 处理4(L列时间筛选): 634 行
[INFO] 处理5(Q列为空): 636 行
[INFO] 处理6(T列为空): 571 行
[INFO] 组1(1&2&3-6): 0 行
[INFO] 组2(1&2&4-5): 3 行
[SUCCESS] 最终完成处理数据: 3 行
✅ 缓存已保存: b596da92_1915_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1915
✅ 单角色筛选完成: 输入3行，输出0行，角色来源列=未添加
项目1915文件3处理完成: 原始3行，显示0行
处理项目1916的文件3: 外部接口ICM报表191620251126.xlsx
开始处理待处理文件3: 外部接口ICM报表191620251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表191620251126.xlsx
读取到数据：3907 行，65 列
[INFO] 读取到数据：3907 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 862 行符合条件
[INFO] 处理1完成：找到 862 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 19 行符合条件
[INFO] 处理2完成：找到 19 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 666 行符合条件
[INFO] 处理3完成：找到 666 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 2614 行符合条件
[INFO] 处理4完成：找到 2614 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 3215 行符合条件
[INFO] 处理5完成：找到 3215 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 706 行符合条件
[INFO] 处理6完成：找到 706 行符合条件
最终完成处理数据（原始筛选）: 5 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 5 行
[INFO] 处理1(I列为B): 862 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 19 行
[INFO] 处理3(M列时间筛选): 666 行
[INFO] 处理4(L列时间筛选): 2614 行
[INFO] 处理5(Q列为空): 3215 行
[INFO] 处理6(T列为空): 706 行
[INFO] 组1(1&2&3-6): 0 行
[INFO] 组2(1&2&4-5): 5 行
[SUCCESS] 最终完成处理数据: 5 行
✅ 缓存已保存: 1a139a9e_1916_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=1916
✅ 单角色筛选完成: 输入5行，输出4行，角色来源列=已添加
项目1916文件3处理完成: 原始5行，显示4行
处理项目2016的文件3: 外部接口ICM报表201620251126.xlsx
开始处理待处理文件3: 外部接口ICM报表201620251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表201620251126.xlsx
读取到数据：4492 行，65 列
[INFO] 读取到数据：4492 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 920 行符合条件
[INFO] 处理1完成：找到 920 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 48 行符合条件
[INFO] 处理2完成：找到 48 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 1670 行符合条件
[INFO] 处理3完成：找到 1670 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 3712 行符合条件
[INFO] 处理4完成：找到 3712 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 4012 行符合条件
[INFO] 处理5完成：找到 4012 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 1777 行符合条件
[INFO] 处理6完成：找到 1777 行符合条件
最终完成处理数据（原始筛选）: 11 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 11 行
[INFO] 处理1(I列为B): 920 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 48 行
[INFO] 处理3(M列时间筛选): 1670 行
[INFO] 处理4(L列时间筛选): 3712 行
[INFO] 处理5(Q列为空): 4012 行
[INFO] 处理6(T列为空): 1777 行
[INFO] 组1(1&2&3-6): 2 行
[INFO] 组2(1&2&4-5): 11 行
[SUCCESS] 最终完成处理数据: 11 行
✅ 缓存已保存: 3b3b075d_2016_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2016
✅ 单角色筛选完成: 输入11行，输出9行，角色来源列=已添加
项目2016文件3处理完成: 原始11行，显示9行
处理项目2026的文件3: 外部接口ICM报表202620251126.xlsx
开始处理待处理文件3: 外部接口ICM报表202620251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表202620251126.xlsx
读取到数据：4968 行，65 列
[INFO] 读取到数据：4968 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 1107 行符合条件
[INFO] 处理1完成：找到 1107 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 65 行符合条件
[INFO] 处理2完成：找到 65 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 1405 行符合条件
[INFO] 处理3完成：找到 1405 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 3439 行符合条件
[INFO] 处理4完成：找到 3439 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 4476 行符合条件
[INFO] 处理5完成：找到 4476 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 2487 行符合条件
[INFO] 处理6完成：找到 2487 行符合条件
最终完成处理数据（原始筛选）: 10 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 10 行
[INFO] 处理1(I列为B): 1107 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 65 行
[INFO] 处理3(M列时间筛选): 1405 行
[INFO] 处理4(L列时间筛选): 3439 行
[INFO] 处理5(Q列为空): 4476 行
[INFO] 处理6(T列为空): 2487 行
[INFO] 组1(1&2&3-6): 0 行
[INFO] 组2(1&2&4-5): 10 行
[SUCCESS] 最终完成处理数据: 10 行
✅ 缓存已保存: 35536d08_2026_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2026
✅ 单角色筛选完成: 输入10行，输出2行，角色来源列=已添加
项目2026文件3处理完成: 原始10行，显示2行
处理项目2306的文件3: 外部接口ICM报表230620251126.xlsx
开始处理待处理文件3: 外部接口ICM报表230620251126.xlsx
[PROCESS] 开始处理待处理文件3: 外部接口ICM报表230620251126.xlsx
读取到数据：541 行，65 列
[INFO] 读取到数据：541 行，65 列
执行处理1：筛选I列为'B'的数据
[PROCESS] 处理1：筛选I列为'B'的数据
处理1完成：找到 199 行符合条件
[INFO] 处理1完成：找到 199 行符合条件
执行处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
[PROCESS] 处理2：筛选AL列以'河北分公司-建筑结构所'开头的数据
处理2完成：找到 7 行符合条件
[INFO] 处理2完成：找到 7 行符合条件
执行处理3：筛选M列时间数据
[PROCESS] 处理3：筛选M列时间数据
筛选日期范围: 2025-01-01 到 2025-12-31
处理3完成：找到 259 行符合条件
[INFO] 处理3完成：找到 259 行符合条件
执行处理4：筛选L列时间数据（包括4444开头特殊处理）
[PROCESS] 处理4：筛选L列时间数据（包括4444开头特殊处理）
筛选日期范围: 2025-01-01 到 2025-12-31
处理4完成：找到 318 行符合条件
[INFO] 处理4完成：找到 318 行符合条件
执行处理5：筛选Q列为空值的数据
[PROCESS] 处理5：筛选Q列为空值的数据
处理5完成：找到 345 行符合条件
[INFO] 处理5完成：找到 345 行符合条件
执行处理6：筛选T列为空值的数据
[PROCESS] 处理6：筛选T列为空值的数据
处理6完成：找到 422 行符合条件
[INFO] 处理6完成：找到 422 行符合条件
最终完成处理数据（原始筛选）: 3 行

========== [Registry] 开始查询待审查任务（文件类型3） ==========
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 查询待审查任务失败: database disk image is malformed
Traceback (most recent call last):
  File "main.py", line 1615, in process_target_file3
    cursor = conn.execute("""
sqlite3.DatabaseError: database disk image is malformed
最终完成处理数据（含待审查）: 3 行
[INFO] 处理1(I列为B): 199 行
[INFO] 处理2(AL列河北分公司-建筑结构所开头): 7 行
[INFO] 处理3(M列时间筛选): 259 行
[INFO] 处理4(L列时间筛选): 318 行
[INFO] 处理5(Q列为空): 345 行
[INFO] 处理6(T列为空): 422 行
[INFO] 组1(1&2&3-6): 1 行
[INFO] 组2(1&2&4-5): 2 行
[SUCCESS] 最终完成处理数据: 3 行
✅ 缓存已保存: bf324433_2306_file3.pkl
🔍 角色筛选: user_name=闫伟, user_roles=['所领导'], project_id=2306
✅ 单角色筛选完成: 输入3行，输出2行，角色来源列=已添加
项目2306文件3处理完成: 原始3行，显示2行
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目1818: 写入9个任务
[INFO] Registry: 文件3项目1818写入9个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目1907: 写入4个任务
[INFO] Registry: 文件3项目1907写入4个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目1915: 写入3个任务
[INFO] Registry: 文件3项目1915写入3个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目1916: 写入5个任务
[INFO] Registry: 文件3项目1916写入5个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目2016: 写入11个任务
[INFO] Registry: 文件3项目2016写入11个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目2026: 写入10个任务
[INFO] Registry: 文件3项目2026写入10个任务
[Registry] 已启用强制网络模式（本地测试用）
[Registry] 批量upsert失败: database disk image is malformed
[Registry] on_process_done 失败: database disk image is malformed
Traceback (most recent call last):
  File "registry\hooks.py", line 154, in on_process_done
  File "registry\hooks.py", line 33, in _retry_on_lock
  File "registry\hooks.py", line 152, in do_batch_upsert
  File "registry\service.py", line 1026, in batch_upsert_tasks
  File "registry\service.py", line 33, in find_task_by_business_id
sqlite3.DatabaseError: database disk image is malformed
[Registry] ✓ 文件3项目2306: 写入3个任务
[INFO] Registry: 文件3项目2306写入3个任务
文件3批量处理完成，显示: 30 行
开始批量处理文件4类型，共 7 个文件
处理项目1818的文件4: 外部接口单报表181820251126.xlsx
开始处理待处理文件4: 外部接口单报表181820251126.xlsx
[PROCESS] 开始处理待处理文件4: 外部接口单报表181820251126.xlsx
