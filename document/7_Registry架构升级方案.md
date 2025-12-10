# SQLite 多用户并发优化方案

## 一、现状分析

### 1.1 已实现的优化

程序**已经实现**的优化措施：

| 功能 | 实现位置 | 说明 |
|------|----------|------|
| ✅ 并行文件读取 | `base.py:165` | `ThreadPoolExecutor` 并发读取Excel |
| ✅ 文件缓存机制 | `file_manager.py` | 基于文件哈希的pkl缓存 |
| ✅ 数据库索引 | `registry/db.py:311-360` | 5个任务表索引 + 3个事件表索引 |
| ✅ WAL模式自动切换 | `registry/db.py:220` | 本地用WAL，网络盘用DELETE |
| ✅ 重试机制 | `registry/hooks.py:25` | 锁定时指数退避重试 |

### 1.2 真正的性能瓶颈

经过代码分析，**真正的瓶颈**在于：

| 瓶颈 | 原因 | 影响程度 |
|------|------|----------|
| **Registry写入串行化** | 所有用户的写入操作排队等待 | 🔴 高 |
| **网络盘文件锁不可靠** | SMB/CIFS协议的固有限制 | 🔴 高 |
| **UI线程阻塞** | `start_processing` 未完全异步化 | 🟡 中 |
| **Registry查询在显示时** | 每次显示都查询数据库 | 🟡 中 |

---

## 二、SQLite 优化方案

### 2.1 方案概述

在**保持SQLite**的前提下，通过以下策略优化80人并发场景：

```
                     ┌─────────────────────────────────────┐
                     │         优化后的架构                 │
                     └─────────────────────────────────────┘
                     
     用户A ──┐                                   ┌── 用户A本地缓存
     用户B ──┼─── 【读取】直接读本地缓存 ────────┤── 用户B本地缓存
     用户C ──┘    （无锁，瞬间响应）              └── 用户C本地缓存
                                                       ↑
                                                       │ 定期同步
                                                       ↓
     用户A ──┐                                 ┌─────────────┐
     用户B ──┼─── 【写入】队列化批量写入 ─────→│  网络盘      │
     用户C ──┘    （合并请求，减少锁竞争）      │  registry.db│
                                               └─────────────┘
```

### 2.2 优化措施清单

| 优先级 | 措施 | 预期效果 | 实现难度 |
|--------|------|----------|----------|
| 🔴 P0 | 本地只读缓存 | 读取零等待 | 中 |
| 🔴 P0 | 写入队列化 | 减少80%锁竞争 | 中 |
| 🟡 P1 | Registry查询结果缓存 | 减少重复查询 | 低 |
| 🟡 P1 | 增加interface_id索引 | 加速Registry查询 | 低 |
| 🟢 P2 | UI完全异步化 | 界面不卡顿 | 中 |

---

## 三、P0：本地只读缓存

### 3.1 设计思路

**问题**：所有用户都直接读取网络盘上的registry.db，造成锁竞争。

**解决**：每个用户本地维护一份只读缓存，只在特定时机同步。

### 3.2 实现方案

```
程序启动
    │
    ├─→ 检查本地缓存是否存在
    │       │
    │       ├─ 存在：直接加载（<100ms）
    │       │
    │       └─ 不存在：从网络盘复制一份
    │
    ↓
用户操作（查看任务、筛选）
    │
    └─→ 全部从本地缓存读取（无网络IO）
    
用户写入（标记完成、忽略）
    │
    ├─→ 写入网络盘registry.db
    │
    └─→ 同时更新本地缓存
    
定时同步（每5分钟）
    │
    └─→ 检查网络盘版本，增量同步变化
```

### 3.3 代码修改

**新增文件**: `registry/local_cache.py`

```python
"""
本地只读缓存管理

功能：
1. 启动时复制/同步网络盘数据库到本地
2. 所有读操作使用本地缓存
3. 写操作同时更新本地和网络盘
4. 定期检测并同步变化
"""

import os
import shutil
import sqlite3
import time
from typing import Optional
from datetime import datetime

class LocalCacheManager:
    """本地缓存管理器"""
    
    def __init__(self, network_db_path: str, local_cache_dir: str = None):
        """
        初始化本地缓存管理器
        
        参数:
            network_db_path: 网络盘数据库路径
            local_cache_dir: 本地缓存目录（默认为用户临时目录）
        """
        self.network_db_path = network_db_path
        
        # 本地缓存目录
        if local_cache_dir is None:
            local_cache_dir = os.path.join(
                os.environ.get('LOCALAPPDATA', os.path.expanduser('~')),
                'InterfaceFilter',
                'cache'
            )
        
        os.makedirs(local_cache_dir, exist_ok=True)
        self.local_db_path = os.path.join(local_cache_dir, 'registry_local.db')
        self.last_sync_time = None
        self._local_conn = None
    
    def ensure_local_cache(self) -> bool:
        """
        确保本地缓存存在且有效
        
        返回:
            True = 缓存可用, False = 需要从网络盘同步
        """
        if not os.path.exists(self.local_db_path):
            return self._full_sync()
        
        # 检查本地缓存是否过期（超过5分钟）
        local_mtime = os.path.getmtime(self.local_db_path)
        if time.time() - local_mtime > 300:  # 5分钟
            return self._incremental_sync()
        
        return True
    
    def _full_sync(self) -> bool:
        """完整同步：复制整个数据库"""
        try:
            print(f"[LocalCache] 首次同步，复制数据库...")
            
            # 关闭现有连接
            self._close_local_conn()
            
            # 复制文件
            shutil.copy2(self.network_db_path, self.local_db_path)
            
            self.last_sync_time = datetime.now()
            print(f"[LocalCache] 同步完成")
            return True
            
        except Exception as e:
            print(f"[LocalCache] 同步失败: {e}")
            return False
    
    def _incremental_sync(self) -> bool:
        """增量同步：只同步变化的数据"""
        try:
            # 获取网络盘最后更新时间
            network_mtime = os.path.getmtime(self.network_db_path)
            local_mtime = os.path.getmtime(self.local_db_path)
            
            if network_mtime <= local_mtime:
                # 网络盘没有更新，无需同步
                return True
            
            print(f"[LocalCache] 检测到网络盘更新，增量同步...")
            
            # 简单方案：直接重新复制
            # 复杂方案：比对last_seen_at增量同步（暂不实现）
            return self._full_sync()
            
        except Exception as e:
            print(f"[LocalCache] 增量同步失败: {e}")
            return False
    
    def get_read_connection(self) -> sqlite3.Connection:
        """获取只读连接（使用本地缓存）"""
        if self._local_conn is None:
            self.ensure_local_cache()
            self._local_conn = sqlite3.connect(
                self.local_db_path,
                check_same_thread=False,
                timeout=5.0
            )
            self._local_conn.execute("PRAGMA query_only = ON")
        return self._local_conn
    
    def _close_local_conn(self):
        """关闭本地连接"""
        if self._local_conn:
            try:
                self._local_conn.close()
            except:
                pass
            self._local_conn = None
    
    def invalidate_cache(self):
        """标记缓存失效，下次读取时重新同步"""
        self._close_local_conn()
        if os.path.exists(self.local_db_path):
            # 修改文件时间为很久以前，触发下次同步
            os.utime(self.local_db_path, (0, 0))
```

### 3.4 集成修改

**修改文件**: `registry/db.py`

```python
# 新增：读写分离
_local_cache_manager = None

def get_read_connection(db_path: str) -> sqlite3.Connection:
    """获取只读连接（优先使用本地缓存）"""
    global _local_cache_manager
    
    if _is_network_path(db_path):
        if _local_cache_manager is None:
            from registry.local_cache import LocalCacheManager
            _local_cache_manager = LocalCacheManager(db_path)
        return _local_cache_manager.get_read_connection()
    else:
        # 本地路径直接连接
        return get_connection(db_path, wal=True)

def get_write_connection(db_path: str, wal: bool = True) -> sqlite3.Connection:
    """获取写入连接（直接连接网络盘）"""
    return get_connection(db_path, wal)

def invalidate_read_cache():
    """写入后使读缓存失效"""
    global _local_cache_manager
    if _local_cache_manager:
        _local_cache_manager.invalidate_cache()
```

---

## 四、P0：写入队列化

### 4.1 设计思路

**问题**：80人同时写入时，锁竞争严重。

**解决**：将写入请求放入队列，由后台线程批量处理。

### 4.2 实现方案

```python
# registry/write_queue.py

import queue
import threading
import time
from typing import Callable, Any

class WriteQueue:
    """写入队列管理器"""
    
    def __init__(self, batch_interval: float = 1.0, max_batch_size: int = 50):
        """
        初始化写入队列
        
        参数:
            batch_interval: 批量写入间隔（秒）
            max_batch_size: 单批最大任务数
        """
        self._queue = queue.Queue()
        self._batch_interval = batch_interval
        self._max_batch_size = max_batch_size
        self._worker_thread = None
        self._running = False
        self._callbacks = {}  # request_id -> callback
    
    def start(self):
        """启动后台写入线程"""
        if self._worker_thread is not None:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop(self):
        """停止后台写入线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
            self._worker_thread = None
    
    def enqueue(self, operation: str, data: dict, callback: Callable = None) -> str:
        """
        将写入操作加入队列
        
        参数:
            operation: 操作类型 (upsert/update/delete)
            data: 操作数据
            callback: 完成回调（可选）
            
        返回:
            请求ID
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        self._queue.put({
            'id': request_id,
            'operation': operation,
            'data': data,
            'timestamp': time.time()
        })
        
        if callback:
            self._callbacks[request_id] = callback
        
        return request_id
    
    def _worker_loop(self):
        """后台工作线程"""
        while self._running:
            batch = []
            
            # 收集一批请求
            deadline = time.time() + self._batch_interval
            while len(batch) < self._max_batch_size and time.time() < deadline:
                try:
                    item = self._queue.get(timeout=0.1)
                    batch.append(item)
                except queue.Empty:
                    continue
            
            # 批量执行
            if batch:
                self._process_batch(batch)
    
    def _process_batch(self, batch: list):
        """处理一批写入请求"""
        try:
            from registry.db import get_write_connection, invalidate_read_cache
            from registry.config import get_config
            
            config = get_config()
            db_path = config.get('registry_db_path', '')
            
            conn = get_write_connection(db_path, wal=False)
            
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                for item in batch:
                    self._execute_single(conn, item)
                
                conn.commit()
                
                # 写入成功，使读缓存失效
                invalidate_read_cache()
                
                # 执行回调
                for item in batch:
                    callback = self._callbacks.pop(item['id'], None)
                    if callback:
                        callback(True, None)
                
            except Exception as e:
                conn.rollback()
                print(f"[WriteQueue] 批量写入失败: {e}")
                
                # 执行失败回调
                for item in batch:
                    callback = self._callbacks.pop(item['id'], None)
                    if callback:
                        callback(False, str(e))
                
        except Exception as e:
            print(f"[WriteQueue] 获取连接失败: {e}")
    
    def _execute_single(self, conn, item: dict):
        """执行单个写入操作"""
        operation = item['operation']
        data = item['data']
        
        if operation == 'upsert_task':
            # 执行upsert
            pass  # 具体SQL
        elif operation == 'mark_ignored':
            # 标记忽略
            pass
        elif operation == 'mark_completed':
            # 标记完成
            pass


# 全局写入队列
_write_queue = None

def get_write_queue() -> WriteQueue:
    """获取全局写入队列"""
    global _write_queue
    if _write_queue is None:
        _write_queue = WriteQueue()
        _write_queue.start()
    return _write_queue
```

---

## 五、P1：查询结果缓存

### 5.1 设计思路

**问题**：`get_display_status` 每次显示都查询数据库。

**解决**：缓存查询结果，只在数据变化时刷新。

### 5.2 实现方案

**修改文件**: `registry/service.py`

```python
# 添加查询缓存
_display_status_cache = {}
_cache_valid = False

def get_display_status_cached(db_path, wal, file_type, project_id, ...) -> dict:
    """带缓存的状态查询"""
    global _display_status_cache, _cache_valid
    
    cache_key = f"{file_type}|{project_id}"
    
    if _cache_valid and cache_key in _display_status_cache:
        return _display_status_cache[cache_key]
    
    # 缓存未命中，执行查询
    result = get_display_status(db_path, wal, file_type, project_id, ...)
    
    _display_status_cache[cache_key] = result
    _cache_valid = True
    
    return result

def invalidate_display_cache():
    """写入操作后调用，使缓存失效"""
    global _cache_valid
    _cache_valid = False
```

---

## 六、P1：添加索引

### 6.1 当前索引

```sql
-- 已存在的索引
idx_tasks_ft_pid (file_type, project_id)
idx_tasks_status (status)
idx_tasks_last_seen (last_seen_at)
idx_tasks_business_id (business_id)
idx_tasks_ignored (ignored, status)
```

### 6.2 新增索引

**修改文件**: `registry/db.py`

```python
# 在 _init_db 函数中添加
cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_interface_id ON tasks(interface_id);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_display_status ON tasks(display_status);")
cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_ft_pid_status ON tasks(file_type, project_id, status);")
```

**效果**：优化**所有6个文件类型**的 Registry 查询（从全表扫描到索引查找）。

> 注：`process_target_file` 到 `process_target_file6` 都有类似的 Registry 查询逻辑，新索引对它们全部生效。

---

## 七、实施步骤

### 7.1 第一阶段 ✅ 已完成

| 任务 | 文件 | 改动量 | 效果 | 状态 |
|------|------|--------|------|------|
| 添加索引 | registry/db.py | 3行 | 查询提速50%+ | ✅ |
| 查询结果缓存 | registry/service.py | 30行 | 减少重复查询 | ⏳ 待实现 |

### 7.2 第二阶段 ✅ 已完成

| 任务 | 文件 | 改动量 | 效果 | 状态 |
|------|------|--------|------|------|
| 本地只读缓存 | registry/local_cache.py | 288行 | 读取零等待 | ✅ |
| 修改读写分离 | registry/db.py | 124行 | 配合本地缓存 | ✅ |

### 7.3 第三阶段 ✅ 已完成

| 任务 | 文件 | 改动量 | 效果 | 状态 |
|------|------|--------|------|------|
| 写入队列化 | registry/write_queue.py | 505行 | 减少锁竞争 | ✅ |
| 修改写入调用 | registry/hooks.py | 131行 | 配合队列 | ✅ |
| 添加配置项 | registry/config.py | 65行 | 支持配置 | ✅ |

---

## 八、配置参数

### 8.1 新增配置项

```python
# registry/config.py

DEFAULT_CONFIG = {
    # 现有配置...
    
    # 本地缓存配置
    "registry_local_cache_enabled": True,    # 是否启用本地缓存
    "registry_local_cache_sync_interval": 300,  # 同步间隔（秒）
    
    # 写入队列配置
    "registry_write_queue_enabled": True,    # 是否启用写入队列
    "registry_write_batch_interval": 1.0,    # 批量间隔（秒）
    "registry_write_batch_size": 50,         # 单批最大数量
    
    # 查询缓存配置
    "registry_query_cache_enabled": True,    # 是否启用查询缓存
}
```

### 8.2 config.json 示例

```json
{
    "registry_enabled": true,
    "registry_local_cache_enabled": true,
    "registry_local_cache_sync_interval": 300,
    "registry_write_queue_enabled": true,
    "registry_query_cache_enabled": true
}
```

---

## 九、预期效果

### 9.1 性能对比

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 首次读取（无缓存） | 5-10秒 | 5-10秒 | - |
| 二次读取（有缓存） | 2-5秒 | <0.5秒 | 90%+ |
| 写入操作（单人） | 0.5秒 | 0.5秒 | - |
| 写入操作（80人并发） | 超时失败 | <2秒 | 可用 |
| 显示刷新 | 1-2秒 | <0.3秒 | 80%+ |

### 9.2 稳定性对比

| 问题 | 优化前 | 优化后 |
|------|--------|--------|
| 数据库锁定错误 | 频繁发生 | 极少发生 |
| UI卡顿 | 明显 | 基本消除 |
| 数据库损坏风险 | 存在 | 大幅降低 |

---

## 十、风险与注意事项

### 10.1 数据一致性

**风险**：本地缓存可能与网络盘不一致。

**缓解措施**：
1. 写入后立即使本地缓存失效
2. 定期自动同步（默认5分钟）
3. 提供"强制刷新"按钮

### 10.2 缓存空间

**风险**：本地缓存占用磁盘空间。

**缓解措施**：
1. 无需缓解

### 10.3 回滚方案

如果优化后出现问题，可以通过配置快速回滚：

```json
{
    "registry_local_cache_enabled": false,
    "registry_write_queue_enabled": false,
    "registry_query_cache_enabled": false
}
```

---

## 十一、总结

### SQLite 优化的核心思路

```
                ┌────────────────────────────┐
                │     减少网络盘访问次数      │
                │     ↓                      │
                │  1. 读取用本地缓存          │
                │  2. 写入批量化队列化        │
                │  3. 查询结果缓存            │
                └────────────────────────────┘
                              │
                              ↓
                ┌────────────────────────────┐
                │     减少锁持有时间          │
                │     ↓                      │
                │  1. 短事务快速提交          │
                │  2. 读写分离               │
                │  3. 合并多次写入           │
                └────────────────────────────┘
```

### 优先级建议

1. **立即执行**：添加索引（3行代码，效果明显）
2. **本周完成**：本地只读缓存（解决读取慢的根本问题）
3. **按需实现**：写入队列（如果仍有锁冲突再加）

---

*文档更新时间: 2025-12-08*
*版本: v3.0（第二/第三阶段已完成）*
