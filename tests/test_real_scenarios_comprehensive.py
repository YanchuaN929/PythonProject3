"""
真实场景综合测试
测试用户实际使用中遇到的复杂场景
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime
from pathlib import Path

# 导入Registry模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from registry import hooks as registry_hooks
from registry.service import (
    batch_upsert_tasks, get_display_status, mark_ignored_batch,
    find_task_by_business_id, query_task_history
)
from registry.db import init_db


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # 配置registry使用临时数据库
    def mock_cfg():
        return {'registry_db_path': path, 'wal': False}
    
    registry_hooks._cfg = mock_cfg
    
    # 初始化数据库
    conn = sqlite3.connect(path)
    init_db(conn)
    conn.close()
    
    yield path
    
    # 清理
    try:
        # 关闭全局连接
        from registry.db import _CONN
        if _CONN:
            _CONN.close()
            from registry import db as db_module
            db_module._CONN = None
        
        # 删除临时文件
        max_retries = 3
        for i in range(max_retries):
            try:
                os.unlink(path)
                break
            except PermissionError:
                if i < max_retries - 1:
                    import time
                    time.sleep(0.1)
                else:
                    print(f"Warning: Could not delete temp db {path}")
    except Exception as e:
        print(f"Cleanup error: {e}")


def test_scenario1_ignored_overdue_time_change(temp_db):
    """
    场景1：延期5个月且已忽略的接口，修改预期时间为11-30
    
    预期结果：
    1. 自动取消忽略状态
    2. 重新显示
    3. 状态为待完成
    """
    now = datetime(2025, 11, 12, 10, 0, 0)
    
    # 第一步：创建一个延期5个月的接口（预期时间是2025-06-01）
    tasks_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-TEST-001',
            'source_file': 'test.xlsx',
            'row_index': 10,
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.06.01',  # 延期5个月
            'role': '设计',
            'responsible_person': '张三',
            '_completed_col_value': '',  # 未完成
        }
    }]
    
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 验证任务创建成功
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-001')
    assert task is not None
    assert task['interface_time'] == '2025.06.01'
    assert task['status'] == 'open'
    assert (task.get('ignored') or 0) == 0  # ignored可能是None或0
    
    # 第二步：忽略这个接口
    task_keys = [{
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-TEST-001',
        'source_file': 'test.xlsx',
        'row_index': 10
    }]
    
    result = mark_ignored_batch(
        temp_db, False, task_keys, 
        ignored_by='所领导',
        ignored_reason='延期太久暂不处理',
        now=now
    )
    
    assert result['success_count'] == 1
    assert len(result['failed_tasks']) == 0
    
    # 验证忽略成功
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-001')
    assert task['ignored'] == 1
    assert task['ignored_by'] == '所领导'
    assert task['interface_time_when_ignored'] == '2025.06.01'
    
    # 验证不显示（被忽略）
    from registry.util import make_task_id
    tid = make_task_id(1, '2016', 'S-TEST-001', 'test.xlsx', 10)
    status_map = get_display_status(temp_db, False, [{
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-TEST-001',
        'source_file': 'test.xlsx',
        'row_index': 10,
        'interface_time': '2025.06.01'
    }], [])
    # 被忽略的任务不应该出现在status_map中
    assert tid not in status_map
    
    print("\n[测试场景1] 步骤1-2完成：任务已创建并忽略 ✓")
    
    # 第三步：修改预期时间为11-30，重新导入
    tasks_data[0]['fields']['interface_time'] = '2025.11.30'
    
    print("\n[测试场景1] 步骤3：修改预期时间并重新导入...")
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 验证：应该自动取消忽略
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-001')
    print(f"[测试场景1] 验证结果：")
    print(f"  ignored: {task.get('ignored', 0)}")
    print(f"  status: {task['status']}")
    print(f"  interface_time: {task['interface_time']}")
    
    assert (task.get('ignored') or 0) == 0, f"ignored应该为0，实际为{task.get('ignored')}"
    assert task['status'] == 'open', f"status应该为open，实际为{task['status']}"
    assert task['interface_time'] == '2025.11.30'
    
    # 验证：应该重新显示
    status_map = get_display_status(temp_db, False, [{
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-TEST-001',
        'source_file': 'test.xlsx',
        'row_index': 10,
        'interface_time': '2025.11.30'
    }], [])
    assert tid in status_map, "任务应该重新出现在显示列表中"
    
    # 验证：显示状态应该包含"待完成"（可能有emoji前缀）
    assert '待完成' in status_map[tid]
    
    print("[测试场景1] 通过 ✓")


def test_scenario2_confirmed_cleared_and_time_change(temp_db):
    """
    场景2：已审查状态的11-01接口，所有信息被清零，预期时间变成11-30
    
    预期结果：
    1. 归档旧记录（因为有完整数据链）
    2. 创建新记录，状态为待完成
    3. 重新显示
    """
    now = datetime(2025, 11, 12, 10, 0, 0)
    
    # 第一步：创建一个接口并完成+确认（形成完整数据链）
    tasks_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-TEST-002',
            'source_file': 'test.xlsx',
            'row_index': 20,
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.01',
            'role': '设计',
            'responsible_person': '李四',
            '_completed_col_value': '2025-11-05',  # 已完成
        }
    }]
    
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 手动设置为已确认状态（模拟上级确认）
    conn = sqlite3.connect(temp_db)
    from registry.util import make_task_id
    tid = make_task_id(1, '2016', 'S-TEST-002', 'test.xlsx', 20)
    conn.execute("""
        UPDATE tasks
        SET status = 'confirmed',
            display_status = '已审查',
            completed_at = ?,
            completed_by = '李四',
            confirmed_at = ?,
            confirmed_by = '室主任'
        WHERE id = ?
    """, (now.isoformat(), now.isoformat(), tid))
    conn.commit()
    conn.close()
    
    # 验证任务状态
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-002')
    assert task['status'] == 'confirmed'
    assert task['completed_at'] is not None
    assert task['confirmed_at'] is not None
    assert task['confirmed_by'] == '室主任'
    
    print("\n[测试场景2] 步骤1完成：任务已创建并确认 ✓")
    
    # 第二步：清空完成信息并修改预期时间
    tasks_data[0]['fields']['_completed_col_value'] = ''  # 清空完成列
    tasks_data[0]['fields']['interface_time'] = '2025.11.30'  # 修改预期时间
    
    print("\n[测试场景2] 步骤2：清空完成信息并修改预期时间...")
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 验证：旧记录应该被归档
    history = query_task_history(temp_db, False, '2016', 'S-TEST-002', 1)
    print(f"[测试场景2] 历史记录数量: {len(history)}")
    
    archived_records = [h for h in history if h.get('status') == 'archived']
    active_records = [h for h in history if h.get('status') != 'archived']
    
    print(f"  归档记录: {len(archived_records)}")
    print(f"  活动记录: {len(active_records)}")
    
    assert len(archived_records) == 1, f"应该有1条归档记录，实际有{len(archived_records)}条"
    assert len(active_records) == 1, f"应该有1条活动记录，实际有{len(active_records)}条"
    
    # 验证：归档记录保留了完整数据链
    archived = archived_records[0]
    assert archived['completed_at'] is not None
    assert archived['confirmed_at'] is not None
    assert archived['interface_time'] == '2025.11.01'  # 保留旧的预期时间
    assert archived['archive_reason'] == 'task_reset_completed_cleared'
    
    # 验证：新记录状态为待完成
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-002')
    print(f"[测试场景2] 新记录验证：")
    print(f"  status: {task['status']}")
    print(f"  completed_at: {task.get('completed_at')}")
    print(f"  confirmed_at: {task.get('confirmed_at')}")
    print(f"  interface_time: {task['interface_time']}")
    
    assert task['status'] == 'open', f"status应该为open，实际为{task['status']}"
    assert task['completed_at'] is None, "completed_at应该为空"
    assert task['confirmed_at'] is None, "confirmed_at应该为空"
    assert task['interface_time'] == '2025.11.30'
    
    # 验证：应该重新显示
    from registry.util import make_task_id
    tid = make_task_id(1, '2016', 'S-TEST-002', 'test.xlsx', 20)
    status_map = get_display_status(temp_db, False, [{
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-TEST-002',
        'source_file': 'test.xlsx',
        'row_index': 20,
        'interface_time': '2025.11.30'
    }], [])
    assert tid in status_map
    assert '待完成' in status_map[tid]  # 可能包含emoji
    
    print("[测试场景2] 通过 ✓")


def test_scenario3_time_format_variation_no_reset(temp_db):
    """
    场景3：预期时间仅格式变化（2025.11.07 vs 2025-11-07），不应触发重置
    
    预期结果：
    1. 不触发重置
    2. 保持原有状态
    3. 不输出"接口时间变化，重置状态"
    """
    now = datetime(2025, 11, 12, 10, 0, 0)
    
    # 第一步：创建并完成一个接口
    tasks_data = [{
        'key': {
            'file_type': 2,
            'project_id': '2016',
            'interface_id': 'S-TEST-003',
            'source_file': 'test.xlsx',
            'row_index': 30,
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.11.07',  # 点分隔格式
            'role': '设计',
            'responsible_person': '王五',
            '_completed_col_value': '2025-11-08',
        }
    }]
    
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 手动设置为已完成状态
    conn = sqlite3.connect(temp_db)
    from registry.util import make_task_id
    tid = make_task_id(2, '2016', 'S-TEST-003', 'test.xlsx', 30)
    conn.execute("""
        UPDATE tasks
        SET status = 'completed',
            display_status = '待审查',
            completed_at = ?,
            completed_by = '王五'
        WHERE id = ?
    """, (now.isoformat(), tid))
    conn.commit()
    conn.close()
    
    task = find_task_by_business_id(temp_db, False, 2, '2016', 'S-TEST-003')
    assert task['status'] == 'completed'
    assert task['completed_at'] is not None
    
    print("\n[测试场景3] 步骤1完成：任务已创建并完成 ✓")
    
    # 第二步：修改时间格式为横杠分隔，重新导入
    tasks_data[0]['fields']['interface_time'] = '2025-11-07'  # 横杠分隔格式
    
    print("\n[测试场景3] 步骤2：仅改变时间格式并重新导入...")
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 验证：状态不应该被重置
    task = find_task_by_business_id(temp_db, False, 2, '2016', 'S-TEST-003')
    print(f"[测试场景3] 验证结果：")
    print(f"  status: {task['status']}")
    print(f"  completed_at: {task.get('completed_at')}")
    print(f"  interface_time: {task['interface_time']}")
    
    assert task['status'] == 'completed', f"status应该保持completed，实际为{task['status']}"
    assert task['completed_at'] is not None, "completed_at不应该被清空"
    assert task['completed_by'] == '王五'
    
    # 验证：不应该有归档记录
    history = query_task_history(temp_db, False, '2016', 'S-TEST-003', 2)
    archived_records = [h for h in history if h.get('status') == 'archived']
    assert len(archived_records) == 0, "不应该有归档记录"
    
    print("[测试场景3] 通过 ✓")


def test_scenario4_combined_ignore_and_time_change(temp_db):
    """
    场景4：已忽略且已审查的接口，预期时间变化
    
    预期结果：
    1. 取消忽略
    2. 归档旧记录（因为有完整数据链）
    3. 重置为待完成状态
    """
    now = datetime(2025, 11, 12, 10, 0, 0)
    
    # 第一步：创建、完成并确认一个接口
    tasks_data = [{
        'key': {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-TEST-004',
            'source_file': 'test.xlsx',
            'row_index': 40,
        },
        'fields': {
            'department': '测试科室',
            'interface_time': '2025.10.01',
            'role': '设计',
            'responsible_person': '赵六',
            '_completed_col_value': '2025-10-05',
        }
    }]
    
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 设置为已确认
    conn = sqlite3.connect(temp_db)
    from registry.util import make_task_id
    tid = make_task_id(1, '2016', 'S-TEST-004', 'test.xlsx', 40)
    conn.execute("""
        UPDATE tasks
        SET status = 'confirmed',
            display_status = '已审查',
            completed_at = ?,
            completed_by = '赵六',
            confirmed_at = ?,
            confirmed_by = '所领导'
        WHERE id = ?
    """, (now.isoformat(), now.isoformat(), tid))
    conn.commit()
    conn.close()
    
    # 忽略这个接口
    task_keys = [{
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-TEST-004',
        'source_file': 'test.xlsx',
        'row_index': 40
    }]
    
    result = mark_ignored_batch(
        temp_db, False, task_keys,
        ignored_by='所领导',
        ignored_reason='测试忽略',
        now=now
    )
    
    assert result['success_count'] == 1
    
    # 验证忽略成功
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-004')
    assert task['ignored'] == 1
    assert task['status'] == 'confirmed'
    assert task['interface_time_when_ignored'] == '2025.10.01'
    
    print("\n[测试场景4] 步骤1完成：任务已创建、确认并忽略 ✓")
    
    # 第二步：修改预期时间
    tasks_data[0]['fields']['interface_time'] = '2025.12.01'
    
    print("\n[测试场景4] 步骤2：修改预期时间并重新导入...")
    batch_upsert_tasks(temp_db, False, tasks_data, now)
    
    # 验证：应该取消忽略
    task = find_task_by_business_id(temp_db, False, 1, '2016', 'S-TEST-004')
    print(f"[测试场景4] 验证结果：")
    print(f"  ignored: {task.get('ignored', 0)}")
    print(f"  status: {task['status']}")
    print(f"  interface_time: {task['interface_time']}")
    
    assert (task.get('ignored') or 0) == 0, f"ignored应该为0，实际为{task.get('ignored')}"
    assert task['status'] == 'open', "status应该重置为open"
    assert task['interface_time'] == '2025.12.01'
    
    # 验证：应该有归档记录
    history = query_task_history(temp_db, False, '2016', 'S-TEST-004', 1)
    archived_records = [h for h in history if h.get('status') == 'archived']
    assert len(archived_records) == 1, "应该有1条归档记录"
    
    # 验证：归档记录保留了完整数据链
    archived = archived_records[0]
    assert archived['completed_at'] is not None
    assert archived['confirmed_at'] is not None
    assert archived['ignored'] == 1  # 归档记录保留了忽略状态
    
    print("[测试场景4] 通过 ✓")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

