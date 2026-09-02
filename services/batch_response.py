"""Batch response/FU writers with one lock and one save per source workbook."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import os
import re
import time
from typing import Dict, Iterable, List, Tuple

from utils.excel_io import (
    ExcelWriteError,
    OoxmlWorksheetSnapshot,
    SharedWorkbookLock,
    atomic_patch_ooxml_cells,
    atomic_save_workbook,
    is_legacy_xls,
    normalize_header_text,
    open_workbook_for_edit,
    read_legacy_xls_cell,
    write_legacy_xls_cells,
)


MAX_PARALLEL_WORKBOOKS = 4
VERIFY_RETRY_DELAYS = (0.25, 0.5, 1.0, 2.0)


def _file_group_key(file_path: str) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(file_path)))


def _merge_update(updates: Dict[str, dict], update: dict) -> None:
    """Merge cell updates and reject two different values for one target cell."""
    cell = str(update.get("cell", "") or "").strip().upper()
    if not cell:
        raise ValueError("批量写入包含空单元格地址")
    normalized = dict(update)
    normalized["cell"] = cell
    existing = updates.get(cell)
    if existing is None:
        updates[cell] = normalized
        return
    if str(existing.get("value", "") or "") != str(normalized.get("value", "") or ""):
        raise ExcelWriteError(
            "BATCH_TARGET_CONFLICT",
            "PRECHECK_BATCH",
            f"同一批次试图向{cell}写入两个不同值，已拒绝整组写入。",
            retryable=False,
            committed=False,
        )
    if existing.get("style_id") is None and normalized.get("style_id") is not None:
        existing["style_id"] = normalized["style_id"]
    if not existing.get("number_format") and normalized.get("number_format"):
        existing["number_format"] = normalized["number_format"]


def _response_result(item: dict, resolved_row: int, response_col: str, already_present: bool) -> dict:
    result = dict(item)
    result["requested_row_index"] = int(item.get("row_index", 0) or 0)
    result["row_index"] = int(resolved_row)
    result["response_col"] = str(response_col)
    result["already_present"] = bool(already_present)
    return result


def _parse_file6_expected_date(value, *, date_1904: bool = False):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
        try:
            numeric_date = float(text)
            if 1 <= numeric_date <= 100000:
                from openpyxl.utils.datetime import CALENDAR_MAC_1904, WINDOWS_EPOCH, from_excel

                epoch = CALENDAR_MAC_1904 if date_1904 else WINDOWS_EPOCH
                parsed = from_excel(numeric_date, epoch=epoch)
                return parsed.date() if hasattr(parsed, "date") else parsed
        except Exception:
            pass
    try:
        import pandas as pd

        parsed = pd.to_datetime(value, errors="coerce")
        if pd.notna(parsed):
            return parsed.date() if hasattr(parsed, "date") else parsed
    except Exception:
        pass
    return None


def _file6_reply_status(expected_value, *, date_1904: bool = False) -> str:
    expected_date = _parse_file6_expected_date(expected_value, date_1904=date_1904)
    if not expected_date:
        return ""
    return "按时回复" if date.today() <= expected_date else "延期回复"


def _verify_ooxml_responses(file_path: str, sheet_path: str, results: List[dict]) -> None:
    from ui.input_handler import _response_text

    last_error = None
    for attempt in range(len(VERIFY_RETRY_DELAYS) + 1):
        try:
            snapshot = OoxmlWorksheetSnapshot(file_path, sheet_path=sheet_path)
            for item in results:
                cell = f"{item['response_col']}{item['row_index']}"
                actual = snapshot.value(cell)
                expected = item.get("response_number", "")
                if _response_text(actual) != _response_text(expected):
                    raise RuntimeError(f"{cell}期望“{expected}”，实际“{actual}”")
            return
        except Exception as exc:
            last_error = exc
        if attempt < len(VERIFY_RETRY_DELAYS):
            time.sleep(VERIFY_RETRY_DELAYS[attempt])
    raise ExcelWriteError(
        "VERIFY_FAILED",
        "VERIFY_FINAL",
        f"批量回文已替换正式文件，但重新打开核验失败：{last_error}",
        retryable=True,
        committed=True,
    ) from last_error


def _write_ooxml_response_group(file_path: str, items: List[dict]) -> List[dict]:
    from ui.input_handler import (
        _ensure_response_cell_writable,
        _resolve_ooxml_response_row,
        get_ooxml_write_columns,
    )

    snapshot = OoxmlWorksheetSnapshot(file_path)
    updates: Dict[str, dict] = {}
    results: List[dict] = []
    for raw_item in items:
        item = dict(raw_item)
        file_type = int(item.get("file_type", 0) or 0)
        resolved_row = _resolve_ooxml_response_row(
            snapshot,
            file_type,
            int(item.get("row_index", 0) or 0),
            item.get("interface_id"),
        )
        columns = get_ooxml_write_columns(
            file_type,
            resolved_row,
            snapshot,
            item.get("source_column"),
        )
        if not columns:
            raise ExcelWriteError(
                "WRITE_COLUMNS_UNKNOWN",
                "RESOLVE_COLUMNS",
                f"无法确定文件类型{file_type}的批量回文写入列。",
                retryable=False,
                committed=False,
            )
        response_col = columns["response_col"]
        response_cell = f"{response_col}{resolved_row}"
        should_write = _ensure_response_cell_writable(
            snapshot.value(response_cell),
            item.get("response_number", ""),
            response_cell,
        )
        result = _response_result(item, resolved_row, response_col, not should_write)
        results.append(result)
        if not should_write:
            continue

        _merge_update(updates, {"cell": response_cell, "value": item.get("response_number", "")})
        _merge_update(updates, {"cell": f"{columns['time_col']}{resolved_row}", "value": date.today().isoformat()})
        _merge_update(updates, {"cell": f"{columns['name_col']}{resolved_row}", "value": item.get("user_name", "")})
        for header_update in columns.get("header_updates", []):
            _merge_update(updates, header_update)
        if file_type == 6:
            reply_status = _file6_reply_status(
                snapshot.value(f"I{resolved_row}"),
                date_1904=snapshot.date_1904,
            )
            if reply_status:
                _merge_update(updates, {"cell": f"M{resolved_row}", "value": reply_status})

    if updates:
        atomic_patch_ooxml_cells(file_path, snapshot.sheet_path, list(updates.values()))
    _verify_ooxml_responses(file_path, snapshot.sheet_path, results)
    return results


def _write_xls_response_group(file_path: str, items: List[dict]) -> List[dict]:
    from ui.input_handler import (
        _ensure_response_cell_writable,
        _resolve_xls_response_row,
        get_write_columns,
    )

    updates: Dict[str, dict] = {}
    results: List[dict] = []
    for raw_item in items:
        item = dict(raw_item)
        file_type = int(item.get("file_type", 0) or 0)
        resolved_row = _resolve_xls_response_row(
            file_path,
            file_type,
            int(item.get("row_index", 0) or 0),
            item.get("interface_id"),
        )
        source_column = item.get("source_column")
        if file_type == 3 and source_column not in {"M", "L"}:
            m_value = read_legacy_xls_cell(file_path, f"M{resolved_row}")
            l_value = read_legacy_xls_cell(file_path, f"L{resolved_row}")
            t_value = read_legacy_xls_cell(file_path, f"T{resolved_row}")
            q_value = read_legacy_xls_cell(file_path, f"Q{resolved_row}")
            if m_value not in (None, "") and t_value in (None, ""):
                source_column = "M"
            elif l_value not in (None, "") and q_value in (None, ""):
                source_column = "L"
            else:
                source_column = "M"
        columns = get_write_columns(file_type, resolved_row, None, source_column)
        if not columns:
            raise ExcelWriteError(
                "WRITE_COLUMNS_UNKNOWN",
                "RESOLVE_COLUMNS",
                f"无法确定文件类型{file_type}的批量回文写入列。",
                retryable=False,
                committed=False,
            )
        response_col = columns["response_col"]
        response_cell = f"{response_col}{resolved_row}"
        should_write = _ensure_response_cell_writable(
            read_legacy_xls_cell(file_path, response_cell),
            item.get("response_number", ""),
            response_cell,
        )
        result = _response_result(item, resolved_row, response_col, not should_write)
        results.append(result)
        if not should_write:
            continue

        _merge_update(updates, {"cell": response_cell, "value": item.get("response_number", "")})
        _merge_update(updates, {"cell": f"{columns['time_col']}{resolved_row}", "value": date.today().isoformat()})
        _merge_update(updates, {"cell": f"{columns['name_col']}{resolved_row}", "value": item.get("user_name", "")})
        for header_update in columns.get("header_updates", []):
            header_cell = str(header_update["cell"])
            expected_header = str(header_update["value"])
            current_header = read_legacy_xls_cell(file_path, header_cell)
            if current_header in (None, ""):
                _merge_update(updates, {"cell": header_cell, "value": expected_header})
            elif normalize_header_text(current_header) != normalize_header_text(expected_header):
                raise ExcelWriteError(
                    "PROGRAM_COLUMN_CONFLICT",
                    "RESOLVE_COLUMNS",
                    f"{header_cell}已有业务表头“{current_header}”，未执行批量写入。",
                    retryable=False,
                    committed=False,
                )
        if file_type == 6:
            reply_status = _file6_reply_status(read_legacy_xls_cell(file_path, f"I{resolved_row}"))
            if reply_status:
                _merge_update(updates, {"cell": f"M{resolved_row}", "value": reply_status})

    if updates:
        write_legacy_xls_cells(file_path, list(updates.values()))
    from ui.input_handler import _verify_xls_response

    for item in results:
        _verify_xls_response(
            file_path,
            item["row_index"],
            item["response_col"],
            item.get("response_number", ""),
        )
    return results


def _write_response_file_group(file_path: str, items: List[dict]) -> List[dict]:
    if not os.path.exists(file_path):
        raise ExcelWriteError(
            "FILE_NOT_FOUND",
            "PRECHECK_BATCH",
            f"目标Excel文件不存在：{file_path}",
            retryable=False,
            committed=False,
        )
    with SharedWorkbookLock(file_path):
        try:
            with open(file_path, "r+b"):
                pass
        except PermissionError as exc:
            raise ExcelWriteError(
                "FILE_LOCKED",
                "PRECHECK_BATCH",
                f"目标Excel文件被占用或没有写权限：{exc}",
                retryable=True,
                committed=False,
            ) from exc
        if is_legacy_xls(file_path):
            return _write_xls_response_group(file_path, items)
        return _write_ooxml_response_group(file_path, items)


def _group_items(items: Iterable[dict]) -> List[Tuple[str, List[dict]]]:
    groups: Dict[str, Tuple[str, List[dict]]] = {}
    for index, raw_item in enumerate(items or []):
        item = dict(raw_item or {})
        file_path = str(item.get("file_path", "") or "").strip()
        item["_batch_order"] = index
        key = _file_group_key(file_path)
        if key not in groups:
            groups[key] = (file_path, [])
        groups[key][1].append(item)
    return list(groups.values())


def _batch_failure(item: dict, error: Exception) -> dict:
    failure = dict(item)
    failure["reason"] = str(error)
    failure["error_code"] = getattr(error, "code", type(error).__name__)
    return failure


def write_responses_batch(items: Iterable[dict]) -> dict:
    """Write file types 1-6; each workbook group is all-or-nothing."""
    groups = _group_items(items)
    successful: List[dict] = []
    failed: List[dict] = []
    if not groups:
        return {"success_count": 0, "already_present_count": 0, "successful_items": [], "failed_tasks": []}

    workers = min(MAX_PARALLEL_WORKBOOKS, len(groups))
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="ResponseExcel") as pool:
        futures = {
            pool.submit(_write_response_file_group, file_path, group_items): (file_path, group_items)
            for file_path, group_items in groups
        }
        for future in as_completed(futures):
            _file_path, group_items = futures[future]
            try:
                successful.extend(future.result())
            except Exception as exc:
                failed.extend(_batch_failure(item, exc) for item in group_items)

    successful.sort(key=lambda item: int(item.get("_batch_order", 0) or 0))
    failed.sort(key=lambda item: int(item.get("_batch_order", 0) or 0))
    return {
        "success_count": len(successful),
        "already_present_count": sum(1 for item in successful if item.get("already_present")),
        "successful_items": successful,
        "failed_tasks": failed,
    }


def _normalize_target_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value or "").strip()[:10])


def _dates_equal(left, right: date) -> bool:
    if left in (None, ""):
        return False
    try:
        return _normalize_target_date(left) == right
    except Exception:
        return False


def _write_ooxml_fu_group(file_path: str, items: List[dict]) -> List[dict]:
    from ui.input_handler import _resolve_xlsx_fu_row

    workbook = open_workbook_for_edit(file_path)
    verify_workbook = None
    results: List[dict] = []
    try:
        worksheet = workbook.active
        target_cells = set()
        changed = False
        for raw_item in items:
            item = dict(raw_item)
            resolved_row = _resolve_xlsx_fu_row(
                worksheet,
                int(item.get("row_index", 0) or 0),
                item.get("interface_id"),
            )
            cell_reference = f"D{resolved_row}"
            if cell_reference in target_cells:
                raise ExcelWriteError(
                    "BATCH_TARGET_DUPLICATE",
                    "PRECHECK_BATCH",
                    f"同一批次重复包含{cell_reference}，已拒绝整组写入。",
                    retryable=False,
                    committed=False,
                )
            target_cells.add(cell_reference)
            target_date = _normalize_target_date(item.get("completion_date"))
            current = worksheet[cell_reference].value
            already_present = _dates_equal(current, target_date)
            if current not in (None, "") and not already_present:
                raise ExcelWriteError(
                    "FU_DATE_CONFLICT",
                    "CHECK_EXISTING",
                    f"{cell_reference}已有实际FU日期“{current}”，本次未覆盖。",
                    retryable=False,
                    committed=False,
                )
            result = dict(item)
            result["requested_row_index"] = int(item.get("row_index", 0) or 0)
            result["row_index"] = int(resolved_row)
            result["already_present"] = already_present
            results.append(result)
            if not already_present:
                worksheet[cell_reference].value = target_date
                worksheet[cell_reference].number_format = "yyyy/m/d"
                changed = True
        if changed:
            atomic_save_workbook(workbook, file_path)
        workbook.close()
        workbook = None

        verify_workbook = open_workbook_for_edit(file_path)
        verify_sheet = verify_workbook.active
        for item in results:
            actual = verify_sheet[f"D{item['row_index']}"].value
            expected = _normalize_target_date(item.get("completion_date"))
            if not _dates_equal(actual, expected):
                raise ExcelWriteError(
                    "VERIFY_FAILED",
                    "VERIFY_FINAL",
                    f"D{item['row_index']}期望“{expected}”，实际“{actual}”。",
                    retryable=True,
                    committed=changed,
                )
        return results
    finally:
        for candidate in (workbook, verify_workbook):
            try:
                if candidate is not None:
                    candidate.close()
            except Exception:
                pass


def _write_xls_fu_group(file_path: str, items: List[dict]) -> List[dict]:
    from ui.input_handler import _resolve_xls_fu_row

    updates: Dict[str, dict] = {}
    results: List[dict] = []
    target_cells = set()
    for raw_item in items:
        item = dict(raw_item)
        resolved_row = _resolve_xls_fu_row(
            file_path,
            int(item.get("row_index", 0) or 0),
            item.get("interface_id"),
        )
        cell_reference = f"D{resolved_row}"
        if cell_reference in target_cells:
            raise ExcelWriteError(
                "BATCH_TARGET_DUPLICATE",
                "PRECHECK_BATCH",
                f"同一批次重复包含{cell_reference}，已拒绝整组写入。",
                retryable=False,
                committed=False,
            )
        target_cells.add(cell_reference)
        target_date = _normalize_target_date(item.get("completion_date"))
        current = read_legacy_xls_cell(file_path, cell_reference)
        already_present = _dates_equal(current, target_date)
        if current not in (None, "") and not already_present:
            raise ExcelWriteError(
                "FU_DATE_CONFLICT",
                "CHECK_EXISTING",
                f"{cell_reference}已有实际FU日期“{current}”，本次未覆盖。",
                retryable=False,
                committed=False,
            )
        result = dict(item)
        result["requested_row_index"] = int(item.get("row_index", 0) or 0)
        result["row_index"] = int(resolved_row)
        result["already_present"] = already_present
        results.append(result)
        if not already_present:
            _merge_update(updates, {
                "cell": cell_reference,
                "value": target_date,
                "number_format": "yyyy/m/d",
            })
    if updates:
        write_legacy_xls_cells(file_path, list(updates.values()))
    for item in results:
        actual = read_legacy_xls_cell(file_path, f"D{item['row_index']}")
        expected = _normalize_target_date(item.get("completion_date"))
        if not _dates_equal(actual, expected):
            raise ExcelWriteError(
                "VERIFY_FAILED",
                "VERIFY_FINAL",
                f"D{item['row_index']}期望“{expected}”，实际“{actual}”。",
                retryable=True,
                committed=bool(updates),
            )
    return results


def _write_fu_file_group(file_path: str, items: List[dict]) -> List[dict]:
    if not os.path.exists(file_path):
        raise ExcelWriteError(
            "FILE_NOT_FOUND",
            "PRECHECK_BATCH",
            f"目标Excel文件不存在：{file_path}",
            retryable=False,
            committed=False,
        )
    with SharedWorkbookLock(file_path):
        try:
            with open(file_path, "r+b"):
                pass
        except PermissionError as exc:
            raise ExcelWriteError(
                "FILE_LOCKED",
                "PRECHECK_BATCH",
                f"目标Excel文件被占用或没有写权限：{exc}",
                retryable=True,
                committed=False,
            ) from exc
        if is_legacy_xls(file_path):
            return _write_xls_fu_group(file_path, items)
        return _write_ooxml_fu_group(file_path, items)


def write_fu_completions_batch(items: Iterable[dict]) -> dict:
    """Write file type 7 completion dates; each workbook group is all-or-nothing."""
    groups = _group_items(items)
    successful: List[dict] = []
    failed: List[dict] = []
    if not groups:
        return {"success_count": 0, "already_present_count": 0, "successful_items": [], "failed_tasks": []}

    workers = min(MAX_PARALLEL_WORKBOOKS, len(groups))
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="FuExcel") as pool:
        futures = {
            pool.submit(_write_fu_file_group, file_path, group_items): (file_path, group_items)
            for file_path, group_items in groups
        }
        for future in as_completed(futures):
            _file_path, group_items = futures[future]
            try:
                successful.extend(future.result())
            except Exception as exc:
                failed.extend(_batch_failure(item, exc) for item in group_items)

    successful.sort(key=lambda item: int(item.get("_batch_order", 0) or 0))
    failed.sort(key=lambda item: int(item.get("_batch_order", 0) or 0))
    return {
        "success_count": len(successful),
        "already_present_count": sum(1 for item in successful if item.get("already_present")),
        "successful_items": successful,
        "failed_tasks": failed,
    }
