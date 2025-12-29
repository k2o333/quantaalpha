import os
import threading
import queue
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class StorageManager:
    """存储管理器 - 异步持久化"""

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

    def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
        """写入特定接口的数据"""
        try:
            # 调试信息
            logger.debug(f"Writing data for {interface_name}, data length: {len(data)}")
            if data and len(data) > 0:
                logger.debug(f"First record keys: {list(data[0].keys()) if data else 'No data'}")
                logger.debug(f"First record sample: {data[0] if data else 'No data'}")

            # 转换为 DataFrame
            df = pd.DataFrame(data)

            # 更多调试信息
            logger.debug(f"DataFrame shape: {df.shape}")
            logger.debug(f"DataFrame columns: {list(df.columns)}")
            logger.debug(f"DataFrame column types: {[type(col) for col in df.columns]}")
            if not df.empty:
                logger.debug(f"DataFrame dtypes: {df.dtypes.to_dict()}")

            # 确保列名是字符串类型，避免PyArrow的FieldRef问题
            original_columns = df.columns.tolist()
            df.columns = df.columns.astype(str)
            new_columns = df.columns.tolist()
            if original_columns != new_columns:
                logger.debug(f"Column names changed: {original_columns} -> {new_columns}")

            # 确保没有重复的列名
            duplicated_cols = df.columns[df.columns.duplicated()].tolist()
            if duplicated_cols:
                logger.debug(f"Duplicated columns found: {duplicated_cols}")
            df = df.loc[:, ~df.columns.duplicated()]
            logger.debug(f"DataFrame columns after deduplication: {list(df.columns)}")

            # 生成文件路径
            file_path = os.path.join(self.storage_dir, f"{interface_name}.{self.format}")

            # 如果文件已存在，追加数据
            logger.debug(f"Checking file path: {file_path}")
            logger.debug(f"File exists: {os.path.exists(file_path)}")
            logger.debug(f"Format: {self.format}")
            if os.path.exists(file_path) and self.format == "parquet":
                logger.debug(f"Reading existing data from: {file_path}")
                try:
                    # 读取现有数据
                    existing_df = pd.read_parquet(file_path)

                    # 确保列名是字符串类型（防止整数列名被误处理）
                    existing_df.columns = [str(col) for col in existing_df.columns]

                    # 合并数据（去重）
                    combined_df = pd.concat([existing_df, df]).drop_duplicates()

                    # 确保合并后的数据也进行类型处理
                    combined_df.columns = [str(col) for col in combined_df.columns]
                    for col in combined_df.columns:
                        if combined_df[col].dtype == 'object':
                            combined_df[col] = combined_df[col].astype(str)
                        elif combined_df[col].dtype == 'int64':
                            if combined_df[col].isna().any():
                                combined_df[col] = combined_df[col].astype('float64')

                    # 使用PyArrow创建表并写入，以获得更好的类型控制
                    import pyarrow as pa
                    from pyarrow import parquet as pq

                    # 创建明确的schema
                    schema_fields = []
                    for col in combined_df.columns:
                        col_dtype = combined_df[col].dtype
                        if col_dtype in ['object', 'string']:
                            schema_fields.append((col, pa.string()))
                        elif col_dtype in ['int64', 'int32']:
                            schema_fields.append((col, pa.int64()))
                        elif col_dtype in ['float64', 'float32']:
                            schema_fields.append((col, pa.float64()))
                        else:
                            schema_fields.append((col, pa.string()))

                    schema = pa.schema(schema_fields)
                    table = pa.Table.from_pandas(combined_df, schema=schema, preserve_index=False)
                    pq.write_table(table, file_path)
                except Exception as read_error:
                    logger.warning(f"Error reading existing file {file_path}: {str(read_error)}")
                    logger.warning("Creating new file instead of appending")
                    # 如果读取失败，创建新的文件
                    import pyarrow as pa
                    from pyarrow import parquet as pq

                    # 创建明确的schema
                    schema_fields = []
                    for col in df.columns:
                        col_dtype = df[col].dtype
                        if col_dtype in ['object', 'string']:
                            schema_fields.append((col, pa.string()))
                        elif col_dtype in ['int64', 'int32']:
                            schema_fields.append((col, pa.int64()))
                        elif col_dtype in ['float64', 'float32']:
                            schema_fields.append((col, pa.float64()))
                        else:
                            schema_fields.append((col, pa.string()))

                    schema = pa.schema(schema_fields)
                    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
                    pq.write_table(table, file_path)
            else:
                # 直接写入新文件
                if self.format == "parquet":
                    # 确保列名是字符串类型
                    df.columns = df.columns.astype(str)
                    # 确保没有重复的列名
                    df = df.loc[:, ~df.columns.duplicated()]

                    # 清理数据类型以避免PyArrow的FieldRef问题
                    for col in df.columns:
                        if df[col].dtype == 'object':
                            # 对于object类型，尝试转换为一致的字符串类型
                            df[col] = df[col].astype(str)
                        elif df[col].dtype == 'int64':
                            # 确保整数列没有NaN值
                            if df[col].isna().any():
                                df[col] = df[col].astype('float64')

                    # 使用PyArrow创建表并写入，以获得更好的类型控制
                    import pyarrow as pa
                    from pyarrow import parquet as pq

                    # 创建明确的schema
                    schema_fields = []
                    for col in df.columns:
                        col_dtype = df[col].dtype
                        if col_dtype in ['object', 'string']:
                            schema_fields.append((col, pa.string()))
                        elif col_dtype in ['int64', 'int32']:
                            schema_fields.append((col, pa.int64()))
                        elif col_dtype in ['float64', 'float32']:
                            schema_fields.append((col, pa.float64()))
                        else:
                            schema_fields.append((col, pa.string()))

                    schema = pa.schema(schema_fields)
                    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
                    pq.write_table(table, file_path)
                else:
                    # 默认使用 CSV 格式
                    df.to_csv(file_path, index=False)

            logger.info(f"Written {len(data)} records to {file_path}")

        except Exception as e:
            import traceback
            logger.error(f"Error writing data for interface {interface_name}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")

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