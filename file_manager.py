# -*- coding: utf-8 -*-
"""
文件标识管理和勾选状态持久化模块

功能：
1. 为每个Excel文件生成唯一标识（基于文件名、大小、修改时间）
2. 管理"是否已完成"勾选状态的持久化
3. 检测文件变化并自动清空勾选状态
4. 管理处理结果缓存（按文件+项目粒度）
"""

import os
import sys
import json
import hashlib
import pickle
import shutil
from datetime import datetime
from typing import Dict, Set, Optional, Tuple, List
import pandas as pd


def _get_app_directory():
    """
    获取程序所在目录的绝对路径
    
    支持：
    - 开发环境：返回脚本所在目录
    - 打包环境：返回exe所在目录
    - 开机自启动：确保返回程序实际目录
    """
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        app_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    return app_dir


class FileIdentityManager:
    """文件标识管理器"""
    
    def __init__(self, cache_file="file_cache.json", result_cache_dir="result_cache"):
        """
        初始化文件标识管理器
        
        参数:
            cache_file: 缓存文件名（将转为绝对路径）
            result_cache_dir: 结果缓存目录名（将转为绝对路径）
        """
        # 获取程序所在目录
        app_dir = _get_app_directory()
        
        # 转换为绝对路径（基于程序所在目录）
        self.cache_file = os.path.join(app_dir, cache_file)
        self.result_cache_dir = os.path.join(app_dir, result_cache_dir)
        
        self.file_identities = {}  # {file_path: identity_hash}
        # 【修复】completed_rows改为按用户姓名分组
        # 结构: {user_name: {file_path: {row_index: True}}}
        self.completed_rows = {}
        
        print(f"缓存目录: {self.result_cache_dir}")
        print(f"缓存文件: {self.cache_file}")
        
        # 确保缓存目录存在
        self._ensure_cache_dir()
        
        # 加载缓存
        self._load_cache()
    
    def generate_file_identity(self, file_path: str) -> Optional[str]:
        """
        生成文件唯一标识
        
        基于：文件名 + 文件大小 + 修改时间
        
        返回:
            文件标识哈希值，如果文件不存在返回None
        """
        try:
            if not os.path.exists(file_path):
                return None
            
            # 获取文件信息
            file_stat = os.stat(file_path)
            file_name = os.path.basename(file_path)
            file_size = file_stat.st_size
            modify_time = file_stat.st_mtime
            
            # 生成标识字符串
            identity_str = f"{file_name}|{file_size}|{modify_time}"
            
            # 生成哈希
            identity_hash = hashlib.md5(identity_str.encode('utf-8')).hexdigest()
            
            return identity_hash
            
        except Exception as e:
            print(f"生成文件标识失败 {file_path}: {e}")
            return None
    
    def check_files_changed(self, file_paths: List[str]) -> bool:
        """
        检查文件列表中是否有文件发生变化
        
        只要有一个文件标识不一致，就返回True
        
        参数:
            file_paths: 文件路径列表
            
        返回:
            True = 有文件变化，False = 无变化
        """
        for file_path in file_paths:
            if not file_path:
                continue
                
            current_identity = self.generate_file_identity(file_path)
            if current_identity is None:
                # 文件不存在，视为变化
                continue
                
            cached_identity = self.file_identities.get(file_path)
            
            if cached_identity is None:
                # 新文件，视为变化
                return True
            
            if current_identity != cached_identity:
                # 标识不匹配，文件已变化
                print(f"文件已变化: {os.path.basename(file_path)}")
                return True
        
        return False
    
    def update_file_identities(self, file_paths: List[str]):
        """
        更新文件标识缓存
        
        参数:
            file_paths: 文件路径列表
        """
        for file_path in file_paths:
            if not file_path:
                continue
            
            identity = self.generate_file_identity(file_path)
            if identity:
                self.file_identities[file_path] = identity
        
        self._save_cache()
    
    def set_row_completed(self, file_path: str, row_index: int, completed: bool = True, user_name: str = ""):
        """
        设置某行的完成状态
        
        参数:
            file_path: 文件路径
            row_index: 行索引
            completed: 是否已完成
            user_name: 用户姓名（新增）
        """
        if not user_name:
            user_name = "默认用户"
        
        # 确保用户姓名的字典存在
        if user_name not in self.completed_rows:
            self.completed_rows[user_name] = {}
        
        # 确保文件路径的字典存在
        if file_path not in self.completed_rows[user_name]:
            self.completed_rows[user_name][file_path] = {}
        
        if completed:
            self.completed_rows[user_name][file_path][row_index] = True
        else:
            # 取消勾选
            if row_index in self.completed_rows[user_name][file_path]:
                del self.completed_rows[user_name][file_path][row_index]
        
        self._save_cache()
    
    def is_row_completed(self, file_path: str, row_index: int, user_name: str = "") -> bool:
        """
        查询某行是否已完成
        
        参数:
            file_path: 文件路径
            row_index: 行索引
            user_name: 用户姓名（新增）
            
        返回:
            True = 已完成，False = 未完成
        """
        if not user_name:
            user_name = "默认用户"
        
        if user_name not in self.completed_rows:
            return False
        
        if file_path not in self.completed_rows[user_name]:
            return False
        
        return self.completed_rows[user_name][file_path].get(row_index, False)
    
    def get_completed_rows(self, file_path: str, user_name: str = "") -> Set[int]:
        """
        获取文件所有已完成的行索引
        
        参数:
            file_path: 文件路径
            user_name: 用户姓名（新增）
            
        返回:
            已完成行索引的集合
        """
        if not user_name:
            user_name = "默认用户"
        
        if user_name not in self.completed_rows:
            return set()
        
        if file_path not in self.completed_rows[user_name]:
            return set()
        
        return set(self.completed_rows[user_name][file_path].keys())
    
    def clear_all_completed_rows(self):
        """
        清空所有文件的完成状态
        
        用于文件发生变化时
        """
        print("检测到文件变化，清空所有勾选状态")
        self.completed_rows = {}
        self._save_cache()
    
    def clear_file_completed_rows(self, file_path: str, user_name: str = ""):
        """
        清空指定文件的完成状态（可选：仅清空指定用户的）
        
        参数:
            file_path: 文件路径
            user_name: 用户姓名（如果为空，清空所有用户的该文件状态）
        """
        if user_name:
            # 清空指定用户的指定文件
            if user_name in self.completed_rows and file_path in self.completed_rows[user_name]:
                del self.completed_rows[user_name][file_path]
                self._save_cache()
        else:
            # 清空所有用户的指定文件
            for user in self.completed_rows:
                if file_path in self.completed_rows[user]:
                    del self.completed_rows[user][file_path]
            self._save_cache()
    
    def _load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.file_identities = data.get('file_identities', {})
                
                # 【修复】转换completed_rows的key为int,支持新的按用户分组结构
                completed_rows_raw = data.get('completed_rows', {})
                self.completed_rows = {}
                
                # 判断是旧格式还是新格式
                if completed_rows_raw:
                    # 检查第一个key是否是文件路径(旧格式)或用户姓名(新格式)
                    first_key = list(completed_rows_raw.keys())[0]
                    first_value = completed_rows_raw[first_key]
                    
                    # 如果first_value的第一个value是bool,说明是旧格式{file_path: {row: bool}}
                    # 如果first_value的第一个value是dict,说明是新格式{user: {file_path: {row: bool}}}
                    is_old_format = False
                    if first_value:
                        first_inner_value = list(first_value.values())[0]
                        if isinstance(first_inner_value, bool):
                            is_old_format = True
                    
                    if is_old_format:
                        # 旧格式：将所有数据迁移到"默认用户"下
                        print("  检测到旧格式缓存，自动迁移到新格式")
                        self.completed_rows["默认用户"] = {}
                        for file_path, rows in completed_rows_raw.items():
                            self.completed_rows["默认用户"][file_path] = {int(k): v for k, v in rows.items()}
                    else:
                        # 新格式：按用户姓名分组
                        for user_name, user_data in completed_rows_raw.items():
                            self.completed_rows[user_name] = {}
                            for file_path, rows in user_data.items():
                                self.completed_rows[user_name][file_path] = {int(k): v for k, v in rows.items()}
                
                print(f"加载缓存成功: {len(self.file_identities)}个文件标识")
        except Exception as e:
            print(f"加载缓存失败: {e}")
            self.file_identities = {}
            self.completed_rows = {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            # 检查目录是否可写
            cache_dir = os.path.dirname(self.cache_file)
            if not os.access(cache_dir, os.W_OK):
                print(f"⚠️ 缓存目录无写入权限，跳过保存: {cache_dir}")
                return
            
            # 【修复】转换completed_rows的key为str（JSON要求），支持新的按用户分组结构
            completed_rows_serializable = {}
            for user_name, user_data in self.completed_rows.items():
                completed_rows_serializable[user_name] = {}
                for file_path, rows in user_data.items():
                    completed_rows_serializable[user_name][file_path] = {str(k): v for k, v in rows.items()}
            
            data = {
                'file_identities': self.file_identities,
                'completed_rows': completed_rows_serializable,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
        except PermissionError as e:
            print(f"⚠️ 缓存文件无写入权限，跳过保存: {self.cache_file}")
        except Exception as e:
            print(f"⚠️ 保存缓存失败: {e}")
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        try:
            # 检查父目录是否可写
            parent_dir = os.path.dirname(self.result_cache_dir)
            if not parent_dir:
                parent_dir = os.path.dirname(os.path.abspath(self.result_cache_dir))
            
            if not os.access(parent_dir, os.W_OK):
                print(f"⚠️ 父目录无写入权限，无法创建缓存目录: {parent_dir}")
                print(f"⚠️ 缓存功能将被禁用，但不影响程序主要功能")
                return
            
            if not os.path.exists(self.result_cache_dir):
                os.makedirs(self.result_cache_dir, exist_ok=True)
                print(f"✅ 创建缓存目录: {self.result_cache_dir}")
        except PermissionError as e:
            print(f"⚠️ 权限不足，无法创建缓存目录: {self.result_cache_dir}")
            print(f"⚠️ 缓存功能将被禁用，但不影响程序主要功能")
        except Exception as e:
            print(f"⚠️ 创建缓存目录失败: {e}")
            print(f"⚠️ 缓存功能将被禁用，但不影响程序主要功能")
    
    def _get_cache_filename(self, file_path: str, project_id: str, file_type: str) -> str:
        """
        生成缓存文件名
        
        格式: {文件hash前8位}_{项目号}_{文件类型}.pkl
        例如: a1b2c3d4_2016_file1.pkl
        
        参数:
            file_path: 源文件路径
            project_id: 项目号
            file_type: 文件类型（file1-file6）
            
        返回:
            缓存文件名
        """
        file_hash = hashlib.md5(os.path.abspath(file_path).encode('utf-8')).hexdigest()[:8]
        cache_filename = f"{file_hash}_{project_id}_{file_type}.pkl"
        return os.path.join(self.result_cache_dir, cache_filename)
    
    def save_cached_result(self, file_path: str, project_id: str, file_type: str, 
                          dataframe: pd.DataFrame) -> bool:
        """
        保存处理结果到缓存
        
        参数:
            file_path: 源文件路径
            project_id: 项目号
            file_type: 文件类型（file1-file6）
            dataframe: 处理后的DataFrame
            
        返回:
            True = 保存成功, False = 保存失败
        """
        try:
            # 检查缓存目录是否存在且可写
            if not os.path.exists(self.result_cache_dir):
                print(f"⚠️ 缓存目录不存在，跳过保存: {self.result_cache_dir}")
                return False
            
            if not os.access(self.result_cache_dir, os.W_OK):
                print(f"⚠️ 缓存目录无写入权限，跳过保存: {self.result_cache_dir}")
                return False
            
            cache_file = self._get_cache_filename(file_path, project_id, file_type)
            
            # 使用pickle保存DataFrame
            with open(cache_file, 'wb') as f:
                pickle.dump(dataframe, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            print(f"✅ 缓存已保存: {os.path.basename(cache_file)}")
            return True
            
        except PermissionError as e:
            print(f"⚠️ 权限不足，无法保存缓存 [{file_type}, {project_id}]")
            return False
        except Exception as e:
            print(f"⚠️ 保存缓存失败 [{file_type}, {project_id}]: {e}")
            return False
    
    def load_cached_result(self, file_path: str, project_id: str, file_type: str) -> Optional[pd.DataFrame]:
        """
        加载缓存的处理结果
        
        参数:
            file_path: 源文件路径
            project_id: 项目号
            file_type: 文件类型（file1-file6）
            
        返回:
            DataFrame对象，如果缓存不存在或加载失败返回None
        """
        try:
            cache_file = self._get_cache_filename(file_path, project_id, file_type)
            
            # 检查缓存文件是否存在
            if not os.path.exists(cache_file):
                return None
            
            # 验证源文件标识是否一致
            current_identity = self.generate_file_identity(file_path)
            cached_identity = self.file_identities.get(file_path)
            
            # 【修复】只有当cached_identity存在且不一致时，才使缓存失效
            # 如果cached_identity是None（新文件），允许使用缓存
            if cached_identity is not None and current_identity != cached_identity:
                print(f"⚠️ 文件已变化，缓存失效: {os.path.basename(cache_file)}")
                # 静默删除失效的缓存
                try:
                    os.remove(cache_file)
                except:
                    pass
                return None
            
            # 【新增】如果这是新文件（cached_identity是None），更新文件标识
            if cached_identity is None and current_identity is not None:
                self.file_identities[file_path] = current_identity
                self._save_cache()
            
            # 加载缓存
            with open(cache_file, 'rb') as f:
                dataframe = pickle.load(f)
            
            print(f"✅ 缓存已加载: {os.path.basename(cache_file)} ({len(dataframe)}行)")
            return dataframe
            
        except (pickle.UnpicklingError, EOFError, ValueError) as e:
            # 损坏的缓存文件，静默删除并重新处理
            print(f"⚠️ 缓存文件损坏，将重新处理: {e}")
            try:
                cache_file = self._get_cache_filename(file_path, project_id, file_type)
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    print(f"已删除损坏的缓存文件: {os.path.basename(cache_file)}")
            except Exception as del_err:
                print(f"删除损坏缓存失败: {del_err}")
            return None
            
        except Exception as e:
            print(f"❌ 加载缓存失败 [{file_type}, {project_id}]: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def clear_file_cache(self, file_path: str):
        """
        清除指定文件的所有缓存（所有项目、所有类型）
        
        参数:
            file_path: 源文件路径
        """
        try:
            file_hash = hashlib.md5(os.path.abspath(file_path).encode('utf-8')).hexdigest()[:8]
            
            # 查找所有匹配的缓存文件
            deleted_count = 0
            if os.path.exists(self.result_cache_dir):
                for filename in os.listdir(self.result_cache_dir):
                    if filename.startswith(file_hash) and filename.endswith('.pkl'):
                        cache_file = os.path.join(self.result_cache_dir, filename)
                        try:
                            os.remove(cache_file)
                            deleted_count += 1
                        except Exception as e:
                            print(f"删除缓存文件失败 {filename}: {e}")
            
            if deleted_count > 0:
                print(f"已清除 {deleted_count} 个缓存文件: {os.path.basename(file_path)}")
                
        except Exception as e:
            print(f"清除文件缓存失败: {e}")
    
    def clear_all_caches(self):
        """
        清除所有缓存（包括结果缓存和勾选状态）
        
        用于"清除缓存"按钮
        """
        try:
            # 1. 清除结果缓存目录
            if os.path.exists(self.result_cache_dir):
                shutil.rmtree(self.result_cache_dir)
                print(f"✅ 已删除缓存目录: {self.result_cache_dir}")
            
            # 2. 重新创建空目录
            self._ensure_cache_dir()
            
            # 3. 清空内存中的数据
            self.file_identities = {}
            self.completed_rows = {}
            
            # 4. 保存空的file_cache.json
            self._save_cache()
            
            print("✅ 所有缓存已清除")
            return True
            
        except Exception as e:
            print(f"❌ 清除缓存失败: {e}")
            import traceback
            traceback.print_exc()
            return False


# 全局单例
_file_manager_instance = None


def get_file_manager() -> FileIdentityManager:
    """获取文件管理器单例"""
    global _file_manager_instance
    if _file_manager_instance is None:
        _file_manager_instance = FileIdentityManager()
    return _file_manager_instance

