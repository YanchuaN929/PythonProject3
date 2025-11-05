"""
测试所有新任务（无论是否指派）都显示"待完成"状态
"""
import pytest
import tempfile
import shutil
import os
import pandas as pd
from datetime import datetime
from registry import hooks as registry_hooks
from registry.service import get_display_status
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


def test_unassigned_task_shows_pending_status(temp_db_path):
    """
    测试：无指派的任务（设计人员自己职责内）也应显示"待完成"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件（无指派任务）
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
        now=datetime(2025, 11, 4, 10, 0, 0)
    )
    
    # 查询显示状态
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25E6',
        'source_file': 'test_file.xlsx',
        'row_index': 2
    }]
    
    status_map = registry_hooks.get_display_status(task_keys)
    
    # 验证：应该显示"📌 待完成"
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25E6', 'test_file.xlsx', 2)
    assert tid in status_map, "任务应该有显示状态"
    assert "待完成" in status_map[tid], f"无指派任务应显示'待完成'，实际：{status_map[tid]}"
    assert "📌" in status_map[tid], "应包含Emoji"


def test_assigned_task_shows_pending_status(temp_db_path):
    """
    测试：有指派的任务同样显示"待完成"
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
        now=datetime(2025, 11, 4, 10, 0, 0)
    )
    
    # 指派任务
    registry_hooks.on_assigned(
        file_type=2,
        file_path='test_file2.xlsx',
        row_index=3,
        interface_id='S-SA---1JT-01-25C1-25E7',
        project_id='2016',
        assigned_by='王工（2016接口工程师）',
        assigned_to='张三',
        now=datetime(2025, 11, 4, 11, 0, 0)
    )
    
    # 查询显示状态
    task_keys = [{
        'file_type': 2,
        'project_id': '2016',
        'interface_id': 'S-SA---1JT-01-25C1-25E7',
        'source_file': 'test_file2.xlsx',
        'row_index': 3
    }]
    
    status_map = registry_hooks.get_display_status(task_keys)
    
    # 验证：应该显示"📌 待完成"
    tid = make_task_id(2, '2016', 'S-SA---1JT-01-25C1-25E7', 'test_file2.xlsx', 3)
    assert tid in status_map, "任务应该有显示状态"
    assert "待完成" in status_map[tid], f"有指派任务应显示'待完成'，实际：{status_map[tid]}"
    assert "📌" in status_map[tid], "应包含Emoji"


def test_completed_unassigned_shows_waiting_superior(temp_db_path):
    """
    测试：无指派任务完成后显示"⏳ 待上级确认"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件
    result_df = pd.DataFrame({
        '原始行号': [4],
        '接口号': ['S-SA---1JT-01-25C1-25E8(设计人员)'],
        '项目号': ['1818'],
        '部门': ['结构三室'],
        '接口时间': ['2025.03.10']
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test_file3.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 4, 10, 0, 0)
    )
    
    # 设计人员填写回文单号
    registry_hooks.on_response_written(
        file_type=1,
        file_path='test_file3.xlsx',
        row_index=4,
        interface_id='S-SA---1JT-01-25C1-25E8',
        response_number='RES-001',
        user_name='张三',
        project_id='1818',
        role='设计人员',
        now=datetime(2025, 11, 4, 14, 0, 0)
    )
    
    # 查询显示状态
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25E8',
        'source_file': 'test_file3.xlsx',
        'row_index': 4
    }]
    
    status_map = registry_hooks.get_display_status(task_keys)
    
    # 验证：应该显示"⏳ 待上级确认"
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25E8', 'test_file3.xlsx', 4)
    assert tid in status_map, "任务应该有显示状态"
    assert "待上级确认" in status_map[tid], f"无指派任务完成后应显示'待上级确认'，实际：{status_map[tid]}"
    assert "⏳" in status_map[tid], "应包含Emoji"


def test_completed_assigned_shows_waiting_assigner(temp_db_path):
    """
    测试：有指派任务完成后显示"⏳ 待指派人确认"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件
    result_df = pd.DataFrame({
        '原始行号': [5],
        '接口号': ['S-SA---1JT-01-25C1-25E9(设计人员)'],
        '项目号': ['2016'],
        '部门': ['结构四室'],
        '接口时间': ['2025.04.05']
    })
    
    registry_hooks.on_process_done(
        file_type=2,
        project_id='2016',
        source_file='test_file4.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 4, 10, 0, 0)
    )
    
    # 指派任务
    registry_hooks.on_assigned(
        file_type=2,
        file_path='test_file4.xlsx',
        row_index=5,
        interface_id='S-SA---1JT-01-25C1-25E9',
        project_id='2016',
        assigned_by='李主任（结构四室主任）',
        assigned_to='王五',
        now=datetime(2025, 11, 4, 11, 0, 0)
    )
    
    # 设计人员填写回文单号
    registry_hooks.on_response_written(
        file_type=2,
        file_path='test_file4.xlsx',
        row_index=5,
        interface_id='S-SA---1JT-01-25C1-25E9',
        response_number='RES-002',
        user_name='王五',
        project_id='2016',
        role='设计人员',
        now=datetime(2025, 11, 4, 15, 0, 0)
    )
    
    # 查询显示状态
    task_keys = [{
        'file_type': 2,
        'project_id': '2016',
        'interface_id': 'S-SA---1JT-01-25C1-25E9',
        'source_file': 'test_file4.xlsx',
        'row_index': 5
    }]
    
    status_map = registry_hooks.get_display_status(task_keys)
    
    # 验证：应该显示"⏳ 待指派人确认"
    tid = make_task_id(2, '2016', 'S-SA---1JT-01-25C1-25E9', 'test_file4.xlsx', 5)
    assert tid in status_map, "任务应该有显示状态"
    assert "待指派人确认" in status_map[tid], f"有指派任务完成后应显示'待指派人确认'，实际：{status_map[tid]}"
    assert "⏳" in status_map[tid], "应包含Emoji"


def test_status_not_overwritten_on_reprocess(temp_db_path):
    """
    测试：再次处理文件时，已有的display_status不会被覆盖
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 第一次处理文件
    result_df = pd.DataFrame({
        '原始行号': [6],
        '接口号': ['S-SA---1JT-01-25C1-25F1(设计人员)'],
        '项目号': ['1818'],
        '部门': ['结构五室'],
        '接口时间': ['2025.05.15']
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test_file5.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 4, 10, 0, 0)
    )
    
    # 设计人员填写回文单号（状态变为"待上级确认"）
    registry_hooks.on_response_written(
        file_type=1,
        file_path='test_file5.xlsx',
        row_index=6,
        interface_id='S-SA---1JT-01-25C1-25F1',
        response_number='RES-003',
        user_name='赵六',
        project_id='1818',
        role='设计人员',
        now=datetime(2025, 11, 4, 14, 0, 0)
    )
    
    # 再次处理文件（模拟文件更新）
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test_file5.xlsx',
        result_df=result_df,
        now=datetime(2025, 11, 4, 16, 0, 0)
    )
    
    # 查询显示状态
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25F1',
        'source_file': 'test_file5.xlsx',
        'row_index': 6
    }]
    
    status_map = registry_hooks.get_display_status(task_keys)
    
    # 验证：状态应该仍然是"⏳ 待上级确认"，不应被改回"待完成"
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25F1', 'test_file5.xlsx', 6)
    assert tid in status_map, "任务应该有显示状态"
    assert "待上级确认" in status_map[tid], f"再次处理文件时状态不应被覆盖，应保持'待上级确认'，实际：{status_map[tid]}"
    assert "待完成" not in status_map[tid], "状态不应该回退到'待完成'"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

