from __future__ import annotations

import os
import threading
from typing import Dict, List, Tuple

from .models import WriteTask

try:
    from utils.dept_config import get_superior_keywords
except ImportError:
    def get_superior_keywords():
        return ['一室主任', '二室主任', '建筑总图室主任', '所长', '所领导', '接口工程师']

Key = Tuple[str, int, int]  # (file_path, row_index, file_type)

DESIGNER_KEYWORD = "设计人员"
SUPERIOR_KEYWORDS = get_superior_keywords()
EMOJI_MAP = {
    "待完成": "📌",
    "待设计人员完成": "📌",
    "请指派": "❗",
    "待审查": "⏳",
    "待指派人审查": "⏳",
    "待确认（可自行确认）": "⏳",
    "已审查": "",
}


class PendingCache:
    """记录尚未写入完成的指派/回文任务，用于 UI 临时覆盖。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._assignments: Dict[Key, Dict] = {}
        self._responses: Dict[Key, Dict] = {}
        self._task_index: Dict[str, List[Tuple[str, Key]]] = {}

    # ------------------------------------------------------------------ #
    # Record tasks
    # ------------------------------------------------------------------ #
    def add_assignment_entries(self, task_id: str, assignments: List[Dict]):
        with self._lock:
            entries = []
            for assignment in assignments:
                # 兼容：UI 的 DataFrame 里 source_file 可能是“全路径”或“文件名(basename)”
                # 指派 payload 的 file_path 往往是全路径，因此这里双写两份 key，确保能命中覆盖。
                keys = self._make_keys(assignment)
                for key in keys:
                    self._assignments[key] = {
                        "assigned_name": assignment.get("assigned_name", ""),
                        "assigned_by": assignment.get("assigned_by", ""),
                        "project_id": assignment.get("project_id", ""),
                        "interface_id": assignment.get("interface_id", ""),
                        "file_type": assignment.get("file_type"),
                        "status_text": assignment.get("status_text", "待完成"),
                        "status": "pending",
                    }
                    entries.append(("assignment", key))
            if entries:
                self._task_index[task_id] = entries

    def add_response_entry(self, task_id: str, info: Dict):
        self.add_response_entries(task_id, [info])

    def add_response_entries(self, task_id: str, infos: List[Dict]):
        """记录一个批量任务的全部临时回文/FU覆盖项。"""
        with self._lock:
            entries = []
            for info in infos or []:
                keys = self._make_keys(info)
                for key in keys:
                    self._responses[key] = {
                        "response_number": info.get("response_number", ""),
                        "user_name": info.get("user_name", ""),
                        "project_id": info.get("project_id", ""),
                        "status_text": info.get("status_text", ""),
                        "has_assignor": bool(info.get("has_assignor")),
                        "status": "pending",
                    }
                    entries.append(("response", key))
            # 记录索引：用于状态变更时清理/更新（同一任务可能对应多行、每行多个key）
            self._task_index[task_id] = entries

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #
    def apply_overrides_to_dataframe(self, df, file_type: int, user_roles=None, current_user: str = ""):
        """将缓存中的指派/回文信息覆盖到 DataFrame，供 UI 显示。"""
        if df is None or df.empty or '原始行号' not in df.columns:
            return df
        df = df.copy()
        rows_to_drop = []
        rows = df.to_dict("index")
        current_user = (current_user or "").strip()
        user_roles = self._normalize_roles(user_roles)
        for idx, row in rows.items():
            file_path = row.get('source_file') or row.get('源文件') or ''
            row_index = row.get('原始行号') or row.get('行号') or 0
            key_full = self._normalize_key(file_path, row_index, file_type)
            key_base = self._normalize_key(os.path.basename(str(file_path or "")), row_index, file_type)
            info = None
            if key_full in self._assignments:
                info = self._assignments[key_full]
            elif key_base in self._assignments:
                info = self._assignments[key_base]
            if info:
                if '责任人' in df.columns:
                    df.at[idx, '责任人'] = info.get('assigned_name', '')
                if '状态' in df.columns and info.get('assigned_name'):
                    status_text = self._resolve_assignment_status(info, user_roles)
                    df.at[idx, '状态'] = status_text
            info = None
            if key_full in self._responses:
                info = self._responses[key_full]
            elif key_base in self._responses:
                info = self._responses[key_base]
            if info:
                if '回文单号' in df.columns:
                    df.at[idx, '回文单号'] = info.get('response_number', '')
                if '是否已完成' in df.columns:
                    df.at[idx, '是否已完成'] = '☑'
                if '状态' in df.columns:
                    status_text = self._resolve_response_status(info, user_roles)
                    df.at[idx, '状态'] = status_text
                if current_user and info.get("user_name") == current_user:
                    rows_to_drop.append(idx)
        if rows_to_drop:
            df = df.drop(rows_to_drop).reset_index(drop=True)
        return df

    def is_assignment_pending(self, file_path: str, row_index: int, file_type: int) -> bool:
        key = self._normalize_key(file_path, row_index, file_type)
        entry = self._assignments.get(key)
        return bool(entry and entry.get("status") == "pending")

    def get_summary(self, only_user: str = None):
        with self._lock:
            items = []
            for key, info in self._assignments.items():
                if only_user and info.get("assigned_by") and only_user not in info.get("assigned_by"):
                    continue
                items.append({
                    "type": "assignment",
                    "file_path": key[0],
                    "row_index": key[1],
                    "status": info.get("status"),
                    "detail": info.get("assigned_name"),
                })
            for key, info in self._responses.items():
                if only_user and info.get("user_name") != only_user:
                    continue
                items.append({
                    "type": "response",
                    "file_path": key[0],
                    "row_index": key[1],
                    "status": info.get("status"),
                    "detail": info.get("response_number"),
                })
            return items

    # ------------------------------------------------------------------ #
    # Status updates from manager
    # ------------------------------------------------------------------ #
    def on_task_status_changed(self, task: WriteTask):
        with self._lock:
            entries = self._task_index.get(task.task_id, [])
            if not entries:
                return
            successful_response_keys = None
            if task.status == "completed" and task.task_type in ("response_batch", "fu_completion_batch"):
                result = (task.payload or {}).get("_result") or {}
                successful_items = result.get("successful_items") or []
                if successful_items:
                    successful_response_keys = set()
                    for item in successful_items:
                        cache_item = dict(item or {})
                        cache_item["row_index"] = int(
                            cache_item.get("requested_row_index", cache_item.get("row_index", 0)) or 0
                        )
                        successful_response_keys.update(self._make_keys(cache_item))
            for entry_type, key in entries:
                if entry_type == "assignment" and key in self._assignments:
                    self._assignments[key]["status"] = task.status
                    # 关键：completed 也保留覆盖，避免“写完但未重读Excel导致UI回弹”
                    # failed 则移除覆盖，让任务重新显示为未指派。
                    if task.status in ("failed",):
                        del self._assignments[key]
                elif entry_type == "response" and key in self._responses:
                    self._responses[key]["status"] = task.status
                    if successful_response_keys is not None and key not in successful_response_keys:
                        del self._responses[key]
                        continue
                    if task.status in ("failed",):
                        del self._responses[key]
            # 仅当失败时清理索引；completed 仍保留覆盖信息用于UI展示
            if task.status in ("failed",):
                self._task_index.pop(task.task_id, None)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _make_keys(self, payload: Dict) -> List[Key]:
        """
        同一条记录生成多个 Key：
        - full path key：用于 DataFrame 存 full path 的情况
        - basename key：用于 DataFrame 存 source_file basename 的情况（常见于 registry 逻辑）
        """
        file_path = payload.get("file_path", "") or payload.get("source_file", "") or payload.get("源文件", "") or ""
        row_index = int(payload.get("row_index", 0) or 0)
        file_type = int(payload.get("file_type", 0) or 0)
        keys = []
        # full
        keys.append(self._normalize_key(str(file_path or ""), row_index, file_type))
        # basename
        try:
            base = os.path.basename(str(file_path or ""))
            if base:
                keys.append(self._normalize_key(base, row_index, file_type))
        except Exception:
            pass
        # 去重保序
        seen = set()
        out = []
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
        return out

    def _normalize_key(self, file_path: str, row_index: int, file_type: int) -> Key:
        normalized = os.path.normpath(str(file_path or "")).lower()
        return normalized, int(row_index or 0), int(file_type or 0)

    # ------------------------------------------------------------------ #
    # Role helpers
    # ------------------------------------------------------------------ #
    def _normalize_roles(self, roles):
        if not roles:
            return []
        if isinstance(roles, (list, tuple, set)):
            return [str(role or "").strip() for role in roles if role]
        return [str(roles).strip()]

    def _is_designer(self, roles):
        return any(DESIGNER_KEYWORD in (role or "") for role in roles)

    def _is_superior(self, roles):
        for role in roles:
            text = role or ""
            for keyword in SUPERIOR_KEYWORDS:
                if keyword in text:
                    return True
        return False

    def _resolve_assignment_status(self, info: Dict, user_roles: List[str]) -> str:
        base = info.get("status_text") or "待完成"
        if base in ("待完成", "待设计人员完成"):
            if self._is_superior(user_roles) and not self._is_designer(user_roles):
                base = "待设计人员完成"
            else:
                base = "待完成"
        return self._format_status(base)

    def _resolve_response_status(self, info: Dict, user_roles: List[str]) -> str:
        if info.get("status_text"):
            return self._format_status(info["status_text"])
        has_assignor = info.get("has_assignor")
        base = "待指派人审查" if has_assignor else "待审查"
        return self._format_status(base)

    def _format_status(self, status_text: str) -> str:
        status_text = status_text or ""
        plain = status_text.replace('（已延期）', '')
        emoji = EMOJI_MAP.get(plain, '')
        if emoji and not status_text.startswith(emoji):
            return f"{emoji} {status_text}"
        return status_text


_pending_cache: PendingCache = PendingCache()


def get_pending_cache() -> PendingCache:
    return _pending_cache

