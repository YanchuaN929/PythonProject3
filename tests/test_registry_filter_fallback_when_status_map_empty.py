import pandas as pd


def test_registry_filter_fallback_when_status_map_empty(monkeypatch):
    """
    回归：当 Registry 返回空 status_map（例如新库/路径变化/未初始化）时，
    不应把所有行当作“无状态”过滤掉，应该降级为不过滤（仅保留超期过滤）。
    """
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.config = {"auto_hide_overdue_enabled": False}
    app.user_roles = ["管理员"]

    # 伪造 registry_hooks.get_display_status -> {}
    import registry.hooks as registry_hooks

    monkeypatch.setattr(registry_hooks, "get_display_status", lambda task_keys, current_user_roles_str=None: {})

    df = pd.DataFrame(
        {
            "接口号": ["A", "B", "C"],
            "原始行号": [2, 3, 4],
            "项目号": ["1818", "1818", "1818"],
            "接口时间": ["01-01", "01-02", "01-03"],
        }
    )

    out = app._exclude_pending_confirmation_rows(
        df=df,
        source_file="X.xlsx",
        file_type=1,
        project_id="1818",
        project_source_map={"1818": "X.xlsx"},
    )

    assert out is not None
    assert len(out) == 3, "status_map为空时不应把所有行过滤掉"



