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
REGISTRY_RETRY_DELAYS = (5, 15, 30, 60)


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
        # 【路径统一】获取当前的 data_folder
        data_folder = None
        try:
            from registry import hooks as registry_hooks
            data_folder = registry_hooks.get_data_folder()
        except Exception:
            pass
        payload = {"assignments": assignments, "data_folder": data_folder}
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
        data_folder: Optional[str] = None,
        description: str,
    ) -> WriteTask:
        # 【路径统一】如果未传入 data_folder，尝试从 registry hooks 获取当前设置的路径
        if not data_folder:
            try:
                from registry import hooks as registry_hooks
                data_folder = registry_hooks.get_data_folder()
            except Exception:
                pass
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
            "data_folder": data_folder,
        }
        return self._submit("response", payload, user_name or "未知用户", description)

    def submit_response_batch_task(
        self,
        *,
        items,
        user_name: str,
        data_folder: Optional[str] = None,
        description: str,
    ) -> WriteTask:
        """提交文件1-6批量回文；执行器按源工作簿分组并一次保存。"""
        if not data_folder:
            try:
                from registry import hooks as registry_hooks
                data_folder = registry_hooks.get_data_folder()
            except Exception:
                pass
        normalized_items = [dict(item or {}) for item in (items or [])]
        if not normalized_items:
            raise ValueError("批量回文任务不能为空")
        payload = {
            "batch_id": str(uuid.uuid4()),
            "items": normalized_items,
            "user_name": user_name,
            "data_folder": data_folder,
        }
        return self._submit("response_batch", payload, user_name or "未知用户", description)

    def submit_fu_completion_task(
        self,
        *,
        file_path: str,
        row_index: int,
        interface_id: str,
        user_name: str,
        project_id: str,
        completion_date: str,
        role: Optional[str] = None,
        data_folder: Optional[str] = None,
        description: str,
    ) -> WriteTask:
        if not data_folder:
            try:
                from registry import hooks as registry_hooks
                data_folder = registry_hooks.get_data_folder()
            except Exception:
                pass
        payload = {
            "file_path": file_path,
            "file_type": 7,
            "row_index": row_index,
            "interface_id": interface_id,
            "user_name": user_name,
            "project_id": project_id,
            "completion_date": completion_date,
            "role": role,
            "data_folder": data_folder,
        }
        return self._submit("fu_completion", payload, user_name or "未知用户", description)

    def submit_fu_completion_batch_task(
        self,
        *,
        items,
        user_name: str,
        data_folder: Optional[str] = None,
        description: str,
    ) -> WriteTask:
        """提交文件7批量完成；执行器按源工作簿分组并一次保存。"""
        if not data_folder:
            try:
                from registry import hooks as registry_hooks
                data_folder = registry_hooks.get_data_folder()
            except Exception:
                pass
        normalized_items = [dict(item or {}) for item in (items or [])]
        if not normalized_items:
            raise ValueError("批量FU完成任务不能为空")
        payload = {
            "batch_id": str(uuid.uuid4()),
            "items": normalized_items,
            "user_name": user_name,
            "data_folder": data_folder,
        }
        return self._submit("fu_completion_batch", payload, user_name or "未知用户", description)

    def submit_registry_sync_task(
        self,
        compensation: dict,
        *,
        submitted_by: str,
        origin_task_id: str,
    ) -> WriteTask:
        """提交只写 Registry 的持久化补偿任务，绝不重新进入 Excel 执行器。"""
        task = self._build_registry_sync_task(
            compensation,
            submitted_by=submitted_by,
            origin_task_id=origin_task_id,
        )
        self.tasks[task.task_id] = task
        self.cache.save(self.tasks.values())
        self._sync_to_shared_log(task)
        self._queue.put(task.task_id)
        return task

    @staticmethod
    def _build_registry_sync_task(
        compensation: dict,
        *,
        submitted_by: str,
        origin_task_id: str,
    ) -> WriteTask:
        """构造补偿任务；由调用方决定何时与原任务一起持久化和入队。"""
        payload = dict(compensation or {})
        payload["origin_task_id"] = origin_task_id
        payload.setdefault("_retry_count", 0)
        registry_payload = payload.get("registry_payload") or {}
        interface_id = str(registry_payload.get("interface_id", "") or "").strip()
        operation_name = {
            "response_written": "回文状态",
            "fu_completed": "FU完成状态",
            "assigned": "指派状态",
        }.get(str(payload.get("operation", "") or ""), "Registry状态")
        description = f"{operation_name}补偿"
        if interface_id:
            description += f" {interface_id}"
        return WriteTask(
            task_id=str(uuid.uuid4()),
            task_type="registry_sync",
            payload=payload,
            submitted_by=submitted_by or "未知用户",
            description=description,
        )

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

            retry_delay = None
            compensation_tasks = []
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

                compensations = []
                if isinstance(result, dict):
                    compensation = result.get("registry_compensation")
                    if compensation:
                        compensations.append(compensation)
                    compensations.extend(result.get("registry_compensations") or [])
                result_message = ""
                if isinstance(result, dict):
                    result_message = str(result.get("result_message", "") or "").strip()
                if compensations:
                    # 先在内存中同时设置“原任务已完成”和“补偿任务待执行”，
                    # 再由 finally 一次写入状态文件。这样异常退出后只会恢复
                    # Registry 补偿，不会把原 Excel 任务重新放回队列。
                    compensation_tasks = [
                        self._build_registry_sync_task(
                            compensation_item,
                            submitted_by=task.submitted_by,
                            origin_task_id=task.task_id,
                        )
                        for compensation_item in compensations
                    ]
                    for compensation_task in compensation_tasks:
                        self.tasks[compensation_task.task_id] = compensation_task
                    compensation_message = (
                        f"Excel写入已成功；{len(compensation_tasks)}条Registry同步已转补偿队列"
                    )
                    task.error = "；".join(
                        text for text in (result_message, compensation_message) if text
                    )
                else:
                    task.error = result_message or None
                task.status = "completed"
            except Exception as e:
                if task.task_type == "registry_sync":
                    retry_count = int((task.payload or {}).get("_retry_count", 0) or 0) + 1
                    task.payload["_retry_count"] = retry_count
                    task.status = "pending"
                    task.error = str(e)
                    task.completed_at = None
                    retry_delay = REGISTRY_RETRY_DELAYS[
                        min(retry_count - 1, len(REGISTRY_RETRY_DELAYS) - 1)
                    ]
                    print(
                        f"[Registry补偿] 第{retry_count}次同步失败，"
                        f"{retry_delay}秒后仅重试Registry: {e}"
                    )
                else:
                    task.status = "failed"
                    task.error = str(e)
            finally:
                if task.status in ("completed", "failed"):
                    task.completed_at = utc_now_iso()
                self.cache.save(self.tasks.values())
                self._notify_listeners(task)
                self._sync_to_shared_log(task)
                self._queue.task_done()
            for compensation_task in compensation_tasks:
                self._sync_to_shared_log(compensation_task)
                self._queue.put(compensation_task.task_id)
            if retry_delay is not None:
                self._schedule_registry_retry(task.task_id, retry_delay)

    def _schedule_registry_retry(self, task_id: str, delay_seconds: float) -> None:
        """延迟重新入队；等待期间不占用写入工作线程。"""
        def delayed_requeue():
            if self._stop_event.wait(timeout=max(0.0, float(delay_seconds))):
                return
            task = self.tasks.get(task_id)
            if task and task.task_type == "registry_sync" and task.status == "pending":
                self._queue.put(task_id)

        thread = threading.Thread(target=delayed_requeue, daemon=True)
        thread.start()

    # ------------------------------------------------------------------ #
    # Helpers for UI / other components
    # ------------------------------------------------------------------ #
    def has_pending_tasks(self, include_registry_sync: bool = False) -> bool:
        """Registry补偿不阻塞新一轮Excel处理，两类任务使用彼此独立的等待语义。"""
        return any(
            task.status in ("pending", "running")
            and (include_registry_sync or task.task_type != "registry_sync")
            for task in self.tasks.values()
        )

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
            from registry.db import open_isolated_connection

            conn = open_isolated_connection(db_path, wal)
            try:
                _shared_log_upsert_task(conn, task)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
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

