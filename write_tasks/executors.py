"""
写入任务执行器。

为了避免循环依赖，这里在函数内部才导入对应模块。
"""
from typing import Any, Dict


def _registry_compensation_result(operation: str, registry_payload: Dict[str, Any], error) -> Dict[str, Any]:
    """Return an Excel-success result that asks the manager for Registry-only compensation."""
    return {
        "success": True,
        "registry_compensation": {
            "operation": operation,
            "registry_payload": dict(registry_payload),
            "data_folder": registry_payload.get("data_folder"),
            "origin_error": str(error or "Registry同步返回失败"),
        },
    }


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
    result = save_assignments_batch(assignments)
    registry_compensations = []
    for failure in (result.get("registry_failures") or []):
        failure = failure or {}
        registry_payload = dict(failure.get("registry_payload") or {})
        registry_payload["data_folder"] = payload.get("data_folder")
        registry_compensations.append({
            "operation": "assigned",
            "registry_payload": registry_payload,
            "data_folder": payload.get("data_folder"),
            "origin_error": str(failure.get("origin_error") or "Registry指派同步失败"),
        })
    if registry_compensations:
        result["registry_compensations"] = registry_compensations
    return result


def execute_response_task(payload: Dict[str, Any]):
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

    interface_id = str(payload.get("interface_id", "") or "").strip()
    if interface_id.endswith(")") and "(" in interface_id:
        import re

        interface_id = re.sub(r"\([^)]*\)$", "", interface_id).strip()
    registry_payload = {
        "file_type": payload["file_type"],
        "file_path": payload["file_path"],
        "row_index": payload["row_index"],
        "interface_id": interface_id,
        "response_number": payload["response_number"],
        "user_name": payload["user_name"],
        "project_id": payload["project_id"],
        "source_column": payload.get("source_column"),
        "role": payload.get("role"),
        "data_folder": payload.get("data_folder"),
    }

    # 关键：同步写入 registry.db（状态/完成人/完成时间/回文单号/待审查等）
    try:
        from registry import hooks as registry_hooks
    except Exception as exc:
        return _registry_compensation_result("response_written", registry_payload, exc)

    if registry_hooks:
        # 【修复】不再从文件路径推导数据目录，应由主程序在启动/刷新时统一设置
        # 如果 _DATA_FOLDER 尚未设置，则尝试从 payload 中获取（如果调用方传入了 data_folder）
        try:
            data_folder = str(payload.get("data_folder", "") or "").strip()
            if data_folder:
                registry_hooks.set_data_folder(data_folder)
        except Exception as e:
            print(f"[Registry] 设置数据目录失败(已忽略): {e}")
        hook_payload = {
            key: value for key, value in registry_payload.items()
            if key != "data_folder"
        }
        try:
            registry_ok = registry_hooks.on_response_written(**hook_payload)
            if registry_ok is not True:
                print("[Registry] 回文状态同步失败；Excel写入已成功，转入Registry补偿队列")
                return _registry_compensation_result(
                    "response_written", registry_payload, "Registry同步返回False"
                )
        except Exception as exc:
            print(f"[Registry] 回文状态同步异常；Excel写入已成功，转入Registry补偿队列: {exc}")
            return _registry_compensation_result("response_written", registry_payload, exc)
    return True


def _response_registry_payload(item: Dict[str, Any], data_folder: str = "") -> Dict[str, Any]:
    import re

    interface_id = str(item.get("interface_id", "") or "").strip()
    if interface_id.endswith(")") and "(" in interface_id:
        interface_id = re.sub(r"\([^)]*\)$", "", interface_id).strip()
    return {
        "file_type": int(item.get("file_type", 0) or 0),
        "file_path": item.get("file_path", ""),
        "row_index": int(item.get("row_index", 0) or 0),
        "interface_id": interface_id,
        "response_number": str(item.get("response_number", "") or ""),
        "user_name": item.get("user_name", ""),
        "project_id": str(item.get("project_id", "") or ""),
        "source_column": item.get("source_column"),
        "role": item.get("role"),
        "data_folder": item.get("data_folder") or data_folder,
    }


def _fu_registry_payload(item: Dict[str, Any], data_folder: str = "") -> Dict[str, Any]:
    return {
        "file_path": item.get("file_path", ""),
        "row_index": int(item.get("row_index", 0) or 0),
        "interface_id": str(item.get("interface_id", "") or "").strip(),
        "actual_date": str(item.get("completion_date", "") or ""),
        "user_name": item.get("user_name", ""),
        "project_id": str(item.get("project_id", "") or ""),
        "role": item.get("role"),
        "data_folder": item.get("data_folder") or data_folder,
    }


def _batch_result_summary(result: Dict[str, Any], total: int, noun: str) -> str:
    success_count = int(result.get("success_count", 0) or 0)
    failed_count = len(result.get("failed_tasks") or [])
    already_count = int(result.get("already_present_count", 0) or 0)
    parts = [f"批量{noun}{success_count}/{total}条成功"]
    if already_count:
        parts.append(f"其中{already_count}条原值已相同")
    if failed_count:
        parts.append(f"{failed_count}条失败")
    return "，".join(parts)


def execute_response_batch_task(payload: Dict[str, Any]):
    """批量回文：工作簿分组写Excel，成功项再逐条同步Registry。"""
    from services.batch_response import write_responses_batch

    items = [dict(item or {}) for item in (payload.get("items") or [])]
    if not items:
        raise ValueError("批量回文任务没有可执行项")
    data_folder = str(payload.get("data_folder", "") or "").strip()
    user_name = str(payload.get("user_name", "") or "").strip()
    for item in items:
        item.setdefault("user_name", user_name)
        item.setdefault("data_folder", data_folder)

    result = write_responses_batch(items)
    result["total_count"] = len(items)
    payload["_result"] = result
    if int(result.get("success_count", 0) or 0) <= 0:
        failures = result.get("failed_tasks") or []
        first_reason = str((failures[0] or {}).get("reason", "") or "") if failures else "没有成功项"
        raise RuntimeError(f"批量回文全部失败：{first_reason}")

    compensations = []
    successful_items = result.get("successful_items") or []
    try:
        from registry import hooks as registry_hooks

        if data_folder:
            registry_hooks.set_data_folder(data_folder)
        for item in successful_items:
            registry_payload = _response_registry_payload(item, data_folder)
            hook_payload = {key: value for key, value in registry_payload.items() if key != "data_folder"}
            try:
                registry_ok = registry_hooks.on_response_written(**hook_payload)
                if registry_ok is not True:
                    raise RuntimeError("Registry同步返回False")
            except Exception as exc:
                compensations.append({
                    "operation": "response_written",
                    "registry_payload": registry_payload,
                    "data_folder": registry_payload.get("data_folder"),
                    "origin_error": str(exc),
                })
    except Exception as exc:
        existing_keys = {
            (
                str((item.get("registry_payload") or {}).get("file_path", "")),
                int((item.get("registry_payload") or {}).get("row_index", 0) or 0),
                str((item.get("registry_payload") or {}).get("interface_id", "")),
            )
            for item in compensations
        }
        for item in successful_items:
            registry_payload = _response_registry_payload(item, data_folder)
            key = (
                str(registry_payload.get("file_path", "")),
                int(registry_payload.get("row_index", 0) or 0),
                str(registry_payload.get("interface_id", "")),
            )
            if key in existing_keys:
                continue
            compensations.append({
                "operation": "response_written",
                "registry_payload": registry_payload,
                "data_folder": registry_payload.get("data_folder"),
                "origin_error": str(exc),
            })

    if compensations:
        result["registry_compensations"] = compensations
    result["result_message"] = _batch_result_summary(result, len(items), "回文")
    return result


def execute_fu_completion_task(payload: Dict[str, Any]):
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
    # Registry 是后续状态同步，失败时转独立补偿任务，不能触发 Excel 重写。
    try:
        from registry import hooks as registry_hooks

        data_folder = str(payload.get("data_folder", "") or "").strip()
        if data_folder:
            registry_hooks.set_data_folder(data_folder)
        registry_payload = {
            "file_path": payload["file_path"],
            "row_index": payload["row_index"],
            "interface_id": str(payload.get("interface_id", "") or "").strip(),
            "actual_date": payload.get("completion_date", ""),
            "user_name": payload.get("user_name", ""),
            "project_id": payload.get("project_id", ""),
            "role": payload.get("role"),
            "data_folder": payload.get("data_folder"),
        }
        hook_payload = {
            key: value for key, value in registry_payload.items()
            if key != "data_folder"
        }
        registry_ok = registry_hooks.on_fu_completed(**hook_payload)
        if registry_ok is not True:
            print("[Registry] FU状态同步失败；Excel写入已成功，转入Registry补偿队列")
            return _registry_compensation_result(
                "fu_completed", registry_payload, "Registry同步返回False"
            )
    except Exception as exc:
        registry_payload = {
            "file_path": payload["file_path"],
            "row_index": payload["row_index"],
            "interface_id": str(payload.get("interface_id", "") or "").strip(),
            "actual_date": payload.get("completion_date", ""),
            "user_name": payload.get("user_name", ""),
            "project_id": payload.get("project_id", ""),
            "role": payload.get("role"),
            "data_folder": payload.get("data_folder"),
        }
        print("[Registry] FU状态同步异常；Excel写入已成功，转入Registry补偿队列: {}".format(exc))
        return _registry_compensation_result("fu_completed", registry_payload, exc)
    return True


def execute_fu_completion_batch_task(payload: Dict[str, Any]):
    """批量FU完成：工作簿分组写Excel，成功项再逐条同步Registry。"""
    from services.batch_response import write_fu_completions_batch

    items = [dict(item or {}) for item in (payload.get("items") or [])]
    if not items:
        raise ValueError("批量FU完成任务没有可执行项")
    data_folder = str(payload.get("data_folder", "") or "").strip()
    user_name = str(payload.get("user_name", "") or "").strip()
    for item in items:
        item.setdefault("user_name", user_name)
        item.setdefault("data_folder", data_folder)
        item["file_type"] = 7

    result = write_fu_completions_batch(items)
    result["total_count"] = len(items)
    payload["_result"] = result
    if int(result.get("success_count", 0) or 0) <= 0:
        failures = result.get("failed_tasks") or []
        first_reason = str((failures[0] or {}).get("reason", "") or "") if failures else "没有成功项"
        raise RuntimeError(f"批量FU完成全部失败：{first_reason}")

    compensations = []
    successful_items = result.get("successful_items") or []
    try:
        from registry import hooks as registry_hooks

        if data_folder:
            registry_hooks.set_data_folder(data_folder)
        for item in successful_items:
            registry_payload = _fu_registry_payload(item, data_folder)
            hook_payload = {key: value for key, value in registry_payload.items() if key != "data_folder"}
            try:
                registry_ok = registry_hooks.on_fu_completed(**hook_payload)
                if registry_ok is not True:
                    raise RuntimeError("Registry同步返回False")
            except Exception as exc:
                compensations.append({
                    "operation": "fu_completed",
                    "registry_payload": registry_payload,
                    "data_folder": registry_payload.get("data_folder"),
                    "origin_error": str(exc),
                })
    except Exception as exc:
        existing_keys = {
            (
                str((item.get("registry_payload") or {}).get("file_path", "")),
                int((item.get("registry_payload") or {}).get("row_index", 0) or 0),
                str((item.get("registry_payload") or {}).get("interface_id", "")),
            )
            for item in compensations
        }
        for item in successful_items:
            registry_payload = _fu_registry_payload(item, data_folder)
            key = (
                str(registry_payload.get("file_path", "")),
                int(registry_payload.get("row_index", 0) or 0),
                str(registry_payload.get("interface_id", "")),
            )
            if key in existing_keys:
                continue
            compensations.append({
                "operation": "fu_completed",
                "registry_payload": registry_payload,
                "data_folder": registry_payload.get("data_folder"),
                "origin_error": str(exc),
            })

    if compensations:
        result["registry_compensations"] = compensations
    result["result_message"] = _batch_result_summary(result, len(items), "FU完成")
    return result


def execute_registry_sync_task(payload: Dict[str, Any]) -> bool:
    """Retry Registry state only. This executor must never open or write an Excel file."""
    from registry import hooks as registry_hooks

    data_folder = str(payload.get("data_folder", "") or "").strip()
    if data_folder:
        registry_hooks.set_data_folder(data_folder)

    operation = str(payload.get("operation", "") or "").strip()
    registry_payload = dict(payload.get("registry_payload") or {})
    registry_payload.pop("data_folder", None)
    if operation == "response_written":
        result = registry_hooks.on_response_written(**registry_payload)
    elif operation == "fu_completed":
        result = registry_hooks.on_fu_completed(**registry_payload)
    elif operation == "assigned":
        result = registry_hooks.on_assigned(**registry_payload)
    else:
        raise ValueError(f"未知Registry补偿操作: {operation}")

    if result is not True:
        raise RuntimeError(f"Registry补偿仍未成功: {operation}")
    return True


EXECUTOR_MAP = {
    "assignment": execute_assignment_task,
    "response": execute_response_task,
    "response_batch": execute_response_batch_task,
    "fu_completion": execute_fu_completion_task,
    "fu_completion_batch": execute_fu_completion_batch_task,
    "registry_sync": execute_registry_sync_task,
}


def get_executor(task_type: str):
    executor = EXECUTOR_MAP.get(task_type)
    if not executor:
        raise ValueError(f"未知的写入任务类型: {task_type}")
    return executor

