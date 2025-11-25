import types

import base


class DummyVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value


class DummyRoot:
    def __init__(self, calls):
        self._calls = calls

    def after(self, delay, func):
        self._calls.append(("after", delay))
        func()

    def quit(self):
        self._calls.append("quit")

    def destroy(self):
        self._calls.append("destroy")


def _build_stub_app():
    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    app._log_update_message = lambda msg: None
    app._update_shutdown_scheduled = False
    return app


def test_schedule_exit_for_update_invokes_root_and_exit(monkeypatch):
    calls = []
    logs = []
    app = _build_stub_app()
    app.root = DummyRoot(calls)
    app._log_update_message = lambda msg: logs.append(msg)

    exit_marker = {}

    def fake_exit(code):
        exit_marker["code"] = code

    monkeypatch.setattr(base.os, "_exit", fake_exit)

    app._schedule_exit_for_update()

    assert exit_marker["code"] == 0
    assert "quit" in calls
    assert "destroy" in calls
    assert app._update_shutdown_scheduled is True
    assert any("程序即将退出" in msg for msg in logs)


def test_ensure_up_to_date_requests_shutdown(monkeypatch):
    app = _build_stub_app()
    app.root = types.SimpleNamespace()
    app.path_var = DummyVar("D:\\\\MockSource")
    app.config = {}
    app.auto_mode = False

    exit_requested = {}

    def fake_schedule():
        exit_requested["called"] = True

    app._schedule_exit_for_update = fake_schedule

    class DummyManager:
        def check_and_update(self, **kwargs):
            return False

    app.update_manager = DummyManager()

    result = app._ensure_up_to_date("start_processing", "start_processing")

    assert result is False
    assert exit_requested.get("called") is True

