from write_tasks.models import WriteTask
from write_tasks.task_panel import TaskRecordPanel


def test_extract_interface_ids_from_assignment_task():
    task = WriteTask(
        task_id="1",
        task_type="assignment",
        payload={
            "assignments": [
                {"interface_id": "A"},
                {"interface_id": "B"},
                {"interface_id": "A"},
            ]
        },
        submitted_by="u",
        description="d",
    )
    assert TaskRecordPanel._extract_interface_ids_from_task(task) == ["A", "B"]


def test_extract_interface_ids_from_response_task():
    task = WriteTask(
        task_id="2",
        task_type="response",
        payload={"interface_id": "X"},
        submitted_by="u",
        description="d",
    )
    assert TaskRecordPanel._extract_interface_ids_from_task(task) == ["X"]


