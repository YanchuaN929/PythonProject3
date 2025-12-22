import pandas as pd

from write_tasks.pending_cache import PendingCache
from write_tasks.models import WriteTask


def _make_task(task_id: str, status: str = "pending"):
    return WriteTask(
        task_id=task_id,
        task_type="assignment",
        payload={},
        submitted_by="tester",
        description="",
        status=status,
    )


def test_assignment_overrides():
    cache = PendingCache()
    task_id = "task-1"
    cache.add_assignment_entries(
        task_id,
        [
            {
                "file_path": "D:/data/file1.xlsx",
                "row_index": 5,
                "file_type": 1,
                "assigned_name": "张三",
                "assigned_by": "李四",
            }
        ],
    )

    df = pd.DataFrame(
        {
            "source_file": ["D:/data/file1.xlsx"],
            "原始行号": [5],
            "责任人": [""],
            "状态": [""],
        }
    )
    overridden = cache.apply_overrides_to_dataframe(df, 1, ["设计人员"], "")
    assert overridden.loc[0, "责任人"] == "张三"
    assert overridden.loc[0, "状态"] == "📌 待完成"

    overridden_superior = cache.apply_overrides_to_dataframe(df, 1, ["一室主任"], "")
    assert overridden_superior.loc[0, "状态"] == "📌 待设计人员完成"

    task = _make_task(task_id, status="completed")
    cache.on_task_status_changed(task)
    overridden2 = cache.apply_overrides_to_dataframe(df, 1)
    # completed 仍保留覆盖，避免未重读Excel导致UI回弹
    assert overridden2.loc[0, "责任人"] == "张三"


def test_response_overrides():
    cache = PendingCache()
    task_id = "task-2"
    cache.add_response_entry(
        task_id,
        {
            "file_path": "file2.xlsx",
            "row_index": 3,
            "file_type": 2,
            "response_number": "HW-001",
            "user_name": "测试",
            "has_assignor": True,
        },
    )

    df = pd.DataFrame(
        {
            "source_file": ["file2.xlsx"],
            "原始行号": [3],
            "回文单号": [""],
            "是否已完成": [""],
            "状态": [""],
        }
    )
    overridden = cache.apply_overrides_to_dataframe(df, 2, [], "")
    assert overridden.loc[0, "回文单号"] == "HW-001"
    assert overridden.loc[0, "是否已完成"] == "☑"
    assert overridden.loc[0, "状态"] == "⏳ 待指派人审查"

    # 没有指派人的情况下
    cache_no_assignor = PendingCache()
    cache_no_assignor.add_response_entry(
        "task-2b",
        {
            "file_path": "file2.xlsx",
            "row_index": 3,
            "file_type": 2,
            "response_number": "HW-002",
            "user_name": "测试",
            "has_assignor": False,
        },
    )
    df2 = df.copy()
    df2["回文单号"] = [""]
    overridden_no_assignor = cache_no_assignor.apply_overrides_to_dataframe(df2, 2, [], "")
    assert overridden_no_assignor.loc[0, "状态"] == "⏳ 待审查"

    task = _make_task(task_id, status="completed")
    cache.on_task_status_changed(task)
    overridden2 = cache.apply_overrides_to_dataframe(df, 2, [], "")
    # completed 仍保留覆盖，避免未重读Excel导致UI回弹
    assert overridden2.loc[0, "回文单号"] == "HW-001"


def test_response_hides_row_for_submitter():
    cache = PendingCache()
    task_id = "task-3"
    cache.add_response_entry(
        task_id,
        {
            "file_path": "file3.xlsx",
            "row_index": 4,
            "file_type": 1,
            "response_number": "HW-123",
            "user_name": "张三",
            "project_id": "1818",
            "has_assignor": True,
        },
    )
    df = pd.DataFrame(
        {
            "source_file": ["file3.xlsx"],
            "原始行号": [4],
            "回文单号": [""],
            "是否已完成": [""],
        }
    )
    overridden = cache.apply_overrides_to_dataframe(df, 1, ["设计人员"], "张三")
    assert overridden.empty

