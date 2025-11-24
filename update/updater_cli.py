# -*- coding: utf-8 -*-
"""
update.exe 的入口脚本：
1. 等待主程序退出
2. 从共享目录复制最新版本到本地
3. 重新启动主程序
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Iterable, Optional


def parse_args(argv: Optional[Iterable[str]] = None):
    parser = argparse.ArgumentParser(description="接口筛选程序自动更新器")
    parser.add_argument("--remote", required=True, help="最新版本所在的 EXE 目录")
    parser.add_argument("--local", required=True, help="当前程序所在目录")
    parser.add_argument("--version", required=True, help="目标版本号")
    parser.add_argument("--resume", default="", help="重启后需要恢复的动作")
    parser.add_argument("--main-exe", default="", help="主程序可执行文件名")
    parser.add_argument("--auto-mode", action="store_true", help="重启时附加 --auto")
    return parser.parse_args(list(argv) if argv is not None else None)


def wait_for_main_exit(main_executable: Optional[str], timeout: int = 120) -> bool:
    if not main_executable or not os.path.exists(main_executable):
        return True

    deadline = time.time() + timeout
    while time.time() <= deadline:
        try:
            with open(main_executable, "rb+"):
                return True
        except OSError:
            time.sleep(1)

    return False


def copy_directory_atomic(remote_dir: str, local_dir: str) -> None:
    """
    先复制到临时目录，再同步到目标目录，避免半成品。
    """
    parent_dir = os.path.dirname(local_dir.rstrip("\\/")) or "."
    tmp_dir = tempfile.mkdtemp(prefix="update_tmp_", dir=parent_dir)

    try:
        shutil.copytree(remote_dir, tmp_dir, dirs_exist_ok=True)
        sync_directory(tmp_dir, local_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def sync_directory(source: str, target: str) -> None:
    os.makedirs(target, exist_ok=True)
    for root, dirs, files in os.walk(source):
        rel_root = os.path.relpath(root, source)
        target_root = target if rel_root == "." else os.path.join(target, rel_root)
        os.makedirs(target_root, exist_ok=True)

        for file_name in files:
            src_file = os.path.join(root, file_name)
            dst_file = os.path.join(target_root, file_name)
            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            shutil.copy2(src_file, dst_file)


def restart_main_program(
    local_dir: str,
    main_executable: Optional[str],
    resume_action: str,
    auto_mode: bool,
) -> None:
    cmd: list[str]

    if main_executable:
        candidate = os.path.join(local_dir, main_executable)
        if os.path.exists(candidate):
            cmd = [candidate]
        else:
            cmd = []
    else:
        cmd = []

    if not cmd:
        # 回退到Python脚本启动
        base_script = os.path.join(local_dir, "base.py")
        cmd = [sys.executable, base_script]

    if auto_mode and "--auto" not in cmd:
        cmd.append("--auto")

    if resume_action:
        cmd += ["--resume", resume_action]

    subprocess.Popen(cmd, cwd=local_dir, close_fds=False)


def perform_update(args) -> bool:
    remote_dir = os.path.abspath(args.remote)
    local_dir = os.path.abspath(args.local)

    if not os.path.exists(remote_dir):
        print(f"[update] 远程目录不存在: {remote_dir}")
        return False

    print(f"[update] 准备更新到版本 {args.version}")
    main_exe_path = (
        os.path.join(local_dir, args.main_exe) if args.main_exe else None
    )

    wait_for_main_exit(main_exe_path)
    copy_directory_atomic(remote_dir, local_dir)
    restart_main_program(local_dir, args.main_exe, args.resume, args.auto_mode)
    print("[update] 更新流程已完成，主程序正在重启")
    return True


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    success = perform_update(args)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

