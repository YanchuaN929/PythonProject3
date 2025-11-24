import json
from pathlib import Path

import pytest

from update.manager import UpdateManager, UpdateReason
import update.manager as manager_module


def write_version(path: Path, version: str):
    path.write_text(json.dumps({"version": version}, ensure_ascii=False), encoding="utf-8")


def test_skip_when_remote_missing(tmp_path):
    local = tmp_path / "local"
    local.mkdir()
    write_version(local / "version.json", "2025.11.21.1")

    manager = UpdateManager(app_root=str(local), log_fn=lambda msg: None)
    assert manager.check_and_update(
        folder_path=str(tmp_path / "not_exists"),
        reason=UpdateReason.START_PROCESSING,
        resume_action=UpdateReason.START_PROCESSING,
        auto_mode=False,
        parent_window=None,
    )


def test_no_update_when_version_same(tmp_path, monkeypatch):
    local = tmp_path / "local"
    remote_root = tmp_path / "remote"
    exe_dir = remote_root / "EXE"
    exe_dir.mkdir(parents=True)
    local.mkdir()
    write_version(local / "version.json", "2025.11.21.1")
    write_version(exe_dir / "version.json", "2025.11.21.1")

    manager = UpdateManager(app_root=str(local), log_fn=lambda msg: None)
    called = {"launch": False}

    def fake_launch(_ctx):
        called["launch"] = True

    monkeypatch.setattr(manager, "_launch_update_exe", fake_launch)
    monkeypatch.setattr(manager_module, "messagebox", None)

    assert manager.check_and_update(
        folder_path=str(remote_root),
        reason=UpdateReason.START_PROCESSING,
        resume_action=UpdateReason.START_PROCESSING,
        auto_mode=False,
        parent_window=None,
    )
    assert not called["launch"]


def test_trigger_update_when_remote_newer(tmp_path, monkeypatch):
    local = tmp_path / "local"
    remote_root = tmp_path / "remote"
    exe_dir = remote_root / "EXE"
    exe_dir.mkdir(parents=True)
    local.mkdir()
    write_version(local / "version.json", "2025.11.21.1")
    write_version(exe_dir / "version.json", "2025.11.22.1")

    manager = UpdateManager(app_root=str(local), log_fn=lambda msg: None)
    captured = {}

    def fake_launch(ctx):
        captured["resume"] = ctx.resume_action
        captured["remote"] = ctx.remote_version

    monkeypatch.setattr(manager, "_launch_update_exe", fake_launch)
    monkeypatch.setattr(manager_module, "messagebox", None)

    assert not manager.check_and_update(
        folder_path=str(remote_root),
        reason=UpdateReason.START_PROCESSING,
        resume_action="start_processing",
        auto_mode=True,
        parent_window=None,
    )
    assert captured["resume"] == "start_processing"
    assert captured["remote"] == "2025.11.22.1"


def test_remote_version_from_internal_folder(tmp_path, monkeypatch):
    local = tmp_path / "local"
    remote_root = tmp_path / "remote"
    exe_dir = remote_root / "EXE" / "_internal"
    exe_dir.mkdir(parents=True)
    local.mkdir()

    write_version(local / "version.json", "2025.11.21.1")
    write_version(exe_dir / "version.json", "2025.11.25.1")

    manager = UpdateManager(app_root=str(local), log_fn=lambda msg: None)
    captured = {}

    def fake_launch(ctx):
        captured["remote"] = ctx.remote_version

    monkeypatch.setattr(manager, "_launch_update_exe", fake_launch)
    monkeypatch.setattr(manager_module, "messagebox", None)

    assert not manager.check_and_update(
        folder_path=str(remote_root),
        reason=UpdateReason.START_PROCESSING,
        resume_action=UpdateReason.START_PROCESSING,
        auto_mode=False,
        parent_window=None,
    )
    assert captured["remote"] == "2025.11.25.1"


def test_local_version_from_meipass(tmp_path, monkeypatch):
    local = tmp_path / "local"
    meipass = tmp_path / "embedded"
    local.mkdir()
    meipass.mkdir()

    write_version(meipass / "version.json", "2025.11.30.1")

    manager = UpdateManager(app_root=str(local), log_fn=lambda msg: None)
    monkeypatch.setattr(manager_module.sys, "_MEIPASS", str(meipass), raising=False)

    assert manager._read_local_version() == "2025.11.30.1"

