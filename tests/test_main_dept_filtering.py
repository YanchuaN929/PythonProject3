# -*- coding: utf-8 -*-
"""
core/main.py 科室筛选逻辑参数化测试

验证 6 种文件类型的筛选函数在不同参数族下的行为：
- execute_process1 (File1 H列)
- execute2_process1 (File2 I列)
- execute3_process2 (File3 AL列)
- execute4_process1 (File4 AF列)
- execute5_process1 (File5 G列)
- execute6_process1 (File6 V列)

同时验证科室映射函数的正确性。
"""

import json
import pytest
import pandas as pd
from unittest.mock import patch

# 确保每个测试都重置 dept_config 缓存
@pytest.fixture(autouse=True)
def reset_dept_config():
    import utils.dept_config as dc
    dc._profile_cache = None
    yield
    dc._profile_cache = None


@pytest.fixture
def patch_electric_profile(tmp_path):
    """将 dept_config 切换到电气所参数族"""
    config = {
        "department_profile": "电气工程及其自动化所",
        "department_profiles": {
            "电气工程及其自动化所": {
                "organization_filter": "河北分公司-电气工程及其自动化所",
                "organization_filter_file6": "河北分公司.电气工程及其自动化所",
                "department_codes": ["25D1", "25D2"],
                "department_code_mapping": {
                    "25D1": "电气一室",
                    "25D2": "电气二室",
                },
                "director_role_mapping": {
                    "电气一室主任": "电气一室",
                    "电气二室主任": "电气二室",
                },
                "default_folder_path": "//server/电气所",
                "watermark_text": "电气工程及其自动化所",
            }
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    return patch(
        "utils.dept_config._get_config_path",
        return_value=str(config_file),
    )


# =========================================================================
# File1: execute_process1 (H列包含科室编码)
# =========================================================================

class TestFile1ExecuteProcess1:
    """File1 H列筛选测试"""

    def _make_df(self, h_values):
        """创建 H 列在索引 7 的 DataFrame（含标题行）"""
        # 需要至少 8 列，H 列 = index 7
        data = {}
        for i in range(8):
            col_name = f"col{i}"
            if i == 7:
                data[col_name] = ["标题"] + h_values
            else:
                data[col_name] = [""] * (len(h_values) + 1)
        return pd.DataFrame(data)

    def test_default_profile_filters_25C_codes(self):
        """默认参数族下，25C1/25C2/25C3 的行被筛选"""
        from core.main import execute_process1
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df(["25C1", "25C2", "25C3", "25D1", "无关"])
            result = execute_process1(df)
        # 行索引 1,2,3 应被选中（跳过标题行 0）
        assert result == {1, 2, 3}

    def test_electric_profile_filters_25D_codes(self, patch_electric_profile):
        """电气所参数族下，25D1/25D2 被筛选，25C 不被筛选"""
        from core.main import execute_process1
        with patch_electric_profile:
            df = self._make_df(["25C1", "25D1", "25D2", "25C2", "无关"])
            result = execute_process1(df)
        assert result == {2, 3}

    def test_empty_column_returns_empty_set(self):
        from core.main import execute_process1
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df(["无关", "其他", ""])
            result = execute_process1(df)
        assert result == set()


# =========================================================================
# File2: execute2_process1 (I列包含组织或编码)
# =========================================================================

class TestFile2ExecuteProcess1:
    """File2 I列筛选测试"""

    def _make_df(self, i_values):
        data = {}
        for col_idx in range(9):
            col = f"col{col_idx}"
            if col_idx == 8:
                data[col] = ["标题"] + i_values
            else:
                data[col] = [""] * (len(i_values) + 1)
        return pd.DataFrame(data)

    def test_default_profile_matches_org_and_codes(self):
        from core.main import execute2_process1
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df([
                "河北分公司-建筑结构所-结构一室",  # 组织名命中
                "25C1-xxx",                         # 编码命中
                "河北分公司-电气工程及其自动化所",    # 不命中
                "25D1",                              # 不命中
                "无关",                              # 不命中
            ])
            result = execute2_process1(df)
        assert result == {1, 2}

    def test_electric_profile_matches_electric_org_and_codes(
        self, patch_electric_profile
    ):
        from core.main import execute2_process1
        with patch_electric_profile:
            df = self._make_df([
                "河北分公司-电气工程及其自动化所-电气一室",
                "25D1-yyy",
                "河北分公司-建筑结构所",
                "25C1",
            ])
            result = execute2_process1(df)
        assert result == {1, 2}


# =========================================================================
# File3: execute3_process2 (AL列以组织名开头)
# =========================================================================

class TestFile3ExecuteProcess2:
    """File3 AL列筛选测试"""

    def _make_df(self, al_values):
        """AL 列 = index 37"""
        data = {}
        for col_idx in range(38):
            col = f"col{col_idx}"
            if col_idx == 37:
                data[col] = al_values
            else:
                data[col] = [""] * len(al_values)
        return pd.DataFrame(data)

    def test_default_profile_startswith_org(self):
        from core.main import execute3_process2
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df([
                "河北分公司-建筑结构所-结构一室",
                "河北分公司-电气工程及其自动化所",
                "其他公司-建筑结构所",
                "",
            ])
            result = execute3_process2(df)
        assert 0 in result
        assert 1 not in result

    def test_electric_profile(self, patch_electric_profile):
        from core.main import execute3_process2
        with patch_electric_profile:
            df = self._make_df([
                "河北分公司-电气工程及其自动化所-电气一室",
                "河北分公司-建筑结构所-结构一室",
            ])
            result = execute3_process2(df)
        assert 0 in result
        assert 1 not in result


# =========================================================================
# File4: execute4_process1 (AF列以组织名开头)
# =========================================================================

class TestFile4ExecuteProcess1:
    """File4 AF列筛选测试"""

    def _make_df(self, af_values):
        """AF 列 = index 31"""
        data = {}
        for col_idx in range(32):
            col = f"col{col_idx}"
            if col_idx == 31:
                data[col] = af_values
            else:
                data[col] = [""] * len(af_values)
        return pd.DataFrame(data)

    def test_default_profile(self):
        from core.main import execute4_process1
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df([
                "河北分公司-建筑结构所-结构二室",
                "河北分公司-电气工程及其自动化所",
                "无关数据",
            ])
            result = execute4_process1(df)
        assert 0 in result
        assert 1 not in result
        assert 2 not in result

    def test_electric_profile(self, patch_electric_profile):
        from core.main import execute4_process1
        with patch_electric_profile:
            df = self._make_df([
                "河北分公司-电气工程及其自动化所-电气二室",
                "河北分公司-建筑结构所",
            ])
            result = execute4_process1(df)
        assert 0 in result
        assert 1 not in result


# =========================================================================
# File5: execute5_process1 (G列包含科室编码)
# =========================================================================

class TestFile5ExecuteProcess1:
    """File5 G列筛选测试"""

    def _make_df(self, g_values):
        """G 列 = index 6"""
        data = {}
        for col_idx in range(7):
            col = f"col{col_idx}"
            if col_idx == 6:
                data[col] = ["标题"] + g_values
            else:
                data[col] = [""] * (len(g_values) + 1)
        return pd.DataFrame(data)

    def test_default_profile(self):
        from core.main import execute5_process1
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df(["25C1", "25D1", "25C3"])
            result = execute5_process1(df)
        assert result == {1, 3}

    def test_electric_profile(self, patch_electric_profile):
        from core.main import execute5_process1
        with patch_electric_profile:
            df = self._make_df(["25D1", "25C1", "25D2"])
            result = execute5_process1(df)
        assert result == {1, 3}


# =========================================================================
# File6: execute6_process1 (V列包含组织名.点号版)
# =========================================================================

class TestFile6ExecuteProcess1:
    """File6 V列筛选测试"""

    def _make_df(self, v_values):
        """V 列 = index 21"""
        data = {}
        for col_idx in range(22):
            col = f"col{col_idx}"
            if col_idx == 21:
                data[col] = ["标题"] + v_values
            else:
                data[col] = [""] * (len(v_values) + 1)
        return pd.DataFrame(data)

    def test_default_profile(self):
        from core.main import execute6_process1
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            df = self._make_df([
                "河北分公司.建筑结构所.结构一室",
                "河北分公司.电气工程及其自动化所",
                "无关",
            ])
            result = execute6_process1(df)
        assert 1 in result
        assert 2 not in result
        assert 3 not in result

    def test_electric_profile(self, patch_electric_profile):
        from core.main import execute6_process1
        with patch_electric_profile:
            df = self._make_df([
                "河北分公司.电气工程及其自动化所.电气一室",
                "河北分公司.建筑结构所.结构一室",
            ])
            result = execute6_process1(df)
        assert 1 in result
        assert 2 not in result


# =========================================================================
# 科室映射：map_code_to_department 在 process_target_file 中的调用
# =========================================================================

class TestDepartmentMappingInProcessing:
    """验证处理函数中科室列的映射正确性"""

    def test_map_code_returns_correct_dept_default(self):
        from utils.dept_config import map_code_to_department
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert map_code_to_department("S-YA-25C1-ZZ") == "结构一室"
            assert map_code_to_department("S-YA-25C2-ZZ") == "结构二室"
            assert map_code_to_department("S-YA-25C3-ZZ") == "建筑总图室"
            assert map_code_to_department("S-YA-25D1-ZZ") == ""

    def test_match_dept_name_returns_correct_default(self):
        from utils.dept_config import match_department_name
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert match_department_name(
                "河北分公司-建筑结构所-结构一室"
            ) == "结构一室"
            assert match_department_name(
                "结构二室-张工"
            ) == "结构二室"
            # 未匹配返回原文
            assert match_department_name("电气一室") == "电气一室"

    def test_map_code_electric_profile(self, patch_electric_profile):
        from utils.dept_config import map_code_to_department
        with patch_electric_profile:
            assert map_code_to_department("X-25D1-Y") == "电气一室"
            assert map_code_to_department("X-25D2-Y") == "电气二室"
            assert map_code_to_department("X-25C1-Y") == ""


# =========================================================================
# 电力工程研究设计所参数族筛选测试
# =========================================================================

@pytest.fixture
def patch_power_eng_profile(tmp_path):
    """将 dept_config 切换到电力工程研究设计所参数族"""
    config = {
        "department_profile": "电力工程研究设计所",
        "department_profiles": {
            "电力工程研究设计所": {
                "organization_filter": "河北分公司-电力工程研究设计所",
                "organization_filter_file6": "河北分公司.电力工程研究设计所",
                "department_codes": ["25D1", "25D2", "25D3", "25D4"],
                "department_code_mapping": {
                    "25D1": "机务室",
                    "25D2": "电气室",
                    "25D3": "土建室",
                    "25D4": "仪控室",
                },
                "director_role_mapping": {
                    "机务室主任": "机务室",
                    "电气室主任": "电气室",
                    "土建室主任": "土建室",
                    "仪控室主任": "仪控室",
                },
                "default_folder_path": "//10.102.2.7/电力工程研究设计所/软件/接口管理软件",
                "watermark_text": "建筑结构所",
            }
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    return patch(
        "utils.dept_config._get_config_path",
        return_value=str(config_file),
    )


class TestPowerEngFile1:
    """电力工程研究设计所 File1 H列筛选"""

    def _make_df(self, h_values):
        data = {}
        for i in range(8):
            col_name = f"col{i}"
            if i == 7:
                data[col_name] = ["标题"] + h_values
            else:
                data[col_name] = [""] * (len(h_values) + 1)
        return pd.DataFrame(data)

    def test_filters_25D_codes(self, patch_power_eng_profile):
        """电力工程研究设计所下，25D1-25D4 被筛选"""
        from core.main import execute_process1
        with patch_power_eng_profile:
            df = self._make_df(["25D1", "25D2", "25D3", "25D4", "25C1", "无关"])
            result = execute_process1(df)
        assert result == {1, 2, 3, 4}

    def test_25C_codes_not_matched(self, patch_power_eng_profile):
        """电力工程研究设计所下，25C 编码不匹配"""
        from core.main import execute_process1
        with patch_power_eng_profile:
            df = self._make_df(["25C1", "25C2", "25C3"])
            result = execute_process1(df)
        assert result == set()


class TestPowerEngFile5:
    """电力工程研究设计所 File5 G列筛选"""

    def _make_df(self, g_values):
        data = {}
        for i in range(7):
            col_name = f"col{i}"
            if i == 6:
                data[col_name] = ["标题"] + g_values
            else:
                data[col_name] = [""] * (len(g_values) + 1)
        return pd.DataFrame(data)

    def test_filters_25D_codes(self, patch_power_eng_profile):
        from core.main import execute5_process1
        with patch_power_eng_profile:
            df = self._make_df(["25D1", "25D2", "25D3", "25D4", "25C1"])
            result = execute5_process1(df)
        assert result == {1, 2, 3, 4}


class TestPowerEngDeptMapping:
    """电力工程研究设计所科室映射测试"""

    def test_map_code(self, patch_power_eng_profile):
        from utils.dept_config import map_code_to_department
        with patch_power_eng_profile:
            assert map_code_to_department("X-25D1-Y") == "机务室"
            assert map_code_to_department("X-25D2-Y") == "电气室"
            assert map_code_to_department("X-25D3-Y") == "土建室"
            assert map_code_to_department("X-25D4-Y") == "仪控室"
            assert map_code_to_department("X-25C1-Y") == ""

    def test_match_dept_name(self, patch_power_eng_profile):
        from utils.dept_config import match_department_name
        with patch_power_eng_profile:
            assert match_department_name("河北-机务室-xx") == "机务室"
            assert match_department_name("仪控室") == "仪控室"
            assert match_department_name("结构一室") == "结构一室"  # 未匹配返回原始

    def test_contains_code(self, patch_power_eng_profile):
        from utils.dept_config import contains_department_code
        with patch_power_eng_profile:
            assert contains_department_code("25D1") is True
            assert contains_department_code("25D4!!") is True
            assert contains_department_code("25C1") is False


# =========================================================================
# 核工程研究设计所参数族筛选测试
# =========================================================================

@pytest.fixture
def patch_nuclear_eng_profile(tmp_path):
    """将 dept_config 切换到核工程研究设计所参数族"""
    config = {
        "department_profile": "核工程研究设计所",
        "department_profiles": {
            "核工程研究设计所": {
                "organization_filter": "河北分公司-核工程研究设计所",
                "organization_filter_file6": "河北分公司.核工程研究设计所",
                "department_codes": ["25E5", "25E6"],
                "department_code_mapping": {
                    "25E5": "设备室",
                    "25E6": "通信室",
                },
                "director_role_mapping": {
                    "设备室主任": "设备室",
                    "通信室主任": "通信室",
                },
                "default_folder_path": "//10.102.2.7/文件服务器/核工程研究设计所/软件/接口管理软件",
                "watermark_text": "建筑结构所",
            }
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    return patch(
        "utils.dept_config._get_config_path",
        return_value=str(config_file),
    )


class TestNuclearEngFile1:
    """核工程研究设计所 File1 H列筛选"""

    def _make_df(self, h_values):
        data = {}
        for i in range(8):
            col_name = f"col{i}"
            if i == 7:
                data[col_name] = ["标题"] + h_values
            else:
                data[col_name] = [""] * (len(h_values) + 1)
        return pd.DataFrame(data)

    def test_filters_25E_codes(self, patch_nuclear_eng_profile):
        """核工程所下，25E5/25E6 被筛选"""
        from core.main import execute_process1
        with patch_nuclear_eng_profile:
            df = self._make_df(["25E5", "25E6", "25C1", "25D1", "无关"])
            result = execute_process1(df)
        assert result == {1, 2}

    def test_25C_25D_codes_not_matched(self, patch_nuclear_eng_profile):
        """核工程所下，25C 和 25D 编码不匹配"""
        from core.main import execute_process1
        with patch_nuclear_eng_profile:
            df = self._make_df(["25C1", "25C2", "25D1", "25D4"])
            result = execute_process1(df)
        assert result == set()


class TestNuclearEngFile5:
    """核工程研究设计所 File5 G列筛选"""

    def _make_df(self, g_values):
        data = {}
        for i in range(7):
            col_name = f"col{i}"
            if i == 6:
                data[col_name] = ["标题"] + g_values
            else:
                data[col_name] = [""] * (len(g_values) + 1)
        return pd.DataFrame(data)

    def test_filters_25E_codes(self, patch_nuclear_eng_profile):
        from core.main import execute5_process1
        with patch_nuclear_eng_profile:
            df = self._make_df(["25E5", "25E6", "25C1", "25D2"])
            result = execute5_process1(df)
        assert result == {1, 2}


class TestNuclearEngDeptMapping:
    """核工程研究设计所科室映射测试"""

    def test_map_code(self, patch_nuclear_eng_profile):
        from utils.dept_config import map_code_to_department
        with patch_nuclear_eng_profile:
            assert map_code_to_department("X-25E5-Y") == "设备室"
            assert map_code_to_department("X-25E6-Y") == "通信室"
            assert map_code_to_department("X-25C1-Y") == ""
            assert map_code_to_department("X-25D1-Y") == ""

    def test_match_dept_name(self, patch_nuclear_eng_profile):
        from utils.dept_config import match_department_name
        with patch_nuclear_eng_profile:
            assert match_department_name("河北-设备室-xx") == "设备室"
            assert match_department_name("通信室") == "通信室"
            assert match_department_name("结构一室") == "结构一室"

    def test_contains_code(self, patch_nuclear_eng_profile):
        from utils.dept_config import contains_department_code
        with patch_nuclear_eng_profile:
            assert contains_department_code("25E5") is True
            assert contains_department_code("25E6!!") is True
            assert contains_department_code("25C1") is False
            assert contains_department_code("25D1") is False


# =========================================================================
# 电气自动化所参数族筛选测试
# =========================================================================

@pytest.fixture
def patch_automation_profile(tmp_path):
    """将 dept_config 切换到电气自动化所参数族"""
    config = {
        "department_profile": "电气自动化所",
        "department_profiles": {
            "电气自动化所": {
                "organization_filter": "河北分公司-电气自动化所",
                "organization_filter_file6": "河北分公司.电气自动化所",
                "department_codes": ["25B1", "25B2", "25B3"],
                "department_code_mapping": {
                    "25B1": "电气室",
                    "25B2": "仪控一室",
                    "25B3": "仪控二室",
                },
                "director_role_mapping": {
                    "电气室主任": "电气室",
                    "一室主任": "仪控一室",
                    "二室主任": "仪控二室",
                },
                "default_folder_path": "//10.102.2.7/文件服务器/电气自动化所/自动化室/21 接口管理",
                "watermark_text": "建筑结构所",
            }
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(config, ensure_ascii=False), encoding="utf-8"
    )
    return patch(
        "utils.dept_config._get_config_path",
        return_value=str(config_file),
    )


class TestAutomationFile1:
    """电气自动化所 File1 H列筛选"""

    def _make_df(self, h_values):
        data = {}
        for i in range(8):
            col_name = f"col{i}"
            if i == 7:
                data[col_name] = ["标题"] + h_values
            else:
                data[col_name] = [""] * (len(h_values) + 1)
        return pd.DataFrame(data)

    def test_filters_25B_codes(self, patch_automation_profile):
        from core.main import execute_process1
        with patch_automation_profile:
            df = self._make_df(["25B1", "25B2", "25B3", "25C1", "25D1", "25E5"])
            result = execute_process1(df)
        assert result == {1, 2, 3}


class TestAutomationFile5:
    """电气自动化所 File5 G列筛选"""

    def _make_df(self, g_values):
        data = {}
        for i in range(7):
            col_name = f"col{i}"
            if i == 6:
                data[col_name] = ["标题"] + g_values
            else:
                data[col_name] = [""] * (len(g_values) + 1)
        return pd.DataFrame(data)

    def test_filters_25B_codes(self, patch_automation_profile):
        from core.main import execute5_process1
        with patch_automation_profile:
            df = self._make_df(["25B1", "25B2", "25B3", "25C1", "25D2", "25E6"])
            result = execute5_process1(df)
        assert result == {1, 2, 3}


class TestAutomationDeptMapping:
    """电气自动化所科室映射测试"""

    def test_map_code(self, patch_automation_profile):
        from utils.dept_config import map_code_to_department
        with patch_automation_profile:
            assert map_code_to_department("X-25B1-Y") == "电气室"
            assert map_code_to_department("X-25B2-Y") == "仪控一室"
            assert map_code_to_department("X-25B3-Y") == "仪控二室"
            assert map_code_to_department("X-25C1-Y") == ""
            assert map_code_to_department("X-25D1-Y") == ""
            assert map_code_to_department("X-25E5-Y") == ""

    def test_match_dept_name(self, patch_automation_profile):
        from utils.dept_config import match_department_name
        with patch_automation_profile:
            assert match_department_name("河北-电气室-xx") == "电气室"
            assert match_department_name("河北-仪控一室-xx") == "仪控一室"
            assert match_department_name("河北-仪控二室-xx") == "仪控二室"
            assert match_department_name("结构一室") == "结构一室"

    def test_contains_code(self, patch_automation_profile):
        from utils.dept_config import contains_department_code
        with patch_automation_profile:
            assert contains_department_code("25B1") is True
            assert contains_department_code("25B2!!") is True
            assert contains_department_code("25B3 test") is True
            assert contains_department_code("25C1") is False
            assert contains_department_code("25D1") is False
            assert contains_department_code("25E5") is False
