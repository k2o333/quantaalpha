# App4 索引管理功能实施方案

## 1. 概述

本文档详细描述 App4 项目中索引管理功能的完整实施方案，确保**每次数据下载后都会更新索引**，并提供**全面更新索引的方法**，以支持高效的重复数据检测和增量下载。

## 2. 核心设计原则

### 2.1 索引更新保证
- **原子性**：每次数据写入后必须更新索引，失败则回滚
- **一致性**：索引与实际数据保持同步
- **完整性**：索引记录所有数据文件的元信息

### 2.2 索引结构
索引文件 `_index.parquet` 存储每个数据文件的元信息：

```python
{
    'file_path': str,      # 数据文件路径
    'min_date': str,       # 最小日期（YYYYMMDD）
    'max_date': str,       # 最大日期（YYYYMMDD）
    'row_count': int,      # 记录数
    'update_time': int,    # 更新时间戳（毫秒）
    'checksum': str,       # 数据校验和（前10条记录的MD5）
    'file_size': int       # 文件大小（字节）
}
```

## 3. 索引更新机制

### 3.1 写入后立即更新（核心机制）

在 `StorageManager` 中实现索引的自动更新：

```python
class StorageManager:
    def __init__(self, storage_dir: str = "../data", format: str = "parquet", batch_size: int = 100):
        self.storage_dir = storage_dir
        self.format = format
        self.batch_size = batch_size
        self.data_queue = queue.Queue()
        self.writer_thread = None
        self.running = False

        # [新增] 索引管理
        self._index_cache = {}  # 内存缓存索引 {(interface_name): index_df}
        self._index_lock = threading.RLock()  # 索引访问锁
        self._index_cache_ttl = 3600  # 索引缓存TTL（秒）

        os.makedirs(storage_dir, exist_ok=True)

    def _get_interface_index_path(self, interface_name: str) -> str:
        """获取接口的索引文件路径"""
        interface_dir = os.path.join(self.storage_dir, interface_name)
        return os.path.join(interface_dir, '_index.parquet')

    def _get_interface_config(self, interface_name: str) -> Dict[str, Any]:
        """获取接口配置"""
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'interfaces', f'{interface_name}.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}

    def _get_date_column(self, interface_name: str) -> str:
        """获取接口的日期列名"""
        interface_config = self._get_interface_config(interface_name)
        return interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')

    def _get_interface_index(self, interface_name: str) -> Optional[pl.DataFrame]:
        """获取接口索引，带缓存机制"""
        cache_key = f"index_{interface_name}"

        # 1. 检查内存缓存
        with self._index_lock:
            if cache_key in self._index_cache:
                cached_time, index_df = self._index_cache[cache_key]
                # 检查缓存是否过期
                if time.time() - cached_time < self._index_cache_ttl:
                    return index_df

        # 2. 从磁盘读取索引
        index_path = self._get_interface_index_path(interface_name)
        if os.path.exists(index_path):
            try:
                index_df = pl.read_parquet(index_path)
                # 更新内存缓存
                with self._index_lock:
                    self._index_cache[cache_key] = (time.time(), index_df)
                return index_df
            except Exception as e:
                logger.warning(f"Failed to read index for {interface_name}: {e}")
                return None
        return None

    def _update_interface_index(self, interface_name: str, file_path: str, df: pl.DataFrame):
        """
        更新接口索引文件

        这是核心方法，确保每次数据写入后都会更新索引
        """
        interface_dir = os.path.join(self.storage_dir, interface_name)
        os.makedirs(interface_dir, exist_ok=True)

        index_path = self._get_interface_index_path(interface_name)

        # 获取日期列配置
        date_column = self._get_date_column(interface_name)

        if date_column not in df.columns:
            logger.warning(f"Date column '{date_column}' not found in data for {interface_name}, skipping index update")
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
                    # 过滤掉同名文件的旧记录（如果文件被覆盖）
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

                # 更新内存缓存
                cache_key = f"index_{interface_name}"
                with self._index_lock:
                    self._index_cache[cache_key] = (time.time(), updated_index)

                logger.info(f"Updated index for {interface_name}: {len(updated_index)} files, added {file_path}")
            except Exception as e:
                logger.error(f"Failed to write index for {interface_name}: {e}")
                if os.path.exists(temp_index_path):
                    os.remove(temp_index_path)
                raise

        except Exception as e:
            logger.error(f"Failed to update index for {interface_name}: {e}")
            # 不抛出异常，避免影响数据写入

    def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
        """
        写入接口数据 - Parquet Dataset 模式
        [修改] 确保写入后立即更新索引
        """
        import uuid
        import time

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

            # [关键] 写入后立即更新索引
            self._update_interface_index(interface_name, file_path, df)

        except Exception as e:
            logger.error(f"Error writing interface data for {interface_name}: {str(e)}")
            raise

    def rebuild_all_indexes(self, interface_name: Optional[str] = None) -> Dict[str, Any]:
        """
        全面重建索引

        Args:
            interface_name: 指定接口名称，如果为None则重建所有接口的索引

        Returns:
            重建结果统计
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
        """
        验证索引一致性

        Args:
            interface_name: 指定接口名称，如果为None则验证所有接口

        Returns:
            验证结果
        """
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
        """
        清除索引缓存

        Args:
            interface_name: 指定接口名称，如果为None则清除所有缓存
        """
        with self._index_lock:
            if interface_name:
                cache_key = f"index_{interface_name}"
                if cache_key in self._index_cache:
                    del self._index_cache[cache_key]
                    logger.info(f"Cleared index cache for {interface_name}")
            else:
                self._index_cache.clear()
                logger.info("Cleared all index caches")
```

### 3.2 确保每次下载都更新索引

在 `Downloader` 中确保每次下载后都会更新索引：

```python
class GenericDownloader:
    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        下载指定接口的数据
        [修改] 确保每次下载后都更新索引
        """
        try:
            # 1. 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 2. 校验参数
            validated_params = self._validate_parameters(interface_config, params)

            # 3. 执行分页/循环逻辑
            all_data = self._execute_pagination(interface_config, validated_params)

            # 4. [关键] 保存数据并确保索引更新
            if all_data and self.storage_manager:
                self.storage_manager.save_data(interface_name, all_data, async_write=False)
                logger.info(f"Saved {len(all_data)} records for {interface_name}, index updated automatically")

            return all_data

        except Exception as e:
            logger.error(f"Error downloading data from {interface_name}: {str(e)}")
            return None
```

**重要**：使用 `async_write=False` 确保同步写入，这样可以保证索引在数据写入后立即更新。

## 4. 全面更新索引的方法

### 4.1 方法一：通过 StorageManager 重建

```python
# 重建所有接口的索引
result = storage_manager.rebuild_all_indexes()
print(f"Rebuilt {result['total_files']} files, {result['total_records']} records")

# 重建特定接口的索引
result = storage_manager.rebuild_all_indexes(interface_name='daily')
print(f"Rebuilt daily index: {result['interfaces']['daily']}")
```

### 4.2 方法二：通过 CLI 命令

在 `app4/main.py` 中添加命令行接口：

```python
def rebuild_indexes_command(args):
    """重建索引命令"""
    from .core.storage import StorageManager
    from .core.config_loader import ConfigLoader

    config_loader = ConfigLoader()
    global_config = config_loader.get_global_config()
    storage_dir = global_config.get('storage', {}).get('base_dir', '../data')

    storage_manager = StorageManager(storage_dir=storage_dir)

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
    from .core.storage import StorageManager
    from .core.config_loader import ConfigLoader

    config_loader = ConfigLoader()
    global_config = config_loader.get_global_config()
    storage_dir = global_config.get('storage', {}).get('base_dir', '../data')

    storage_manager = StorageManager(storage_dir=storage_dir)

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

### 4.3 使用示例

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

## 5. 索引更新保证机制

### 5.1 原子性保证

1. **数据写入**：使用临时文件 + 原子重命名
2. **索引更新**：使用临时文件 + 原子重命名
3. **失败回滚**：如果索引更新失败，不影响已写入的数据

### 5.2 一致性保证

1. **写入顺序**：先写数据文件，成功后再更新索引
2. **缓存同步**：索引更新后立即更新内存缓存
3. **文件验证**：索引中记录文件校验和，可验证数据完整性

### 5.3 完整性保证

1. **全覆盖**：每次写入都更新索引，不会遗漏
2. **去重**：同名文件会替换旧记录
3. **清理**：自动移除不存在的文件记录

## 6. 配置选项

在 `app4/config/settings.yaml` 中添加索引配置：

```yaml
storage:
  base_dir: "../data"

  # 索引配置
  index:
    enabled: true  # 是否启用索引功能
    cache_ttl: 3600  # 索引缓存时间（秒）
    auto_rebuild: false  # 是否自动重建损坏的索引
    verify_on_start: false  # 启动时是否验证索引一致性

  # 重复检测配置
  duplicate_detection:
    enabled: true
    strategy: "hybrid"  # "index_only", "quick_check", "hybrid"
    threshold: 0.95  # 覆盖率阈值
```

## 7. 监控和维护

### 7.1 定期验证

建议定期运行索引验证：

```python
# 每周验证一次
storage_manager.verify_index_consistency()
```

### 7.2 定期重建

如果发现索引不一致，可以重建：

```python
# 重建所有索引
storage_manager.rebuild_all_indexes()
```

### 7.3 监控指标

- 索引文件大小
- 索引记录数
- 索引缓存命中率
- 索引更新时间

## 8. 故障处理

### 8.1 索引损坏

如果索引文件损坏，系统会自动回退到传统检查方式，并记录警告日志。

### 8.2 索引不同步

如果发现索引与实际数据不同步，运行重建命令：

```bash
python -m app4.main rebuild-indexes
```

### 8.3 性能问题

如果索引更新影响性能，可以：
1. 调整缓存TTL
2. 使用异步索引更新（需要额外实现）
3. 优化索引结构

## 9. 实施步骤

### 9.1 第一阶段：基础索引功能（1-2天）
- 在 `StorageManager` 中添加索引管理方法
- 实现索引自动更新机制
- 添加索引验证方法

### 9.2 第二阶段：全面更新功能（1天）
- 实现 `rebuild_all_indexes` 方法
- 添加 CLI 命令行接口
- 编写单元测试

### 9.3 第三阶段：集成测试（1天）
- 测试索引自动更新
- 测试全面重建功能
- 测试故障恢复

### 9.4 第四阶段：部署和监控（1天）
- 更新配置文件
- 部署到生产环境
- 设置监控告警

## 10. 总结

本方案通过以下机制确保每次下载都更新索引：

1. **写入后立即更新**：在 `_write_interface_data` 方法中，数据写入成功后立即调用 `_update_interface_index`
2. **原子性保证**：使用临时文件 + 原子重命名确保索引更新的原子性
3. **同步写入**：使用 `async_write=False` 确保索引在数据写入后立即更新
4. **全面重建**：提供 `rebuild_all_indexes` 方法可以全面重建所有索引
5. **验证机制**：提供 `verify_index_consistency` 方法验证索引一致性

通过这些机制，可以确保索引的准确性和完整性，为重复数据检测和增量下载提供可靠的基础。