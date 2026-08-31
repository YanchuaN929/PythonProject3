import datetime
import threading

import pandas as pd

import base
from core import main, main2


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _ImmediateRoot:
    def after(self, _delay, callback):
        callback()


def test_excel_export_and_summary_run_outside_tk_thread(tmp_path, monkeypatch):
    export_event = threading.Event()
    summary_event = threading.Event()
    worker_names = {}

    def fake_export(*_args, **_kwargs):
        worker_names["export"] = threading.current_thread().name
        export_event.set()
        return str(tmp_path / "result.xlsx")

    def fake_summary(**_kwargs):
        worker_names["summary"] = threading.current_thread().name
        summary_event.set()
        return str(tmp_path / "summary.txt")

    monkeypatch.setattr(main, "export_result_to_excel", fake_export)
    monkeypatch.setattr(main2, "write_export_summary", fake_summary)
    monkeypatch.setattr(base, "registry_hooks", None)

    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    app.root = _ImmediateRoot()
    app.config = {"user_name": "测试用户", "simple_export_mode": False}
    app.user_roles = ["设计人员"]
    app.current_datetime = datetime.datetime(2026, 7, 27)
    app.export_path_var = _Var(str(tmp_path))
    app.path_var = _Var(str(tmp_path))
    app._manual_operation = True
    app.last_summary_written_path = None

    for file_type in range(1, 8):
        setattr(app, "process_file{}_var".format(file_type), _Var(file_type == 1))
        setattr(app, "processing_results_multi{}".format(file_type), {})
        setattr(app, "target_files{}".format(file_type), [])

    app.processing_results_multi1 = {
        "2026": pd.DataFrame([{"接口号": "TEST-001", "原始行号": 2}])
    }
    app.target_files1 = [(str(tmp_path / "source.xlsx"), "2026")]

    app._ensure_up_to_date = lambda *_args: True
    app._should_show_popup = lambda: False
    app.apply_role_based_filter = lambda data, project_id=None: data
    app.apply_auto_role_date_window = lambda data: data
    app._exclude_completed_rows = lambda data, _path: data
    app._exclude_pending_confirmation_rows = (
        lambda data, _path, _file_type, _project_id: data
    )
    app.show_export_waiting_dialog = lambda *_args: (object(), object())
    app.update_export_progress = lambda *_args: None
    app.close_waiting_dialog = lambda *_args: None
    app._post_ui_task = lambda callback: callback()

    app.export_results()

    assert export_event.wait(2)
    assert summary_event.wait(2)
    assert worker_names["export"] == "ExcelExportWorker"
    assert worker_names["summary"] == "ExportSummaryWorker"
