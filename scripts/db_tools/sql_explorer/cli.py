"""CLI and wizard entry for SQL Explorer."""

from __future__ import annotations

import argparse
import json
import traceback
from typing import Any, Dict, List, Optional

from .config_store import (
    ConnectionProfile,
    clear_profile,
    create_run_output_dir,
    ensure_output_root,
    get_profile_path,
    load_profile,
    merge_profile,
    save_profile,
)
from .connect import connect_sql_server, run_connect_test
from .discovery import discover_candidates
from .report import build_markdown_report, flatten_candidates_for_csv, write_csv, write_json
from .roster import load_roster_names, validate_owner_values
from .sampling import sample_table
from .schema import scan_schema_snapshot
from .template_spec import load_template_spec


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""

    parser = argparse.ArgumentParser(
        description="SQL Explorer（支持双击向导与CLI）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    _add_common_args(parser)

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="执行完整探索流程")
    _add_common_args(run_parser)
    run_parser.add_argument("--top", type=int, default=200, help="每表采样行数")
    run_parser.add_argument("--table-limit", type=int, default=80, help="最大采样表数量")
    run_parser.add_argument("--candidate-top", type=int, default=5, help="每类输出候选数量")
    run_parser.add_argument("--include-views", action="store_true", help="包含视图")
    run_parser.add_argument("--schema", action="append", default=None, help="仅扫描指定schema")

    connect_parser = subparsers.add_parser("connect-test", help="连接测试")
    _add_common_args(connect_parser)

    schema_parser = subparsers.add_parser("schema", help="仅导出Schema")
    _add_common_args(schema_parser)
    schema_parser.add_argument("--include-views", action="store_true", help="包含视图")
    schema_parser.add_argument("--schema", action="append", default=None, help="仅扫描指定schema")

    sample_parser = subparsers.add_parser("sample", help="采样单表")
    _add_common_args(sample_parser)
    sample_parser.add_argument("--table", required=True, help="表名，格式 schema.table")
    sample_parser.add_argument("--top", type=int, default=50, help="采样行数")
    sample_parser.add_argument("--where", default=None, help="where 条件（可选）")

    return parser


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Attach common connection/output arguments."""

    parser.add_argument("--host", help="SQL Server 主机/IP")
    parser.add_argument("--port", type=int, default=None, help="SQL Server 端口")
    parser.add_argument("--database", help="数据库名")
    parser.add_argument("--username", help="用户名")
    parser.add_argument("--password", help="密码")
    parser.add_argument(
        "--driver-preference",
        default=None,
        choices=["auto", "pymssql", "pyodbc"],
        help="连接器偏好",
    )
    parser.add_argument("--use-saved-profile", action="store_true", help="优先使用本地保存连接")
    parser.add_argument("--save-profile", action="store_true", help="保存连接到本地用户目录")
    parser.add_argument("--clear-profile", action="store_true", help="清空本地保存连接")
    parser.add_argument("--output-root", default=None, help="输出根目录")
    parser.add_argument("--roster-file", default=None, help="指定姓名角色表路径")
    parser.add_argument("--no-wizard", action="store_true", help="无参数时禁用向导")


def _prompt_with_tk(existing: Optional[ConnectionProfile]) -> Optional[ConnectionProfile]:
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()

    defaults = existing or ConnectionProfile()
    messagebox.showinfo(
        "SQL Explorer",
        "首次运行请填写 SQL Server 连接信息。\n"
        "信息将保存到本机用户目录，后续可直接复用。",
    )

    host = simpledialog.askstring("连接信息", "主机/IP:", initialvalue=defaults.host)
    if host is None:
        return None
    database = simpledialog.askstring(
        "连接信息", "数据库名:", initialvalue=defaults.database or "master"
    )
    if database is None:
        return None
    username = simpledialog.askstring("连接信息", "用户名:", initialvalue=defaults.username)
    if username is None:
        return None
    password = simpledialog.askstring(
        "连接信息", "密码:", initialvalue=defaults.password, show="*"
    )
    if password is None:
        return None

    profile = ConnectionProfile(
        host=host.strip(),
        port=defaults.port or 1433,
        database=(database.strip() or "master"),
        username=username.strip(),
        password=password,
        driver_preference="auto",
        encrypt=False,
        trust_server_certificate=True,
    )
    return profile


def _prompt_with_console(existing: Optional[ConnectionProfile]) -> Optional[ConnectionProfile]:
    defaults = existing or ConnectionProfile()
    print("SQL Explorer 首次向导，请输入连接信息（直接回车可使用默认值）")
    try:
        host = input(f"主机/IP [{defaults.host}]: ").strip() or defaults.host
        if not host:
            print("未输入主机，已取消。")
            return None
        database = (
            input(f"数据库名 [{defaults.database or 'master'}]: ").strip()
            or defaults.database
            or "master"
        )
        username = input(f"用户名 [{defaults.username}]: ").strip() or defaults.username
        if not username:
            print("未输入用户名，已取消。")
            return None
        password = input("密码 [已隐藏，输入后回车]: ").strip() or defaults.password
        if not password:
            print("未输入密码，已取消。")
            return None
    except KeyboardInterrupt:
        print("\n已取消。")
        return None

    return ConnectionProfile(
        host=host,
        port=defaults.port or 1433,
        database=database,
        username=username,
        password=password,
        driver_preference="auto",
        encrypt=False,
        trust_server_certificate=True,
    )


def prompt_profile(existing: Optional[ConnectionProfile]) -> Optional[ConnectionProfile]:
    """Prompt profile by GUI then fallback to console."""

    profile = _prompt_with_tk(existing)
    if profile is not None:
        return profile
    return _prompt_with_console(existing)


def resolve_profile(args: argparse.Namespace) -> Optional[ConnectionProfile]:
    """Resolve profile from saved+cli options."""

    if args.clear_profile:
        clear_profile()
        print(f"已清空本地连接配置: {get_profile_path()}")
        return None

    saved = load_profile() if args.use_saved_profile or True else None
    overrides: Dict[str, Any] = {
        "host": args.host,
        "port": args.port,
        "database": args.database,
        "username": args.username,
        "password": args.password,
        "driver_preference": args.driver_preference,
    }
    profile = merge_profile(saved, overrides)

    if not profile.host or not profile.username or not profile.password:
        return None

    if args.save_profile:
        target = save_profile(profile)
        print(f"已保存连接配置: {target}")

    return profile


def run_full_pipeline(args: argparse.Namespace, profile: ConnectionProfile) -> int:
    """Run full exploration pipeline."""

    run_dir = create_run_output_dir(args.output_root)
    diagnostics_path = run_dir / "run_diagnostics.txt"
    diagnostics_lines: List[str] = []

    def diag(message: str) -> None:
        diagnostics_lines.append(message)
        print(message)

    diag(f"[INFO] 输出目录: {run_dir}")
    diag(f"[INFO] 连接目标: {profile.host}:{profile.port}/{profile.database}")

    test_result = run_connect_test(profile)
    if not test_result.success:
        diag(f"[ERROR] 连接测试失败: {test_result.message}")
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        return 2
    diag(f"[OK] 连接测试成功，连接器: {test_result.connector}")

    conn = None
    try:
        conn, connector = connect_sql_server(profile)
        schema_snapshot = scan_schema_snapshot(
            conn,
            include_views=bool(getattr(args, "include_views", False)),
            schema_whitelist=getattr(args, "schema", None),
        )
        diag(f"[INFO] Schema 扫描完成，表数量: {schema_snapshot.get('table_count', 0)}")

        tables = schema_snapshot.get("tables", [])
        table_limit = max(1, int(getattr(args, "table_limit", 80)))
        top_n = max(20, int(getattr(args, "top", 200)))
        sampled_tables: List[Dict[str, Any]] = []

        for table_item in tables[:table_limit]:
            table_ref = f"{table_item['schema']}.{table_item['table']}"
            try:
                sampled = sample_table(conn, table_ref, top_n=top_n, where_clause=None)
                sampled_tables.append(sampled)
            except Exception as exc:
                diag(f"[WARN] 采样失败 {table_ref}: {exc}")

        diag(f"[INFO] 采样完成，成功采样表数: {len(sampled_tables)}")

        roster_names = load_roster_names(args.roster_file)
        diag(f"[INFO] 姓名角色表加载人数: {len(roster_names)}")
        template_spec = load_template_spec()
        if template_spec:
            diag(
                f"[INFO] 模板规范已加载: version={template_spec.get('version', 'unknown')}"
            )
        else:
            diag("[WARN] 未加载到 example/template_spec.json，将仅输出候选结果")

        discovery_result = discover_candidates(
            sampled_tables,
            roster_names=roster_names,
            top_n=max(3, int(getattr(args, "candidate_top", 5))),
        )

        quality_rows: List[Dict[str, Any]] = []
        for candidate in discovery_result.get("global_owner_candidates", [])[:10]:
            table_ref = candidate.get("table_ref")
            col = candidate.get("column")
            table_match = next(
                (item for item in sampled_tables if item.get("table_ref") == table_ref), None
            )
            if not table_match:
                continue
            values = [record.get(col) for record in table_match.get("records", [])]
            quality = validate_owner_values(values, roster_names)
            quality_rows.append(
                {
                    "table_ref": table_ref,
                    "column": col,
                    **quality,
                }
            )

        report_payload = {
            "metadata": {
                "host": profile.host,
                "database": profile.database,
                "connector": connector,
                "table_limit": table_limit,
                "sample_top_n": top_n,
            },
            "connect_test": {
                "success": test_result.success,
                "connector": test_result.connector,
                "message": test_result.message,
                "details": test_result.details,
            },
            "schema_snapshot": schema_snapshot,
            "discovery_result": discovery_result,
            "quality_result": quality_rows,
            "template_spec": template_spec,
        }

        write_json(run_dir / "mapping_report.json", report_payload)
        write_json(run_dir / "schema_snapshot.json", schema_snapshot)
        write_json(run_dir / "discovery_result.json", discovery_result)

        candidate_rows = flatten_candidates_for_csv(discovery_result)
        write_csv(
            run_dir / "candidate_columns.csv",
            candidate_rows,
            headers=["file_type", "category", "table_ref", "column", "score", "evidence"],
        )
        write_csv(
            run_dir / "quality_report.csv",
            quality_rows,
            headers=[
                "table_ref",
                "column",
                "name_in_roster_rate",
                "multi_owner_rate",
                "invalid_name_examples",
                "total_name_tokens",
                "matched_name_tokens",
            ],
        )

        markdown_text = build_markdown_report(
            schema_snapshot=schema_snapshot,
            discovery_result=discovery_result,
            quality_rows=quality_rows,
            metadata={"connector": connector, "database": profile.database},
            template_spec=template_spec,
        )
        (run_dir / "mapping_report.md").write_text(markdown_text, encoding="utf-8")
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")

        diag(f"[SUCCESS] 报告已生成: {run_dir}")
        return 0

    except Exception as exc:
        diag(f"[ERROR] 执行失败: {exc}")
        diag(traceback.format_exc())
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def run_schema_only(args: argparse.Namespace, profile: ConnectionProfile) -> int:
    output_root = ensure_output_root(args.output_root)
    out_path = output_root / "schema_snapshot.json"
    conn, _connector = connect_sql_server(profile)
    try:
        snapshot = scan_schema_snapshot(
            conn,
            include_views=bool(getattr(args, "include_views", False)),
            schema_whitelist=getattr(args, "schema", None),
        )
    finally:
        conn.close()
    write_json(out_path, snapshot)
    print(f"Schema 已导出: {out_path}")
    return 0


def run_sample_only(args: argparse.Namespace, profile: ConnectionProfile) -> int:
    output_root = ensure_output_root(args.output_root)
    out_path = output_root / "sample_result.json"
    conn, _connector = connect_sql_server(profile)
    try:
        sampled = sample_table(conn, args.table, top_n=args.top, where_clause=args.where)
    finally:
        conn.close()
    write_json(out_path, sampled)
    print(f"采样结果已导出: {out_path}")
    return 0


def _handle_no_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.no_wizard:
        parser.print_help()
        return 0

    saved = load_profile()
    profile = prompt_profile(saved)
    if profile is None:
        print("已取消向导。")
        return 0

    save_profile(profile)
    print(f"连接配置已保存到: {get_profile_path()}")

    wizard_args = argparse.Namespace(
        command="run",
        include_views=False,
        schema=None,
        top=200,
        table_limit=80,
        candidate_top=5,
        output_root=None,
        roster_file=None,
    )
    return run_full_pipeline(wizard_args, profile)


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None and not any(
        [args.host, args.database, args.username, args.password, args.clear_profile]
    ):
        return _handle_no_args(parser, args)

    profile = resolve_profile(args)
    if args.command in {"run", "connect-test", "schema", "sample"} and profile is None:
        print("连接信息不完整，请提供参数或使用向导。")
        return 2

    if args.command == "connect-test":
        assert profile is not None
        result = run_connect_test(profile)
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0 if result.success else 2

    if args.command == "schema":
        assert profile is not None
        return run_schema_only(args, profile)

    if args.command == "sample":
        assert profile is not None
        return run_sample_only(args, profile)

    if args.command == "run":
        assert profile is not None
        return run_full_pipeline(args, profile)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
