"""CLI and wizard entry for SQL Explorer."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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
from .distribution_chain_live import execute_distribution_chain
from .identity_resolver import build_identity_context
from .report import build_markdown_report, flatten_candidates_for_csv, write_csv, write_json
from .roster import load_roster_names, validate_owner_values
from .sampling import sample_table
from .schema import scan_schema_snapshot
from .template_spec import load_template_spec

PRIORITY_TABLE_NAMES = {
    "idiacp1000",
    "icmacp1000",
    "intinterfacedoc",
    "intinterfacedocidiacp1000",
    "iitf",
    "iics",
    "sendreceivedata",
    "ta",
    "tareply",
    "tadesigndoc",
    "taminiofile",
    "telefax",
    "memorandum",
    "internalminutes",
    "externalminutes",
    "filetransmission",
    "user",
    "department",
    "project",
    "projectmember",
    "staffscheme",
    "staffschemeuser",
    "interfacereopeninfo",
    "idiinterfacereopeninfolink",
    "icminterfacereopeninfolink",
}

TARGET_FILE_TYPES = ("1", "2", "3", "4", "6")
DEEP_SUCCESS_TIME_SCORE = 0.82
DEEP_SUCCESS_OWNER_SCORE = 0.26
DEEP_SUCCESS_OWNER_ID_RATE = 0.80
DEEP_SUCCESS_OWNER_DEPT_RATE = 0.80
DEEP_TOP_N_CAP = 1200


def _resource_base() -> Path:
    """Runtime resource base; supports PyInstaller onefile."""

    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parents[3]


def _resolve_runtime_file_path(path_value: str, default_subdir: str = "example") -> Path:
    """Resolve input file path from cwd/repo/_MEIPASS locations."""

    raw = str(path_value or "").strip()
    target = Path(raw)
    if target.is_absolute():
        return target

    base = _resource_base()
    candidates: List[Path] = []
    if raw:
        candidates.extend(
            [
                target,
                Path.cwd() / target,
                base / target,
                base / default_subdir / target.name,
                Path(__file__).resolve().parents[3] / target,
            ]
        )
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return target


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
    run_parser.add_argument("--table-limit", type=int, default=160, help="最大采样表数量")
    run_parser.add_argument("--candidate-top", type=int, default=5, help="每类输出候选数量")
    run_parser.add_argument("--include-views", action="store_true", help="包含视图")
    run_parser.add_argument("--schema", action="append", default=None, help="仅扫描指定schema")
    run_parser.add_argument(
        "--deep-detect",
        action="store_true",
        help="开启深度检测：未达到成功判定时自动扩大采样继续探测",
    )
    run_parser.add_argument(
        "--deep-max-rounds",
        type=int,
        default=0,
        help="深度检测最大轮次（0=直到成功或达到采样上限）",
    )

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

    chain_parser = subparsers.add_parser(
        "distribution-chain",
        help="文件2/4责任人分发链闭环探测",
    )
    _add_common_args(chain_parser)
    chain_parser.add_argument("--schema", default="innovator", help="目标 schema")
    chain_parser.add_argument("--sample-top", type=int, default=2000, help="关键表采样行数")
    chain_parser.add_argument(
        "--file2-excel",
        default="example/内部接口信息单报表181820260128.xlsx",
        help="文件2样本 Excel（A/D/AM）",
    )
    chain_parser.add_argument(
        "--file4-excel",
        default="example/外部接口单报表181820260128.xlsx",
        help="文件4样本 Excel（E/AH）",
    )
    chain_parser.add_argument("--skip-overview", action="store_true", help="跳过总览 run")
    chain_parser.add_argument(
        "--overview-table-limit",
        type=int,
        default=320,
        help="总览 run 表数量上限",
    )
    chain_parser.add_argument("--overview-top", type=int, default=1000, help="总览 run 每表采样行数")
    chain_parser.add_argument(
        "--overview-candidate-top",
        type=int,
        default=30,
        help="总览 run 每类候选数量",
    )
    chain_parser.add_argument(
        "--overview-deep-max-rounds",
        type=int,
        default=1,
        help="总览 run 深度检测最大轮次",
    )

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
    parser.add_argument(
        "--pause-on-error", action="store_true", help="发生错误时退出前等待按键"
    )
    parser.add_argument(
        "--no-pause-on-error", action="store_true", help="发生错误时退出前不等待按键"
    )
    parser.add_argument(
        "--pause-on-exit",
        action="store_true",
        help="无论成功/失败，退出前都等待按键",
    )
    parser.add_argument(
        "--no-pause-on-exit",
        action="store_true",
        help="无论成功/失败，退出前都不等待按键",
    )


def _build_connection_hints(profile: ConnectionProfile, error_message: str) -> List[str]:
    """Build user-facing connection troubleshooting hints."""

    hints: List[str] = []
    host = (profile.host or "").strip().lower()
    msg = (error_message or "").lower()

    if host in {"127.0.0.1", "localhost", "."}:
        hints.append(
            "当前连接目标是本机地址（127.0.0.1/localhost），如果数据库在内网服务器，请改为真实IP。"
        )
    if "10061" in msg or "unable to connect" in msg or "unavailable" in msg:
        hints.append("目标服务器不可达或端口不通，请确认IP/端口及目标机 SQL Server 服务状态。")
    if "18456" in msg or "login failed" in msg:
        hints.append("登录失败，请检查用户名、密码和数据库访问权限。")
    if "pyodbc 无可用 sql server 驱动" in error_message:
        hints.append("pyodbc 未找到可用驱动，建议安装 ODBC Driver 17/18 for SQL Server。")
    if "timeout" in msg:
        hints.append("连接超时，请检查网络连通性、防火墙策略和端口开放情况。")

    hints.append(f"本地保存连接配置位置: {get_profile_path()}")
    return hints


def _prioritize_tables_for_sampling(
    tables: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Move key business tables to the front before sampling."""

    prioritized: List[Dict[str, Any]] = []
    others: List[Dict[str, Any]] = []

    for item in tables:
        table_name = str(item.get("table", "")).strip("[] ").lower()
        if table_name in PRIORITY_TABLE_NAMES:
            prioritized.append(item)
        else:
            others.append(item)
    return [*prioritized, *others]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _sample_tables_with_progress(
    conn: Any,
    tables: Sequence[Dict[str, Any]],
    table_limit: int,
    top_n: int,
    diag: Any,
) -> Dict[str, Any]:
    sampled_tables: List[Dict[str, Any]] = []
    is_current_filtered_count = 0
    total = min(len(tables), max(1, int(table_limit)))
    if total <= 0:
        return {
            "sampled_tables": sampled_tables,
            "is_current_filtered_count": is_current_filtered_count,
            "total": 0,
        }

    for idx, table_item in enumerate(tables[:total], start=1):
        table_ref = f"{table_item['schema']}.{table_item['table']}"
        try:
            columns = {
                str(col.get("name", "")).lower() for col in (table_item.get("columns", []) or [])
            }
            where_clause = None
            if "is_current" in columns:
                where_clause = "IS_CURRENT = '1'"
                is_current_filtered_count += 1

            sampled = sample_table(conn, table_ref, top_n=top_n, where_clause=where_clause)
            sampled_tables.append(sampled)
        except Exception as exc:
            diag(f"[WARN] 采样失败 {table_ref}: {exc}")

        # 进度打印，防止用户误以为程序卡住
        if idx == 1 or idx == total or idx % 10 == 0:
            percent = int((idx / max(1, total)) * 100)
            diag(f"[PROGRESS] 采样进度: {idx}/{total} ({percent}%)")

    return {
        "sampled_tables": sampled_tables,
        "is_current_filtered_count": is_current_filtered_count,
        "total": total,
    }


def _build_quality_rows(
    discovery_result: Dict[str, Any],
    sampled_tables: Sequence[Dict[str, Any]],
    roster_names: Sequence[str],
    user_id_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
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
        quality = validate_owner_values(values, set(roster_names), user_id_map=user_id_map)
        quality_rows.append(
            {
                "table_ref": table_ref,
                "column": col,
                **quality,
            }
        )
    return quality_rows


def _evaluate_discovery_success(discovery_result: Dict[str, Any]) -> Dict[str, Any]:
    file_type_rows = discovery_result.get("file_type_candidates") or {}
    details: Dict[str, Dict[str, Any]] = {}
    all_ok = True

    for file_type in TARGET_FILE_TYPES:
        row = file_type_rows.get(file_type) or {}
        time_candidates = row.get("time_candidates") or []
        owner_candidates = row.get("owner_candidates") or []

        best_time = time_candidates[0] if time_candidates else {}
        best_owner = owner_candidates[0] if owner_candidates else {}
        owner_evidence = best_owner.get("evidence") or {}

        time_score = _safe_float(best_time.get("score"))
        owner_score = _safe_float(best_owner.get("score"))
        owner_id_rate = _safe_float(owner_evidence.get("id_resolved_rate"))
        owner_dept_rate = _safe_float(owner_evidence.get("resolved_dept_rate"))

        time_ok = time_score >= DEEP_SUCCESS_TIME_SCORE
        owner_ok = (
            owner_score >= DEEP_SUCCESS_OWNER_SCORE
            and owner_id_rate >= DEEP_SUCCESS_OWNER_ID_RATE
            and owner_dept_rate >= DEEP_SUCCESS_OWNER_DEPT_RATE
        )
        row_ok = bool(time_ok and owner_ok)
        all_ok = all_ok and row_ok

        details[file_type] = {
            "ok": row_ok,
            "time_score": round(time_score, 6),
            "owner_score": round(owner_score, 6),
            "owner_id_resolved_rate": round(owner_id_rate, 6),
            "owner_dept_resolved_rate": round(owner_dept_rate, 6),
            "time_top": {
                "table_ref": best_time.get("table_ref", ""),
                "column": best_time.get("column", ""),
            },
            "owner_top": {
                "table_ref": best_owner.get("table_ref", ""),
                "column": best_owner.get("column", ""),
            },
        }

    return {
        "success": all_ok,
        "detail": details,
        "thresholds": {
            "time_score": DEEP_SUCCESS_TIME_SCORE,
            "owner_score": DEEP_SUCCESS_OWNER_SCORE,
            "owner_id_resolved_rate": DEEP_SUCCESS_OWNER_ID_RATE,
            "owner_dept_resolved_rate": DEEP_SUCCESS_OWNER_DEPT_RATE,
        },
    }


def _normalize_argv_for_subcommand(raw_argv: List[str]) -> List[str]:
    """
    Normalize argv so subcommand appears first.

    This allows both forms:
    - sql_explorer.exe run --host 10.27.14.216 ...
    - sql_explorer.exe --host 10.27.14.216 ... run
    """

    commands = {"run", "connect-test", "schema", "sample", "distribution-chain"}
    if not raw_argv:
        return raw_argv

    cmd_index = -1
    for idx, token in enumerate(raw_argv):
        if token in commands:
            cmd_index = idx
            break

    if cmd_index <= 0:
        return raw_argv

    cmd = raw_argv[cmd_index]
    rest = [item for i, item in enumerate(raw_argv) if i != cmd_index]
    return [cmd, *rest]


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


def _profile_complete(profile: Optional[ConnectionProfile]) -> bool:
    if profile is None:
        return False
    return bool(profile.host and profile.username and profile.password)


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

    diag("[PROGRESS] 阶段 1/5: 连接测试...")
    test_result = run_connect_test(profile)
    if not test_result.success:
        diag(f"[ERROR] 连接测试失败: {test_result.message}")
        for hint in _build_connection_hints(profile, test_result.message):
            diag(f"[HINT] {hint}")
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        diag(f"[INFO] 诊断日志: {diagnostics_path}")
        return 2
    diag(f"[OK] 连接测试成功，连接器: {test_result.connector}")
    diag("[PROGRESS] 阶段 2/5: 扫描 Schema ...")

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
        tables = _prioritize_tables_for_sampling(tables)
        total_tables = len(tables)
        base_table_limit = max(1, int(getattr(args, "table_limit", 160)))
        base_top_n = max(20, int(getattr(args, "top", 200)))
        candidate_top = max(3, int(getattr(args, "candidate_top", 5)))

        deep_detect = bool(getattr(args, "deep_detect", False))
        deep_max_rounds = max(0, int(getattr(args, "deep_max_rounds", 0)))

        diag("[PROGRESS] 阶段 3/5: 加载名单与身份映射 ...")
        roster_names = load_roster_names(args.roster_file)
        diag(f"[INFO] 姓名角色表加载人数: {len(roster_names)}")

        identity_context = build_identity_context(
            conn,
            schema_snapshot=schema_snapshot,
            schema_whitelist=getattr(args, "schema", None),
        )
        user_id_map = identity_context.get("user_id_map") or {}
        diag(
            "[INFO] 身份映射加载: "
            f"USER={identity_context.get('user_count', 0)}, "
            f"DEPARTMENT={identity_context.get('department_count', 0)}"
        )
        if identity_context.get("user_schema") or identity_context.get("department_schema"):
            diag(
                "[INFO] 身份映射来源schema: "
                f"USER={identity_context.get('user_schema', '')}, "
                f"DEPARTMENT={identity_context.get('department_schema', '')}"
            )
        for warning in (identity_context.get("warnings") or []):
            diag(f"[WARN] 身份映射: {warning}")

        template_spec = load_template_spec()
        if template_spec:
            diag(
                f"[INFO] 模板规范已加载: version={template_spec.get('version', 'unknown')}"
            )
        else:
            diag("[WARN] 未加载到 example/template_spec.json，将仅输出候选结果")

        diag("[PROGRESS] 阶段 4/5: 候选探测与深度判定 ...")
        sampled_tables: List[Dict[str, Any]] = []
        discovery_result: Dict[str, Any] = {}
        quality_rows: List[Dict[str, Any]] = []
        deep_round_summaries: List[Dict[str, Any]] = []
        final_eval: Dict[str, Any] = {"success": True, "detail": {}, "thresholds": {}}
        current_table_limit = min(total_tables, base_table_limit) if total_tables else base_table_limit
        current_top_n = base_top_n
        round_index = 1

        while True:
            diag(
                "[PROGRESS] 探测轮次 "
                f"{round_index} 开始: table_limit={current_table_limit}, top={current_top_n}"
            )
            sampled_payload = _sample_tables_with_progress(
                conn=conn,
                tables=tables,
                table_limit=current_table_limit,
                top_n=current_top_n,
                diag=diag,
            )
            sampled_tables = sampled_payload["sampled_tables"]
            is_current_filtered_count = int(sampled_payload["is_current_filtered_count"])

            diag(f"[INFO] 采样完成，成功采样表数: {len(sampled_tables)}")
            if is_current_filtered_count:
                diag(
                    f"[INFO] 采样策略: {is_current_filtered_count} 张表自动附加 IS_CURRENT='1' 过滤"
                )

            discovery_result = discover_candidates(
                sampled_tables,
                roster_names=roster_names,
                user_id_map=user_id_map,
                top_n=candidate_top,
            )
            quality_rows = _build_quality_rows(
                discovery_result=discovery_result,
                sampled_tables=sampled_tables,
                roster_names=roster_names,
                user_id_map=user_id_map,
            )
            final_eval = _evaluate_discovery_success(discovery_result)

            deep_round_summaries.append(
                {
                    "round": round_index,
                    "table_limit": current_table_limit,
                    "top_n": current_top_n,
                    "sampled_tables": len(sampled_tables),
                    "success": bool(final_eval.get("success")),
                    "details": final_eval.get("detail", {}),
                }
            )

            for file_type in TARGET_FILE_TYPES:
                detail = (final_eval.get("detail") or {}).get(file_type, {})
                diag(
                    "[PROGRESS] "
                    f"文件{file_type}: "
                    f"time={detail.get('time_score', 0.0):.3f}, "
                    f"owner={detail.get('owner_score', 0.0):.3f}, "
                    f"id={detail.get('owner_id_resolved_rate', 0.0):.3f}, "
                    f"dept={detail.get('owner_dept_resolved_rate', 0.0):.3f} "
                    f"=> {'OK' if detail.get('ok') else '待提升'}"
                )

            if not deep_detect:
                break

            if bool(final_eval.get("success")):
                diag(f"[SUCCESS] 深度检测判定通过（轮次 {round_index}）")
                break

            round_limit_hit = deep_max_rounds > 0 and round_index >= deep_max_rounds
            data_cap_hit = current_table_limit >= total_tables and current_top_n >= DEEP_TOP_N_CAP
            if round_limit_hit or data_cap_hit:
                reason = "达到最大轮次" if round_limit_hit else "达到采样上限"
                diag(f"[WARN] 深度检测停止：{reason}，仍未达到成功判定。")
                break

            next_table_limit = min(
                total_tables, max(current_table_limit + 20, int(current_table_limit * 1.35))
            )
            next_top_n = min(DEEP_TOP_N_CAP, max(current_top_n + 100, int(current_top_n * 1.5)))
            if next_table_limit == current_table_limit and next_top_n == current_top_n:
                diag("[WARN] 深度检测无法继续扩展参数，停止。")
                break

            current_table_limit = next_table_limit
            current_top_n = next_top_n
            round_index += 1

        identity_summary = {
            "user_count": int(identity_context.get("user_count", 0)),
            "department_count": int(identity_context.get("department_count", 0)),
            "user_schema": identity_context.get("user_schema", ""),
            "department_schema": identity_context.get("department_schema", ""),
            "warnings": list(identity_context.get("warnings", []) or []),
        }

        report_payload = {
            "metadata": {
                "host": profile.host,
                "database": profile.database,
                "connector": connector,
                "table_limit": current_table_limit,
                "sample_top_n": current_top_n,
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
            "identity_summary": identity_summary,
            "template_spec": template_spec,
            "deep_detection": {
                "enabled": deep_detect,
                "max_rounds": deep_max_rounds,
                "rounds": deep_round_summaries,
                "final_success": bool(final_eval.get("success")),
                "thresholds": final_eval.get("thresholds", {}),
            },
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
                "id_token_count",
                "resolved_id_count",
                "id_resolved_rate",
                "resolved_name_rate",
                "resolved_dept_rate",
                "unresolved_id_examples",
                "resolved_user_examples",
            ],
        )

        markdown_text = build_markdown_report(
            schema_snapshot=schema_snapshot,
            discovery_result=discovery_result,
            quality_rows=quality_rows,
            metadata={
                "connector": connector,
                "database": profile.database,
                "identity_summary": identity_summary,
            },
            template_spec=template_spec,
        )
        (run_dir / "mapping_report.md").write_text(markdown_text, encoding="utf-8")
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")

        if deep_detect and not bool(final_eval.get("success")):
            diag(f"[WARN] 报告已生成，但深度检测未达到成功判定: {run_dir}")
            return 3

        diag(f"[SUCCESS] 报告已生成: {run_dir}")
        return 0

    except Exception as exc:
        diag(f"[ERROR] 执行失败: {exc}")
        diag(traceback.format_exc())
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        diag(f"[INFO] 诊断日志: {diagnostics_path}")
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


def run_distribution_chain_pipeline(args: argparse.Namespace, profile: ConnectionProfile) -> int:
    """Run file2/file4 distribution-chain closure pipeline."""

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
        for hint in _build_connection_hints(profile, test_result.message):
            diag(f"[HINT] {hint}")
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        diag(f"[INFO] 诊断日志: {diagnostics_path}")
        return 2
    diag(f"[OK] 连接测试成功，连接器: {test_result.connector}")

    if not bool(getattr(args, "skip_overview", False)):
        diag("[PROGRESS] 执行总览 run（用于基线证据） ...")
        overview_output_root = run_dir / "raw_runs" / "overview"
        overview_output_root.mkdir(parents=True, exist_ok=True)
        overview_args = argparse.Namespace(
            include_views=False,
            schema=[args.schema],
            top=max(100, int(getattr(args, "overview_top", 1000))),
            table_limit=max(1, int(getattr(args, "overview_table_limit", 320))),
            candidate_top=max(5, int(getattr(args, "overview_candidate_top", 30))),
            deep_detect=True,
            deep_max_rounds=max(0, int(getattr(args, "overview_deep_max_rounds", 1))),
            output_root=str(overview_output_root),
            roster_file=args.roster_file,
        )
        overview_code = run_full_pipeline(overview_args, profile)
        diag(f"[INFO] 总览 run 完成，exit_code={overview_code}")

    conn = None
    try:
        conn, _connector = connect_sql_server(profile)
        schema_snapshot = scan_schema_snapshot(
            conn,
            include_views=False,
            schema_whitelist=[args.schema],
        )
        diag(f"[INFO] 分发链扫描范围: schema={args.schema}, tables={schema_snapshot.get('table_count', 0)}")

        identity_context = build_identity_context(
            conn,
            schema_snapshot=schema_snapshot,
            schema_whitelist=[args.schema],
        )
        user_id_map = identity_context.get("user_id_map") or {}
        diag(
            "[INFO] 身份映射加载: "
            f"USER={identity_context.get('user_count', 0)}, "
            f"DEPARTMENT={identity_context.get('department_count', 0)}"
        )

        file2_excel = _resolve_runtime_file_path(getattr(args, "file2_excel"))
        file4_excel = _resolve_runtime_file_path(getattr(args, "file4_excel"))
        diag(f"[INFO] 文件2样本路径: {file2_excel}")
        diag(f"[INFO] 文件4样本路径: {file4_excel}")
        if not file2_excel.exists():
            raise FileNotFoundError(
                f"文件2样本不存在: {file2_excel}（可通过 --file2-excel 指定绝对路径）"
            )
        if not file4_excel.exists():
            raise FileNotFoundError(
                f"文件4样本不存在: {file4_excel}（可通过 --file4-excel 指定绝对路径）"
            )

        payload = execute_distribution_chain(
            conn=conn,
            schema_snapshot=schema_snapshot,
            run_root=run_dir,
            schema_name=args.schema,
            sample_top_n=max(200, int(getattr(args, "sample_top", 2000))),
            file2_excel=file2_excel,
            file4_excel=file4_excel,
            user_id_map=user_id_map,
            diag=diag,
            connection_factory=lambda: connect_sql_server(profile)[0],
        )

        blocked = (
            (((payload.get("question_answers") or {}).get("q4_blocked_by_permission_or_data")) or {})
            .get("answer")
            == "YES"
        )
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        diag(f"[INFO] 诊断日志: {diagnostics_path}")
        if blocked:
            diag("[WARN] 分发链探测完成，但存在阻塞（详见报告 blocking_points）。")
            return 3
        diag(f"[SUCCESS] 分发链报告已生成: {run_dir}")
        return 0
    except Exception as exc:
        diag(f"[ERROR] 分发链执行失败: {exc}")
        diag(traceback.format_exc())
        diagnostics_path.write_text("\n".join(diagnostics_lines), encoding="utf-8")
        diag(f"[INFO] 诊断日志: {diagnostics_path}")
        return 1
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _handle_no_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if args.no_wizard:
        parser.print_help()
        return 0

    saved = load_profile()
    if _profile_complete(saved):
        profile = saved
        print("检测到本地连接配置，已按默认模式自动运行：")
        print("  run --use-saved-profile --deep-detect --pause-on-exit")
    else:
        print("未检测到可用的本地连接配置，进入首次向导。")
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
        table_limit=160,
        candidate_top=5,
        deep_detect=True,
        deep_max_rounds=0,
        output_root=None,
        roster_file=None,
    )
    return run_full_pipeline(wizard_args, profile)


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""

    parser = build_parser()
    try:
        raw_argv = list(argv) if argv is not None else sys.argv[1:]
        normalized_argv = _normalize_argv_for_subcommand(raw_argv)
        args = parser.parse_args(normalized_argv)

        if args.command is None and not any(
            [args.host, args.database, args.username, args.password, args.clear_profile]
        ):
            return _handle_no_args(parser, args)

        profile = resolve_profile(args)
        if args.command in {"run", "connect-test", "schema", "sample", "distribution-chain"} and profile is None:
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

        if args.command == "distribution-chain":
            assert profile is not None
            return run_distribution_chain_pipeline(args, profile)

        parser.print_help()
        return 0
    except Exception as exc:
        print(f"[FATAL] 程序出现未处理异常: {exc}")
        print(traceback.format_exc())
        return 1


def maybe_pause_on_error(exit_code: int) -> None:
    """
    Prevent console from closing immediately on failure.

    Default behavior:
    - Double-click launch (no args): pause on non-zero exit.
    - CLI launch with args: no pause unless --pause-on-error.
    """

    argv = sys.argv[1:]
    if "--no-pause-on-exit" in argv:
        return
    if "--pause-on-exit" in argv:
        should_pause = True
    elif not argv:
        # 双击启动（无参数）默认总是暂停，避免窗口闪退
        should_pause = True
    else:
        should_pause = exit_code != 0 and "--no-pause-on-error" not in argv

    if not should_pause:
        return

    if "--no-pause-on-error" in argv:
        if exit_code != 0:
            return

    try:
        import msvcrt

        if exit_code == 0:
            tip = "程序执行完成"
        elif exit_code == 3:
            tip = "程序执行完成（存在阻塞，请查看报告）"
        else:
            tip = "程序执行失败"
        print(f"\n{tip}，按任意键退出...", end="", flush=True)
        msvcrt.getch()
        print("")
    except Exception:
        try:
            if exit_code == 0:
                tip = "程序执行完成"
            elif exit_code == 3:
                tip = "程序执行完成（存在阻塞，请查看报告）"
            else:
                tip = "程序执行失败"
            input(f"\n{tip}，按回车键退出...")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
