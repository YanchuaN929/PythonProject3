import pandas as pd


def test_on_tab_changed_uses_display_results2_so_pending_cache_applies(monkeypatch):
    """
    回归：tab切换/刷新路径如果直接用 processing_results2 渲染，会绕开 PendingCache，导致“指派后责任人不更新”。
    现在应统一走 display_results2()。
    """
    from base import ExcelProcessorApp
    from write_tasks.pending_cache import PendingCache

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.pending_cache = PendingCache()
    app.user_roles = ["设计人员"]
    app.user_name = "Alice"

    # 模拟 tab2 有处理结果
    app.target_file2 = "dummy.xlsx"
    app.has_processed_results2 = True
    app.processing_results2 = pd.DataFrame(
        {
            "项目号": [1907.0],
            "原始行号": [15357],
            "责任人": [""],
            "状态": [""],
        }
    )

    # source_file 映射
    app._get_source_files_for_tab = lambda tab_name: [r"E:\p1907.xlsx"]
    app._get_project_source_file_map = lambda tab_name: {"1907": r"E:\p1907.xlsx"}

    # 预置 pending 指派覆盖
    app.pending_cache.add_assignment_entries(
        "t1",
        [
            {
                "file_type": 2,
                "file_path": r"E:\p1907.xlsx",
                "row_index": 15357,
                "assigned_name": "严鹏南",
                "assigned_by": "测试用户",
                "project_id": "1907",
                "interface_id": "IF-X",
                "status_text": "待完成",
            }
        ],
    )

    # 伪造 notebook 行为：当前选中 tab2
    class DummyNotebook:
        def select(self):
            return "tab2"

        def index(self, _):
            return 1

    app.notebook = DummyNotebook()

    # 替换 display_results2 捕获其传入的 df（它内部会应用 PendingCache）
    captured = {}

    def fake_display_results2(df, show_popup=False):
        # 复制一下，避免后续修改
        captured["df"] = df.copy()

    app.display_results2 = fake_display_results2

    # 触发 tab changed
    app.on_tab_changed(event=None)

    assert "df" in captured
    # 注意：display_results2 会在内部创建 display_df 才覆盖，我们这里只验证“走到了 display_results2”
    # 更深入的覆盖验证由 PendingCache 自身测试/集成测试承担



