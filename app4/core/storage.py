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
            if self.writer_thread:
                self.writer_thread.join()
            logger.info("Storage writer thread stopped")

    def _writer_worker(self):
        """写入工作者线程"""
        while self.running:
            try:
                # 从队列中获取数据批次
                batch_data = []
                try:
                    # 尝试获取第一个元素
                    item = self.data_queue.get(timeout=1)
                    batch_data.append(item)

                    # 尝试获取更多元素以组成批次
                    while len(batch_data) < self.batch_size:
                        try:
                            item = self.data_queue.get_nowait()
                            batch_data.append(item)
                        except queue.Empty:
                            break

                    # 处理批次数据
                    self._write_batch(batch_data)

                except queue.Empty:
                    continue

            except Exception as e:
                logger.error(f"Error in storage writer worker: {str(e)}")

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
            date_col = 'trade_date' if 'trade_date' in df.columns else ('cal_date' if 'cal_date' in df.columns else None)
            if date_col:
                min_date = df[date_col].min()
                max_date = df[date_col].max()
                date_range_str = f"{min_date}_{max_date}"
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
            df = pl.read_parquet(files_to_read, columns=columns)

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