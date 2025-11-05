"""
测试基于角色的状态显示
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


def test_designer_sees_pending(temp_db_path):
    """
    测试：设计人员看到自己的任务显示"待完成"
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟处理文件
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
    
    # 作为设计人员查询
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25E6',
        'source_file': 'test_file.xlsx',
        'row_index': 2
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "设计人员")
    
    # 验证
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25E6', 'test_file.xlsx', 2)
    assert tid in status_map, "任务应该有显示状态"
    assert "待完成" in status_map[tid], f"设计人员应看到'待完成'，实际：{status_map[tid]}"
    assert "待设计人员完成" not in status_map[tid], "设计人员不应看到'待设计人员完成'"


def test_superior_sees_pending_by_designer(temp_db_path):
    """
    测试：上级角色看到已指派给设计人员的任务显示"待设计人员完成"
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
    
    # 【新增】指派任务
    registry_hooks.on_assigned(
        file_type=2,
        file_path='test_file2.xlsx',
        row_index=3,
        interface_id='S-SA---1JT-01-25C1-25E7',
        project_id='2016',
        assigned_by='李主任（结构二室主任）',
        assigned_to='张三',
        now=datetime(2025, 11, 4, 11, 0, 0)
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


def test_overlapping_role_sees_pending(temp_db_path):
    """
    测试：同时是设计人员和接口工程师的用户，看到已指派给自己的任务显示"待完成"
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
    
    # 【新增】指派任务给这个重叠角色的用户
    registry_hooks.on_assigned(
        file_type=1,
        file_path='test_file3.xlsx',
        row_index=4,
        interface_id='S-SA---1JT-01-25C1-25E8',
        project_id='1818',
        assigned_by='系统管理员',
        assigned_to='王工',  # 重叠角色用户
        now=datetime(2025, 11, 4, 11, 0, 0)
    )
    
    # 作为"设计人员+1818接口工程师"查询
    task_keys = [{
        'file_type': 1,
        'project_id': '1818',
        'interface_id': 'S-SA---1JT-01-25C1-25E8',
        'source_file': 'test_file3.xlsx',
        'row_index': 4,
        'interface_time': '2025.03.10'
    }]
    
    status_map = registry_hooks.get_display_status(task_keys, "设计人员,1818接口工程师")
    
    # 验证
    tid = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-25E8', 'test_file3.xlsx', 4)
    assert tid in status_map, "任务应该有显示状态"
    assert "待完成" in status_map[tid], f"重叠角色应看到'待完成'，实际：{status_map[tid]}"
    assert "待设计人员完成" not in status_map[tid], "重叠角色不应看到'待设计人员完成'"


def test_completed_status_unchanged_by_role(temp_db_path):
    """
    测试：已完成任务的状态不受角色影响（待确认状态不变）
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
    
    # 设计人员填写回文单号
    registry_hooks.on_response_written(
        file_type=2,
        file_path='test_file4.xlsx',
        row_index=5,
        interface_id='S-SA---1JT-01-25C1-25E9',
        response_number='RES-001',
        user_name='张三',
        project_id='2016',
        role='设计人员',
        now=datetime(2025, 11, 4, 14, 0, 0)
    )
    
    task_keys = [{
        'file_type': 2,
        'project_id': '2016',
        'interface_id': 'S-SA---1JT-01-25C1-25E9',
        'source_file': 'test_file4.xlsx',
        'row_index': 5
    }]
    
    # 作为设计人员查询
    status_map_designer = registry_hooks.get_display_status(task_keys, "设计人员")
    # 作为上级查询
    status_map_superior = registry_hooks.get_display_status(task_keys, "结构四室主任")
    
    # 验证：两个角色看到的待确认状态应该一致
    tid = make_task_id(2, '2016', 'S-SA---1JT-01-25C1-25E9', 'test_file4.xlsx', 5)
    assert tid in status_map_designer
    assert tid in status_map_superior
    assert "待上级确认" in status_map_designer[tid]
    assert "待上级确认" in status_map_superior[tid]
    assert status_map_designer[tid] == status_map_superior[tid], "待确认状态应该对所有角色一致"


def test_multiple_files_status_query(temp_db_path):
    """
    测试：模拟window.py的逻辑，查询多个源文件中的任务状态
    """
    # 配置Registry
    registry_hooks.set_data_folder(os.path.dirname(temp_db_path))
    
    # 模拟3个不同文件中的任务
    for i, file_name in enumerate(['file1.xlsx', 'file2.xlsx', 'file3.xlsx']):
        result_df = pd.DataFrame({
            '原始行号': [i + 2],
            '接口号': [f'S-SA---1JT-01-25C1-25{i}(设计人员)'],
            '项目号': ['1818'],
            '部门': ['结构一室'],
            '接口时间': ['2025.01.15']
        })
        
        registry_hooks.on_process_done(
            file_type=1,
            project_id='1818',
            source_file=file_name,
            result_df=result_df,
            now=datetime(2025, 11, 4, 10, 0, 0)
        )
    
    # 模拟window.py的查询逻辑：对同一个接口号尝试所有源文件
    source_files = ['file1.xlsx', 'file2.xlsx', 'file3.xlsx']
    task_keys = []
    
    # 对第一个接口号，尝试所有文件（模拟不知道它在哪个文件）
    for source_file in source_files:
        task_keys.append({
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'S-SA---1JT-01-25C1-250',
            'source_file': source_file,
            'row_index': 2
        })
    
    status_map = registry_hooks.get_display_status(task_keys, "设计人员")
    
    # 验证：应该找到file1.xlsx中的任务
    tid1 = make_task_id(1, '1818', 'S-SA---1JT-01-25C1-250', 'file1.xlsx', 2)
    assert tid1 in status_map, "应该找到file1.xlsx中的任务"
    assert "待完成" in status_map[tid1]


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

