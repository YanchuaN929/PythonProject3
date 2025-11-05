"""
Registry模块基础测试

测试数据库建表、任务创建更新、状态流转等核心功能
"""
import pytest
import os
import shutil
import tempfile
import pandas as pd
from datetime import datetime

from registry import hooks
from registry.db import get_connection, init_db
from registry.service import upsert_task, write_event, mark_completed, mark_confirmed
from registry.models import Status, EventType
from registry.util import make_task_id, extract_interface_id, normalize_project_id
from registry.config import load_config


class TestRegistryBasic:
    """Registry模块基础测试"""
    
    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库"""
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test_registry.db")
        yield db_path
        # 清理：先关闭数据库连接
        try:
            from registry.db import close_connection
            close_connection()
        except:
            pass
        # 等待一下让文件句柄释放
        import time
        time.sleep(0.1)
        # 删除临时目录
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except PermissionError:
            # Windows上可能文件还在占用，忽略
            pass
    
    def test_database_initialization(self, temp_db_path):
        """测试数据库初始化和建表"""
        conn = get_connection(temp_db_path, wal=False)
        assert conn is not None
        
        # 检查tasks表
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        assert cursor.fetchone() is not None
        
        # 检查events表
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        assert cursor.fetchone() is not None
        
        print("[PASS] 数据库建表测试通过")
    
    def test_task_upsert(self, temp_db_path):
        """测试任务创建和更新"""
        now = datetime.now()
        
        # 第一次创建任务
        key = {
            'file_type': 1,
            'project_id': '1234',
            'interface_id': 'INT-001',
            'source_file': 'test.xlsx',
            'row_index': 10
        }
        fields = {
            'department': '研发部',
            'interface_time': '12.25'
        }
        
        upsert_task(temp_db_path, False, key, fields, now)
        
        # 验证任务创建
        conn = get_connection(temp_db_path, False)
        tid = make_task_id(1, '1234', 'INT-001', 'test.xlsx', 10)
        cursor = conn.execute("SELECT * FROM tasks WHERE id=?", (tid,))
        task = cursor.fetchone()
        
        assert task is not None
        # 列顺序：id, file_type, project_id, interface_id, source_file, row_index, 
        #        department, interface_time, role, status, ...
        assert task[9] == Status.OPEN  # status列（索引9）
        print(f"任务创建成功: {task[0][:8]}...")
        
        # 第二次更新任务（模拟再次扫描）
        fields['department'] = '技术部'
        upsert_task(temp_db_path, False, key, fields, now)
        
        cursor = conn.execute("SELECT department FROM tasks WHERE id=?", (tid,))
        updated_task = cursor.fetchone()
        assert updated_task[0] == '技术部'
        
        print("[PASS] 任务创建和更新测试通过")
    
    def test_status_flow(self, temp_db_path):
        """测试状态流转: open → completed → confirmed"""
        now = datetime.now()
        
        # 创建任务
        key = {
            'file_type': 2,
            'project_id': '5678',
            'interface_id': 'INT-002',
            'source_file': 'test2.xlsx',
            'row_index': 20
        }
        fields = {'department': '设计部', 'interface_time': '01.15'}
        upsert_task(temp_db_path, False, key, fields, now)
        
        tid = make_task_id(2, '5678', 'INT-002', 'test2.xlsx', 20)
        conn = get_connection(temp_db_path, False)
        
        # 验证初始状态
        cursor = conn.execute("SELECT status FROM tasks WHERE id=?", (tid,))
        assert cursor.fetchone()[0] == Status.OPEN
        
        # 标记为completed
        mark_completed(temp_db_path, False, key, now)
        cursor = conn.execute("SELECT status, completed_at FROM tasks WHERE id=?", (tid,))
        row = cursor.fetchone()
        assert row[0] == Status.COMPLETED
        assert row[1] is not None
        print(f"状态转换: open -> completed [OK]")
        
        # 标记为confirmed
        mark_confirmed(temp_db_path, False, key, now)
        cursor = conn.execute("SELECT status, confirmed_at FROM tasks WHERE id=?", (tid,))
        row = cursor.fetchone()
        assert row[0] == Status.CONFIRMED
        assert row[1] is not None
        print(f"状态转换: completed -> confirmed [OK]")
        
        print("[PASS] 状态流转测试通过")
    
    def test_event_logging(self, temp_db_path):
        """测试事件记录"""
        now = datetime.now()
        
        # 记录process_done事件
        write_event(temp_db_path, False, EventType.PROCESS_DONE, {
            'file_type': 3,
            'project_id': '9999',
            'source_file': 'test3.xlsx',
            'extra': {'count': 10}
        }, now)
        
        # 记录response_written事件
        write_event(temp_db_path, False, EventType.RESPONSE_WRITTEN, {
            'file_type': 3,
            'project_id': '9999',
            'interface_id': 'INT-003',
            'source_file': 'test3.xlsx',
            'row_index': 5,
            'extra': {'response_number': 'RESP-001', 'user_name': '张三'}
        }, now)
        
        # 验证事件记录
        conn = get_connection(temp_db_path, False)
        cursor = conn.execute("SELECT COUNT(*) FROM events")
        count = cursor.fetchone()[0]
        assert count >= 2
        
        cursor = conn.execute("SELECT event FROM events WHERE event=?", (EventType.RESPONSE_WRITTEN,))
        assert cursor.fetchone() is not None
        
        print(f"[PASS] 事件记录测试通过，共{count}条事件")
    
    def test_util_functions(self):
        """测试工具函数"""
        # 测试task_id生成
        tid1 = make_task_id(1, '1234', 'INT-001', 'test.xlsx', 10)
        tid2 = make_task_id(1, '1234', 'INT-001', 'test.xlsx', 10)
        assert tid1 == tid2  # 相同输入应生成相同ID
        assert len(tid1) == 40  # SHA1长度
        
        # 测试接口号提取
        row = pd.Series(['INT-001', 'data1', 'data2'], index=[0, 1, 2])
        interface_id = extract_interface_id(row, file_type=1)
        assert interface_id == 'INT-001'
        
        # 测试项目号规范化
        pid = normalize_project_id('  1234  ', 1)
        assert pid == '1234'
        
        pid_file6 = normalize_project_id('', 6)
        assert pid_file6 == '未知项目'
        
        print("[PASS] 工具函数测试通过")
    
    def test_hooks_integration(self, temp_db_path, monkeypatch):
        """测试钩子集成"""
        # 临时设置配置
        monkeypatch.setenv('REGISTRY_ENABLED', 'true')
        
        # 模拟配置
        test_config = {
            'registry_enabled': True,
            'registry_db_path': temp_db_path,
            'registry_wal': False
        }
        
        # 创建测试DataFrame
        df = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002'],
            '项目号': ['1234', '1234'],
            '部门': ['研发部', '设计部'],
            '接口时间': ['12.25', '01.15'],
            '原始行号': [10, 11]
        })
        
        # 调用on_process_done钩子
        from registry.config import DEFAULTS
        DEFAULTS['registry_enabled'] = True
        DEFAULTS['registry_db_path'] = temp_db_path
        DEFAULTS['registry_wal'] = False
        
        hooks.on_process_done(
            file_type=1,
            project_id='1234',
            source_file='test.xlsx',
            result_df=df,
            now=datetime.now()
        )
        
        # 验证任务创建
        conn = get_connection(temp_db_path, False)
        cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id='1234'")
        count = cursor.fetchone()[0]
        assert count == 2
        
        # 验证事件记录
        cursor = conn.execute("SELECT COUNT(*) FROM events WHERE event=?", (EventType.PROCESS_DONE,))
        event_count = cursor.fetchone()[0]
        assert event_count >= 1
        
        print(f"[PASS] 钩子集成测试通过，创建{count}个任务，{event_count}个事件")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

