import os

import pandas as pd


def test_process_with_cache_invalidates_stale_cache_missing_responsible(tmp_path):
    """
    回归：若命中旧 .pkl 缓存但缺少“责任人”列，UI会把责任人全显示为“无”。
    期望：_process_with_cache 视为缓存不兼容，清理该文件缓存并触发一次重算，返回结果必须包含“责任人”列。
    """
    from base import ExcelProcessorApp
    from file_manager import FileIdentityManager

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app._should_show_popup = lambda: False

    result_cache_dir = tmp_path / "result_cache"
    result_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = tmp_path / "file_cache.json"

    fm = FileIdentityManager(cache_file=str(cache_file), result_cache_dir=str(result_cache_dir))
    app.file_manager = fm

    src = tmp_path / "src.xlsx"
    src.write_text("dummy", encoding="utf-8")

    # 先写入一个“旧缓存”（缺少责任人列）
    stale = pd.DataFrame({"原始行号": [2, 3], "接口时间": ["2025.12.01", "2025.12.02"]})
    assert fm.save_cached_result(str(src), "1907", "file1", stale)
    assert fm.load_cached_result(str(src), "1907", "file1") is not None

    # 处理函数返回包含责任人列的新结果
    called = {"n": 0}

    def process_func(file_path, *args):
        called["n"] += 1
        return pd.DataFrame(
            {
                "原始行号": [2, 3],
                "接口时间": ["2025.12.01", "2025.12.02"],
                "责任人": ["张三", "李四"],
            }
        )

    out = app._process_with_cache(str(src), "1907", "file1", process_func)
    assert isinstance(out, pd.DataFrame)
    assert "责任人" in out.columns
    assert called["n"] == 1, "旧缓存不兼容时应触发一次重算"

    # 缓存应已被覆盖为新结构（包含责任人）
    cached2 = fm.load_cached_result(str(src), "1907", "file1")
    assert cached2 is not None
    assert "责任人" in cached2.columns


