import inspect

import base
from ui.window import WindowManager


def test_primary_toolbar_only_uses_settings_as_account_management_entry():
    primary_toolbar_source = inspect.getsource(WindowManager.create_path_section)
    settings_source = inspect.getsource(base.ExcelProcessorApp.show_settings_menu)

    assert "on_account_management" not in primary_toolbar_source
    assert "账户管理 ·" not in primary_toolbar_source
    assert "on_settings_menu" in primary_toolbar_source
    assert "self.show_account_management()" in settings_source
