"""
数据模型定义

定义任务状态、事件类型等枚举和数据类。
"""
from dataclasses import dataclass
from typing import Optional

class Status:
    """任务状态枚举"""
    OPEN = "open"
    COMPLETED = "completed"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"

class EventType:
    """事件类型枚举"""
    PROCESS_DONE = "process_done"
    EXPORT_DONE = "export_done"
    RESPONSE_WRITTEN = "response_written"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"
    ASSIGNED = "assigned"

@dataclass
class TaskKey:
    """
    任务唯一标识
    
    用于定位和查询任务的关键字段组合
    """
    file_type: int
    project_id: str
    interface_id: str
    source_file: str
    row_index: int

@dataclass
class Task:
    """
    任务完整信息
    
    包含任务的所有字段和状态
    """
    id: str
    file_type: int
    project_id: str
    interface_id: str
    source_file: str
    row_index: int
    department: str
    interface_time: str
    status: str
    completed_at: Optional[str]
    confirmed_at: Optional[str]
    first_seen_at: str
    last_seen_at: str
    missing_since: Optional[str]
    archive_reason: Optional[str]

@dataclass
class Event:
    """
    事件记录
    
    记录系统中发生的各类操作
    """
    id: Optional[int]
    ts: str
    event: str
    file_type: Optional[int]
    project_id: Optional[str]
    interface_id: Optional[str]
    source_file: Optional[str]
    row_index: Optional[int]
    extra: Optional[str]  # JSON字符串

