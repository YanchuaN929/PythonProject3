from pathlib import Path

import base


def _make_app(tmp_path):
    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    app.config = {"user_name": "张三"}
    app.user_roles = ["设计人员"]
    app._get_account_table_path = lambda **_kwargs: str(tmp_path / "姓名角色表.xlsx")
    return app


def test_authenticate_then_switch_applies_user_only_after_success(tmp_path, monkeypatch):
    app = _make_app(tmp_path)
    applied = []
    app._handle_user_name_change = lambda name, trigger_refresh=False: applied.append(
        (name, trigger_refresh)
    )

    monkeypatch.setattr(base, "verify_account_password", lambda *_: False)
    success, message = app._authenticate_and_switch_user("李四", "wrong")
    assert success is False
    assert "密码不正确" in message
    assert applied == []

    monkeypatch.setattr(base, "verify_account_password", lambda *_: True)
    success, message = app._authenticate_and_switch_user("李四", "correct")
    assert success is True
    assert "李四" in message
    assert applied == [("李四", True)]


def test_change_password_validates_confirmation_before_write(tmp_path, monkeypatch):
    app = _make_app(tmp_path)
    writes = []
    monkeypatch.setattr(
        base,
        "change_account_password",
        lambda *args, **kwargs: writes.append((args, kwargs)),
    )

    success, message = app._change_current_account_password("old", "new-a", "new-b")
    assert success is False
    assert "不一致" in message
    assert writes == []

    success, message = app._change_current_account_password("old", "new", "new")
    assert success is True
    assert "同步" in message
    assert writes[0][0][1:] == ("张三", "old", "new")


def test_frozen_account_table_uses_shared_release_copy(tmp_path, monkeypatch):
    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    app._resolve_update_folder_path = lambda include_runtime_selection=True: str(tmp_path)
    monkeypatch.setattr(base.sys, "frozen", True, raising=False)
    monkeypatch.setattr(base, "get_role_table_file", lambda: "excel_bin/姓名角色表.xlsx")

    result = Path(app._get_account_table_path(for_write=True))

    assert result == tmp_path / "EXE" / "_internal" / "excel_bin" / "姓名角色表.xlsx"


def test_development_account_table_uses_configured_role_workbook(monkeypatch):
    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    expected = Path(base.__file__).resolve().parent / "excel_bin" / "姓名角色表.xlsx"
    monkeypatch.delattr(base.sys, "frozen", raising=False)
    monkeypatch.setattr(base, "get_role_table_file", lambda: "excel_bin/姓名角色表.xlsx")

    assert Path(app._get_account_table_path()) == expected


def test_account_combobox_accepts_keyboard_input_and_keeps_account_choices(monkeypatch):
    created = []
    sentinel = object()

    def fake_combobox(*args, **kwargs):
        created.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(base.ttk, "Combobox", fake_combobox)
    parent = object()
    textvariable = object()
    accounts = ["李子香", "曾添君"]

    result = base.ExcelProcessorApp._create_account_combobox(
        parent,
        textvariable,
        accounts,
    )

    assert result is sentinel
    assert created == [
        (
            (parent,),
            {
                "textvariable": textvariable,
                "values": accounts,
                "state": "normal",
                "width": 28,
            },
        )
    ]
