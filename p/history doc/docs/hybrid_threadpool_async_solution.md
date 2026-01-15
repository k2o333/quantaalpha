# App4 混合线程池异步方案（精简版）

## 1. 核心思想

**保留现有线程池架构**，通过**三级队列**实现异步化：
- **判断层**：内存缓存/Bloom Filter 快速判断（<10ms）
- **下载层**：10线程并发下载
- **保存层**：批量保存 + 异步索引

**优势**：零重构、零新依赖、实施快（2-3天）

## 2. 架构

```
主线程 → 判断 → 下载队列 → 10工作线程 → 保存队列 → 保存线程 → 索引队列 → 索引线程
          (缓存)       (并发下载)           (批量保存)         (后台合并)
```

## 3. 核心组件伪代码

### 3.1 FastCoverageManager - 快速判断

```python
class FastCoverageManager:
    def __init__(self, storage_manager, config_loader):
        self.cache = {}  # {interface: {record_key: timestamp}}
        self.cache_lock = threading.RLock()
        self.cache_ttl = 300  # 5分钟过期
        self.bloom_filters = {}  # 可选
    
    def should_download(self, interface_name, params) -> bool:
        """判断是否需要下载（<10ms）"""
        # 1. 生成记录键
        record_keys = self._generate_keys(interface_name, params)
        
        # 2. 查缓存
        missing = self._check_cache(interface_name, record_keys)
        if missing is not None:  # 缓存完整
            return len(missing) > 0
        
        # 3. 查Bloom Filter（可选）
        if self.use_bloom:
            missing = self._check_bloom(interface_name, record_keys)
            if len(missing) < len(record_keys):
                return True
        
        # 4. 查索引
        if hasattr(self.storage_manager, 'index_manager'):
            existing = self.storage_manager.index_manager.get_existing_records(
                interface_name, **filters
            )
            return len(record_keys - existing) > 0
        
        # 5. 降级
        return True  # 默认下载
    
    def _check_cache(self, interface_name, record_keys):
        """内存缓存检查"""
        with self.cache_lock:
            cache = self.cache.get(interface_name, {})
            
            # 清理过期
            now = time.time()
            for k, t in list(cache.items()):
                if now - t > self.cache_ttl:
                    del cache[k]
            
            # 检查缺失
            missing = {k for k in record_keys if k not in cache}
            
            # 如果部分命中，返回None（表示缓存不完整）
            if 0 < len(missing) < len(record_keys):
                return None
            
            return missing
    
    def update_cache(self, interface_name, record_keys):
        """更新缓存"""
        with self.cache_lock:
            cache = self.cache.setdefault(interface_name, {})
            now = time.time()
            for key in record_keys:
                cache[key] = now

class SimpleBloomFilter:
    """简化版Bloom Filter"""
    def __init__(self, capacity, error_rate=0.001):
        self.size = int(-(capacity * math.log(error_rate)) / (math.log(2)**2))
        self.hash_count = int((self.size / capacity) * math.log(2))
        self.bit_array = 0
    
    def add(self, item):
        for i in range(self.hash_count):
            digest = hashlib.md5(f"{item}{i}".encode()).hexdigest()
            index = int(digest, 16) % self.size
            self.bit_array |= (1 << index)
    
    def contains(self, item):
        for i in range(self.hash_count):
            digest = hashlib.md5(f"{item}{i}".encode()).hexdigest()
            index = int(digest, 16) % self.size
            if not (self.bit_array & (1 << index)):
                return False
        return True
```

### 3.2 AsyncStorageManager - 异步存储

```python
class AsyncStorageManager:
    def __init__(self, storage_dir, config_loader):
        # 复用现有StorageManager
        self.base_storage = StorageManager(storage_dir, config_loader)
        
        # 新增队列
        self.save_queue = queue.Queue(maxsize=1000)
        self.index_queue = queue.Queue(maxsize=10000)
        
        # 启动后台线程
        self.save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self.save_thread.start()
        
        self.index_thread = threading.Thread(target=self._index_worker, daemon=True)
        self.index_thread.start()
    
    def save_data_async(self, interface_name, data, file_path, record_keys=None):
        """异步保存（立即返回）"""
        task = {
            'interface': interface_name,
            'data': data,
            'file_path': file_path,
            'record_keys': record_keys or set()
        }
        
        try:
            self.save_queue.put_nowait(task)
        except queue.Full:
            # 降级：同步保存
            self._save_sync(task)
    
    def _save_worker(self):
        """后台保存线程"""
        while True:
            batch = self._get_batch(self.save_queue, 50)
            if batch:
                self._process_save_batch(batch)
    
    def _get_batch(self, queue, max_size):
        """批量获取任务"""
        batch = []
        try:
            batch.append(queue.get(timeout=1.0))
            while len(batch) < max_size:
                batch.append(queue.get_nowait())
        except (queue.Empty, queue.Full):
            pass
        return batch
    
    def _process_save_batch(self, batch):
        """批量保存"""
        # 按接口分组
        by_interface = {}
        for task in batch:
            iface = task['interface']
            by_interface.setdefault(iface, []).append(task)
        
        # 批量保存
        for iface, tasks in by_interface.items():
            self._save_interface_batch(iface, tasks)
    
    def _save_interface_batch(self, interface_name, tasks):
        """批量保存单个接口"""
        # 按文件分组
        file_groups = {}
        for task in tasks:
            fp = task['file_path']
            file_groups.setdefault(fp, {'data': [], 'keys': set()})
            file_groups[fp]['data'].extend(task['data'])
            file_groups[fp]['keys'].update(task['record_keys'])
        
        # 保存每个文件
        for file_path, group in file_groups.items():
            df = pl.DataFrame(group['data'])
            df.write_parquet(file_path + ".tmp", compression='snappy')
            Path(file_path + ".tmp").rename(file_path)
            
            # 投递到索引队列
            self.index_queue.put({
                'interface': interface_name,
                'file_path': file_path,
                'df': df,
                'keys': group['keys']
            })
    
    def _index_worker(self):
        """后台索引线程"""
        while True:
            batch = self._get_batch(self.index_queue, 100)
            if batch:
                self._process_index_batch(batch)
    
    def _process_index_batch(self, batch):
        """批量更新索引"""
        by_interface = {}
        for task in batch:
            iface = task['interface']
            by_interface.setdefault(iface, []).append(task)
        
        for iface, tasks in by_interface.items():
            for task in tasks:
                self.index_manager.add_records(iface, task['file_path'], task['df'])
```

### 3.3 AsyncGenericDownloader - 异步下载器

```python
class AsyncGenericDownloader:
    def __init__(self, config_loader, storage_manager):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        self.coverage = FastCoverageManager(storage_manager, config_loader)
        
        self.download_queue = queue.Queue(maxsize=100)
        self.num_workers = 10
        self.workers = []
        self.running = False
        self.stats = {'downloaded': 0, 'skipped': 0, 'errors': 0}
    
    def start(self):
        """启动工作线程"""
        self.running = True
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self.workers.append(t)
    
    def stop(self):
        """停止工作线程"""
        self.running = False
        for _ in self.workers:
            self.download_queue.put(None)
        for w in self.workers:
            w.join()
    
    def download_interface(self, interface_name, **params):
        """异步下载（立即返回）"""
        # 1. 生成分页批次
        batches = self._generate_batches(interface_name, params)
        
        # 2. 快速判断
        filtered = []
        for batch in batches:
            if self.coverage.should_download(interface_name, batch):
                filtered.append(batch)
            else:
                self.stats['skipped'] += 1
        
        if not filtered:
            return {'status': 'completed', 'message': 'All records exist'}
        
        # 3. 投递队列
        task_id = f"{interface_name}_{int(time.time() * 1000)}"
        for i, batch in enumerate(filtered):
            task = {
                'id': f"{task_id}_{i}",
                'interface': interface_name,
                'params': batch,
                'retry': 0
            }
            self.download_queue.put(task)
        
        return {'status': 'queued', 'batches': len(filtered)}
    
    def _worker(self):
        """工作线程"""
        while self.running:
            try:
                task = self.download_queue.get(timeout=1.0)
                if task is None:
                    break
                self._execute(task)
            except queue.Empty:
                continue
    
    def _execute(self, task):
        """执行下载任务"""
        try:
            # 1. 下载
            data = self._fetch_data(task['interface'], task['params'])
            
            # 2. 生成记录键
            keys = self.coverage._generate_keys(task['interface'], task['params'])
            
            # 3. 生成文件路径
            file_path = self._generate_filepath(task['interface'], task['params'])
            
            # 4. 异步保存
            self.storage_manager.save_data_async(
                task['interface'], data, file_path, keys
            )
            
            self.stats['downloaded'] += len(data)
            
        except Exception as e:
            # 重试逻辑
            if task['retry'] < 3:
                task['retry'] += 1
                time.sleep(min(2 ** task['retry'], 30))
                self.download_queue.put(task)
            else:
                self.stats['errors'] += 1
```

### 3.4 UnifiedIndexManager - 索引管理

```python
class UnifiedIndexManager:
    def __init__(self, storage_dir, config_loader):
        self.storage_dir = Path(storage_dir)
        self.config_loader = config_loader
        self.daily_index = []  # 内存增量
        self.lock = threading.RLock()
        
        # 启动合并线程
        self.merge_thread = threading.Thread(target=self._periodic_merge, daemon=True)
        self.merge_thread.start()
    
    def add_records(self, interface_name, file_path, df):
        """添加记录（增量）"""
        with self.lock:
            records = []
            for row in df.iter_rows(named=True):
                records.append({
                    "interface": interface_name,
                    "ts_code": row.get('ts_code', ""),
                    "trade_date": str(row.get('trade_date', "")),
                    "file_path": str(file_path),
                    "update_time": int(time.time() * 1000),
                })
            self.daily_index.extend(records)
            
            # 内存过大则刷盘
            if len(self.daily_index) > 10000:
                self._flush()
    
    def _flush(self):
        """刷写增量到磁盘"""
        with self.lock:
            records = self.daily_index.copy()
            self.daily_index.clear()
        
        today = date.today().isoformat()
        path = self.storage_dir / f"index_delta_{today}.parquet"
        
        # 读取现有 + 合并 + 原子写入
        try:
            existing = pl.read_parquet(path)
        except:
            existing = pl.DataFrame()
        
        new_df = pl.DataFrame(records)
        updated = pl.concat([existing, new_df])
        updated.write_parquet(str(path) + ".tmp", compression='snappy')
        Path(str(path) + ".tmp").rename(path)
    
    def _periodic_merge(self):
        """每天凌晨2点合并历史增量"""
        while True:
            # 等待到2点
            self._wait_until(2, 0)
            
            # 执行合并
            self._flush()  # 先刷内存
            
            delta_files = list(self.storage_dir.glob("index_delta_*.parquet"))
            if not delta_files:
                continue
            
            # 读取所有增量
            dfs = [pl.read_parquet(f) for f in delta_files]
            all_delta = pl.concat(dfs)
            
            # 读取主索引
            main_path = self.storage_dir / "index_main.parquet"
            try:
                main_df = pl.read_parquet(main_path)
            except:
                main_df = pl.DataFrame()
            
            # 合并并去重
            combined = pl.concat([main_df, all_delta])
            combined = combined.sort("update_time", descending=True)
            merged = combined.unique(subset=["interface", "ts_code", "trade_date"], keep="first")
            
            # 写入主索引
            merged.write_parquet(str(main_path) + ".tmp", compression='snappy')
            Path(str(main_path) + ".tmp").rename(main_path)
            
            # 删除增量文件
            for f in delta_files:
                f.unlink()
```

## 4. 配置

```yaml
storage:
  base_dir: "../data"
  async:
    enabled: true
    download_workers: 10      # 下载线程数
    save_queue_maxsize: 1000   # 保存队列
    index_queue_maxsize: 10000 # 索引队列

coverage:
  fast_mode: true          # 启用快速判断
  use_bloom_filter: false  # 可选Bloom
  cache_ttl: 300           # 缓存5分钟

index:
  enabled: true
  merge_hour: 2            # 凌晨2点合并
```

## 5. 使用示例

```python
# 初始化
config_loader = ConfigLoader()
storage_manager = AsyncStorageManager("../data", config_loader)
downloader = AsyncGenericDownloader(config_loader, storage_manager)

# 启动
downloader.start()

# 异步下载（立即返回）
result = downloader.download_interface(
    interface_name="daily",
    start_date="20240101",
    end_date="20240131",
    ts_codes=["000001.SZ", "000002.SZ"]
)
print(f"Queued: {result}")

# 等待完成
downloader.wait_completion(timeout=3600)

# 查看统计
stats = downloader.get_stats()
print(f"Downloaded: {stats['total_downloaded']}")
print(f"Throughput: {stats['throughput']:.2f} records/s")

# 停止
downloader.stop()
```

## 6. CLI

```bash
# 下载
python app4/main.py download \
    --interface daily \
    --start-date 20240101 \
    --end-date 20240131 \
    --ts-codes 000001.SZ,000002.SZ

# 重建索引
python app4/main.py rebuild-index
```

## 7. 性能指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 判断延迟 | 1-10ms | 内存缓存/Bloom |
| 下载吞吐量 | 500+ records/sec | 10线程并发 |
| 保存吞吐量 | 2000+ records/sec | 批量保存 |
| 内存占用 | < 500MB | 缓存+队列 |

## 8. 实施计划

**总计：5天**

- Day 1: AsyncStorageManager（包装现有组件）
- Day 2: FastCoverageManager（内存缓存+Bloom）
- Day 3: AsyncGenericDownloader（线程池+队列）
- Day 4: UnifiedIndexManager（增量+合并）
- Day 5: 集成测试和部署

## 9. 监控

```python
# 关键指标
stats = {
    'download_queue_size': downloader.download_queue.qsize(),
    'save_queue_size': storage_manager.save_queue.qsize(),
    'download_throughput': stats['total_downloaded'] / elapsed,
    'cache_hit_rate': cache_hits / total_checks,
}
```

## 10. 总结

**优势**：
- ✅ 零重构：复用现有线程池架构
- ✅ 零依赖：不引入新库
- ✅ 易调试：同步代码为主
- ✅ 实施快：5天完成
- ✅ 性能够：500+ records/sec

**适用**：团队不熟悉asyncio，需快速上线，性能要求适中场景