#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Registry历史记录版本化功能

测试场景：
1. 检测更新/重置并创建新轮次记录
2. 归档旧记录并设置archived_at
3. 新记录first_seen_at标注为(更新日期)格式
4. 历史查询显示所有轮次记录（包括已归档）
5. 确认后7天自动归档
"""
import sys
import os
import tempfile
import pytest
from datetime import datetime, timedelta

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry.service import upsert_task, query_task_history, finalize_scan
from registry.db import get_connection
from registry.models import Status


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except:
        pass


def test_versioning_on_update_with_complete_data_chain(temp_db):
    """
    测试场景1：检测更新/重置并创建新轮次记录
    
    步骤：
    1. 创建初始任务
    2. 填写completed_at（模拟设计人员填写回文单号）
    3. 填写confirmed_at（模拟上级确认）
    4. 修改interface_time，清空completed_at（模拟更新/重置）
    5. 验证：旧记录被归档，新记录被创建
    """
    print("\n[测试] 场景1：完整数据链下的版本化更新")
    
    now = datetime.now()
    
    # 步骤1：创建初始任务
    key1 = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'TEST-VERSION-001',
        'source_file': 'test.xlsx',
        'row_index': 100
    }
    fields1 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        '_completed_col_value': ''  # 初始为空
    }
    upsert_task(temp_db, True, key1, fields1, now)
    print("[OK] 步骤1: 创建初始任务")
    
    # 步骤2：填写completed_at（模拟设计人员填写回文单号）
    fields2 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        'completed_at': now.isoformat(),
        'completed_by': '设计人员张三',
        'response_number': 'HW-2025-001',
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, True, key1, fields2, now)
    print("[OK] 步骤2: 填写completed_at")
    
    # 步骤3：填写confirmed_at（模拟上级确认）
    fields3 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        'completed_at': now.isoformat(),
        'completed_by': '设计人员张三',
        'confirmed_at': now.isoformat(),
        'confirmed_by': '室主任李四',
        'response_number': 'HW-2025-001',
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, True, key1, fields3, now)
    print("[OK] 步骤3: 上级确认")
    
    # 验证：此时应该只有一条记录
    history1 = query_task_history(temp_db, True, '2016', 'TEST-VERSION-001', 1)
    assert len(history1) == 1, f"确认后应该只有1条记录，实际{len(history1)}条"
    assert history1[0]['status'] == Status.OPEN or history1[0]['confirmed_at'] is not None
    print(f"[OK] 验证: 确认后有1条记录，状态={history1[0].get('status')}")
    
    # 步骤4：修改interface_time，清空completed_at（模拟更新/重置）
    future_time = now + timedelta(days=1)
    fields4 = {
        'department': '一室',
        'interface_time': '2025-02-20',  # 时间变化
        'role': '设计人员',
        '_completed_col_value': ''  # 完成列变空
    }
    upsert_task(temp_db, True, key1, fields4, future_time)
    print("[OK] 步骤4: 更新interface_time并清空completed_at")
    
    # 步骤5：验证版本化结果
    history2 = query_task_history(temp_db, True, '2016', 'TEST-VERSION-001', 1)
    print(f"[OK] 更新后历史记录数: {len(history2)}")
    
    assert len(history2) == 2, f"更新后应该有2条记录（1条归档+1条新建），实际{len(history2)}条"
    
    # 验证归档记录
    archived_record = None
    new_record = None
    for record in history2:
        if record.get('status') == 'archived':
            archived_record = record
        elif record.get('status') == Status.OPEN:
            new_record = record
    
    assert archived_record is not None, "应该有一条归档记录"
    assert archived_record['archive_reason'] == 'updated', f"归档原因应为'updated'，实际为{archived_record['archive_reason']}"
    assert archived_record['archived_at'] is not None, "归档记录应有archived_at"
    assert archived_record['completed_at'] is not None, "归档记录应保留completed_at"
    assert archived_record['confirmed_at'] is not None, "归档记录应保留confirmed_at"
    print(f"[OK] 验证归档记录: status={archived_record['status']}, reason={archived_record['archive_reason']}")
    
    # 验证新记录
    assert new_record is not None, "应该有一条新记录"
    assert new_record['interface_time'] == '2025-02-20', "新记录应有新的interface_time"
    assert new_record['completed_at'] is None, "新记录的completed_at应为空"
    assert new_record['confirmed_at'] is None, "新记录的confirmed_at应为空"
    # 验证first_seen_at格式
    first_seen = new_record['first_seen_at']
    assert '(更新日期)' in first_seen, f"新记录的first_seen_at应包含'(更新日期)'，实际为{first_seen}"
    print(f"[OK] 验证新记录: first_seen_at={first_seen}, interface_time={new_record['interface_time']}")
    
    print("[PASS] 测试场景1通过：版本化更新功能正常")


def test_no_versioning_without_complete_chain(temp_db):
    """
    测试场景2：没有完整数据链时不触发版本化
    
    步骤：
    1. 创建任务
    2. 只填写completed_at，不填写confirmed_at
    3. 修改interface_time，清空completed_at
    4. 验证：不创建新版本，只是重置状态
    """
    print("\n[测试] 场景2：无完整数据链时不触发版本化")
    
    now = datetime.now()
    
    # 创建任务并填写completed_at（但不确认）
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'TEST-VERSION-002',
        'source_file': 'test.xlsx',
        'row_index': 101
    }
    fields1 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        'completed_at': now.isoformat(),
        'completed_by': '设计人员张三',
        '_completed_col_value': '有值'
        # 注意：没有confirmed_at
    }
    upsert_task(temp_db, True, key, fields1, now)
    print("[OK] 创建任务并填写completed_at（无confirmed_at）")
    
    # 修改interface_time，清空completed_at
    future_time = now + timedelta(days=1)
    fields2 = {
        'department': '一室',
        'interface_time': '2025-02-20',
        'role': '设计人员',
        '_completed_col_value': ''
    }
    upsert_task(temp_db, True, key, fields2, future_time)
    print("[OK] 更新interface_time并清空completed_at")
    
    # 验证：应该只有1条记录，且状态被重置
    history = query_task_history(temp_db, True, '2016', 'TEST-VERSION-002', 1)
    print(f"[OK] 历史记录数: {len(history)}")
    
    assert len(history) == 1, f"无完整数据链时应该只有1条记录，实际{len(history)}条"
    assert history[0]['status'] == Status.OPEN, "记录状态应被重置为OPEN"
    assert history[0]['completed_at'] is None, "completed_at应被清空"
    assert history[0].get('archive_reason') is None, "不应该有归档记录"
    print(f"[OK] 验证: 状态重置为{history[0]['status']}, completed_at={history[0]['completed_at']}")
    
    print("[PASS] 测试场景2通过：无完整数据链时正确处理")


def test_confirmed_task_archived_after_7_days(temp_db):
    """
    测试场景3：确认后7天自动归档
    
    步骤：
    1. 创建任务并确认
    2. 将confirmed_at设置为8天前
    3. 运行finalize_scan
    4. 验证：任务被归档，归档原因为'confirmed_expired'
    """
    print("\n[测试] 场景3：确认后7天自动归档")
    
    now = datetime.now()
    eight_days_ago = now - timedelta(days=8)
    
    # 创建并确认任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'TEST-VERSION-003',
        'source_file': 'test.xlsx',
        'row_index': 102
    }
    fields = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'role': '设计人员',
        'completed_at': eight_days_ago.isoformat(),
        'completed_by': '设计人员张三',
        'confirmed_at': eight_days_ago.isoformat(),
        'confirmed_by': '室主任李四',
        'status': Status.CONFIRMED,
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, True, key, fields, eight_days_ago)
    print(f"[OK] 创建任务并设置confirmed_at为8天前: {eight_days_ago.strftime('%Y-%m-%d')}")
    
    # 运行归档扫描
    finalize_scan(temp_db, True, now, missing_keep_days=7)
    print("[OK] 运行finalize_scan")
    
    # 验证归档结果
    conn = get_connection(temp_db, True)
    cursor = conn.execute("""
        SELECT status, archive_reason, archived_at 
        FROM tasks 
        WHERE interface_id = 'TEST-VERSION-003'
    """)
    row = cursor.fetchone()
    
    assert row is not None, "应该找到任务记录"
    status, archive_reason, archived_at = row
    print(f"[OK] 任务状态: status={status}, archive_reason={archive_reason}, archived_at={archived_at}")
    
    assert status == 'archived', f"任务状态应为'archived'，实际为{status}"
    assert archive_reason == 'confirmed_expired', f"归档原因应为'confirmed_expired'，实际为{archive_reason}"
    assert archived_at is not None, "应该有archived_at时间戳"
    
    print("[PASS] 测试场景3通过：确认后7天归档功能正常")


def test_history_query_includes_archived(temp_db):
    """
    测试场景4：历史查询包含已归档记录
    
    步骤：
    1. 创建多个版本的任务（包括归档的）
    2. 查询历史记录
    3. 验证：所有版本都被返回
    """
    print("\n[测试] 场景4：历史查询包含所有版本")
    
    now = datetime.now()
    
    # 创建第一个版本并归档
    key1 = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'TEST-VERSION-004',
        'source_file': 'test.xlsx',
        'row_index': 103
    }
    fields1 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'completed_at': now.isoformat(),
        'confirmed_at': now.isoformat(),
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, True, key1, fields1, now)
    
    # 触发版本化（修改interface_time并清空completed_at）
    future_time = now + timedelta(days=1)
    fields2 = {
        'department': '一室',
        'interface_time': '2025-02-20',
        '_completed_col_value': ''
    }
    upsert_task(temp_db, True, key1, fields2, future_time)
    print("[OK] 创建两个版本（一个归档，一个活跃）")
    
    # 查询历史记录
    history = query_task_history(temp_db, True, '2016', 'TEST-VERSION-004', 1)
    print(f"[OK] 历史记录数: {len(history)}")
    
    assert len(history) == 2, f"应该查询到2条记录，实际{len(history)}条"
    
    # 验证包含归档记录
    statuses = [record['status'] for record in history]
    assert 'archived' in statuses, "历史记录应包含归档记录"
    assert Status.OPEN in statuses, "历史记录应包含活跃记录"
    
    print("[PASS] 测试场景4通过：历史查询包含所有版本")


def test_first_seen_at_format_for_versioned_record(temp_db):
    """
    测试场景5：验证新轮次记录的first_seen_at格式
    
    步骤：
    1. 创建完整数据链任务
    2. 触发版本化更新
    3. 验证新记录的first_seen_at包含"(更新日期)"标记
    """
    print("\n[测试] 场景5：验证first_seen_at格式")
    
    now = datetime.now()
    
    # 创建完整数据链任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'TEST-VERSION-005',
        'source_file': 'test.xlsx',
        'row_index': 104
    }
    fields1 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'completed_at': now.isoformat(),
        'confirmed_at': now.isoformat(),
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, True, key, fields1, now)
    
    # 触发版本化
    future_time = now + timedelta(days=1)
    fields2 = {
        'department': '一室',
        'interface_time': '2025-02-20',
        '_completed_col_value': ''
    }
    upsert_task(temp_db, True, key, fields2, future_time)
    
    # 查询并验证格式
    history = query_task_history(temp_db, True, '2016', 'TEST-VERSION-005', 1)
    print(f"[DEBUG] 查询到{len(history)}条记录")
    for idx, r in enumerate(history):
        print(f"[DEBUG] 记录{idx+1}: status={r['status']}, first_seen_at={r.get('first_seen_at')}")
    
    new_records = [r for r in history if r['status'] == Status.OPEN]
    assert len(new_records) > 0, f"应该有status为OPEN的记录，实际查询到{len(history)}条记录"
    new_record = new_records[0]
    
    first_seen = new_record['first_seen_at']
    expected_date = future_time.strftime('%Y-%m-%d')
    
    print(f"[OK] 新记录first_seen_at: {first_seen}")
    assert '(更新日期)' in first_seen, f"应包含'(更新日期)'标记，实际为{first_seen}"
    assert expected_date in first_seen, f"应包含日期{expected_date}，实际为{first_seen}"
    
    print("[PASS] 测试场景5通过：first_seen_at格式正确")


def test_no_versioning_on_first_completion(temp_db):
    """
    测试场景6：首次填写completed_at不触发版本化
    
    步骤：
    1. 创建任务（无completed_at）
    2. 首次填写completed_at
    3. 验证：不触发版本化
    """
    print("\n[测试] 场景6：首次填写不触发版本化")
    
    now = datetime.now()
    
    # 创建空任务
    key = {
        'file_type': 1,
        'project_id': '2016',
        'interface_id': 'TEST-VERSION-006',
        'source_file': 'test.xlsx',
        'row_index': 105
    }
    fields1 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        '_completed_col_value': ''
    }
    upsert_task(temp_db, True, key, fields1, now)
    
    # 首次填写completed_at
    fields2 = {
        'department': '一室',
        'interface_time': '2025-01-15',
        'completed_at': now.isoformat(),
        'completed_by': '设计人员张三',
        '_completed_col_value': '有值'
    }
    upsert_task(temp_db, True, key, fields2, now)
    print("[OK] 首次填写completed_at")
    
    # 验证只有一条记录
    history = query_task_history(temp_db, True, '2016', 'TEST-VERSION-006', 1)
    assert len(history) == 1, f"首次填写应该只有1条记录，实际{len(history)}条"
    assert history[0].get('archive_reason') is None, "不应该有归档记录"
    
    print("[PASS] 测试场景6通过：首次填写不触发版本化")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

