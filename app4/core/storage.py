import os
import json
import hashlib
import threading
import queue
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import uuid
import time
from datetime import date, datetime
from typing import List, Dict, Any, Optional
import logging
from .dedup import deduplicate_against_existing
from .schema_manager import SchemaManager
from .constants import STORAGE_BUFFER_THRESHOLD

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """自定义 JSON 编码器，处理 date 和 datetime 类型"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)

class StorageMonitor:
    def __init__(self):
        self.successful_saves = 0
        self.failed_saves = 0
        self.duplicate_saves = 0
        self.total_records_saved = 0
        self.save_times = []
        self.errors = []

    def record_successful_save(self, record_count: int):
        self.successful_saves += 1
        self.total_records_saved += record_count
        self.save_times.append(time.time())

    def record_error(self, message: str):
        self.failed_saves += 1
        self.errors.append({
            'message': message,
            'timestamp': time.time()
        })

    def record_duplicate_save(self):
        self.duplicate_saves += 1

    def reset(self):
        self.successful_saves = 0
        self.failed_saves = 0
        self.duplicate_saves = 0
        self.total_records_saved = 0
        self.save_times = []
        self.errors = []

    def get_summary(self) -> str:
        average_records = (
            self.total_records_saved / self.successful_saves
            if self.successful_saves > 0 else 0
        )
        return "\n".join([
            "Storage Operation Summary",
            f"Successful Saves: {self.successful_saves}",
            f"Failed Saves: {self.failed_saves}",
            f"Duplicate Saves: {self.duplicate_saves}",
            f"Total Records Saved: {self.total_records_saved}",
            f"Average Records per Save: {average_records}"
        ])

class StorageManager:
    """存储管理器 - 支持接口缓存和异步处理"""

    def __init__(self, processor: Optional['DataProcessor'] = None, config_loader=None, storage_dir: str = "../data",
                 format: str = "parquet", batch_size: int = 10000):
        # 现有属性
        self.storage_dir = storage_dir
        self.format = format
        self.batch_size = batch_size
        self.data_queue = queue.Queue()
        self.writer_thread = None
        self.running = False
        self.stats = {
            'total_records': 0,
            'files_written': 0,
            'start_time': time.time()
        }

        # 新增属性
        self.processor = processor  # 持有Processor引用
        self.config_loader = config_loader  # 持有配置加载器引用
        self.interface_buffers = {}  # 接口缓存 {interface_name: BufferContext}
        self.process_queue = queue.Queue()  # 处理队列
        self.process_thread = None  # 处理线程
        self.buffer_threshold = STORAGE_BUFFER_THRESHOLD
        self.buffer_lock = threading.Lock()  # 缓存锁
        self.failed_interfaces = set()  # 失败接口集合
        self.monitor = StorageMonitor()
        self._last_save_signature = {}

        # 确保存储目录存在
        os.makedirs(storage_dir, exist_ok=True)

    def start_writer(self):
        """启动写入线程和处理线程"""
        if not self.running:
            self.running = True

            # 启动写入线程（现有）
            self.writer_thread = threading.Thread(
                target=self._writer_worker,
                daemon=True
            )
            self.writer_thread.start()

            # 启动处理线程（新增）
            self.process_thread = threading.Thread(
                target=self._process_worker,
                daemon=True
            )
            self.process_thread.start()

            logger.info("Storage writer and process threads started")

    def stop_writer(self):
        """停止所有线程"""
        if self.running:
            self.running = False

            # 处理剩余的数据
            self.flush_remaining_data()

            # 等待处理队列中的数据被消费完毕
            logger.info("Waiting for process queue to empty...")
            while not self.process_queue.empty():
                time.sleep(0.1)

            # 停止处理线程
            self.process_queue.put(None)  # 发送哨兵
            if self.process_thread:
                self.process_thread.join(timeout=60)
                if self.process_thread.is_alive():
                    logger.warning("Process thread did not stop within timeout")

            # 停止写入线程 - 直接发送哨兵，让writer线程自己处理剩余数据
            logger.info("Stopping writer thread...")
            self.data_queue.put(None)  # 发送哨兵
            if self.writer_thread:
                self.writer_thread.join(timeout=120)
                if self.writer_thread.is_alive():
                    logger.warning("Writer thread did not stop within timeout")

            logger.info("Storage threads stopped")

    def _writer_worker(self):
        """写入工作者线程"""
        pending_stop = False
        while True:
            try:
                # 从队列中获取数据批次
                batch_data = []
                try:
                    # 尝试获取第一个元素
                    item = self.data_queue.get(timeout=1)

                    # 检查哨兵
                    if item is None:
                        # 收到停止信号，处理完当前批次（如果还有剩余）后退出
                        # 将队列中剩余所有非None项取出处理
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

                    # 尝试获取更多元素以组成批次
                    while len(batch_data) < self.batch_size:
                        try:
                            item = self.data_queue.get_nowait()
                            if item is None:
                                # 如果在批次收集中遇到None，说明要结束
                                # 标记收到停止信号，处理完当前批次后退出
                                pending_stop = True
                                break
                            batch_data.append(item)
                        except queue.Empty:
                            break

                    # 处理批次数据
                    if batch_data:
                        self._write_batch(batch_data)

                    # 如果之前收到停止信号，退出循环
                    if pending_stop:
                        break

                except queue.Empty:
                    # 如果队列为空且收到停止信号（通过self.running判断作为双重保障）
                    if not self.running:
                        break
                    continue

            except Exception as e:
                logger.error(f"Error in storage writer worker: {str(e)}")
                # 防止死循环
                if not self.running:
                    break

    def _write_batch(self, batch_data: List[Dict[str, Any]]):
        """写入数据批次"""
        try:
            # 按接口名称分组数据
            grouped_data = {}
            for item in batch_data:
                interface_name = item.get('interface_name')
                if interface_name not in grouped_data:
                    grouped_data[interface_name] = []
                grouped_data[interface_name].append(item.get('data', []))

            # 写入每个接口的数据
            for interface_name, data_list in grouped_data.items():
                # 展平数据列表
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

    def _get_interface_config(self, interface_name: str) -> Dict[str, Any]:
        try:
            if self.config_loader:
                return self.config_loader.get_interface_config(interface_name)
            from .config_loader import ConfigLoader
            config_loader = ConfigLoader()
            return config_loader.get_interface_config(interface_name)
        except Exception:
            return {}

    def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
        """
        写入接口数据 - Parquet Dataset 模式
        """
        import uuid
        import time

        dir_path = os.path.join(self.storage_dir, interface_name)
        os.makedirs(dir_path, exist_ok=True)

        try:
            if not data:
                return

            # [优化] 增加写入时间戳，用于确定性去重
            current_time = int(time.time() * 1000)
            for item in data:
                item['_update_time'] = current_time

            # ✅ 使用SchemaManager安全创建DataFrame
            try:
                df = SchemaManager.create_dataframe_safe(data, interface_name)
                if df.is_empty():
                    logger.error(f"无法为 {interface_name} 创建DataFrame，跳过保存")
                    return
                logger.info(f"使用SchemaManager成功创建DataFrame for {interface_name}，记录数: {len(df)}")
            except Exception as df_error:
                logger.error(f"SchemaManager创建DataFrame失败 for {interface_name}: {str(df_error)}")
                return

            # [优化] 从数据中提取日期范围用于文件名元数据
            # 优先级：对于不同接口，优先使用最相关的日期字段
            # 对于income_vip等period_range接口，优先使用period字段
            # 对于daily等date_range接口，使用trade_date
            date_col = None

            # 如果接口名包含特定关键词，优先使用相应的日期字段
            if 'income' in interface_name or 'balance' in interface_name or 'cashflow' in interface_name:
                # 财务数据接口，优先使用period字段
                priority_cols = ['period', 'end_date', 'ann_date', 'trade_date', 'cal_date']
            else:
                # 其他接口，优先使用交易日期字段
                priority_cols = ['trade_date', 'cal_date', 'ann_date', 'end_date', 'period']

            for col in priority_cols:
                if col in df.columns:
                    date_col = col
                    break

            if date_col:
                # 获取日期范围
                min_val = df[date_col].min()
                max_val = df[date_col].max()

                # 处理不同类型的日期值
                if isinstance(min_val, (str, int)):
                    # 如果是字符串或整数格式（如'20230630'或20230630）
                    min_date_str = str(min_val)
                    max_date_str = str(max_val)
                elif hasattr(min_val, 'strftime'):
                    # 如果是日期/时间对象
                    min_date_str = min_val.strftime('%Y%m%d')
                    max_date_str = max_val.strftime('%Y%m%d')
                else:
                    # 其他类型转换为字符串
                    min_date_str = str(min_val)
                    max_date_str = str(max_val)

                date_range_str = f"{min_date_str}_{max_date_str}"
            else:
                date_range_str = "nodate"

            # 生成带元数据的文件名: {interface}_{start}_{end}_{timestamp}_{uuid}.parquet
            unique_id = uuid.uuid4().hex[:8]
            file_name = f"{interface_name}_{date_range_str}_{current_time}_{unique_id}.parquet"
            file_path = os.path.join(dir_path, file_name)

            # [优化] 原子写入，但使用更安全的写入方式
            temp_file_path = file_path + ".tmp"
            try:
                df.write_parquet(temp_file_path, compression='snappy')
            except Exception as write_error:
                logger.warning(f"snappy压缩写入失败, 尝试其他方式: {str(write_error)[:100]}...")  # 只记录错误摘要
                # 尝试使用不同的写入选项
                try:
                    # 尝试使用不同的压缩方式和选项
                    df.write_parquet(temp_file_path, compression='gzip')
                except Exception:
                    # 最后尝试使用默认设置
                    df.write_parquet(temp_file_path)

            os.rename(temp_file_path, file_path)

            logger.info(f"Wrote {len(df)} records to {file_path}")

        except Exception as e:
            logger.error(f"Error writing interface data for {interface_name}: {str(e)}")
            # 不再raise异常，而是记录错误并继续
            # raise

    def _create_dataframe_safe(self, data: List[Dict[str, Any]]) -> pl.DataFrame:
        """安全创建DataFrame的方法，用于处理类型不匹配问题"""
        if not data:
            return pl.DataFrame()

        try:
            # 尝试使用很大的推断长度
            return pl.DataFrame(data, infer_schema_length=min(len(data), 100000))
        except Exception:
            # 如果还是失败，创建一个空DataFrame
            logger.warning("无法创建DataFrame，返回空DataFrame")
            return pl.DataFrame()

    def read_interface_data(self, interface_name: str, start_date: str = None, end_date: str = None, columns: Optional[List[str]] = None) -> pl.DataFrame:
        """
        读取接口数据 - 支持文件名过滤和确定性去重
        """
        dir_path = os.path.join(self.storage_dir, interface_name)

        if not os.path.exists(dir_path):
            return pl.DataFrame()

        try:
            # [优化] 文件名过滤 (Predicate Pushdown 模拟)
            files_to_read = []
            all_files = os.listdir(dir_path)

            for f in all_files:
                if not f.endswith('.parquet'): continue # 忽略 .tmp

                # 简单过滤：如果提供了日期范围，且文件名包含日期信息，则进行过滤
                # 文件名格式: name_start_end_ts_uuid.parquet
                parts = f.split('_')
                if len(parts) >= 4 and start_date and end_date:
                    # 这是一个简化的过滤逻辑，实际可能需要更健壮的解析
                    # 假设 parts[1] 是 min_date, parts[2] 是 max_date
                    f_min, f_max = parts[1], parts[2]
                    if f_min != "nodate":
                        # 检查范围重叠
                        if f_max < start_date or f_min > end_date:
                            continue

                files_to_read.append(os.path.join(dir_path, f))

            if not files_to_read:
                return pl.DataFrame()

            # 读取所有符合条件的文件
            if columns:
                # 如果指定了列，先读取所有列，然后选择需要的列
                try:
                    df_full = pl.read_parquet(files_to_read)
                    available_cols = [col for col in columns if col in df_full.columns]
                    df = df_full.select(available_cols)
                except Exception as e:
                    # 如果类型不匹配或其他错误，使用更兼容的方法
                    # 先读取所有文件的schema，然后统一处理
                    df = pl.DataFrame()
                    for file_path in files_to_read:
                        try:
                            # 读取单个文件，只取需要的列
                            temp_df = pl.read_parquet(file_path)
                            available_cols = [col for col in columns if col in temp_df.columns]
                            temp_df = temp_df.select(available_cols)
                            df = df.vstack(temp_df) if not df.is_empty() else temp_df
                        except Exception:
                            # 如果单个文件有问题，跳过它
                            continue
            else:
                df = pl.read_parquet(files_to_read)

            # [优化] 确定性去重
            interface_config = self._get_interface_config(interface_name)
            primary_keys = interface_config.get('output', {}).get('primary_key', [])

            if primary_keys and not df.is_empty():
                existing_keys = [k for k in primary_keys if k in df.columns]
                if existing_keys:
                    # 按 _update_time 排序，确保保留最新写入的数据
                    if '_update_time' in df.columns:
                        df = df.sort('_update_time', descending=False)

                    df = df.unique(subset=existing_keys, keep='last')

            return df
        except Exception as e:
            logger.error(f"Error reading interface data for {interface_name}: {str(e)}")
            raise

    def add_to_buffer(self, interface_name: str, data: List[Dict[str, Any]],
                      flush_immediately: bool = False) -> None:
        """
        Add data to buffer with optimized lock usage.

        Args:
            interface_name: 接口名称
            data: 数据列表
            flush_immediately: 是否立即刷新（适用于小数据量场景）
        """
        data_to_process = None
        interface_to_process = None

        with self.buffer_lock:
            # Only perform minimal necessary operations while holding the lock
            buffer = self._get_or_create_buffer(interface_name)
            buffer['data'].extend(data)
            buffer['count'] += len(data)

            # Check if we should flush the buffer
            should_flush = (
                buffer['count'] >= self.buffer_threshold or
                flush_immediately or
                buffer['count'] < 100  # 小数据量立即处理
            )

            if should_flush:
                data_to_process = buffer['data']
                interface_to_process = interface_name
                buffer['data'] = []
                buffer['count'] = 0

        # Process the data outside the lock to avoid blocking other threads
        if data_to_process:
            item = {
                'interface': interface_to_process,
                'data': data_to_process,
                'timestamp': time.time()
            }
            self.process_queue.put(item)

            self.total_buffered_items = getattr(self, 'total_buffered_items', 0) + len(data_to_process)
            self.last_processed_time = time.time()

            if flush_immediately or len(data_to_process) < 100:
                logger.debug(f"Immediately processed {len(data_to_process)} records for {interface_to_process}")

    def _get_or_create_buffer(self, interface_name: str) -> Dict[str, Any]:
        """
        Get existing buffer for interface or create new one.
        This helper method is used inside the critical section to avoid code duplication.
        """
        if interface_name not in self.interface_buffers:
            self.interface_buffers[interface_name] = {
                'data': [],
                'count': 0,
                'created_at': time.time()
            }
        return self.interface_buffers[interface_name]

    def flush_remaining_data(self):
        """处理所有缓存中的剩余数据"""
        items_to_flush = []

        with self.buffer_lock:
            for interface_name, buffer in self.interface_buffers.items():
                if buffer['count'] > 0 and buffer['data']:
                    # 收集需要处理的数据（在锁内做最小操作）
                    items_to_flush.append({
                        'interface_name': interface_name,
                        'data': buffer['data'],
                        'count': buffer['count']
                    })

                    # 重置缓存
                    buffer['data'] = []
                    buffer['count'] = 0

        # 处理收集的数据（在锁外）
        for item in items_to_flush:
            # 放入处理队列
            try:
                self.process_queue.put({
                    'interface': item['interface_name'],
                    'data': item['data'],
                    'timestamp': time.time()
                }, block=False)
                logger.info(f"Flushed {len(item['data'])} remaining records for processing: {item['interface_name']}")
            except queue.Full:
                logger.error(f"Process queue is full, unable to flush data for {item['interface_name']}")

    def _process_worker(self):
        """处理线程：数据去重、验证、放入写入队列"""
        dedup_stats_total = {
            'total_processed': 0,
            'total_deduped': 0,
            'interfaces': set()
        }

        while self.running:
            try:
                task = self.process_queue.get(timeout=1)

                # 检查停止信号
                if task is None:
                    # 线程结束时输出统计
                    if dedup_stats_total['total_processed'] > 0:
                        dedup_rate = (dedup_stats_total['total_deduped'] / dedup_stats_total['total_processed']) * 100
                        logger.info(f"Process worker summary: processed {dedup_stats_total['total_processed']} records, "
                                   f"deduped {dedup_stats_total['total_deduped']} ({dedup_rate:.2f}%), "
                                   f"interfaces={len(dedup_stats_total['interfaces'])}")

                    logger.info("Process worker received stop signal")
                    break

                interface_name = task['interface']
                data = task['data']

                # ✅ 检查接口是否已失败
                if interface_name in self.failed_interfaces:
                    logger.warning(f"Skipping processing for failed interface: {interface_name}")
                    continue

                try:
                    # 获取接口配置
                    try:
                        if self.config_loader:
                            interface_config = self.config_loader.get_interface_config(interface_name)
                        else:
                            from .config_loader import ConfigLoader
                            config_loader = ConfigLoader()
                            interface_config = config_loader.get_interface_config(interface_name)
                    except Exception as e:
                        logger.warning(f"Failed to load interface config for {interface_name}, using default: {e}")
                        interface_config = {
                            'api_name': interface_name,
                            'output': {'primary_key': ['ts_code', 'trade_date']},
                            'dedup': {'enabled': True}
                        }

                    # ✅ 处理数据（内部去重）
                    if self.processor:
                        try:
                            df = self.processor.process_data(data, interface_config)
                        except Exception as process_error:
                            logger.error(f"Processor failed for {interface_name}: {str(process_error)}")
                            try:
                                df = SchemaManager.create_dataframe_safe(data, interface_name)
                                if df.is_empty():
                                    logger.error(f"无法为 {interface_name} 创建DataFrame，跳过处理")
                                    continue
                            except Exception as fallback_error:
                                logger.error(f"SchemaManager安全模式也失败 for {interface_name}: {str(fallback_error)}")
                                continue
                    else:
                        try:
                            df = SchemaManager.create_dataframe_safe(data, interface_name)
                            if df.is_empty():
                                logger.error(f"无法为 {interface_name} 创建DataFrame，跳过处理")
                                continue
                        except Exception as e:
                            logger.error(f"SchemaManager创建DataFrame失败 for {interface_name}: {str(e)}")
                            continue

                    if df.is_empty():
                        logger.warning(f"No data to save after processing: {interface_name}")
                        continue

                    # 验证数据
                    if self.processor:
                        validation_result = self.processor.validate_data(df, interface_config)
                        if not validation_result['valid']:
                            logger.warning(f"Data validation failed for {interface_name}")
                            continue

                    # ✅ 与历史数据去重（外部去重）
                    output_config = interface_config.get('output', {})
                    primary_keys = output_config.get('primary_key', [])
                    dedup_config = interface_config.get('dedup', {'dedup_enabled': True})

                    if dedup_config.get('dedup_enabled', True) and primary_keys:
                        try:
                            existing_df = self.read_interface_data(interface_name, columns=primary_keys)
                        except Exception as e:
                            logger.warning(f"无法读取现有数据进行去重: {e}")
                            existing_df = pl.DataFrame()

                        if not existing_df.is_empty():
                            import tempfile
                            try:
                                with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
                                    existing_df.write_parquet(tmp_file.name)
                                    temp_path = tmp_file.name

                                df, dedup_stats = deduplicate_against_existing(
                                    new_data=df,
                                    existing_data_path=temp_path,
                                    primary_keys=primary_keys
                                )

                                # 累加统计
                                dedup_stats_total['total_processed'] += dedup_stats.input_rows
                                dedup_stats_total['total_deduped'] += dedup_stats.removed_rows
                                dedup_stats_total['interfaces'].add(interface_name)

                                logger.info(f"Deduplication completed for {interface_name}: "
                                           f"input={dedup_stats.input_rows}, "
                                           f"output={dedup_stats.output_rows}, "
                                           f"removed={dedup_stats.removed_rows}")

                                # ✅ 全相同则跳过保存
                                if len(df) == 0:
                                    logger.info(f"All records already exist for {interface_name}, skipping save")
                                    continue
                            finally:
                                if 'temp_path' in locals() and os.path.exists(temp_path):
                                    os.unlink(temp_path)

                    # 写入数据
                    self.data_queue.put({
                        'interface_name': interface_name,
                        'data': df.to_dicts()
                    })

                    logger.info(f"Processed and queued {len(df)} records for {interface_name}")

                except Exception as e:
                    logger.error(f"Error processing {interface_name}: {str(e)}")
                    import traceback
                    logger.debug(f"Full traceback: {traceback.format_exc()}")
                    self.failed_interfaces.add(interface_name)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in process worker: {str(e)}")
                import traceback
                logger.debug(f"Full traceback: {traceback.format_exc()}")

    def get_failed_interfaces(self) -> set:
        """获取失败的接口集合"""
        return self.failed_interfaces.copy()

    def clear_failed_interface(self, interface_name: str):
        """清除接口的失败状态"""
        self.failed_interfaces.discard(interface_name)

    def get_buffer_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.buffer_lock:
            stats = {
                'total_interfaces': len(self.interface_buffers),
                'interface_stats': {}
            }

            for interface_name, buffer in self.interface_buffers.items():
                # 简单估算内存占用
                buffer_size_mb = sum(len(str(record)) for record in buffer['data']) / 1024 / 1024 if buffer['data'] else 0
                stats['interface_stats'][interface_name] = {
                    'buffer_count': buffer['count'],
                    'buffer_size_mb': buffer_size_mb
                }

            return stats

    def save_data(self, interface_name: str, data: List[Dict[str, Any]], async_write: bool = True):
        """
        保存数据

        Args:
            interface_name: 接口名称
            data: 要保存的数据
            async_write: 是否异步写入
        """
        try:
            if isinstance(data, pl.DataFrame):
                data_records = data.to_dicts()
            elif isinstance(data, dict):
                data_records = [data]
            else:
                data_records = data or []

            if not data_records:
                return

            signature = self._make_save_signature(data_records)
            if self._last_save_signature.get(interface_name) == signature:
                self.monitor.record_duplicate_save()
            self._last_save_signature[interface_name] = signature
            self.monitor.record_successful_save(len(data_records))

            if async_write:
                data_already_processed = (
                    data_records and isinstance(data_records, list) and
                    len(data_records) > 0 and '_update_time' in data_records[0]
                )

                if data_already_processed:
                    try:
                        self.data_queue.put({
                            'interface_name': interface_name,
                            'data': data_records
                        }, block=False)
                        logger.debug(f"Queued processed data ({len(data_records)} records) for {interface_name}")
                    except queue.Full:
                        logger.warning(f"Storage queue is full, dropping data for {interface_name}")
                else:
                    self.add_to_buffer(interface_name, data_records, flush_immediately=(len(data_records) < 100))
            else:
                self._write_interface_data(interface_name, data_records)
        except Exception as e:
            self.monitor.record_error(str(e))
            raise

    def _make_save_signature(self, data_records: List[Dict[str, Any]]) -> str:
        digest_value = 0
        modulus = 1 << 256
        for record in data_records:
            normalized = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"), cls=DateTimeEncoder)
            record_digest = hashlib.sha256(normalized.encode("utf-8")).digest()
            digest_value = (digest_value + int.from_bytes(record_digest, byteorder="big")) % modulus
        return f"{digest_value:064x}"

    def write_interface_data(self, interface_name: str, df: pl.DataFrame) -> None:
        """
        写入接口数据 - 供 UpdateManager 使用

        Args:
            interface_name: 接口名称
            df: 要写入的 DataFrame
        """
        if df.is_empty():
            logger.warning(f"DataFrame is empty for {interface_name}, skipping write")
            return

        try:
            # 将 DataFrame 转换为字典列表
            data = df.to_dicts()

            # 添加 _update_time 字段标记数据已处理
            current_time = int(time.time() * 1000)
            for item in data:
                item['_update_time'] = current_time

            # 使用异步写入
            self.save_data(interface_name, data, async_write=True)

            logger.info(f"Queued {len(data)} records for {interface_name} via write_interface_data")

        except Exception as e:
            logger.error(f"Error in write_interface_data for {interface_name}: {str(e)}")
            raise

    def get_storage_info(self) -> Dict[str, Any]:
        """获取存储信息"""
        files = os.listdir(self.storage_dir)
        total_size = sum(os.path.getsize(os.path.join(self.storage_dir, f)) for f in files if os.path.isfile(os.path.join(self.storage_dir, f)))

        return {
            'storage_dir': self.storage_dir,
            'format': self.format,
            'total_files': len(files),
            'total_size_bytes': total_size,
            'async_enabled': self.running
        }
