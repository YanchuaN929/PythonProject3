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
        os.makedirs(self.state_path.parent, exist_ok=True)
        self._lock = threading.Lock()

    def load(self) -> List[WriteTask]:
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
        payload = {"tasks": [task.to_dict() for task in tasks]}
        with self._lock:
            tmp_path = self.state_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.state_path)

    def to_dict(self, tasks: Dict[str, WriteTask]):
        return {"tasks": [task.to_dict() for task in tasks.values()]}

