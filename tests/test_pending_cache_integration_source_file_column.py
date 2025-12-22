import pandas as pd


def test_base_ensures_source_file_column_for_pending_cache_and_overrides_apply():
    """
    回归：处理结果 DataFrame 没有 source_file 列时，PendingCache 覆盖无法命中，导致“指派后不实时”。
    base.py 应在显示前补齐 source_file 列，从而让 PendingCache 能覆盖“责任人/状态”。
    """
    from write_tasks.pending_cache import PendingCache
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)  # 跳过 __init__（避免 Tk/配置加载）
    app.pending_cache = PendingCache()
    app.user_roles = ["设计人员"]
    app.user_name = "Alice"

    # stub：给出 tab 对应的默认源文件与项目映射
    app._get_source_files_for_tab = lambda tab_name: [r"\\server\share\a.xlsx"]
    app._get_project_source_file_map = lambda tab_name: {"1907": r"\\server\share\a.xlsx"}

    # 模拟：处理结果没有 source_file 列
    df = pd.DataFrame(
        {
            "项目号": ["1907"],
            "原始行号": [5013],
            "责任人": [""],
            "状态": ["请指派"],
        }
    )

    # 写入一条 pending 指派覆盖（file_path 为全路径）
    app.pending_cache.add_assignment_entries(
        "t1",
        [
            {
                "file_type": 2,
                "file_path": r"\\server\share\a.xlsx",
                "row_index": 5013,
                "assigned_name": "严鹏南",
                "assigned_by": "测试用户",
                "project_id": "1907",
                "interface_id": "IF-X",
                "status_text": "待完成",
            }
        ],
    )

    ensured = app._ensure_source_file_column_for_pending_cache(df, "内部需回复接口")
    assert "source_file" in ensured.columns

    overridden = app._apply_pending_overrides(ensured, 2)
    assert overridden.loc[0, "责任人"] == "严鹏南"
    assert "待完成" in str(overridden.loc[0, "状态"])


