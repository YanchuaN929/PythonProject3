import pandas as pd


def test_tab1_on_tab_changed_uses_display_results_not_filter_and_display():
    import base

    app = base.ExcelProcessorApp.__new__(base.ExcelProcessorApp)

    # notebook: 当前选中 tab0
    class _NB:
        def select(self):
            return 0

        def index(self, tab_id):
            return int(tab_id)

    app.notebook = _NB()

    # 必要条件：tab1 且 target_file1 存在
    app.target_file1 = "dummy.xlsx"
    app.has_processed_results1 = True
    app.processing_results = pd.DataFrame({"原始行号": [2], "接口号": ["X"]})

    # spy
    calls = {"display_results": 0, "filter_and_display_results": 0}

    def _display_results(_df, show_popup=True):
        calls["display_results"] += 1

    def _filter_and_display_results(_df):
        calls["filter_and_display_results"] += 1

    app.display_results = _display_results
    app.filter_and_display_results = _filter_and_display_results

    app.on_tab_changed(event=None)

    assert calls["display_results"] == 1
    assert calls["filter_and_display_results"] == 0


