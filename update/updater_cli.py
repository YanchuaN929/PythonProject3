# -*- coding: utf-8 -*-
"""
update.exe 的入口脚本：
1. 等待主程序退出
2. 从共享目录复制最新版本到本地
3. 重新启动主程序
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from typing import Iterable, Optional


# 日志文件路径（与 update.exe 同目录）
LOG_FILE: Optional[str] = None

# 等待主程序退出的默认超时（秒）
# 说明：主程序若未能及时退出，更新器仍会继续尝试更新（会打印 WARNING）。
DEFAULT_MAIN_EXIT_TIMEOUT_SECONDS = 30


def init_log_file(local_dir: str) -> None:
    """初始化日志文件"""
    global LOG_FILE
    try:
        LOG_FILE = os.path.join(local_dir, "update_log.txt")
    except Exception:
        LOG_FILE = None


def log(message: str, level: str = "INFO") -> None:
    """输出日志到控制台和文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{level}] {message}"
    print(formatted)
    
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass


def parse_args(argv: Optional[Iterable[str]] = None):
    parser = argparse.ArgumentParser(description="接口筛选程序自动更新器")
    parser.add_argument("--remote", default="", help="最新版本所在的 EXE 目录")
    parser.add_argument("--local", default="", help="当前程序所在目录")
    parser.add_argument("--version", default="", help="目标版本号")
    parser.add_argument("--resume", default="", help="重启后需要恢复的动作")
    parser.add_argument("--main-exe", default="", help="主程序可执行文件名")
    parser.add_argument("--main-pid", type=int, default=0, help="主程序进程ID（优先用于等待退出）")
    parser.add_argument("--auto-mode", action="store_true", help="重启时附加 --auto")
    return parser.parse_args(list(argv) if argv is not None else None)


def _read_json_file(file_path: str) -> dict:
    try:
        if not file_path or not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_version_from_candidates(*candidates: str) -> str:
    for file_path in candidates:
        try:
            if not file_path or not os.path.exists(file_path):
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                value = str(data.get("version", "")).strip()
                if value:
                    return value
            elif isinstance(data, str) and data.strip():
                return data.strip()
        except Exception:
            continue
    return ""


def _detect_local_root() -> str:
    try:
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
    except Exception:
        pass
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_folder_path_from_config(local_dir: str) -> str:
    candidate_configs = [
        os.path.join(os.path.expanduser("~"), ".excel_processor", "config.json"),
        os.path.join(local_dir, "_internal", "config.json"),
        os.path.join(local_dir, "config.json"),
    ]
    for config_path in candidate_configs:
        config = _read_json_file(config_path)
        if not config:
            continue
        folder_path = str(config.get("folder_path", "")).strip()
        if folder_path:
            return folder_path
        defaults = config.get("defaults", {})
        if isinstance(defaults, dict):
            folder_path = str(defaults.get("folder_path", "")).strip()
            if folder_path:
                return folder_path
    return ""


def _detect_main_executable(local_dir: str) -> str:
    preferred = os.path.join(local_dir, "接口筛选.exe")
    if os.path.exists(preferred):
        return os.path.basename(preferred)

    try:
        for file_name in os.listdir(local_dir):
            lower = file_name.lower()
            if lower.endswith(".exe") and lower != "update.exe":
                return file_name
    except Exception:
        pass
    return ""


def fill_missing_args(args):
    """补全缺失参数，支持双击 update.exe 时自动推断上下文。"""
    local_dir = os.path.abspath(args.local or _detect_local_root())
    args.local = local_dir

    if not args.main_exe:
        args.main_exe = _detect_main_executable(local_dir)

    if not args.remote:
        folder_path = _load_folder_path_from_config(local_dir)
        if folder_path:
            args.remote = os.path.join(folder_path, "EXE")

    if not args.version and args.remote:
        args.version = _read_version_from_candidates(
            os.path.join(args.remote, "version.json"),
            os.path.join(args.remote, "_internal", "version.json"),
        )

    if not args.version:
        args.version = _read_version_from_candidates(
            os.path.join(local_dir, "version.json"),
            os.path.join(local_dir, "_internal", "version.json"),
        )

    return args


def _is_process_running(process_name: str) -> bool:
    """
    检测指定名称的进程是否正在运行
    
    使用 Windows tasklist 命令，不需要额外依赖
    """
    try:
        # 使用 tasklist 命令查找进程
        result = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {process_name}', '/NH'],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        # 如果输出中包含进程名，说明进程正在运行
        output = result.stdout.lower()
        return process_name.lower() in output
        
    except Exception as e:
        log(f"进程检测失败: {e}", "WARNING")
        return False  # 检测失败时假设进程已退出


def _is_pid_running(pid: int) -> bool:
    """根据 PID 检测进程是否存在。"""
    if not pid or pid <= 0:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        output = (result.stdout or "").lower()
        # 兼容中英文系统：输出里包含 PID 号即视为进程仍存在
        return str(pid) in output
    except Exception as e:
        log(f"PID检测失败(pid={pid}): {e}", "WARNING")
        return False


def _is_file_locked(filepath: str) -> bool:
    """检测文件是否被锁定（正在被使用）"""
    try:
        # 尝试以独占写入模式打开文件
        with open(filepath, "rb+"):
            return False  # 能打开，说明未锁定
    except (OSError, PermissionError):
        return True  # 打不开，说明被锁定


def wait_for_main_exit(
    main_executable: Optional[str],
    timeout: int = DEFAULT_MAIN_EXIT_TIMEOUT_SECONDS,
    main_pid: Optional[int] = None,
) -> bool:
    """
    等待主程序退出
    
    优先使用进程检测（更可靠），备用文件锁检测
    """
    deadline = time.time() + timeout
    wait_count = 0

    # 优先按 PID 等待（更精准，避免同名进程误判）。
    if main_pid and int(main_pid) > 0:
        log(f"等待主程序退出: pid={main_pid}")
        time.sleep(0.3)
        while time.time() <= deadline:
            if not _is_pid_running(int(main_pid)):
                log(f"主程序已退出（PID检测），等待了 {wait_count} 秒")
                time.sleep(0.3)
                return True
            wait_count += 1
            if wait_count % 5 == 0:
                log(f"仍在等待主程序退出... ({wait_count}秒)")
            time.sleep(1)
        log(f"等待主程序退出超时 ({timeout}秒, pid={main_pid})", "WARNING")
        return False

    if not main_executable or not os.path.exists(main_executable):
        log("主程序文件不存在或未指定，跳过等待")
        return True

    exe_name = os.path.basename(main_executable)
    log(f"等待主程序退出: {exe_name}")

    # 先等待一小段时间，让主程序有机会开始退出流程
    time.sleep(0.5)

    while time.time() <= deadline:
        if not _is_process_running(exe_name):
            log(f"主程序已退出（进程检测），等待了 {wait_count} 秒")
            time.sleep(0.5)
            return True

        wait_count += 1
        if wait_count % 5 == 0:
            log(f"仍在等待主程序退出... ({wait_count}秒)")
        time.sleep(1)

    # 超时后，尝试用文件锁检测作为最后验证
    log("进程检测超时，尝试文件锁检测...")
    if not _is_file_locked(main_executable):
        log("文件锁检测通过，继续更新")
        return True

    log(f"等待主程序退出超时 ({timeout}秒)", "WARNING")
    return False


def get_current_executable() -> Optional[str]:
    """获取当前正在运行的可执行文件名"""
    try:
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的 exe
            return os.path.basename(sys.executable)
        else:
            # Python 脚本模式
            return None
    except Exception:
        return None


def copy_directory_atomic(remote_dir: str, local_dir: str, skip_files: Optional[set] = None) -> list:
    """
    同步远程目录到本地目录（增量复制）。
    
    Args:
        remote_dir: 源目录
        local_dir: 目标目录
        skip_files: 要跳过的文件名集合（如正在运行的 update.exe）
    
    Returns:
        被占用而跳过的文件列表
    """
    skip_files = skip_files or set()

    log(f"开始复制: {remote_dir} -> {local_dir}")
    if skip_files:
        log(f"跳过文件: {skip_files}")

    # 直接做增量同步，避免“远程->临时->本地”双倍复制导致更新过慢。
    locked_files = sync_directory(remote_dir, local_dir, skip_files)
    log("文件复制完成")
    return locked_files


def _should_copy_file(src_file: str, dst_file: str) -> bool:
    """判断文件是否需要复制（按大小+修改时间做快速比较）。"""
    if not os.path.exists(dst_file):
        return True
    try:
        src_stat = os.stat(src_file)
        dst_stat = os.stat(dst_file)
        if src_stat.st_size != dst_stat.st_size:
            return True
        return int(src_stat.st_mtime) != int(dst_stat.st_mtime)
    except Exception:
        return True


def sync_directory(source: str, target: str, skip_files: Optional[set] = None) -> list:
    """
    同步目录
    
    返回:
        被占用而跳过的文件列表（相对路径）
    """
    skip_files = skip_files or set()
    skip_lower = {f.lower() for f in skip_files}
    
    os.makedirs(target, exist_ok=True)
    
    file_count = 0
    skip_count = 0
    unchanged_count = 0
    error_count = 0
    locked_files = []  # 记录被占用的文件
    
    for root, dirs, files in os.walk(source):
        rel_root = os.path.relpath(root, source)
        target_root = target if rel_root == "." else os.path.join(target, rel_root)
        os.makedirs(target_root, exist_ok=True)

        for file_name in files:
            # 检查是否需要跳过
            if file_name.lower() in skip_lower:
                skip_count += 1
                continue
            
            src_file = os.path.join(root, file_name)
            dst_file = os.path.join(target_root, file_name)
            rel_path = os.path.join(rel_root, file_name) if rel_root != "." else file_name

            # 增量复制：未变化文件直接跳过
            if not _should_copy_file(src_file, dst_file):
                unchanged_count += 1
                continue

            try:
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                shutil.copy2(src_file, dst_file)
                file_count += 1
            except PermissionError:
                # 文件被占用，记录下来
                log(f"  文件被占用，跳过: {file_name}", "WARNING")
                locked_files.append(rel_path)
                skip_count += 1
            except Exception as e:
                log(f"  同步文件失败: {file_name} - {e}", "ERROR")
                error_count += 1
    
    log(
        f"同步完成: 更新 {file_count} 个, 未变化 {unchanged_count} 个, "
        f"跳过 {skip_count} 个, 失败 {error_count} 个"
    )
    return locked_files


def restart_main_program(
    local_dir: str,
    main_executable: Optional[str],
    resume_action: str,
    auto_mode: bool,
) -> None:
    """重启主程序"""
    cmd: list[str] = []

    if main_executable:
        candidate = os.path.join(local_dir, main_executable)
        if os.path.exists(candidate):
            cmd = [candidate]
            log(f"找到主程序: {candidate}")
        else:
            log(f"主程序不存在: {candidate}", "WARNING")

    if not cmd:
        # 回退到Python脚本启动
        base_script = os.path.join(local_dir, "base.py")
        if os.path.exists(base_script):
            cmd = [sys.executable, base_script]
            log(f"使用Python脚本启动: {base_script}")
        else:
            log("找不到可启动的程序", "ERROR")
            return

    if auto_mode and "--auto" not in cmd:
        cmd.append("--auto")

    if resume_action:
        cmd += ["--resume", resume_action]

    log(f"启动命令: {' '.join(cmd)}")
    
    try:
        subprocess.Popen(cmd, cwd=local_dir, close_fds=False)
        log("主程序启动成功")
    except Exception as e:
        log(f"启动主程序失败: {e}", "ERROR")
        raise


def analyze_locked_files(locked_files: list) -> dict:
    """
    分析被锁定的文件，判断是否影响更新
    
    Args:
        locked_files: 被锁定的文件列表
    
    Returns:
        分析结果字典，包含 critical（关键文件）和 safe（安全跳过的文件）
    """
    # 关键文件模式（如果这些文件需要更新但被跳过，可能会有问题）
    critical_patterns = [
        # Python 核心 - 只有在 Python 版本升级时才变化
        "python3",  # python3xx.dll
        "base_library.zip",
    ]
    
    # 安全跳过的文件（运行时库，通常不变）
    safe_patterns = [
        "ucrtbase.dll",
        "VCRUNTIME",
        "api-ms-win",
        "_bz2.pyd",
        "_lzma.pyd",
        "_hashlib.pyd",
        "_ssl.pyd",
        "_ctypes.pyd",
    ]
    
    result = {
        "critical": [],
        "safe": [],
        "unknown": []
    }
    
    for file_path in locked_files:
        file_name = os.path.basename(file_path).lower()
        
        # 检查是否是安全跳过的文件
        is_safe = any(pattern.lower() in file_name for pattern in safe_patterns)
        if is_safe:
            result["safe"].append(file_path)
            continue
        
        # 检查是否是关键文件
        is_critical = any(pattern.lower() in file_name for pattern in critical_patterns)
        if is_critical:
            result["critical"].append(file_path)
            continue
        
        result["unknown"].append(file_path)
    
    return result


def _has_restart_blocking_locks(analysis: dict) -> bool:
    """判断被占用文件是否会导致重启后程序不完整。"""
    if analysis.get("critical"):
        return True

    blocking_suffixes = (".dll", ".pyd", ".exe", ".zip")
    for file_path in analysis.get("unknown", []):
        normalized = str(file_path).replace("/", "\\").lower()
        if normalized.endswith(blocking_suffixes):
            return True
        if "\\_internal\\" in normalized:
            return True
    return False


def perform_update(args) -> bool:
    """执行更新流程"""
    remote_dir = os.path.abspath(args.remote)
    local_dir = os.path.abspath(args.local)
    
    # 初始化日志文件
    init_log_file(local_dir)
    
    log("=" * 60)
    log("自动更新开始")
    log(f"目标版本: {args.version}")
    log(f"远程目录: {remote_dir}")
    log(f"本地目录: {local_dir}")
    log(f"主程序: {args.main_exe or '(未指定)'}")
    log(f"主程序PID: {args.main_pid or '(未指定)'}")
    log(f"自动模式: {args.auto_mode}")
    log("=" * 60)

    # 检查远程目录
    if not os.path.exists(remote_dir):
        log(f"远程目录不存在: {remote_dir}", "ERROR")
        return False

    try:
        # 获取当前运行的可执行文件名（需要跳过）
        current_exe = get_current_executable()
        skip_files = set()
        if current_exe:
            skip_files.add(current_exe)
            log(f"当前运行的程序: {current_exe} (将跳过复制)")
        
        # 等待主程序退出
        main_exe_path = (
            os.path.join(local_dir, args.main_exe) if args.main_exe else None
        )
        
        log("步骤 1/3: 等待主程序退出...")
        if not wait_for_main_exit(main_exe_path, main_pid=args.main_pid or None):
            log("主程序未能正常退出，继续尝试更新", "WARNING")
        
        # 复制文件
        log("步骤 2/3: 复制更新文件...")
        locked_files = copy_directory_atomic(remote_dir, local_dir, skip_files)
        
        # 分析被锁定的文件
        if locked_files:
            log("-" * 40)
            log("被占用文件分析:")
            analysis = analyze_locked_files(locked_files)
            
            if analysis["safe"]:
                log(f"  [安全] 运行时库文件 (无影响): {len(analysis['safe'])} 个")
                for f in analysis["safe"]:
                    log(f"    - {f}")
            
            if analysis["critical"]:
                log(f"  [注意] Python核心文件: {len(analysis['critical'])} 个", "WARNING")
                for f in analysis["critical"]:
                    log(f"    - {f}")
                log("  提示: 这些文件通常只在Python版本升级时需要更新", "WARNING")
                log("  如果遇到问题，请手动复制这些文件", "WARNING")
            
            if analysis["unknown"]:
                log(f"  [未知] 其他文件: {len(analysis['unknown'])} 个")
                for f in analysis["unknown"]:
                    log(f"    - {f}")
            
            log("-" * 40)

            if _has_restart_blocking_locks(analysis):
                log("检测到关键运行文件仍被占用，本次更新终止，避免重启后出现运行时损坏。", "ERROR")
                log("请确认旧程序已完全退出后重新执行更新。", "ERROR")
                return False
        
        # 重启主程序
        log("步骤 3/3: 重启主程序...")
        restart_main_program(local_dir, args.main_exe, args.resume, args.auto_mode)
        
        log("=" * 60)
        log("更新流程完成！")
        log("=" * 60)
        return True
        
    except Exception as e:
        log(f"更新过程中发生错误: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return False


def main(argv: Optional[Iterable[str]] = None) -> int:
    """主入口"""
    try:
        args = parse_args(argv)
        args = fill_missing_args(args)
        init_log_file(args.local or _detect_local_root())

        missing_args = []
        if not args.remote:
            missing_args.append("--remote")
        if not args.local:
            missing_args.append("--local")
        if not args.version:
            missing_args.append("--version")
        if missing_args:
            log(f"缺少必要参数，且自动推断失败: {', '.join(missing_args)}", "ERROR")
            print("提示：可由主程序自动触发更新，或在配置中补齐 folder_path/defaults.folder_path。")
            print("当前推断结果：")
            print(f"  local={args.local or '(空)'}")
            print(f"  remote={args.remote or '(空)'}")
            print(f"  version={args.version or '(空)'}")
            return 1

        success = perform_update(args)
        
        if not success:
            # 更新失败时暂停，让用户能看到错误信息
            print("\n" + "=" * 60)
            print("更新失败！请查看上方错误信息。")
            print("按 Enter 键退出...")
            print("=" * 60)
            try:
                input()
            except Exception:
                time.sleep(10)  # 如果无法等待输入，至少等待10秒
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        print(traceback.format_exc())
        print("\n按 Enter 键退出...")
        try:
            input()
        except Exception:
            time.sleep(10)
        return 1


if __name__ == "__main__":
    sys.exit(main())
