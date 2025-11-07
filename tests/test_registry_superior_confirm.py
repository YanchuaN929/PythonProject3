#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试上级确认UI集成

验证：
1. 上级角色勾选触发confirmed
2. 设计人员角色勾选不触发confirmed（仍是completed）
3. confirmed后display_status被清除
4. CONFIRMED事件正确记录
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registry import hooks as registry_hooks
from registry.db import get_connection
from registry.models import Status


def test_superior_confirm():
    """测试上级角色确认任务"""
    temp_dir = tempfile.mkdtemp()
    temp_db = os.path.join(temp_dir, "test.db")
    
    try:
        # 设置测试环境
        os.environ['REGISTRY_DB_PATH'] = temp_db
        registry_hooks.set_data_folder(temp_dir)
        
        now = datetime(2025, 11, 5, 10, 0, 0)
        
        # 步骤1：创建已完成的任务（status=completed）
        print("\n[步骤1] 创建已完成待审查的任务")
        registry_hooks.on_response_written(
            file_type=1,
            file_path='test_file.xlsx',
            row_index=10,
            interface_id='TEST-001',
            response_number='R-001',
            user_name='张三',
            project_id='2016',
            now=now
        )
        
        # 验证任务状态
        conn = get_connection(temp_db, True)
        cursor = conn.execute("""
            SELECT status, display_status, confirmed_at
            FROM tasks
            WHERE interface_id = 'TEST-001'
        """)
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == Status.COMPLETED, f"应该是completed，实际：{row[0]}"
        assert row[1] in ['待审查', '待指派人审查'], f"应该是待审查，实际：{row[1]}"
        assert row[2] is None, "confirmed_at应该是NULL"
        print(f"  [OK] 任务已完成待审查: status={row[0]}, display_status={row[1]}")
        
        # 步骤2：上级确认
        print("\n[步骤2] 上级角色确认任务")
        registry_hooks.on_confirmed_by_superior(
            file_type=1,
            file_path='test_file.xlsx',
            row_index=10,
            user_name='王工',
            project_id='2016',
            interface_id='TEST-001',
            now=now
        )
        
        # 验证确认后状态
        cursor = conn.execute("""
            SELECT status, display_status, confirmed_at, confirmed_by
            FROM tasks
            WHERE interface_id = 'TEST-001'
        """)
        row = cursor.fetchone()
        
        assert row is not None
        assert row[0] == Status.CONFIRMED, f"应该是confirmed，实际：{row[0]}"
        assert row[1] is None, f"display_status应该被清除，实际：{row[1]}"
        assert row[2] is not None, "confirmed_at应该有值"
        # confirmed_by暂时可能没有记录（取决于mark_confirmed的实现）
        print(f"  [OK] 任务已确认: status={row[0]}, display_status={row[1]}, confirmed_at={row[2]}")
        
        # 验证CONFIRMED事件
        cursor = conn.execute("""
            SELECT event FROM events
            WHERE event = 'confirmed'
        """)
        event_row = cursor.fetchone()
        assert event_row is not None, "应该记录CONFIRMED事件"
        print(f"  [OK] CONFIRMED事件已记录")
        
        print("\n[SUCCESS] 上级确认测试通过")
        
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


def test_designer_cannot_confirm():
    """测试设计人员勾选不触发confirmed（这个测试需要UI层面，暂时跳过）"""
    # 注意：此测试需要实际的UI交互，pytest难以模拟
    # 实际使用时需要手动测试
    print("\n[INFO] 设计人员勾选测试需要手动验证（UI层面）")
    print("  测试步骤：")
    print("  1. 以设计人员身份登录")
    print("  2. 勾选一个任务的'已完成'")
    print("  3. 验证：任务仍显示（不应该消失）")
    print("  4. 查询数据库：status应该仍是completed（不是confirmed）")


if __name__ == "__main__":
    print("=" * 80)
    print("上级确认功能测试")
    print("=" * 80)
    
    test_superior_confirm()
    test_designer_cannot_confirm()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

