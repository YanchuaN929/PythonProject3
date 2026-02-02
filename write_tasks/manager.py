from __future__ import annotations

import queue
import threading
import uuid
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

from .cache import WriteTaskCache
from .models import WriteTask, utc_now_iso
from . import executors
try:
    from registry import hooks as registry_hooks
except Exception:
    registry_hooks = None

try:
    from .shared_log import upsert_task as _shared_log_upsert_task
except Exception:
    _shared_log_upsert_task = None

def _get_app_directory() -> Path:
    """
    获取程序根目录（与 file_manager._get_app_directory() 口径一致）：
    - 打包环境：exe 所在目录
    - 开发环境：源码所在目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _get_default_state_path() -> Path:
    # 固定写入到“程序根目录/result_cache/”下（满足用户“固定路径”的诉求）
    return _get_app_directory() / "result_cache" / "write_tasks_state.json"


def _legacy_state_paths() -> list[Path]:
    """
    兼容旧版本：write_tasks_state.json 可能在
    - 当前工作目录下的 result_cache/
    - (打包环境) exe 目录下的 result_cache/
    - (历史版本) 每用户目录（LOCALAPPDATA/APPDATA），仅用于迁移读取，不作为新写入位置
    """
    paths: list[Path] = []
    try:
        paths.append((Path.cwd() / "result_cache" / "write_tasks_state.json").resolve())
    except Exception:
        paths.append(Path("result_cache") / "write_tasks_state.json")
    try:
        exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
        if exe_dir:
            paths.append(exe_dir / "result_cache" / "write_tasks_state.json")
    except Exception:
        pass
    # 兼容迁移：把之前错误放到每用户目录的 state 文件迁回程序根目录
    try:
        local_appdata = os.environ.get("LOCALAPPDATA") or ""
        appdata = os.environ.get("APPDATA") or ""
        for base in (local_appdata, appdata):
            if base:
                paths.append((Path(base) / "接口筛选" / "result_cache" / "write_tasks_state.json").resolve())
    except Exception:
        pass
    # 去重（保持顺序）
    seen = set()
    uniq: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


DEFAULT_STATE_PATH = _get_default_state_path()

_manager_singleton: Optional["WriteTaskManager"] = None
_singleton_lock = threading.Lock()


class WriteTaskManager:
    """后台写入任务队列管理器。"""

    def __init__(self, state_path: Path = DEFAULT_STATE_PATH):
        self.state_path = Path(state_path)
        # 兼容迁移：如果新位置不存在，但旧位置存在，则拷贝过去（只做一次，尽量不影响启动）
        try:
            if not self.state_path.exists():
                for legacy in _legacy_state_paths():
                    try:
                        if legacy.exists() and legacy.is_file():
                            self.state_path.parent.mkdir(parents=True, exist_ok=True)
                            # 如果旧文件和新文件是同一路径，跳过
                            if legacy.resolve() != self.state_path.resolve():
                                self.state_path.write_bytes(legacy.read_bytes())
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        self.cache = WriteTaskCache(self.state_path)
        self.tasks: Dict[str, WriteTask] = {}
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stop_event = threading.Event()
        self._listeners = []
        self._queue_lock = threading.Lock()
        self._load_existing_tasks()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    # ------------------------------------------------------------------ #
    # Initialization helpers
    # ------------------------------------------------------------------ #
    def _load_existing_tasks(self):
        for task in self.cache.load():
            if task.status in ("pending", "running"):
                task.status = "pending"
                self._queue.put(task.task_id)
            self.tasks[task.task_id] = task

    # ------------------------------------------------------------------ #
    # Submission API
    # ------------------------------------------------------------------ #
    def submit_assignment_task(self, assignments, submitted_by: str, description: str) -> WriteTask:
        payload = {"assignments": assignments}
        return self._submit("assignment", payload, submitted_by, description)

    def submit_response_task(
        self,
        *,
        file_path: str,
        file_type: int,
        row_index: int,
        interface_id: str,
        response_number: str,
        user_name: str,
        project_id: str,
        source_column: Optional[str],
        role: Optional[str] = None,
        description: str,
    ) -> WriteTask:
        payload = {
            "file_path": file_path,
            "file_type": file_type,
            "row_index": row_index,
            "interface_id": interface_id,
            "response_number": response_number,
            "user_name": user_name,
            "project_id": project_id,
            "source_column": source_column,
            "role": role,
        }
        return self._submit("response", payload, user_name or "未知用户", description)

    def _submit(self, task_type: str, payload: dict, submitted_by: str, description: str) -> WriteTask:
        task = WriteTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            payload=payload,
            submitted_by=submitted_by or "未知用户",
            description=description,
        )
        self.tasks[task.task_id] = task
        self.cache.save(self.tasks.values())
        self._sync_to_shared_log(task)
        self._queue.put(task.task_id)
        return task

    # ------------------------------------------------------------------ #
    # Worker loop
    # ------------------------------------------------------------------ #
    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                task_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            task = self.tasks.get(task_id)
            if not task:
                self._queue.task_done()
                continue

            executor = None
            try:
                executor = executors.get_executor(task.task_type)
            except Exception as e:
                task.status = "failed"
                task.error = f"无法找到执行器: {e}"
                self.cache.save(self.tasks.values())
                self._notify_listeners(task)
                self._queue.task_done()
                continue

            task.status = "running"
            task.started_at = utc_now_iso()
            self.cache.save(self.tasks.values())
            self._notify_listeners(task)
            self._sync_to_shared_log(task)

            try:
                result = executor(task.payload)
                if result is False:
                    raise RuntimeError("写入任务执行失败，返回 False")

                # ----------------------------------------------------------
                # 指派任务：distribution.save_assignments_batch 返回 dict
                # 需要根据 success_count/failed_tasks 判断真实成败。
                # 否则会出现“全部失败但任务仍显示完成”，导致 UI/用户误判。
                # ----------------------------------------------------------
                if task.task_type == "assignment" and isinstance(result, dict):
                    try:
                        expected_total = len((task.payload or {}).get("assignments") or [])
                    except Exception:
                        expected_total = 0
                    try:
                        success_count = int(result.get("success_count", 0) or 0)
                    except Exception:
                        success_count = 0
                    failed_tasks = result.get("failed_tasks") or []
                    failed_count = len(failed_tasks) if isinstance(failed_tasks, list) else 0

                    # 严格策略：只要存在失败/成功数不匹配，就视为失败（避免“看起来完成但没写入”）
                    if success_count <= 0 or failed_count > 0 or (expected_total and success_count < expected_total):
                        first_reason = ""
                        try:
                            if isinstance(failed_tasks, list) and failed_tasks:
                                ft = failed_tasks[0] or {}
                                first_reason = str(ft.get("reason", "") or "")
                        except Exception:
                            first_reason = ""
                        raise RuntimeError(
                            f"指派写入失败: success_count={success_count}"
                            f"{f'/{expected_total}' if expected_total else ''}, "
                            f"failed={failed_count}"
                            f"{f', reason={first_reason}' if first_reason else ''}"
                        )
                task.status = "completed"
                task.error = None
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
            finally:
                task.completed_at = utc_now_iso()
                self.cache.save(self.tasks.values())
                self._notify_listeners(task)
                self._sync_to_shared_log(task)
                self._queue.task_done()

    # ------------------------------------------------------------------ #
    # Helpers for UI / other components
    # ------------------------------------------------------------------ #
    def has_pending_tasks(self) -> bool:
        return any(task.status in ("pending", "running") for task in self.tasks.values())

    def get_tasks(self) -> Iterable[WriteTask]:
        return list(self.tasks.values())

    def wait_until_empty(self, check_interval: float = 1.0):
        """供自动模式使用：阻塞直到队列清空或停止。"""
        while self.has_pending_tasks() and not self._stop_event.is_set():
            self._stop_event.wait(timeout=check_interval)

    def shutdown(self):
        self._stop_event.set()
        self._worker_thread.join(timeout=2)

    def register_listener(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def _notify_listeners(self, task: WriteTask):
        for callback in list(self._listeners):
            try:
                callback(task)
            except Exception as e:
                print(f"[WriteTaskManager] listener 调用失败: {e}")

    def _sync_to_shared_log(self, task: WriteTask):
        """
        将任务状态同步到公共盘 registry.db 的全局写入任务日志表。
        - 仅在registry模块可用且已启用时执行
        - 所有异常吞掉，确保不影响主流程
        """
        if not registry_hooks or not _shared_log_upsert_task:
            return
        try:
            cfg = registry_hooks._cfg()
            if not cfg.get("registry_enabled", True):
                return
            db_path = cfg.get("registry_db_path")
            if not db_path:
                return
            wal = bool(cfg.get("registry_wal", False))
            from registry.db import get_connection, close_connection_after_use

            conn = get_connection(db_path, wal)
            try:
                _shared_log_upsert_task(conn, task)
            finally:
                close_connection_after_use()
        except Exception as e:
            print(f"[WriteTaskManager] 同步全局任务日志失败(已忽略): {e}")


# ---------------------------------------------------------------------- #
# Singleton helpers
# ---------------------------------------------------------------------- #
def get_write_task_manager() -> WriteTaskManager:
    global _manager_singleton
    with _singleton_lock:
        if _manager_singleton is None:
            _manager_singleton = WriteTaskManager()
            try:
                from .pending_cache import get_pending_cache

                cache = get_pending_cache()
                _manager_singleton.register_listener(cache.on_task_status_changed)
            except Exception as e:
                print(f"[WriteTaskManager] 注册PendingCache监听失败: {e}")
        return _manager_singleton


def reset_write_task_manager_for_tests():
    global _manager_singleton
    with _singleton_lock:
        if _manager_singleton is not None:
            _manager_singleton.shutdown()
            _manager_singleton = None

