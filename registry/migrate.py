#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registry数据库迁移脚本

用于将旧数据库升级到新版本（添加display_status等字段）
"""
import sqlite3
import os


def check_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """检查列是否存在"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_database(db_path: str) -> None:
    """
    迁移数据库到最新版本
    
    添加新字段：
    - assigned_by
    - assigned_at
    - display_status
    - confirmed_by
    - responsible_person
    - business_id（接口号继承功能）
    - response_number（回文单号记录）
    """
    if not os.path.exists(db_path):
        print("[Migrate] Database not found, skip")
        return
    
    print("[Migrate] Checking database...")
    
    conn = sqlite3.connect(db_path)
    
    try:
        # 检查并添加新字段
        new_columns = [
            ("assigned_by", "TEXT DEFAULT NULL"),
            ("assigned_at", "TEXT DEFAULT NULL"),
            ("display_status", "TEXT DEFAULT NULL"),
            ("confirmed_by", "TEXT DEFAULT NULL"),
            ("responsible_person", "TEXT DEFAULT NULL"),
            ("business_id", "TEXT DEFAULT NULL"),
            ("response_number", "TEXT DEFAULT NULL")
        ]
        
        added_count = 0
        for col_name, col_def in new_columns:
            if not check_column_exists(conn, "tasks", col_name):
                try:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    print(f"  [OK] Added column: {col_name}")
                    added_count += 1
                except Exception as e:
                    print(f"  [FAIL] Failed to add {col_name}: {e}")
            else:
                print(f"  [SKIP] Column exists: {col_name}")
        
        if added_count > 0:
            print(f"[Migrate] Done! Added {added_count} columns")
            
            # 【新增】为现有任务填充business_id
            cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE business_id IS NULL")
            null_count = cursor.fetchone()[0]
            
            if null_count > 0:
                print(f"[Migrate] 填充{null_count}个任务的business_id...")
                conn.execute("""
                    UPDATE tasks 
                    SET business_id = file_type || '|' || project_id || '|' || interface_id
                    WHERE business_id IS NULL
                """)
                conn.commit()
                print(f"[Migrate] ✓ business_id填充完成")
        else:
            print("[Migrate] Database is up-to-date")
            
    except Exception as e:
        print(f"[Migrate] Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


def migrate_if_needed(db_path: str) -> None:
    """
    智能迁移：检查是否需要迁移
    
    参数:
        db_path: 数据库路径
    """
    if not os.path.exists(db_path):
        # 数据库不存在，会自动创建最新版本，无需迁移
        return
    
    conn = sqlite3.connect(db_path)
    try:
        # 检查是否缺少新字段（需要检查所有关键字段）
        missing_fields = []
        required_fields = ["display_status", "business_id", "response_number"]
        
        for field in required_fields:
            if not check_column_exists(conn, "tasks", field):
                missing_fields.append(field)
        
        if missing_fields:
            print(f"[Registry] 检测到数据库缺少字段: {', '.join(missing_fields)}，开始自动迁移...")
            conn.close()
            migrate_database(db_path)
        # else: 版本检查通过，不输出（避免频繁日志）
    except Exception as e:
        print(f"[Registry] 版本检查失败: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python migrate.py <数据库路径>")
        print("示例: python migrate.py result_cache/registry.db")
        sys.exit(1)
    
    db_path = sys.argv[1]
    migrate_database(db_path)

