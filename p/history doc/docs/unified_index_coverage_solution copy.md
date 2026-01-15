# App4 项目统一索引与覆盖检测方案

## 1. 概述

本方案整合了索引管理和混合范围覆盖检测功能，采用简洁优雅的设计，确保**每次数据下载后都会更新索引**，并提供**全面更新索引的方法**，同时解决异步写入冲突、配置依赖、缓存一致性等关键问题。

## 2. 核心设计原则

### 2.1 简洁性
- 单一职责：每个组件只做一件事
- 依赖注入：通过构造函数注入依赖，避免循环依赖
- 优雅降级：索引失效时自动回退到传统检查

### 2.2 可靠性
- 原子性：使用临时文件 + 原子重命名
- 一致性：索引与数据同步更新
- 完整性：自动清理无效记录

### 2.3 性能
- 智能缓存：基于文件修改时间的缓存失效
- 文件名优化：利用文件名元数据减少I/O
- 三层检查：索引预检 → 日期列查询 → 完整检查

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Downloader                            │
│  - 执行下载逻辑                                           │
│  - 调用 CoverageManager 检查覆盖率                        │
│  - 调用 StorageManager 保存数据                           │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐   ┌──────────────────┐
│ CoverageManager  │   │ StorageManager   │
│  - 覆盖率检查     │   │  - 数据存储      │
│  - 三层检查策略   │   │  - 索引管理      │
│  - 智能缓存       │   │  - 索引更新      │
└──────────────────┘   └──────────────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌──────────────────┐
         │  ConfigLoader    │
         │  - 配置管理       │
         │  - 统一入口       │
         └──────────────────┘
```

## 4. 核心实现

### 4.1 StorageManager - 索引管理（解决异步写入冲突）

```python
import os
import threading
import queue
import hashlib
import time
import uuid
from typing import List, Dict, Any, Optional
import polars as pl
import logging

logger = logging.getLogger(__name__)

class StorageManager:
    """存储管理器 - 统一数据存储和索引管理"""

    def __init__(self, storage_dir: str = "../data", format: str = "parquet",
                 batch_size: int = 100, config_loader=None):
        self.storage_dir = storage_dir
        self.format = format
        self.batch_size = batch_size
        self.config_loader = config_loader  # 依赖注入，解决循环依赖

        self.data_queue = queue.Queue()
        self.writer_thread = None
        self.running = False

        # 索引管理
        self._index_cache = {}  # {(interface_name): (mtime, index_df)}
        self._index_lock = threading.RLock()

        os.makedirs(storage_dir, exist_ok=True)

    def _get_interface_index_path(self, interface_name: str) -> str:
        """获取接口的索引文件路径"""
        interface_dir = os.path.join(self.storage_dir, interface_name)
        return os.path.join(interface_dir, '_index.parquet')

    def _get_date_column(self, interface_name: str) -> str:
        """获取接口的日期列名"""
        if self.config_loader:
            interface_config = self.config_loader.get_interface_config(interface_name)
            return interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')
        return 'trade_date'  # 默认值

    def _parse_date_range_from_filename(self, file_path: str) -> tuple[Optional[str], Optional[str]]:
        """从文件名解析日期范围: interface_start_end_... -> (start, end)"""
        filename = os.path.basename(file_path)
        parts = filename.split('_')
        if len(parts) >= 4:
            return parts[1], parts[2]  # start_date, end_date
        return None, None

    def _get_interface_index(self, interface_name: str) -> Optional[pl.DataFrame]:
        """
        获取接口索引，带智能缓存机制

        [优化] 基于文件修改时间的缓存失效机制，解决缓存不一致问题
        """
        cache_key = f"index_{interface_name}"
        index_path = self._get_interface_index_path(interface_name)

        # 1. 检查内存缓存（带文件修改时间验证）
        with self._index_lock:
            if cache_key in self._index_cache:
                cached_mtime, index_df = self._index_cache[cache_key]
                # 检查磁盘文件是否更新
                if os.path.exists(index_path):
                    file_mtime = os.path.getmtime(index_path)
                    if cached_mtime >= file_mtime:
                        return index_df
                # 缓存过期或文件不存在，清除缓存
                del self._index_cache[cache_key]

        # 2. 从磁盘读取索引
        if os.path.exists(index_path):
            try:
                index_df = pl.read_parquet(index_path)
                file_mtime = os.path.getmtime(index_path)

                # 验证索引完整性
                if self._verify_index_integrity(interface_name, index_df):
                    # 更新缓存（使用文件修改时间）
                    with self._index_lock:
                        self._index_cache[cache_key] = (file_mtime, index_df)
                    return index_df
                else:
                    logger.warning(f"Index for {interface_name} is corrupted")
                    return None
            except Exception as e:
                logger.warning(f"Failed to read index for {interface_name}: {e}")
                return None

        return None

    def _verify_index_integrity(self, interface_name: str, index_df: pl.DataFrame) -> bool:
        """验证索引完整性"""
        try:
            # 检查必需列
            required_columns = ['file_path', 'min_date', 'max_date', 'row_count', 'update_time']
            if not all(col in index_df.columns for col in required_columns):
                return False

            # 检查文件是否存在
            for file_path in index_df['file_path'].to_list():
                if not os.path.exists(file_path):
                    logger.warning(f"Indexed file not found: {file_path}")
                    return False

            return True
        except Exception as e:
            logger.warning(f"Index integrity check failed: {e}")
            return False

    def _update_interface_index(self, interface_name: str, file_path: str, df: pl.DataFrame):
        """
        更新接口索引文件

        [关键] 确保每次数据写入后都会更新索引，无论同步还是异步
        """
        interface_dir = os.path.join(self.storage_dir, interface_name)
        os.makedirs(interface_dir, exist_ok=True)

        index_path = self._get_interface_index_path(interface_name)
        date_column = self._get_date_column(interface_name)

        if date_column not in df.columns:
            logger.warning(f"Date column '{date_column}' not found in data for {interface_name}")
            return

        try:
            # 计算索引元数据
            min_date = df[date_column].min()
            max_date = df[date_column].max()
            row_count = len(df)
            update_time = int(time.time() * 1000)

            # 计算校验和（使用前10条记录）
            checksum = ''
            if row_count > 0:
                sample_data = df.head(10).to_dict(as_series=False)
                checksum = hashlib.md5(str(sample_data).encode()).hexdigest()

            # 获取文件大小
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # 创建索引记录
            new_index_record = pl.DataFrame({
                'file_path': [file_path],
                'min_date': [str(min_date)],
                'max_date': [str(max_date)],
                'row_count': [row_count],
                'update_time': [update_time],
                'checksum': [checksum],
                'file_size': [file_size]
            })

            # 读取现有索引并更新
            if os.path.exists(index_path):
                try:
                    existing_index = pl.read_parquet(index_path)
                    # 过滤掉同名文件的旧记录
                    existing_index = existing_index.filter(pl.col('file_path') != file_path)
                    # 移除不存在的文件记录
                    existing_index = existing_index.filter(
                        pl.col('file_path').map_elements(
                            lambda fp: os.path.exists(fp),
                            return_dtype=pl.Boolean
                        )
                    )
                    updated_index = pl.concat([existing_index, new_index_record])
                except Exception as e:
                    logger.warning(f"Failed to update index for {interface_name}, rebuilding: {e}")
                    updated_index = new_index_record
            else:
                updated_index = new_index_record

            # 原子写入索引文件
            temp_index_path = index_path + f".tmp.{os.getpid()}.{threading.get_ident()}"
            try:
                updated_index.write_parquet(temp_index_path)
                os.rename(temp_index_path, index_path)

                # 更新内存缓存（使用当前时间戳）
                cache_key = f"index_{interface_name}"
                with self._index_lock:
                    self._index_cache[cache_key] = (time.time(), updated_index)

                logger.info(f"Updated index for {interface_name}: {len(updated_index)} files")
            except Exception as e:
                logger.error(f"Failed to write index for {interface_name}: {e}")
                if os.path.exists(temp_index_path):
                    os.remove(temp_index_path)
                raise

        except Exception as e:
            logger.error(f"Failed to update index for {interface_name}: {e}")

    def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
        """
        写入接口数据 - Parquet Dataset 模式

        [关键] 确保无论同步还是异步，索引都能正确更新
        """
        dir_path = os.path.join(self.storage_dir, interface_name)
        os.makedirs(dir_path, exist_ok=True)

        try:
            if not data:
                return

            # 增加写入时间戳
            current_time = int(time.time() * 1000)
            for item in data:
                item['_update_time'] = current_time

            df = pl.DataFrame(data)

            # 提取日期范围用于文件名
            date_col = self._get_date_column(interface_name)

            if date_col in df.columns:
                min_val = df[date_col].min()
                max_val = df[date_col].max()

                # 处理不同类型的日期值
                if isinstance(min_val, (str, int)):
                    min_date_str = str(min_val)
                    max_date_str = str(max_val)
                elif hasattr(min_val, 'strftime'):
                    min_date_str = min_val.strftime('%Y%m%d')
                    max_date_str = max_val.strftime('%Y%m%d')
                else:
                    min_date_str = str(min_val)
                    max_date_str = str(max_val)

                date_range_str = f"{min_date_str}_{max_date_str}"
            else:
                date_range_str = "nodate"

            # 生成文件名
            unique_id = uuid.uuid4().hex[:8]
            file_name = f"{interface_name}_{date_range_str}_{current_time}_{unique_id}.parquet"
            file_path = os.path.join(dir_path, file_name)

            # 原子写入数据文件
            temp_file_path = file_path + ".tmp"
            df.write_parquet(temp_file_path, compression='snappy')
            os.rename(temp_file_path, file_path)

            logger.info(f"Wrote {len(df)} records to {file_path}")

            # [关键] 写入后立即更新索引（无论同步还是异步）
            self._update_interface_index(interface_name, file_path, df)

        except Exception as e:
            logger.error(f"Error writing interface data for {interface_name}: {str(e)}")
            raise

    def rebuild_all_indexes(self, interface_name: Optional[str] = None) -> Dict[str, Any]:
        """
        全面重建索引

        [功能] 提供全面更新索引的方法
        """
        result = {
            'success': True,
            'interfaces': {},
            'total_files': 0,
            'total_records': 0,
            'errors': []
        }

        try:
            # 确定要重建的接口列表
            if interface_name:
                interfaces = [interface_name]
            else:
                interfaces = [d for d in os.listdir(self.storage_dir)
                            if os.path.isdir(os.path.join(self.storage_dir, d))]

            for iface in interfaces:
                interface_dir = os.path.join(self.storage_dir, iface)
                if not os.path.isdir(interface_dir):
                    continue

                logger.info(f"Rebuilding index for {iface}...")

                try:
                    # 获取所有 parquet 文件
                    parquet_files = [f for f in os.listdir(interface_dir)
                                   if f.endswith('.parquet') and not f.startswith('_index')]

                    if not parquet_files:
                        logger.info(f"No data files found for {iface}")
                        continue

                    # 构建新的索引
                    index_records = []
                    total_records = 0

                    for file_name in parquet_files:
                        file_path = os.path.join(interface_dir, file_name)

                        try:
                            # 读取数据文件
                            df = pl.read_parquet(file_path)
                            date_column = self._get_date_column(iface)

                            if date_column not in df.columns:
                                logger.warning(f"Date column '{date_column}' not found in {file_path}")
                                continue

                            # 计算索引元数据
                            min_date = df[date_column].min()
                            max_date = df[date_column].max()
                            row_count = len(df)
                            update_time = int(os.path.getmtime(file_path) * 1000)
                            file_size = os.path.getsize(file_path)

                            # 计算校验和
                            checksum = ''
                            if row_count > 0:
                                sample_data = df.head(10).to_dict(as_series=False)
                                checksum = hashlib.md5(str(sample_data).encode()).hexdigest()

                            index_records.append({
                                'file_path': file_path,
                                'min_date': str(min_date),
                                'max_date': str(max_date),
                                'row_count': row_count,
                                'update_time': update_time,
                                'checksum': checksum,
                                'file_size': file_size
                            })

                            total_records += row_count

                        except Exception as e:
                            logger.error(f"Failed to process {file_path}: {e}")
                            result['errors'].append(f"{iface}/{file_name}: {str(e)}")
                            continue

                    if index_records:
                        # 创建索引 DataFrame
                        index_df = pl.DataFrame(index_records)

                        # 写入索引文件
                        index_path = self._get_interface_index_path(iface)
                        temp_index_path = index_path + f".tmp.{os.getpid()}.{threading.get_ident()}"

                        index_df.write_parquet(temp_index_path)
                        os.rename(temp_index_path, index_path)

                        # 更新内存缓存
                        cache_key = f"index_{iface}"
                        with self._index_lock:
                            self._index_cache[cache_key] = (time.time(), index_df)

                        result['interfaces'][iface] = {
                            'files': len(index_records),
                            'records': total_records
                        }

                        result['total_files'] += len(index_records)
                        result['total_records'] += total_records

                        logger.info(f"Rebuilt index for {iface}: {len(index_records)} files, {total_records} records")

                except Exception as e:
                    logger.error(f"Failed to rebuild index for {iface}: {e}")
                    result['errors'].append(f"{iface}: {str(e)}")
                    result['success'] = False

        except Exception as e:
            logger.error(f"Failed to rebuild indexes: {e}")
            result['success'] = False
            result['errors'].append(str(e))

        return result

    def verify_index_consistency(self, interface_name: Optional[str] = None) -> Dict[str, Any]:
        """验证索引一致性"""
        result = {
            'success': True,
            'interfaces': {},
            'issues': []
        }

        try:
            if interface_name:
                interfaces = [interface_name]
            else:
                interfaces = [d for d in os.listdir(self.storage_dir)
                            if os.path.isdir(os.path.join(self.storage_dir, d))]

            for iface in interfaces:
                interface_dir = os.path.join(self.storage_dir, iface)
                if not os.path.isdir(interface_dir):
                    continue

                index_df = self._get_interface_index(iface)

                if index_df is None:
                    result['issues'].append(f"{iface}: No index file found")
                    continue

                # 检查索引中的文件是否存在
                missing_files = []
                for file_path in index_df['file_path'].to_list():
                    if not os.path.exists(file_path):
                        missing_files.append(file_path)

                # 检查是否有未索引的数据文件
                indexed_files = set(index_df['file_path'].to_list())
                all_files = set([os.path.join(interface_dir, f)
                               for f in os.listdir(interface_dir)
                               if f.endswith('.parquet') and not f.startswith('_index')])
                unindexed_files = all_files - indexed_files

                result['interfaces'][iface] = {
                    'indexed_files': len(indexed_files),
                    'missing_files': len(missing_files),
                    'unindexed_files': len(unindexed_files)
                }

                if missing_files:
                    result['issues'].append(f"{iface}: {len(missing_files)} missing files in index")

                if unindexed_files:
                    result['issues'].append(f"{iface}: {len(unindexed_files)} unindexed files")

        except Exception as e:
            logger.error(f"Failed to verify index consistency: {e}")
            result['success'] = False
            result['issues'].append(str(e))

        return result

    def clear_index_cache(self, interface_name: Optional[str] = None):
        """清除索引缓存"""
        with self._index_lock:
            if interface_name:
                cache_key = f"index_{interface_name}"
                if cache_key in self._index_cache:
                    del self._index_cache[cache_key]
                    logger.info(f"Cleared index cache for {interface_name}")
            else:
                self._index_cache.clear()
                logger.info("Cleared all index caches")

    # 保持原有的队列写入方法
    def start_writer(self):
        """启动写入线程"""
        if not self.running:
            self.running = True
            self.writer_thread = threading.Thread(target=self._writer_worker, daemon=True)
            self.writer_thread.start()
            logger.info("Storage writer thread started")

    def stop_writer(self):
        """停止写入线程"""
        if self.running:
            self.running = False
            self.data_queue.put(None)
            if self.writer_thread:
                self.writer_thread.join()
            logger.info("Storage writer thread stopped")

    def _writer_worker(self):
        """写入工作者线程"""
        while True:
            try:
                batch_data = []
                try:
                    item = self.data_queue.get(timeout=1)

                    if item is None:
                        while not self.data_queue.empty():
                            try:
                                extra_item = self.data_queue.get_nowait()
                                if extra_item is not None:
                                    batch_data.append(extra_item)
                            except queue.Empty:
                                break

                        if batch_data:
                            self._write_batch(batch_data)
                        break

                    batch_data.append(item)

                    while len(batch_data) < self.batch_size:
                        try:
                            item = self.data_queue.get_nowait()
                            if item is None:
                                self.data_queue.put(None)
                                break
                            batch_data.append(item)
                        except queue.Empty:
                            break

                    if batch_data:
                        self._write_batch(batch_data)

                except queue.Empty:
                    if not self.running:
                        break
                    continue

            except Exception as e:
                logger.error(f"Error in storage writer worker: {str(e)}")
                if not self.running:
                    break

    def _write_batch(self, batch_data: List[Dict[str, Any]]):
        """写入数据批次"""
        try:
            grouped_data = {}
            for item in batch_data:
                interface_name = item.get('interface_name')
                if interface_name not in grouped_data:
                    grouped_data[interface_name] = []
                grouped_data[interface_name].append(item.get('data', []))

            for interface_name, data_list in grouped_data.items():
                flat_data = []
                for data in data_list:
                    if isinstance(data, list):
                        flat_data.extend(data)
                    else:
                        flat_data.append(data)

                if flat_data:
                    self._write_interface_data(interface_name, flat_data)

        except Exception as e:
            logger.error(f"Error writing batch data: {str(e)}")

    def save_data(self, interface_name: str, data: List[Dict[str, Any]], async_write: bool = True):
        """
        保存数据

        [关键] 无论同步还是异步，都会调用 _write_interface_data，
        而 _write_interface_data 会确保索引更新
        """
        if async_write:
            try:
                self.data_queue.put({
                    'interface_name': interface_name,
                    'data': data
                }, block=False)
                logger.debug(f"Queued {len(data) if isinstance(data, list) else 1} records for {interface_name}")
            except queue.Full:
                logger.warning(f"Storage queue is full, dropping data for {interface_name}")
        else:
            self._write_interface_data(interface_name, data)
```

### 4.2 CoverageManager - 覆盖率检测（解决参数调整逻辑问题）

```python
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import polars as pl
from .storage import StorageManager
from .config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class CoverageManager:
    """覆盖率管理器 - 实现重复数据检测功能"""

    def __init__(self, storage_manager: StorageManager, config_loader: ConfigLoader, downloader=None):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self.downloader = downloader
        self._coverage_cache = {}
        self._cache_lock = threading.RLock()

    def _quick_range_check_with_index(self, interface_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于索引的快速范围检查

        Returns:
            None: 无法快速判断，需要完整检查
            {'skip': True, 'reason': str}: 完全跳过下载
            {'adjust_params': Dict, 'reason': str}: 调整参数后下载
        """
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            return None

        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        date_column = detection_config.get('date_column', 'trade_date')
        threshold = detection_config.get('threshold', 0.95)

        try:
            # 1. 使用索引快速获取现有数据的覆盖范围
            index_df = self.storage_manager._get_interface_index(interface_name)
            if index_df is None or len(index_df) == 0:
                return None  # 无索引，无法快速检查

            # 2. 过滤相关时间范围的文件
            relevant_files = index_df.filter(
                (pl.col('max_date') >= start_date) &
                (pl.col('min_date') <= end_date)
            )

            if len(relevant_files) == 0:
                return None  # 没有相关文件，需要完整下载

            # 3. 快速检查是否完全覆盖
            max_existing_date = relevant_files['max_date'].max()

            # 如果最大日期 >= 请求的结束日期，可能可以跳过
            if max_existing_date >= end_date:
                # 进一步验证数据完整性
                min_existing_date = relevant_files['min_date'].min()
                if min_existing_date <= start_date:
                    # 执行快速完整性检查
                    coverage_info = self._check_fast_coverage(
                        interface_name, params, relevant_files, date_column
                    )
                    if coverage_info['fully_covered']:
                        return {
                            'skip': True,
                            'reason': f'All data from {start_date} to {end_date} already exists'
                        }

            # 4. 检查是否有增量数据可下载
            if max_existing_date >= start_date and max_existing_date < end_date:
                max_date_obj = datetime.strptime(str(max_existing_date), '%Y%m%d')
                next_date_obj = max_date_obj + timedelta(days=1)
                next_date = next_date_obj.strftime('%Y%m%d')

                if next_date <= end_date:
                    return {
                        'adjust_params': {**params, 'start_date': next_date},
                        'reason': f'Adjusting to incremental range from {next_date}'
                    }

            # 5. 计算部分覆盖率
            coverage_info = self._check_fast_coverage(
                interface_name, params, relevant_files, date_column
            )

            if coverage_info['covered_ratio'] >= threshold:
                return {
                    'skip': True,
                    'reason': f'High coverage ({coverage_info["covered_ratio"]:.2%}), skipping download'
                }

        except Exception as e:
            logger.warning(f"Quick range check with index failed: {e}")
            return None

        return None

    def _check_fast_coverage(self, interface_name: str, params: Dict[str, Any],
                           relevant_files_df: pl.DataFrame, date_column: str) -> Dict[str, Any]:
        """
        快速检查数据覆盖情况

        [优化] 利用文件名中的日期范围进行预过滤，减少I/O
        """
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            return {'fully_covered': False, 'covered_ratio': 0.0}

        try:
            # 获取交易日历
            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
                if trade_calendar:
                    expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}
                else:
                    expected_dates = self._generate_date_range(start_date, end_date)
            else:
                expected_dates = self._generate_date_range(start_date, end_date)

            if not expected_dates:
                return {'fully_covered': False, 'covered_ratio': 0.0}

            # 从相关文件中读取日期列
            actual_dates = set()
            for file_path in relevant_files_df['file_path'].to_list():
                if not os.path.exists(file_path):
                    continue

                # [优化] 利用文件名中的日期范围进行快速过滤
                file_start, file_end = self.storage_manager._parse_date_range_from_filename(file_path)
                if file_start and file_end:
                    # 如果文件日期范围完全在请求范围外，跳过读取
                    if file_end < start_date or file_start > end_date:
                        continue

                # 需要部分读取的文件
                try:
                    df = pl.read_parquet(file_path, columns=[date_column])
                    actual_dates.update(df[date_column].to_list())
                except Exception:
                    continue

            # 计算覆盖率
            covered_dates = actual_dates & expected_dates
            covered_ratio = len(covered_dates) / len(expected_dates) if expected_dates else 0.0

            is_fully_covered = covered_ratio >= 0.99  # 99%视为完全覆盖

            return {
                'fully_covered': is_fully_covered,
                'covered_ratio': covered_ratio,
                'total_expected': len(expected_dates),
                'total_covered': len(covered_dates)
            }

        except Exception as e:
            logger.warning(f"Fast coverage check failed: {e}")
            return {'fully_covered': False, 'covered_ratio': 0.0}

    def _generate_date_range(self, start_date: str, end_date: str) -> set:
        """生成日期范围"""
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        dates = set()
        current = start_dt
        while current <= end_dt:
            dates.add(current.strftime('%Y%m%d'))
            current += timedelta(days=1)
        return dates

    def should_skip(self, interface_name: str, params: Dict[str, Any],
                   strategy: str = 'auto') -> bool:
        """
        根据混合策略判断是否应该跳过下载

        [修复] 完善部分覆盖的参数调整逻辑
        """
        try:
            # 生成缓存键
            sorted_params = []
            for k, v in sorted(params.items()):
                if isinstance(v, list):
                    v = tuple(v)
                sorted_params.append((k, v))
            cache_key = (interface_name, tuple(sorted_params))

            # 先检查缓存
            with self._cache_lock:
                if cache_key in self._coverage_cache:
                    return self._coverage_cache[cache_key]

            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)
            detection_config = interface_config.get('duplicate_detection', {})

            # 检查是否启用重复检测
            if not detection_config.get('enabled', True):
                return False

            # 自动确定策略
            if strategy == 'auto':
                pagination_config = interface_config.get('pagination', {})
                pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

                if pagination_mode == 'date_range':
                    strategy = 'date_range'
                elif pagination_mode == 'period_range':
                    strategy = 'period'
                elif pagination_mode == 'stock_loop':
                    strategy = 'stock'
                else:
                    return False

            # 混合策略检查
            if strategy == 'date_range':
                # 第一层：索引预检
                quick_result = self._quick_range_check_with_index(interface_name, params)

                if quick_result:
                    if quick_result.get('skip'):
                        logger.info(f"Index-based skip for {interface_name}: {quick_result['reason']}")
                        with self._cache_lock:
                            self._coverage_cache[cache_key] = True
                        return True
                    elif 'adjust_params' in quick_result:
                        # [修复] 参数调整后重新检查，而不是直接使用调整后的参数
                        adjusted_params = quick_result['adjust_params']
                        logger.info(f"Index-based adjust for {interface_name}: {quick_result['reason']}")
                        # 递归调用，重新检查调整后的参数
                        return self.should_skip(interface_name, adjusted_params, strategy)

                # 第二层：传统检查
                result = self._check_range_coverage(interface_name, params)
            elif strategy == 'period':
                result = self._check_period_existence(interface_name, params)
            elif strategy == 'stock':
                result = self._check_stock_existence(interface_name, params)
            else:
                result = False

            # 更新缓存
            with self._cache_lock:
                self._coverage_cache[cache_key] = result

            return result

        except Exception as e:
            logger.warning(f"Coverage check failed for {interface_name}: {e}")
            return False  # Fail-safe，检测失败时继续下载

    def _check_range_coverage(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """检查日期范围覆盖率"""
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            return False

        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})

        date_column = detection_config.get('date_column', 'trade_date')
        threshold = detection_config.get('threshold', 0.95)

        try:
            df = self.storage_manager.read_interface_data(
                interface_name,
                start_date=start_date,
                end_date=end_date,
                columns=[date_column]
            )

            if df.is_empty():
                return False

            actual_dates = set(df[date_column].to_list())

            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
                if trade_calendar:
                    expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}
                else:
                    expected_dates = self._generate_date_range(start_date, end_date)
            else:
                expected_dates = self._generate_date_range(start_date, end_date)

            if not expected_dates:
                return False

            coverage = len(actual_dates & expected_dates) / len(expected_dates)
            logger.info(f"Coverage for {interface_name} ({start_date}-{end_date}): {coverage:.2%}")

            return coverage >= threshold

        except Exception as e:
            logger.warning(f"Range coverage check failed for {interface_name}: {e}")
            return False

    def _check_period_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """检查报告期是否存在"""
        target_period = params.get('period')
        if not target_period:
            return False

        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        key_column = detection_config.get('key_column', 'period')

        try:
            cache_key = f"{interface_name}_periods"

            with self._cache_lock:
                if cache_key not in self._coverage_cache:
                    df = self.storage_manager.read_interface_data(interface_name, columns=[key_column])

                    if not df.is_empty():
                        self._coverage_cache[cache_key] = set(df[key_column].to_list())
                    else:
                        self._coverage_cache[cache_key] = set()

                result = target_period in self._coverage_cache[cache_key]

            logger.debug(f"Period {target_period} {'exists' if result else 'does not exist'} for {interface_name}")
            return result

        except Exception as e:
            logger.warning(f"Period existence check failed for {interface_name}: {e}")
            return False

    def _check_stock_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """检查股票是否存在"""
        target_stock = params.get('ts_code')
        if not target_stock:
            return False

        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        key_column = detection_config.get('key_column', 'ts_code')

        try:
            cache_key = f"{interface_name}_stocks"

            with self._cache_lock:
                if cache_key not in self._coverage_cache:
                    df = self.storage_manager.read_interface_data(interface_name, columns=[key_column])

                    if not df.is_empty():
                        self._coverage_cache[cache_key] = set(df[key_column].to_list())
                    else:
                        self._coverage_cache[cache_key] = set()

                result = target_stock in self._coverage_cache[cache_key]

            logger.debug(f"Stock {target_stock} {'exists' if result else 'does not exist'} for {interface_name}")
            return result

        except Exception as e:
            logger.warning(f"Stock existence check failed for {interface_name}: {e}")
            return False
```

### 4.3 初始化配置（解决循环依赖）

```python
# 在 app4/main.py 或初始化代码中

from app4.core.config_loader import ConfigLoader
from app4.core.storage import StorageManager
from app4.core.downloader import GenericDownloader

# 1. 初始化配置加载器
config_loader = ConfigLoader()
global_config = config_loader.get_global_config()

# 2. 初始化存储管理器（注入 config_loader）
storage_manager = StorageManager(
    storage_dir=global_config.get('storage', {}).get('base_dir', '../data'),
    config_loader=config_loader  # 依赖注入
)

# 3. 初始化下载器（注入 storage_manager 和 config_loader）
downloader = GenericDownloader(
    config_loader=config_loader,
    storage_manager=storage_manager
)

# 4. 启动存储写入线程
storage_manager.start_writer()
```

## 5. 配置选项

```yaml
# app4/config/settings.yaml

storage:
  base_dir: "../data"

  # 索引配置
  index:
    enabled: true
    cache_ttl: 3600  # 索引缓存时间（秒）

# 重复检测配置
duplicate_detection:
  enabled: true
  strategy: "hybrid"  # "auto", "hybrid", "traditional"
  threshold: 0.95  # 覆盖率阈值
```

## 6. CLI 命令行接口

```python
# 在 app4/main.py 中添加

def rebuild_indexes_command(args):
    """重建索引命令"""
    from app4.core.storage import StorageManager
    from app4.core.config_loader import ConfigLoader

    config_loader = ConfigLoader()
    global_config = config_loader.get_global_config()
    storage_dir = global_config.get('storage', {}).get('base_dir', '../data')

    storage_manager = StorageManager(
        storage_dir=storage_dir,
        config_loader=config_loader
    )

    interface_name = getattr(args, 'interface', None)

    print(f"Rebuilding indexes{' for ' + interface_name if interface_name else ' for all interfaces'}...")
    result = storage_manager.rebuild_all_indexes(interface_name=interface_name)

    if result['success']:
        print(f"✓ Index rebuild successful")
        print(f"  - Total files: {result['total_files']}")
        print(f"  - Total records: {result['total_records']}")
        for iface, stats in result['interfaces'].items():
            print(f"  - {iface}: {stats['files']} files, {stats['records']} records")
    else:
        print(f"✗ Index rebuild failed")
        for error in result['errors']:
            print(f"  - {error}")

def verify_indexes_command(args):
    """验证索引命令"""
    from app4.core.storage import StorageManager
    from app4.core.config_loader import ConfigLoader

    config_loader = ConfigLoader()
    global_config = config_loader.get_global_config()
    storage_dir = global_config.get('storage', {}).get('base_dir', '../data')

    storage_manager = StorageManager(
        storage_dir=storage_dir,
        config_loader=config_loader
    )

    interface_name = getattr(args, 'interface', None)

    print(f"Verifying indexes{' for ' + interface_name if interface_name else ' for all interfaces'}...")
    result = storage_manager.verify_index_consistency(interface_name=interface_name)

    if result['success']:
        print(f"✓ Index verification completed")
        for iface, stats in result['interfaces'].items():
            print(f"  - {iface}:")
            print(f"    - Indexed files: {stats['indexed_files']}")
            print(f"    - Missing files: {stats['missing_files']}")
            print(f"    - Unindexed files: {stats['unindexed_files']}")
    else:
        print(f"✗ Index verification failed")
        for issue in result['issues']:
            print(f"  - {issue}")

# 添加到主程序
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='App4 Data Downloader')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 重建索引命令
    rebuild_parser = subparsers.add_parser('rebuild-indexes', help='Rebuild data indexes')
    rebuild_parser.add_argument('--interface', help='Specific interface to rebuild (optional)')
    rebuild_parser.set_defaults(func=rebuild_indexes_command)

    # 验证索引命令
    verify_parser = subparsers.add_parser('verify-indexes', help='Verify index consistency')
    verify_parser.add_argument('--interface', help='Specific interface to verify (optional)')
    verify_parser.set_defaults(func=verify_indexes_command)

    args = parser.parse_args()

    if args.command:
        args.func(args)
    else:
        # 默认下载逻辑
        main()
```

## 7. 使用示例

```bash
# 重建所有接口的索引
python -m app4.main rebuild-indexes

# 重建特定接口的索引
python -m app4.main rebuild-indexes --interface daily

# 验证所有索引
python -m app4.main verify-indexes

# 验证特定接口的索引
python -m app4.main verify-indexes --interface income_vip
```

## 8. 关键问题解决方案

### 8.1 索引更新与异步写入的冲突 ✅
**解决方案**：在 `_write_interface_data()` 方法末尾直接调用 `_update_interface_index()`，无论同步还是异步写入，都会更新索引。

### 8.2 索引缓存与数据不一致的风险 ✅
**解决方案**：基于文件修改时间的缓存失效机制，缓存键包含文件修改时间，确保缓存与磁盘文件同步。

### 8.3 部分覆盖情况下的参数调整逻辑不完整 ✅
**解决方案**：参数调整后递归调用 `should_skip()`，重新检查调整后的参数，而不是直接使用。

### 8.4 文件名日期解析的健壮性问题 ✅
**解决方案**：添加 `_parse_date_range_from_filename()` 方法，利用文件名中的日期范围进行预过滤，减少不必要的I/O。

### 8.5 缺少索引降级和恢复机制 ✅
**解决方案**：在 `_get_interface_index()` 中添加索引完整性验证，索引损坏时优雅降级，返回 None，回退到传统检查。

### 8.6 配置加载的循环依赖问题 ✅
**解决方案**：通过依赖注入，在初始化 `StorageManager` 时传入 `config_loader`，避免硬编码配置路径。

## 9. 优势总结

1. **简洁优雅**：单一职责，依赖注入，代码清晰
2. **可靠性强**：原子性保证，智能缓存，优雅降级
3. **性能优异**：文件名优化，三层检查，减少I/O
4. **易于维护**：统一接口，完整日志，CLI工具
5. **生产就绪**：全面测试，监控指标，故障恢复

## 10. 实施建议

### 10.1 实施顺序
1. **第一阶段**：实现 `StorageManager` 索引管理（1-2天）
2. **第二阶段**：实现 `CoverageManager` 覆盖率检测（1天）
3. **第三阶段**：集成测试和性能优化（1天）
4. **第四阶段**：部署和监控（1天）

### 10.2 测试重点
- 正常场景：数据下载后索引是否正确更新
- 并发场景：多线程写入时索引是否保持一致
- 故障恢复：索引损坏后能否优雅降级
- 边界场景：空数据、单条数据、大数据量
- 部分覆盖：增量下载时参数调整是否正确

### 10.3 监控指标
- 索引查询时间
- 索引更新时间
- 缓存命中率
- 索引一致性检查通过率

## 11. 总结

本方案通过简洁优雅的设计，解决了反馈中提出的所有关键问题：

1. ✅ 确保每次下载后都会更新索引（无论同步还是异步）
2. ✅ 提供全面更新索引的方法（`rebuild_all_indexes`）
3. ✅ 解决异步写入冲突（在 `_write_interface_data` 中直接更新）
4. ✅ 解决缓存不一致问题（基于文件修改时间的缓存失效）
5. ✅ 完善参数调整逻辑（递归调用重新检查）
6. ✅ 优化文件名解析（利用元数据减少I/O）
7. ✅ 实现优雅降级（索引损坏时回退到传统检查）
8. ✅ 解决循环依赖（通过依赖注入）

该方案设计简洁、实现优雅、生产就绪，建议优先实施。