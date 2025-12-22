import pandas as pd

from write_tasks.pending_cache import PendingCache


def test_pending_cache_matches_dataframe_basename_source_file():
    """
    现场复现点：
    - 指派 payload 里 file_path 往往是全路径（UNC/本地）
    - UI DataFrame 的 source_file 可能只存文件名（basename）
    若 key 只按 full path，会导致覆盖不命中，从而“指派后仍显示未指派/不实时”。
    """
    cache = PendingCache()
    cache.add_assignment_entries(
        "task-x",
        [
            {
                "file_path": r"\\10.102.2.7\文件服务器\建筑结构所\接口文件\各项目内外部接口手册\A.xlsx",
                "row_index": 10,
                "file_type": 1,
                "assigned_name": "张三",
                "assigned_by": "李经理",
            }
        ],
    )

    df = pd.DataFrame(
        {
            "source_file": ["A.xlsx"],  # 注意：只存 basename
            "原始行号": [10],
            "责任人": [""],
            "状态": [""],
        }
    )

    overridden = cache.apply_overrides_to_dataframe(df, 1, ["设计人员"], "")
    assert overridden.loc[0, "责任人"] == "张三"


