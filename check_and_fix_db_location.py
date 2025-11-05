"""
检查并修复Registry数据库位置

功能：
1. 检查当前数据库位置
2. 如果数据库在错误位置（本地result_cache），提供迁移选项
3. 迁移数据库到数据文件夹（公共盘）
"""

import os
import sys
import json
import shutil

def main():
    print("=" * 80)
    print("[Registry DB Location Check]")
    print("=" * 80)
    
    # 1. 读取config.json
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to read config.json: {e}")
        return
    
    folder_path = config.get('folder_path', '').strip()
    
    if not folder_path:
        print("\n[WARNING] folder_path not set in config.json")
        print("Registry database will use local path: result_cache\\registry.db")
        print("\nTo enable multi-user mode:")
        print("1. Set 'folder_path' in config.json to a network drive")
        print("2. Restart the program")
        return
    
    print(f"\n[INFO] Data folder (from config.json):")
    print(f"  {folder_path}")
    
    # 2. 计算正确的数据库路径
    correct_db_dir = os.path.join(folder_path, '.registry')
    correct_db_path = os.path.join(correct_db_dir, 'registry.db')
    
    print(f"\n[INFO] Correct database location (multi-user):")
    print(f"  {correct_db_path}")
    
    # 3. 检查本地数据库
    local_db_path = os.path.join('result_cache', 'registry.db')
    
    print(f"\n[INFO] Local database location:")
    print(f"  {local_db_path}")
    
    local_exists = os.path.exists(local_db_path)
    correct_exists = os.path.exists(correct_db_path)
    
    print(f"\n[CHECK] Local DB exists: {local_exists}")
    print(f"[CHECK] Correct DB exists: {correct_exists}")
    
    # 4. 判断是否需要迁移
    if local_exists and not correct_exists:
        print("\n" + "=" * 80)
        print("[ACTION NEEDED] Local database found, but no database in data folder")
        print("=" * 80)
        
        # 获取本地数据库大小
        local_size = os.path.getsize(local_db_path)
        print(f"\nLocal database size: {local_size} bytes")
        
        # 询问是否迁移
        print("\nOptions:")
        print("1. [M] Migrate local database to data folder (recommended for multi-user)")
        print("2. [K] Keep local database (single user mode)")
        print("3. [D] Delete local database (start fresh in data folder)")
        print("4. [C] Cancel (do nothing)")
        
        choice = input("\nYour choice [M/K/D/C]: ").strip().upper()
        
        if choice == 'M':
            # 迁移数据库
            print(f"\n[INFO] Migrating database to: {correct_db_path}")
            
            try:
                # 创建目标目录
                os.makedirs(correct_db_dir, exist_ok=True)
                print(f"[OK] Created directory: {correct_db_dir}")
                
                # 复制数据库文件
                shutil.copy2(local_db_path, correct_db_path)
                print(f"[OK] Copied database to: {correct_db_path}")
                
                # 询问是否删除本地副本
                delete_local = input("\nDelete local copy? [Y/N]: ").strip().upper()
                if delete_local == 'Y':
                    os.remove(local_db_path)
                    print("[OK] Deleted local database")
                else:
                    print("[INFO] Kept local database as backup")
                
                print("\n[SUCCESS] Migration completed!")
                print("\nNext steps:")
                print("1. Restart the program")
                print("2. All users should access the same data folder")
                print("3. The database will be shared across users")
                
            except Exception as e:
                print(f"\n[ERROR] Migration failed: {e}")
                import traceback
                traceback.print_exc()
        
        elif choice == 'K':
            print("\n[INFO] Keeping local database")
            print("[WARNING] Multi-user mode will NOT work!")
            print("[INFO] Each user will have their own local database")
        
        elif choice == 'D':
            confirm = input("\nAre you sure to delete local database? [YES/NO]: ").strip()
            if confirm == 'YES':
                os.remove(local_db_path)
                print("[OK] Deleted local database")
                print("[INFO] Program will create new database in data folder on next run")
            else:
                print("[INFO] Cancelled")
        
        else:
            print("\n[INFO] Cancelled")
    
    elif correct_exists and local_exists:
        print("\n" + "=" * 80)
        print("[WARNING] Both local and data folder databases exist!")
        print("=" * 80)
        
        local_size = os.path.getsize(local_db_path)
        correct_size = os.path.getsize(correct_db_path)
        
        print(f"\nLocal DB size: {local_size} bytes")
        print(f"Data folder DB size: {correct_size} bytes")
        
        print("\n[RECOMMENDATION] Delete the local database to avoid confusion")
        print("The program will use the data folder database when running normally.")
        
        delete_local = input("\nDelete local database? [Y/N]: ").strip().upper()
        if delete_local == 'Y':
            os.remove(local_db_path)
            print("[OK] Deleted local database")
        else:
            print("[INFO] Keeping both databases (not recommended)")
    
    elif correct_exists and not local_exists:
        print("\n" + "=" * 80)
        print("[OK] Database is in correct location!")
        print("=" * 80)
        print("\nThe program is correctly configured for multi-user mode.")
        print(f"Database location: {correct_db_path}")
    
    else:
        print("\n" + "=" * 80)
        print("[INFO] No database found yet")
        print("=" * 80)
        print("\nThe database will be created automatically when you:")
        print("1. Run the main program")
        print("2. Click 'Start Processing'")
        print(f"\nDatabase will be created at: {correct_db_path}")
    
    print("\n" + "=" * 80)
    print("[DONE]")
    print("=" * 80)

if __name__ == "__main__":
    main()

