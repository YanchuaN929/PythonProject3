#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import pytest

from core.main import _build_registry_excel_index, _filter_rows_by_highest_version


pytestmark = pytest.mark.allow_empty_name


def test_filter_rows_by_highest_version_keeps_highest_version_without_series_fallback():
    df = pd.DataFrame({
        "A": ["header", "x", "x", "x"],
        "B": ["header", "", "", ""],
        "C": ["header", "", "", ""],
        "D": ["header", "", "", ""],
        "E": ["版次", "A", "C", "B"],
        "F": ["header", "", "", ""],
        "G": ["header", "", "", ""],
        "H": ["header", "", "", ""],
        "I": ["header", "", "", ""],
        "J": ["header", "", "", ""],
        "K": ["header", "", "", ""],
        "L": ["header", "", "", ""],
        "M": ["header", "", "", ""],
        "N": ["header", "", "", ""],
        "O": ["header", "", "", ""],
        "P": ["header", "", "", ""],
        "Q": ["header", "", "", ""],
        "R": ["接口号", "IF-001(管理员)", "IF-001(管理员)", "IF-002"],
    })

    allowed_rows = _filter_rows_by_highest_version(df, 2, {1, 2, 3}, 4)

    assert allowed_rows == {2, 3}


def test_build_registry_excel_index_uses_column_values_and_strips_role_suffix(tmp_path):
    source_file = tmp_path / "2026测试.xlsx"
    df = pd.DataFrame({
        "项目号": ["项目号", "2026", "2026"],
        "接口号": ["接口号", "IF-001(管理员)", "IF-002"],
    })

    file_project_id, excel_index, excel_index_by_iface = _build_registry_excel_index(
        df,
        file_type=2,
        file_path=str(source_file),
    )

    assert file_project_id == "2026"
    assert excel_index[("IF-001", "2026")] == [1]
    assert excel_index[("IF-002", "2026")] == [2]
    assert excel_index_by_iface == {}
