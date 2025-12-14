class _FakeRoot:
    def __init__(self):
        self.scheduled = []

    def after(self, _ms, func):
        # 记录但不自动执行（由测试手动调用）
        self.scheduled.append(func)


class _FakeWindowManager:
    def __init__(self):
        self.last_text = None

    def update_file_info(self, text):
        self.last_text = text


def test_ui_task_queue_drains_tasks():
    """
    验证：后台线程入队的UI任务，能被主线程 drain 执行。
    这是刷新结束更新“Excel文件信息”的关键机制。
    """
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.root = _FakeRoot()
    app.window_manager = _FakeWindowManager()

    # 初始化队列（会调用 root.after 调度 drain）
    app._ui_task_queue = None
    app._init_ui_task_queue()

    # 入队一个“更新文件信息”的任务
    app._post_ui_task(lambda: app.update_file_info("hello"))

    # 主线程执行一次 drain
    app._drain_ui_tasks()

    assert app.window_manager.last_text == "hello"


