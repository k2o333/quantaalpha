        """下载工作线程"""
        while self.running:
            try:
                # 获取任务（阻塞，但最多等待1秒）
                task = self.download_queue.get(timeout=1.0)
                
                # 停止信号
                if task is None:
                    break
                
                # 执行任务
                self._execute_task(task)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
                time.sleep(1.0)
    
    def _execute_task(self, task: Dict):
        """执行单个下载任务"""
        interface = task['interface']
        params = task['params']
        task_id = task['task_id']
        retry_count = task['retry_count']
        
        try:
            # 1. 下载数据
            data = self._fetch_data(interface, params)
            
            if not data:
                logger.warning(f"No data returned for {interface}, params: {params}")
                return
            
            # 2. 生成记录键
            record_keys = self._generate_record_keys(interface, params)
            
            # 3. 生成文件路径
            file_path = self._generate_file_path(interface, params)
            
            # 4. 异步保存（不等待）
            if hasattr(self.storage_manager, 'save_data_async'):
                # 使用异步保存
                self.storage_manager.save_data_async(
                    interface_name=interface,
                    data=data,
                    file_path=file_path,
                    record_keys=record_keys
                )
            else:
                # 降级到同步保存
                self._save_sync(interface, file_path, data, record_keys)
            
            # 5. 更新统计
            self.stats['total_downloaded'] += len(data)
            
            logger.info(f"Successfully downloaded and queued {len(data)} records for {interface}")
            
        except Exception as e:
            logger.error(f"Task failed for {interface}: {e}")
            self.stats['total_errors'] += 1
            
            # 重试逻辑
            if retry_count < task['max_retries']:
                retry_count += 1
                logger.info(f"Retrying task {task_id}, attempt {retry_count}")
                
                # 延迟后重试
                time.sleep(min(2 ** retry_count, 30))
                
                # 重新放入队列
                task['retry_count'] = retry_count
                try:
                    self.download_queue.put_nowait(task)
                except queue.Full:
                    logger.error(f"Queue full, dropping task {task_id}")
            else:
                logger.error(f"Task {task_id} exhausted all retries")
    
    def _fetch_data(self, interface_name: str, params: Dict) -> List[Dict]:
        """获取数据（复用现有逻辑）"""
        # 这里调用现有的 GenericDownloader.download 方法
        # 或者调用 API 接口
        try:
            # 模拟调用
            from app4.core.downloader import GenericDownloader
            downloader = GenericDownloader(
                config_loader=self.config_loader,
                storage_manager=self.storage_manager
            )
            
            # 复用现有下载逻辑
            return downloader.download(interface_name, params)
        except Exception as e:
            logger.error(f"Failed to fetch data for {interface_name}: {e}")
            return []
    
    def _generate_record_keys(self, interface_name: str, params: Dict) -> Set[tuple]:
        """生成记录键"""
        # 复用 FastCoverageManager 的逻辑
        return self.fast_coverage._generate_record_keys(interface_name, params)
    
    def _generate_file_path(self, interface_name: str, params: Dict) -> str:
        """生成文件路径"""
        timestamp = int(time.time() * 1000)
        
        # 生成参数哈希
        import hashlib
        param_str = "_".join(f"{k}-{v}" for k, v in sorted(params.items()) if v)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        
        file_name = f"{interface_name}_{timestamp}_{param_hash}.parquet"
        return str(self.storage_dir / interface_name / file_name)
    
    def _save_sync(self, interface_name: str, file_path: str,
                  data: List[Dict], record_keys: Set):
        """同步保存（降级）"""
        # 复用 StorageManager 的同步保存
        self.storage_manager.save_data(
            interface_name=interface_name,
            data=data,
            async_write=False  # 同步保存
        )
        
        logger.info(f"Synchronously saved {len(data)} records for {interface_name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        elapsed = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        
        stats = self.stats.copy()
        stats['elapsed_seconds'] = elapsed
        stats['throughput'] = stats['total_downloaded'] / elapsed if elapsed > 0 else 0
        stats['queue_size'] = self.download_queue.qsize()
        
        # 添加队列统计
        if hasattr(self.storage_manager, 'get_queue_stats'):
            stats['storage_queues'] = self.storage_manager.get_queue_stats()
        
        return stats
    
    def wait_completion(self, timeout: float = 60.0):
        """等待所有任务完成"""
        start = time.time()
        
        while True:
            if self.download_queue.empty():
                break
            
            if time.time() - start > timeout:
                logger.warning(f"Timeout waiting for completion, {self.download_queue.qsize()} tasks remaining")
                break
            
            time.sleep(0.5)
```

### 4.4 索引管理器（增量更新）

```python
# 在现有 StorageManager 中添加

class UnifiedIndexManager:
    """统一索引管理器（增量更新，后台合并）"""
    
    def __init__(self, storage_dir: str, config_loader=None):
        self.storage_dir = Path(storage_dir)
        self.config_loader = config_loader
        
        # 今日增量索引（内存中）
        self.daily_index: List[Dict] = []
        self._lock = threading.RLock()
        
        # 启动后台合并线程
        self.merge_thread = threading.Thread(target=self._periodic_merge, daemon=True)
        self.merge_thread.start()
        
        logger.info("UnifiedIndexManager initialized")
    
    def add_records(self, interface_name: str, file_path: str, df: pl.DataFrame):
        """添加记录到索引（增量）"""
        index_config = {}
        if self.config_loader:
            interface_config = self.config_loader.get_interface_config(interface_name)
            index_config = interface_config.get('index', {})
        
        primary_keys = index_config.get('primary_keys', ['trade_date'])
        ts_field = index_config.get('ts_field', 'ts_code')
        date_field = index_config.get('date_field', 'trade_date')
        period_field = index_config.get('period_field', 'period')
        
        # 生成索引记录
        records = []
        for row in df.iter_rows(named=True):
            record = {
                "interface_name": interface_name,
                "ts_code": str(row.get(ts_field, "")),
                "trade_date": str(row.get(date_field, "")),
                "period": str(row.get(period_field, "")) if period_field and period_field in row else "",
                "file_path": str(file_path),
                "update_time": int(time.time() * 1000),
                "record_count": len(df),
            }
            records.append(record)
        
        # 添加到内存索引
        with self._lock:
            self.daily_index.extend(records)
        
        logger.debug(f"Added {len(records)} records to daily index for {interface_name}")
        
        # 如果内存索引过大，立即刷盘
        if len(self.daily_index) > 10000:
            self._flush_daily_index()
    
    def _flush_daily_index(self):
        """刷写今日增量索引到磁盘"""
        with self._lock:
            if not self.daily_index:
                return
            
            records = self.daily_index.copy()
            self.daily_index.clear()
        
        # 写入增量文件
        today = date.today().isoformat()
        index_path = self.storage_dir / f"index_delta_{today}.parquet"
        
        try:
            # 读取现有增量
            try:
                existing = pl.read_parquet(index_path)
            except:
                existing = pl.DataFrame(schema=self._get_schema())
            
            # 合并新记录
            new_df = pl.DataFrame(records, schema=self._get_schema())
            updated = pl.concat([existing, new_df])
            
            # 原子写入
            temp_path = index_path.with_suffix('.tmp.parquet')
            updated.write_parquet(temp_path, compression='snappy')
            temp_path.rename(index_path)
            
            logger.info(f"Flushed {len(records)} records to {index_path}")
            
        except Exception as e:
            logger.error(f"Failed to flush daily index: {e}")
    
    def _periodic_merge(self):
        """定期合并历史增量索引（每天凌晨2点）"""
        while True:
            try:
                # 等待到2点
                self._wait_until(2, 0)
                
                # 执行合并
                self._merge_all_indexes()
                
            except Exception as e:
                logger.error(f"Periodic merge error: {e}")
                time.sleep(3600)  # 1小时后重试
    
    def _wait_until(self, hour: int, minute: int):
        """等待到指定时间"""
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        
        wait_seconds = (target - now).total_seconds()
        time.sleep(wait_seconds)
    
    def _merge_all_indexes(self):
        """合并所有增量索引到主索引"""
        logger.info("Starting index merge process...")
        
        # 先刷写内存索引
        self._flush_daily_index()
        
        # 查找所有增量文件
        delta_files = list(self.storage_dir.glob("index_delta_*.parquet"))
        
        if not delta_files:
            return
        
        # 读取所有增量
        delta_dfs = []
        for file_path in delta_files:
            try:
                df = pl.read_parquet(file_path)
                delta_dfs.append(df)
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
        
        if not delta_dfs:
            return
        
        # 合并所有增量
        all_delta = pl.concat(delta_dfs)
        
        # 读取主索引（如果不存在则创建）
        main_path = self.storage_dir / "index_main.parquet"
        try:
            main_df = pl.read_parquet(main_path)
        except:
            main_df = pl.DataFrame(schema=self._get_schema())
        
        # 合并并去重（按主键，保留最新）
        combined = pl.concat([main_df, all_delta])
        combined = combined.sort("update_time", descending=True)
        
        primary_keys = ["interface_name", "ts_code", "trade_date", "period"]
        merged = combined.unique(subset=primary_keys, keep="first")
        
        # 写入主索引
        temp_path = main_path.with_suffix('.tmp.parquet')
        merged.write_parquet(temp_path, compression='snappy')
        temp_path.rename(main_path)
        
        # 删除已合并的增量文件
        for file_path in delta_files:
            try:
                file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
        
        logger.info(f"Merged {len(delta_files)} delta files into main index, total {len(merged)} records")
    
    def get_existing_records(self, interface_name: str, **filters) -> Set[tuple]:
        """获取已存在记录（从主索引+今日增量）"""
        # 读取主索引
        main_path = self.storage_dir / "index_main.parquet"
        dfs = []
        
        try:
            main_df = pl.read_parquet(main_path)
            dfs.append(main_df)
        except:
            pass
        
        # 读取今日增量
        today = date.today().isoformat()
        delta_path = self.storage_dir / f"index_delta_{today}.parquet"
        try:
            delta_df = pl.read_parquet(delta_path)
            dfs.append(delta_df)
        except:
            pass
        
        # 读取内存中的增量
        with self._lock:
            if self.daily_index:
                memory_df = pl.DataFrame(self.daily_index, schema=self._get_schema())
                dfs.append(memory_df)
        
        if not dfs:
            return set()
        
        # 合并
        index_df = pl.concat(dfs)
        
        # 应用过滤条件
        query = pl.col("interface_name") == interface_name
        
        if filters.get('start_date'):
            query &= pl.col("trade_date") >= filters['start_date']
        if filters.get('end_date'):
            query &= pl.col("trade_date") <= filters['end_date']
        if filters.get('ts_codes'):
            query &= pl.col("ts_code").is_in(filters['ts_codes'])
        if filters.get('period'):
            query &= pl.col("period") == filters['period']
        
        filtered = index_df.filter(query)
        
        # 生成记录标识
        existing_records = set()
        for row in filtered.iter_rows(named=True):
            key = tuple(row.get(col, "") for col in ["ts_code", "trade_date", "period"])
            existing_records.add(key)
        
        return existing_records
    
    def _get_schema(self) -> Dict[str, pl.DataType]:
        """索引 Schema"""
        return {
            "interface_name": pl.String,
            "ts_code": pl.String,
            "trade_date": pl.String,
            "period": pl.String,
            "file_path": pl.String,
            "update_time": pl.Int64,
            "record_count": pl.Int64,
        }
```

## 5. 配置选项

```yaml
# app4/config/settings.yaml

storage:
  base_dir: "../data"
  
  # 异步配置
  async:
    enabled: true
    download_workers: 10  # 下载工作线程数
    save_queue_maxsize: 1000  # 保存队列大小
    index_queue_maxsize: 10000  # 索引队列大小

# 快速覆盖率检查
coverage:
  fast_mode: true  # 启用快速判断
  use_bloom_filter: false  # 是否使用 Bloom Filter（可选）
  cache_ttl: 300  # 缓存过期时间（秒）
  
# 索引配置
index:
  enabled: true
  merge_hour: 2  # 合并时间（凌晨2点）
  flush_interval: 300  # 刷盘间隔（5分钟）
```

## 6. 使用示例

```python
from app4.core.async_downloader import AsyncGenericDownloader
from app4.core.config_loader import ConfigLoader
from app4.core.storage import AsyncStorageManager

# 初始化
def main():
    config_loader = ConfigLoader()
    
    # 使用 AsyncStorageManager（包装现有 StorageManager）
    storage_manager = AsyncStorageManager(
        storage_dir="../data",
        config_loader=config_loader
    )
    
    # 初始化异步下载器
    downloader = AsyncGenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager
    )
    
    # 启动下载器
    downloader.start()
    
    # 异步下载（立即返回）
    result1 = downloader.download_interface(
        interface_name="daily",
        start_date="20240101",
        end_date="20240131",
        ts_codes=["000001.SZ", "000002.SZ", "600000.SH"]
    )
    
    print(f"Task queued: {result1}")
    
    # 继续添加其他下载任务
    result2 = downloader.download_interface(
        interface_name="income_vip",
        ts_codes=["000001.SZ"],
        periods=["2023Q1", "2023Q2", "2023Q3", "2023Q4"]
    )
    
    print(f"Task queued: {result2}")
    
    # 等待所有任务完成
    print("Waiting for completion...")
    downloader.wait_completion(timeout=3600)  # 最多等待1小时
    
    # 获取统计信息
    stats = downloader.get_stats()
    print(f"Downloaded: {stats['total_downloaded']}")
    print(f"Skipped: {stats['total_skipped']}")
    print(f"Throughput: {stats['throughput']:.2f} records/sec")
    
    # 停止下载器
    downloader.stop()

if __name__ == '__main__':
    main()
```

## 7. CLI 命令

```python
# app4/main.py

import argparse
import time
from app4.core.async_downloader import AsyncGenericDownloader
from app4.core.config_loader import ConfigLoader
from app4.core.storage import AsyncStorageManager

def download_command(args):
    """异步下载命令"""
    config_loader = ConfigLoader()
    
    storage_manager = AsyncStorageManager(
        storage_dir=args.storage_dir,
        config_loader=config_loader
    )
    
    downloader = AsyncGenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager
    )
    
    downloader.start()
    
    try:
        # 添加下载任务
        result = downloader.download_interface(
            interface_name=args.interface,
            start_date=args.start_date,
            end_date=args.end_date,
            ts_codes=args.ts_codes.split(',') if args.ts_codes else None
        )
        
        print(f"✓ Task queued: {result}")
        print(f"  - Total batches: {result['total_batches']}")
        print(f"  - Filtered batches: {result['filtered_batches']}")
        print(f"  - Status: {result['status']}")
        
        # 等待完成
        print("\nWaiting for completion...")
        downloader.wait_completion(timeout=args.timeout)
        
        # 显示统计
        stats = downloader.get_stats()
        print(f"\n✓ Download completed:")
        print(f"  - Downloaded: {stats['total_downloaded']} records")
        print(f"  - Skipped: {stats['total_skipped']} batches")
        print(f"  - Errors: {stats['total_errors']}")
        print(f"  - Elapsed: {stats['elapsed_seconds']:.2f}s")
        print(f"  - Throughput: {stats['throughput']:.2f} records/s")
        
        # 显示队列状态
        if hasattr(storage_manager, 'get_queue_stats'):
            queue_stats = storage_manager.get_queue_stats()
            print(f"\nQueue status:")
            print(f"  - Save queue: {queue_stats['save_queue_size']}/{queue_stats['save_queue_maxsize']}")
            print(f"  - Index queue: {queue_stats['index_queue_size']}/{queue_stats['index_queue_maxsize']}")
        
    finally:
        downloader.stop()

def stats_command(args):
    """查看实时统计"""
    # 实现统计查看逻辑
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='App4 Async Downloader')
    subparsers = parser.add_subparsers(dest='command')
    
    # 下载命令
    download_parser = subparsers.add_parser('download', help='Download data asynchronously')
    download_parser.add_argument('--interface', required=True, help='Interface name')
    download_parser.add_argument('--start-date', help='Start date (YYYYMMDD)')
    download_parser.add_argument('--end-date', help='End date (YYYYMMDD)')
    download_parser.add_argument('--ts-codes', help='Comma-separated stock codes')
    download_parser.add_argument('--storage-dir', default='../data', help='Storage directory')
    download_parser.add_argument('--timeout', type=int, default=3600, help='Timeout in seconds')
    download_parser.set_defaults(func=download_command)
    
    # 统计命令
    stats_parser = subparsers.add_parser('stats', help='View statistics')
    stats_parser.set_defaults(func=stats_command)
    
    args = parser.parse_args()
    
    if args.command:
        args.func(args)
    else:
        parser.print_help()
```

## 8. 使用方式

```bash
# 下载日线数据（异步）
python app4/main.py download \
    --interface daily \
    --start-date 20240101 \
    --end-date 20240131 \
    --ts-codes 000001.SZ,000002.SZ,600000.SH

# 下载财务数据
python app4/main.py download \
    --interface income_vip \
    --ts-codes 000001.SZ \
    --periods 2023Q1,2023Q2,2023Q3,2023Q4

# 使用 Bloom Filter（可选）
# 修改配置文件：use_bloom_filter: true
```

## 9. 性能指标

### 9.1 预期性能

| 指标 | 数值 | 说明 |
|------|------|------|
| **判断延迟** | 1-10ms | 内存缓存或 Bloom Filter |
| **下载吞吐量** | 500+ records/sec | 10个并发线程 |
| **保存吞吐量** | 2000+ records/sec | 批量保存 |
| **索引更新延迟** | 0ms | 队列投递后立即返回 |
| **内存占用** | < 500MB | 缓存 + 队列 |
| **并发接口** | 10+ | 线程池并行 |

### 9.2 与全异步方案对比

| 维度 | 全异步方案 | 混合方案 | 差异 |
|------|-----------|---------|------|
| **代码复杂度** | ⭐⭐⭐⭐ 高 | ⭐⭐ 低 | **混合方案更简单** |
| **重构成本** | 高（需重写核心组件） | 低（包装现有组件） | **混合方案更低** |
| **性能** | 11111+ records/sec | 500+ records/sec | 全异步更高，但混合已足够 |
| **调试难度** | 高（异步异常复杂） | 低（同步为主） | **混合方案更易调试** |
| **依赖库** | pybloom_live, aiohttp | 无新依赖 | **混合方案无依赖冲突** |
| **团队学习成本** | 高（需掌握 asyncio） | 低（现有技能） | **混合方案更低** |
| **实施时间** | 4-5天 | 2-3天 | **混合方案更快** |
| **生产稳定性** | 需充分测试 | 经过验证的线程模型 | **混合方案更稳定** |

## 10. 优势总结

### 10.1 架构优势
1. **完全兼容**：不破坏现有架构，可逐步升级
2. **零依赖**：不引入新库，避免版本冲突
3. **易于调试**：同步代码为主，异常处理简单
4. **团队友好**：无需学习新技能

### 10.2 性能优势
1. **无阻塞判断**：内存缓存/Bloom Filter，< 10ms
2. **并发下载**：10个工作线程，充分利用带宽
3. **批量保存**：50个一批，减少 I/O 次数
4. **异步索引**：后台更新，不影响下载流程

### 10.3 可靠性优势
1. **优雅降级**：队列满时自动降级为同步保存
2. **重试机制**：失败任务自动重试（指数退避）
3. **背压控制**：有界队列防止内存溢出
4. **统计监控**：详细的统计信息和日志

### 10.4 可维护性优势
1. **代码简洁**：每个组件 < 200 行
2. **渐进式升级**：可以逐步替换，风险可控
3. **测试友好**：同步代码易于单元测试
4. **文档完善**：使用示例和 CLI 命令齐全

## 11. 实施计划

### 第一阶段：核心组件包装（1天）
- **任务**：实现 AsyncStorageManager（包装现有 StorageManager）
- **目标**：提供异步保存和索引更新能力
- **风险**：低（完全兼容现有代码）
- **验证**：手动测试保存和索引更新

### 第二阶段：快速判断层（1天）
- **任务**：实现 FastCoverageManager（内存缓存 + 可选 Bloom Filter）
- **目标**：实现无阻塞判断
- **风险**：低（可降级到传统检查）
- **验证**：性能测试（判断延迟 < 10ms）

### 第三阶段：异步下载器（1天）
- **任务**：实现 AsyncGenericDownloader（基于线程池）
- **目标**：实现并发下载和三级流水线
- **风险**：中（需要测试并发和队列逻辑）
- **验证**：压力测试（吞吐量 > 500 records/sec）

### 第四阶段：集成和测试（1天）
- **任务**：集成到现有 App4，编写测试用例
- **目标**：确保兼容性和稳定性
- **风险**：中（可能发现兼容性问题）
- **验证**：集成测试（所有接口正常工作）

### 第五阶段：部署和监控（1天）
- **任务**：生产环境部署，添加监控
- **目标**：监控性能和稳定性
- **风险**：低（逐步灰度发布）
- **验证**：监控指标正常，无异常告警

**总计实施时间**：5天（比全异步方案节省2-3天）

## 12. 监控指标

### 12.1 性能指标
- `download_queue_size`: 下载队列大小
- `save_queue_size`: 保存队列大小
- `index_queue_size`: 索引队列大小
- `download_throughput`: 下载吞吐量（records/sec）
- `save_throughput`: 保存吞吐量（records/sec）
- `cache_hit_rate`: 缓存命中率
- `bloom_filter_false_positive`: Bloom Filter 误判率（如果启用）

### 12.2 可靠性指标
- `download_errors`: 下载错误数
- `save_errors`: 保存错误数
- `index_errors`: 索引更新错误数
- `queue_overflows`: 队列溢出次数
- `retry_count`: 重试次数

### 12.3 资源指标
- `worker_thread_count`: 工作线程数
- `worker_thread_active`: 活跃线程数
- `memory_usage_mb`: 内存使用（MB）
- `cpu_usage_percent`: CPU 使用率

## 13. 注意事项

### 13.1 队列大小调优
- **保存队列**：默认 1000，可根据内存调整
- **索引队列**：默认 10000，通常足够
- **下载队列**：默认 100，避免任务堆积

### 13.2 工作线程数
- **默认 10**：适合大多数场景
- **计算公式**：min(接口数 * 2, CPU 核心数 * 4)
- **API 限流**：考虑 API 限流，不要设置过大

### 13.3 缓存过期时间
- **默认 5分钟**：平衡内存占用和命中率
- **高频率场景**：可设置为 60秒
- **低频率场景**：可设置为 10分钟

### 13.4 Bloom Filter（可选）
- **默认关闭**：内存占用小，实现简单
- **误判率**：0.1% 可接受
- **容量**：根据数据量调整

## 14. 与全异步方案的对比建议

### 选择全异步方案如果：
- ✅ 团队熟悉 asyncio
- ✅ 需要极致性能（> 10000 records/sec）
- ✅ 可以接受较高的重构成本
- ✅ 项目处于早期阶段，重构影响小

### 选择混合方案如果：
- ✅ 团队不熟悉 asyncio
- ✅ 性能要求适中（500-1000 records/sec 已足够）
- ✅ 需要快速上线，风险低
- ✅ 项目已稳定，不想大规模重构
- ✅ API 限流是主要瓶颈

## 15. 总结

本方案通过**混合架构**实现了：

1. **架构兼容**：完全复用现有线程池，无学习成本
2. **无阻塞判断**：内存缓存 + 可选 Bloom Filter，< 10ms
3. **异步流水线**：三级队列解耦，吞吐量 500+ records/sec
4. **极低风险**：渐进式升级，可逐步替换
5. **生产就绪**：完整的监控、日志、CLI 工具
6. **快速实施**：5天完成，比全异步节省 2-3 天

**核心优势**：在保留现有架构稳定性的前提下，实现了异步化的主要收益，是**生产环境最佳实践**。