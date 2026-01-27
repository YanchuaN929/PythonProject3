from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from registry.util import extract_interface_id, extract_project_id, normalize_project_id
from ui.ui_copy import normalize_interface_id


@dataclass
class RegistryTaskSnapshot:
    file_type: int
    project_id: str
    interface_id: str
    display_status: str
    status: str
    source_file: str
    row_index: Optional[int]
    completed_at: Optional[str]
    completed_by: Optional[str]
    confirmed_at: Optional[str]
    confirmed_by: Optional[str]
    response_number: Optional[str]


def open_registry(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def read_registry_tasks(conn: sqlite3.Connection, interface_id: str, project_id: str) -> List[RegistryTaskSnapshot]:
    interface_id = normalize_interface_id(interface_id)
    project_id = str(project_id).strip()

    rows = conn.execute(
        """
        SELECT file_type, project_id, interface_id, display_status, status, source_file, row_index,
               completed_at, completed_by, confirmed_at, confirmed_by, response_number
        FROM tasks
        WHERE interface_id = ?
          AND project_id = ?
          AND status != 'archived'
        ORDER BY last_seen_at DESC
        """,
        (interface_id, project_id),
    ).fetchall()

    out: List[RegistryTaskSnapshot] = []
    for r in rows:
        out.append(
            RegistryTaskSnapshot(
                file_type=int(r[0]),
                project_id=str(r[1] or ""),
                interface_id=str(r[2] or ""),
                display_status=str(r[3] or ""),
                status=str(r[4] or ""),
                source_file=str(r[5] or ""),
                row_index=int(r[6]) if r[6] is not None else None,
                completed_at=r[7],
                completed_by=r[8],
                confirmed_at=r[9],
                confirmed_by=r[10],
                response_number=r[11],
            )
        )
    return out


def list_excel_files(data_folder: str) -> List[str]:
    out = []
    for root, _, files in os.walk(data_folder):
        for name in files:
            if name.lower().endswith((".xlsx", ".xls")):
                out.append(os.path.join(root, name))
    return sorted(out)


def find_data_folders(scan_root: str, limit: int = 50) -> List[str]:
    """
    仅用ASCII根目录扫描数据目录，避免命令行中文路径编码问题。
    规则：找到形如 <data_folder>\\registry\\registry.db 的路径，则认为 <data_folder> 为候选。
    """
    scan_root = str(scan_root or "").strip()
    if not scan_root or not os.path.exists(scan_root):
        return []
    found: List[str] = []
    try:
        for root, dirs, files in os.walk(scan_root):
            # 小优化：只在包含registry.db时处理
            if "registry.db" not in {f.lower() for f in files}:
                continue
            for name in files:
                if name.lower() != "registry.db":
                    continue
                db_path = os.path.join(root, name)
                # 期望...\\registry\\registry.db
                parent = os.path.basename(os.path.dirname(db_path)).lower()
                if parent == "registry":
                    data_folder = os.path.dirname(os.path.dirname(db_path))
                    if data_folder not in found:
                        found.append(data_folder)
                        if len(found) >= limit:
                            return found
    except Exception:
        return found
    return found


def infer_registry_db_path(data_folder: str) -> Optional[str]:
    """
    尝试推断registry.db位置：
    1) data_folder/registry/registry.db（旧约定）
    2) data_folder/registry.db
    3) data_folder 下递归搜索 registry.db（测试目录可能不同结构）
    4) 读取程序配置 registry_db_path（更贴近真实运行逻辑）
    """
    def _has_tasks_table(db_path: str) -> bool:
        try:
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks' LIMIT 1"
                ).fetchone()
                return bool(row and row[0] == "tasks")
            finally:
                conn.close()
        except Exception:
            return False

    cand = os.path.join(data_folder, "registry", "registry.db")
    if os.path.exists(cand):
        return cand
    cand2 = os.path.join(data_folder, "registry.db")
    if os.path.exists(cand2):
        if _has_tasks_table(cand2):
            return cand2

    # 递归搜索
    try:
        best_registry_folder = None
        best_any = None
        for root, _, files in os.walk(data_folder):
            for name in files:
                if name.lower() == "registry.db":
                    p = os.path.join(root, name)
                    if not os.path.exists(p):
                        continue
                    parent = os.path.basename(os.path.dirname(p)).lower()
                    if parent == "registry" and _has_tasks_table(p):
                        # 最优：位于registry目录且具备tasks表
                        return p
                    if parent == "registry" and best_registry_folder is None:
                        best_registry_folder = p
                    if best_any is None and _has_tasks_table(p):
                        best_any = p
        # 次优：registry目录下的registry.db（即使无法快速校验tasks表）
        if best_registry_folder:
            return best_registry_folder
        # 兜底：任何包含tasks表的registry.db
        if best_any:
            return best_any
    except Exception:
        pass

    # 尝试从程序配置读取（与主程序一致）
    try:
        from registry.hooks import _cfg

        cfg = _cfg()
        db_path = cfg.get("registry_db_path")
        if db_path and os.path.exists(db_path):
            return db_path
    except Exception:
        pass

    return None


def parse_project_id_from_filename(file_path: str) -> str:
    name = os.path.basename(file_path)
    m = re.search(r"(\d{4})", name)
    return m.group(1) if m else ""


def scan_interface_rows(df: pd.DataFrame, file_type: int, interface_id: str) -> List[int]:
    target = normalize_interface_id(interface_id)
    idxs: List[int] = []
    for i in range(len(df)):
        if i == 0:
            continue
        try:
            got = extract_interface_id(df.iloc[i], file_type)
        except Exception:
            continue
        if got == target:
            idxs.append(i)
    return idxs


def simulate_process(file_type: int, file_path: str, now: datetime) -> pd.DataFrame:
    from core import main as main_module

    if file_type == 1:
        return main_module.process_target_file(file_path, now)
    if file_type == 3:
        return main_module.process_target_file3(file_path, now)
    if file_type == 4:
        return main_module.process_target_file4(file_path, now)
    raise ValueError(f"暂不支持的file_type: {file_type}")


def contains_interface_in_result(result_df: pd.DataFrame, file_type: int, interface_id: str) -> bool:
    if result_df is None or result_df.empty:
        return False
    target = normalize_interface_id(interface_id)
    for i in range(len(result_df)):
        try:
            got = extract_interface_id(result_df.iloc[i], file_type)
        except Exception:
            continue
        if got == target:
            return True
    return False


def engineer_project_from_role(role: str) -> Optional[str]:
    s = (role or "").strip()
    m = re.search(r"(\d{4})\s*接口工程师", s)
    return m.group(1) if m else None


def build_debug_report(
    *,
    data_folder: str,
    interface_id: str,
    project_id: str,
    role: str,
    file_types: Sequence[int] = (3, 4),
    registry_db_path: Optional[str] = None,
) -> Tuple[str, Dict]:
    """
    返回：(可读报告文本, 结构化数据dict)。
    """
    info: Dict = {
        "data_folder": data_folder,
        "interface_id": normalize_interface_id(interface_id),
        "project_id": str(project_id),
        "role": role,
        "file_types": list(file_types),
        "registry_db": None,
        "effective_data_folder": None,
        "registry_tasks": [],
        "checks": [],
    }

    lines: List[str] = []
    lines.append("== 可见性调试报告 ==")
    lines.append(f"- data_folder: {data_folder}")
    lines.append(f"- interface_id: {info['interface_id']}")
    lines.append(f"- project_id: {info['project_id']}")
    lines.append(f"- role: {role}")

    eng_pid = engineer_project_from_role(role)
    lines.append(f"- 解析接口工程师项目号: {eng_pid or '(未识别)'}")
    if eng_pid and eng_pid != str(project_id):
        lines.append(f"⚠️ 角色项目号({eng_pid})与输入project_id({project_id})不一致，可能导致角色过滤为空。")

    db_path = registry_db_path or infer_registry_db_path(data_folder)
    info["registry_db"] = db_path
    if not db_path:
        lines.append("❌ 未找到 registry.db")
        lines.append("  - 已尝试：data_folder/registry/registry.db、data_folder/registry.db、递归搜索、程序配置registry_db_path")
        lines.append("  - 你可以显式传参：--registry-db \"<path-to-registry.db>\"")
        return "\n".join(lines), info

    # 如果db位于 data_folder/.registry/registry.db 或 data_folder/registry/registry.db，则反推出更准确的数据目录
    effective_folder = data_folder
    try:
        db_dir = os.path.dirname(db_path)
        db_parent = os.path.basename(db_dir).lower()
        if db_parent in (".registry", "registry"):
            effective_folder = os.path.dirname(db_dir)
    except Exception:
        effective_folder = data_folder
    info["effective_data_folder"] = effective_folder

    lines.append(f"- registry_db: {db_path}")
    if effective_folder != data_folder:
        lines.append(f"- effective_data_folder: {effective_folder}")

    # 关键：让main.py的registry查询使用同一数据目录（避免落到result_cache/registry.db）
    try:
        from registry import hooks as registry_hooks

        registry_hooks.set_data_folder(effective_folder)
    except Exception:
        pass
    conn = open_registry(db_path)
    try:
        tasks = read_registry_tasks(conn, interface_id, str(project_id))
    except Exception as e:
        lines.append(f"❌ 查询 registry tasks 失败: {e}")
        return "\n".join(lines), info

    info["registry_tasks"] = [t.__dict__ for t in tasks]
    if not tasks:
        lines.append("❌ registry中未找到该接口/项目记录（请先确认历史查询能查到）")
        return "\n".join(lines), info

    lines.append(f"- registry匹配记录数: {len(tasks)}（显示前3条）")
    for t in tasks[:3]:
        lines.append(
            f"  - file_type={t.file_type} display_status={t.display_status} status={t.status} "
            f"completed_by={t.completed_by or '-'} completed_at={t.completed_at or '-'} source_file={t.source_file or '-'}"
        )

    excel_files = list_excel_files(effective_folder)
    if not excel_files:
        lines.append("❌ data_folder下未找到任何Excel文件(.xlsx/.xls)")
        return "\n".join(lines), info

    now = datetime.now()
    for ft in file_types:
        # 只对registry里出现过的file_type优先调试；但仍允许强制检查
        lines.append(f"\n== 检查 file_type={ft} ==")

        # 候选文件：先按文件名项目号过滤，再兜底全扫（调试场景可接受）
        candidates = [p for p in excel_files if str(project_id) in os.path.basename(p)]
        if not candidates:
            candidates = excel_files
            lines.append("⚠️ 未找到文件名包含项目号的候选文件，将退化为全目录扫描（可能较慢）")
        else:
            lines.append(f"- 候选文件数(文件名含项目号): {len(candidates)}")

        hit_any = False
        for file_path in candidates[:50]:
            try:
                df = pd.read_excel(file_path, sheet_name=0, engine="openpyxl" if file_path.lower().endswith("xlsx") else None)
            except Exception:
                continue

            row_hits = scan_interface_rows(df, ft, interface_id)
            if not row_hits:
                continue

            hit_any = True
            pid_from_row = ""
            try:
                pid_from_row = extract_project_id(df.iloc[row_hits[0]], ft) or ""
            except Exception:
                pid_from_row = ""
            pid_final = pid_from_row or parse_project_id_from_filename(file_path)
            pid_final = normalize_project_id(pid_final, ft) if pid_final else pid_final

            lines.append(f"- 在Excel中找到接口：{os.path.basename(file_path)} 行索引={row_hits[:5]} 项目号推断={pid_final or '(空)'}")

            try:
                result_df = simulate_process(ft, file_path, now)
            except Exception as e:
                lines.append(f"  ❌ process_target_file{ft} 运行失败: {e}")
                continue

            visible = contains_interface_in_result(result_df, ft, interface_id)
            lines.append(f"  - process结果是否包含该接口: {'YES' if visible else 'NO'} (result_rows={0 if result_df is None else len(result_df)})")
            info["checks"].append(
                {
                    "file_type": ft,
                    "file_path": file_path,
                    "row_hits": row_hits,
                    "project_id_inferred": pid_final,
                    "visible_in_process": bool(visible),
                }
            )
            # 找到一条能复现就停止继续扫，避免输出太大
            break

        if not hit_any:
            lines.append("❌ 未在候选Excel中找到该接口号（检查是否属于其他file_type，或源文件不在此目录）")

    return "\n".join(lines), info


