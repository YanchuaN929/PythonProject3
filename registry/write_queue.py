"""
写入队列管理

功能：
1. 将写入请求放入队列
2. 后台线程批量处理写入
3. 减少锁竞争，提高并发性能

使用场景：
- 80人同时操作时，避免所有写入都直接竞争数据库锁
- 合并多个写入请求，减少锁持有次数
"""

import queue
import threading
import time
import uuid
from typing import Callable, Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class WriteOperation(Enum):
    """写入操作类型"""
    UPSERT_TASK = "upsert_task"
    BATCH_UPSERT = "batch_upsert"
    MARK_COMPLETED = "mark_completed"
    MARK_CONFIRMED = "mark_confirmed"
    MARK_IGNORED = "mark_ignored"
    UNMARK_IGNORED = "unmark_ignored"
    WRITE_EVENT = "write_event"


class WriteRequest:
    """写入请求"""
    
    def __init__(self, operation: WriteOperation, data: dict, 
                 callback: Callable[[bool, Optional[str]], None] = None):
        """
        创建写入请求
        
        参数:
            operation: 操作类型
            data: 操作数据
            callback: 完成回调 (success, error_message)
        """
        self.id = str(uuid.uuid4())
        self.operation = operation
        self.data = data
        self.callback = callback
        self.timestamp = time.time()
        self.result = None
        self.error = None


class WriteQueue:
    """写入队列管理器"""
    
    def __init__(self, db_path: str = None, batch_interval: float = 1.0, 
                 max_batch_size: int = 50, enabled: bool = True):
        """
        初始化写入队列
        
        参数:
            db_path: 数据库路径
            batch_interval: 批量写入间隔（秒）
            max_batch_size: 单批最大任务数
            enabled: 是否启用队列（禁用时直接执行）
        """
        self._queue: queue.Queue = queue.Queue()
        self._db_path = db_path
        self._batch_interval = batch_interval
        self._max_batch_size = max_batch_size
        self._enabled = enabled
        
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # 统计信息
        self._stats = {
            'total_requests': 0,
            'total_batches': 0,
            'total_success': 0,
            'total_failed': 0,
            'last_batch_time': None,
            'last_batch_size': 0,
        }
    
    def is_enabled(self) -> bool:
        """检查队列是否启用"""
        return self._enabled
    
    def set_enabled(self, enabled: bool):
        """设置队列是否启用"""
        self._enabled = enabled
        if enabled and not self._running:
            self.start()
        elif not enabled and self._running:
            self.stop()
    
    def set_db_path(self, db_path: str):
        """设置数据库路径"""
        self._db_path = db_path
    
    def start(self):
        """启动后台写入线程"""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._worker_loop, 
                daemon=True,
                name="RegistryWriteQueue"
            )
            self._worker_thread.start()
            print("[WriteQueue] 后台写入线程已启动")
    
    def stop(self, timeout: float = 5.0):
        """停止后台写入线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)
            self._worker_thread = None
            print("[WriteQueue] 后台写入线程已停止")
    
    def enqueue(self, operation: WriteOperation, data: dict, 
                callback: Callable[[bool, Optional[str]], None] = None,
                wait: bool = False) -> str:
        """
        将写入操作加入队列
        
        参数:
            operation: 操作类型
            data: 操作数据
            callback: 完成回调（可选）
            wait: 是否等待完成（默认False）
            
        返回:
            请求ID
        """
        request = WriteRequest(operation, data, callback)
        self._stats['total_requests'] += 1
        
        if not self._enabled:
            # 队列禁用，直接执行
            self._execute_single(request)
            return request.id
        
        # 加入队列
        self._queue.put(request)
        
        if wait:
            # 等待完成（简单实现：轮询检查）
            deadline = time.time() + 30  # 最多等30秒
            while request.result is None and time.time() < deadline:
                time.sleep(0.1)
        
        return request.id
    
    def enqueue_batch(self, requests: List[tuple]) -> List[str]:
        """
        批量加入队列
        
        参数:
            requests: [(operation, data, callback), ...]
            
        返回:
            请求ID列表
        """
        ids = []
        for item in requests:
            if len(item) == 2:
                op, data = item
                callback = None
            else:
                op, data, callback = item
            
            ids.append(self.enqueue(op, data, callback))
        return ids
    
    def _worker_loop(self):
        """后台工作线程"""
        while self._running:
            batch = []
            
            # 收集一批请求
            deadline = time.time() + self._batch_interval
            while len(batch) < self._max_batch_size and time.time() < deadline:
                try:
                    request = self._queue.get(timeout=0.1)
                    batch.append(request)
                except queue.Empty:
                    continue
            
            # 批量执行
            if batch:
                self._process_batch(batch)
    
    def _process_batch(self, batch: List[WriteRequest]):
        """处理一批写入请求"""
        if not self._db_path:
            print("[WriteQueue] 错误：数据库路径未设置")
            for request in batch:
                request.result = False
                request.error = "数据库路径未设置"
                if request.callback:
                    request.callback(False, request.error)
            return
        
        self._stats['total_batches'] += 1
        self._stats['last_batch_time'] = datetime.now().isoformat()
        self._stats['last_batch_size'] = len(batch)
        
        print(f"[WriteQueue] 处理批次: {len(batch)}个请求")
        
        try:
            from registry.db import get_write_connection, invalidate_read_cache
            
            conn = get_write_connection(self._db_path)
            
            try:
                # 开始事务
                conn.execute("BEGIN IMMEDIATE")
                
                success_count = 0
                for request in batch:
                    try:
                        self._execute_in_transaction(conn, request)
                        request.result = True
                        success_count += 1
                    except Exception as e:
                        request.result = False
                        request.error = str(e)
                        print(f"[WriteQueue] 单个请求失败: {e}")
                
                # 提交事务
                conn.commit()
                
                # 写入成功，使读缓存失效
                invalidate_read_cache()
                
                self._stats['total_success'] += success_count
                self._stats['total_failed'] += len(batch) - success_count
                
                # 执行回调
                for request in batch:
                    if request.callback:
                        try:
                            request.callback(request.result, request.error)
                        except Exception as e:
                            print(f"[WriteQueue] 回调执行失败: {e}")
                
                print(f"[WriteQueue] 批次完成: {success_count}/{len(batch)}成功")
                
            except Exception as e:
                conn.rollback()
                print(f"[WriteQueue] 批量写入失败，已回滚: {e}")
                
                self._stats['total_failed'] += len(batch)
                
                # 所有请求标记失败
                for request in batch:
                    request.result = False
                    request.error = str(e)
                    if request.callback:
                        try:
                            request.callback(False, str(e))
                        except:
                            pass
                
        except Exception as e:
            print(f"[WriteQueue] 获取连接失败: {e}")
            for request in batch:
                request.result = False
                request.error = str(e)
                if request.callback:
                    try:
                        request.callback(False, str(e))
                    except:
                        pass
    
    def _execute_single(self, request: WriteRequest):
        """直接执行单个请求（队列禁用时使用）"""
        if not self._db_path:
            request.result = False
            request.error = "数据库路径未设置"
            if request.callback:
                request.callback(False, request.error)
            return
        
        try:
            from registry.db import get_write_connection, invalidate_read_cache
            
            conn = get_write_connection(self._db_path)
            self._execute_in_transaction(conn, request)
            conn.commit()
            
            invalidate_read_cache()
            
            request.result = True
            self._stats['total_success'] += 1
            
            if request.callback:
                request.callback(True, None)
                
        except Exception as e:
            request.result = False
            request.error = str(e)
            self._stats['total_failed'] += 1
            
            if request.callback:
                request.callback(False, str(e))
    
    def _execute_in_transaction(self, conn, request: WriteRequest):
        """在事务中执行单个写入操作"""
        op = request.operation
        data = request.data
        
        if op == WriteOperation.UPSERT_TASK:
            self._do_upsert_task(conn, data)
        elif op == WriteOperation.BATCH_UPSERT:
            self._do_batch_upsert(conn, data)
        elif op == WriteOperation.MARK_COMPLETED:
            self._do_mark_completed(conn, data)
        elif op == WriteOperation.MARK_CONFIRMED:
            self._do_mark_confirmed(conn, data)
        elif op == WriteOperation.MARK_IGNORED:
            self._do_mark_ignored(conn, data)
        elif op == WriteOperation.UNMARK_IGNORED:
            self._do_unmark_ignored(conn, data)
        elif op == WriteOperation.WRITE_EVENT:
            self._do_write_event(conn, data)
        else:
            raise ValueError(f"未知操作类型: {op}")
    
    def _do_upsert_task(self, conn, data: dict):
        """执行任务upsert"""
        # 调用 service 层的实际逻辑
        from registry.service import upsert_task
        upsert_task(
            conn=conn,
            key=data['key'],
            fields=data['fields']
        )
    
    def _do_batch_upsert(self, conn, data: dict):
        """执行批量upsert"""
        from registry.service import batch_upsert_tasks
        batch_upsert_tasks(
            db_path=data.get('db_path', self._db_path),
            wal=data.get('wal', False),
            tasks=data['tasks'],
            current_user=data.get('current_user', ''),
            conn=conn
        )
    
    def _do_mark_completed(self, conn, data: dict):
        """标记完成"""
        from registry.service import mark_task_completed
        mark_task_completed(
            db_path=data.get('db_path', self._db_path),
            wal=data.get('wal', False),
            file_type=data['file_type'],
            project_id=data['project_id'],
            interface_id=data['interface_id'],
            source_file=data['source_file'],
            row_index=data['row_index'],
            completed_by=data.get('completed_by', ''),
            response_number=data.get('response_number'),
            conn=conn
        )
    
    def _do_mark_confirmed(self, conn, data: dict):
        """标记确认"""
        from registry.service import mark_task_confirmed
        mark_task_confirmed(
            db_path=data.get('db_path', self._db_path),
            wal=data.get('wal', False),
            file_type=data['file_type'],
            project_id=data['project_id'],
            interface_id=data['interface_id'],
            source_file=data['source_file'],
            row_index=data['row_index'],
            confirmed_by=data.get('confirmed_by', ''),
            conn=conn
        )
    
    def _do_mark_ignored(self, conn, data: dict):
        """标记忽略"""
        from registry.service import mark_task_ignored
        mark_task_ignored(
            db_path=data.get('db_path', self._db_path),
            wal=data.get('wal', False),
            file_type=data['file_type'],
            project_id=data['project_id'],
            interface_id=data['interface_id'],
            source_file=data['source_file'],
            row_index=data['row_index'],
            ignored_by=data.get('ignored_by', ''),
            reason=data.get('reason', ''),
            conn=conn
        )
    
    def _do_unmark_ignored(self, conn, data: dict):
        """取消忽略"""
        from registry.service import unmark_task_ignored
        unmark_task_ignored(
            db_path=data.get('db_path', self._db_path),
            wal=data.get('wal', False),
            file_type=data['file_type'],
            project_id=data['project_id'],
            interface_id=data['interface_id'],
            source_file=data['source_file'],
            row_index=data['row_index'],
            conn=conn
        )
    
    def _do_write_event(self, conn, data: dict):
        """写入事件"""
        from registry.service import write_event
        write_event(
            conn=conn,
            event=data['event'],
            file_type=data['file_type'],
            project_id=data['project_id'],
            interface_id=data.get('interface_id'),
            operator=data.get('operator', ''),
            detail=data.get('detail')
        )
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return dict(self._stats)
    
    def get_queue_size(self) -> int:
        """获取队列中待处理的请求数"""
        return self._queue.qsize()
    
    def flush(self, timeout: float = 10.0) -> bool:
        """
        刷新队列，等待所有请求处理完成
        
        参数:
            timeout: 最大等待时间（秒）
            
        返回:
            True = 队列已清空，False = 超时
        """
        deadline = time.time() + timeout
        while self._queue.qsize() > 0 and time.time() < deadline:
            time.sleep(0.1)
        return self._queue.qsize() == 0


# 模块级单例
_write_queue: Optional[WriteQueue] = None
_queue_lock = threading.Lock()


def get_write_queue(db_path: str = None) -> WriteQueue:
    """
    获取全局写入队列单例
    
    参数:
        db_path: 数据库路径（首次调用时必须提供）
    
    返回:
        WriteQueue 实例
    """
    global _write_queue
    
    with _queue_lock:
        if _write_queue is None:
            from registry.config import get_config
            config = get_config()
            
            _write_queue = WriteQueue(
                db_path=db_path,
                batch_interval=config.get('registry_write_batch_interval', 1.0),
                max_batch_size=config.get('registry_write_batch_size', 50),
                enabled=config.get('registry_write_queue_enabled', True)
            )
            
            if _write_queue.is_enabled():
                _write_queue.start()
        
        if db_path and _write_queue._db_path != db_path:
            _write_queue.set_db_path(db_path)
        
        return _write_queue


def shutdown_write_queue():
    """关闭写入队列"""
    global _write_queue
    with _queue_lock:
        if _write_queue:
            _write_queue.flush(timeout=5.0)
            _write_queue.stop()
            _write_queue = None

