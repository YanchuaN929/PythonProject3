from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class WriteTask:
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    submitted_by: str
    description: str
    submitted_at: str = field(default_factory=utc_now_iso)
    status: str = "pending"  # pending | running | completed | failed
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "submitted_by": self.submitted_by,
            "description": self.description,
            "submitted_at": self.submitted_at,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WriteTask":
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            payload=data.get("payload", {}),
            submitted_by=data.get("submitted_by", "未知用户"),
            description=data.get("description", ""),
            submitted_at=data.get("submitted_at", utc_now_iso()),
            status=data.get("status", "pending"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )

