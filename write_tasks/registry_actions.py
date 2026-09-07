"""Registry business actions executed by the same ordered business queue."""
import os
import re


def execute_registry_action(payload, operation):
    from registry import hooks, service
    from registry.db import close_connection_after_use

    role = str(payload.get("role") or "")
    if not any(word in role for word in ("管理员", "所领导", "所长", "室主任", "接口工程师")):
        raise PermissionError("当前提交身份无权执行上级业务操作")
    if operation == "ignore" and "所领导" not in role:
        raise PermissionError("只有所领导角色可以忽略延期任务")
    if payload.get("data_folder"):
        hooks.set_data_folder(payload["data_folder"])
    successes, failures = [], []
    try:
        for item in payload.get("items", []):
            try:
                engineer_projects = re.findall(r"(\d{4})\s*接口工程师", role)
                if (engineer_projects
                        and not any(word in role for word in ("管理员", "所领导", "所长", "室主任"))
                        and str(item.get("project_id")) not in engineer_projects):
                    raise PermissionError("接口工程师无权操作该项目")
                key = {name: item.get(name) for name in
                       ("file_type", "project_id", "interface_id", "row_index", "interface_time")}
                key["source_file"] = os.path.basename(item.get("file_path") or item.get("source_file") or "")
                snapshot = hooks.get_task_snapshot(key)
                if not snapshot:
                    raise ValueError("找不到当前任务，请重新处理后再提交")
                status = snapshot.get("status")
                if operation == "confirmation":
                    if status != "completed":
                        raise ValueError("当前状态为{}，仅已完成任务可以审查".format(status))
                    ok = hooks.on_confirmed_by_superior(
                        file_type=key["file_type"], project_id=key["project_id"],
                        interface_id=key["interface_id"], row_index=key["row_index"],
                        file_path=item.get("file_path") or item["source_file"],
                        user_name=payload["user_name"], role=role)
                elif operation == "unconfirmation":
                    if status != "confirmed":
                        raise ValueError("仅尚未归档的已确认任务可以取消确认")
                    ok = hooks.on_unconfirmed_by_superior(key, payload["user_name"])
                elif operation == "ignore":
                    if status in ("confirmed", "archived"):
                        raise ValueError("已确认或归档的任务不能忽略")
                    cfg = hooks._cfg()
                    result = service.mark_ignored_batch(
                        cfg["registry_db_path"], cfg.get("registry_wal", False), [key],
                        payload["user_name"], payload.get("reason", ""))
                    ok = result.get("success_count") == 1
                    hooks.invalidate_cache()
                else:
                    raise ValueError("未知业务操作")
                if ok is not True:
                    raise RuntimeError("Registry写入失败，请检查任务当前状态")
                successes.append(item)
            except Exception as exc:
                failures.append("{}: {}".format(item.get("interface_id", ""), exc))
        # Retain partial outcomes for UI refresh and audit, including on failure.
        payload["succeeded_items"] = successes
        payload["failed_messages"] = failures
        if failures:
            raise RuntimeError("成功 {} 条，失败 {} 条：{}".format(
                len(successes), len(failures), "；".join(failures[:8])))
        return {"result_message": "成功 {} 条".format(len(successes))}
    finally:
        close_connection_after_use()
