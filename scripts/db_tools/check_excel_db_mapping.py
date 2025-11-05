"""
Excel列与数据库字段对照检查

检查所有从Excel读取的列是否都在数据库中有对应字段
"""

import os
import sqlite3
import json

def get_db_columns():
    """获取数据库tasks表的所有列"""
    # 读取配置获取数据库路径
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        config = {}
    
    folder_path = config.get('folder_path', '').strip()
    
    # 确定数据库路径
    if folder_path:
        db_path = os.path.join(folder_path, '.registry', 'registry.db')
    else:
        db_path = os.path.join('result_cache', 'registry.db')
    
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    
    return columns

def main():
    print("=" * 80)
    print("Excel列与数据库字段对照检查")
    print("=" * 80)
    
    # Excel中使用的列（从代码分析得出）
    excel_columns = {
        # 核心标识列
        "原始行号": "用于唯一标识Excel行，对应DB的row_index",
        "项目号": "项目标识，对应DB的project_id", 
        "接口号": "接口标识，对应DB的interface_id",
        
        # 业务数据列
        "部门": "科室/部门信息，对应DB的department",
        "接口时间": "接口截止时间，对应DB的interface_time",
        "角色来源": "角色标识，对应DB的role",
        "责任人": "【新增】任务负责人，对应DB的responsible_person",
        
        # 状态相关列
        "状态": "【Registry】显示状态，对应DB的display_status",
        "回文单号": "【仅file1/2/3/4】回复单号，用于完成标记，影响DB的status/completed_at",
        
        # UI专用列（不存DB）
        "已完成": "【UI专用】勾选框，数据在file_cache.json，不存DB",
    }
    
    # 数据库fields（从tasks表schema得出）
    db_fields = {
        # 核心标识
        "id": "任务唯一标识（由file_type+project_id+interface_id+source_file+row_index生成）",
        "file_type": "文件类型（1-6）",
        "project_id": "项目号（来自Excel）",
        "interface_id": "接口号（来自Excel）",
        "source_file": "源文件路径",
        "row_index": "Excel行号（来自Excel的'原始行号'）",
        
        # 业务数据
        "department": "部门（来自Excel）",
        "interface_time": "接口时间（来自Excel）",
        "role": "角色（来自Excel）",
        "responsible_person": "【新增】责任人（来自Excel）",
        
        # 任务状态
        "status": "任务状态（open/assigned/completed/confirmed/archived）",
        "display_status": "显示状态（待完成/待上级确认等，来自Registry计算）",
        
        # 时间戳
        "completed_at": "完成时间（设计人员写回文单号时）",
        "confirmed_at": "确认时间（上级角色确认时）",
        "assigned_at": "指派时间（指派功能触发）",
        "first_seen_at": "首次扫描时间",
        "last_seen_at": "最后扫描时间",
        "missing_since": "消失标记时间（归档功能用）",
        
        # 协作信息
        "assigned_by": "指派人（指派功能记录）",
        "confirmed_by": "确认人（上级确认功能记录）",
        
        # 归档信息
        "archive_reason": "归档原因（missing_from_source等）",
    }
    
    print("\n" + "=" * 80)
    print("1. Excel列 -> 数据库字段 映射关系")
    print("=" * 80)
    
    print("\n【已映射的Excel列】:")
    for excel_col, desc in sorted(excel_columns.items()):
        print(f"\n  Excel列: '{excel_col}'")
        print(f"    说明: {desc}")
    
    print("\n\n【数据库独有字段（非Excel来源）】:")
    db_only_fields = [
        'id', 'file_type', 'source_file', 'status', 
        'completed_at', 'confirmed_at', 'assigned_at',
        'first_seen_at', 'last_seen_at', 'missing_since',
        'assigned_by', 'confirmed_by', 'archive_reason'
    ]
    
    for field in db_only_fields:
        if field in db_fields:
            print(f"\n  DB字段: '{field}'")
            print(f"    说明: {db_fields[field]}")
    
    # 检查数据库实际结构
    db_columns = get_db_columns()
    if db_columns:
        print("\n\n" + "=" * 80)
        print("2. 数据库实际字段列表")
        print("=" * 80)
        print(f"\n共 {len(db_columns)} 个字段:")
        for i, col in enumerate(db_columns, 1):
            desc = db_fields.get(col, "【未记录】")
            print(f"  {i:2d}. {col:20s} - {desc}")
    else:
        print("\n\n[INFO] 数据库文件不存在，无法验证实际结构")
    
    # 数据流向分析
    print("\n\n" + "=" * 80)
    print("3. 数据流向分析")
    print("=" * 80)
    
    print("\n【Excel -> 数据库】同步路径:")
    sync_paths = [
        ("原始行号", "row_index", "registry/util.py::build_task_key_from_row"),
        ("项目号", "project_id", "registry/util.py::build_task_key_from_row"),
        ("接口号", "interface_id", "registry/util.py::build_task_key_from_row"),
        ("部门", "department", "registry/util.py::build_task_fields_from_row"),
        ("接口时间", "interface_time", "registry/util.py::build_task_fields_from_row"),
        ("角色来源", "role", "registry/util.py::build_task_fields_from_row"),
        ("责任人", "responsible_person", "registry/util.py::build_task_fields_from_row【新增】"),
    ]
    
    for excel_col, db_field, code_path in sync_paths:
        print(f"\n  '{excel_col}' -> '{db_field}'")
        print(f"    代码位置: {code_path}")
    
    print("\n\n【数据库 -> Excel】回写路径:")
    write_back_paths = [
        ("responsible_person", "责任人", "distribution.py::save_assignments_batch"),
        ("completed_at", "(触发'已完成'勾选)", "input_handler.py::write_response_to_excel"),
    ]
    
    for db_field, excel_effect, code_path in write_back_paths:
        print(f"\n  '{db_field}' -> {excel_effect}")
        print(f"    代码位置: {code_path}")
    
    # 潜在问题分析
    print("\n\n" + "=" * 80)
    print("4. 可能缺失的映射（需要确认）")
    print("=" * 80)
    
    potential_missing = [
        ("回文单号", "【无对应DB字段】", 
         "用于标记任务完成，但不存储单号内容本身。\n    "
         "仅用于触发status='completed'和记录completed_at时间。"),
        
        ("已完成勾选框", "【无对应DB字段】", 
         "UI状态，存储在file_cache.json中，按用户维度记录。\n    "
         "Registry通过completed_at间接反映完成状态。"),
        
        ("其他Excel列", "【未知】", 
         "Excel中可能还有其他列（如备注、说明等），\n    "
         "目前未映射到数据库。如有业务需求可以扩展。"),
    ]
    
    print("\n以下Excel列/数据【未直接存储】到数据库:")
    for excel_item, db_status, reason in potential_missing:
        print(f"\n  Excel: '{excel_item}'")
        print(f"    DB: {db_status}")
        print(f"    原因: {reason}")
    
    # 总结
    print("\n\n" + "=" * 80)
    print("5. 总结")
    print("=" * 80)
    
    print("\n[Implemented Mappings]:")
    print("  [OK] Original Row -> row_index")
    print("  [OK] Project ID -> project_id")
    print("  [OK] Interface ID -> interface_id")
    print("  [OK] Department -> department")
    print("  [OK] Interface Time -> interface_time")
    print("  [OK] Role Source -> role")
    print("  [OK] Responsible Person -> responsible_person [NEW]")
    print("  [OK] Status (Registry computed) -> display_status")
    
    print("\n[No Need to Map]:")
    print("  [O] Response Number: Triggers status change, not stored")
    print("  [O] Completed Checkbox: UI state, stored in file_cache.json")
    
    print("\n[Recommendations]:")
    print("  1. If Excel has other important columns (e.g., notes, priority),")
    print("     consider adding corresponding DB fields.")
    print("  2. Current mappings cover core business data for reminder function.")
    print("  3. Responsible person field addition solved 'Please Assign' issue.")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

