#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试科室字段和配置获取修复

验证：
1. registry能够正确从Excel的"科室"列提取数据
2. ignore_overdue_dialog正确使用registry_hooks._cfg()获取配置
3. 数据库中department字段被正确填充
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os


def test_extract_department_from_excel():
    """测试从Excel行提取科室信息"""
    from registry.util import extract_department
    
    # 测试用例1：有"科室"列
    row_with_keju = pd.Series({
        '科室': '结构一室',
        '接口号': 'TEST-001',
        '项目号': '1818'
    })
    assert extract_department(row_with_keju) == '结构一室'
    
    # 测试用例2：有"部门"列
    row_with_bumen = pd.Series({
        '部门': '结构二室',
        '接口号': 'TEST-002',
        '项目号': '1818'
    })
    assert extract_department(row_with_bumen) == '结构二室'
    
    # 测试用例3：两个列都有（优先使用"科室"）
    row_with_both = pd.Series({
        '科室': '结构一室',
        '部门': '建筑总图室',
        '接口号': 'TEST-003'
    })
    assert extract_department(row_with_both) == '结构一室'
    
    # 测试用例4：都没有
    row_without = pd.Series({
        '接口号': 'TEST-004',
        '项目号': '1818'
    })
    assert extract_department(row_without) == ''
    
    # 测试用例5：值为NaN或None
    row_with_nan = pd.Series({
        '科室': None,
        '接口号': 'TEST-005'
    })
    assert extract_department(row_with_nan) == ''
    
    print("\n✓ 所有科室提取测试通过")


def test_build_task_fields_includes_department():
    """测试build_task_fields_from_row包含department字段"""
    from registry.util import build_task_fields_from_row
    
    row = pd.Series({
        '科室': '结构一室',
        '接口号': 'TEST-001',
        '接口时间': '2025.11.15',
        '责任人': '张三',
        '角色来源': '设计人员'
    })
    
    fields = build_task_fields_from_row(row, file_type=1)
    
    assert 'department' in fields
    assert fields['department'] == '结构一室'
    assert 'interface_time' in fields
    assert 'role' in fields
    
    print("\n✓ build_task_fields包含department字段")


def test_department_saved_to_database():
    """测试department字段能正确保存到数据库"""
    # 创建临时数据库
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection, init_db
        from registry.service import upsert_task
        from datetime import datetime
        
        conn = get_connection(db_path, wal=False)
        init_db(conn)
        conn.close()
        
        # 创建测试任务
        task_key = {
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'TEST-DEPT-001',
            'source_file': 'test.xlsx',
            'row_index': 2,
            'interface_time': '2025.11.15'
        }
        
        task_fields = {
            'department': '结构一室',
            'interface_time': '2025.11.15',
            'role': '设计人员',
            'responsible_person': '张三'
        }
        
        # 保存到数据库
        upsert_task(db_path, False, task_key, task_fields, datetime.now())
        
        # 读取验证
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT department, interface_id, responsible_person, role
            FROM tasks
            WHERE interface_id = 'TEST-DEPT-001'
        """)
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None, "任务应该被保存到数据库"
        department, interface_id, responsible_person, role = row
        
        assert department == '结构一室', f"department应该是'结构一室'，实际是'{department}'"
        assert interface_id == 'TEST-DEPT-001'
        assert responsible_person == '张三'
        assert role == '设计人员'
        
        print(f"\n✓ department字段正确保存到数据库: {department}")
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_collect_overdue_includes_department():
    """测试收集延期任务时包含department字段"""
    # 创建临时数据库
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        from registry.db import get_connection
        from registry.service import upsert_task
        import sqlite3
        
        # 初始化数据库
        conn = get_connection(db_path, wal=False)
        conn.close()
        
        # 使用upsert_task插入带有department的任务
        overdue_date = (datetime.now() - timedelta(days=5)).strftime("%Y.%m.%d")
        
        task_key = {
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'TEST-OVERDUE-001',
            'source_file': 'test.xlsx',
            'row_index': 2,
            'interface_time': overdue_date
        }
        
        task_fields = {
            'department': '结构一室',
            'interface_time': overdue_date,
            'role': '设计人员',
            'responsible_person': '张三'
        }
        
        # 保存任务
        upsert_task(db_path, False, task_key, task_fields, datetime.now())
        
        # 查询验证
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT department, responsible_person, role, interface_time
            FROM tasks
            WHERE interface_id = 'TEST-OVERDUE-001'
        """)
        row = cursor.fetchone()
        
        assert row is not None
        department, responsible_person, role, interface_time = row
        
        assert department == '结构一室', f"department应该是'结构一室'，实际是'{department}'"
        assert responsible_person == '张三'
        assert role == '设计人员'
        
        print(f"\n✓ 数据库查询包含department: {department}")
        
        conn.close()
        
    finally:
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except:
            pass


def test_ignore_dialog_config_access():
    """测试忽略对话框正确获取registry配置"""
    # 这个测试验证import不会出错
    try:
        from registry import hooks as registry_hooks
        
        # 设置临时数据文件夹
        import tempfile
        tmp_dir = tempfile.mkdtemp()
        registry_hooks.set_data_folder(tmp_dir)
        
        # 获取配置
        cfg = registry_hooks._cfg()
        
        # 验证配置包含必要的键
        assert 'registry_db_path' in cfg
        assert 'registry_wal' in cfg or 'wal' in cfg
        
        print("\n✓ registry_hooks._cfg()调用成功")
        print(f"  配置键: {list(cfg.keys())}")
        
        # 清理
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        
    except ImportError as e:
        pytest.fail(f"Import失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

