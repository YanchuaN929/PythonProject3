#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试收集延期任务功能的真实场景

验证：
1. _collect_overdue_tasks能够从viewer.df中正确读取数据
2. 能够正确识别延期任务
3. 能够处理各种边界情况
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock


def test_collect_overdue_from_viewer_df():
    """测试从viewer.df收集延期任务"""
    # 模拟ExcelProcessorApp实例
    from base import ExcelProcessorApp
    
    # 创建mock app（不启动GUI）
    app = Mock(spec=ExcelProcessorApp)
    
    # 构建包含延期任务的测试数据
    overdue_date = (datetime.now() - timedelta(days=5)).strftime("%Y.%m.%d")  # 5天前
    future_date = (datetime.now() + timedelta(days=5)).strftime("%Y.%m.%d")   # 5天后
    today_date = datetime.now().strftime("%Y.%m.%d")                           # 今天
    
    test_df = pd.DataFrame({
        '接口号': ['TEST-001', 'TEST-002', 'TEST-003', 'TEST-004'],
        '项目号': ['1818', '1818', '2016', '1818'],
        '接口时间': [overdue_date, future_date, overdue_date, today_date],
        '状态': ['待完成', '待审查', '待完成', '已完成'],
        '_source_file': ['test1.xlsx', 'test2.xlsx', 'test3.xlsx', 'test4.xlsx'],
        '_original_row': [2, 3, 4, 5]
    })
    
    print(f"\n测试数据:")
    print(f"  TEST-001: {overdue_date} (已延期)")
    print(f"  TEST-002: {future_date} (未来)")
    print(f"  TEST-003: {overdue_date} (已延期)")
    print(f"  TEST-004: {today_date} (今天)")
    
    # 创建mock viewer
    mock_viewer = Mock()
    mock_viewer.df = test_df
    
    # 设置app的viewers
    app.tab1_viewer = mock_viewer
    app.tab2_viewer = Mock()
    app.tab2_viewer.df = pd.DataFrame()  # 空数据
    app.tab3_viewer = Mock()
    app.tab3_viewer.df = None  # None数据
    app.tab4_viewer = Mock()
    app.tab4_viewer.df = test_df.iloc[[1]]  # 只有未来日期的任务
    app.tab5_viewer = Mock()
    app.tab5_viewer.df = pd.DataFrame()
    app.tab6_viewer = Mock()
    app.tab6_viewer.df = pd.DataFrame()
    
    # 绑定真实的_collect_overdue_tasks方法
    from base import ExcelProcessorApp as RealApp
    app._collect_overdue_tasks = RealApp._collect_overdue_tasks.__get__(app, type(app))
    
    # 执行收集
    overdue_tasks = app._collect_overdue_tasks()
    
    print(f"\n收集到的延期任务: {len(overdue_tasks)}")
    for task in overdue_tasks:
        print(f"  - {task['interface_id']} ({task['interface_time']})")
    
    # 验证结果
    assert len(overdue_tasks) == 2, f"应该收集到2个延期任务（TEST-001和TEST-003），实际收集到{len(overdue_tasks)}个"
    
    # 验证具体任务
    interface_ids = [task['interface_id'] for task in overdue_tasks]
    assert 'TEST-001' in interface_ids, "应该包含TEST-001"
    assert 'TEST-003' in interface_ids, "应该包含TEST-003"
    assert 'TEST-002' not in interface_ids, "不应该包含未来日期的TEST-002"
    assert 'TEST-004' not in interface_ids, "不应该包含今天日期的TEST-004"
    
    print("\n✓ 延期任务收集功能正常")


def test_collect_overdue_with_empty_data():
    """测试当所有viewer都是空数据时的情况"""
    from base import ExcelProcessorApp
    
    app = Mock(spec=ExcelProcessorApp)
    
    # 所有viewer都是空的
    for attr in ['tab1_viewer', 'tab2_viewer', 'tab3_viewer', 'tab4_viewer', 'tab5_viewer', 'tab6_viewer']:
        mock_viewer = Mock()
        mock_viewer.df = pd.DataFrame()
        setattr(app, attr, mock_viewer)
    
    # 绑定方法
    from base import ExcelProcessorApp as RealApp
    app._collect_overdue_tasks = RealApp._collect_overdue_tasks.__get__(app, type(app))
    
    # 执行收集
    overdue_tasks = app._collect_overdue_tasks()
    
    print(f"\n✓ 空数据情况：收集到 {len(overdue_tasks)} 个任务")
    assert len(overdue_tasks) == 0, "空数据应该返回0个任务"


def test_collect_overdue_with_invalid_dates():
    """测试包含无效日期的情况"""
    from base import ExcelProcessorApp
    
    app = Mock(spec=ExcelProcessorApp)
    
    overdue_date = (datetime.now() - timedelta(days=3)).strftime("%Y.%m.%d")
    
    # 包含各种无效日期
    test_df = pd.DataFrame({
        '接口号': ['TEST-001', 'TEST-002', 'TEST-003', 'TEST-004', 'TEST-005'],
        '项目号': ['1818', '1818', '1818', '1818', '1818'],
        '接口时间': [overdue_date, '', '-', 'nan', None],
        '状态': ['待完成', '待完成', '待完成', '待完成', '待完成'],
        '_source_file': ['test.xlsx'] * 5,
        '_original_row': [2, 3, 4, 5, 6]
    })
    
    mock_viewer = Mock()
    mock_viewer.df = test_df
    app.tab1_viewer = mock_viewer
    
    for attr in ['tab2_viewer', 'tab3_viewer', 'tab4_viewer', 'tab5_viewer', 'tab6_viewer']:
        mock = Mock()
        mock.df = pd.DataFrame()
        setattr(app, attr, mock)
    
    from base import ExcelProcessorApp as RealApp
    app._collect_overdue_tasks = RealApp._collect_overdue_tasks.__get__(app, type(app))
    
    overdue_tasks = app._collect_overdue_tasks()
    
    print(f"\n✓ 无效日期处理：只收集到 {len(overdue_tasks)} 个有效延期任务")
    assert len(overdue_tasks) == 1, "只有TEST-001有有效的延期日期"
    assert overdue_tasks[0]['interface_id'] == 'TEST-001'


def test_collect_overdue_with_missing_columns():
    """测试缺少必要列的情况"""
    from base import ExcelProcessorApp
    
    app = Mock(spec=ExcelProcessorApp)
    
    overdue_date = (datetime.now() - timedelta(days=3)).strftime("%Y.%m.%d")
    
    # 缺少项目号列
    test_df_no_project = pd.DataFrame({
        '接口号': ['TEST-001'],
        '接口时间': [overdue_date],
        '状态': ['待完成']
    })
    
    mock_viewer = Mock()
    mock_viewer.df = test_df_no_project
    app.tab1_viewer = mock_viewer
    
    for attr in ['tab2_viewer', 'tab3_viewer', 'tab4_viewer', 'tab5_viewer', 'tab6_viewer']:
        mock = Mock()
        mock.df = pd.DataFrame()
        setattr(app, attr, mock)
    
    from base import ExcelProcessorApp as RealApp
    app._collect_overdue_tasks = RealApp._collect_overdue_tasks.__get__(app, type(app))
    
    # 应该能够处理而不崩溃
    overdue_tasks = app._collect_overdue_tasks()
    
    print(f"\n✓ 缺少列处理：收集到 {len(overdue_tasks)} 个任务（应为0，因为缺少项目号）")
    assert len(overdue_tasks) == 0, "缺少项目号的任务不应该被收集"


def test_collect_overdue_integration():
    """集成测试：模拟真实的多选项卡场景"""
    from base import ExcelProcessorApp
    
    app = Mock(spec=ExcelProcessorApp)
    
    # 创建不同选项卡的数据
    overdue1 = (datetime.now() - timedelta(days=10)).strftime("%Y.%m.%d")
    overdue2 = (datetime.now() - timedelta(days=5)).strftime("%Y.%m.%d")
    overdue3 = (datetime.now() - timedelta(days=1)).strftime("%Y.%m.%d")
    future = (datetime.now() + timedelta(days=3)).strftime("%Y.%m.%d")
    
    # Tab1: 内部需打开接口 - 1个延期，1个未来
    tab1_df = pd.DataFrame({
        '接口号': ['INT-OPEN-001', 'INT-OPEN-002'],
        '项目号': ['1818', '1818'],
        '接口时间': [overdue1, future],
        '状态': ['待完成', '待完成'],
        '_source_file': ['internal_open.xlsx', 'internal_open.xlsx'],
        '_original_row': [2, 3]
    })
    
    # Tab2: 内部需回复接口 - 1个延期
    tab2_df = pd.DataFrame({
        '接口号': ['INT-REPLY-001'],
        '项目号': ['2016'],
        '接口时间': [overdue2],
        '状态': ['待审查'],
        '_source_file': ['internal_reply.xlsx'],
        '_original_row': [2]
    })
    
    # Tab3: 外部需打开接口 - 无数据
    tab3_df = pd.DataFrame()
    
    # Tab4: 外部需回复接口 - 1个延期
    tab4_df = pd.DataFrame({
        '接口号': ['EXT-REPLY-001'],
        '项目号': ['1818'],
        '接口时间': [overdue3],
        '状态': ['待完成'],
        '_source_file': ['external_reply.xlsx'],
        '_original_row': [5]
    })
    
    # 设置所有viewer
    app.tab1_viewer = Mock()
    app.tab1_viewer.df = tab1_df
    app.tab2_viewer = Mock()
    app.tab2_viewer.df = tab2_df
    app.tab3_viewer = Mock()
    app.tab3_viewer.df = tab3_df
    app.tab4_viewer = Mock()
    app.tab4_viewer.df = tab4_df
    app.tab5_viewer = Mock()
    app.tab5_viewer.df = pd.DataFrame()
    app.tab6_viewer = Mock()
    app.tab6_viewer.df = pd.DataFrame()
    
    from base import ExcelProcessorApp as RealApp
    app._collect_overdue_tasks = RealApp._collect_overdue_tasks.__get__(app, type(app))
    
    overdue_tasks = app._collect_overdue_tasks()
    
    print(f"\n集成测试收集到的任务:")
    for task in overdue_tasks:
        print(f"  - {task['interface_id']} ({task['tab_name']}, {task['interface_time']})")
    
    assert len(overdue_tasks) == 3, f"应该收集到3个延期任务（10天前、5天前、1天前），实际收集到{len(overdue_tasks)}个"
    
    # 验证包含所有延期任务
    interface_ids = [task['interface_id'] for task in overdue_tasks]
    assert 'INT-OPEN-001' in interface_ids, "应包含10天前的任务"
    assert 'INT-REPLY-001' in interface_ids, "应包含5天前的任务"
    assert 'EXT-REPLY-001' in interface_ids, "应包含1天前的任务"
    assert 'INT-OPEN-002' not in interface_ids, "未来日期不应包含"
    
    # 验证file_type正确
    file_types = {task['interface_id']: task['file_type'] for task in overdue_tasks}
    assert file_types['INT-OPEN-001'] == 1
    assert file_types['INT-REPLY-001'] == 2
    assert file_types['EXT-REPLY-001'] == 4
    
    print("\n✓ 集成测试通过：多选项卡延期任务收集正常")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

