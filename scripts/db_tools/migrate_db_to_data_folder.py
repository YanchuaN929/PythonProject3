"""
自动迁移Registry数据库到数据文件夹（公共盘）

运行此脚本将：
1. 检查数据库位置
2. 自动迁移本地数据库到数据文件夹
3. 保留本地副本作为备份
"""

import os
import sys
import json
import shutil

def main():
    print("=" * 80)
    print("[Registry DB Migration Tool]")
    print("=" * 80)
    
    # 1. 读取config.json
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read config.json: {e}")
        return False
    
    folder_path = config.get('folder_path', '').strip()
    
    if not folder_path:
        print("\n[ERROR] folder_path not set in config.json")
        print("Cannot migrate database without data folder path.")
        return False
    
    print(f"\n[INFO] Data folder: {folder_path}")
    
    # 2. 计算路径
    correct_db_dir = os.path.join(folder_path, '.registry')
    correct_db_path = os.path.join(correct_db_dir, 'registry.db')
    local_db_path = os.path.join('result_cache', 'registry.db')
    
    print(f"[INFO] Target location: {correct_db_path}")
    print(f"[INFO] Source location: {local_db_path}")
    
    # 3. 检查状态
    local_exists = os.path.exists(local_db_path)
    correct_exists = os.path.exists(correct_db_path)
    
    print(f"\n[CHECK] Local DB exists: {local_exists}")
    print(f"[CHECK] Target DB exists: {correct_exists}")
    
    if not local_exists:
        print("\n[INFO] No local database found.")
        print("[INFO] Database will be created in data folder on next program run.")
        return True
    
    if correct_exists:
        local_size = os.path.getsize(local_db_path)
        correct_size = os.path.getsize(correct_db_path)
        
        print(f"\n[WARNING] Target database already exists!")
        print(f"  Local size: {local_size} bytes")
        print(f"  Target size: {correct_size} bytes")
        print("\n[INFO] Skipping migration to avoid overwriting existing database.")
        print("[RECOMMENDATION] Delete local database if target is correct.")
        return False
    
    # 4. 执行迁移
    print("\n" + "-" * 80)
    print("[MIGRATION] Starting migration process...")
    print("-" * 80)
    
    try:
        # 创建目标目录
        print(f"\n[STEP 1] Creating target directory...")
        os.makedirs(correct_db_dir, exist_ok=True)
        print(f"[OK] Directory ready: {correct_db_dir}")
        
        # 复制数据库
        print(f"\n[STEP 2] Copying database...")
        local_size = os.path.getsize(local_db_path)
        print(f"[INFO] Database size: {local_size} bytes")
        
        shutil.copy2(local_db_path, correct_db_path)
        print(f"[OK] Database copied to: {correct_db_path}")
        
        # 验证复制
        print(f"\n[STEP 3] Verifying migration...")
        if os.path.exists(correct_db_path):
            target_size = os.path.getsize(correct_db_path)
            if target_size == local_size:
                print(f"[OK] Verification passed (size: {target_size} bytes)")
            else:
                print(f"[WARNING] Size mismatch! Local: {local_size}, Target: {target_size}")
        else:
            print(f"[ERROR] Target file not found after copy!")
            return False
        
        print("\n" + "=" * 80)
        print("[SUCCESS] Migration completed!")
        print("=" * 80)
        
        print("\n[INFO] Local database kept as backup at: {local_db_path}")
        print("\n[NEXT STEPS]")
        print("1. Restart the program")
        print("2. All users accessing the same data folder will share this database")
        print("3. You can manually delete the local backup if migration works well")
        print(f"\n   To delete local backup: del {local_db_path}")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print("\n" + "=" * 80)
    if success:
        print("[RESULT] Migration successful or not needed")
    else:
        print("[RESULT] Migration failed or skipped")
    print("=" * 80)

