import pandas as pd


def test_ensure_source_file_column_normalizes_float_project_id_for_mapping():
    """
    回归：项目号在 DataFrame 中可能是 float(1907.0)，str(x) 会变成 '1907.0'，
    导致 project_source_map['1907'] 命中失败，从而 source_file 填错，PendingCache key 无法命中。
    """
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app._get_source_files_for_tab = lambda tab_name: [r"E:\a.xlsx"]
    app._get_project_source_file_map = lambda tab_name: {"1907": r"E:\p1907.xlsx"}

    df = pd.DataFrame({"项目号": [1907.0], "原始行号": [4573], "责任人": ["无"]})
    out = app._ensure_source_file_column_for_pending_cache(df, "内部需回复接口")
    assert out.loc[0, "source_file"] == r"E:\p1907.xlsx"


