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
