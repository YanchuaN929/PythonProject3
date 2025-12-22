import datetime as _dt

import pandas as pd


def _add_workdays(start: _dt.date, n: int) -> _dt.date:
    """向后加 n 个工作日（跳过周六周日）"""
    d = start
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining > 0:
        d = d + _dt.timedelta(days=step)
        if d.weekday() < 5:  # 0-4: Mon-Fri
            remaining -= 1
    return d


def _fmt_full_date(d: _dt.date) -> str:
    return f"{d.year}.{d.month:02d}.{d.day:02d}"


def test_director_filters_to_7_workdays_and_keeps_overdue():
    """
    室主任默认应显示：
    - 已延期（workday_diff < 0）：全部保留
    - 未来 <= 7 个工作日：保留
    - 未来 > 7 个工作日：不显示
    """
    from base import ExcelProcessorApp

    today = _dt.date.today()
    d_in_7 = _add_workdays(today, 7)
    d_in_8 = _add_workdays(today, 8)
    d_overdue = today - _dt.timedelta(days=10)

    df = pd.DataFrame(
        {
            "原始行号": [1, 2, 3],
            "科室": ["结构一室", "结构一室", "结构一室"],
            "责任人": ["A", "B", "C"],
            "接口时间": [_fmt_full_date(d_in_7), _fmt_full_date(d_in_8), _fmt_full_date(d_overdue)],
        }
    )

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.user_name = "张三"
    app.config = {"role_export_days": {"一室主任": 7}}

    out = app._filter_by_single_role(df, "一室主任", project_id="1818")

    # 7个工作日内保留、8个工作日剔除、延期保留
    assert len(out) == 2
    assert _fmt_full_date(d_in_7) in set(out["接口时间"])
    assert _fmt_full_date(d_in_8) not in set(out["接口时间"])
    assert _fmt_full_date(d_overdue) in set(out["接口时间"])


def test_multi_role_admin_does_not_expand_director_window():
    """
    回归：当用户_roles 同时包含“管理员”和“室主任”时，不应因为管理员“不过滤”而扩大显示范围。
    """
    from base import ExcelProcessorApp

    today = _dt.date.today()
    d_in_7 = _add_workdays(today, 7)
    d_in_8 = _add_workdays(today, 8)

    df = pd.DataFrame(
        {
            "原始行号": [1, 2],
            "科室": ["结构一室", "结构一室"],
            "责任人": ["A", "B"],
            "接口时间": [_fmt_full_date(d_in_7), _fmt_full_date(d_in_8)],
        }
    )

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.user_name = "张三"
    app.user_roles = ["一室主任", "管理员"]
    app.config = {"role_export_days": {"一室主任": 7}}

    out = app.apply_role_based_filter(df, project_id="1818")
    assert _fmt_full_date(d_in_7) in set(out["接口时间"])
    assert _fmt_full_date(d_in_8) not in set(out["接口时间"])


