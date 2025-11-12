"""
测试Registry的上级确认功能
"""
import os
import tempfile
import pytest
from datetime import datetime, timedelta
from registry.service import (
    upsert_task, mark_completed, mark_confirmed, mark_unconfirmed,
    query_task_history, get_display_status
)
from registry.db import init_db
from registry.util import make_task_id, make_business_id


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # 初始化数据库
    from registry.db import get_connection
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


def test_superior_confirm_after_designer_completes(temp_db):
    """
    测试场景：设计人员完成任务后，上级点击勾选框确认
    """
    now = datetime.now()
    
    # 1. 设计人员填写回文单号（模拟on_response_written）
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-SA---1JJ-01-25C1-25C3',  # 不含角色后缀
        'source_file': 'test.xlsx',
        'row_index': 89
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
    
    # 创建任务
    upsert_task(temp_db, False, key, fields, now)
    
    # 标记为已完成
    mark_completed(temp_db, False, key, now)
    
    # 验证任务状态
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    assert len(history) == 1
    task = history[0]
    assert task['status'] == 'completed'
    assert task['completed_by'] == '张三'
    assert task['confirmed_at'] is None
    
    # 2. 上级点击勾选框确认（模拟on_confirmed_by_superior）
    mark_confirmed(temp_db, False, key, now + timedelta(seconds=10), confirmed_by='李主任')
    
    # 3. 验证确认后的状态
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    assert len(history) == 1
    task = history[0]
    assert task['status'] == 'confirmed'
    assert task['confirmed_by'] == '李主任'
    assert task['confirmed_at'] is not None
    assert task['completed_by'] == '张三'  # 完成人不变
    
    # 4. 验证display_status
    task_key_for_status = {
        'file_type': key['file_type'],
        'project_id': key['project_id'],
        'interface_id': key['interface_id'],
        'source_file': key['source_file'],
        'row_index': key['row_index'],
        'interface_time': fields['interface_time']
    }
    display_status = get_display_status(temp_db, False, [task_key_for_status], [])
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    assert tid in display_status
    assert '已审查' in display_status[tid]
    
    print("测试通过: 设计人员完成后上级确认")


def test_superior_unconfirm(temp_db):
    """
    测试场景：上级取消确认
    """
    now = datetime.now()
    
    # 1. 创建已确认的任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-SA---1JJ-01-25C1-25C3',
        'source_file': 'test.xlsx',
        'row_index': 89
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员(一室主任)',
        'status': 'completed',
        'display_status': '已审查',
        'responsible_person': '张三',
        'response_number': 'HW-2025-001',
        'completed_by': '张三',
        'confirmed_by': '李主任',
        'confirmed_at': now.isoformat()
    }
    
    upsert_task(temp_db, False, key, fields, now)
    mark_confirmed(temp_db, False, key, now, confirmed_by='李主任')
    
    # 验证已确认
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    assert len(history) == 1
    task = history[0]
    assert task['status'] == 'confirmed'
    assert task['confirmed_by'] == '李主任'
    
    # 2. 上级取消确认
    mark_unconfirmed(temp_db, False, key, now + timedelta(seconds=10))
    
    # 3. 验证取消确认后的状态
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    assert len(history) == 1
    task = history[0]
    assert task['status'] == 'completed'
    assert task['confirmed_by'] is None
    assert task['confirmed_at'] is None
    assert task['completed_by'] == '张三'  # 完成人不变
    
    # 4. 验证display_status变为"待审查"
    task_key_for_status = {
        'file_type': key['file_type'],
        'project_id': key['project_id'],
        'interface_id': key['interface_id'],
        'source_file': key['source_file'],
        'row_index': key['row_index'],
        'interface_time': fields['interface_time']
    }
    display_status = get_display_status(temp_db, False, [task_key_for_status], [])
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    assert tid in display_status
    assert '待审查' in display_status[tid]
    
    print("测试通过: 上级取消确认")


def test_interface_id_with_role_suffix_removed(temp_db):
    """
    测试场景：接口号包含角色后缀时，能正确去除后缀并找到任务
    
    这是修复的关键场景：
    - 显示的接口号：S-SA---1JJ-01-25C1-25C3(一室主任)
    - Registry存储的接口号：S-SA---1JJ-01-25C1-25C3
    """
    now = datetime.now()
    
    # 1. 创建任务（不含角色后缀）
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-SA---1JJ-01-25C1-25C3',  # 不含角色后缀
        'source_file': 'test.xlsx',
        'row_index': 89
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员(一室主任)',
        'status': 'completed',
        'display_status': '待审查',
        'responsible_person': '张三',
        'response_number': 'HW-2025-001',
        'completed_by': '张三'
    }
    
    upsert_task(temp_db, False, key, fields, now)
    mark_completed(temp_db, False, key, now)
    
    # 2. 模拟window.py从metadata获取到带角色后缀的接口号
    # 在window.py中会去除后缀：
    # interface_id = 'S-SA---1JJ-01-25C1-25C3(一室主任)'
    # interface_id_clean = re.sub(r'\([^)]*\)$', '', interface_id).strip()
    # -> 'S-SA---1JJ-01-25C1-25C3'
    
    import re
    interface_id_with_suffix = 'S-SA---1JJ-01-25C1-25C3(一室主任)'
    interface_id_clean = re.sub(r'\([^)]*\)$', '', interface_id_with_suffix).strip()
    
    # 3. 使用清理后的接口号确认
    key_clean = key.copy()
    key_clean['interface_id'] = interface_id_clean
    
    mark_confirmed(temp_db, False, key_clean, now + timedelta(seconds=10), confirmed_by='李主任')
    
    # 4. 验证能正确找到并更新任务
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    assert len(history) == 1
    task = history[0]
    assert task['status'] == 'confirmed'
    assert task['confirmed_by'] == '李主任'
    assert task['confirmed_at'] is not None
    
    print("测试通过: 接口号含角色后缀时能正确去除并找到任务")


def test_superior_self_complete_and_auto_confirm(temp_db):
    """
    测试场景：上级自己填写回文单号，自动确认
    """
    now = datetime.now()
    
    # 1. 上级填写回文单号（模拟on_response_written，is_superior=True）
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-SA---1JJ-01-25C1-25C3',
        'source_file': 'test.xlsx',
        'row_index': 89
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '一室主任',
        'status': 'open',
        'display_status': '已审查',  # 上级自己填写，直接设为已审查
        'responsible_person': '李主任',
        'response_number': 'HW-2025-002',
        'completed_by': '李主任',
        'confirmed_by': '李主任',
        'confirmed_at': now.isoformat()
    }
    
    # 创建任务
    upsert_task(temp_db, False, key, fields, now)
    
    # 标记为已完成
    mark_completed(temp_db, False, key, now)
    
    # 自动确认
    mark_confirmed(temp_db, False, key, now, confirmed_by='李主任')
    
    # 2. 验证状态
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    assert len(history) == 1
    task = history[0]
    assert task['status'] == 'confirmed'
    assert task['completed_by'] == '李主任'
    assert task['confirmed_by'] == '李主任'
    assert task['confirmed_at'] is not None
    
    # 3. 验证display_status
    task_key_for_status = {
        'file_type': key['file_type'],
        'project_id': key['project_id'],
        'interface_id': key['interface_id'],
        'source_file': key['source_file'],
        'row_index': key['row_index'],
        'interface_time': fields['interface_time']
    }
    display_status = get_display_status(temp_db, False, [task_key_for_status], [])
    tid = make_task_id(
        key['file_type'],
        key['project_id'],
        key['interface_id'],
        key['source_file'],
        key['row_index']
    )
    assert tid in display_status
    assert '已审查' in display_status[tid]
    
    print("测试通过: 上级自己填写回文单号自动确认")


def test_confirm_after_versioning(temp_db):
    """
    测试场景：历史记录版本化后，确认功能仍然能找到最新的任务
    """
    now = datetime.now()
    
    # 1. 创建第一轮任务并完成确认
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'S-SA---1JJ-01-25C1-25C3',
        'source_file': 'test.xlsx',
        'row_index': 89
    }
    
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员(一室主任)',
        'status': 'completed',
        'display_status': '已审查',
        'responsible_person': '张三',
        'response_number': 'HW-2025-001',
        'completed_by': '张三',
        'confirmed_by': '李主任',
        'confirmed_at': now.isoformat()
    }
    
    upsert_task(temp_db, False, key, fields, now)
    mark_completed(temp_db, False, key, now)
    mark_confirmed(temp_db, False, key, now, confirmed_by='李主任')
    
    # 2. 模拟接口更新（interface_time变化，completed_at清空）
    # 这会触发历史记录版本化，旧记录被归档，创建新记录
    fields_new = {
        'department': '一室',
        'interface_time': '2025-02-01',  # 时间变化
        'role': '设计人员(一室主任)',
        'status': 'open',
        'display_status': '待完成',
        'responsible_person': '张三',
        '_completed_col_value': ''  # 完成列清空
    }
    
    upsert_task(temp_db, False, key, fields_new, now + timedelta(days=1))
    
    # 3. 新一轮：设计人员完成
    fields_complete = {
        'response_number': 'HW-2025-003',
        'completed_by': '张三',
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, False, key, fields_complete, now + timedelta(days=2))
    mark_completed(temp_db, False, key, now + timedelta(days=2))
    
    # 4. 上级确认新一轮任务
    mark_confirmed(temp_db, False, key, now + timedelta(days=3), confirmed_by='王所长')
    
    # 5. 验证历史记录
    history = query_task_history(temp_db, False, key['project_id'], key['interface_id'], key['file_type'])
    # 应该有2条记录：1条归档的旧记录，1条当前的新记录
    assert len(history) >= 2
    
    # 找到非归档记录
    active_tasks = [t for t in history if t['status'] != 'archived']
    assert len(active_tasks) == 1
    
    active_task = active_tasks[0]
    assert active_task['status'] == 'confirmed'
    assert active_task['confirmed_by'] == '王所长'
    assert active_task['response_number'] == 'HW-2025-003'
    
    # 找到归档记录
    archived_tasks = [t for t in history if t['status'] == 'archived']
    assert len(archived_tasks) >= 1
    
    archived_task = archived_tasks[0]
    assert archived_task['confirmed_by'] == '李主任'
    assert archived_task['response_number'] == 'HW-2025-001'
    
    print("测试通过: 版本化后确认功能正常")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
