"""
测试3个严重问题的修复

问题1：被忽略的任务仍然显示（显示为❗标记）
问题2：预期时间变化时未触发归档+自动取消忽略
问题3：文件2不停输出"接口时间变化，重置状态"
"""

import pytest
import tempfile
import os
from datetime import datetime
from registry import hooks as registry_hooks
from registry.service import (
    batch_upsert_tasks,
    mark_ignored_batch,
    find_task_by_business_id,
    get_display_status,
    make_task_id,
    should_reset_task_status
)
from registry.migrate import migrate_if_needed


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_registry.db")
        
        # 配置 registry
        registry_hooks.set_data_folder(tmpdir)
        
        # 修改 _cfg 函数使其返回我们的测试数据库路径
        original_cfg = registry_hooks._cfg
        registry_hooks._cfg = lambda: {'registry_db_path': db_path, 'wal': False}
        
        # 确保数据库已迁移
        migrate_if_needed(db_path)
        
        try:
            yield db_path
        finally:
            # 恢复原始配置
            registry_hooks._cfg = original_cfg
            
            # 关闭所有数据库连接
            from registry.db import _CONN
            if _CONN is not None:
                try:
                    _CONN.close()
                except:
                    pass
            
            # 等待一下让文件锁释放
            import time
            time.sleep(0.1)


def test_problem1_ignored_tasks_not_displayed(temp_db):
    """
    问题1：被忽略的任务应该完全不显示（不在status_map中）
    
    步骤：
    1. 创建任务
    2. 忽略任务
    3. 调用get_display_status
    4. 验证任务不在返回的status_map中
    """
    now = datetime.now()
    
    # 1. 创建任务
    task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'PROB1-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '测试人员'
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_data, now)
    
    # 2. 忽略任务
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'PROB1-TEST',
        'interface_time': '2025.11.07'
    }]
    result = mark_ignored_batch(temp_db, False, task_keys, '测试用户', '测试', now)
    assert result['success_count'] == 1
    
    # 3. 调用get_display_status
    display_keys = [{
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'PROB1-TEST',
        'source_file': 'test.xlsx',
        'row_index': 10
    }]
    statuses = get_display_status(temp_db, False, display_keys, [])
    
    # 4. 验证任务不在status_map中
    tid = make_task_id(1, '2016', 'PROB1-TEST', 'test.xlsx', 10)
    assert tid not in statuses, "已忽略的任务不应出现在status_map中"
    print("✓ 问题1验证通过：已忽略任务不在status_map中")


def test_problem2_time_change_triggers_archive_and_unignore(temp_db):
    """
    问题2：预期时间变化时应该：
    1. 归档旧记录（如果有完整数据链）
    2. 自动取消忽略状态
    3. 创建新记录
    
    步骤：
    1. 创建任务并完成+确认（形成完整数据链）
    2. 忽略任务
    3. 修改预期时间并重新导入
    4. 验证：旧记录被归档，ignored状态被取消，新记录状态为待完成
    """
    now = datetime.now()
    
    # 1. 创建任务并完成+确认
    task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'PROB2-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '测试人员',
            '_completed_col_value': '2025-11-08'
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_data, now)
    
    # 标记为已完成
    from registry.service import mark_completed
    key = {'file_type': 1, 'project_id': '2016', 'interface_id': 'PROB2-TEST'}
    mark_completed(temp_db, False, key, now)
    
    # 标记为已确认
    from registry.service import mark_confirmed
    mark_confirmed(temp_db, False, key, now, '上级')
    
    # 验证已确认
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'PROB2-TEST')
    assert task['status'] == 'confirmed'
    assert task['completed_at'] is not None
    assert task['confirmed_at'] is not None
    print("✓ 任务已完成并确认，形成完整数据链")
    
    # 2. 忽略任务
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'PROB2-TEST',
        'interface_time': '2025.11.07'
    }]
    result = mark_ignored_batch(temp_db, False, task_keys, '测试用户', '延期处理', now)
    assert result['success_count'] == 1
    
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'PROB2-TEST')
    assert task['ignored'] == 1
    print("✓ 任务已忽略")
    
    # 3. 修改预期时间并重新导入
    updated_task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'PROB2-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.20',  # 时间变化：11.07 -> 11.20
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '测试人员',
            '_completed_col_value': '2025-11-08'  # 保持完成列有值，触发时间变化重置逻辑
        }
    }]
    
    batch_upsert_tasks(temp_db, False, updated_task_data, now)
    
    # 4. 验证结果
    # 4a. 新记录的ignored状态应该被取消
    task_after = find_task_by_business_id(temp_db, False, 1, '2016', 'PROB2-TEST')
    assert task_after['ignored'] == 0, "预期时间变化后，ignored状态应该被取消"
    print("✓ ignored状态已自动取消")
    
    # 4b. 新记录状态应该重置为待完成
    assert task_after['status'] == 'open', "预期时间变化后，状态应该重置"
    assert task_after['completed_at'] is None, "预期时间变化后，completed_at应该被清除"
    assert task_after['confirmed_at'] is None, "预期时间变化后，confirmed_at应该被清除"
    print("✓ 任务状态已重置")
    
    # 4c. 旧记录应该被归档
    from registry.service import query_task_history
    history = query_task_history(temp_db, False, '2016', 'PROB2-TEST', 1)
    
    archived_records = [h for h in history if h['status'] == 'archived']
    assert len(archived_records) >= 1, "应该有至少1条归档记录"
    print(f"✓ 旧记录已归档，共{len(archived_records)}条归档记录")


def test_problem3_time_format_normalization(temp_db):
    """
    问题3：时间格式差异不应触发重置
    
    验证：
    1. "2025.11.07" 和 "2025-11-07" 应该被视为相同时间
    2. 不应该触发"接口时间变化，重置状态"的输出
    """
    now = datetime.now()
    
    # 1. 创建任务（使用 "2025.11.07" 格式）
    task_data = [{
        'key': {
            'file_type': 2,
            'project_id': '2016',
            'interface_id': 'PROB3-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',  # 点号格式
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '测试人员',
            '_completed_col_value': ''
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_data, now)
    
    task = find_task_by_business_id(temp_db, False, 2, '2016', 'PROB3-TEST')
    assert task is not None
    print(f"✓ 任务已创建，interface_time={task['interface_time']}")
    
    # 2. 重新导入，使用不同格式但相同时间（"2025-11-07" 格式）
    reimport_task_data = [{
        'key': {
            'file_type': 2,
            'project_id': '2016',
            'interface_id': 'PROB3-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025-11-07',  # 横杠格式
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '测试人员',
            '_completed_col_value': ''
        }
    }]
    
    batch_upsert_tasks(temp_db, False, reimport_task_data, now)
    
    # 3. 验证状态未被重置
    task_after = find_task_by_business_id(temp_db, False, 2, '2016', 'PROB3-TEST')
    assert task_after['status'] == 'open'
    print("✓ 时间格式差异不会触发重置")
    
    # 4. 测试should_reset_task_status函数
    should_reset = should_reset_task_status('2025.11.07', '2025-11-07', '', '')
    assert should_reset == False, "相同时间但格式不同不应触发重置"
    print("✓ should_reset_task_status正确处理格式差异")
    
    # 5. 测试真正的时间变化
    should_reset_real = should_reset_task_status('2025.11.07', '2025.11.20', '', '')
    assert should_reset_real == True, "真正的时间变化应该触发重置"
    print("✓ 真正的时间变化会触发重置")


def test_integration_all_three_problems(temp_db):
    """
    综合测试：所有3个问题的综合场景
    
    场景：
    1. 创建任务A和B
    2. 忽略任务A
    3. 任务B的时间从"2025.11.07"变为"2025-11-07"（格式变化，不应重置）
    4. 验证：A不显示，B正常显示且未重置
    5. 任务A的时间从"2025.11.07"变为"2025.11.20"（真正的时间变化）
    6. 验证：A自动取消忽略并重新显示，状态重置
    """
    now = datetime.now()
    
    # 1. 创建任务A和B
    tasks_data = [
        {
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'TASK-A',
                'source_file': 'test.xlsx',
                'row_index': 10
            },
            'fields': {
                'department': '科室A',
                'interface_time': '2025.11.07',
                'display_status': '待完成',
                'status': 'open',
                '_completed_col_value': ''
            }
        },
        {
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'TASK-B',
                'source_file': 'test.xlsx',
                'row_index': 11
            },
            'fields': {
                'department': '科室B',
                'interface_time': '2025.11.07',
                'display_status': '待完成',
                'status': 'open',
                '_completed_col_value': ''
            }
        }
    ]
    
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    print("✓ 任务A和B已创建")
    
    # 2. 忽略任务A
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'TASK-A',
        'interface_time': '2025.11.07'
    }]
    mark_ignored_batch(temp_db, False, task_keys, '测试用户', '测试', now)
    print("✓ 任务A已忽略")
    
    # 3. 任务B的时间格式变化（不应重置）
    task_b_updated = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TASK-B',
            'source_file': 'test.xlsx',
            'row_index': 11
        },
        'fields': {
            'department': '科室B',
            'interface_time': '2025-11-07',  # 格式变化
            'display_status': '待完成',
            'status': 'open',
            '_completed_col_value': ''
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_b_updated, now)
    
    # 4. 验证：A不显示，B正常显示
    display_keys = [
        {'file_type': 1, 'project_id': '2016', 'interface_id': 'TASK-A', 'source_file': 'test.xlsx', 'row_index': 10},
        {'file_type': 1, 'project_id': '2016', 'interface_id': 'TASK-B', 'source_file': 'test.xlsx', 'row_index': 11}
    ]
    statuses = get_display_status(temp_db, False, display_keys, [])
    
    tid_a = make_task_id(1, '2016', 'TASK-A', 'test.xlsx', 10)
    tid_b = make_task_id(1, '2016', 'TASK-B', 'test.xlsx', 11)
    
    assert tid_a not in statuses, "任务A（已忽略）不应显示"
    assert tid_b in statuses, "任务B应该显示"
    print("✓ 任务A不显示，任务B正常显示")
    
    # 验证B未被重置
    task_b = find_task_by_business_id(temp_db, False, 1, '2016', 'TASK-B')
    assert task_b['status'] == 'open'
    print("✓ 任务B格式变化未触发重置")
    
    # 5. 任务A的时间真正变化（应取消忽略）
    task_a_time_changed = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TASK-A',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '科室A',
            'interface_time': '2025.11.20',  # 真正的时间变化
            'display_status': '待完成',
            'status': 'open',
            '_completed_col_value': ''
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_a_time_changed, now)
    
    # 6. 验证：A自动取消忽略并重新显示
    task_a_after = find_task_by_business_id(temp_db, False, 1, '2016', 'TASK-A')
    assert task_a_after['ignored'] == 0, "时间变化后应自动取消忽略"
    print("✓ 任务A的ignored状态已自动取消")
    
    # 再次获取显示状态
    statuses_after = get_display_status(temp_db, False, display_keys, [])
    assert tid_a in statuses_after, "任务A取消忽略后应该显示"
    print("✓ 任务A重新显示")
    
    print("\n✅ 综合测试通过：所有3个问题都已正确修复！")

