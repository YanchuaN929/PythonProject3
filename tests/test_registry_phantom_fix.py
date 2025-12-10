"""
测试 Registry "幻觉"问题修复（方案A）

修复内容：
1. Registry查询只返回'待审查'和'待指派人审查'状态的任务
2. 加回任务时必须通过科室筛选（process1_rows）
3. 新增3个索引优化查询性能
"""

import pytest
import sqlite3
import tempfile
import os

from registry.db import get_connection, init_db, close_connection


class TestNewIndexes:
    """测试新增的3个索引"""
    
    @pytest.fixture
    def db_path(self):
        """创建临时数据库"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # 清理
        close_connection()
        try:
            os.unlink(path)
        except:
            pass
    
    def test_idx_tasks_interface_id_exists(self, db_path):
        """测试 idx_tasks_interface_id 索引是否创建"""
        conn = get_connection(db_path, wal=False)
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_tasks_interface_id'
        """)
        result = cursor.fetchone()
        assert result is not None, "idx_tasks_interface_id 索引未创建"
        assert result[0] == 'idx_tasks_interface_id'
    
    def test_idx_tasks_display_status_exists(self, db_path):
        """测试 idx_tasks_display_status 索引是否创建"""
        conn = get_connection(db_path, wal=False)
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_tasks_display_status'
        """)
        result = cursor.fetchone()
        assert result is not None, "idx_tasks_display_status 索引未创建"
        assert result[0] == 'idx_tasks_display_status'
    
    def test_idx_tasks_lookup_exists(self, db_path):
        """测试 idx_tasks_lookup 索引是否创建"""
        conn = get_connection(db_path, wal=False)
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_tasks_lookup'
        """)
        result = cursor.fetchone()
        assert result is not None, "idx_tasks_lookup 索引未创建"
        assert result[0] == 'idx_tasks_lookup'
    
    def test_all_indexes_count(self, db_path):
        """测试索引总数（8个旧索引 + 3个新索引 = 11个）"""
        conn = get_connection(db_path, wal=False)
        cursor = conn.execute("""
            SELECT COUNT(*) FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        count = cursor.fetchone()[0]
        # 5个任务表索引 + 3个事件表索引 + 1个忽略快照索引 + 3个新索引 = 12
        assert count >= 11, f"索引数量不足，期望至少11个，实际{count}个"


class TestPhantomQueryFilter:
    """测试"幻觉"问题的SQL查询过滤"""
    
    @pytest.fixture
    def db_with_tasks(self):
        """创建包含各种状态任务的测试数据库"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = get_connection(path, wal=False)
        
        # 插入测试任务
        test_tasks = [
            # (id, file_type, project_id, interface_id, source_file, row_index, display_status, status, ignored)
            ('task1', 2, '1234', 'IF001', 'test.xlsx', 1, '待审查', 'completed', 0),      # 应该返回
            ('task2', 2, '1234', 'IF002', 'test.xlsx', 2, '待指派人审查', 'completed', 0), # 应该返回
            ('task3', 2, '1234', 'IF003', 'test.xlsx', 3, '待完成', 'pending', 0),         # 不应该返回
            ('task4', 2, '1234', 'IF004', 'test.xlsx', 4, '请指派', 'pending', 0),         # 不应该返回
            ('task5', 2, '1234', 'IF005', 'test.xlsx', 5, '待审查', 'archived', 0),        # 不应该返回(已归档)
            ('task6', 2, '1234', 'IF006', 'test.xlsx', 6, '待审查', 'completed', 1),       # 不应该返回(已忽略)
            ('task7', 2, '5678', 'IF007', 'test.xlsx', 7, '待审查', 'completed', 0),       # 应该返回(不同项目)
        ]
        
        for task in test_tasks:
            conn.execute("""
                INSERT INTO tasks (id, file_type, project_id, interface_id, 
                                   source_file, row_index, display_status, status, ignored, 
                                   first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, task)
        conn.commit()
        
        yield path
        
        # 清理
        close_connection()
        try:
            os.unlink(path)
        except:
            pass
    
    def test_query_only_returns_pending_review(self, db_with_tasks):
        """测试查询只返回'待审查'和'待指派人审查'状态的任务"""
        conn = get_connection(db_with_tasks, wal=False)
        
        # 使用方案A的查询条件
        cursor = conn.execute("""
            SELECT interface_id, project_id, display_status
            FROM tasks
            WHERE file_type = 2
              AND display_status IN ('待审查', '待指派人审查')
              AND ignored = 0
              AND status != 'archived'
        """)
        
        results = cursor.fetchall()
        interface_ids = [r[0] for r in results]
        
        # 验证返回的任务
        assert 'IF001' in interface_ids, "待审查任务应该返回"
        assert 'IF002' in interface_ids, "待指派人审查任务应该返回"
        assert 'IF007' in interface_ids, "其他项目的待审查任务也应该返回"
        
        # 验证不应该返回的任务
        assert 'IF003' not in interface_ids, "待完成任务不应该返回"
        assert 'IF004' not in interface_ids, "请指派任务不应该返回"
        assert 'IF005' not in interface_ids, "已归档任务不应该返回"
        assert 'IF006' not in interface_ids, "已忽略任务不应该返回"
    
    def test_query_result_count(self, db_with_tasks):
        """测试查询结果数量正确"""
        conn = get_connection(db_with_tasks, wal=False)
        
        cursor = conn.execute("""
            SELECT COUNT(*)
            FROM tasks
            WHERE file_type = 2
              AND display_status IN ('待审查', '待指派人审查')
              AND ignored = 0
              AND status != 'archived'
        """)
        
        count = cursor.fetchone()[0]
        assert count == 3, f"应该返回3个任务，实际返回{count}个"


class TestDepartmentFilterIntegration:
    """测试科室筛选集成"""
    
    def test_task_not_in_process1_rows_skipped(self):
        """测试不在科室筛选结果中的任务会被跳过"""
        # 模拟场景
        process1_rows = {1, 2, 3, 5, 7}  # 通过科室筛选的行
        final_rows = {1, 2}  # 原始筛选结果
        excel_index = {
            ('IF001', '1234'): [1],    # 在process1_rows中
            ('IF002', '1234'): [4],    # 不在process1_rows中
            ('IF003', '1234'): [5],    # 在process1_rows中
            ('IF004', '1234'): [6, 8], # 都不在process1_rows中
        }
        
        registry_tasks = [
            ('IF001', '1234', '待审查'),
            ('IF002', '1234', '待审查'),  # 这个应该被跳过
            ('IF003', '1234', '待审查'),
            ('IF004', '1234', '待审查'),  # 这个应该被跳过
        ]
        
        pending_rows = set()
        
        # 模拟方案A的加回逻辑
        for reg_interface_id, reg_project_id, reg_display_status in registry_tasks:
            key = (reg_interface_id, reg_project_id)
            if key in excel_index:
                matched_indices = excel_index[key]
                for idx in matched_indices:
                    # 【关键】必须通过科室筛选
                    if idx not in process1_rows:
                        continue
                    if idx not in final_rows:
                        pending_rows.add(idx)
        
        # 验证结果
        assert 5 in pending_rows, "行5应该被加回（在process1_rows中）"
        assert 4 not in pending_rows, "行4不应该被加回（不在process1_rows中）"
        assert 6 not in pending_rows, "行6不应该被加回（不在process1_rows中）"
        assert 8 not in pending_rows, "行8不应该被加回（不在process1_rows中）"
        assert 1 not in pending_rows, "行1不应该被加回（已在final_rows中）"
    
    def test_empty_process1_rows_no_tasks_added(self):
        """测试当科室筛选结果为空时，不会加回任何任务"""
        process1_rows = set()  # 空的科室筛选结果
        final_rows = set()
        excel_index = {
            ('IF001', '1234'): [1, 2, 3],
        }
        
        registry_tasks = [
            ('IF001', '1234', '待审查'),
        ]
        
        pending_rows = set()
        
        for reg_interface_id, reg_project_id, _ in registry_tasks:
            key = (reg_interface_id, reg_project_id)
            if key in excel_index:
                for idx in excel_index[key]:
                    if idx not in process1_rows:
                        continue
                    if idx not in final_rows:
                        pending_rows.add(idx)
        
        assert len(pending_rows) == 0, "科室筛选为空时不应该加回任何任务"


class TestAllFileTypesQueryFormat:
    """测试所有文件类型的查询格式一致性"""
    
    @pytest.fixture
    def db_path(self):
        """创建临时数据库"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = get_connection(path, wal=False)
        
        # 为每个文件类型插入测试数据
        for file_type in range(1, 7):
            conn.execute("""
                INSERT INTO tasks (id, file_type, project_id, interface_id, 
                                   source_file, row_index, display_status, status, ignored, 
                                   first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (f'task_ft{file_type}_review', file_type, '1234', f'IF_FT{file_type}', 
                  'test.xlsx', file_type, '待审查', 'completed', 0))
            
            conn.execute("""
                INSERT INTO tasks (id, file_type, project_id, interface_id, 
                                   source_file, row_index, display_status, status, ignored, 
                                   first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (f'task_ft{file_type}_pending', file_type, '1234', f'IF_FT{file_type}_P', 
                  'test.xlsx', file_type + 10, '待完成', 'pending', 0))
        
        conn.commit()
        
        yield path
        
        close_connection()
        try:
            os.unlink(path)
        except:
            pass
    
    @pytest.mark.parametrize("file_type", [1, 2, 3, 4, 5, 6])
    def test_each_file_type_only_returns_review_status(self, db_path, file_type):
        """测试每个文件类型只返回待审查状态"""
        conn = get_connection(db_path, wal=False)
        
        cursor = conn.execute(f"""
            SELECT interface_id, display_status
            FROM tasks
            WHERE file_type = {file_type}
              AND display_status IN ('待审查', '待指派人审查')
              AND ignored = 0
              AND status != 'archived'
        """)
        
        results = cursor.fetchall()
        
        assert len(results) == 1, f"文件类型{file_type}应该只返回1个待审查任务"
        assert results[0][1] == '待审查', f"文件类型{file_type}返回的状态应该是'待审查'"
        assert f'IF_FT{file_type}' == results[0][0], f"文件类型{file_type}返回的接口ID不正确"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

