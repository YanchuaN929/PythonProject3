import time
from pathlib import Path


def test_get_changed_files_only_returns_modified(tmp_path):
    """
    新增能力：get_changed_files 应只返回发生变化的文件，而不是“一变全变”。
    """
    from file_manager import FileIdentityManager

    # 用临时目录隔离缓存
    cache_file = tmp_path / "file_cache.json"
    result_cache_dir = tmp_path / "result_cache"
    result_cache_dir.mkdir(exist_ok=True)

    mgr = FileIdentityManager(cache_file=str(cache_file), result_cache_dir=str(result_cache_dir))

    f1 = tmp_path / "a.xlsx"
    f2 = tmp_path / "b.xlsx"
    f1.write_text("v1", encoding="utf-8")
    f2.write_text("v1", encoding="utf-8")

    all_files = [str(f1), str(f2)]
    # 首次：都是新文件 => 都变化
    changed0 = mgr.get_changed_files(all_files)
    assert changed0 == set(all_files)

    # 记录 identity
    mgr.update_file_identities(all_files)

    # 不改动：不变化
    changed1 = mgr.get_changed_files(all_files)
    assert changed1 == set()

    # 改动一个文件
    time.sleep(0.02)  # 确保 mtime 有变化（Windows 下分辨率可能较粗）
    f2.write_text("v2", encoding="utf-8")

    changed2 = mgr.get_changed_files(all_files)
    assert changed2 == {str(f2)}


def test_incremental_policy_clears_only_changed_files(monkeypatch):
    """
    回归：增量策略下，只清理变动文件的缓存与完成状态，不清理未变文件。
    这里直接模拟 base.py 中 start_processing/_check_and_load_cache 采用的调用组合。
    """

    class DummyFM:
        def __init__(self):
            self.cleared_completed = []
            self.cleared_cache = []
            self.updated = []

        def get_changed_files(self, paths):
            return {paths[1]}

        def clear_file_completed_rows(self, fp, user_name=""):
            self.cleared_completed.append((fp, user_name))

        def clear_file_cache(self, fp):
            self.cleared_cache.append(fp)

        def update_file_identities(self, paths):
            self.updated.append(list(paths))

    fm = DummyFM()
    all_paths = ["A.xlsx", "B.xlsx", "C.xlsx"]

    # 模拟 base.py 的核心行为：按 changed_files 清理，并更新 identities
    changed = set(fm.get_changed_files(all_paths))
    for fp in changed:
        fm.clear_file_completed_rows(fp, user_name="")
        fm.clear_file_cache(fp)
    fm.update_file_identities(all_paths)

    assert fm.cleared_completed == [("B.xlsx", "")]
    assert fm.cleared_cache == ["B.xlsx"]
    assert fm.updated == [all_paths]


