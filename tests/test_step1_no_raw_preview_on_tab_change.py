import pandas as pd


def test_step1_on_tab_changed_unprocessed_does_not_load_or_preview_excel(monkeypatch):
    """
    Step1回归：已确认“删除预加载/删除未处理原始预览”，因此 tab 切换到未处理页时：
    - 不应调用 load_file_to_viewer（避免读Excel）
    - 不应调用 display_excel_data（避免原始预览渲染）
    - 应显示“请点击开始处理生成结果”提示
    """
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)

    # 伪造 notebook：当前选中 tab2（内部需回复接口）
    class DummyNotebook:
        def select(self):
            return "tab2"

        def index(self, _):
            return 1

    app.notebook = DummyNotebook()

    # 必要字段：满足 on_tab_changed 的分支条件
    app.target_file2 = "dummy.xlsx"
    app.has_processed_results2 = False
    app.processing_results2 = pd.DataFrame()

    # 即便存在 file2_data，也不应走原始预览
    app.file2_data = pd.DataFrame({"col": [1]})

    # viewer 占位
    app.tab2_viewer = object()

    # 若被调用则直接失败
    def _boom(*_a, **_kw):
        raise AssertionError("Step1：不应在未处理状态触发Excel读取/原始预览")

    app.load_file_to_viewer = _boom
    app.display_excel_data = _boom

    captured = {}

    def fake_show_empty_message(viewer, message):
        captured["viewer"] = viewer
        captured["message"] = message

    app.show_empty_message = fake_show_empty_message

    # 执行
    app.on_tab_changed(event=None)

    assert captured.get("viewer") is app.tab2_viewer
    assert "请点击开始处理生成结果" in str(captured.get("message", ""))


