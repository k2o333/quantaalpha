import os
import threading
import queue
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import uuid
import time
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class StorageManager:
    """存储管理器 - 异步持久化 - Dataset 模式"""

    def __init__(self, storage_dir: str = "../data", format: str = "parquet", batch_size: int = 100):
        self.storage_dir = storage_dir
        self.format = format
        self.batch_size = batch_size
        self.data_queue = queue.Queue()
        self.writer_thread = None
        self.running = False

        # 确保存储目录存在
        os.makedirs(storage_dir, exist_ok=True)

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
            # 发送哨兵信号，确保队列中的数据被处理完
            self.data_queue.put(None)
            if self.writer_thread:
                self.writer_thread.join()
            logger.info("Storage writer thread stopped")

    def _writer_worker(self):
        """写入工作者线程"""
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
                        # 但这里我们设计的是单个哨兵结束整个循环，
                        # 且由于是一个个get，收到None说明前面没有数据了（如果队列FIFO）
                        # 或者有数据但被None隔开了。
                        # 为了安全起见，收到None后，我们将队列中剩余所有非None项取出处理
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
                                # 将None放回队列，以便外层循环处理退出逻辑
                                self.data_queue.put(None)
                                break
                            batch_data.append(item)
                        except queue.Empty:
                            break

                    # 处理批次数据
                    if batch_data:
                        self._write_batch(batch_data)

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
        """获取接口配置

        Args:
            interface_name: 接口名称

        Returns:
            接口配置字典
        """
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'interfaces', f'{interface_name}.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
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

            df = pl.DataFrame(data)

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

            # [优化] 原子写入
            temp_file_path = file_path + ".tmp"
            df.write_parquet(temp_file_path, compression='snappy')
            os.rename(temp_file_path, file_path)

            logger.info(f"Wrote {len(df)} records to {file_path}")

        except Exception as e:
            logger.error(f"Error writing interface data for {interface_name}: {str(e)}")
            raise

    def read_interface_data(self, interface_name: str, start_date: str = None, end_date: str = None, columns: Optional[List[str]] = None, **kwargs) -> pl.DataFrame:
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
                            if df.is_empty():
                                df = temp_df
                            else:
                                try:
                                    df = pl.concat([df, temp_df], how='vertical')
                                except Exception:
                                    # 如果类型不匹配，尝试diagonal模式
                                    df = pl.concat([df, temp_df], how='diagonal')
                        except Exception:
                            # 如果单个文件有问题，跳过它
                            continue
            else:
                df = pl.read_parquet(files_to_read)

            # [新增] 过滤额外参数（例如 ts_code）
            for param_name, param_value in kwargs.items():
                if param_name in df.columns and param_value is not None:
                    df = df.filter(pl.col(param_name) == param_value)

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

    def save_data(self, interface_name: str, data: List[Dict[str, Any]], async_write: bool = True):
        """
        保存数据

        Args:
            interface_name: 接口名称
            data: 要保存的数据
            async_write: 是否异步写入
        """
        if async_write:
            # 异步写入：将数据放入队列
            try:
                self.data_queue.put({
                    'interface_name': interface_name,
                    'data': data
                }, block=False)
                logger.debug(f"Queued {len(data) if isinstance(data, list) else 1} records for {interface_name}")
            except queue.Full:
                logger.warning(f"Storage queue is full, dropping data for {interface_name}")
        else:
            # 同步写入：直接写入
            self._write_interface_data(interface_name, data)

    def filter_new_records(self, interface_name: str, new_data: List[Dict], dedup_config: Dict[str, Any]) -> List[Dict]:
        """
        根据去重配置过滤新记录，只返回不存在的记录

        Args:
            interface_name: 接口名称
            new_data: 新数据列表
            dedup_config: 去重配置

        Returns:
            过滤后的新记录列表
        """
        if not dedup_config.get('enabled', False):
            return new_data

        strategy = dedup_config.get('strategy', 'none')
        dedup_columns = dedup_config.get('columns', [])

        if strategy != 'primary_key' or not dedup_columns:
            return new_data

        # 读取现有数据
        existing_df = self.read_interface_data(interface_name, columns=dedup_columns)

        if existing_df.is_empty():
            return new_data

        # 构建现有主键集合
        existing_keys = set()
        for row in existing_df.iter_rows(named=True):
            key_tuple = tuple(row.get(k) for k in dedup_columns if k in row)
            if all(v is not None for v in key_tuple):
                existing_keys.add(key_tuple)

        logger.info(f"Found {len(existing_keys)} existing key combinations for {interface_name}")

        # 过滤出不存在的新记录
        original_count = len(new_data)
        new_records = []
        for record in new_data:
            key_tuple = tuple(record.get(k) for k in dedup_columns if k in record)
            if key_tuple not in existing_keys and all(v is not None for v in key_tuple):
                new_records.append(record)

        if not new_records:
            logger.info(f"All {original_count} records already exist for {interface_name}, skipping save")
            return []

        logger.info(f"Filtered {original_count - len(new_records)} duplicate records, "
                    f"saving {len(new_records)} new records for {interface_name}")

        return new_records

    def save_data_with_dedup(self, interface_name: str, data: List[Dict], dedup_config: Dict[str, Any], async_write: bool = True):
        """
        带去重功能的数据保存

        Args:
            interface_name: 接口名称
            data: 要保存的数据
            dedup_config: 去重配置
            async_write: 是否异步写入
        """
        # 先过滤新记录
        filtered_data = self.filter_new_records(interface_name, data, dedup_config)

        if not filtered_data:
            return  # 没有新数据需要保存

        # 保存过滤后的数据
        self.save_data(interface_name, filtered_data, async_write)

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