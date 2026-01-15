import os
import sys


def test_write_task_state_defaults_to_app_root(monkeypatch):
    # 默认 state_path 应固定在“程序根目录/result_cache/”
    import importlib
    from write_tasks import manager as manager_module

    importlib.reload(manager_module)
    manager_module.reset_write_task_manager_for_tests()

    mgr = manager_module.get_write_task_manager()
    try:
        # 计算期望的 app_root（与 manager._get_app_directory 同口径）
        if getattr(sys, "frozen", False):
            app_root = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # write_tasks/manager.py 的父目录就是项目根
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(manager_module.__file__)))

        assert os.path.normcase(str(mgr.state_path)).startswith(os.path.normcase(os.path.join(app_root, "result_cache")))
        assert mgr.state_path.name == "write_tasks_state.json"
    finally:
        manager_module.reset_write_task_manager_for_tests()


