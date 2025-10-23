# -*- coding: utf-8 -*-
"""
文件标识管理和勾选状态持久化模块

功能：
1. 为每个Excel文件生成唯一标识（基于文件名、大小、修改时间）
2. 管理"是否已完成"勾选状态的持久化
3. 检测文件变化并自动清空勾选状态
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Set, Optional, Tuple, List


class FileIdentityManager:
    """文件标识管理器"""
    
    def __init__(self, cache_file="file_cache.json"):
        """
        初始化文件标识管理器
        
        参数:
            cache_file: 缓存文件路径
        """
        self.cache_file = cache_file
        self.file_identities = {}  # {file_path: identity_hash}
        self.completed_rows = {}   # {file_path: {row_index: True}}
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
    
    def set_row_completed(self, file_path: str, row_index: int, completed: bool = True):
        """
        设置某行的完成状态
        
        参数:
            file_path: 文件路径
            row_index: 行索引
            completed: 是否已完成
        """
        if file_path not in self.completed_rows:
            self.completed_rows[file_path] = {}
        
        if completed:
            self.completed_rows[file_path][row_index] = True
        else:
            # 取消勾选
            if row_index in self.completed_rows[file_path]:
                del self.completed_rows[file_path][row_index]
        
        self._save_cache()
    
    def is_row_completed(self, file_path: str, row_index: int) -> bool:
        """
        查询某行是否已完成
        
        参数:
            file_path: 文件路径
            row_index: 行索引
            
        返回:
            True = 已完成，False = 未完成
        """
        if file_path not in self.completed_rows:
            return False
        
        return self.completed_rows[file_path].get(row_index, False)
    
    def get_completed_rows(self, file_path: str) -> Set[int]:
        """
        获取文件所有已完成的行索引
        
        参数:
            file_path: 文件路径
            
        返回:
            已完成行索引的集合
        """
        if file_path not in self.completed_rows:
            return set()
        
        return set(self.completed_rows[file_path].keys())
    
    def clear_all_completed_rows(self):
        """
        清空所有文件的完成状态
        
        用于文件发生变化时
        """
        print("检测到文件变化，清空所有勾选状态")
        self.completed_rows = {}
        self._save_cache()
    
    def clear_file_completed_rows(self, file_path: str):
        """
        清空指定文件的完成状态
        
        参数:
            file_path: 文件路径
        """
        if file_path in self.completed_rows:
            del self.completed_rows[file_path]
            self._save_cache()
    
    def _load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.file_identities = data.get('file_identities', {})
                
                # 转换completed_rows的key为int
                completed_rows_raw = data.get('completed_rows', {})
                self.completed_rows = {}
                for file_path, rows in completed_rows_raw.items():
                    self.completed_rows[file_path] = {int(k): v for k, v in rows.items()}
                
                print(f"加载缓存成功: {len(self.file_identities)}个文件标识")
        except Exception as e:
            print(f"加载缓存失败: {e}")
            self.file_identities = {}
            self.completed_rows = {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        try:
            # 转换completed_rows的key为str（JSON要求）
            completed_rows_serializable = {}
            for file_path, rows in self.completed_rows.items():
                completed_rows_serializable[file_path] = {str(k): v for k, v in rows.items()}
            
            data = {
                'file_identities': self.file_identities,
                'completed_rows': completed_rows_serializable,
                'last_update': datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
        except Exception as e:
            print(f"保存缓存失败: {e}")


# 全局单例
_file_manager_instance = None


def get_file_manager() -> FileIdentityManager:
    """获取文件管理器单例"""
    global _file_manager_instance
    if _file_manager_instance is None:
        _file_manager_instance = FileIdentityManager()
    return _file_manager_instance

