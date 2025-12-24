import pandas as pd


def test_step2_refresh_cache_reuse_rules():
    """
    Step2回归：start_processing 允许复用 refresh 阶段“已加载到内存的 raw 缓存结果”，但必须满足：
    - all_file_paths 快照匹配
    - file_path 不在 changed_files
    否则返回 None，退回到读 .pkl / 重新处理。
    """
    from base import ExcelProcessorApp

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)

    fp = r"\\server\share\p2016.xlsx"
    all_paths = [fp]
    pid = "2016"

    raw_df = pd.DataFrame({"接口号": ["X"], "项目号": [pid]})

    app._cache_loaded_snapshot = {"all_file_paths": tuple(sorted(all_paths))}
    app._cache_loaded_raw_multi1 = {pid: raw_df}

    # 1) 未变化 + 快照匹配 => 命中
    got = app._get_refresh_cached_raw_df(
        file_type=1,
        file_path=fp,
        project_id=pid,
        all_file_paths=all_paths,
        changed_files=set(),
    )
    assert got is raw_df

    # 2) 文件变化 => 不命中
    got2 = app._get_refresh_cached_raw_df(
        file_type=1,
        file_path=fp,
        project_id=pid,
        all_file_paths=all_paths,
        changed_files={fp},
    )
    assert got2 is None

    # 3) 快照不匹配 => 不命中
    got3 = app._get_refresh_cached_raw_df(
        file_type=1,
        file_path=fp,
        project_id=pid,
        all_file_paths=[fp, r"C:\other.xlsx"],
        changed_files=set(),
    )
    assert got3 is None


