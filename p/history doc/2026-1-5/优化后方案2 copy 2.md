# Cache 改为 Data 目录去重优化方案（修正版）

**项目**: aspipe_v4/app4  
**日期**: 2026-01-05  
**版本**: v2.1 (修正版 - 修复 Parquet 追加错误)

---

## 目标

彻底去掉 cache 方案，采用 **Parquet Dataset (文件夹存储)** 模式，实现 **Append-Only (追加写)** 高效存储。每次下载的数据直接写入新的分片文件，**读取时自动合并并根据主键去重**。此方案解决了单文件追加导致的损坏风险，同时提升写入性能。

---

## 优化点说明

### 1. 核心目标未完全达成问题修复

**原方案缺陷**: 仅提及新增 Data 去重逻辑，未提及如何移除现有的 `CacheManager`。

**优化方案**:
- 彻底删除 `CacheManager` 相关代码
- 修改 `Downloader` 不再依赖 Cache
- 清理缓存相关配置

### 2. 存储性能瓶颈修复（已修正）⚠️

**原方案缺陷**: 忽略了 `core/storage.py` 现有的严重性能隐患，并引入了**Parquet追加写错误**。

**优化方案**:
- 采用 **Parquet Dataset 模式**（方案 A）
- 每个接口数据存储为目录（如 `data/daily/`），而非单个文件
- 每次写入生成独立分片文件，实现真正的 O(1) 追加性能
- 读取时自动合并目录下所有文件，并执行去重

### 3. 内存与并发风险修复

**原方案缺陷**: `stock_loop` 模式下内存压力大。

**优化方案**:
- 实现分批处理，每收集一定数量数据就立即处理和保存
- 减少内存占用

### 4. 代码逻辑冲突修复

**原方案缺陷**: 与现有 `_remove_duplicates` 方法逻辑冲突。

**优化方案**:
- 彻底重写 `_remove_duplicates` 方法
- 确保与新逻辑兼容

### 5. 依赖管理修复

**新增修复**: 确保 `polars` 库在依赖清单中。

**优化方案**:
- 更新 `requirements.txt`，添加 `polars` 依赖

---

## 改动文件

### 1. `core/storage.py` - 优化写入与读取逻辑（修正后）

采用 Parquet Dataset 模式，并实现读取时去重：

```python
def _write_interface_data(self, interface_name: str, data: List[Dict[str, Any]]):
    """
    写入接口数据 - Parquet Dataset 模式
    """
    import uuid
    
    # 接口数据存储目录
    dir_path = os.path.join(self.storage_dir, interface_name)
    os.makedirs(dir_path, exist_ok=True)
    
    try:
        if not data:
            logger.warning(f"No data to write for {interface_name}")
            return
            
        # 获取接口配置
        interface_config = self._get_interface_config(interface_name)
        # 注意：Dataset 模式写入时不检查主键，仅负责快速写入
        
        # 创建 DataFrame
        df = pl.DataFrame(data)
        
        # 生成唯一文件名: part-{timestamp}-{uuid}.parquet
        timestamp = int(time.time() * 1000)
        unique_id = uuid.uuid4().hex[:8]
        file_name = f"part-{timestamp}-{unique_id}.parquet"
        file_path = os.path.join(dir_path, file_name)
        
        # [修改] 原子写入：先写临时文件，再原子重命名
        # 避免写入中断导致产生损坏的 Parquet 文件
        temp_file_path = file_path + ".tmp"
        df.write_parquet(temp_file_path, compression='snappy')
        os.rename(temp_file_path, file_path)
        
        logger.info(f"Wrote {len(df)} records to {file_path}")
            
    except Exception as e:
        logger.error(f"Error writing interface data for {interface_name}: {str(e)}")
        raise

def read_interface_data(self, interface_name: str, columns: Optional[List[str]] = None) -> pl.DataFrame:
    """
    读取接口数据 - 支持 Dataset 目录读取并自动去重
    """
    dir_path = os.path.join(self.storage_dir, interface_name)
    
    if not os.path.exists(dir_path):
        logger.warning(f"No data found for {interface_name}")
        return pl.DataFrame()
    
    try:
        # 读取整个目录（自动合并所有分片）
        df = pl.read_parquet(dir_path, columns=columns)
        
        # [读取时去重]
        interface_config = self._get_interface_config(interface_name)
        primary_keys = interface_config.get('output', {}).get('primary_key', [])
        
        if primary_keys and not df.is_empty():
            # 确保主键列存在于 DataFrame 中
            existing_keys = [k for k in primary_keys if k in df.columns]
            if existing_keys:
                before = len(df)
                df = df.unique(subset=existing_keys, keep='last')
                after = len(df)
                if before > after:
                    logger.debug(f"Read-time deduplication removed {before - after} records")
        
        return df
    except Exception as e:
        logger.error(f"Error reading interface data for {interface_name}: {str(e)}")
        raise
```

### 2. `core/processor.py` - 完善去重逻辑

重写 `_remove_duplicates` 方法（保持不变，逻辑有效）:

```python
def _remove_duplicates(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """
    移除重复数据 - 启用版
    """
    if df.is_empty():
        return df
        
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])
    
    if not primary_keys:
        logger.warning(f"No primary keys defined for deduplication")
        return df
        
    existing_key_fields = [key for key in primary_keys if key in df.columns]
    
    if not existing_key_fields:
        logger.warning(f"Primary keys not found in DataFrame columns")
        return df
        
    before_dedup = len(df)
    df = df.unique(subset=existing_key_fields, keep='last')
    after_dedup = len(df)
    
    if before_dedup > after_dedup:
        logger.info(f"Removed {before_dedup - after_dedup} duplicates")
        
    return df
```

### 3. `main.py` - 实现分批处理

修改 `run_concurrent_stock_download` 函数（保持不变）:

```python
def run_concurrent_stock_download(downloader, storage_manager, processor, interfaces_to_run, params):
    """
    并发下载股票数据 - 分批处理版
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    all_data = []
    batch_size = 5000  # 每 5000 条数据处理一次
    
    async def download_stock(stock_code):
        async with semaphore:
            try:
                params['stock_code'] = stock_code
                data = await downloader.async_download(interface_name, params)
                return data
            except Exception as e:
                logger.error(f"Error downloading {stock_code}: {str(e)}")
                return []
    
    # 并发下载
    tasks = [download_stock(stock_code) for stock_code in stock_codes]
    results = await asyncio.gather(*tasks)
    
    # 分批处理
    for i, data in enumerate(results):
        if data:
            all_data.extend(data)
            
            # 每 batch_size 条数据处理一次
            if len(all_data) >= batch_size:
                process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
                all_data = []
    
    # 处理剩余数据
    if all_data:
        process_and_save_data(all_data, interface_name, interface_config, processor, storage_manager)
```

### 4. `main.py` - 移除 CacheManager

删除 `CacheManager` 相关代码（保持不变）:

```python
# 删除以下代码：
# from cache.cache_manager import CacheManager
# cache_manager = CacheManager()
# downloader = GenericDownloader(cache_manager=cache_manager)
```

修改为：

```python
# 新的 Downloader 初始化（不依赖 Cache）
downloader = GenericDownloader()
```

### 5. `config/settings.yaml` - 清理配置

删除缓存相关配置（保持不变）:

```yaml
# 删除以下配置：
# cache:
#   type: redis
#   host: localhost
#   port: 6379
```

### 6. `app4/requirements.txt` - 更新依赖

添加缺失的 `polars` 依赖：

```txt
# 数据处理和存储
polars>=0.19.0
# 原有的 pandas 可根据实际情况保留或移除
# pandas>=1.5.0
```

### 7. 关键冲突解决 (Critical Conflict Resolution)

针对 `CacheManager` 移除后产生的代码冲突，采取以下替代方案：

#### A. 交易日历预加载 (`main.py` & `downloader.py`)
- **冲突**: `main.py` 的 `preload_global_trade_calendar` 和 `downloader.py` 的 `_execute_date_range_pagination` 深度依赖 `CacheManager` 来获取/存储交易日历。
- **解决方案**: **以 Data 目录为单一真值来源 (Source of Truth)**。
    1. **Downloader 修改**:
        - 移除 `__init__` 中的 `cache_manager` 参数。
        - 内部维护一个简单的内存字典 `self._memory_cache` (用于本次运行的 `trade_cal` 和 `stock_list`)。
        - 修改 `_get_trade_calendar` 逻辑：
            - 1. 查内存 `self._memory_cache`。
            - 2. (新增) 查 Data 目录 (`data/trade_cal/`)。使用 `pl.read_parquet` 读取并合并，如果有覆盖所需日期范围的数据，则使用。
            - 3. 查 API (TuShare)。
    2. **Main 修改**:
        - 重写 `preload_global_trade_calendar`，不再调用 `cache_manager`，而是直接调用 `downloader.download('trade_cal', ...)` (如果 Data 目录已有则会自动利用，或者直接强制下载并保存到 Data 目录)。

#### B. Downloader 构造函数
- **冲突**: `GenericDownloader` 强制要求 `CacheManager` 实例。
- **解决方案**: 修改 `core/downloader.py` 的 `__init__` 方法，删除 `cache_manager` 参数，并清理所有 `self.cache_manager` 的调用。

#### C. 配置清理
- **冲突**: `settings.yaml` 中移除 `cache` 字段可能导致 `ConfigLoader` 或 `main.py` 读取配置时报错。
- **解决方案**: 确保代码中使用 `.get('cache', {})` 安全读取，或在 `ConfigLoader` 中设置默认空值，防止 KeyError。

#### D. 详细实现逻辑 (Implementation Details)

**1. 股票列表缓存处理**
- **问题**: `downloader.py` 中 `stock_loop` 分页模式依赖 `cache_manager.get_stock_list()`。
- **解决**: 同样采用 Data 目录作为持久化存储 (`data/stock_basic/`)，运行时使用 `self._memory_cache` 加速。

**2. 内存缓存机制设计**
```python
class GenericDownloader:
    def __init__(self, config_loader):
        # ... 其他初始化 ...
        # 运行时简易缓存，替代原有的 CacheManager
        self._memory_cache = {
            'trade_cal': {},      # Key: ('start_date', 'end_date'), Value: list[dict]
            'stock_list': None    # Value: list[dict]
        }
        self._cache_lock = threading.RLock()  # 确保线程安全
```

**3. Data 目录查询逻辑示例**
```python
def _get_trade_calendar_from_data_dir(self, start_date, end_date):
    """从 Data 目录查询交易日历 (Source of Truth)"""
    # 假设存储目录为 data/trade_cal/
    dir_path = os.path.join(self.global_config.get('storage', {}).get('base_dir', '../data'), 'trade_cal')
    
    if not os.path.exists(dir_path):
        return None

    try:
        # 读取目录下所有 parquet 文件 (Dataset 模式)
        # 注意: 如果文件很多，这一步可能会慢，后续可考虑优化为只读取特定分区
        df = pl.read_parquet(dir_path)
        
        if df.is_empty():
            return None

        # 过滤日期范围并去重
        # 必须去重，因为 Dataset 模式下可能有重复数据
        filtered_df = df.filter(
            (pl.col('cal_date') >= start_date) &
            (pl.col('cal_date') <= end_date) &
            (pl.col('is_open') == 1)
        ).unique(subset=['cal_date'], keep='last').sort('cal_date')
        
        if filtered_df.is_empty():
            return None

        return filtered_df.to_dicts()
        
    except Exception as e:
        logger.warning(f"Failed to read trade calendar from Data dir: {e}")
        return None
```

---

## 实施步骤

1. **备份现有代码**: 在修改前备份相关文件
2. **更新依赖**: 修改 `app4/requirements.txt`，添加 `polars`
3. **移除 CacheManager**: 删除 `main.py` 中 CacheManager 相关代码
4. **优化存储逻辑**: 修改 `core/storage.py`，采用 Parquet Dataset 模式
5. **完善去重逻辑**: 重写 `core/processor.py` 中的 `_remove_duplicates` 方法
6. **实现分批处理**: 修改 `main.py` 中的 `run_concurrent_stock_download` 函数
7. **清理配置**: 删除 `config/settings.yaml` 中的缓存配置
8. **测试**: 
   - 运行单元测试，确保功能正常
   - 验证 Dataset 读取：`pl.read_parquet("data/daily/")` 能正确合并数据
   - 验证去重逻辑：主键重复时正确过滤
9. **性能测试**: 测试大文件处理和并发下载性能

---

## 预期效果

1. **彻底去掉 cache**: 不再使用 CacheManager，减少存储冗余
2. **性能提升**: 写入时无需读取旧数据，实现 O(1) 追加，减少 IO 开销
3. **内存优化**: 分批处理减少内存占用
4. **逻辑一致**: 去重逻辑统一，避免冲突
5. **配置整洁**: 清理无用配置
6. **文件安全**: 避免 Parquet 追加写导致的文件损坏问题

---

## 风险评估

1. **数据一致性 (重复数据)**: 
   - **风险**: Dataset 模式是 Append-Only 的，重复下载会导致磁盘上存在重复数据。
   - **对策**: 已在 `read_interface_data` 中实现**读取时去重** (`Read-time Deduplication`)，确保业务层获取的数据是唯一的。
2. **小文件问题 (Small Files)**: 
   - **风险**: 高频分批写入会产生大量小文件（KB级别），可能导致 inode 耗尽或读取性能下降。
   - **对策**: 建议后续增加 `compact` 命令，定期将目录下的多个小文件合并为大文件。
3. **兼容性**: Dataset 读取需要 `polars >= 0.19.0`，需严格锁定依赖版本。
4. **存储空间**: 由于允许磁盘存在重复数据（直到去重/合并），可能会占用比去重后更多的磁盘空间。

---

## 后续建议

1. **实现 Compaction**: 开发一个定期任务或 CLI 命令（如 `python app4/main.py --compact`），读取 Dataset 目录，去重后覆写为一个或少数几个大文件。
2. **监控**: 添加对数据目录文件数量的监控，当文件数超过阈值（如 1000 个）时报警或自动触发合并。
3. **事务支持**: 考虑写入临时文件后原子移动，确保写入原子性。
4. **文档**: 更新相关文档，说明 Dataset 模式的使用方法和磁盘空间特性。