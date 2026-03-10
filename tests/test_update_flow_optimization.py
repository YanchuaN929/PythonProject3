#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import pytest

from update.manager import UpdateManager
from update import updater_cli


pytestmark = pytest.mark.allow_empty_name


def test_update_manager_passes_main_pid(monkeypatch, tmp_path):
    captured = {"cmd": None}

    manager = UpdateManager(str(tmp_path), log_fn=lambda _msg: None)

    monkeypatch.setattr(manager, "_resolve_remote_dir", lambda _folder: str(tmp_path / "remote"))
    monkeypatch.setattr(manager, "_read_local_version", lambda: "1.0.0")
    monkeypatch.setattr(manager, "_read_remote_version", lambda _remote: "1.0.1")
    monkeypatch.setattr(manager, "_notify_user", lambda _ctx: None)
    monkeypatch.setattr(manager, "_resolve_update_runner", lambda: ["python", "updater_cli.py"])

    def fake_popen(cmd, close_fds=False):
        captured["cmd"] = list(cmd)

        class _DummyProc:
            pass

        return _DummyProc()

    monkeypatch.setattr("update.manager.subprocess.Popen", fake_popen)

    should_continue = manager.check_and_update(
        folder_path="E:/dummy",
        reason="auto_flow",
        resume_action="auto_flow",
        auto_mode=False,
    )

    assert should_continue is False
    assert captured["cmd"] is not None
    assert "--main-pid" in captured["cmd"]
    pid_idx = captured["cmd"].index("--main-pid")
    assert captured["cmd"][pid_idx + 1] == str(os.getpid())


def test_resolve_update_runner_prefers_update_exe_when_frozen(monkeypatch, tmp_path):
    manager = UpdateManager(str(tmp_path), log_fn=lambda _msg: None)
    update_exe = tmp_path / "update.exe"
    update_exe.write_text("stub", encoding="utf-8")

    monkeypatch.setattr("update.manager.sys", type("FrozenSys", (), {"_MEIPASS": "X:/bundle", "frozen": True})())
    monkeypatch.setattr(manager, "_resolve_updater_script", lambda: str(tmp_path / "_internal" / "update" / "updater_cli.py"))
    monkeypatch.setattr(manager, "_resolve_cli_python", lambda: str(tmp_path / "_internal" / "python" / "Scripts" / "python.exe"))

    runner = manager._resolve_update_runner()

    assert runner == [str(update_exe)]


def test_resolve_update_runner_does_not_fallback_to_cli_when_frozen(monkeypatch, tmp_path):
    manager = UpdateManager(str(tmp_path), log_fn=lambda _msg: None)

    monkeypatch.setattr("update.manager.sys", type("FrozenSys", (), {"_MEIPASS": "X:/bundle", "frozen": True})())
    monkeypatch.setattr(manager, "_resolve_updater_script", lambda: str(tmp_path / "_internal" / "update" / "updater_cli.py"))
    monkeypatch.setattr(manager, "_resolve_cli_python", lambda: str(tmp_path / "_internal" / "python" / "Scripts" / "python.exe"))

    runner = manager._resolve_update_runner()

    assert runner is None


def test_launch_update_executable_uses_shell_execute(monkeypatch, tmp_path):
    manager = UpdateManager(str(tmp_path), log_fn=lambda _msg: None)
    update_exe = tmp_path / "update.exe"
    update_exe.write_text("stub", encoding="utf-8")
    captured = {}

    class DummyShell32:
        @staticmethod
        def ShellExecuteW(_hwnd, operation, file, params, directory, show_cmd):
            captured["operation"] = operation
            captured["file"] = file
            captured["params"] = params
            captured["directory"] = directory
            captured["show_cmd"] = show_cmd
            return 33

    class DummyWindll:
        shell32 = DummyShell32()

    monkeypatch.setattr("update.manager.ctypes.windll", DummyWindll())

    launched = manager._launch_update_executable(
        str(update_exe),
        ["--remote", "X:/remote/EXE", "--local", str(tmp_path)],
    )

    assert launched is True
    assert captured["operation"] == "open"
    assert captured["file"] == str(update_exe)
    assert "--remote" in captured["params"]
    assert captured["directory"] == str(tmp_path)
    assert captured["show_cmd"] == 1


def test_wait_for_main_exit_prefers_pid(monkeypatch):
    state = {"pid_checks": 0}

    def fake_pid_running(_pid):
        state["pid_checks"] += 1
        return state["pid_checks"] < 2

    monkeypatch.setattr(updater_cli, "_is_pid_running", fake_pid_running)
    monkeypatch.setattr(updater_cli, "_is_process_running", lambda _name: (_ for _ in ()).throw(AssertionError("should not call process-name check when pid is set")))
    monkeypatch.setattr(updater_cli.time, "sleep", lambda _s: None)

    tick = {"t": 0.0}

    def fake_time():
        tick["t"] += 0.2
        return tick["t"]

    monkeypatch.setattr(updater_cli.time, "time", fake_time)

    assert updater_cli.wait_for_main_exit(main_executable=None, timeout=5, main_pid=12345) is True
    assert state["pid_checks"] >= 2


def test_sync_directory_skips_unchanged_file(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    src_file = source / "a.txt"
    dst_file = target / "a.txt"
    src_file.write_text("same-content", encoding="utf-8")
    dst_file.write_text("same-content", encoding="utf-8")

    # 同步修改时间，确保 _should_copy_file 判定为未变化
    src_stat = src_file.stat()
    os.utime(dst_file, (src_stat.st_atime, src_stat.st_mtime))

    assert updater_cli._should_copy_file(str(src_file), str(dst_file)) is False


def test_resolve_update_folder_path_falls_back_to_defaults():
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.config = {
        "folder_path": "",
        "defaults": {"folder_path": "//server/share/project"},
    }
    app.default_config = {
        "defaults": {"folder_path": "//server/share/fallback"},
        "folder_path_lock_enabled": False,
    }

    assert (
        app._resolve_update_folder_path(include_runtime_selection=False)
        == "//server/share/project"
    )


def test_ensure_up_to_date_rechecks_after_startup_check_finished():
    from base import ExcelProcessorApp

    captured = {"folder_path": None}

    class DummyManager:
        def check_and_update(self, **kwargs):
            captured["folder_path"] = kwargs["folder_path"]
            return True

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.update_manager = DummyManager()
    app.config = {
        "folder_path": "",
        "defaults": {"folder_path": "//server/share/project"},
    }
    app.default_config = {
        "defaults": {"folder_path": "//server/share/fallback"},
        "folder_path_lock_enabled": False,
    }
    app.root = None
    app._startup_update_check_scheduled = True
    app._startup_update_check_finished = True
    app._update_shutdown_scheduled = False
    app.auto_mode = False

    assert app._ensure_up_to_date("start_processing", "start_processing") is True
    assert captured["folder_path"] == "//server/share/project"


def test_startup_update_worker_does_not_exit_when_launcher_fails():
    from base import ExcelProcessorApp

    events = []

    class DummyRoot:
        @staticmethod
        def after(_delay, callback):
            callback()

    class DummyManager:
        app_root = "E:/local-app"

        @staticmethod
        def sync_update_executable(_folder_path):
            return True

        @staticmethod
        def _resolve_remote_dir(_folder_path):
            return "//server/share/EXE"

        @staticmethod
        def _read_local_version():
            return "1.0.0"

        @staticmethod
        def _read_remote_version(_remote_root):
            return "1.0.1"

        @staticmethod
        def _notify_user(_context):
            events.append("notify")

        @staticmethod
        def _launch_update_exe(_context):
            events.append("launch_failed")
            return False

        @staticmethod
        def _log(_message):
            return None

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.update_manager = DummyManager()
    app.root = DummyRoot()
    app.config = {
        "folder_path": "",
        "defaults": {"folder_path": "//server/share/project"},
    }
    app.default_config = {
        "defaults": {"folder_path": "//server/share/fallback"},
        "folder_path_lock_enabled": False,
    }
    app.auto_mode = False
    app._startup_update_check_finished = False
    app._schedule_exit_for_update = lambda: events.append("exit")
    app._log_update_message = lambda _msg: None

    app._startup_update_check_worker()

    assert "launch_failed" in events
    assert "exit" not in events
    assert app._startup_update_check_finished is True


def test_fill_missing_args_supports_double_click(monkeypatch, tmp_path):
    local_dir = tmp_path / "app"
    internal_dir = local_dir / "_internal"
    remote_dir = tmp_path / "remote-root" / "EXE"
    home_dir = tmp_path / "home"
    config_dir = home_dir / ".excel_processor"
    config_dir.mkdir(parents=True, exist_ok=True)
    internal_dir.mkdir(parents=True, exist_ok=True)
    remote_dir.mkdir(parents=True, exist_ok=True)

    (local_dir / "接口筛选.exe").write_text("stub", encoding="utf-8")
    (remote_dir / "version.json").write_text('{"version":"1.2.3"}', encoding="utf-8")
    (config_dir / "config.json").write_text(
        '{"folder_path":"","defaults":{"folder_path":"%s"}}' % str(remote_dir.parent).replace("\\", "/"),
        encoding="utf-8",
    )

    monkeypatch.setattr(updater_cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(updater_cli.sys, "executable", str(local_dir / "update.exe"))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    monkeypatch.setenv("HOME", str(home_dir))

    args = updater_cli.parse_args([])
    args = updater_cli.fill_missing_args(args)

    assert args.local == str(local_dir)
    assert os.path.normpath(args.remote) == os.path.normpath(str(remote_dir))
    assert args.version == "1.2.3"
    assert args.main_exe == "接口筛选.exe"
