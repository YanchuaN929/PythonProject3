"""
测试 ignored 状态在数据重新导入后是否正确保留

问题场景：
1. 用户忽略一个任务（ignored = 1）
2. 点击"开始处理"，程序从 Excel 重新导入数据
3. 重新导入时，fields 中不包含 ignored 字段（默认为 None）
4. 预期：ignored 状态应该保留为 1
5. 实际（修复前）：ignored 被重置为 0（因为默认值是 0）

修复方案：
- 将 batch_upsert_tasks 中 fields.get('ignored', 0) 改为 fields.get('ignored', None)
- 确保 SQL UPDATE 使用 COALESCE 保留原值
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
    query_task_history,
    get_display_status,
    make_task_id
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


def test_ignored_status_preserved_after_reimport(temp_db):
    """
    测试：在重新导入数据后，ignored 状态应该被保留
    
    步骤：
    1. 创建并插入一个任务
    2. 忽略该任务（ignored = 1）
    3. 模拟重新导入（batch_upsert_tasks，不包含 ignored 字段）
    4. 验证 ignored 状态仍然为 1
    """
    now = datetime.now()
    
    # 1. 创建任务
    task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JZ-02-25C1-25C3',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',
            'role': '',
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '张三'
        }
    }]
    
    count = batch_upsert_tasks(temp_db, False, task_data, now)
    assert count == 1
    
    # 2. 忽略该任务
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'S-SA---1JZ-02-25C1-25C3',
        'interface_time': '2025.11.07'
    }]
    result = mark_ignored_batch(
        temp_db, False, task_keys, '测试用户', '测试原因', now
    )
    assert result['success_count'] == 1
    assert len(result['failed_tasks']) == 0
    
    # 3. 验证忽略成功
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-SA---1JZ-02-25C1-25C3')
    assert task is not None
    assert task['ignored'] == 1
    assert task['ignored_by'] == '测试用户'
    print(f"✓ 忽略前：ignored = {task['ignored']}")
    
    # 4. 模拟重新导入（不包含 ignored 字段）
    reimport_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JZ-02-25C1-25C3',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',  # 时间未变化
            'role': '',
            'display_status': '待完成',
            'status': 'open',
            'responsible_person': '张三'
            # 注意：这里没有 ignored 字段！
        }
    }]
    
    count = batch_upsert_tasks(temp_db, False, reimport_data, now)
    assert count == 1
    
    # 5. 验证 ignored 状态仍然为 1
    task_after = find_task_by_business_id(temp_db, False, 1, '2016', 'S-SA---1JZ-02-25C1-25C3')
    assert task_after is not None
    assert task_after['ignored'] == 1, f"❌ ignored 应该为 1，但实际为 {task_after['ignored']}"
    assert task_after['ignored_by'] == '测试用户'
    assert task_after['ignored_reason'] == '测试原因'
    print(f"✓ 重新导入后：ignored = {task_after['ignored']}")


def test_ignored_status_cleared_on_explicit_unignore(temp_db):
    """
    测试：明确取消忽略时，ignored 状态应该被清除
    
    步骤：
    1. 创建并忽略一个任务
    2. 明确设置 ignored = 0（例如自动取消忽略）
    3. 验证 ignored 状态被清除
    """
    now = datetime.now()
    
    # 1. 创建并忽略任务
    task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-001',
            'source_file': 'test.xlsx',
            'row_index': 20
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',
            'role': '',
            'display_status': '待完成',
            'status': 'open'
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_data, now)
    
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'TEST-001',
        'interface_time': '2025.11.07'
    }]
    mark_ignored_batch(temp_db, False, task_keys, '测试用户', '测试', now)
    
    # 验证已忽略
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'TEST-001')
    assert task['ignored'] == 1
    
    # 2. 明确取消忽略
    unignore_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-001',
            'source_file': 'test.xlsx',
            'row_index': 20
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.08',  # 时间变化触发自动取消忽略
            'role': '',
            'display_status': '待完成',
            'status': 'open',
            'ignored': 0,  # 明确设置为 0
            'ignored_at': None,
            'ignored_by': None,
            'interface_time_when_ignored': None,
            'ignored_reason': None
        }
    }]
    
    batch_upsert_tasks(temp_db, False, unignore_data, now)
    
    # 3. 验证 ignored 被清除
    task_after = find_task_by_business_id(temp_db, False, 1, '2016', 'TEST-001')
    assert task_after['ignored'] == 0
    # 注意：ignored_by 等历史信息可能会保留，这是合理的设计
    # 它们记录了"谁曾经忽略了这个任务"，即使现在已经取消忽略
    print(f"✓ ignored 已清除为 0，历史信息保留：ignored_by={task_after['ignored_by']}")


def test_ignored_task_filtered_from_display(temp_db):
    """
    测试：已忽略的任务应该被 get_display_status 过滤掉
    
    步骤：
    1. 创建两个任务
    2. 忽略其中一个
    3. 调用 get_display_status
    4. 验证只返回未忽略的任务
    """
    now = datetime.now()
    
    # 1. 创建两个任务
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
                'status': 'open'
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
                'status': 'open'
            }
        }
    ]
    
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 2. 忽略 TASK-A
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'TASK-A',
        'interface_time': '2025.11.07'
    }]
    mark_ignored_batch(temp_db, False, task_keys, '测试用户', '测试', now)
    
    # 3. 获取显示状态
    task_keys = [
        {'file_type': 1, 'project_id': '2016', 'interface_id': 'TASK-A', 'source_file': 'test.xlsx', 'row_index': 10},
        {'file_type': 1, 'project_id': '2016', 'interface_id': 'TASK-B', 'source_file': 'test.xlsx', 'row_index': 11}
    ]
    statuses = get_display_status(temp_db, False, task_keys, [])
    
    # 4. 验证 TASK-A 被过滤，TASK-B 显示
    # statuses 是一个字典 {task_id: status_text}
    # 已忽略的任务不会出现在结果中
    task_a_key = make_task_id(1, '2016', 'TASK-A', 'test.xlsx', 10)
    task_b_key = make_task_id(1, '2016', 'TASK-B', 'test.xlsx', 11)
    
    assert task_a_key not in statuses, "TASK-A should be filtered out"
    assert task_b_key in statuses, "TASK-B should be displayed"
    print(f"✓ 过滤成功：TASK-A被过滤，TASK-B显示")


def test_history_shows_ignored_status(temp_db):
    """
    测试：历史记录应该正确显示 ignored 状态
    
    步骤：
    1. 创建任务
    2. 忽略任务
    3. 查询历史记录
    4. 验证 ignored 字段正确
    """
    now = datetime.now()
    
    # 1. 创建任务
    task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'HISTORY-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',
            'display_status': '待完成',
            'status': 'open'
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_data, now)
    
    # 2. 忽略任务
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'HISTORY-TEST',
        'interface_time': '2025.11.07'
    }]
    mark_ignored_batch(temp_db, False, task_keys, '张三', '优先级低', now)
    
    # 3. 查询历史记录
    history = query_task_history(temp_db, False, '2016', 'HISTORY-TEST', 1)
    
    # 4. 验证历史记录
    assert len(history) > 0
    latest = history[0]
    assert latest['ignored'] == 1
    assert latest['ignored_by'] == '张三'
    assert latest['ignored_reason'] == '优先级低'
    print(f"✓ 历史记录显示：ignored={latest['ignored']}, ignored_by={latest['ignored_by']}")


def test_ignored_preserved_across_multiple_reimports(temp_db):
    """
    测试：多次重新导入后，ignored 状态仍然保留
    
    步骤：
    1. 创建并忽略任务
    2. 重新导入 3 次（模拟多次点击"开始处理"）
    3. 验证 ignored 状态始终为 1
    """
    now = datetime.now()
    
    # 1. 创建并忽略任务
    task_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'MULTI-TEST',
            'source_file': 'test.xlsx',
            'row_index': 10
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',
            'display_status': '待完成',
            'status': 'open'
        }
    }]
    
    batch_upsert_tasks(temp_db, False, task_data, now)
    task_keys = [{
        'file_type': '1',
        'project_id': '2016',
        'interface_id': 'MULTI-TEST',
        'interface_time': '2025.11.07'
    }]
    mark_ignored_batch(temp_db, False, task_keys, '李四', '测试', now)
    
    # 2. 多次重新导入
    for i in range(3):
        reimport_data = [{
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'MULTI-TEST',
                'source_file': 'test.xlsx',
                'row_index': 10
            },
            'fields': {
                'department': '测试科室',
                'interface_time': '2025.11.07',
                'display_status': '待完成',
                'status': 'open'
            }
        }]
        
        batch_upsert_tasks(temp_db, False, reimport_data, now)
        
        # 验证每次导入后 ignored 仍为 1
        task = find_task_by_business_id(temp_db, False, 1, '2016', 'MULTI-TEST')
        assert task['ignored'] == 1, f"第{i+1}次重新导入后，ignored 应该为 1"
        print(f"✓ 第{i+1}次重新导入后：ignored = {task['ignored']}")

