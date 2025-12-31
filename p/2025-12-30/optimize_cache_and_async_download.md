# aspipe_v4 优化方案：激活缓存和异步下载

## 概述

当前 aspipe_v4 App4 存在以下问题：
1. **数据缓存未激活**：只缓存股票列表和交易日历，不缓存接口业务数据（如 pro_bar）
2. **下载同步串行**：虽然有 ThreadPoolExecutor，但在 main.py 中未使用，导致下载效率低下
3. **资源浪费**：重复运行时重新下载数据，浪费时间

## 现状分析

### 1. 缓存现状

#### 已实现的缓存功能

**位置**：`app4/core/cache_manager.py`

| 缓存类型 | 方法 | 缓存时长 | 说明 |
|---------|------|---------|------|
| 股票列表 | `get_stock_list()` / `set_stock_list()` | 24小时 | 存储全部股票基本信息 |
| 交易日历 | `get_trade_calendar()` / `set_trade_calendar()` | 24小时 | 按日期范围缓存交易日历 |
| 通用缓存 | `get()` / `set()` | 24小时（默认） | 支持任意键值对 |

#### 缓存使用位置

**股票列表缓存**（`downloader.py:237-252`）：
```python
stock_list = self.cache_manager.get_stock_list()
if stock_list is None:
    # 缓存未命中，从API获取
    stock_list = self._make_request(...)
    self.cache_manager.set_stock_list(stock_list)
else:
    logger.info(f"从缓存获取到 {len(stock_list)} 只股票")
```

**交易日历缓存**（`downloader.py:130-145`）：
```python
# 检查交易日历缓存
trade_calendar = self.cache_manager.get_trade_calendar(start_date, end_date)
if trade_calendar is None:
    # 缓存未命中，从API获取
    trade_calendar = self._make_request(...)
    self.cache_manager.set_trade_calendar(start_date, end_date, trade_calendar)
```

#### 缺失的缓存

**业务数据未缓存**：
- `pro_bar` 数据（日线行情）
- 其他接口数据（每日行情、财务数据等）

每次运行都会重新下载这些数据，即使数据已经下载过。

### 2. 下载现状

#### 已实现的并发能力

**位置**：`app4/core/scheduler.py`

```python
class TaskScheduler:
    def __init__(self, max_workers: int = 8):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit_task(self, func: Callable, *args, **kwargs) -> Any:
        """提交单个任务到线程池"""
        future = self.executor.submit(func, *args, **kwargs)
        return future

    def submit_tasks(self, tasks: List[Dict[str, Any]]) -> List[Any]:
        """批量提交任务到线程池"""
        futures = []
        for task in tasks:
            func = task['func']
            args = task.get('args', ())
            kwargs = task.get('kwargs', {})
            future = self.executor.submit(func, *args, **kwargs)
            futures.append(future)

        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Task execution error: {str(e)}")
                results.append(None)
        return results
```

#### 实际使用情况

**问题**：虽然定义了 `TaskScheduler`，但在 `main.py` 中**没有使用**：

```python
# main.py:211 - 直接调用，没有使用并发
data = downloader.download(interface_name, params)
```

**下载流程**（`downloader.py`）：
```
download()
├── _execute_date_range_pagination()  # 日期范围分页（同步）
│   ├── get_trade_calendar()          # 获取交易日历
│   ├── _make_request()               # API请求（同步）
│   └── 循环下载各个时间窗口
└── _execute_stock_loop_pagination()  # 股票循环分页（同步）
    ├── get_stock_list()              # 获取股票列表
    └── for stock in stock_list:      # 串行遍历每只股票
        ├── get_trade_calendar()
        ├── _execute_date_range_pagination()
        └── _make_request()
```

#### 性能瓶颈

**下载一只股票的时间**（从日志）：
- 000001.SZ：34 秒（8264 条记录）
  - 获取交易日历：20 秒
  - 下载窗口1：7 秒（5782 条）
  - 下载窗口2：6 秒（2482 条）
- 000002.SZ：~34 秒

**5470 只股票的总时间**：
- 串行下载：5470 × 34 秒 ≈ **51 小时**
- 8 并发下载：51 小时 ÷ 8 ≈ **6.4 小时**

### 3. 存储现状

#### 已实现的异步存储

**位置**：`app4/core/storage.py`

```python
class StorageManager:
    def __init__(self, batch_size: int = 100):
        self.data_queue = queue.Queue()
        self.writer_thread = None

    def start_writer(self):
        """启动写入线程"""
        self.writer_thread = threading.Thread(target=self._writer_worker, daemon=True)
        self.writer_thread.start()

    def _writer_worker(self):
        """后台写入线程"""
        while self.running:
            batch_data = []
            # 从队列中批量获取数据
            item = self.data_queue.get(timeout=1)
            batch_data.append(item)

            while len(batch_data) < self.batch_size:
                try:
                    item = self.data_queue.get_nowait()
                    batch_data.append(item)
                except queue.Empty:
                    break

            self._write_batch(batch_data)

    def save_data(self, interface_name: str, data: List[Dict], async_write: bool = True):
        """保存数据"""
        if async_write:
            # 放入队列，异步写入
            self.data_queue.put({
                'interface_name': interface_name,
                'data': data
            })
        else:
            # 同步写入
            self._write_interface_data(interface_name, data)
```

**结论**：存储已经是**完全异步的**，无需修改。

---

## 优化方案

### 目标

1. **激活业务数据缓存**：避免重复下载已获取的数据
2. **实现异步下载**：使用 ThreadPoolExecutor 并发下载多只股票
3. **保持向后兼容**：不影响现有功能

### 方案设计

#### 1. 激活业务数据缓存

##### 缓存策略

**缓存键设计**：
```
格式：{interface_name}_{ts_code}_{start_date}_{end_date}_{adj}
示例：pro_bar_000001.SZ_19910403_20251230_qfq
```

**缓存内容**：
- 原始返回的 dict 列表（与 API 返回格式一致）

**缓存 TTL**：
- 股票数据：7天（股票历史数据一般不会频繁变化）
- 交易日历：24小时（保持不变）

**缓存逻辑**：
```
下载前：
  1. 生成缓存键
  2. 尝试从缓存获取
  3. 如果缓存命中，直接返回缓存数据
  4. 如果缓存未命中，从 API 下载
  5. 下载成功后，将数据写入缓存
```

##### 实现修改

**文件**：`app4/core/cache_manager.py`

新增方法：
```python
def get_interface_data(self, interface_name: str, params: Dict[str, Any], ttl: Optional[int] = None) -> Optional[List[Dict]]:
    """
    获取接口数据缓存

    Args:
        interface_name: 接口名称（如 'pro_bar'）
        params: 请求参数（用于生成缓存键）
        ttl: 缓存时间（秒）

    Returns:
        缓存数据或 None
    """
    if ttl is None:
        ttl = 604800  # 默认7天

    # 生成缓存键
    cache_key = self._generate_interface_cache_key(interface_name, params)

    return self.get(cache_key, ttl)

def set_interface_data(self, interface_name: str, params: Dict[str, Any], data: List[Dict], ttl: Optional[int] = None) -> bool:
    """
    设置接口数据缓存

    Args:
        interface_name: 接口名称
        params: 请求参数
        data: 要缓存的数据
        ttl: 缓存时间（秒）

    Returns:
        是否设置成功
    """
    if ttl is None:
        ttl = 604800  # 默认7天

    cache_key = self._generate_interface_cache_key(interface_name, params)
    return self.set(cache_key, data, ttl)

def _generate_interface_cache_key(self, interface_name: str, params: Dict[str, Any]) -> str:
    """
    生成接口数据缓存键

    Args:
        interface_name: 接口名称
        params: 请求参数

    Returns:
        缓存键字符串
    """
    # 提取关键参数用于生成缓存键
    key_params = {}

    # 对于 pro_bar，使用这些参数
    if interface_name == 'pro_bar':
        key_params = {
            'ts_code': params.get('ts_code', ''),
            'start_date': params.get('start_date', ''),
            'end_date': params.get('end_date', ''),
            'adj': params.get('adj', 'qfq'),
            'freq': params.get('freq', 'D'),
        }
    else:
        # 其他接口使用所有参数
        key_params = params.copy()

    # 生成缓存键
    param_str = '_'.join([f"{k}:{v}" for k, v in sorted(key_params.items())])
    cache_key = f"{interface_name}_{param_str}"

    return cache_key
```

**文件**：`app4/core/downloader.py`

修改 `_make_request` 方法，增加缓存检查：

```python
def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict]:
    """
    执行API请求（支持缓存）

    Args:
        interface_config: 接口配置
        params: 请求参数

    Returns:
        返回的数据
    """
    api_name = interface_config.get('api_name')

    # 尝试从缓存获取
    cache_key = self.cache_manager._generate_interface_cache_key(api_name, params)
    cached_data = self.cache_manager.get_interface_data(api_name, params)

    if cached_data is not None:
        logger.info(f"Cache hit for {api_name} with params: {params}")
        return cached_data

    # 缓存未命中，从API获取
    # ... 原有的 API 请求逻辑 ...

    # 请求成功后，写入缓存
    if data and len(data) > 0:
        self.cache_manager.set_interface_data(api_name, params, data)
        logger.info(f"Cache set for {api_name}, {len(data)} records")

    return data
```

#### 2. 实现异步下载

##### 并发策略

**方案A：股票级别并发**（推荐）

```
主线程：
├── 获取股票列表（5470只）
├── 将股票分为批次（每批 8 只）
└── for batch in batches:
    └── 提交批量任务到线程池（并发下载）
        ├── 股票1：交易日历 + API请求
        ├── 股票2：交易日历 + API请求
        ├── ...
        └── 股票8：交易日历 + API请求
```

**优点**：
- 实现简单
- 并发度高（8只股票同时下载）
- 缓存机制自动生效（如果某个股票已缓存，会自动跳过）

**缺点**：
- 需要处理线程安全（缓存写入）
- API 速率限制需要考虑

##### 实现修改

**文件**：`app4/main.py`

修改下载逻辑：

```python
# 原有代码（同步串行）
# for interface_name in interfaces_to_run:
#     data = downloader.download(interface_name, params)
#     storage_manager.save_data(interface_name, data)

# 新代码（异步并发）
for interface_name in interfaces_to_run:
    interface_config = config_loader.get_interface_config(interface_name)

    # 获取下载参数
    params = {...}

    # 检查是否是股票循环分页
    pagination_type = interface_config.get('pagination', {}).get('type', 'date_range')

    if pagination_type == 'stock_loop':
        # 股票循环分页：异步并发下载
        logger.info(f"Starting concurrent download for {interface_name}...")

        # 获取股票列表
        stock_list = downloader.cache_manager.get_stock_list()
        if not stock_list:
            stock_list = downloader._fetch_stock_list()

        # 分批处理（每批 max_workers 只股票）
        max_workers = config_loader.global_config.get('concurrency', {}).get('max_workers', 8)
        batch_size = max_workers

        total_batches = (len(stock_list) + batch_size - 1) // batch_size
        logger.info(f"Processing {len(stock_list)} stocks in {total_batches} batches (batch_size={batch_size})")

        all_data = []

        for batch_idx in range(total_batches):
            # 计算当前批次
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(stock_list))
            batch_stocks = stock_list[start_idx:end_idx]

            logger.info(f"Processing batch {batch_idx + 1}/{total_batches} (stocks {start_idx + 1}-{end_idx})")

            # 准备任务列表
            tasks = []
            for stock in batch_stocks:
                stock_params = params.copy()
                stock_params['ts_code'] = stock['ts_code']
                # 设置日期范围...

                task = {
                    'func': downloader.download_single_stock,
                    'args': (interface_config, stock_params),
                    'kwargs': {}
                }
                tasks.append(task)

            # 批量提交任务到线程池
            results = scheduler.submit_tasks(tasks)

            # 合并结果
            for result in results:
                if result:
                    all_data.extend(result)

            # 批次进度
            logger.info(f"Batch {batch_idx + 1}/{total_batches} completed. Total records: {len(all_data)}")

        # 保存所有数据
        if all_data:
            storage_manager.save_data(interface_name, all_data, async_write=True)
            logger.info(f"Saved total {len(all_data)} records for {interface_name}")

    else:
        # 日期范围分页：保持原有逻辑
        data = downloader.download(interface_name, params)
        if data:
            storage_manager.save_data(interface_name, data, async_write=True)
```

**文件**：`app4/core/downloader.py`

新增方法：

```python
def download_single_stock(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict]:
    """
    下载单只股票的数据（用于并发下载）

    Args:
        interface_config: 接口配置
        params: 请求参数（必须包含 ts_code）

    Returns:
        返回的数据
    """
    api_name = interface_config.get('api_name')
    ts_code = params.get('ts_code')

    # 尝试从缓存获取
    cached_data = self.cache_manager.get_interface_data(api_name, params)
    if cached_data is not None:
        logger.debug(f"Cache hit for {api_name} {ts_code}")
        return cached_data

    # 缓存未命中，执行下载
    logger.info(f"Downloading {api_name} for {ts_code}")

    # 执行日期范围分页下载
    data = self._execute_date_range_pagination(interface_config, params)

    # 写入缓存
    if data and len(data) > 0:
        self.cache_manager.set_interface_data(api_name, params, data)
        logger.debug(f"Cache set for {api_name} {ts_code}, {len(data)} records")

    return data
```

##### 速率限制

由于并发下载会增加 API 调用频率，需要调整速率限制器：

**文件**：`app4/core/scheduler.py`

```python
class RateLimiter:
    """速率限制器 - 令牌桶算法"""

    def __init__(self, rate_limit: int, time_window: int = 60):
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.tokens = rate_limit
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌（线程安全）

        Args:
            tokens: 需要的令牌数

        Returns:
            是否获取成功
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            refill_tokens = int(elapsed * self.rate_limit / self.time_window)

            if refill_tokens > 0:
                self.tokens = min(self.rate_limit, self.tokens + refill_tokens)
                self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_for_tokens(self, tokens: int = 1):
        """等待直到有足够的令牌"""
        while not self.acquire(tokens):
            sleep_time = self.time_window / self.rate_limit
            time.sleep(sleep_time)
```

**使用示例**：

```python
# 在下载前获取令牌
rate_limit = interface_config.get('permissions', {}).get('rate_limit', 60)
rate_limiter = RateLimiter(rate_limit)
rate_limiter.wait_for_tokens(1)
```

##### 线程安全

**缓存写入**：
- CacheManager 的 `set()` 方法需要加锁
- 或者使用文件锁确保并发写入安全

**建议**：
- Parquet 文件写入时使用临时文件 + 原子重命名
- 或者使用 SQLite 数据库作为缓存后端

---

## 实施步骤

### 阶段1：激活缓存

1. **扩展 CacheManager**
   - 添加 `get_interface_data()` 方法
   - 添加 `set_interface_data()` 方法
   - 添加 `_generate_interface_cache_key()` 方法

2. **修改 Downloader**
   - 在 `_make_request()` 中添加缓存检查
   - 在 `_execute_date_range_pagination()` 中添加缓存检查
   - 在 `_execute_stock_loop_pagination()` 中添加缓存检查

3. **测试缓存**
   - 运行一次程序，下载 pro_bar 数据
   - 清空 data 目录，保留 cache 目录
   - 再次运行，验证从缓存读取数据

### 阶段2：实现异步下载

1. **扩展 Downloader**
   - 添加 `download_single_stock()` 方法
   - 提取 `_execute_date_range_pagination()` 逻辑

2. **修改 main.py**
   - 识别股票循环分页接口
   - 分批提交任务到 scheduler
   - 等待所有任务完成

3. **调整速率限制**
   - 根据并发数调整 rate_limit
   - 测试 API 限流情况

4. **测试并发下载**
   - 运行程序，观察并发效果
   - 检查日志中的并发信息
   - 验证下载时间是否缩短

### 阶段3：优化和测试

1. **性能测试**
   - 对比优化前后的下载时间
   - 测试缓存命中率
   - 测试并发稳定性

2. **错误处理**
   - 添加重试机制
   - 处理 API 错误
   - 处理缓存读写错误

3. **文档更新**
   - 更新用户文档
   - 更新配置说明

---

## 预期效果

### 性能提升

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 首次下载 5470 只股票 | 51 小时 | 6.4 小时 | **8倍** |
| 二次运行（缓存命中） | 51 小时 | 几分钟 | **600倍** |
| 部分数据已缓存 | 51 小时 | 1-3 小时 | **17-50倍** |

### 资源优化

- **API 调用次数**：大幅减少（缓存命中时）
- **网络带宽**：显著降低
- **存储空间**：增加（缓存数据占用磁盘空间）

### 用户体验

- **运行时间**：从几十小时缩短到几小时
- **重复运行**：几乎瞬间完成（缓存命中）
- **可靠性**：提高（减少长时间运行的中断风险）

---

## 风险和注意事项

### 1. API 限流

**风险**：
- 并发下载可能触发 API 限流
- 高并发可能导致 IP 被封禁

**缓解措施**：
- 控制并发数（建议 4-8）
- 设置合理的速率限制
- 添加请求间隔时间

### 2. 缓存一致性

**风险**：
- 缓存数据可能与实时数据不一致
- 历史数据可能被修正

**缓解措施**：
- 设置合理的 TTL（7天）
- 提供手动清空缓存的命令
- 提供 `--force-refresh` 参数强制刷新

### 3. 磁盘空间

**风险**：
- 缓存数据占用大量磁盘空间
- 5470 只股票 × 8000 条记录 × 100 字节 ≈ 4.4 GB

**缓解措施**：
- 定期清理过期缓存
- 提供 `--clean-cache` 命令
- 使用压缩格式（Parquet 已经是压缩格式）

### 4. 线程安全

**风险**：
- 多线程并发写入缓存可能导致数据损坏
- Parquet 文件并发写入可能失败

**缓解措施**：
- 使用文件锁
- 使用临时文件 + 原子重命名
- 或者改用 SQLite 作为缓存后端

---

## 配置调整建议

### 全局配置

```yaml
# app4/config/global_config.yaml

cache:
  base_dir: "../cache"
  default_ttl: 86400  # 默认 24 小时
  interface_data_ttl: 604800  # 接口数据缓存 7 天

concurrency:
  max_workers: 8  # 并发数
  max_queue_size: 1000

storage:
  base_dir: "../data"
  format: "parquet"
  batch_size: 100
```

### 接口配置

```yaml
# app4/config/interfaces/pro_bar.yaml

api_name: "pro_bar"
pagination:
  type: "stock_loop"  # 股票循环分页
  window_size: 6000  # 时间窗口大小（天）

permissions:
  rate_limit: 60  # 每分钟 60 次请求
  min_points: 0
```

---

## 测试计划

### 单元测试

1. **缓存测试**
   - 测试 `get_interface_data()` 方法
   - 测试 `set_interface_data()` 方法
   - 测试缓存过期逻辑
   - 测试缓存键生成

2. **下载测试**
   - 测试 `download_single_stock()` 方法
   - 测试并发下载逻辑
   - 测试错误处理

### 集成测试

1. **端到端测试**
   - 测试完整的下载流程
   - 测试缓存命中场景
   - 测试并发下载场景

2. **性能测试**
   - 测试下载时间
   - 测试缓存命中率
   - 测试并发效率

### 回归测试

1. **功能测试**
   - 确保所有现有功能正常工作
   - 确保数据格式不变
   - 确保存储格式不变

2. **兼容性测试**
   - 测试不同的接口
   - 测试不同的参数组合
   - 测试不同的操作系统

---

## 总结

本优化方案通过以下措施大幅提升 aspipe_v4 的性能：

1. **激活业务数据缓存**：避免重复下载，减少 API 调用
2. **实现异步下载**：利用 ThreadPoolExecutor 并发下载多只股票
3. **保持异步存储**：继续使用后台线程异步写入数据

**预期收益**：
- 首次下载：8倍性能提升（51 小时 → 6.4 小时）
- 重复运行：600倍性能提升（51 小时 → 几分钟）

**实施难度**：中等
- 缓存扩展：简单（约 50 行代码）
- 异步下载：中等（约 100 行代码）
- 测试验证：需要充分测试

**风险可控**：通过合理的配置和错误处理，风险可以降到最低。
