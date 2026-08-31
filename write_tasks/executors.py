"""
写入任务执行器。

为了避免循环依赖，这里在函数内部才导入对应模块。
"""
from typing import Any, Dict


def execute_assignment_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """执行指派写入任务。"""
    from services.distribution import save_assignments_batch

    # 【路径统一】确保 data_folder 已设置
    try:
        from registry import hooks as registry_hooks
        data_folder = str(payload.get("data_folder", "") or "").strip()
        if data_folder:
            registry_hooks.set_data_folder(data_folder)
    except Exception:
        pass

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
        interface_id=payload.get("interface_id"),
        return_details=True,
    )
    if not ok:
        return False

    # 文件更新后若接口行发生过唯一重定位，后续Registry必须使用实际写入行号。
    actual_row_index = getattr(ok, "row_index", None)
    if actual_row_index is not None:
        payload["row_index"] = int(actual_row_index)

    # 关键：同步写入 registry.db（状态/完成人/完成时间/回文单号/待审查等）
    try:
        from registry import hooks as registry_hooks
    except Exception:
        registry_hooks = None

    if registry_hooks:
        # 【修复】不再从文件路径推导数据目录，应由主程序在启动/刷新时统一设置
        # 如果 _DATA_FOLDER 尚未设置，则尝试从 payload 中获取（如果调用方传入了 data_folder）
        try:
            data_folder = str(payload.get("data_folder", "") or "").strip()
            if data_folder:
                registry_hooks.set_data_folder(data_folder)
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


def execute_fu_completion_task(payload: Dict[str, Any]) -> bool:
    """Write the FU actual date and persist the completion in Registry."""
    from ui.input_handler import write_fu_completion_to_excel

    ok = write_fu_completion_to_excel(
        payload["file_path"],
        payload["row_index"],
        payload.get("completion_date"),
        interface_id=payload.get("interface_id"),
        return_details=True,
    )
    if not ok:
        return False

    actual_row_index = getattr(ok, "row_index", None)
    if actual_row_index is not None:
        payload["row_index"] = int(actual_row_index)

    # Excel 已写入并校验成功后即视为本写任务成功。
    # Registry 是后续状态同步，失败时只记录日志，不能触发 Excel 重写。
    try:
        from registry import hooks as registry_hooks

        data_folder = str(payload.get("data_folder", "") or "").strip()
        if data_folder:
            registry_hooks.set_data_folder(data_folder)
        registry_ok = registry_hooks.on_fu_completed(
            file_path=payload["file_path"],
            row_index=payload["row_index"],
            interface_id=str(payload.get("interface_id", "") or "").strip(),
            actual_date=payload.get("completion_date", ""),
            user_name=payload.get("user_name", ""),
            project_id=payload.get("project_id", ""),
            role=payload.get("role"),
        )
        if registry_ok is False:
            print("[Registry] FU状态同步失败；Excel写入已成功，不重试Excel")
    except Exception as exc:
        print("[Registry] FU状态同步异常；Excel写入已成功，不重试Excel: {}".format(exc))
    return True


EXECUTOR_MAP = {
    "assignment": execute_assignment_task,
    "response": execute_response_task,
    "fu_completion": execute_fu_completion_task,
}


def get_executor(task_type: str):
    executor = EXECUTOR_MAP.get(task_type)
    if not executor:
        raise ValueError(f"未知的写入任务类型: {task_type}")
    return executor

