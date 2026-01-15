from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Dict, Iterable, List

from .models import WriteTask


class WriteTaskCache:
    """负责写入任务的持久化记录（轻量级 JSON 文件）。"""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._disabled = False
        self._disabled_reason = ""
        self._warned = False
        try:
            os.makedirs(self.state_path.parent, exist_ok=True)
        except PermissionError as e:
            # 关键：开机自启/安装目录无写权限时，不能让程序启动直接崩溃
            self._disabled = True
            self._disabled_reason = str(e)
        except Exception as e:
            self._disabled = True
            self._disabled_reason = str(e)
        self._lock = threading.Lock()

    def load(self) -> List[WriteTask]:
        if self._disabled:
            return []
        if not self.state_path.exists():
            return []
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            tasks = data.get("tasks", [])
            return [WriteTask.from_dict(item) for item in tasks]
        except Exception as e:
            # 如果文件损坏，记录并返回空列表，避免阻塞主流程
            print(f"[WriteTaskCache] 加载失败，已忽略: {e}")
            return []

    def save(self, tasks: Iterable[WriteTask]) -> None:
        if self._disabled:
            if not self._warned:
                self._warned = True
                print(f"[WriteTaskCache] 持久化已禁用（权限/环境问题）：{self._disabled_reason}")
            return
        payload = {"tasks": [task.to_dict() for task in tasks]}
        with self._lock:
            tmp_path = self.state_path.with_suffix(".tmp")
            try:
                with tmp_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                tmp_path.replace(self.state_path)
            except PermissionError as e:
                # 运行中权限变化/目录不可写：降级为内存，不阻塞主流程
                self._disabled = True
                self._disabled_reason = str(e)
                if not self._warned:
                    self._warned = True
                    print(f"[WriteTaskCache] 写入失败，已降级为仅内存（权限不足）：{e}")
            except Exception as e:
                # 其他写入失败同样降级（避免影响主流程）
                self._disabled = True
                self._disabled_reason = str(e)
                if not self._warned:
                    self._warned = True
                    print(f"[WriteTaskCache] 写入失败，已降级为仅内存：{e}")

    def to_dict(self, tasks: Dict[str, WriteTask]):
        return {"tasks": [task.to_dict() for task in tasks.values()]}

