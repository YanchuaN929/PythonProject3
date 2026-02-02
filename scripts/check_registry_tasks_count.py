"""
只读诊断脚本：统计 Registry(tasks) 数量，验证是否存在“被清空/覆盖写入”等异常。

用法（PowerShell 示例）：
  python scripts/check_registry_tasks_count.py --data-folder "E:\\program\\接口筛选\\测试文件"

输出：
  - db_path（实际连接的 registry.db）
  - tasks_count（总任务数）
  - 按 file_type 的数量分布（便于观察是否异常归零）
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Check registry tasks count (read-only).")
    parser.add_argument(
        "--data-folder",
        required=True,
        help="数据目录（公共盘或本地平替目录），如 E:\\program\\接口筛选\\测试文件 或 //10.102.2.7/... ",
    )
    args = parser.parse_args()

    data_folder = (args.data_folder or "").strip()

    import registry.hooks as registry_hooks
    from registry.config import load_config
    from registry.db import get_connection, close_connection_after_use

    registry_hooks.set_data_folder(data_folder)
    cfg = load_config(data_folder=data_folder, ensure_registry_dir=True)
    db_path = cfg.get("registry_db_path", "")
    wal = bool(cfg.get("registry_wal", False))

    conn = get_connection(db_path, wal)
    try:
        # 确保 tasks 表存在（正常情况下 init_db 会创建）
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if not row:
            print(f"db_path={db_path}")
            print("tasks_table_exists=False")
            print("tasks_count=0")
            return 0

        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        print(f"db_path={db_path}")
        print("tasks_table_exists=True")
        print(f"tasks_count={int(total)}")

        # file_type 分布
        rows = conn.execute(
            "SELECT file_type, COUNT(*) AS c FROM tasks GROUP BY file_type ORDER BY file_type"
        ).fetchall()
        if rows:
            print("by_file_type=" + ", ".join([f"{r[0]}:{r[1]}" for r in rows]))
        else:
            print("by_file_type=(empty)")

        return 0
    finally:
        close_connection_after_use()


if __name__ == "__main__":
    raise SystemExit(main())


