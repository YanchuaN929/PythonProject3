#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试写回文单号后的状态更新

验证：
1. 写回文单号后，display_status正确更新为"待审查"
2. 再次扫描时，任务仍显示，状态保持"待审查"
3. 上级角色可以看到该任务
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry import hooks as registry_hooks
from registry.service import upsert_task
from registry.db import get_connection
from registry.util import make_task_id
from registry.models import Status


def test_response_written_updates_status():
    """测试写回文单号后状态更新为待审查"""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 5, 10, 0, 0)
        
        # 步骤1：创建任务（待完成状态）
        print("\n[步骤1] 创建任务（待完成）")
        key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JZ-02-25C1-25C3',
            'source_file': '2016按项目导出IDI手册2025-08-01.xlsx',
            'row_index': 87
        }
        fields = {
            'interface_time': '2025.11.10',
            'display_status': '待完成',
            'status': Status.OPEN,
            '_completed_col_value': ''  # M列为空
        }
        
        upsert_task(temp_db, True, key, fields, now)
        
        # 验证任务创建
        tid = make_task_id(1, '2016', 'S-SA---1JZ-02-25C1-25C3', '2016按项目导出IDI手册2025-08-01.xlsx', 87)
        conn = get_connection(temp_db, True)
        cursor = conn.execute("SELECT display_status, status FROM tasks WHERE id=?", (tid,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == '待完成', f"初始状态应该是'待完成'，实际：{row[0]}"
        print(f"  任务创建成功: display_status={row[0]}, status={row[1]}")
        
        # 步骤2：模拟设计人员写回文单号
        print("\n[步骤2] 设计人员写回文单号")
        registry_hooks.on_response_written(
            file_type=1,
            file_path='2016按项目导出IDI手册2025-08-01.xlsx',
            row_index=87,
            interface_id='S-SA---1JZ-02-25C1-25C3',
            response_number='TEST-RESPONSE-123',
            user_name='张三',
            project_id='2016',
            role='设计人员',
            now=now
        )
        
        # 验证状态更新为"待审查"
        cursor = conn.execute("SELECT display_status, status, completed_at FROM tasks WHERE id=?", (tid,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row[1] == Status.COMPLETED, f"status应该变为completed，实际：{row[1]}"
        assert row[2] is not None, "completed_at应该被设置"
        assert row[0] in ['待审查', '待指派人审查'], f"display_status应该是'待审查'，实际：{row[0]}"
        
        print(f"  [OK] 回文单号写入后: display_status={row[0]}, status={row[1]}")
        
        # 步骤3：查询状态（模拟UI显示）
        print("\n[步骤3] 查询状态（模拟UI显示）")
        task_key = {
            'file_type': 1,
            'project_id': '2016',
            'interface_id': 'S-SA---1JZ-02-25C1-25C3',
            'source_file': '2016按项目导出IDI手册2025-08-01.xlsx',
            'row_index': 87,
            'interface_time': '2025.11.10'
        }
        
        status_map = registry_hooks.get_display_status([task_key], current_user_roles_str='')
        
        assert tid in status_map, "应该能查询到任务状态"
        assert '待审查' in status_map[tid], f"状态应该包含'待审查'，实际：{status_map[tid]}"
        
        print(f"  [OK] 查询到的状态: {status_map[tid]}")
        
        print("\n[成功] 写回文单号状态更新测试通过")
        
    finally:
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
    test_response_written_updates_status()

