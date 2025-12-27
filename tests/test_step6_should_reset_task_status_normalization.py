from registry.service import should_reset_task_status


def test_should_not_reset_when_only_format_diff_and_mmdd_can_be_year_completed():
    # 旧：只有月日；新：带年份。应视为同一天（不重置）
    assert should_reset_task_status("12.03", "2025-12-03", "", "") is False


def test_should_reset_when_date_really_changed():
    assert should_reset_task_status("2025-12-03", "2025-12-04", "", "") is True


def test_should_not_treat_non_date_like_25c2_as_mmdd():
    # "25C2" 不应被解析为 2025-25-02 之类的日期
    assert should_reset_task_status("25C2", "25C2", "", "") is False


