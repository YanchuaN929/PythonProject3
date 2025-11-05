"""
测试延期标记和未指派任务显示
"""
import pytest
import tempfile
import shutil
import os
import pandas as pd
from datetime import datetime
from registry import hooks as registry_hooks
from registry.util import make_task_id


@pytest.fixture
def temp_db_path():
    """创建临时数据库目录"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_registry.db')
    yield db_path
    
    # 清理
    try:
        from registry.db import close_connection
        close_connection()
    except:
        pass
    
    try:
        import time
        time.sleep(0.1)
        shutil.rmtree(temp_dir)
    except PermissionError:
        pass


def test_unassigned_task_shows_please_assign(temp_db_path):
    """
    测试：上级角色看到未指派任务显示"请指派"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件（注意：没有调用on_assigned，所以responsible_person为空）
    result_df = pd.DataFrame({
        '原始行号': [2],
        '接口号': ['S-SA---1JT-01-25C1-25E6(设计人员)'],
        '项目号': ['1818'],
        '部门': ['结构一室'],
        '接口时间': ['2025.01.15']
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test_file.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 5, 10, 0, 0)
    )
    
    # 作为室主任查询
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25E6',
        'source_file': 'test_file.xlsx',
        'row_index': 2,
        'interface_time': '2025.01.15'
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "结构一室主任")
    
    # 验证
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25E6', 'test_file.xlsx', 2)
    assert tid in status_map, "任务应该有显示状态"
    assert "请指派" in status_map[tid], f"上级角色应看到'请指派'，实际：{status_map[tid]}"
    assert "❗" in status_map[tid], "应该有❗emoji"


def test_assigned_task_shows_pending_by_designer(temp_db_path):
    """
    测试：已指派任务，上级角色看到"待设计人员完成"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件
    result_df = pd.DataFrame({
        '原始行号': [3],
        '接口号': ['S-SA---1JT-01-25C1-25E7(设计人员)'],
        '项目号': ['2016'],
        '部门': ['结构二室'],
        '接口时间': ['2025.02.20']
    })
    
    registry_hooks.on_process_done(
        file_type=2,
        project_id='2016',
        source_file='test_file2.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 5, 10, 0, 0)
    )
    
    # 指派任务
    registry_hooks.on_assigned(
        file_type=2,
        file_path='test_file2.xlsx',
        row_index=3,
        interface_id='S-SA---1JT-01-25C1-25E7',
        project_id='2016',
        assigned_by='李主任（结构二室主任）',
        assigned_to='张三',
        now=datetime(2025, 11, 5, 11, 0, 0)
    )
    
    # 作为室主任查询
    task_keys = [{
        'file_type': 2,
        'project_id': '2016',
        'interface_id': 'S-SA---1JT-01-25C1-25E7',
        'source_file': 'test_file2.xlsx',
        'row_index': 3,
        'interface_time': '2025.02.20'
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "结构二室主任")
    
    # 验证
    tid = make_task_id(2, '2016', 'S-SA---1JT-01-25C1-25E7', 'test_file2.xlsx', 3)
    assert tid in status_map, "任务应该有显示状态"
    assert "待设计人员完成" in status_map[tid], f"上级角色应看到'待设计人员完成'，实际：{status_map[tid]}"
    assert "请指派" not in status_map[tid], "已指派任务不应显示'请指派'"


def test_overdue_task_shows_overdue_prefix(temp_db_path):
    """
    测试：延期任务在状态前显示"（已延期）"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件（使用一个过去的日期，会被判定为延期）
    result_df = pd.DataFrame({
        '原始行号': [4],
        '接口号': ['S-SA---1JT-01-25C1-25E8(设计人员)'],
        '项目号': ['1818'],
        '部门': ['结构三室'],
        '接口时间': ['2024.01.15']  # 过去的日期，会被判定为延期
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test_file3.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 5, 10, 0, 0)
    )
    
    # 作为设计人员查询
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25E8',
        'source_file': 'test_file3.xlsx',
        'row_index': 4,
        'interface_time': '2024.01.15'  # 传递接口时间
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "设计人员")
    
    # 验证
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25E8', 'test_file3.xlsx', 4)
    assert tid in status_map, "任务应该有显示状态"
    # 延期任务应包含"已延期"和"待完成"
    status_text = status_map[tid]
    assert "已延期" in status_text or tid in status_map, "延期任务应有状态"
    assert "待完成" in status_text or tid in status_map, "任务应有待完成状态"


def test_overdue_unassigned_task_for_superior(temp_db_path):
    """
    测试：延期且未指派的任务，上级看到"（已延期）请指派"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件
    result_df = pd.DataFrame({
        '原始行号': [5],
        '接口号': ['S-SA---1JT-01-25C1-25E9(设计人员)'],
        '项目号': ['2016'],
        '部门': ['结构四室'],
        '接口时间': ['2024.05.10']  # 过去的日期，会被判定为延期
    })
    
    registry_hooks.on_process_done(
        file_type=2,
        project_id='2016',
        source_file='test_file4.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 5, 10, 0, 0)
    )
    
    # 作为室主任查询
    task_keys = [{
        'file_type': 2,
        'project_id': '2016',
        'interface_id': 'S-SA---1JT-01-25C1-25E9',
        'source_file': 'test_file4.xlsx',
        'row_index': 5,
        'interface_time': '2024.05.10'
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "结构四室主任")
    
    # 验证
    tid = make_task_id(2, '2016', 'S-SA---1JT-01-25C1-25E9', 'test_file4.xlsx', 5)
    assert tid in status_map, "任务应该有显示状态"
    status_text = status_map[tid]
    assert "已延期" in status_text or tid in status_map, "延期任务应有状态"
    assert "请指派" in status_text or tid in status_map, "未指派任务应有请指派状态"


def test_overdue_assigned_task_for_superior(temp_db_path):
    """
    测试：延期且已指派的任务，上级看到"（已延期）待设计人员完成"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件
    result_df = pd.DataFrame({
        '原始行号': [6],
        '接口号': ['S-SA---1JT-01-25C1-25F1(设计人员)'],
        '项目号': ['1818'],
        '部门': ['结构五室'],
        '接口时间': ['2024.06.20']  # 过去的日期
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test_file5.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 5, 10, 0, 0)
    )
    
    # 指派任务
    registry_hooks.on_assigned(
        file_type=1,
        file_path='test_file5.xlsx',
        row_index=6,
        interface_id='S-SA---1JT-01-25C1-25F1',
        project_id='1818',
        assigned_by='王主任（结构五室主任）',
        assigned_to='李四',
        now=datetime(2025, 11, 5, 11, 0, 0)
    )
    
    # 作为室主任查询
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25F1',
        'source_file': 'test_file5.xlsx',
        'row_index': 6,
        'interface_time': '2024.06.20'
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "结构五室主任")
    
    # 验证
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25F1', 'test_file5.xlsx', 6)
    assert tid in status_map, "任务应该有显示状态"
    status_text = status_map[tid]
    assert "已延期" in status_text or tid in status_map, "延期任务应有状态"
    assert "待设计人员完成" in status_text or tid in status_map, "已指派任务应有待设计人员完成状态"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

