# -*- coding: utf-8 -*-
"""当前流式处理器的科室参数族回归测试。"""

import datetime
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from openpyxl import Workbook

from core import main
import utils.dept_config as dept_config


PROJECT_PROFILES = [
    "建筑结构所",
    "电力工程研究设计所",
    "核工程研究设计所",
    "核电工艺所",
    "电气自动化所",
]


@pytest.fixture(autouse=True)
def reset_dept_config():
    dept_config._profile_cache = None
    yield
    dept_config._profile_cache = None


@pytest.fixture
def no_registry_merge(monkeypatch):
    monkeypatch.setattr(
        main,
        "_merge_registry_pending_rows",
        lambda **kwargs: (kwargs["final_rows"], set()),
    )


def _profile_config(tmp_path, profile_name):
    source = json.loads(Path("config.json").read_text(encoding="utf-8"))
    source["department_profile"] = profile_name
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    return patch("utils.dept_config._get_config_path", return_value=str(config_path))


def _make_workbook(tmp_path, filename, rows):
    path = tmp_path / filename
    workbook = Workbook()
    worksheet = workbook.active
    worksheet["A1"] = "header"
    for row_number, values in rows:
        for column, value in values.items():
            worksheet["{}{}".format(column, row_number)] = value
    workbook.save(path)
    workbook.close()
    return str(path)


@pytest.mark.parametrize("profile_name", PROJECT_PROFILES)
def test_all_stream_processors_use_active_department_profile(
    tmp_path, no_registry_merge, profile_name
):
    now = datetime.datetime(2026, 5, 14)
    profile = json.loads(Path("config.json").read_text(encoding="utf-8"))[
        "department_profiles"
    ][profile_name]
    department_code = profile["department_codes"][0]
    organization = profile["organization_filter"]
    organization_file6 = profile["organization_filter_file6"]

    files = {
        1: _make_workbook(
            tmp_path,
            "2026按项目导出IDI手册2026-05-14.xlsx",
            [
                (2, {"A": "MATCH-1", "B": "", "H": department_code, "K": now, "M": ""}),
                (3, {"A": "OTHER-1", "B": "", "H": "NO-MATCH", "K": now, "M": ""}),
            ],
        ),
        2: _make_workbook(
            tmp_path,
            "内部接口信息单报表202620260514.xlsx",
            [
                (2, {"A": "x", "E": "A", "F": "", "I": organization, "M": now, "N": "", "R": "MATCH-2", "AB": ""}),
                (3, {"A": "x", "E": "A", "F": "", "I": "OTHER-ORG", "M": now, "N": "", "R": "OTHER-2", "AB": ""}),
            ],
        ),
        3: _make_workbook(
            tmp_path,
            "外部接口ICM报表202620260514.xlsx",
            [
                (2, {"C": "MATCH-3", "I": "B", "M": now, "T": "", "AC": "A", "AL": organization}),
                (3, {"C": "OTHER-3", "I": "B", "M": now, "T": "", "AC": "A", "AL": "OTHER-ORG"}),
            ],
        ),
        4: _make_workbook(
            tmp_path,
            "外部接口单报表202620260514.xlsx",
            [
                (2, {"E": "MATCH-4", "I": "A", "P": "B", "S": now, "V": "", "AF": organization}),
                (3, {"E": "OTHER-4", "I": "A", "P": "B", "S": now, "V": "", "AF": "OTHER-ORG"}),
            ],
        ),
        5: _make_workbook(
            tmp_path,
            "2026接口提资清单.xlsx",
            [
                (2, {"A": "MATCH-5", "G": department_code, "L": now, "N": ""}),
                (3, {"A": "OTHER-5", "G": "NO-MATCH", "L": now, "N": ""}),
            ],
        ),
        6: _make_workbook(
            tmp_path,
            "收发文清单2026.xlsx",
            [
                (2, {"E": "MATCH-6", "I": now, "J": "", "M": "尚未回复", "V": organization_file6, "AC": "A"}),
                (3, {"E": "OTHER-6", "I": now, "J": "", "M": "尚未回复", "V": "OTHER-ORG", "AC": "A"}),
            ],
        ),
    }

    with _profile_config(tmp_path, profile_name):
        dept_config._profile_cache = None
        results = {
            1: main.process_target_file(files[1], now),
            2: main.process_target_file2(files[2], now, "2026"),
            3: main.process_target_file3(files[3], now),
            4: main.process_target_file4(files[4], now),
            5: main.process_target_file5(files[5], now),
            6: main.process_target_file6(files[6], now),
        }

    for file_type, result in results.items():
        assert result["接口号"].tolist() == ["MATCH-{}".format(file_type)]
        assert result["原始行号"].tolist() == [2]


@pytest.mark.parametrize("profile_name", PROJECT_PROFILES)
def test_department_mapping_uses_active_profile(tmp_path, profile_name):
    profile = json.loads(Path("config.json").read_text(encoding="utf-8"))[
        "department_profiles"
    ][profile_name]
    department_code = profile["department_codes"][0]
    department_name = profile["department_code_mapping"][department_code]

    with _profile_config(tmp_path, profile_name):
        dept_config._profile_cache = None
        assert dept_config.contains_department_code("X-{}-Y".format(department_code))
        assert dept_config.map_code_to_department("X-{}-Y".format(department_code)) == department_name
