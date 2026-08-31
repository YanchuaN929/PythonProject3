#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
打包验证脚本

用途：
1. 打包前检查：验证所有必要文件是否存在
2. 打包后检查：验证打包结果是否完整

使用方法：
    python verify_package.py --pre   # 打包前检查
    python verify_package.py --post  # 打包后检查
"""

import os
import sys
import hashlib

def print_ok(msg):
    print(f"[OK] {msg}")

def print_error(msg):
    print(f"[ERROR] {msg}")

def print_warning(msg):
    print(f"[WARNING] {msg}")

def check_file(file_path, description):
    """检查文件是否存在"""
    if os.path.exists(file_path):
        print_ok(f"{description}: {file_path}")
        return True
    else:
        print_error(f"{description}不存在: {file_path}")
        return False

def _sha256(file_path):
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def check_same_file(source_path, packaged_path, description):
    """确认打包目录中的数据文件就是本次工作区版本。"""
    if not os.path.exists(source_path) or not os.path.exists(packaged_path):
        return check_file(packaged_path, description)
    if _sha256(source_path) != _sha256(packaged_path):
        print_error(f"{description}与当前源码不一致: {packaged_path}")
        return False
    print_ok(f"{description}与当前源码一致")
    return True

def check_pre_build():
    """打包前检查"""
    print("\n" + "="*50)
    print("[打包前检查]")
    print("="*50 + "\n")
    
    all_ok = True
    
    # 检查主要Python文件
    print("【核心模块】")
    all_ok &= check_file("base.py", "主程序")
    all_ok &= check_file("core/main.py", "处理模块1")
    all_ok &= check_file("core/main2.py", "处理模块2")
    all_ok &= check_file("core/Monitor.py", "监控模块")
    all_ok &= check_file("ui/window.py", "窗口管理模块")
    all_ok &= check_file("services/file_manager.py", "文件管理模块")
    print()
    
    # 检查功能模块
    print("【功能模块】")
    all_ok &= check_file("ui/ignore_overdue_dialog.py", "忽略延期对话框")
    all_ok &= check_file("utils/date_utils.py", "日期工具模块")
    all_ok &= check_file("ui/input_handler.py", "输入处理模块")
    all_ok &= check_file("services/distribution.py", "任务指派模块")
    all_ok &= check_file("services/db_status.py", "数据库状态显示器")
    all_ok &= check_file("services/account_service.py", "账户管理服务")
    all_ok &= check_file("utils/dept_config.py", "科室配置模块")
    all_ok &= check_file("utils/excel_io.py", "Excel安全读写模块")
    all_ok &= check_file("utils/role_table.py", "角色表读取模块")
    print()
    
    # 检查配置文件
    print("【配置文件】")
    all_ok &= check_file("config.json", "配置文件")
    all_ok &= check_file("version.json", "版本文件")
    print()
    
    # 检查资源文件
    print("【资源文件】")
    all_ok &= check_file("ico_bin/tubiao.ico", "程序图标")
    all_ok &= check_file("excel_bin/姓名角色表.xlsx", "角色表(建筑结构所)")
    all_ok &= check_file("excel_bin/姓名角色表-电力工程研究设计所.xlsx", "角色表(电力工程研究设计所)")
    all_ok &= check_file("excel_bin/姓名角色表——核工程所通信专业+设备专业.xlsx", "角色表(核工程研究设计所)")
    all_ok &= check_file("excel_bin/姓名角色表-核电工艺所.xlsx", "角色表(核电工艺所)")
    all_ok &= check_file("excel_bin/姓名角色表-电气自动化所.xlsx", "角色表(电气自动化所)")
    print()
    
    # 检查打包配置
    print("【打包配置】")
    all_ok &= check_file("excel_processor.spec", "打包配置文件")
    print()
    
    # 检查依赖
    print("【依赖检查】")
    try:
        import pandas
        print_ok(f"pandas: {pandas.__version__}")
    except ImportError:
        print_error("pandas 未安装")
        all_ok = False
    
    try:
        import openpyxl
        print_ok(f"openpyxl: {openpyxl.__version__}")
    except ImportError:
        print_error("openpyxl 未安装")
        all_ok = False
    
    try:
        import pystray  # noqa: F401
        print_ok("pystray: installed")
    except ImportError:
        print_error("pystray 未安装")
        all_ok = False
    
    try:
        import PIL
        print_ok(f"pillow: {PIL.__version__}")
    except ImportError:
        print_error("pillow 未安装")
        all_ok = False
    
    try:
        import PyInstaller
        print_ok(f"PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print_error("PyInstaller 未安装")
        all_ok = False
    
    print()
    
    # 总结
    print("="*50)
    if all_ok:
        print_ok("所有检查通过！可以开始打包。")
        print("\n打包命令:")
        print("  pyinstaller excel_processor.spec")
    else:
        print_error("有检查项未通过，请先解决问题。")
    print("="*50 + "\n")
    
    return all_ok

def check_post_build():
    """打包后检查"""
    print("\n" + "="*50)
    print("[打包后检查]")
    print("="*50 + "\n")
    
    dist_dir = "dist/接口筛选"
    
    if not os.path.exists(dist_dir):
        print_error(f"打包输出目录不存在: {dist_dir}")
        print_warning("请先运行: pyinstaller excel_processor.spec")
        return False
    
    all_ok = True
    
    # 检查exe
    print("【主程序】")
    all_ok &= check_file(os.path.join(dist_dir, "接口筛选.exe"), "可执行文件")
    print()
    
    # 检查Python模块
    internal = os.path.join(dist_dir, "_internal")
    print("【核心模块】")
    all_ok &= check_file(os.path.join(internal, "core", "main.py"), "处理模块1")
    all_ok &= check_file(os.path.join(internal, "core", "main2.py"), "处理模块2")
    all_ok &= check_file(os.path.join(internal, "core", "Monitor.py"), "监控模块")
    all_ok &= check_file(os.path.join(internal, "ui", "window.py"), "窗口管理模块")
    all_ok &= check_file(os.path.join(internal, "services", "file_manager.py"), "文件管理模块")
    print()
    
    # 检查功能模块
    print("【功能模块】")
    all_ok &= check_file(os.path.join(internal, "ui", "ignore_overdue_dialog.py"), "忽略延期对话框")
    all_ok &= check_file(os.path.join(internal, "utils", "date_utils.py"), "日期工具模块")
    all_ok &= check_file(os.path.join(internal, "ui", "input_handler.py"), "输入处理模块")
    all_ok &= check_file(os.path.join(internal, "services", "distribution.py"), "任务指派模块")
    all_ok &= check_file(os.path.join(internal, "services", "db_status.py"), "数据库状态显示器")
    all_ok &= check_file(os.path.join(internal, "services", "account_service.py"), "账户管理服务")
    all_ok &= check_file(os.path.join(internal, "utils", "dept_config.py"), "科室配置模块")
    all_ok &= check_file(os.path.join(internal, "utils", "excel_io.py"), "Excel安全读写模块")
    all_ok &= check_file(os.path.join(internal, "utils", "role_table.py"), "角色表读取模块")
    print()
    
    # 检查配置文件
    print("【配置文件】")
    all_ok &= check_file(os.path.join(internal, "config.json"), "配置文件")
    all_ok &= check_file(os.path.join(internal, "version.json"), "版本文件")
    print()
    
    # 检查资源文件
    print("【资源文件】")
    all_ok &= check_file(os.path.join(internal, "ico_bin", "tubiao.ico"), "程序图标")
    all_ok &= check_file(os.path.join(internal, "excel_bin", "姓名角色表.xlsx"), "角色表(建筑结构所)")
    all_ok &= check_file(os.path.join(internal, "excel_bin", "姓名角色表-电力工程研究设计所.xlsx"), "角色表(电力工程研究设计所)")
    all_ok &= check_file(os.path.join(internal, "excel_bin", "姓名角色表——核工程所通信专业+设备专业.xlsx"), "角色表(核工程研究设计所)")
    all_ok &= check_file(os.path.join(internal, "excel_bin", "姓名角色表-核电工艺所.xlsx"), "角色表(核电工艺所)")
    all_ok &= check_file(os.path.join(internal, "excel_bin", "姓名角色表-电气自动化所.xlsx"), "角色表(电气自动化所)")
    print()
    
    # 检查更新程序
    print("【更新程序】")
    all_ok &= check_file(os.path.join(dist_dir, "update.exe"), "更新程序")
    print()

    print("【构建新鲜度】")
    source_pairs = [
        ("core/main.py", os.path.join(internal, "core", "main.py"), "处理模块1"),
        ("ui/input_handler.py", os.path.join(internal, "ui", "input_handler.py"), "输入处理模块"),
        ("services/distribution.py", os.path.join(internal, "services", "distribution.py"), "任务指派模块"),
        ("services/file_manager.py", os.path.join(internal, "services", "file_manager.py"), "结果缓存模块"),
        ("services/account_service.py", os.path.join(internal, "services", "account_service.py"), "账户管理服务"),
        ("utils/excel_io.py", os.path.join(internal, "utils", "excel_io.py"), "Excel安全读写模块"),
        ("version.json", os.path.join(internal, "version.json"), "版本文件"),
        ("excel_bin/姓名角色表.xlsx", os.path.join(internal, "excel_bin", "姓名角色表.xlsx"), "建筑结构所角色表"),
    ]
    for source_path, packaged_path, description in source_pairs:
        all_ok &= check_same_file(source_path, packaged_path, description)
    executable_path = os.path.join(dist_dir, "接口筛选.exe")
    freshness_sources = ["base.py"] + [item[0] for item in source_pairs]
    if os.path.exists(executable_path):
        newest_source = max(os.path.getmtime(path) for path in freshness_sources if os.path.exists(path))
        if os.path.getmtime(executable_path) + 1 < newest_source:
            print_error("主程序时间早于本次关键源码，疑似仍为旧构建")
            all_ok = False
        else:
            print_ok("主程序时间不早于本次关键源码")
    print()
    
    # 检查依赖库
    print("【依赖库】")
    if os.path.exists(internal):
        dll_files = [f for f in os.listdir(internal) if f.endswith('.dll')]
        pyd_files = [f for f in os.listdir(internal) if f.endswith('.pyd')]
        print_ok(f"找到 {len(dll_files)} 个DLL文件")
        print_ok(f"找到 {len(pyd_files)} 个PYD文件")
    else:
        print_error("_internal目录不存在")
    print()
    
    # 总结
    print("="*50)
    if all_ok:
        print_ok("所有检查通过！")
        print("\n建议的测试步骤:")
        print("  1. 运行 dist/接口筛选/接口筛选.exe")
        print("  2. 测试文件加载功能")
        print("  3. 测试数据处理功能")
        print("  4. 测试缓存功能")
        print("  5. 测试勾选功能")
        print("  6. 测试开机自启动")
    else:
        print_error("有检查项未通过，请检查打包过程。")
    print("="*50 + "\n")
    
    return all_ok

def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python verify_package.py --pre   # 打包前检查")
        print("  python verify_package.py --post  # 打包后检查")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "--pre":
        success = check_pre_build()
    elif mode == "--post":
        success = check_post_build()
    else:
        print(f"未知参数: {mode}")
        print("使用 --pre 或 --post")
        sys.exit(1)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

