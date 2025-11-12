"""
测试Registry确认后的过滤功能
验证确认后任务是否正确从显示列表中移除
"""
import os
import tempfile
import pytest
import pandas as pd
from datetime import datetime, timedelta
from registry.service import (
    upsert_task, mark_completed, mark_confirmed,
    query_task_history
)
from registry.db import init_db
from registry.util import make_task_id, extract_interface_id
import sys
import importlib

# 导入base模块用于测试过滤逻辑
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
base = importlib.import_module('base')


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


def test_filter_confirmed_tasks_from_display(temp_db):
    """
    测试场景：确认任务后，该任务应该从显示列表中过滤掉
    
    模拟流程：
    1. 创建3个待确认任务
    2. 上级确认其中1个
    3. 调用_exclude_pending_confirmation_rows过滤
    4. 验证已确认的任务被过滤，其他任务保留
    """
    now = datetime.now()
    
    # 1. 创建3个任务，都是已完成但待确认状态
    tasks_data = [
        {
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'IF-001',
                'source_file': 'test.xlsx',
                'row_index': 10
            },
            'fields': {
                'department': '一室',
                'interface_time': '2025-01-15',
                'role': '设计人员(一室主任)',
                'status': 'completed',
                'display_status': '待审查',
                'responsible_person': '张三',
                'response_number': 'HW-2025-001',
                'completed_by': '张三'
            }
        },
        {
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'IF-002',
                'source_file': 'test.xlsx',
                'row_index': 20
            },
            'fields': {
                'department': '一室',
                'interface_time': '2025-01-15',
                'role': '设计人员(一室主任)',
                'status': 'completed',
                'display_status': '待审查',
                'responsible_person': '李四',
                'response_number': 'HW-2025-002',
                'completed_by': '李四'
            }
        },
        {
            'key': {
                'file_type': 1,
                'project_id': '2016',
                'interface_id': 'IF-003',
                'source_file': 'test.xlsx',
                'row_index': 30
            },
            'fields': {
                'department': '一室',
                'interface_time': '2025-01-15',
                'role': '设计人员(一室主任)',
                'status': 'completed',
                'display_status': '待审查',
                'responsible_person': '王五',
                'response_number': 'HW-2025-003',
                'completed_by': '王五'
            }
        }
    ]
    
    # 创建所有任务
    for task in tasks_data:
        upsert_task(temp_db, False, task['key'], task['fields'], now)
        mark_completed(temp_db, False, task['key'], now)
    
    # 2. 上级确认第一个任务
    mark_confirmed(temp_db, False, tasks_data[0]['key'], now + timedelta(seconds=10), confirmed_by='李主任')
    
    # 3. 构造模拟DataFrame（包含所有3个任务）
    df = pd.DataFrame({
        '原始行号': [10, 20, 30],
        '接口号': ['IF-001', 'IF-002', 'IF-003'],
        '项目号': ['2016', '2016', '2016'],
        '责任人': ['张三', '李四', '王五'],
        '回文单号': ['HW-2025-001', 'HW-2025-002', 'HW-2025-003']
    })
    
    # 4. 创建一个模拟的app对象来调用_exclude_pending_confirmation_rows
    class MockApp:
        pass
    
    app = MockApp()
    # 将_exclude_pending_confirmation_rows方法绑定到app
    app._exclude_pending_confirmation_rows = lambda df, sf, ft, pid: base.ExcelProcessorApp._exclude_pending_confirmation_rows(
        app, df, sf, ft, pid
    )
    
    # 临时修改registry配置，使用我们的测试数据库
    import registry.hooks as registry_hooks
    original_cfg = registry_hooks._cfg
    registry_hooks._cfg = lambda: {'registry_db_path': temp_db, 'wal': False}
    
    try:
        # 5. 调用过滤函数
        filtered_df = app._exclude_pending_confirmation_rows(
            df.copy(),
            'test.xlsx',
            1,  # file_type
            '2016'  # project_id
        )
        
        # 6. 验证结果
        # IF-001已确认，应该被过滤掉
        # IF-002和IF-003待审查，应该保留
        assert len(filtered_df) == 2, f"应该保留2行，实际保留了{len(filtered_df)}行"
        assert 'IF-002' in filtered_df['接口号'].values, "IF-002应该保留"
        assert 'IF-003' in filtered_df['接口号'].values, "IF-003应该保留"
        assert 'IF-001' not in filtered_df['接口号'].values, "IF-001已确认，应该被过滤"
        
        print("[测试通过] 确认后任务正确从显示列表中过滤")
        
    finally:
        # 恢复原始配置
        registry_hooks._cfg = original_cfg


def test_filter_multiple_confirmed_tasks(temp_db):
    """
    测试场景：多个任务被确认后，都应该被过滤
    """
    now = datetime.now()
    
    # 创建5个任务
    tasks = []
    for i in range(5):
        key = {
            'file_type': 2,
            'project_id': '1818',
            'interface_id': f'IF-{i+1:03d}',
            'source_file': 'test2.xlsx',
            'row_index': (i+1) * 10
        }
        fields = {
            'department': '二室',
            'interface_time': '2025-01-20',
            'role': '设计人员',
            'status': 'completed',
            'display_status': '待审查',
            'responsible_person': f'员工{i+1}',
            'response_number': f'HW-{i+1:03d}',
            'completed_by': f'员工{i+1}'
        }
        tasks.append({'key': key, 'fields': fields})
        upsert_task(temp_db, False, key, fields, now)
        mark_completed(temp_db, False, key, now)
    
    # 确认前3个任务
    for i in range(3):
        mark_confirmed(temp_db, False, tasks[i]['key'], now + timedelta(seconds=i+1), confirmed_by='王主任')
    
    # 构造DataFrame
    df = pd.DataFrame({
        '原始行号': [(i+1) * 10 for i in range(5)],
        '接口号': [f'IF-{i+1:03d}' for i in range(5)],
        '项目号': ['1818'] * 5,
        '责任人': [f'员工{i+1}' for i in range(5)]
    })
    
    # 模拟过滤
    class MockApp:
        pass
    
    app = MockApp()
    app._exclude_pending_confirmation_rows = lambda df, sf, ft, pid: base.ExcelProcessorApp._exclude_pending_confirmation_rows(
        app, df, sf, ft, pid
    )
    
    import registry.hooks as registry_hooks
    original_cfg = registry_hooks._cfg
    registry_hooks._cfg = lambda: {'registry_db_path': temp_db, 'wal': False}
    
    try:
        filtered_df = app._exclude_pending_confirmation_rows(
            df.copy(),
            'test2.xlsx',
            2,
            '1818'
        )
        
        # 验证：前3个已确认，应该被过滤；后2个待审查，应该保留
        assert len(filtered_df) == 2, f"应该保留2行（IF-004和IF-005），实际保留了{len(filtered_df)}行"
        assert 'IF-004' in filtered_df['接口号'].values
        assert 'IF-005' in filtered_df['接口号'].values
        assert 'IF-001' not in filtered_df['接口号'].values
        assert 'IF-002' not in filtered_df['接口号'].values
        assert 'IF-003' not in filtered_df['接口号'].values
        
        print("[测试通过] 多个确认任务正确过滤")
        
    finally:
        registry_hooks._cfg = original_cfg


def test_no_filter_if_all_pending(temp_db):
    """
    测试场景：如果所有任务都待审查，不应该过滤任何任务
    """
    now = datetime.now()
    
    # 创建2个待审查任务
    for i in range(2):
        key = {
            'file_type': 3,
            'project_id': '1907',
            'interface_id': f'EXT-{i+1:02d}',
            'source_file': 'test3.xlsx',
            'row_index': (i+1) * 10
        }
        fields = {
            'department': '三室',
            'interface_time': '2025-02-01',
            'role': '设计人员',
            'status': 'completed',
            'display_status': '待审查',
            'responsible_person': f'设计{i+1}',
            'response_number': f'EXT-{i+1:02d}',
            'completed_by': f'设计{i+1}'
        }
        upsert_task(temp_db, False, key, fields, now)
        mark_completed(temp_db, False, key, now)
    
    # 不确认任何任务
    
    # 构造DataFrame
    df = pd.DataFrame({
        '原始行号': [10, 20],
        '接口号': ['EXT-01', 'EXT-02'],
        '项目号': ['1907', '1907'],
        '责任人': ['设计1', '设计2']
    })
    
    # 模拟过滤
    class MockApp:
        pass
    
    app = MockApp()
    app._exclude_pending_confirmation_rows = lambda df, sf, ft, pid: base.ExcelProcessorApp._exclude_pending_confirmation_rows(
        app, df, sf, ft, pid
    )
    
    import registry.hooks as registry_hooks
    original_cfg = registry_hooks._cfg
    registry_hooks._cfg = lambda: {'registry_db_path': temp_db, 'wal': False}
    
    try:
        filtered_df = app._exclude_pending_confirmation_rows(
            df.copy(),
            'test3.xlsx',
            3,
            '1907'
        )
        
        # 验证：所有任务都保留
        assert len(filtered_df) == 2, "所有任务都应该保留"
        assert 'EXT-01' in filtered_df['接口号'].values
        assert 'EXT-02' in filtered_df['接口号'].values
        
        print("[测试通过] 无已确认任务时不过滤")
        
    finally:
        registry_hooks._cfg = original_cfg


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

