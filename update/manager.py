# -*- coding: utf-8 -*-
"""
主程序调用的版本检测与更新触发逻辑。
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Optional

from .versioning import compare_versions, read_version, DEFAULT_VERSION

try:
    from tkinter import messagebox
except Exception:  # pragma: no cover - 在无图形环境下 fallback
    messagebox = None  # type: ignore


class UpdateReason:
    """更新触发原因常量"""

    AUTO_FLOW = "auto_flow"
    START_PROCESSING = "start_processing"
    EXPORT_RESULTS = "export_results"


@dataclass
class UpdateContext:
    local_root: str
    remote_root: str
    remote_version: str
    resume_action: str
    auto_mode: bool
    parent_window: Optional[object] = None


class UpdateManager:
    """负责版本检查与触发 update.exe"""

    def __init__(
        self,
        app_root: str,
        *,
        main_executable: Optional[str] = None,
        version_filename: str = "version.json",
        update_executable: str = "update.exe",
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.app_root = os.path.abspath(app_root)
        self.version_filename = version_filename
        self.update_executable = update_executable
        self.main_executable = (
            main_executable or os.path.basename(sys.executable)
        )
        self.log_fn = log_fn or (lambda msg: print(f"[Update] {msg}"))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def check_and_update(
        self,
        *,
        folder_path: Optional[str],
        reason: str,
        resume_action: Optional[str],
        auto_mode: bool,
        parent_window=None,
    ) -> bool:
        """
        返回 True 表示版本已是最新，可继续执行原逻辑。
        返回 False 表示已触发更新，调用方应立刻中止后续流程。
        """
        remote_root = self._resolve_remote_dir(folder_path)
        if not remote_root:
            return True

        local_version = self._read_local_version()
        remote_version = self._read_remote_version(remote_root)

        if remote_version == DEFAULT_VERSION:
            self._log(f"远程目录缺少版本文件，跳过更新: {remote_root}")
            return True

        cmp_result = compare_versions(local_version, remote_version)
        if cmp_result >= 0:
            self._log(
                f"版本已最新: local={local_version}, remote={remote_version}"
            )
            return True

        resume = resume_action or reason
        context = UpdateContext(
            local_root=self.app_root,
            remote_root=remote_root,
            remote_version=remote_version,
            resume_action=resume,
            auto_mode=auto_mode,
            parent_window=parent_window,
        )
        self._notify_user(context)
        self._launch_update_exe(context)
        return False

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _resolve_remote_dir(self, folder_path: Optional[str]) -> Optional[str]:
        if not folder_path:
            self._log("未配置源文件夹路径，跳过版本检查")
            return None

        remote_root = os.path.join(folder_path, "EXE")
        if not os.path.exists(remote_root):
            self._log(f"远程EXE目录不存在，跳过版本检查: {remote_root}")
            return None

        # 避免本地目录与远程目录相同
        try:
            local_real = os.path.realpath(self.app_root)
            remote_real = os.path.realpath(remote_root)
            if os.path.normcase(local_real) == os.path.normcase(remote_real):
                self._log("远程目录与本地目录相同，跳过更新")
                return None
        except Exception:
            pass

        return remote_root

    def _notify_user(self, context: UpdateContext) -> None:
        message = (
            f"检测到新版本（{context.remote_version}），"
            f"即将自动更新并重启程序..."
        )
        self._log(message)

        if not messagebox:
            return

        try:
            kwargs = {}
            if context.parent_window:
                kwargs["parent"] = context.parent_window
            messagebox.showinfo("更新提示", "检测到新版本，正在执行更新", **kwargs)
        except Exception:
            # 在某些无界面环境下可能失败，静默忽略
            pass

    def _launch_update_exe(self, context: UpdateContext) -> None:
        update_runner = self._resolve_update_runner()
        if not update_runner:
            self._log("未找到 update.exe 或 updater_cli.py，无法执行更新")
            return

        cmd = list(update_runner)
        cmd += [
            "--remote",
            context.remote_root,
            "--local",
            context.local_root,
            "--version",
            context.remote_version,
        ]

        if context.resume_action:
            cmd += ["--resume", context.resume_action]

        if self.main_executable:
            cmd += ["--main-exe", self.main_executable]

        if context.auto_mode:
            cmd.append("--auto-mode")

        self._log(f"启动update进程: {' '.join(cmd)}")

        try:
            subprocess.Popen(cmd, close_fds=False)
        except Exception as exc:
            self._log(f"启动 update 失败: {exc}")
            raise

    def _resolve_update_runner(self):
        exe_path = os.path.join(self.app_root, self.update_executable)
        if os.path.exists(exe_path):
            return [exe_path]

        script_path = os.path.join(self.app_root, "update", "updater_cli.py")
        if os.path.exists(script_path):
            return [sys.executable, script_path]

        return None

    def _log(self, message: str) -> None:
        try:
            self.log_fn(message)
        except Exception:
            print(f"[Update] {message}")

    # ------------------------------------------------------------------ #
    # Version helpers
    # ------------------------------------------------------------------ #
    def _version_candidates_from_local(self):
        yield os.path.join(self.app_root, self.version_filename)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            yield os.path.join(meipass, self.version_filename)

    def _version_candidates_from_remote(self, remote_root: str):
        yield os.path.join(remote_root, self.version_filename)
        yield os.path.join(remote_root, "_internal", self.version_filename)

    def _read_first_available_version(self, candidates) -> str:
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    return read_version(path)
                except Exception as exc:
                    self._log(f"读取版本文件失败({path}): {exc}")
                    continue
        return DEFAULT_VERSION

    def _read_local_version(self) -> str:
        return self._read_first_available_version(
            self._version_candidates_from_local()
        )

    def _read_remote_version(self, remote_root: str) -> str:
        return self._read_first_available_version(
            self._version_candidates_from_remote(remote_root)
        )

