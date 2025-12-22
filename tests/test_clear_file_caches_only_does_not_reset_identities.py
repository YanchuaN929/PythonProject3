import hashlib
import os
from pathlib import Path


def test_clear_file_caches_only_can_target_files_and_keeps_identities(tmp_path):
    from file_manager import FileIdentityManager

    cache_file = tmp_path / "file_cache.json"
    result_cache_dir = tmp_path / "result_cache"
    result_cache_dir.mkdir()

    mgr = FileIdentityManager(cache_file=str(cache_file), result_cache_dir=str(result_cache_dir))

    f1 = tmp_path / "a.xlsx"
    f2 = tmp_path / "b.xlsx"
    f1.write_text("x", encoding="utf-8")
    f2.write_text("y", encoding="utf-8")

    h1 = hashlib.md5(os.path.abspath(str(f1)).encode("utf-8")).hexdigest()[:8]
    h2 = hashlib.md5(os.path.abspath(str(f2)).encode("utf-8")).hexdigest()[:8]

    # 创建两份 .pkl 缓存文件，模拟不同项目/类型
    p1 = result_cache_dir / f"{h1}_1907_file1.pkl"
    p2 = result_cache_dir / f"{h2}_1907_file1.pkl"
    p1.write_bytes(b"1")
    p2.write_bytes(b"2")

    # 预置 identities
    mgr.file_identities = {str(f1): "id1", str(f2): "id2"}

    ok = mgr.clear_file_caches_only([str(f1)])
    assert ok is True

    assert not p1.exists()
    assert p2.exists()
    # identities 不应被清空
    assert mgr.file_identities == {str(f1): "id1", str(f2): "id2"}


