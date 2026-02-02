#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指派记忆模块

功能：
1. 记录每次指派的业务标识（file_type|project_id|interface_id）和指派人
2. 下次处理Excel时，对于责任人为空但业务标识匹配的接口自动填充指派人

存储位置：%LOCALAPPDATA%\\InterfaceFilter\\assignment_memory.json
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Dict, Optional


class AssignmentMemory:
    """指派记忆管理器"""

    def __init__(self, storage_path: Optional[Path] = None):
        """
        初始化指派记忆管理器

        参数:
            storage_path: 存储文件路径（可选，默认为 LOCALAPPDATA/InterfaceFilter/assignment_memory.json）
        """
        if storage_path is None:
            local_appdata = os.environ.get("LOCALAPPDATA", "")
            if not local_appdata:
                local_appdata = os.path.expanduser("~")
            storage_dir = Path(local_appdata) / "InterfaceFilter"
            storage_path = storage_dir / "assignment_memory.json"

        self.storage_path = Path(storage_path)
        self._lock = threading.RLock()  # 使用可重入锁，避免嵌套调用死锁
        self._disabled = False
        self._disabled_reason = ""
        self._warned = False
        self._memories: Dict[str, str] = {}

        # 确保目录存在
        try:
            os.makedirs(self.storage_path.parent, exist_ok=True)
        except PermissionError as e:
            self._disabled = True
            self._disabled_reason = str(e)
        except Exception as e:
            self._disabled = True
            self._disabled_reason = str(e)

        # 加载已有记忆
        self._load()

    def _make_key(self, file_type: int, project_id: str, interface_id: str) -> str:
        """
        生成记忆key

        参数:
            file_type: 文件类型（1-6）
            project_id: 项目号
            interface_id: 接口号

        返回:
            str: 格式化的key，如 "1|1907|HQ-TA-3999"
        """
        # 规范化接口号：去除角色后缀
        normalized_interface_id = self._normalize_interface_id(interface_id)
        return f"{file_type}|{project_id}|{normalized_interface_id}"

    def _normalize_interface_id(self, interface_id: str) -> str:
        """
        规范化接口号，去除角色后缀

        参数:
            interface_id: 原始接口号，可能包含 "(设计人员)" 等后缀

        返回:
            str: 去除后缀后的接口号
        """
        if not interface_id:
            return ""
        # 去除括号及其内容，如 "HQ-TA-3999(设计人员)" -> "HQ-TA-3999"
        normalized = re.sub(r"\([^)]*\)$", "", str(interface_id).strip())
        return normalized.strip()

    def _load(self) -> None:
        """从文件加载记忆"""
        if self._disabled:
            return

        if not self.storage_path.exists():
            self._memories = {}
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self._memories = data.get("memories", {})
        except Exception as e:
            print(f"[AssignmentMemory] 加载失败，已忽略: {e}")
            self._memories = {}

    def _save(self) -> None:
        """保存记忆到文件"""
        if self._disabled:
            if not self._warned:
                self._warned = True
                print(f"[AssignmentMemory] 持久化已禁用：{self._disabled_reason}")
            return

        payload = {"memories": self._memories}
        with self._lock:
            tmp_path = self.storage_path.with_suffix(".tmp")
            try:
                with tmp_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                tmp_path.replace(self.storage_path)
            except PermissionError as e:
                self._disabled = True
                self._disabled_reason = str(e)
                if not self._warned:
                    self._warned = True
                    print(f"[AssignmentMemory] 写入失败，已降级为仅内存：{e}")
            except Exception as e:
                self._disabled = True
                self._disabled_reason = str(e)
                if not self._warned:
                    self._warned = True
                    print(f"[AssignmentMemory] 写入失败，已降级为仅内存：{e}")

    def save_memory(
        self, file_type: int, project_id: str, interface_id: str, assigned_name: str
    ) -> None:
        """
        保存单条指派记忆

        参数:
            file_type: 文件类型（1-6）
            project_id: 项目号
            interface_id: 接口号
            assigned_name: 指派人姓名
        """
        if not assigned_name or not assigned_name.strip():
            return

        key = self._make_key(file_type, project_id, interface_id)
        with self._lock:
            self._memories[key] = assigned_name.strip()
        self._save()

    def get_memory(
        self, file_type: int, project_id: str, interface_id: str
    ) -> Optional[str]:
        """
        获取指派记忆

        参数:
            file_type: 文件类型（1-6）
            project_id: 项目号
            interface_id: 接口号

        返回:
            str: 指派人姓名，如果没有记忆则返回 None
        """
        key = self._make_key(file_type, project_id, interface_id)
        return self._memories.get(key)

    def batch_save_memories(self, assignments: list) -> int:
        """
        批量保存指派记忆

        参数:
            assignments: 指派列表，每项包含:
                {
                    'file_type': int,
                    'project_id': str,
                    'interface_id': str,
                    'assigned_name': str
                }

        返回:
            int: 成功保存的记忆数量
        """
        count = 0
        with self._lock:
            for assignment in assignments:
                file_type = assignment.get("file_type")
                project_id = assignment.get("project_id", "")
                interface_id = assignment.get("interface_id", "")
                assigned_name = assignment.get("assigned_name", "")

                if not assigned_name or not assigned_name.strip():
                    continue

                key = self._make_key(file_type, project_id, interface_id)
                self._memories[key] = assigned_name.strip()
                count += 1

        if count > 0:
            self._save()

        return count

    def clear_memory(
        self, file_type: int, project_id: str, interface_id: str
    ) -> bool:
        """
        清除单条指派记忆

        参数:
            file_type: 文件类型（1-6）
            project_id: 项目号
            interface_id: 接口号

        返回:
            bool: 是否成功清除（如果记忆存在）
        """
        key = self._make_key(file_type, project_id, interface_id)
        with self._lock:
            if key in self._memories:
                del self._memories[key]
                self._save()
                return True
        return False

    def clear_all(self) -> None:
        """清除所有指派记忆"""
        with self._lock:
            self._memories = {}
        self._save()

    def get_all_memories(self) -> Dict[str, str]:
        """
        获取所有指派记忆（用于调试）

        返回:
            dict: 所有记忆的副本
        """
        return dict(self._memories)

    def get_memory_count(self) -> int:
        """获取记忆数量"""
        return len(self._memories)


# 模块级单例
_memory_instance: Optional[AssignmentMemory] = None
_memory_lock = threading.Lock()


def get_assignment_memory() -> AssignmentMemory:
    """
    获取全局指派记忆单例

    返回:
        AssignmentMemory 实例
    """
    global _memory_instance

    with _memory_lock:
        if _memory_instance is None:
            _memory_instance = AssignmentMemory()
        return _memory_instance


# 便捷函数
def save_memory(
    file_type: int, project_id: str, interface_id: str, assigned_name: str
) -> None:
    """保存单条指派记忆（便捷函数）"""
    get_assignment_memory().save_memory(file_type, project_id, interface_id, assigned_name)


def get_memory(file_type: int, project_id: str, interface_id: str) -> Optional[str]:
    """获取指派记忆（便捷函数）"""
    return get_assignment_memory().get_memory(file_type, project_id, interface_id)


def batch_save_memories(assignments: list) -> int:
    """批量保存指派记忆（便捷函数）"""
    return get_assignment_memory().batch_save_memories(assignments)


def clear_memory(file_type: int, project_id: str, interface_id: str) -> bool:
    """清除单条指派记忆（便捷函数）"""
    return get_assignment_memory().clear_memory(file_type, project_id, interface_id)
