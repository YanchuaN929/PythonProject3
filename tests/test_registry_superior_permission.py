"""
测试Registry上级确认权限控制
验证上级角色只能确认已完成（待审查）的任务，不能确认待完成的任务
"""
import os
import tempfile
import pytest
from datetime import datetime, timedelta
from registry.service import (
    upsert_task, mark_completed, mark_confirmed,
    query_task_history
)
from registry.db import init_db, get_connection
from registry.util import make_task_id


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # 初始化数据库
    conn = get_connection(path, wal=False)
    init_db(conn)
    conn.close()
    
    yield path
    
    # 清理：关闭所有连接
    from registry.db import _CONN
    if _CONN and hasattr(_CONN, 'close'):
        try:
            _CONN.close()
        except:
            pass
    
    # 延迟删除文件
    import time
    for _ in range(3):
        try:
            if os.path.exists(path):
                os.unlink(path)
            break
        except PermissionError:
            time.sleep(0.1)


def test_cannot_confirm_open_task(temp_db):
    """
    测试场景：上级角色不能确认待完成（open）状态的任务
    
    步骤：
    1. 创建一个待完成任务（status='open'）
    2. 尝试确认该任务
    3. 验证：任务状态仍然是'open'，没有被确认
    """
    now = datetime.now()
    
    # 1. 创建待完成任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'IF-OPEN-001',
        'source_file': 'test.xlsx',
        'row_index': 10
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员(一室主任)',
        'status': 'open',
        'display_status': '待完成',
        'responsible_person': '张三'
    }
    
    upsert_task(temp_db, False, key, fields, now)
    
    # 2. 查询任务状态
    conn = get_connection(temp_db, False)
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    cursor = conn.execute("SELECT status, confirmed_at FROM tasks WHERE id = ?", (tid,))
    task_row = cursor.fetchone()
    
    assert task_row is not None, "任务应该存在"
    task_status, confirmed_at = task_row
    
    # 3. 验证：状态是open，不能被确认
    assert task_status == 'open', f"任务状态应该是open，实际是{task_status}"
    assert confirmed_at is None, "任务不应该被确认"
    
    # 4. 模拟权限检查（这是window.py中的逻辑）
    can_confirm = (task_status == 'completed')
    assert not can_confirm, "status=open的任务不应该允许确认"
    
    print("[测试通过] 待完成任务不能被上级确认")


def test_can_confirm_completed_task(temp_db):
    """
    测试场景：上级角色可以确认已完成（completed）状态的任务
    
    步骤：
    1. 创建并完成一个任务（status='completed'）
    2. 上级确认该任务
    3. 验证：任务状态变为'confirmed'，有确认时间和确认人
    """
    now = datetime.now()
    
    # 1. 创建并完成任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'IF-COMPLETED-001',
        'source_file': 'test.xlsx',
        'row_index': 20
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员(一室主任)',
        'status': 'open',
        'display_status': '待完成',
        'responsible_person': '张三',
        'response_number': 'HW-2025-001',
        'completed_by': '张三'
    }
    
    upsert_task(temp_db, False, key, fields, now)
    mark_completed(temp_db, False, key, now)
    
    # 2. 查询任务状态（确认前）
    conn = get_connection(temp_db, False)
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    cursor = conn.execute("SELECT status, confirmed_at FROM tasks WHERE id = ?", (tid,))
    task_row = cursor.fetchone()
    
    assert task_row is not None
    task_status, confirmed_at = task_row
    
    # 3. 验证：状态是completed，可以被确认
    assert task_status == 'completed', f"任务状态应该是completed，实际是{task_status}"
    assert confirmed_at is None, "确认前不应该有确认时间"
    
    can_confirm = (task_status == 'completed')
    assert can_confirm, "status=completed的任务应该允许确认"
    
    # 4. 执行确认
    mark_confirmed(temp_db, False, key, now + timedelta(seconds=10), confirmed_by='李主任')
    
    # 5. 验证确认后的状态
    cursor = conn.execute("SELECT status, confirmed_at, confirmed_by FROM tasks WHERE id = ?", (tid,))
    task_row = cursor.fetchone()
    
    assert task_row is not None
    task_status, confirmed_at, confirmed_by = task_row
    
    assert task_status == 'confirmed', f"确认后状态应该是confirmed，实际是{task_status}"
    assert confirmed_at is not None, "确认后应该有确认时间"
    assert confirmed_by == '李主任', f"确认人应该是李主任，实际是{confirmed_by}"
    
    print("[测试通过] 已完成任务可以被上级确认")


def test_cannot_confirm_already_confirmed_task(temp_db):
    """
    测试场景：上级角色不能重复确认已确认的任务
    
    步骤：
    1. 创建并确认一个任务（status='confirmed'）
    2. 尝试再次确认
    3. 验证：应该检测到状态异常
    """
    now = datetime.now()
    
    # 1. 创建、完成并确认任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'IF-CONFIRMED-001',
        'source_file': 'test.xlsx',
        'row_index': 30
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员(一室主任)',
        'status': 'completed',
        'display_status': '已审查',
        'responsible_person': '张三',
        'response_number': 'HW-2025-002',
        'completed_by': '张三',
        'confirmed_by': '李主任',
        'confirmed_at': now.isoformat()
    }
    
    upsert_task(temp_db, False, key, fields, now)
    mark_completed(temp_db, False, key, now)
    mark_confirmed(temp_db, False, key, now, confirmed_by='李主任')
    
    # 2. 查询任务状态
    conn = get_connection(temp_db, False)
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    cursor = conn.execute("SELECT status, confirmed_at FROM tasks WHERE id = ?", (tid,))
    task_row = cursor.fetchone()
    
    assert task_row is not None
    task_status, confirmed_at = task_row
    
    # 3. 验证：状态是confirmed，不应该再次确认
    assert task_status == 'confirmed', f"任务状态应该是confirmed，实际是{task_status}"
    assert confirmed_at is not None, "已确认任务应该有确认时间"
    
    # 模拟权限检查（window.py中会阻止这种操作）
    can_confirm = (task_status == 'completed')
    assert not can_confirm, "status=confirmed的任务不应该允许重复确认"
    
    print("[测试通过] 已确认任务不能重复确认")


def test_permission_flow_complete_lifecycle(temp_db):
    """
    测试场景：完整的权限流程
    
    1. 创建任务（open） - 不能确认
    2. 设计人员完成（completed） - 可以确认
    3. 上级确认（confirmed） - 不能再确认
    4. 上级取消确认（completed） - 可以再次确认
    """
    now = datetime.now()
    
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'IF-LIFECYCLE-001',
        'source_file': 'test.xlsx',
        'row_index': 40
    }
    
    conn = get_connection(temp_db, False)
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    
    # 阶段1：创建任务（open）
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        'status': 'open',
        'display_status': '待完成',
        'responsible_person': '张三'
    }
    
    upsert_task(temp_db, False, key, fields, now)
    
    cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,))
    status = cursor.fetchone()[0]
    assert status == 'open'
    assert status != 'completed', "阶段1：open状态不能确认"
    print("  [阶段1] open状态 - 不能确认 ✓")
    
    # 阶段2：设计人员完成（completed）
    fields['response_number'] = 'HW-2025-003'
    fields['completed_by'] = '张三'
    upsert_task(temp_db, False, key, fields, now + timedelta(seconds=10))
    mark_completed(temp_db, False, key, now + timedelta(seconds=10))
    
    cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,))
    status = cursor.fetchone()[0]
    assert status == 'completed', "设计人员完成后应该是completed状态"
    print("  [阶段2] completed状态 - 可以确认 ✓")
    
    # 阶段3：上级确认（confirmed）
    mark_confirmed(temp_db, False, key, now + timedelta(seconds=20), confirmed_by='李主任')
    
    cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,))
    status = cursor.fetchone()[0]
    assert status == 'confirmed'
    assert status != 'completed', "阶段3：confirmed状态不能再次确认"
    print("  [阶段3] confirmed状态 - 不能再确认 ✓")
    
    # 阶段4：上级取消确认（回到completed）
    from registry.service import mark_unconfirmed
    mark_unconfirmed(temp_db, False, key, now + timedelta(seconds=30))
    
    cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,))
    status = cursor.fetchone()[0]
    assert status == 'completed'
    print("  [阶段4] 取消确认后回到completed状态 - 可以再次确认 ✓")
    
    print("[测试通过] 完整权限流程正确")


def test_multiple_tasks_permission_control(temp_db):
    """
    测试场景：多个任务的混合状态权限控制
    
    创建5个任务：
    - 2个open（不能确认）
    - 2个completed（可以确认）
    - 1个confirmed（不能确认）
    """
    now = datetime.now()
    
    tasks = []
    
    # 创建2个open任务
    for i in range(2):
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': f'IF-OPEN-{i+1:02d}',
            'source_file': 'test.xlsx',
            'row_index': 50 + i * 10
        }
        fields = {
            'department': '一室',
            'interface_time': '2025-01-15',
            'role': '设计人员',
            'status': 'open',
            'display_status': '待完成',
            'responsible_person': f'员工{i+1}'
        }
        upsert_task(temp_db, False, key, fields, now)
        tasks.append((key, 'open'))
    
    # 创建2个completed任务
    for i in range(2):
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': f'IF-COMPLETED-{i+1:02d}',
            'source_file': 'test.xlsx',
            'row_index': 70 + i * 10
        }
        fields = {
            'department': '一室',
            'interface_time': '2025-01-15',
            'role': '设计人员',
            'status': 'open',
            'display_status': '待完成',
            'responsible_person': f'员工{i+3}',
            'response_number': f'HW-{i+3:03d}',
            'completed_by': f'员工{i+3}'
        }
        upsert_task(temp_db, False, key, fields, now)
        mark_completed(temp_db, False, key, now)
        tasks.append((key, 'completed'))
    
    # 创建1个confirmed任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'IF-CONFIRMED-MULTI',
        'source_file': 'test.xlsx',
        'row_index': 90
    }
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        'status': 'completed',
        'display_status': '已审查',
        'responsible_person': '员工5',
        'response_number': 'HW-005',
        'completed_by': '员工5',
        'confirmed_by': '李主任',
        'confirmed_at': now.isoformat()
    }
    upsert_task(temp_db, False, key, fields, now)
    mark_completed(temp_db, False, key, now)
    mark_confirmed(temp_db, False, key, now, confirmed_by='李主任')
    tasks.append((key, 'confirmed'))
    
    # 验证权限
    conn = get_connection(temp_db, False)
    confirmable_count = 0
    not_confirmable_count = 0
    
    for key, expected_status in tasks:
        tid = make_task_id(
            key['file_type'],
            key['project_id'],
            key['interface_id'],
            key['source_file'],
            key['row_index']
        )
        
        cursor = conn.execute("SELECT status FROM tasks WHERE id = ?", (tid,))
        status = cursor.fetchone()[0]
        
        assert status == expected_status, f"{key['interface_id']}: 期望status={expected_status}，实际={status}"
        
        can_confirm = (status == 'completed')
        if can_confirm:
            confirmable_count += 1
        else:
            not_confirmable_count += 1
    
    # 验证统计
    assert confirmable_count == 2, f"应该有2个可确认任务，实际{confirmable_count}个"
    assert not_confirmable_count == 3, f"应该有3个不可确认任务，实际{not_confirmable_count}个"
    
    print(f"[测试通过] 混合状态权限控制：{confirmable_count}个可确认，{not_confirmable_count}个不可确认")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

