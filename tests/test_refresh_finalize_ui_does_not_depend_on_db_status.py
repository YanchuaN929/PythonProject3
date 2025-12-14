def test_update_file_info_does_not_require_db_status():
    """
    回归测试：
    刷新收尾时即使没有 db_status 属性/实例，也必须能够更新 Excel文件信息文本。
    """
    from base import ExcelProcessorApp

    class _WM:
        def __init__(self):
            self.last = None

        def update_file_info(self, text):
            self.last = text

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.window_manager = _WM()

    # 模拟旧问题：没有 db_status 属性
    if hasattr(app, "db_status"):
        delattr(app, "db_status")

    # 调用 update_file_info（finalize_ui 现在会先调用它）
    app.update_file_info("找到 1 个Excel文件")
    assert app.window_manager.last == "找到 1 个Excel文件"


