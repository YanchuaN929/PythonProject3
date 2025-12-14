from __future__ import annotations

import argparse
import json
import sys

from .visibility import build_debug_report, find_data_folders, infer_registry_db_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="接口可见性自动调试（registry + Excel + process模拟）")
    parser.add_argument("--data-folder", required=True, help="数据文件夹路径（包含excel源文件与registry/registry.db）")
    parser.add_argument("--registry-db", default=None, help="可选：显式指定registry.db路径（优先级最高）")
    parser.add_argument("--scan-root", default=None, help="可选：仅用ASCII路径扫描数据目录（例如 D:\\\\Programs），用于解决中文路径乱码")
    parser.add_argument("--pick", type=int, default=0, help="scan-root找到多个候选时，选择第几个（默认0）")
    parser.add_argument("--interface-id", required=True, help="接口号（可带(设计人员)后缀，会自动清洗）")
    parser.add_argument("--project-id", required=True, help="项目号（如1818）")
    parser.add_argument("--role", default="", help="当前角色字符串（如1818接口工程师）。若命令行中文乱码，可改用--engineer-project")
    parser.add_argument("--engineer-project", default=None, help="可选：直接指定接口工程师项目号（如1818），用于绕过中文role输入")
    parser.add_argument("--file-types", default="1,3,4", help="要检查的file_type列表，逗号分隔，默认1,3,4")
    parser.add_argument("--json", dest="json_out", action="store_true", help="同时输出结构化JSON到stdout末尾")
    args = parser.parse_args(argv)

    try:
        file_types = [int(x.strip()) for x in str(args.file_types).split(",") if x.strip()]
    except Exception:
        file_types = [3, 4]

    # 角色：若提供engineer_project，则构造一个标准role（内部构造，不依赖命令行中文输入）
    role = args.role or ""
    if args.engineer_project and not role:
        role = f"{str(args.engineer_project).strip()}接口工程师"

    data_folder = args.data_folder
    registry_db = args.registry_db

    # 若显式未给registry-db，先按data-folder推断
    if not registry_db:
        registry_db = infer_registry_db_path(data_folder)

    # 仍找不到时：允许用scan-root扫描（避免中文路径在命令行乱码）
    if not registry_db and args.scan_root:
        candidates = find_data_folders(args.scan_root)
        if not candidates:
            print("❌ scan-root 未找到任何包含 registry/registry.db 的数据目录")
            return 2
        if args.pick < 0 or args.pick >= len(candidates):
            print(f"❌ pick越界：共有{len(candidates)}个候选，pick={args.pick}")
            for i, c in enumerate(candidates):
                print(f"  [{i}] {c}")
            return 2
        data_folder = candidates[args.pick]
        registry_db = infer_registry_db_path(data_folder)

    report, info = build_debug_report(
        data_folder=data_folder,
        interface_id=args.interface_id,
        project_id=str(args.project_id),
        role=role,
        file_types=file_types,
        registry_db_path=registry_db,
    )
    print(report)
    if args.json_out:
        print("\n== JSON ==")
        print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


