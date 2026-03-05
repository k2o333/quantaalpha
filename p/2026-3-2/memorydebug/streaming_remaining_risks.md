# 流式处理方案 - 遗留风险与修复方案

**创建日期**: 2026-03-04  
**前置方案**: `results_leak_solution.md` + `streaming_implementation.md`  
**状态**: 待修复

---

## 风险 1: `_execute_period_range_sequential` 未接入流式处理

### 严重程度: P2 (确定性问题)

### 具体表现

财务数据接口（income_vip、balance_vip、cashflow_vip 等）使用 `period_range` 模式时，走 `_execute_period_range_sequential` 路径。这个路径**完全没有使用 `on_data_ready` 回调**，数据仍然在内部累积。

### 触发条件

当接口配置中 `periods_per_batch == 1` 且存在 `save_callback` 时触发：

```
execute()  (pagination_executor.py:93)
  ↓ periods_per_batch == 1 and save_callback
  ↓
_execute_period_range_sequential()  ← 走这个分支
  ↓ 不走 _execute_concurrent / _execute_sequential
```

### 对应代码

**文件**: `app4/core/pagination_executor.py` 第 218-272 行

```python
def _execute_period_range_sequential(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    save_callback: Callable,
    # ← 没有 on_data_ready 参数！
) -> List[Dict[str, Any]]:
    all_data = []  # ← 全量累积

    for idx, params in enumerate(params_list):
        # ...
        data = self._execute_single_request(
            interface_config, params, make_request
            # ← 没有传 on_data_ready！
        )

        if data:
            all_data.extend(data)           # ← 累积到 all_data
            save_callback(interface_name, data)  # ← save_callback 也保存了一份
```

**问题**: `all_data` 持有全部数据引用，且 `save_callback` 也保存了一份 → 数据双份存在。

### 解决方案

```python
def _execute_period_range_sequential(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    save_callback: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,  # 新增
) -> List[Dict[str, Any]]:
    all_data = []
    total_count = 0
    interface_name = interface_config.get("name", "unknown")

    for idx, params in enumerate(params_list):
        if progress_callback:
            progress_callback(idx + 1, len(params_list))

        # 覆盖率检查
        if coverage_manager and self._should_skip_by_coverage(
            interface_config, params, coverage_manager
        ):
            period_field = params.get("_period_field", "period")
            period = params.get(period_field, "unknown")
            logger.info(
                f"[{interface_name}] Skipping period {period} - already covered"
            )
            continue

        # 执行请求
        data = self._execute_single_request(
            interface_config, params, make_request, on_data_ready  # ← 传递回调
        )

        if data:
            if on_data_ready:
                # 流式模式：data 是计数
                total_count += data
                period_field = params.get("_period_field", "period")
                period = params.get(period_field, "unknown")
                logger.info(
                    f"[{interface_name}] Streamed {data} records for period {period}"
                )
            else:
                # 兼容模式
                all_data.extend(data)
                # 保留原有的 save_callback 行为
                save_callback(interface_name, data)
                period_field = params.get("_period_field", "period")
                period = params.get(period_field, "unknown")
                logger.info(
                    f"[{interface_name}] Saved {len(data)} records for period {period}"
                )

    if on_data_ready:
        return total_count
    return all_data
```

同时需要修改 `execute` 方法中调用该函数的地方（第 93-101 行），将 `on_data_ready` 传递下去：

```python
# 修改前
if periods_per_batch == 1 and save_callback:
    return self._execute_period_range_sequential(
        interface_config,
        params_list,
        make_request,
        coverage_manager,
        progress_callback,
        save_callback,
    )

# 修改后
if periods_per_batch == 1 and save_callback:
    return self._execute_period_range_sequential(
        interface_config,
        params_list,
        make_request,
        coverage_manager,
        progress_callback,
        save_callback,
        on_data_ready,  # ← 传递
    )
```

---

## 风险 2: buffer 中间层数据生存周期

### 严重程度: P3 (条件性问题)

### 具体表现

流式回调将数据送入 `StorageManager.add_to_buffer()`，buffer 内数据只在满足以下条件之一时才会 flush：

```python
# storage.py 第 500-504 行
should_flush = (
    buffer["count"] >= 5000        # 阈值 (STORAGE_BUFFER_THRESHOLD)
    or flush_immediately
    or buffer["count"] < 100       # 小数据量立即处理
)
```

**盲区**：当 `100 <= buffer["count"] < 5000` 时，数据会在 buffer 中一直等待。

### 当前场景分析

当前大数据量接口（如 cyq_chips）每页返回 5999 条，超过 5000 阈值，`on_data_ready` 每次回调都会触发 flush → **当前场景安全**。

但如果某接口每页返回 200~4000 条，且下载速度较快，4 个线程同时往同一个 interface 的 buffer 写入，可能导致 buffer 在 flush 之前累积较多数据。

### 对应代码

**文件**: `app4/core/storage.py` 第 476-524 行

```python
def add_to_buffer(
    self,
    interface_name: str,
    data: List[Dict[str, Any]],
    flush_immediately: bool = False,
) -> None:
    with self.buffer_lock:
        buffer = self._get_or_create_buffer(interface_name)
        buffer["data"].extend(data)
        buffer["count"] += len(data)

        should_flush = (
            buffer["count"] >= self.buffer_threshold  # 5000
            or flush_immediately
            or buffer["count"] < 100
        )

        if should_flush:
            data_to_process = buffer["data"]
            buffer["data"] = []
            buffer["count"] = 0
    # ...
```

### 解决方案

增加基于时间的定期刷新机制：

```python
def add_to_buffer(
    self,
    interface_name: str,
    data: List[Dict[str, Any]],
    flush_immediately: bool = False,
) -> None:
    data_to_process = None
    interface_to_process = None

    with self.buffer_lock:
        buffer = self._get_or_create_buffer(interface_name)
        buffer["data"].extend(data)
        buffer["count"] += len(data)

        # 计算是否超时（30秒未 flush 则强制刷新）
        time_since_creation = time.time() - buffer["created_at"]
        timed_out = time_since_creation > 30

        should_flush = (
            buffer["count"] >= self.buffer_threshold
            or flush_immediately
            or buffer["count"] < 100
            or timed_out  # ← 新增：超时强制刷新
        )

        if should_flush:
            data_to_process = buffer["data"]
            interface_to_process = interface_name
            buffer["data"] = []
            buffer["count"] = 0
            buffer["created_at"] = time.time()  # ← 重置计时器

    if data_to_process:
        item = {
            "interface": interface_to_process,
            "data": data_to_process,
            "timestamp": time.time(),
        }
        self.process_queue.put(item)
        # ... 其余逻辑不变
```

---

## 风险 3: `_process_worker` 单线程瓶颈导致 queue 堆积

### 严重程度: P3 (性能问题)

### 具体表现

流式处理后的完整数据路径：

```
4个下载线程 
  → on_data_ready(5999条/次)
  → add_to_buffer → flush → process_queue.put()
  
process_queue (无界队列)
  ↓
_process_worker (单线程)
  → process_data() (去重、类型转换、创建DataFrame)
  → validate_data()
  → data_queue.put()
  ↓
_writer_worker (单线程)
  → write_parquet()
```

**瓶颈**: `_process_worker` 是单线程，需要对每批数据执行：
1. `processor.process_data()` - 类型转换、批次内去重
2. `SchemaManager.create_dataframe_safe()` - 创建 DataFrame
3. `processor.validate_data()` - 数据验证

当 4 个下载线程全速运行时，process_queue 的消费速度可能跟不上生产速度，导致 queue 成为新的内存累积点。

### 对应代码

**文件**: `app4/core/storage.py` 第 584-787 行

```python
def _process_worker(self):
    """处理线程：数据去重、验证、放入写入队列"""
    while self.running:
        try:
            task = self.process_queue.get(timeout=1)  # ← 单线程消费
            # ...
            # 耗时操作：
            df = self.processor.process_data(data, interface_config)    # ← CPU密集
            validation_result = self.processor.validate_data(df, ...)   # ← CPU密集
            # ...
```

### process_queue 的定义

**文件**: `app4/core/storage.py` 构造函数

```python
self.process_queue = queue.Queue()  # ← 无界队列，内存无上限
```

### 解决方案

#### 方案 A: 限制 queue 大小 + 反压 (推荐，改动最小)

```python
# 构造函数中修改
self.process_queue = queue.Queue(maxsize=20)  # ← 限制队列大小

# add_to_buffer 中已经使用 process_queue.put() (阻塞模式)
# 当队列满时，put() 会自动阻塞，形成反压
# 下载线程的 on_data_ready 回调会被阻塞，从而限制下载速度
```

这个方案的优势：
- 改动极小（只改一行）
- 自动形成反压，下载速度自动适配处理速度
- process_queue 最多堆积 20 批数据 ≈ 20 × 5999 ≈ 12 万条 ≈ 可控范围

#### 方案 B: 多 process_worker (改动较大)

```python
# 启动 2 个 process worker
def start_writer(self):
    if not self.running:
        self.running = True
        
        self.writer_thread = threading.Thread(
            target=self._writer_worker, daemon=True
        )
        self.writer_thread.start()

        # 启动多个处理线程
        self.process_threads = []
        for i in range(2):  # ← 2个处理线程
            t = threading.Thread(
                target=self._process_worker, daemon=True, name=f"process-worker-{i}"
            )
            t.start()
            self.process_threads.append(t)

        logger.info("Storage writer and process threads started")
```

注意：方案 B 需要确保 `_write_interface_data` 是线程安全的（当前通过文件名中的 uuid 保证了原子性，应该是安全的）。

---

## 实施清单

| 优先级 | 风险 | 修改文件 | 修改内容 | 工作量 |
|--------|------|----------|----------|--------|
| P2 | 风险1 | `pagination_executor.py` | `_execute_period_range_sequential` 添加 `on_data_ready` + `execute` 传递参数 | ~20行 |
| P3 | 风险2 | `storage.py` | `add_to_buffer` 添加超时刷新逻辑 | ~5行 |
| P3 | 风险3 | `storage.py` | `process_queue` 加 `maxsize=20` | 1行 |

---

## 修改影响分析

| 修改 | 兼容性风险 | 回归风险 |
|------|-----------|---------|
| 风险1 修复 | 无（`on_data_ready` 是可选参数，不传时走原逻辑） | 低 |
| 风险2 修复 | 无（只增加了一个刷新条件） | 极低 |
| 风险3 修复 | 有（反压可能导致下载线程阻塞延长） | 低，需观察 |

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `results_leak_solution.md` | 第一层修复：results 列表引用泄漏 |
| `streaming_implementation.md` | 第二层修复：分页累积 → 流式处理 |
| `streaming_remaining_risks.md` (本文档) | 第三层：遗留风险与修复方案 |
