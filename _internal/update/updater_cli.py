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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional


# 日志文件路径（与 update.exe 同目录）
LOG_FILE: Optional[str] = None

# 等待主程序退出的默认超时（秒）
# 说明：主程序若未能及时退出，更新器仍会继续尝试更新（会打印 WARNING）。
DEFAULT_MAIN_EXIT_TIMEOUT_SECONDS = 30
DEFAULT_COPY_RETRY_COUNT = 3
DEFAULT_COPY_RETRY_DELAY_SECONDS = 0.4
DEFAULT_LOCK_RECOVERY_TIMEOUT_SECONDS = 15
LOCKED_FILE_LOG_SAMPLE_LIMIT = 10


@dataclass
class SyncResult:
    """记录一次目录同步的结果，便于决定是否允许重启。"""

    updated_count: int = 0
    skipped_count: int = 0
    unchanged_count: int = 0
    error_count: int = 0
    total_candidates: int = 0
    locked_files: list[str] = field(default_factory=list)


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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    if (
        os.path.basename(script_dir).lower() == "update"
        and os.path.basename(parent_dir).lower() == "_internal"
    ):
        return os.path.dirname(parent_dir)
    return parent_dir


def _normalize_path(path: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(path))
    except Exception:
        return os.path.normcase(str(path))


def _same_file(path_a: str, path_b: str) -> bool:
    try:
        return os.path.samefile(path_a, path_b)
    except Exception:
        return _normalize_path(path_a) == _normalize_path(path_b)


def _is_path_inside(path: str, parent: str) -> bool:
    try:
        path_norm = _normalize_path(path)
        parent_norm = _normalize_path(parent)
        return os.path.commonpath([path_norm, parent_norm]) == parent_norm
    except Exception:
        return False


def _current_executable_inside(local_dir: str) -> bool:
    try:
        return _is_path_inside(sys.executable, local_dir)
    except Exception:
        return False


def _args_to_argv(args) -> list[str]:
    argv: list[str] = []
    if args.remote:
        argv += ["--remote", args.remote]
    if args.local:
        argv += ["--local", args.local]
    if args.version:
        argv += ["--version", args.version]
    if args.resume:
        argv += ["--resume", args.resume]
    if args.main_exe:
        argv += ["--main-exe", args.main_exe]
    if args.main_pid:
        argv += ["--main-pid", str(args.main_pid)]
    if args.auto_mode:
        argv.append("--auto-mode")
    return argv


def _resolve_remote_update_exe(remote_dir: str) -> str:
    for candidate in (
        os.path.join(remote_dir, "update.exe"),
        os.path.join(remote_dir, "_internal", "update.exe"),
    ):
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return ""


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


def _terminate_pid(pid: int) -> bool:
    """只强制结束触发更新的主程序 PID，避免误杀同名程序。"""
    if not pid or int(pid) <= 0:
        return False
    pid = int(pid)
    if pid == os.getpid():
        log("拒绝结束当前更新器进程", "ERROR")
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        if result.returncode == 0:
            log(f"已强制结束主程序 PID: {pid}", "WARNING")
            return True
        log(f"结束主程序 PID 失败: {result.stderr or result.stdout}", "WARNING")
    except Exception as e:
        log(f"结束主程序 PID 异常: {e}", "WARNING")
    return False


def _is_file_locked(filepath: str) -> bool:
    """检测文件是否被锁定（正在被使用）"""
    try:
        # 尝试以独占写入模式打开文件
        with open(filepath, "rb+"):
            return False  # 能打开，说明未锁定
    except (OSError, PermissionError):
        return True  # 打不开，说明被锁定


def _critical_runtime_paths(local_dir: str) -> list[str]:
    """列出本地 PyInstaller 运行时关键文件。"""
    internal_dir = os.path.join(local_dir, "_internal")
    paths = [os.path.join(internal_dir, "base_library.zip")]
    try:
        if os.path.isdir(internal_dir):
            for name in os.listdir(internal_dir):
                lower = name.lower()
                if lower.startswith("python") and lower.endswith(".dll"):
                    paths.append(os.path.join(internal_dir, name))
    except Exception:
        pass
    return paths


def _wait_for_runtime_locks_released(
    local_dir: str,
    timeout: int = DEFAULT_LOCK_RECOVERY_TIMEOUT_SECONDS,
) -> bool:
    """等待本地关键运行时文件锁释放。"""
    deadline = time.time() + timeout
    while time.time() <= deadline:
        locked = [
            path
            for path in _critical_runtime_paths(local_dir)
            if os.path.exists(path) and _is_file_locked(path)
        ]
        if not locked:
            return True
        rel_locked = ", ".join(os.path.relpath(path, local_dir) for path in locked)
        log(f"等待关键运行时文件释放: {rel_locked}", "WARNING")
        time.sleep(1)
    return False


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


def get_current_executable(local_dir: Optional[str] = None) -> Optional[str]:
    """获取当前正在运行的可执行文件名"""
    try:
        if getattr(sys, 'frozen', False):
            if local_dir and not _current_executable_inside(local_dir):
                return None
            # PyInstaller 打包后的 exe
            return os.path.basename(sys.executable)
        else:
            # Python 脚本模式
            return None
    except Exception:
        return None


def copy_directory_atomic(remote_dir: str, local_dir: str, skip_files: Optional[set] = None) -> SyncResult:
    """
    同步远程目录到本地目录（增量复制）。
    
    Args:
        remote_dir: 源目录
        local_dir: 目标目录
        skip_files: 要跳过的文件名集合（如正在运行的 update.exe）
    
    Returns:
        同步结果（包含被占用文件、失败数等）
    """
    skip_files = skip_files or set()

    log(f"开始复制: {remote_dir} -> {local_dir}")
    if skip_files:
        log(f"跳过文件: {skip_files}")

    # 直接做增量同步，避免“远程->临时->本地”双倍复制导致更新过慢。
    sync_result = sync_directory(remote_dir, local_dir, skip_files)
    log("文件复制完成")
    return sync_result


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


def _sync_priority(rel_path: str) -> tuple:
    normalized = str(rel_path).replace("/", "\\").lower()
    if normalized.startswith("_internal\\python\\"):
        return (3, normalized)
    if normalized.startswith("_internal\\"):
        return (2, normalized)
    if "\\" in normalized:
        return (1, normalized)
    return (0, normalized)


def _copy_file_with_retry(src_file: str, dst_file: str) -> str:
    last_error: Optional[Exception] = None
    for attempt in range(1, DEFAULT_COPY_RETRY_COUNT + 1):
        try:
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            shutil.copy2(src_file, dst_file)
            return "copied"
        except PermissionError as exc:
            last_error = exc
            if attempt < DEFAULT_COPY_RETRY_COUNT:
                time.sleep(DEFAULT_COPY_RETRY_DELAY_SECONDS * attempt)
                continue
            return "locked"
        except Exception as exc:
            last_error = exc
            log(f"  同步文件失败: {os.path.basename(src_file)} - {exc}", "ERROR")
            return "error"

    if last_error:
        log(f"  同步文件失败: {os.path.basename(src_file)} - {last_error}", "ERROR")
    return "error"


def sync_directory(source: str, target: str, skip_files: Optional[set] = None) -> SyncResult:
    """
    同步目录
    
    返回:
        目录同步结果
    """
    skip_files = skip_files or set()
    skip_lower = {str(f).replace("/", "\\").lower() for f in skip_files}
    
    os.makedirs(target, exist_ok=True)
    
    result = SyncResult()
    file_entries = []

    for root, dirs, files in os.walk(source):
        rel_root = os.path.relpath(root, source)
        target_root = target if rel_root == "." else os.path.join(target, rel_root)
        os.makedirs(target_root, exist_ok=True)
        for file_name in files:
            src_file = os.path.join(root, file_name)
            dst_file = os.path.join(target_root, file_name)
            rel_path = os.path.join(rel_root, file_name) if rel_root != "." else file_name
            file_entries.append((rel_path, src_file, dst_file, file_name))

    file_entries.sort(key=lambda item: _sync_priority(item[0]))

    result.total_candidates = len(file_entries)
    log(f"待检查文件: {result.total_candidates} 个")

    for rel_path, src_file, dst_file, file_name in file_entries:
        rel_lower = str(rel_path).replace("/", "\\").lower()
        # 检查是否需要跳过
        if file_name.lower() in skip_lower or rel_lower in skip_lower:
            result.skipped_count += 1
            continue

        # 增量复制：未变化文件直接跳过
        if not _should_copy_file(src_file, dst_file):
            result.unchanged_count += 1
            continue

        copy_status = _copy_file_with_retry(src_file, dst_file)
        if copy_status == "copied":
            result.updated_count += 1
        elif copy_status == "locked":
            result.locked_files.append(rel_path)
            result.skipped_count += 1
        else:
            result.error_count += 1
    
    log(
        f"同步完成: 更新 {result.updated_count} 个, 未变化 {result.unchanged_count} 个, "
        f"跳过 {result.skipped_count} 个, 失败 {result.error_count} 个"
    )
    return result


def retry_locked_files(
    remote_dir: str,
    local_dir: str,
    locked_files: list[str],
    skip_files: Optional[set] = None,
) -> list[str]:
    """对第一次同步被锁的文件做定点重试，返回仍未成功的相对路径。"""
    skip_lower = {f.lower() for f in (skip_files or set())}
    remaining: list[str] = []

    for rel_path in locked_files:
        if os.path.basename(rel_path).lower() in skip_lower:
            continue

        src_file = os.path.join(remote_dir, rel_path)
        dst_file = os.path.join(local_dir, rel_path)
        if not os.path.exists(src_file):
            remaining.append(rel_path)
            continue

        status = _copy_file_with_retry(src_file, dst_file)
        if status == "copied":
            log(f"  被占用文件重试成功: {rel_path}")
        else:
            remaining.append(rel_path)

    return remaining


def cleanup_nested_internal_dir(local_dir: str) -> None:
    """清理旧错误版本可能生成的 _internal/_internal 嵌套目录。"""
    nested_internal = os.path.join(local_dir, "_internal", "_internal")
    try:
        local_abs = os.path.abspath(local_dir)
        nested_abs = os.path.abspath(nested_internal)
        if (
            not os.path.isdir(nested_abs)
            or not _is_path_inside(nested_abs, local_abs)
            or os.path.normcase(nested_abs) == os.path.normcase(local_abs)
        ):
            return
        shutil.rmtree(nested_abs)
        log(f"已清理异常嵌套目录: {os.path.relpath(nested_abs, local_abs)}", "WARNING")
    except Exception as exc:
        log(f"清理异常嵌套目录失败: {exc}", "WARNING")


def restart_main_program(
    local_dir: str,
    main_executable: Optional[str],
    resume_action: str,
    auto_mode: bool,
) -> bool:
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
            return False

    if auto_mode and "--auto" not in cmd:
        cmd.append("--auto")

    if resume_action:
        cmd += ["--resume", resume_action]

    log(f"启动命令: {' '.join(cmd)}")
    
    try:
        subprocess.Popen(
            cmd,
            cwd=local_dir,
            close_fds=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log("主程序启动成功")
        return True
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


def log_locked_files_summary(analysis: dict, *, sample_limit: int = LOCKED_FILE_LOG_SAMPLE_LIMIT) -> None:
    total_locked = (
        len(analysis.get("critical", []))
        + len(analysis.get("safe", []))
        + len(analysis.get("unknown", []))
    )
    if total_locked <= 0:
        return

    log("-" * 40)
    log(f"检测到 {total_locked} 个被占用文件，以下显示摘要：", "WARNING")

    sections = [
        ("critical", "关键运行文件", "ERROR"),
        ("unknown", "其他待确认文件", "WARNING"),
        ("safe", "可安全跳过文件", "INFO"),
    ]
    for key, title, level in sections:
        items = analysis.get(key, [])
        if not items:
            continue
        log(f"  [{title}] {len(items)} 个", level)
        for sample in items[:sample_limit]:
            log(f"    - {sample}", level)
        remaining = len(items) - min(len(items), sample_limit)
        if remaining > 0:
            log(f"    ... 另有 {remaining} 个，详见 update_log.txt", level)
    log("-" * 40)


def _has_restart_blocking_locks(analysis: dict) -> bool:
    """判断被占用文件是否会导致重启后程序不完整。"""
    if analysis.get("critical"):
        return True

    blocking_suffixes = (".dll", ".pyd", ".exe", ".zip")
    for file_path in analysis.get("unknown", []):
        normalized = str(file_path).replace("/", "\\").lower()
        if normalized.startswith("_internal\\python\\"):
            continue
        if normalized.endswith(blocking_suffixes):
            return True
        if "\\_internal\\" in normalized:
            return True
    return False


def _reexec_with_remote_update_if_frozen(args) -> bool:
    """
    本地 update.exe 会占用本地 _internal 运行时。若远程包内有 update.exe，
    先切换到远程 update.exe，由它更新本地目录，避免本地运行时文件被锁。
    """
    if not getattr(sys, "frozen", False):
        return False
    if os.environ.get("UPDATE_REMOTE_REEXEC") == "1":
        return False

    local_dir = os.path.abspath(args.local or _detect_local_root())
    if not _current_executable_inside(local_dir):
        return False

    remote_dir = os.path.abspath(args.remote) if args.remote else ""
    remote_update_exe = _resolve_remote_update_exe(remote_dir)
    if not remote_update_exe:
        return False
    if _same_file(remote_update_exe, sys.executable):
        return False

    cmd = [remote_update_exe] + _args_to_argv(args)
    env = os.environ.copy()
    env["UPDATE_REMOTE_REEXEC"] = "1"
    log("检测到本地 update.exe 会占用本地 PyInstaller 运行时，切换到远程 update.exe")
    log(f"切换命令: {' '.join(cmd)}")
    subprocess.Popen(cmd, cwd=local_dir, env=env, close_fds=True)
    return True


def _reexec_with_cli_python_if_frozen(args, argv: Optional[Iterable[str]] = None) -> bool:
    """
    PyInstaller 版 update.exe 会占用本地 _internal/python*.dll。
    发现普通 Python 更新器时，先切换过去，再退出当前 update.exe。
    """
    if not getattr(sys, "frozen", False):
        return False
    if os.environ.get("UPDATE_CLI_REEXEC") == "1":
        return False

    local_dir = os.path.abspath(args.local or _detect_local_root())
    if not _current_executable_inside(local_dir):
        return False

    remote_dir = os.path.abspath(args.remote) if args.remote else ""
    candidates = [
        (
            os.path.join(remote_dir, "_internal", "python", "Scripts", "python.exe"),
            os.path.join(remote_dir, "_internal", "update", "updater_cli.py"),
        ),
        (
            os.path.join(local_dir, "_internal", "python", "Scripts", "python.exe"),
            os.path.join(local_dir, "_internal", "update", "updater_cli.py"),
        ),
        (
            os.path.join(local_dir, "python", "Scripts", "python.exe"),
            os.path.join(local_dir, "update", "updater_cli.py"),
        ),
        (
            os.path.join(local_dir, ".venv", "Scripts", "python.exe"),
            os.path.join(local_dir, "update", "updater_cli.py"),
        ),
    ]

    for python_exe, script_path in candidates:
        if not (os.path.exists(python_exe) and os.path.exists(script_path)):
            continue

        cmd = [python_exe, script_path] + _args_to_argv(args)
        env = os.environ.copy()
        env["UPDATE_CLI_REEXEC"] = "1"
        log("检测到 update.exe 会占用本地 PyInstaller 运行时，切换到普通 Python 更新器")
        log(f"切换命令: {' '.join(cmd)}")
        subprocess.Popen(cmd, cwd=local_dir, env=env, close_fds=True)
        return True

    log("未找到普通 Python 更新器，将继续使用 update.exe；若运行时文件被占用会中止更新", "WARNING")
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
        try:
            current_exe = get_current_executable(local_dir)
        except TypeError:
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
            if args.main_pid:
                _terminate_pid(args.main_pid)
                _wait_for_runtime_locks_released(local_dir)
        
        # 复制文件
        log("步骤 2/3: 复制更新文件...")
        copy_started_at = time.time()
        sync_result = copy_directory_atomic(remote_dir, local_dir, skip_files)
        log(f"复制阶段耗时: {time.time() - copy_started_at:.1f} 秒")
        cleanup_nested_internal_dir(local_dir)

        if sync_result.error_count > 0:
            log(
                f"复制阶段出现 {sync_result.error_count} 个失败项，为避免安装不完整，本次更新终止。",
                "ERROR",
            )
            return False
        
        # 分析被锁定的文件
        if sync_result.locked_files:
            analysis = analyze_locked_files(sync_result.locked_files)
            if _has_restart_blocking_locks(analysis):
                log("检测到关键运行文件被占用，尝试释放主程序并定点重试复制", "WARNING")
                if args.main_pid and _is_pid_running(args.main_pid):
                    _terminate_pid(args.main_pid)
                _wait_for_runtime_locks_released(local_dir)
                sync_result.locked_files = retry_locked_files(
                    remote_dir,
                    local_dir,
                    sync_result.locked_files,
                    skip_files,
                )
                analysis = analyze_locked_files(sync_result.locked_files)

            log_locked_files_summary(analysis)

            if _has_restart_blocking_locks(analysis):
                log("检测到关键运行文件仍被占用，本次更新终止，避免重启后出现运行时损坏。", "ERROR")
                log("请确认旧程序已完全退出后重新执行更新。", "ERROR")
                return False
        
        # 重启主程序
        log("步骤 3/3: 重启主程序...")
        if not restart_main_program(local_dir, args.main_exe, args.resume, args.auto_mode):
            log("未找到可重启的主程序，本次更新终止。", "ERROR")
            return False
        
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
        if _reexec_with_remote_update_if_frozen(args):
            return 0
        if _reexec_with_cli_python_if_frozen(args, argv):
            return 0

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
