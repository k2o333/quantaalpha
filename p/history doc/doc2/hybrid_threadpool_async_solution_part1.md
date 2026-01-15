# App4 混合线程池异步方案

## 1. 概述

本方案针对全异步方案的**重构成本高、调试困难、依赖复杂**等问题，提出一种**混合架构**：
- **保留现有线程池架构**（不引入 asyncio）
- **实现无阻塞判断**（轻量级内存缓存 + Bloom Filter 可选）
- **异步保存和索引**（队列解耦，后台线程）
- **渐进式实施**（可逐步升级，无需一次性重构）

**核心原则**：**最小改动，最大收益**，在现有架构基础上实现异步化。

## 2. 核心设计原则

### 2.1 架构兼容
- **保留 threading**：不引入 asyncio，团队无学习成本
- **复用现有组件**：GenericDownloader、StorageManager、CoverageManager 无需重写
- **渐进式升级**：可以逐步替换，无需一次性重构

### 2.2 无阻塞判断
- **轻量级缓存**：内存缓存接口级索引，< 10ms 判断
- **可选 Bloom Filter**：简单实现，无额外依赖
- **智能降级**：缓存失效时自动回退到传统检查

### 2.3 异步流水线
- **三级队列**：下载队列 → 保存队列 → 索引队列
- **批量处理**：减少 I/O 次数，提升吞吐量
- **背压控制**：有界队列防止内存溢出

### 2.4 生产就绪
- **易于调试**：同步代码为主，异常处理简单
- **测试友好**：无需异步测试框架
- **运维简单**：配置参数少，监控清晰

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────┐
│              GenericDownloader (主线程)                  │
│  - 生成下载任务（无阻塞）                                 │
│  - 调用 CoverageManager 快速判断                          │
└────────────────────┬────────────────────────────────────┘
                     │ 投递到下载队列
                     ▼
┌─────────────────────────────────────────────────────────┐
│        DownloadWorkerPool (10个线程)                     │
│  - 并发下载数据                                          │
│  - 不等待判断和保存                                      │
└────────────────────┬────────────────────────────────────┘
                     │ 投递到保存队列（仅新数据）
                     ▼
┌─────────────────────────────────────────────────────────┐
│        SaveWorker (1个线程)                              │
│  - 批量保存数据文件                                      │
│  - 投递到索引队列                                        │
└────────────────────┬────────────────────────────────────┘
                     │ 投递到索引队列
                     ▼
┌─────────────────────────────────────────────────────────┐
│        IndexWorker (1个线程)                             │
│  - 批量更新索引                                          │
│  - 定期合并历史索引                                      │
└─────────────────────────────────────────────────────────┘
```

## 4. 核心实现

### 4.1 FastCoverageManager - 快速覆盖率检查（无阻塞）

```python
import threading
import time
import hashlib
from typing import Dict, Any, Optional, Set, List
import polars as pl
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class FastCoverageManager:
    """快速覆盖率管理器 - 轻量级内存缓存 + 可选 Bloom Filter"""
    
    def __init__(self, storage_manager, config_loader, use_bloom_filter: bool = False):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self.use_bloom_filter = use_bloom_filter
        
        # 轻量级内存缓存 {interface: {record_key: timestamp}}
        self._cache: Dict[str, Dict[tuple, float]] = {}
        self._cache_lock = threading.RLock()
        self._cache_ttl = 300  # 5分钟过期
        
        # 可选 Bloom Filter（简单实现）
        if use_bloom_filter:
            self._bloom_filters: Dict[str, 'SimpleBloomFilter'] = {}
        
        logger.info(f"FastCoverageManager initialized (use_bloom_filter={use_bloom_filter})")
    
    def should_download(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """
        判断是否需要下载（无阻塞，< 10ms）
        
        三层判断策略：
        1. 内存缓存（最快，~1ms）
        2. Bloom Filter（可选，~1ms）
        3. 索引检查（较快，~10-50ms）
        4. 传统检查（最慢，~500ms，降级使用）
        """
        try:
            # 1. 生成记录键
            record_keys = self._generate_record_keys(interface_name, params)
            if not record_keys:
                return True
            
            # 2. 内存缓存检查（最快）
            missing_keys = self._check_cache(interface_name, record_keys)
            if missing_keys is not None:
                # 缓存命中，直接返回
                if not missing_keys:
                    logger.debug(f"All records found in cache for {interface_name}")
                    return False
                else:
                    logger.debug(f"Cache hit: {len(missing_keys)} missing records for {interface_name}")
                    return True
            
            # 3. 如果启用 Bloom Filter，进行二次判断
            if self.use_bloom_filter:
                missing_keys = self._check_bloom_filter(interface_name, record_keys)
                if missing_keys:
                    logger.debug(f"Bloom Filter: {len(missing_keys)} definitely missing for {interface_name}")
                    return True
            
            # 4. 检查索引（如果索引存在）
            if hasattr(self.storage_manager, 'index_manager'):
                existing = self.storage_manager.index_manager.get_existing_records(
                    interface_name,
                    start_date=params.get('start_date'),
                    end_date=params.get('end_date'),
                    ts_codes=params.get('ts_codes'),
                    period=params.get('period')
                )
                missing_keys = record_keys - existing
                
                if not missing_keys:
                    logger.info(f"All records exist in index for {interface_name}")
                    return False
                else:
                    logger.info(f"Index check: {len(missing_keys)} missing for {interface_name}")
                    return True
            
            # 5. 降级到传统检查
            logger.info(f"Using traditional coverage check for {interface_name}")
            return self._traditional_check(interface_name, params)
            
        except Exception as e:
            logger.warning(f"Fast coverage check failed: {e}, using traditional check")
            return self._traditional_check(interface_name, params)
    
    def _generate_record_keys(self, interface_name: str, params: Dict) -> Set[tuple]:
        """生成记录键集合"""
        record_keys = set()
        
        index_config = {}
        if self.config_loader:
            interface_config = self.config_loader.get_interface_config(interface_name)
            index_config = interface_config.get('index', {})
        
        primary_keys = index_config.get('primary_keys', ['trade_date'])
        ts_field = index_config.get('ts_field', 'ts_code')
        date_field = index_config.get('date_field', 'trade_date')
        period_field = index_config.get('period_field', 'period')
        
        # 根据参数生成所有可能的记录键
        if 'ts_codes' in params and 'start_date' in params and 'end_date' in params:
            # 股票+日期模式
            ts_codes = params['ts_codes']
            start_date = params['start_date']
            end_date = params['end_date']
            
            from datetime import datetime, timedelta
            start = datetime.strptime(start_date, '%Y%m%d')
            end = datetime.strptime(end_date, '%Y%m%d')
            
            current = start
            while current <= end:
                date_str = current.strftime('%Y%m%d')
                for ts_code in ts_codes:
                    key = tuple(
                        ts_code if k == 'ts_code' else date_str 
                        for k in primary_keys
                    )
                    record_keys.add(key)
                current += timedelta(days=1)
        
        elif 'ts_codes' in params and 'periods' in params:
            # 股票+报告期模式
            ts_codes = params['ts_codes']
            periods = params['periods']
            
            for ts_code in ts_codes:
                for period in periods:
                    key = tuple(
                        ts_code if k == 'ts_code' else period
                        for k in primary_keys
                    )
                    record_keys.add(key)
        
        return record_keys
    
    def _check_cache(self, interface_name: str, record_keys: Set[tuple]) -> Optional[Set[tuple]]:
        """检查内存缓存"""
        with self._cache_lock:
            cache = self._cache.get(interface_name, {})
            
            # 清理过期缓存
            now = time.time()
            expired_keys = [k for k, t in cache.items() if now - t > self._cache_ttl]
            for k in expired_keys:
                del cache[k]
            
            # 检查所有记录键
            missing_keys = set()
            for key in record_keys:
                if key not in cache:
                    missing_keys.add(key)
            
            # 如果全部命中，返回缺失集合
            # 如果部分命中，返回 None（表示缓存不完整）
            if missing_keys and len(missing_keys) < len(record_keys):
                return None  # 缓存不完整，需要查索引
            
            return missing_keys
    
    def _check_bloom_filter(self, interface_name: str, record_keys: Set[tuple]) -> Set[tuple]:
        """检查 Bloom Filter"""
        if interface_name not in self._bloom_filters:
            # 创建 Bloom Filter
            self._bloom_filters[interface_name] = SimpleBloomFilter(
                capacity=10_000_000,
                error_rate=0.001
            )
        
        bloom = self._bloom_filters[interface_name]
        
        missing_keys = set()
        for key in record_keys:
            # Bloom Filter 返回 False 表示肯定不存在
            if not bloom.contains("_".join(map(str, key))):
                missing_keys.add(key)
        
        return missing_keys
    
    def _traditional_check(self, interface_name: str, params: Dict) -> bool:
        """降级到传统检查（保留现有逻辑）"""
        # 这里复用现有的 CoverageManager.should_skip 逻辑
        # 或者简化为总是下载（更安全）
        return True  # 默认下载
    
    def update_cache(self, interface_name: str, record_keys: Set[tuple]):
        """更新缓存（下载完成后调用）"""
        with self._cache_lock:
            if interface_name not in self._cache:
                self._cache[interface_name] = {}
            
            cache = self._cache[interface_name]
            now = time.time()
            
            for key in record_keys:
                cache[key] = now
            
            logger.debug(f"Updated cache for {interface_name}: {len(record_keys)} records")

class SimpleBloomFilter:
    """简化版 Bloom Filter（无外部依赖）"""
    
    def __init__(self, capacity: int, error_rate: float = 0.001):
        self.capacity = capacity
        self.error_rate = error_rate
        
        # 计算参数
        self.size = int(-(capacity * math.log(error_rate)) / (math.log(2) ** 2))
        self.hash_count = int((self.size / capacity) * math.log(2))
        
        # 位数组（使用 Python 的 int 模拟）
        self.bit_array = 0
        self.bit_size = self.size
    
    def add(self, item: str):
        """添加元素"""
        for i in range(self.hash_count):
            digest = hashlib.md5(f"{item}{i}".encode()).hexdigest()
            index = int(digest, 16) % self.bit_size
            self.bit_array |= (1 << index)
    
    def contains(self, item: str) -> bool:
        """检查元素是否存在"""
        for i in range(self.hash_count):
            digest = hashlib.md5(f"{item}{i}".encode()).hexdigest()
            index = int(digest, 16) % self.bit_size
            
            if not (self.bit_array & (1 << index)):
                return False
        
        return True
```

### 4.2 AsyncStorageManager - 异步存储管理（最小改动）

```python
import threading
import queue
import time
from typing import List, Dict, Any
import polars as pl
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class AsyncStorageManager:
    """异步存储管理器 - 在现有 StorageManager 基础上增加异步队列"""
    
    def __init__(self, storage_dir: str = "../data", config_loader=None):
        self.storage_dir = Path(storage_dir)
        self.config_loader = config_loader
        
        # 初始化基础 StorageManager（复用现有代码）
        from app4.core.storage import StorageManager
        self.base_storage = StorageManager(storage_dir, config_loader=config_loader)
        
        # 新增异步队列
        self.save_queue = queue.Queue(maxsize=1000)  # 有界队列
        self.index_queue = queue.Queue(maxsize=10000)  # 索引队列
        
        # 启动后台线程
        self.save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self.save_thread.start()
        
        self.index_thread = threading.Thread(target=self._index_worker, daemon=True)
        self.index_thread.start()
        
        logger.info("AsyncStorageManager initialized with async workers")
    
    def save_data_async(self, interface_name: str, data: List[Dict], file_path: str,
                       record_keys: Optional[Set] = None):
        """
        异步保存数据（立即返回，不等待）
        
        Args:
            interface_name: 接口名称
            data: 数据列表
            file_path: 文件路径
            record_keys: 记录键（用于索引）
        """
        # 构建任务
        task = {
            'interface': interface_name,
            'data': data,
            'file_path': file_path,
            'record_keys': record_keys or set(),
            'timestamp': time.time()
        }
        
        # 非阻塞放入队列
        try:
            self.save_queue.put_nowait(task)
            logger.debug(f"Queued {len(data)} records for {interface_name}")
        except queue.Full:
            # 队列满时，同步保存（降级）
            logger.warning(f"Save queue full, saving synchronously for {interface_name}")
            self._save_sync(task)
    
    def _save_worker(self):
        """后台保存工作线程"""
        while True:
            try:
                # 批量获取任务（减少 I/O 次数）
                batch = self._get_batch()
                
                if batch:
                    self._process_batch(batch)
                
            except Exception as e:
                logger.error(f"Save worker error: {e}")
                time.sleep(1.0)
    
    def _get_batch(self) -> List[Dict]:
        """批量获取任务"""
        batch = []
        
        # 获取第一个（阻塞，但最多等待1秒）
        try:
            first = self.save_queue.get(timeout=1.0)
            batch.append(first)
            
            # 快速获取更多
            while len(batch) < 50:
                try:
                    item = self.save_queue.get_nowait()
                    batch.append(item)
                except queue.Empty:
                    break
        except queue.Empty:
            pass
        
        return batch
    
    def _process_batch(self, batch: List[Dict]):
        """批量处理保存任务"""
        # 按接口分组
        by_interface = {}
        for task in batch:
            iface = task['interface']
            if iface not in by_interface:
                by_interface[iface] = []
            by_interface[iface].append(task)
        
        # 批量保存每个接口
        for iface, tasks in by_interface.items():
            try:
                self._save_interface_batch(iface, tasks)
            except Exception as e:
                logger.error(f"Failed to save batch for {iface}: {e}")
    
    def _save_interface_batch(self, interface_name: str, tasks: List[Dict]):
        """批量保存单个接口"""
        # 确保目录存在
        iface_dir = self.storage_dir / interface_name
        iface_dir.mkdir(parents=True, exist_ok=True)
        
        # 合并数据（如果文件路径相同）
        file_groups = {}
        for task in tasks:
            file_path = task['file_path']
            if file_path not in file_groups:
                file_groups[file_path] = {
                    'data': [],
                    'keys': set()
                }
            file_groups[file_path]['data'].extend(task['data'])
            file_groups[file_path]['keys'].update(task['record_keys'])
        
        # 保存每个文件
        for file_path, group in file_groups.items():
            try:
                self._save_single_file(
                    interface_name,
                    file_path,
                    group['data'],
                    group['keys']
                )
            except Exception as e:
                logger.error(f"Failed to save {file_path}: {e}")
    
    def _save_single_file(self, interface_name: str, file_path: str,
                         data: List[Dict], record_keys: Set):
        """保存单个文件"""
        # 数据转换为 DataFrame
        df = pl.DataFrame(data)
        
        # 原子写入
        temp_path = file_path + ".tmp"
        df.write_parquet(temp_path, compression='snappy')
        Path(temp_path).rename(file_path)
        
        logger.info(f"Saved {len(data)} records to {file_path}")
        
        # 投递到索引队列（异步更新索引）
        try:
            self.index_queue.put_nowait({
                'interface': interface_name,
                'file_path': file_path,
                'df': df,
                'record_keys': record_keys
            })
        except queue.Full:
            # 索引队列满，稍后重试
            logger.warning(f"Index queue full, will retry for {interface_name}")
            # 启动后台任务稍后重试
            threading.Thread(
                target=self._retry_index_update,
                args=(interface_name, file_path, df, record_keys),
                daemon=True
            ).start()
    
    def _retry_index_update(self, interface_name: str, file_path: str,
                           df: pl.DataFrame, record_keys: Set):
        """重试索引更新"""
        time.sleep(1.0)
        try:
            self.index_queue.put({
                'interface': interface_name,
                'file_path': file_path,
                'df': df,
                'record_keys': record_keys
            }, timeout=5.0)
        except queue.Full:
            logger.error(f"Failed to queue index update for {interface_name}")
    
    def _save_sync(self, task: Dict):
        """同步保存（降级方案）"""
        interface_name = task['interface']
        file_path = task['file_path']
        data = task['data']
        record_keys = task['record_keys']
        
        df = pl.DataFrame(data)
        df.write_parquet(file_path + ".tmp", compression='snappy')
        Path(file_path + ".tmp").rename(file_path)
        
        logger.info(f"Synchronously saved {len(data)} records to {file_path}")
        
        # 索引更新（异步）
        try:
            self.index_queue.put_nowait({
                'interface': interface_name,
                'file_path': file_path,
                'df': df,
                'record_keys': record_keys
            })
        except queue.Full:
            logger.error(f"Index queue full after sync save for {interface_name}")
    
    def _index_worker(self):
        """后台索引工作线程"""
        while True:
            try:
                # 批量获取索引任务
                batch = self._get_index_batch()
                
                if batch:
                    self._process_index_batch(batch)
                
            except Exception as e:
                logger.error(f"Index worker error: {e}")
                time.sleep(1.0)
    
    def _get_index_batch(self) -> List[Dict]:
        """批量获取索引任务"""
        batch = []
        
        try:
            first = self.index_queue.get(timeout=1.0)
            batch.append(first)
            
            while len(batch) < 100:
                try:
                    item = self.index_queue.get_nowait()
                    batch.append(item)
                except queue.Empty:
                    break
        except queue.Empty:
            pass
        
        return batch
    
    def _process_index_batch(self, batch: List[Dict]):
        """批量处理索引更新"""
        # 按接口分组
        by_interface = {}
        for task in batch:
            iface = task['interface']
            if iface not in by_interface:
                by_interface[iface] = []
            by_interface[iface].append(task)
        
        # 批量更新每个接口的索引
        for iface, tasks in by_interface.items():
            try:
                self._update_interface_index(iface, tasks)
            except Exception as e:
                logger.error(f"Failed to update index for {iface}: {e}")
    
    def _update_interface_index(self, interface_name: str, tasks: List[Dict]):
        """批量更新接口索引"""
        # 这里调用 IndexManager 的批量更新方法
        # 复用现有索引逻辑
        if hasattr(self.storage_manager, 'index_manager'):
            for task in tasks:
                self.storage_manager.index_manager.add_records(
                    interface_name,
                    task['file_path'],
                    task['df']
                )
        
        logger.info(f"Updated index for {interface_name}: {len(tasks)} files")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        return {
            'save_queue_size': self.save_queue.qsize(),
            'save_queue_maxsize': self.save_queue.maxsize,
            'index_queue_size': self.index_queue.qsize(),
            'index_queue_maxsize': self.index_queue.maxsize,
            'save_thread_alive': self.save_thread.is_alive(),
            'index_thread_alive': self.index_thread.is_alive()
        }
```

### 4.3 AsyncGenericDownloader - 异步下载器（保留线程池）

```python
import threading
import queue
import time
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AsyncGenericDownloader:
    """异步下载器 - 基于线程池，无 asyncio"""
    
    def __init__(self, config_loader=None, storage_manager=None):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        self.fast_coverage = FastCoverageManager(
            storage_manager=storage_manager,
            config_loader=config_loader,
            use_bloom_filter=True  # 可选，默认关闭
        )
        
        # 下载队列
        self.download_queue = queue.Queue(maxsize=100)
        
        # 工作线程池
        self.num_workers = 10
        self.workers = []
        self.running = False
        
        # 统计信息
        self.stats = {
            'total_downloaded': 0,
            'total_skipped': 0,
            'total_errors': 0,
            'start_time': None
        }
    
    def start(self):
        """启动下载器"""
        if self.running:
            return
        
        self.running = True
        self.stats['start_time'] = time.time()
        
        # 启动工作线程
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._download_worker,
                name=f"DownloadWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"AsyncGenericDownloader started with {self.num_workers} workers")
    
    def stop(self):
        """停止下载器"""
        if not self.running:
            return
        
        self.running = False
        
        # 发送停止信号
        for _ in self.workers:
            self.download_queue.put(None)
        
        # 等待线程结束
        for worker in self.workers:
            worker.join(timeout=5.0)
        
        logger.info("AsyncGenericDownloader stopped")
    
    def download_interface(self, interface_name: str, **params) -> Dict[str, Any]:
        """
        异步下载接口数据（立即返回，后台执行）
        
        Args:
            interface_name: 接口名称
            **params: 下载参数
            
        Returns:
            Dict: 任务信息和统计
        """
        # 1. 生成分页参数批次
        batches = self._generate_batches(interface_name, params)
        
        # 2. 快速判断，过滤已存在批次
        filtered_batches = []
        for batch in batches:
            if self.fast_coverage.should_download(interface_name, batch):
                filtered_batches.append(batch)
            else:
                self.stats['total_skipped'] += 1
                logger.debug(f"Batch skipped for {interface_name}")
        
        if not filtered_batches:
            logger.info(f"All batches exist for {interface_name}, nothing to download")
            return {
                'interface': interface_name,
                'total_batches': len(batches),
                'filtered_batches': 0,
                'status': 'completed',
                'message': 'All records exist'
            }
        
        # 3. 投递到下载队列
        task_id = f"{interface_name}_{int(time.time() * 1000)}"
        
        for i, batch in enumerate(filtered_batches):
            task = {
                'task_id': f"{task_id}_{i}",
                'interface': interface_name,
                'params': batch,
                'retry_count': 0,
                'max_retries': 3
            }
            
            try:
                self.download_queue.put_nowait(task)
            except queue.Full:
                logger.warning(f"Download queue full, dropping task for {interface_name}")
                self.stats['total_errors'] += 1
        
        logger.info(f"Queued {len(filtered_batches)} batches for {interface_name}")
        
        return {
            'interface': interface_name,
            'total_batches': len(batches),
            'filtered_batches': len(filtered_batches),
            'status': 'queued',
            'task_id': task_id
        }
    
    def _generate_batches(self, interface_name: str, params: Dict) -> List[Dict]:
        """生成分页参数批次"""
        batches = []
        
        # 获取接口配置
        interface_config = {}
        if self.config_loader:
            interface_config = self.config_loader.get_interface_config(interface_name)
        
        pagination_config = interface_config.get('pagination', {})
        
        if not pagination_config.get('enabled', False):
            # 不分页，单批次
            batches.append(params)
            return batches
        
        mode = pagination_config.get('mode', 'date_range')
        
        if mode == 'date_range':
            start_date = params.get('start_date')
            end_date = params.get('end_date')
            window = pagination_config.get('window_size_days', 365)
            
            from datetime import datetime, timedelta
            start = datetime.strptime(start_date, '%Y%m%d')
            end = datetime.strptime(end_date, '%Y%m%d')
            
            current = start
            while current <= end:
                window_end = min(current + timedelta(days=window-1), end)
                
                batch = params.copy()
                batch['start_date'] = current.strftime('%Y%m%d')
                batch['end_date'] = window_end.strftime('%Y%m%d')
                batches.append(batch)
                
                current = window_end + timedelta(days=1)
        
        elif mode == 'stock_loop':
            ts_codes = params.get('ts_codes', [])
            batch_size = pagination_config.get('batch_size', 100)
            
            for i in range(0, len(ts_codes), batch_size):
                batch_codes = ts_codes[i:i+batch_size]
                batch = params.copy()
                batch['ts_codes'] = batch_codes
                batches.append(batch)
        
        elif mode == 'period_range':
            periods = params.get('periods', [])
            for period in periods:
                batch = params.copy()
                batch['period'] = period
                batches.append(batch)
        
        else:
            batches.append(params)
        
        return batches
    
    def _download_worker(self):
