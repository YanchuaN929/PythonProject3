import types


class _NotebookStub:
    def __init__(self, app):
        self._app = app
        self._selected = 0

    def select(self, tab_id=None):
        # getter
        if tab_id is None:
            return self._selected
        # setter
        self._selected = tab_id
        # 模拟 ttk.Notebook.select 触发的 tab-changed 回调（用于验证“抑制渲染”是否生效）
        if not getattr(self._app, "_suppress_tab_change_render", False):
            self._app.on_tab_changed(None)
        return self._selected

    def index(self, tab_id):
        # 真实 ttk 里 tab_id 可能是字符串；这里测试用 int 即可
        return int(tab_id)


def test_post_processing_select_and_render_active_tab_renders_once():
    import base

    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)
    calls = {"on_tab_changed": 0}

    def _on_tab_changed(_event=None):
        calls["on_tab_changed"] += 1

    app.on_tab_changed = _on_tab_changed
    app._suppress_tab_change_render = False
    app.notebook = _NotebookStub(app)

    # 执行：应当仅渲染一次（选择 tab 时由于 suppress，不应触发；随后显式渲染 1 次）
    app._post_processing_select_and_render_active_tab(2)

    assert calls["on_tab_changed"] == 1


