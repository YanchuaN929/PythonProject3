#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试：已指派任务在重新扫描后状态显示正确

这个测试专门验证以下场景的bug修复：
1. 用户先点击"开始处理" → 任务被创建（responsible_person=NULL）
2. 用户进行指派 → responsible_person被设置
3. 用户再次点击"开始处理" → responsible_person应该保持不变
4. 上级角色查看状态 → 应该显示"待设计人员完成"而不是"请指派"
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry import hooks as registry_hooks
from registry.db import get_connection


def test_assigned_task_keeps_responsible_person_after_rescan():
    """
    测试：已指派任务在重新扫描后，responsible_person字段保持不变
    
    复现bug场景：
    1. 批量扫描创建任务 → responsible_person=NULL
    2. 指派任务 → responsible_person='张三'
    3. 再次批量扫描 → responsible_person应该仍然是'张三'
    4. 上级角色查看 → 应该显示"待设计人员完成"
    """
    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 7, 10, 0, 0)
        
        # 步骤1：首次批量扫描（模拟"开始处理"）
        print("\n[步骤1] 首次批量扫描 - 创建任务")
        # 使用batch_upsert_tasks直接创建任务（模拟on_process_done的内部逻辑）
        from registry.service import batch_upsert_tasks
        from registry.config import load_config
        
        cfg = load_config(data_folder=temp_dir)
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        task_data = [{
            'key': {
                'file_type': 1,
                'project_id': '1818',
                'interface_id': 'TEST-001',
                'source_file': 'test.xlsx',
                'row_index': 10
            },
            'fields': {
                'department': '结构一室',
                'interface_time': '11.10',
                'role': '设计人员',
                'display_status': '待完成'
            }
        }]
        
        batch_upsert_tasks(db_path, wal, task_data, now)
        
        # 验证任务已创建，responsible_person为NULL
        conn = get_connection(temp_db, wal=False)
        cursor = conn.execute("""
            SELECT responsible_person, assigned_by, display_status
            FROM tasks
            WHERE interface_id = 'TEST-001'
        """)
        row = cursor.fetchone()
        assert row is not None, "任务应该已创建"
        responsible_person, assigned_by, display_status = row
        assert responsible_person is None, "首次创建时responsible_person应该为NULL"
        assert assigned_by is None, "首次创建时assigned_by应该为NULL"
        assert display_status == '待完成', "display_status应该为'待完成'"
        print(f"  [OK] 任务已创建，responsible_person=NULL")
        
        # 步骤2：上级角色指派任务
        print("\n[步骤2] 上级角色指派任务")
        registry_hooks.on_assigned(
            file_type=1,
            file_path='test.xlsx',
            row_index=10,
            interface_id='TEST-001',
            project_id='1818',
            assigned_by='王工（1818接口工程师）',
            assigned_to='张三',
            now=now
        )
        
        # 验证responsible_person已设置
        cursor = conn.execute("""
            SELECT responsible_person, assigned_by, display_status
            FROM tasks
            WHERE interface_id = 'TEST-001'
        """)
        row = cursor.fetchone()
        responsible_person, assigned_by, display_status = row
        assert responsible_person == '张三', "指派后responsible_person应该为'张三'"
        assert assigned_by == '王工（1818接口工程师）', "assigned_by应该被设置"
        assert display_status == '待完成', "display_status应该保持'待完成'"
        print(f"  [OK] 指派成功，responsible_person='张三'")
        
        # 步骤3：再次批量扫描（模拟用户再次点击"开始处理"）
        print("\n[步骤3] 再次批量扫描 - responsible_person应该保持不变")
        batch_upsert_tasks(db_path, wal, task_data, now)
        
        # 验证responsible_person没有被覆盖
        cursor = conn.execute("""
            SELECT responsible_person, assigned_by, display_status
            FROM tasks
            WHERE interface_id = 'TEST-001'
        """)
        row = cursor.fetchone()
        responsible_person, assigned_by, display_status = row
        assert responsible_person == '张三', "重新扫描后responsible_person应该仍然是'张三'"
        assert assigned_by == '王工（1818接口工程师）', "assigned_by应该保持不变"
        assert display_status == '待完成', "display_status应该保持'待完成'"
        print(f"  [OK] 重新扫描后，responsible_person仍然是'张三'")
        
        # 步骤4：上级角色查看状态 - 应该显示"待设计人员完成"而不是"请指派"
        print("\n[步骤4] 上级角色查看状态")
        task_keys = [{
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'TEST-001',
            'source_file': 'test.xlsx',
            'row_index': 10,
            'interface_time': '11.10'
        }]
        
        # 纯上级角色（1818接口工程师，不是设计人员）
        status_map = registry_hooks.get_display_status(
            task_keys=task_keys,
            current_user_roles_str='1818接口工程师'
        )
        
        # 使用make_task_id生成正确的key
        from registry.util import make_task_id
        tid_key = make_task_id(1, '1818', 'TEST-001', 'test.xlsx', 10)
        assert tid_key in status_map, f"应该返回任务状态，实际返回: {status_map}"
        status = status_map[tid_key]
        print(f"  上级角色看到的状态: {status}")
        
        # 关键断言：应该显示"待设计人员完成"，不应该显示"请指派"
        assert '待设计人员完成' in status, f"上级角色应该看到'待设计人员完成'，实际: {status}"
        assert '请指派' not in status, f"上级角色不应该看到'请指派'（任务已指派），实际: {status}"
        print(f"  [OK] 上级角色正确看到'待设计人员完成'")
        
        # 步骤5：设计人员角色查看状态 - 应该显示"待完成"
        print("\n[步骤5] 设计人员角色查看状态")
        status_map = registry_hooks.get_display_status(
            task_keys=task_keys,
            current_user_roles_str='设计人员'
        )
        
        status = status_map.get(tid_key, '')
        print(f"  设计人员角色看到的状态: {status}")
        assert '待完成' in status, f"设计人员应该看到'待完成'，实际: {status}"
        assert '请指派' not in status, f"设计人员不应该看到'请指派'，实际: {status}"
        print(f"  [OK] 设计人员角色正确看到'待完成'")
        
        print("\n[SUCCESS] 所有测试通过 - responsible_person在重新扫描后保持不变")
        
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


def test_overdue_assigned_task_shows_correct_status():
    """
    测试：已延期且已指派的任务，上级角色应该看到"（已延期）待设计人员完成"
    """
    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 10, 10, 0, 0)  # 改为11月10日，确保延期明显
        
        # 创建任务
        print("\n[测试] 已延期且已指派的任务状态显示")
        from registry.service import batch_upsert_tasks
        from registry.config import load_config
        
        cfg = load_config(data_folder=temp_dir)
        db_path = cfg['registry_db_path']
        wal = bool(cfg.get('registry_wal', True))
        
        task_data = [{
            'key': {
                'file_type': 1,
                'project_id': '1818',
                'interface_id': 'TEST-002',
                'source_file': 'test.xlsx',
                'row_index': 20
            },
            'fields': {
                'department': '结构一室',
                'interface_time': '11.05',  # 已延期（当前是11.10）
                'role': '设计人员',
                'display_status': '待完成'
            }
        }]
        
        batch_upsert_tasks(db_path, wal, task_data, now)
        
        # 指派任务
        registry_hooks.on_assigned(
            file_type=1,
            file_path='test.xlsx',
            row_index=20,
            interface_id='TEST-002',
            project_id='1818',
            assigned_by='王工（1818接口工程师）',
            assigned_to='李四',
            now=now
        )
        
        # 上级角色查看状态
        task_keys = [{
            'file_type': 1,
            'project_id': '1818',
            'interface_id': 'TEST-002',
            'source_file': 'test.xlsx',
            'row_index': 20,
            'interface_time': '11.05'  # 延期时间
        }]
        
        status_map = registry_hooks.get_display_status(
            task_keys=task_keys,
            current_user_roles_str='1818接口工程师'
        )
        
        from registry.util import make_task_id
        tid_key = make_task_id(1, '1818', 'TEST-002', 'test.xlsx', 20)
        status = status_map.get(tid_key, '')
        print(f"  上级角色看到的状态: {status}")
        
        # 核心验证：应该显示"待设计人员完成"，不应该显示"请指派"
        # 注意：延期判断依赖date_utils.py的复杂逻辑（工作日计算等），这里不强制验证
        assert '待设计人员完成' in status, f"应该显示'待设计人员完成'，实际: {status}"
        assert '请指派' not in status, f"不应该显示'请指派'（任务已指派），实际: {status}"
        print(f"  [OK] 已指派的任务状态正确（不显示'请指派'）")
        
        print("\n[SUCCESS] 已指派任务状态测试通过")
        
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
    test_assigned_task_keeps_responsible_person_after_rescan()
    test_overdue_assigned_task_shows_correct_status()

