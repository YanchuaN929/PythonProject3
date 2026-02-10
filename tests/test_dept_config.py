# -*- coding: utf-8 -*-
"""
科室参数化配置模块 (utils/dept_config.py) 测试

覆盖：
1. 默认参数族加载与后备值
2. 从 config.json 加载参数族
3. 多参数族切换
4. 缓存与 reload 机制
5. 所有便捷访问函数
6. 辅助匹配函数 (map_code_to_department / match_department_name / contains_department_code)
7. 字段缺失时的自动补全
8. config.json 不存在时的容错
"""

import json
import pytest
from unittest.mock import patch

# 确保每个测试都重置缓存
@pytest.fixture(autouse=True)
def reset_dept_config_cache():
    """每个测试前重置 dept_config 的模块级缓存"""
    import utils.dept_config as dc
    dc._profile_cache = None
    yield
    dc._profile_cache = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path):
    """创建临时 config.json 并 patch 路径"""
    config_file = tmp_path / "config.json"

    def _write(data):
        config_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return str(config_file)

    return _write


@pytest.fixture
def patch_config_path(tmp_config):
    """Patch _get_config_path 指向临时 config.json"""

    def _patch(data):
        path = tmp_config(data)
        return patch("utils.dept_config._get_config_path", return_value=path)

    return _patch


ELECTRIC_PROFILE = {
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
    "role_export_days": {
        "电气一室主任": 7,
        "电气二室主任": 7,
        "所领导": 2,
        "管理员": None,
        "设计人员": None,
    },
    "default_folder_path": "//server/电气所/接口文件",
    "watermark_text": "电气工程及其自动化所",
}


# =========================================================================
# 1. 默认参数族（无 config.json 时）
# =========================================================================

class TestDefaultProfile:
    """当 config.json 不存在或无 department_profiles 时，使用默认值"""

    def test_fallback_when_no_config_file(self):
        from utils.dept_config import get_active_profile
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent/path/config.json"):
            profile = get_active_profile()
        assert profile["organization_filter"] == "河北分公司-建筑结构所"
        assert profile["department_codes"] == ["25C1", "25C2", "25C3"]

    def test_fallback_when_no_profiles_section(self, patch_config_path):
        from utils.dept_config import get_active_profile
        with patch_config_path({"folder_path": "/some/path"}):
            profile = get_active_profile()
        assert profile["organization_filter"] == "河北分公司-建筑结构所"

    def test_default_profile_has_all_required_keys(self):
        from utils.dept_config import _default_profile
        profile = _default_profile()
        required = [
            "organization_filter",
            "organization_filter_file6",
            "department_codes",
            "department_code_mapping",
            "director_role_mapping",
            "role_export_days",
            "default_folder_path",
            "watermark_text",
        ]
        for key in required:
            assert key in profile, f"默认参数族缺少字段: {key}"


# =========================================================================
# 2. 从 config.json 加载
# =========================================================================

class TestLoadFromConfig:
    """从 config.json 的 department_profiles 加载"""

    def test_load_default_building_profile(self, patch_config_path):
        from utils.dept_config import get_active_profile
        config = {
            "department_profile": "建筑结构所",
            "department_profiles": {
                "建筑结构所": {
                    "organization_filter": "河北分公司-建筑结构所",
                    "organization_filter_file6": "河北分公司.建筑结构所",
                    "department_codes": ["25C1", "25C2", "25C3"],
                    "department_code_mapping": {
                        "25C1": "结构一室",
                        "25C2": "结构二室",
                        "25C3": "建筑总图室",
                    },
                    "director_role_mapping": {
                        "一室主任": "结构一室",
                        "二室主任": "结构二室",
                        "建筑总图室主任": "建筑总图室",
                    },
                    "default_folder_path": "//server/建筑结构所",
                    "watermark_text": "建筑结构所",
                }
            },
        }
        with patch_config_path(config):
            profile = get_active_profile()
        assert profile["department_codes"] == ["25C1", "25C2", "25C3"]
        assert profile["watermark_text"] == "建筑结构所"

    def test_load_electric_profile(self, patch_config_path):
        from utils.dept_config import get_active_profile
        config = {
            "department_profile": "电气工程及其自动化所",
            "department_profiles": {
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        with patch_config_path(config):
            profile = get_active_profile()
        assert profile["department_codes"] == ["25D1", "25D2"]
        assert profile["organization_filter"] == "河北分公司-电气工程及其自动化所"


# =========================================================================
# 3. 多参数族切换
# =========================================================================

class TestProfileSwitching:
    """切换 department_profile 实现不同科室"""

    def test_switch_between_profiles(self, patch_config_path):
        from utils import dept_config as dc

        config = {
            "department_profile": "建筑结构所",
            "department_profiles": {
                "建筑结构所": {
                    "department_codes": ["25C1", "25C2", "25C3"],
                    "department_code_mapping": {
                        "25C1": "结构一室",
                        "25C2": "结构二室",
                        "25C3": "建筑总图室",
                    },
                    "director_role_mapping": {
                        "一室主任": "结构一室",
                    },
                },
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        # 先加载建筑结构所
        with patch_config_path(config):
            profile1 = dc.get_active_profile()
            assert profile1["department_codes"] == ["25C1", "25C2", "25C3"]

        # 切换到电气所
        dc._profile_cache = None
        config["department_profile"] = "电气工程及其自动化所"
        with patch_config_path(config):
            profile2 = dc.get_active_profile()
            assert profile2["department_codes"] == ["25D1", "25D2"]


# =========================================================================
# 4. 缓存与 reload
# =========================================================================

class TestCacheAndReload:

    def test_cache_prevents_repeated_loading(self, patch_config_path):
        from utils.dept_config import get_active_profile
        config = {
            "department_profile": "建筑结构所",
            "department_profiles": {
                "建筑结构所": {
                    "department_codes": ["25C1"],
                    "department_code_mapping": {"25C1": "一室"},
                    "director_role_mapping": {"一室主任": "一室"},
                },
            },
        }
        with patch_config_path(config):
            p1 = get_active_profile()
            p2 = get_active_profile()
        assert p1 is p2  # 同一对象（缓存命中）

    def test_reload_clears_cache(self, patch_config_path):
        from utils import dept_config as dc
        config = {
            "department_profile": "建筑结构所",
            "department_profiles": {
                "建筑结构所": {
                    "department_codes": ["25C1"],
                    "department_code_mapping": {"25C1": "一室"},
                    "director_role_mapping": {"一室主任": "一室"},
                },
            },
        }
        with patch_config_path(config):
            p1 = dc.get_active_profile()
            dc._profile_cache = None  # 手动清缓存模拟 reload
            p2 = dc.get_active_profile()
        assert p1 is not p2


# =========================================================================
# 5. 字段缺失自动补全
# =========================================================================

class TestFieldAutoComplete:
    """config.json 中的参数族缺少某些字段时，应从默认值补全"""

    def test_missing_fields_filled_from_default(self, patch_config_path):
        from utils.dept_config import get_active_profile
        config = {
            "department_profile": "建筑结构所",
            "department_profiles": {
                "建筑结构所": {
                    "department_codes": ["25C1"],
                    "department_code_mapping": {"25C1": "一室"},
                    # 故意缺少 director_role_mapping、watermark_text 等
                },
            },
        }
        with patch_config_path(config):
            profile = get_active_profile()
        # 缺失字段应从默认值补全
        assert "director_role_mapping" in profile
        assert "watermark_text" in profile
        assert profile["watermark_text"] == "建筑结构所"


# =========================================================================
# 6. 便捷访问函数 —— 建筑结构所默认值
# =========================================================================

class TestConvenienceFunctionsDefault:
    """使用默认参数族测试所有便捷函数"""

    def test_get_department_codes(self):
        from utils.dept_config import get_department_codes
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            codes = get_department_codes()
        assert codes == ["25C1", "25C2", "25C3"]

    def test_get_department_code_mapping(self):
        from utils.dept_config import get_department_code_mapping
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            mapping = get_department_code_mapping()
        assert mapping == {
            "25C1": "结构一室",
            "25C2": "结构二室",
            "25C3": "建筑总图室",
        }

    def test_get_department_names(self):
        from utils.dept_config import get_department_names
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            names = get_department_names()
        assert names == ["结构一室", "结构二室", "建筑总图室"]

    def test_get_organization_filter(self):
        from utils.dept_config import get_organization_filter
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert get_organization_filter() == "河北分公司-建筑结构所"

    def test_get_organization_filter_file6(self):
        from utils.dept_config import get_organization_filter_file6
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert get_organization_filter_file6() == "河北分公司.建筑结构所"

    def test_get_director_role_mapping(self):
        from utils.dept_config import get_director_role_mapping
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            mapping = get_director_role_mapping()
        assert "一室主任" in mapping
        assert mapping["一室主任"] == "结构一室"

    def test_get_director_roles(self):
        from utils.dept_config import get_director_roles
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            roles = get_director_roles()
        assert set(roles) == {"一室主任", "二室主任", "建筑总图室主任"}

    def test_get_superior_keywords(self):
        from utils.dept_config import get_superior_keywords
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            keywords = get_superior_keywords()
        # 应包含室主任角色 + 通用上级角色
        assert "一室主任" in keywords
        assert "所领导" in keywords
        assert "接口工程师" in keywords

    def test_get_time_window_roles(self):
        from utils.dept_config import get_time_window_roles
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            roles = get_time_window_roles()
        assert "所领导" in roles
        assert "一室主任" in roles

    def test_get_use_workdays_roles(self):
        from utils.dept_config import get_use_workdays_roles
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            roles = get_use_workdays_roles()
        assert "所领导" in roles
        assert "建筑总图室主任" in roles

    def test_get_default_folder_path(self):
        from utils.dept_config import get_default_folder_path
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            path = get_default_folder_path()
        assert "建筑结构所" in path

    def test_get_watermark_text(self):
        from utils.dept_config import get_watermark_text
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert get_watermark_text() == "建筑结构所"

    def test_get_role_export_days(self):
        from utils.dept_config import get_role_export_days
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            days = get_role_export_days()
        # 室主任角色均为 7 天
        assert days["一室主任"] == 7
        assert days["二室主任"] == 7
        assert days["建筑总图室主任"] == 7
        # 所领导 2 天
        assert days["所领导"] == 2
        # 管理员 / 设计人员无限制
        assert days["管理员"] is None
        assert days["设计人员"] is None

    def test_get_help_section_map(self):
        from utils.dept_config import get_help_section_map
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            mapping = get_help_section_map()
        assert mapping["设计人员"] == "2-设计人员使用指南"
        assert mapping["一室主任"] == "3-室主任使用指南"
        assert mapping["所领导"] == "4-所领导使用指南"
        assert mapping["管理员"] == "5-管理员使用指南"


# =========================================================================
# 7. 便捷访问函数 —— 电气所参数族
# =========================================================================

class TestConvenienceFunctionsElectric:
    """使用电气所参数族测试便捷函数"""

    @pytest.fixture(autouse=True)
    def load_electric_profile(self, patch_config_path):
        config = {
            "department_profile": "电气工程及其自动化所",
            "department_profiles": {
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        with patch_config_path(config):
            yield

    def test_codes(self):
        from utils.dept_config import get_department_codes
        assert get_department_codes() == ["25D1", "25D2"]

    def test_names(self):
        from utils.dept_config import get_department_names
        assert get_department_names() == ["电气一室", "电气二室"]

    def test_org_filter(self):
        from utils.dept_config import get_organization_filter
        assert get_organization_filter() == "河北分公司-电气工程及其自动化所"

    def test_org_filter_file6(self):
        from utils.dept_config import get_organization_filter_file6
        assert get_organization_filter_file6() == "河北分公司.电气工程及其自动化所"

    def test_director_roles(self):
        from utils.dept_config import get_director_roles
        assert set(get_director_roles()) == {"电气一室主任", "电气二室主任"}

    def test_superior_keywords_include_director_and_generic(self):
        from utils.dept_config import get_superior_keywords
        kw = get_superior_keywords()
        assert "电气一室主任" in kw
        assert "所领导" in kw
        assert "接口工程师" in kw
        # 不应包含建筑结构所的角色
        assert "一室主任" not in kw

    def test_help_section_map_uses_electric_directors(self):
        from utils.dept_config import get_help_section_map
        mapping = get_help_section_map()
        assert "电气一室主任" in mapping
        assert mapping["电气一室主任"] == "3-室主任使用指南"
        # 不应包含建筑结构所的角色
        assert "一室主任" not in mapping

    def test_role_export_days_uses_electric_directors(self):
        from utils.dept_config import get_role_export_days
        days = get_role_export_days()
        # 电气所室主任角色
        assert days["电气一室主任"] == 7
        assert days["电气二室主任"] == 7
        # 通用角色
        assert days["所领导"] == 2
        assert days["管理员"] is None
        assert days["设计人员"] is None
        # 不应包含建筑结构所的角色
        assert "一室主任" not in days
        assert "建筑总图室主任" not in days

    def test_watermark(self):
        from utils.dept_config import get_watermark_text
        assert get_watermark_text() == "电气工程及其自动化所"


# =========================================================================
# 8. 辅助匹配函数
# =========================================================================

class TestMatchingHelpers:
    """测试 map_code_to_department / match_department_name / contains_department_code"""

    def test_map_code_to_department_hit(self):
        from utils.dept_config import map_code_to_department
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert map_code_to_department("XX-25C1-YY") == "结构一室"
            assert map_code_to_department("25C2abc") == "结构二室"
            assert map_code_to_department("前缀25C3后缀") == "建筑总图室"

    def test_map_code_to_department_miss(self):
        from utils.dept_config import map_code_to_department
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert map_code_to_department("25D1") == ""
            assert map_code_to_department("") == ""
            assert map_code_to_department("无关内容") == ""

    def test_match_department_name_hit(self):
        from utils.dept_config import match_department_name
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert match_department_name("河北-结构一室-xx") == "结构一室"
            assert match_department_name("结构二室") == "结构二室"
            assert match_department_name("建筑总图室(A)") == "建筑总图室"

    def test_match_department_name_miss_returns_original(self):
        from utils.dept_config import match_department_name
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert match_department_name("电气一室") == "电气一室"
            assert match_department_name("") == ""

    def test_contains_department_code_true(self):
        from utils.dept_config import contains_department_code
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert contains_department_code("xx25C1yy") is True
            assert contains_department_code("25C2") is True
            assert contains_department_code("25C3!!") is True

    def test_contains_department_code_false(self):
        from utils.dept_config import contains_department_code
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert contains_department_code("25D1") is False
            assert contains_department_code("") is False
            assert contains_department_code("C1C2C3") is False

    def test_matching_with_electric_profile(self, patch_config_path):
        """电气所参数族下的匹配"""
        from utils.dept_config import (
            map_code_to_department,
            match_department_name,
            contains_department_code,
        )
        config = {
            "department_profile": "电气工程及其自动化所",
            "department_profiles": {
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        with patch_config_path(config):
            # 编码匹配
            assert map_code_to_department("25D1-xxx") == "电气一室"
            assert map_code_to_department("25C1-xxx") == ""  # 建筑的不匹配
            # 名称匹配
            assert match_department_name("电气一室-张工") == "电气一室"
            assert match_department_name("结构一室") == "结构一室"  # 未匹配返回原文
            # 编码包含
            assert contains_department_code("25D2-test") is True
            assert contains_department_code("25C1-test") is False


# =========================================================================
# 9. distribution.py 集成测试
# =========================================================================

class TestDistributionIntegration:
    """distribution.py 中 is_director / get_department 使用 dept_config"""

    def test_is_director_with_default_profile(self):
        from services.distribution import is_director
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert is_director(["一室主任"]) is True
            assert is_director(["设计人员"]) is False

    def test_get_department_with_default_profile(self):
        from services.distribution import get_department
        with patch("utils.dept_config._get_config_path",
                    return_value="/nonexistent"):
            assert get_department(["一室主任"]) == "结构一室"
            assert get_department(["建筑总图室主任"]) == "建筑总图室"
            assert get_department(["设计人员"]) == ""

    def test_is_director_with_electric_profile(self, patch_config_path):
        from utils import dept_config as dc
        from services.distribution import is_director
        config = {
            "department_profile": "电气工程及其自动化所",
            "department_profiles": {
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        with patch_config_path(config):
            # 需要也 reload distribution 使用的函数
            dc._profile_cache = None  # 让 dept_config 重新加载
            assert is_director(["电气一室主任"]) is True
            assert is_director(["一室主任"]) is False  # 建筑的角色不匹配

    def test_get_department_with_electric_profile(self, patch_config_path):
        from utils import dept_config as dc
        from services.distribution import get_department
        config = {
            "department_profile": "电气工程及其自动化所",
            "department_profiles": {
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        with patch_config_path(config):
            dc._profile_cache = None
            assert get_department(["电气二室主任"]) == "电气二室"


# =========================================================================
# 10. hooks.py 集成测试
# =========================================================================

class TestHooksIntegration:
    """registry/hooks.py 中 superior_roles 使用 dept_config"""

    def test_superior_roles_uses_config(self, patch_config_path):
        """验证 hooks 中的 superior_roles 列表来自 dept_config"""
        from utils.dept_config import get_superior_keywords
        config = {
            "department_profile": "电气工程及其自动化所",
            "department_profiles": {
                "电气工程及其自动化所": ELECTRIC_PROFILE,
            },
        }
        with patch_config_path(config):
            kw = get_superior_keywords()
        assert "电气一室主任" in kw
        assert "电气二室主任" in kw
        assert "所领导" in kw
        assert "接口工程师" in kw


# =========================================================================
# 11. pending_cache.py 集成测试
# =========================================================================

class TestPendingCacheIntegration:
    """write_tasks/pending_cache.py 中 SUPERIOR_KEYWORDS 来自 dept_config"""

    def test_superior_keywords_loaded(self):
        """验证 SUPERIOR_KEYWORDS 模块级变量包含正确角色"""
        from write_tasks.pending_cache import SUPERIOR_KEYWORDS
        assert "所领导" in SUPERIOR_KEYWORDS
        assert "接口工程师" in SUPERIOR_KEYWORDS
        # 应包含室主任角色（具体名称取决于当前 profile）
        assert len(SUPERIOR_KEYWORDS) >= 5

    def test_designer_keyword_unchanged(self):
        """DESIGNER_KEYWORD 是通用角色，不应随参数族变化"""
        from write_tasks.pending_cache import DESIGNER_KEYWORD
        assert DESIGNER_KEYWORD == "设计人员"


# =========================================================================
# 12. help_viewer.py 集成测试
# =========================================================================

class TestHelpViewerIntegration:
    """ui/help_viewer.py 的 ROLE_SECTION_MAP 来自 dept_config"""

    def test_role_section_map_loaded(self):
        from ui.help_viewer import HelpViewer
        mapping = HelpViewer.ROLE_SECTION_MAP
        assert "设计人员" in mapping
        assert "所领导" in mapping
        assert "管理员" in mapping
