from debug_tools.visibility import engineer_project_from_role


def test_engineer_project_from_role_tolerant():
    assert engineer_project_from_role("1818接口工程师") == "1818"
    assert engineer_project_from_role(" 1818 接口工程师 ") == "1818"
    assert engineer_project_from_role("1818接口工程师（临时）") == "1818"
    assert engineer_project_from_role("无关角色") is None


