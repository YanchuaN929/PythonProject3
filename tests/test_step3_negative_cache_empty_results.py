import os
import tempfile

import pandas as pd


def test_step3_process_with_cache_persists_empty_dataframe():
    """
    Step3回归：允许缓存空结果（负缓存）。
    - 第一次：process_func 返回空 df，应写入 .pkl
    - 第二次：应从 .pkl 命中返回空 df（不再调用 process_func）
    """
    from base import ExcelProcessorApp
    from file_manager import FileIdentityManager

    tmpdir = tempfile.mkdtemp()
    try:
        cache_file = os.path.join(tmpdir, "cache.json")
        result_cache_dir = os.path.join(tmpdir, "result_cache")
        fm = FileIdentityManager(cache_file=cache_file, result_cache_dir=result_cache_dir)

        # 创建一个“源文件”用于 identity
        src = os.path.join(tmpdir, "src.xlsx")
        with open(src, "w", encoding="utf-8") as f:
            f.write("v1")
        fm.update_file_identities([src])

        app = ExcelProcessorApp.__new__(ExcelProcessorApp)
        app.file_manager = fm
        app._should_show_popup = lambda: False

        calls = {"n": 0}

        def process_func(_file_path, *_args):
            calls["n"] += 1
            return pd.DataFrame()  # 空结果

        # 第一次：缓存未命中，执行处理并缓存空 df
        out1 = app._process_with_cache(src, "2016", "file1", process_func)
        assert calls["n"] == 1
        assert out1 is not None and out1.empty

        cache_path = fm._get_cache_filename(src, "2016", "file1")
        assert os.path.exists(cache_path), "空结果也应生成 .pkl（负缓存）"

        # 第二次：应命中缓存，不再调用 process_func
        out2 = app._process_with_cache(src, "2016", "file1", process_func)
        assert calls["n"] == 1, "第二次应直接命中缓存（不再执行处理函数）"
        assert out2 is not None and out2.empty
    finally:
        try:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass



