"""
只读诊断脚本：按“界面某一行”的关键信息，精确验证 Registry task_id 是否命中、状态是什么。

用法（PowerShell 示例）：
  python scripts/check_registry_task_lookup.py ^
    --data-folder "E:\\program\\接口筛选\\测试文件" ^
    --file-type 1 --project-id 1818 ^
    --interface-id "S-XXXX" ^
    --source-file "1818按项目导出IDI手册2025-12-03-09_31_29.xlsx" ^
    --row-index 7 ^
    --interface-time "2025.12.25" ^
    --user-roles "管理员"

说明：
  - source_file 只需要 basename（文件名）即可，和 make_task_id 的口径一致
  - 该脚本不会写 DB，仅查询
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookup one registry task by computed task_id (read-only).")
    parser.add_argument("--data-folder", required=True, help="数据目录（公共盘或本地平替目录）")
    parser.add_argument("--file-type", required=True, type=int, choices=[1, 2, 3, 4, 5, 6], help="文件类型 1-6")
    parser.add_argument("--project-id", required=True, help="项目号（如 1818）")
    parser.add_argument("--interface-id", required=True, help="接口号（界面显示的接口号，最好不要带(角色)后缀）")
    parser.add_argument("--source-file", required=True, help="源文件 basename（如 xxx.xlsx）")
    parser.add_argument("--row-index", required=True, type=int, help="原始行号（界面“行号”列）")
    parser.add_argument("--interface-time", default="", help="接口时间（用于 get_display_status 的延期判断，可空）")
    parser.add_argument("--user-roles", default="", help="用户角色逗号分隔（如 管理员,一室主任），可空")
    args = parser.parse_args()

    data_folder = (args.data_folder or "").strip()

    import registry.hooks as registry_hooks
    from registry.config import load_config
    from registry.db import get_connection, close_connection_after_use
    from registry.util import make_task_id

    registry_hooks.set_data_folder(data_folder)
    cfg = load_config(data_folder=data_folder, ensure_registry_dir=True)
    db_path = cfg.get("registry_db_path", "")
    wal = bool(cfg.get("registry_wal", False))

    tid = make_task_id(
        args.file_type,
        str(args.project_id),
        str(args.interface_id),
        str(args.source_file),
        int(args.row_index),
    )

    conn = get_connection(db_path, wal)
    try:
        row = conn.execute(
            "SELECT status, display_status, assigned_by, role, confirmed_at, responsible_person, ignored "
            "FROM tasks WHERE id = ?",
            (tid,),
        ).fetchone()
    finally:
        close_connection_after_use()

    print(f"db_path={db_path}")
    print(f"task_id={tid}")
    print(f"row_exists={bool(row)}")
    print(f"db_row={row}")

    # 同时走一遍 hooks.get_display_status，验证“查询层”是否能拿到 display_status
    task_key = {
        "file_type": args.file_type,
        "project_id": str(args.project_id),
        "interface_id": str(args.interface_id),
        "source_file": str(args.source_file),
        "row_index": int(args.row_index),
        "interface_time": (args.interface_time or ""),
    }
    user_roles_str = (args.user_roles or "").strip()
    status_map = registry_hooks.get_display_status([task_key], user_roles_str)
    print(f"hooks_status_map_has_tid={tid in status_map}")
    print(f"hooks_display_status={status_map.get(tid, None)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


