def test_refresh_current_tab_display_delegates_to_on_tab_changed():
    import base

    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    app._suppress_tab_change_render = False

    calls = {"on_tab_changed": 0}

    def _on_tab_changed(_event=None):
        calls["on_tab_changed"] += 1

    app.on_tab_changed = _on_tab_changed

    app.refresh_current_tab_display()

    assert calls["on_tab_changed"] == 1


