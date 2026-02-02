"""
写入任务执行器。

为了避免循环依赖，这里在函数内部才导入对应模块。
"""
from typing import Any, Dict


def execute_assignment_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行指派写入任务。"""
    from services.distribution import save_assignments_batch

    assignments = payload.get("assignments", [])
    return save_assignments_batch(assignments)


def execute_response_task(payload: Dict[str, Any]) -> bool:
    """执行回文单号写入任务。"""
    from ui.input_handler import write_response_to_excel

    ok = write_response_to_excel(
        file_path=payload["file_path"],
        file_type=payload["file_type"],
        row_index=payload["row_index"],
        response_number=payload["response_number"],
        user_name=payload["user_name"],
        project_id=payload["project_id"],
        source_column=payload.get("source_column"),
    )
    if not ok:
        return False

    # 关键：同步写入 registry.db（状态/完成人/完成时间/回文单号/待审查等）
    try:
        from registry import hooks as registry_hooks
    except Exception:
        registry_hooks = None

    if registry_hooks:
        # 确保 Registry 使用当前文件所在目录，避免误判维护模式
        try:
            file_path = str(payload.get("file_path", "") or "").strip()
            if file_path:
                import os
                registry_hooks.set_data_folder(os.path.dirname(file_path))
        except Exception as e:
            print(f"[Registry] 设置数据目录失败(已忽略): {e}")
        interface_id = str(payload.get("interface_id", "") or "").strip()
        # 去除角色后缀：S-XXX(...)->S-XXX
        if interface_id.endswith(")") and "(" in interface_id:
            import re

            interface_id = re.sub(r"\([^)]*\)$", "", interface_id).strip()
        registry_hooks.on_response_written(
            file_type=payload["file_type"],
            file_path=payload["file_path"],
            row_index=payload["row_index"],
            interface_id=interface_id,
            response_number=payload["response_number"],
            user_name=payload["user_name"],
            project_id=payload["project_id"],
            source_column=payload.get("source_column"),
            role=payload.get("role"),
        )
    return True


EXECUTOR_MAP = {
    "assignment": execute_assignment_task,
    "response": execute_response_task,
}


def get_executor(task_type: str):
    executor = EXECUTOR_MAP.get(task_type)
    if not executor:
        raise ValueError(f"未知的写入任务类型: {task_type}")
    return executor

