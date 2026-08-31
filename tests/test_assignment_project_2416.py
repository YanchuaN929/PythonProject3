#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import pytest


pytestmark = pytest.mark.allow_empty_name


def test_assignment_project_choices_include_2416(monkeypatch):
    from services import distribution

    monkeypatch.setattr(distribution, "get_projects", lambda: ["2026", "2306", "2416"])

    assert distribution.get_assignment_project_choices() == ["2026", "2306", "2416"]
    assert distribution.parse_interface_engineer_project(["2416接口工程师"]) == "2416"


def test_parse_all_interface_engineer_projects_preserves_order_and_deduplicates():
    from services import distribution

    roles = [
        "设计人员",
        "1818接口工程师",
        "2026接口工程师",
        "1818接口工程师",
    ]

    assert distribution.parse_interface_engineer_projects(roles) == ["1818", "2026"]
    assert distribution.parse_interface_engineer_project(roles) == "1818"


def test_unassigned_detection_supports_multi_project_interface_engineer(monkeypatch):
    """双项目角色在指派窗口取数时必须同时保留两个授权项目。"""
    from base import ExcelProcessorApp
    from services import distribution

    monkeypatch.setattr(distribution, "get_pending_cache", lambda: None)

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.user_roles = ["设计人员", "1818接口工程师", "2026接口工程师"]
    app.config = {"auto_hide_overdue_enabled": False}
    app._apply_pending_overrides = lambda df, _file_type: df

    for file_type in range(1, 8):
        setattr(app, f"processing_results_multi{file_type}", {})
    for attr in (
        "processing_results",
        "processing_results2",
        "processing_results3",
        "processing_results4",
        "processing_results5",
        "processing_results6",
        "processing_results7",
    ):
        setattr(app, attr, None)

    def _task(project_id, row_index):
        return {
            "项目号": project_id,
            "接口号": f"S-{project_id}-TEST",
            "接口时间": "2026.08.06",
            "科室": "结构一室",
            "责任人": "无",
            "source_file": rf"C:\tmp\{project_id}内部需回复接口.xlsx",
            "原始行号": row_index,
        }

    app.processing_results_multi2 = {
        "1818": pd.DataFrame([_task("1818", 11)]),
        "2026": pd.DataFrame([_task("2026", 12)]),
        "2306": pd.DataFrame([_task("2306", 13)]),
    }

    assert app._get_my_project_ids() == ["1818", "2026"]
    assert app._get_my_project_id() == "1818"

    unassigned = app._check_unassigned_tasks()

    assert [task["project_id"] for task in unassigned] == ["1818", "2026"]
    assert [task["interface_id"] for task in unassigned] == [
        "S-1818-TEST",
        "S-2026-TEST",
    ]


def test_unassigned_detection_keeps_director_department_filter(monkeypatch):
    """多项目修复不能改变室主任按科室筛选的既有逻辑。"""
    from services import distribution

    monkeypatch.setattr(distribution, "get_pending_cache", lambda: None)
    rows = pd.DataFrame(
        [
            {
                "项目号": "2026",
                "接口号": "S-C1",
                "责任人": "",
                "科室": "结构一室",
                "source_file": r"C:\tmp\director.xlsx",
                "原始行号": 21,
            },
            {
                "项目号": "2026",
                "接口号": "S-C2",
                "责任人": "",
                "科室": "结构二室",
                "source_file": r"C:\tmp\director.xlsx",
                "原始行号": 22,
            },
        ]
    )

    unassigned = distribution.check_unassigned(
        {1: rows},
        ["一室主任"],
        ["1818", "2026"],
        {"auto_hide_overdue_enabled": False},
    )

    assert [task["interface_id"] for task in unassigned] == ["S-C1"]


def test_unassigned_detection_reads_file1_multi_project_2416(monkeypatch):
    from base import ExcelProcessorApp
    from services import distribution

    monkeypatch.setattr(distribution, "get_pending_cache", lambda: None)

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.user_roles = ["2416接口工程师"]
    app.config = {"auto_hide_overdue_enabled": False}
    app._apply_pending_overrides = lambda df, _file_type: df

    for file_type in range(1, 7):
        setattr(app, f"processing_results_multi{file_type}", {})
    app.processing_results = None
    app.processing_results2 = None
    app.processing_results3 = None
    app.processing_results4 = None
    app.processing_results5 = None
    app.processing_results6 = None

    app.processing_results_multi1 = {
        "2416": pd.DataFrame(
            [
                {
                    "项目号": "2416",
                    "接口号": "S-2416-TEST",
                    "接口时间": "2026.06.03",
                    "科室": "结构一室",
                    "责任人": "",
                    "source_file": r"C:\tmp\2416按项目导出IDI手册2026-06-03.xlsx",
                    "原始行号": 12,
                }
            ]
        )
    }

    unassigned = app._check_unassigned_tasks()

    assert len(unassigned) == 1
    assert unassigned[0]["project_id"] == "2416"
    assert unassigned[0]["interface_id"] == "S-2416-TEST"
    assert unassigned[0]["file_type"] == 1


def test_unassigned_detection_keeps_file1_single_result_fallback(monkeypatch):
    from base import ExcelProcessorApp
    from services import distribution

    monkeypatch.setattr(distribution, "get_pending_cache", lambda: None)

    app = ExcelProcessorApp.__new__(ExcelProcessorApp)
    app.user_roles = ["2416接口工程师"]
    app.config = {"auto_hide_overdue_enabled": False}
    app._apply_pending_overrides = lambda df, _file_type: df

    for file_type in range(1, 7):
        setattr(app, f"processing_results_multi{file_type}", {})
    app.processing_results = pd.DataFrame(
        [
            {
                "项目号": "2416",
                "接口号": "S-2416-FALLBACK",
                "接口时间": "2026.06.03",
                "科室": "结构一室",
                "责任人": "",
                "source_file": r"C:\tmp\2416按项目导出IDI手册2026-06-03.xlsx",
                "原始行号": 18,
            }
        ]
    )
    app.processing_results2 = None
    app.processing_results3 = None
    app.processing_results4 = None
    app.processing_results5 = None
    app.processing_results6 = None

    unassigned = app._check_unassigned_tasks()

    assert len(unassigned) == 1
    assert unassigned[0]["project_id"] == "2416"
    assert unassigned[0]["interface_id"] == "S-2416-FALLBACK"
