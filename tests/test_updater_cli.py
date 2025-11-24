from types import SimpleNamespace

from update import updater_cli


def test_perform_update_copies_and_restarts(monkeypatch, tmp_path):
    remote_dir = tmp_path / "remote" / "EXE"
    remote_dir.mkdir(parents=True)
    local_dir = tmp_path / "local"
    local_dir.mkdir()

    (remote_dir / "app.exe").write_text("new binary", encoding="utf-8")
    (remote_dir / "version.json").write_text('{"version":"2025.11.22.1"}', encoding="utf-8")
    (local_dir / "app.exe").write_text("old binary", encoding="utf-8")

    captured = {}

    def fake_popen(cmd, cwd=None, close_fds=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["close_fds"] = close_fds

        class _Proc:
            def __init__(self):
                self.pid = 0

        return _Proc()

    monkeypatch.setattr(updater_cli, "subprocess", SimpleNamespace(Popen=fake_popen))

    args = SimpleNamespace(
        remote=str(remote_dir),
        local=str(local_dir),
        version="2025.11.22.1",
        resume="start_processing",
        main_exe="app.exe",
        auto_mode=True,
    )

    assert updater_cli.perform_update(args)

    # 本地文件已更新
    assert (local_dir / "app.exe").read_text(encoding="utf-8") == "new binary"
    assert "start_processing" in captured["cmd"]
    assert captured["cwd"] == str(local_dir)

