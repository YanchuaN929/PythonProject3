#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Registry接口号继承功能

验证：
1. business_id正确生成
2. 状态继承（时间列和完成列都未变化）
3. 状态重置（时间列或完成列变化）
4. 指派信息保留
5. 6种文件类型全覆盖
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime
import pandas as pd

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry import hooks as registry_hooks
from registry.util import make_business_id, make_task_id, build_task_key_from_row, build_task_fields_from_row
from registry.service import find_task_by_business_id, should_reset_task_status, upsert_task
from registry.db import get_connection
from registry.models import Status


def test_make_business_id():
    """测试business_id生成"""
    business_id = make_business_id(1, '2016', 'S-SA---1JT-01-25C1-25E6')
    
    assert business_id == '1|2016|S-SA---1JT-01-25C1-25E6'
    print(f"[OK] business_id生成正确: {business_id}")


def test_should_reset_task_status():
    """测试状态重置判断逻辑"""
    
    # 场景1：时间列变化 → 需要重置
    result = should_reset_task_status('11.06', '12.30', '', '')
    assert result == True, "时间列变化应该重置状态"
    print("[OK] 时间列变化 -> 重置状态")
    
    # 场景2：完成列从有值变为空 → 需要重置
    result = should_reset_task_status('11.06', '11.06', '有值', '')
    assert result == True, "完成列从有值变为空应该重置状态"
    print("[OK] 完成列从有值变为空 -> 重置状态")
    
    # 场景3：完成列从空变为有值 → 不重置
    result = should_reset_task_status('11.06', '11.06', '', '有值')
    assert result == False, "完成列从空变为有值不应该重置"
    print("[OK] 完成列从空变为有值 -> 不重置")
    
    # 场景4：都不变 → 不重置
    result = should_reset_task_status('11.06', '11.06', '', '')
    assert result == False, "都不变不应该重置"
    print("[OK] 都不变 -> 不重置")


def test_state_inheritance():
    """测试状态继承（文件名变化，接口号相同）"""
    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 5, 10, 0, 0)
        
        # 步骤1：创建旧任务（旧文件名）
        print("\n[步骤1] 创建旧任务（旧文件）")
        old_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JT-01-25C1-25E6',
            'source_file': '2016按项目导出IDI手册2025-08-01.xlsx',
            'row_index': 89
        }
        old_fields = {
            'department': '结构一室',
            'interface_time': '2025.11.06',
            'role': '设计人员',
            'display_status': '待审查',
            'status': Status.COMPLETED,
            'completed_at': '2025-11-05T10:00:00',
            'responsible_person': '张三',
            '_completed_col_value': '2025-11-05'  # M列有值
        }
        
        upsert_task(temp_db, True, old_key, old_fields, now)
        print(f"  旧任务已创建: business_id={make_business_id(1, '2016', 'S-SA---1JT-01-25C1-25E6')}")
        
        # 验证旧任务
        old_task = find_task_by_business_id(temp_db, True, 1, '2016', 'S-SA---1JT-01-25C1-25E6')
        assert old_task is not None, "旧任务应该存在"
        assert old_task['display_status'] == '待审查', f"旧任务状态应该是'待审查'，实际：{old_task['display_status']}"
        print(f"  [OK] 旧任务状态: {old_task['display_status']}")
        
        # 步骤2：创建新任务（新文件名，接口号相同，时间列和完成列都不变）
        print("\n[步骤2] 创建新任务（新文件，接口号相同，时间不变）")
        new_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JT-01-25C1-25E6',  # 接口号相同
            'source_file': '2016按项目导出IDI手册2025-08-08.xlsx',  # 文件名不同
            'row_index': 92  # 行号可能不同
        }
        new_fields = {
            'department': '结构一室',
            'interface_time': '2025.11.06',  # 时间列未变化
            'role': '设计人员',
            'display_status': '待完成',  # 新扫描默认是待完成
            '_completed_col_value': '2025-11-05'  # M列有值，未变化
        }
        
        upsert_task(temp_db, True, new_key, new_fields, now)
        
        # 验证新任务继承了旧状态
        new_task_id = make_task_id(1, '2016', 'S-SA---1JT-01-25C1-25E6', '2016按项目导出IDI手册2025-08-08.xlsx', 92)
        conn = get_connection(temp_db, True)
        cursor = conn.execute("SELECT status, display_status, completed_at, responsible_person FROM tasks WHERE id = ?", (new_task_id,))
        row = cursor.fetchone()
        
        assert row is not None, "新任务应该存在"
        assert row[0] == Status.COMPLETED, f"应该继承status=completed，实际：{row[0]}"
        assert row[1] == '待审查', f"应该继承display_status=待审查，实际：{row[1]}"
        assert row[2] is not None, "应该继承completed_at"
        assert row[3] == '张三', f"应该继承责任人，实际：{row[3]}"
        
        print(f"  [OK] 新任务继承了旧状态: status={row[0]}, display_status={row[1]}")
        print(f"  [OK] 新任务继承了指派信息: responsible_person={row[3]}")
        
        print("\n[成功] 状态继承测试通过")
        
    finally:
        # 清理
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


def test_state_reset():
    """测试状态重置（时间列变化）"""
    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 5, 10, 0, 0)
        
        # 步骤1：创建旧任务
        print("\n[步骤1] 创建旧任务（已完成待审查）")
        old_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-001',
            'source_file': 'old_file.xlsx',
            'row_index': 10
        }
        old_fields = {
            'interface_time': '2025.11.06',
            'display_status': '待审查',
            'status': Status.COMPLETED,
            'completed_at': '2025-11-05T10:00:00',
            'responsible_person': '李四',
            'assigned_by': '王工',
            'assigned_at': '2025-11-01T09:00:00',
            '_completed_col_value': '2025-11-05'
        }
        
        upsert_task(temp_db, True, old_key, old_fields, now)
        print("  旧任务已创建，状态：待审查，责任人：李四")
        
        # 步骤2：创建新任务（时间列变化）
        print("\n[步骤2] 创建新任务（时间列变化）")
        new_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-001',  # 接口号相同
            'source_file': 'new_file.xlsx',  # 新文件
            'row_index': 15
        }
        new_fields = {
            'interface_time': '2025.12.30',  # 时间列变化！
            'display_status': '待完成',
            '_completed_col_value': ''  # M列为空
        }
        
        upsert_task(temp_db, True, new_key, new_fields, now)
        
        # 验证新任务状态被重置
        new_task_id = make_task_id(1, '2016', 'TEST-001', 'new_file.xlsx', 15)
        conn = get_connection(temp_db, True)
        cursor = conn.execute("""
            SELECT status, display_status, completed_at, responsible_person, assigned_by
            FROM tasks WHERE id = ?
        """, (new_task_id,))
        row = cursor.fetchone()
        
        assert row is not None, "新任务应该存在"
        assert row[0] == Status.OPEN, f"应该重置status=open，实际：{row[0]}"
        assert row[1] == '待完成', f"应该重置display_status=待完成，实际：{row[1]}"
        assert row[2] is None, "应该重置completed_at=NULL"
        assert row[3] == '李四', f"应该保留责任人，实际：{row[3]}"
        assert row[4] == '王工', f"应该保留assigned_by，实际：{row[4]}"
        
        print(f"  [OK] 新任务状态已重置: status={row[0]}, display_status={row[1]}")
        print(f"  [OK] 新任务保留了指派信息: responsible_person={row[3]}, assigned_by={row[4]}")
        
        print("\n[成功] 状态重置测试通过")
        
    finally:
        # 清理
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


def test_new_interface_creation():
    """测试新接口创建（数据库中不存在该接口）"""
    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 5, 10, 0, 0)
        
        # 创建新接口任务（数据库中不存在）
        print("\n[测试] 创建全新接口")
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'NEW-INTERFACE-001',  # 新接口号
            'source_file': 'test_file.xlsx',
            'row_index': 20
        }
        fields = {
            'interface_time': '2025.11.20',
            'display_status': '待完成',
            '_completed_col_value': ''
        }
        
        upsert_task(temp_db, True, key, fields, now)
        
        # 验证新任务创建成功
        task_id = make_task_id(1, '2016', 'NEW-INTERFACE-001', 'test_file.xlsx', 20)
        conn = get_connection(temp_db, True)
        cursor = conn.execute("""
            SELECT status, display_status, business_id
            FROM tasks WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()
        
        assert row is not None, "新接口应该被创建"
        assert row[0] == Status.OPEN, "新接口status应该是open"
        assert row[1] == '待完成', "新接口display_status应该是待完成"
        assert row[2] == '1|2016|NEW-INTERFACE-001', "business_id应该正确"
        
        print(f"  [OK] 新接口创建成功: business_id={row[2]}")
        print(f"  [OK] 新接口状态正确: status={row[0]}, display_status={row[1]}")
        
        print("\n[成功] 新接口创建测试通过")
        
    finally:
        # 清理
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


def test_file_type_2_completed_column():
    """测试文件类型2的完成列提取（N列）"""
    from registry.util import extract_completed_column_value
    
    # 创建测试行（模拟Excel数据）
    data = [None] * 20  # 创建20列
    data[13] = '2025-11-05'  # N列（索引13）
    df_row = pd.Series(data)
    
    val = extract_completed_column_value(df_row, 2)
    
    assert val == '2025-11-05', f"文件类型2应该提取N列，实际：{val}"
    print(f"[OK] 文件类型2完成列提取正确: {val}")


def test_file_type_3_completed_column():
    """测试文件类型3的完成列提取（Q列或T列）"""
    from registry.util import extract_completed_column_value
    
    # 测试Q列有值
    data_q = [None] * 25
    data_q[16] = '2025-11-05'  # Q列（索引16）
    df_row_q = pd.Series(data_q)
    val = extract_completed_column_value(df_row_q, 3)
    assert val == '2025-11-05', "文件类型3应该提取Q列"
    print(f"[OK] 文件类型3完成列提取（Q列）: {val}")
    
    # 测试T列有值，Q列无值
    data_t = [None] * 25
    data_t[19] = '2025-11-06'  # T列（索引19）
    df_row_t = pd.Series(data_t)
    val = extract_completed_column_value(df_row_t, 3)
    assert val == '2025-11-06', "文件类型3应该提取T列"
    print(f"[OK] 文件类型3完成列提取（T列）: {val}")


def test_assigned_info_preserved_on_reset():
    """测试状态重置时指派信息保留"""
    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 5, 10, 0, 0)
        
        # 步骤1：创建已指派且已完成的任务
        print("\n[步骤1] 创建已指派且已完成的任务")
        old_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-002',
            'source_file': 'old_file.xlsx',
            'row_index': 50
        }
        old_fields = {
            'interface_time': '2025.10.15',
            'display_status': '待审查',
            'status': Status.COMPLETED,
            'completed_at': '2025-10-20T10:00:00',
            'responsible_person': '张三',
            'assigned_by': '王工（2016接口工程师）',
            'assigned_at': '2025-10-10T09:00:00',
            '_completed_col_value': '2025-10-20'
        }
        
        upsert_task(temp_db, True, old_key, old_fields, now)
        print("  旧任务: 已指派给张三，已完成，状态待审查")
        
        # 步骤2：时间列变化（收到新信息单）
        print("\n[步骤2] 时间列变化（收到新信息单），状态应重置")
        new_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'TEST-002',
            'source_file': 'new_file.xlsx',
            'row_index': 55
        }
        new_fields = {
            'interface_time': '2025.11.30',  # 时间变化！
            'display_status': '待完成',
            '_completed_col_value': ''  # M列为空
        }
        
        upsert_task(temp_db, True, new_key, new_fields, now)
        
        # 验证：状态重置，但指派信息保留
        new_task_id = make_task_id(1, '2016', 'TEST-002', 'new_file.xlsx', 55)
        conn = get_connection(temp_db, True)
        cursor = conn.execute("""
            SELECT status, display_status, completed_at, 
                   responsible_person, assigned_by, assigned_at
            FROM tasks WHERE id = ?
        """, (new_task_id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == Status.OPEN, f"状态应该重置为open，实际：{row[0]}"
        assert row[1] == '待完成', f"显示状态应该重置为待完成，实际：{row[1]}"
        assert row[2] is None, "completed_at应该被清空"
        assert row[3] == '张三', f"责任人应该保留，实际：{row[3]}"
        assert row[4] == '王工（2016接口工程师）', f"assigned_by应该保留，实际：{row[4]}"
        assert row[5] is not None, "assigned_at应该保留"
        
        print(f"  [OK] 状态已重置: status={row[0]}, display_status={row[1]}")
        print(f"  [OK] 指派信息已保留: responsible_person={row[3]}, assigned_by={row[4]}")
        
        print("\n[成功] 状态重置+指派信息保留测试通过")
        
    finally:
        # 清理
        if 'REGISTRY_DB_PATH' in os.environ:
            del os.environ['REGISTRY_DB_PATH']
        if os.path.exists(temp_dir):
            try:
                from registry.db import close_connection
                close_connection()
                import time
                time.sleep(0.1)
                shutil.rmtree(temp_dir)
            except:
                pass


if __name__ == "__main__":
    print("=" * 80)
    print("Registry接口号继承功能测试")
    print("=" * 80)
    
    test_make_business_id()
    test_should_reset_task_status()
    test_file_type_2_completed_column()
    test_file_type_3_completed_column()
    test_state_inheritance()
    test_state_reset()
    test_new_interface_creation()
    test_assigned_info_preserved_on_reset()
    
    print("\n" + "=" * 80)
    print("所有测试通过！[SUCCESS]")
    print("=" * 80)

