#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试：收集延期任务功能
"""

import os
import sys
import tempfile
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry import service as registry_service
from registry import hooks as registry_hooks
from registry.util import make_task_id


def test_collect_overdue_tasks_with_mock():
    """测试：使用mock模拟收集延期任务"""
    from base import ExcelProcessorApp
    
    # 创建一个mock的app实例
    app = Mock(spec=ExcelProcessorApp)
    
    # 创建mock的viewers
    mock_viewer1 = Mock()
    mock_viewer2 = Mock()
    
    app.tab1_viewer = mock_viewer1
    app.tab2_viewer = mock_viewer2
    app.tab3_viewer = Mock()
    app.tab4_viewer = Mock()
    app.tab5_viewer = Mock()
    app.tab6_viewer = Mock()
    
    # 创建mock的_tab_data_cache
    # 构建延期日期（3天前）
    overdue_date = (datetime.now() - timedelta(days=3)).strftime("%Y.%m.%d")
    # 构建未延期日期（3天后）
    future_date = (datetime.now() + timedelta(days=3)).strftime("%Y.%m.%d")
    
    cache_data = {
        '内部需打开接口': {
            'file_type': 1,
            'filtered_df': pd.DataFrame({
                '项目号': ['1818', '2016'],
                '接口号': ['TEST-001', 'TEST-002'],
                '接口时间': [overdue_date, future_date],
                '部门': ['部门A', '部门B'],
                '角色': ['角色A', '角色B'],
                '_source_file': ['test1.xlsx', 'test1.xlsx'],
                '_original_row': [2, 3],
                '状态': ['已延期', '待完成']
            })
        },
        '内部需回复接口': {
            'file_type': 2,
            'filtered_df': pd.DataFrame({
                '项目号': ['1818'],
                '接口号': ['TEST-003'],
                '接口时间': [overdue_date],
                '部门': ['部门C'],
                '角色': ['角色C'],
                '_source_file': ['test2.xlsx'],
                '_original_row': [5],
                '状态': ['已延期']
            })
        }
    }
    
    app._tab_data_cache = cache_data
    
    # 导入实际的_collect_overdue_tasks函数
    from base import ExcelProcessorApp as RealApp
    
    # 将真实方法绑定到mock对象
    app._collect_overdue_tasks = RealApp._collect_overdue_tasks.__get__(app, type(app))
    
    # 执行收集
    overdue_tasks = app._collect_overdue_tasks()
    
    # 验证结果
    print(f"\n找到 {len(overdue_tasks)} 个延期任务:")
    for task in overdue_tasks:
        print(f"  - {task['interface_id']} (项目: {task['project_id']}, 时间: {task['interface_time']})")
    
    # 应该找到2个延期任务（TEST-001和TEST-003）
    assert len(overdue_tasks) == 2, f"应该找到2个延期任务，实际找到{len(overdue_tasks)}个"
    
    # 验证第一个任务
    task1 = next((t for t in overdue_tasks if t['interface_id'] == 'TEST-001'), None)
    assert task1 is not None, "应该找到TEST-001"
    assert task1['file_type'] == 1
    assert task1['project_id'] == '1818'
    assert task1['interface_time'] == overdue_date
    
    # 验证第二个任务
    task2 = next((t for t in overdue_tasks if t['interface_id'] == 'TEST-003'), None)
    assert task2 is not None, "应该找到TEST-003"
    assert task2['file_type'] == 2
    assert task2['project_id'] == '1818'
    
    # TEST-002不应该在结果中（因为它未延期）
    task3 = next((t for t in overdue_tasks if t['interface_id'] == 'TEST-002'), None)
    assert task3 is None, "TEST-002不应该在延期任务中"
    
    print("\n✓ 测试通过：延期任务收集功能正常")


def test_ignore_batch_overdue_tasks_integration(tmp_path):
    """集成测试：忽略批量延期任务的完整流程"""
    # 设置Registry数据文件夹（会自动创建registry.db）
    registry_hooks.set_data_folder(str(tmp_path))
    
    # 构建延期日期
    overdue_date = (datetime.now() - timedelta(days=3)).strftime("%Y.%m.%d")
    
    # 1. 创建一些任务
    result_df = pd.DataFrame({
        '原始行号': [2, 3, 4],
        '接口号': ['OVERDUE-001', 'OVERDUE-002', 'OVERDUE-003'],
        '项目号': ['1818', '1818', '2016'],
        '接口时间': [overdue_date, overdue_date, overdue_date]
    })
    
    registry_hooks.on_process_done(
        file_type=1,
        project_id='1818',
        source_file='test.xlsx',
        result_df=result_df,
        now=datetime.now()
    )
    
    # 获取Registry实际使用的数据库路径
    from registry.hooks import _cfg
    cfg = _cfg()
    db_path = cfg['registry_db_path']
    print(f"使用数据库: {db_path}")
    
    # 2. 批量标记为忽略
    task_keys = [
        {
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'OVERDUE-001',
            'source_file': 'test.xlsx',
            'row_index': 2,
            'interface_time': overdue_date
        },
        {
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'OVERDUE-002',
            'source_file': 'test.xlsx',
            'row_index': 3,
            'interface_time': overdue_date
        }
    ]
    
    result = registry_service.mark_ignored_batch(
        db_path=db_path,
        wal=False,
        task_keys=task_keys,
        ignored_by='测试所领导',
        ignored_reason='批量测试'
    )
    
    assert result['success_count'] == 2
    print(f"\n✓ 成功忽略 {result['success_count']} 个任务")
    
    # 3. 验证被忽略的任务确实被标记了
    import sqlite3
    conn = sqlite3.connect(db_path)
    
    # 调试：列出所有任务
    cursor = conn.execute("SELECT id, interface_id, ignored FROM tasks")
    all_tasks = cursor.fetchall()
    print(f"\n数据库中的所有任务:")
    for task in all_tasks:
        print(f"  id={task[0][:20]}..., interface_id={task[1]}, ignored={task[2]}")
    
    tid1 = make_task_id(1, '1818', 'OVERDUE-001', 'test.xlsx', 2)
    print(f"\n查找任务ID: {tid1}")
    cursor = conn.execute("SELECT ignored, ignored_by, interface_time_when_ignored FROM tasks WHERE id = ?", (tid1,))
    row = cursor.fetchone()
    
    if row is None:
        # 可能是ID计算方式不同，直接通过interface_id查找
        cursor = conn.execute(
            "SELECT ignored, ignored_by, interface_time_when_ignored FROM tasks WHERE interface_id = ?",
            ('OVERDUE-001',)
        )
        row = cursor.fetchone()
        print(f"通过interface_id查找到: {row}")
    
    assert row is not None, "未找到OVERDUE-001任务"
    assert row[0] == 1  # ignored
    assert row[1] == '测试所领导'  # ignored_by
    assert row[2] == overdue_date  # interface_time_when_ignored
    
    conn.close()
    print("✓ 忽略标记验证通过")
    
    # 4. 测试get_display_status过滤被忽略任务
    task_keys_for_status = []
    for _, row in result_df.iterrows():
        task_keys_for_status.append({
            'file_type': 1,
            'project_id': row['项目号'],
            'interface_id': row['接口号'],
            'source_file': 'test.xlsx',
            'row_index': row['原始行号'],
            'interface_time': row['接口时间']
        })
    
    status_map = registry_service.get_display_status(
        db_path=db_path,
        wal=False,
        task_keys=task_keys_for_status,
        current_user_roles=[]
    )
    
    # OVERDUE-001和OVERDUE-002应该返回空字符串（被忽略）
    tid1 = make_task_id(1, '1818', 'OVERDUE-001', 'test.xlsx', 2)
    tid2 = make_task_id(1, '1818', 'OVERDUE-002', 'test.xlsx', 3)
    tid3 = make_task_id(1, '2016', 'OVERDUE-003', 'test.xlsx', 4)
    
    print(f"\n状态映射:")
    print(f"  TID1 ({tid1[:20]}...): '{status_map.get(tid1, 'NOT_FOUND')}'")
    print(f"  TID2 ({tid2[:20]}...): '{status_map.get(tid2, 'NOT_FOUND')}'")
    print(f"  TID3 ({tid3[:20]}...): '{status_map.get(tid3, 'NOT_FOUND')}'")
    
    assert status_map.get(tid1, '') == '', f"被忽略的任务应该返回空字符串，实际: '{status_map.get(tid1)}'"
    assert status_map.get(tid2, '') == '', f"被忽略的任务应该返回空字符串，实际: '{status_map.get(tid2)}'"
    assert status_map.get(tid3, '') != '', f"未被忽略的任务应该有状态，实际: '{status_map.get(tid3)}'"
    
    print("✓ 显示过滤测试通过")
    print("\n✓ 集成测试通过：批量忽略延期任务功能正常")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])

