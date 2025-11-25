#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Registry模块端到端测试"""
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_full_flow():
    """测试完整的Registry流程：初始化 -> 写入任务 -> 查询"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_registry.db')
    
    try:
        print("=" * 50)
        print("Registry端到端测试")
        print("=" * 50)
        
        # Step 1: 初始化数据库
        print("\n[Step 1] 初始化数据库...")
        from registry.db import get_connection, close_connection
        conn = get_connection(db_path, wal=True)
        
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        assert len(cursor.fetchall()) > 0, "tasks表未创建"
        print("  ✓ 数据库初始化成功，tasks表已创建")
        
        close_connection()
        
        # Step 2: 使用batch_upsert_tasks写入任务
        print("\n[Step 2] 测试batch_upsert_tasks...")
        from registry.service import batch_upsert_tasks
        from datetime import datetime
        
        tasks_data = [
            {
                'key': {
                    'file_type': 1,
                    'project_id': '1818',
                    'interface_id': f'S-TEST-{i:03d}',
                    'source_file': 'test_file.xlsx',
                    'row_index': 100 + i
                },
                'fields': {
                    'department': '结构室',
                    'interface_time': '2025.01.15',
                    'role': '设计人员',
                    'display_status': '待完成',
                    'status': 'open'
                }
            }
            for i in range(12)  # 模拟12个任务
        ]
        
        count = batch_upsert_tasks(db_path, True, tasks_data, datetime.now())
        print(f"  batch_upsert_tasks返回: {count}")
        assert count == 12, f"期望插入12个任务，实际插入{count}个"
        print("  ✓ batch_upsert_tasks成功插入12个任务")
        
        # Step 3: 验证数据库内容
        print("\n[Step 3] 验证数据库内容...")
        conn = get_connection(db_path, True)
        
        cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE file_type = 1 AND project_id = '1818'")
        total = cursor.fetchone()[0]
        assert total == 12, f"期望12个任务，实际{total}个"
        print(f"  ✓ 数据库中有{total}个任务")
        
        cursor = conn.execute("SELECT interface_id, display_status FROM tasks ORDER BY interface_id LIMIT 3")
        rows = cursor.fetchall()
        print("  前3个任务:")
        for row in rows:
            print(f"    - {row[0]}: {row[1]}")
        
        # Step 4: 测试更新（upsert逻辑）
        print("\n[Step 4] 测试更新逻辑...")
        tasks_data[0]['fields']['display_status'] = '待审查'
        count = batch_upsert_tasks(db_path, True, [tasks_data[0]], datetime.now())
        assert count == 1, "更新失败"
        
        cursor = conn.execute("SELECT display_status FROM tasks WHERE interface_id = 'S-TEST-000'")
        status = cursor.fetchone()[0]
        assert status == '待审查', f"期望'待审查'，实际'{status}'"
        print("  ✓ 更新逻辑正常工作")
        
        close_connection()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            close_connection()
        except:
            pass
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == '__main__':
    success = test_full_flow()
    sys.exit(0 if success else 1)

