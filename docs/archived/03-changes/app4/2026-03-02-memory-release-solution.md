---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-02
updated: 2026-03-02
summary: 内存释放优化方案
---

# 内存释放优化方案

## 问题总结

当前系统在下载大数据量接口时内存占用过高。核心问题是 **调用链上的 `all_data` 变量持续累积数据**，导致内存无法释放。

### 各种分页模式的数据单元

| 模式 | 数据单元 | 累积位置 |
|------|---------|---------|
| `stock_loop` | 单只股票 | `_execute_single_request.all_data` |
| `period_range` | 单个报告期 | `_execute_sequential.all_data` |
| `reverse_date_range` + `is_date_anchor` | 单个日期 | `_execute_sequential.all_data` |
| `reverse_date_range` + time_window | 时间窗口 | `_execute_sequential.all_data` |
| `offset` | 全量数据 | `_execute_single_request.all_data` |

### 问题代码位置

所有模式最终都会经过以下累积点：

1. **`_execute_single_request.all_data`**（第278行）- 累积单个请求单元内的 offset 分页数据
2. **`_execute_sequential.all_data`**（第172行）- 累积所有顺序请求的数据
3. **`_execute_concurrent.all_data`**（第278行）- 累积所有并发请求的数据

---

## 解决方案

### 核心思路

**在每个请求单元完成后，立即保存数据并清除引用，不让数据向上层传递。**

### 修改点1：`pagination_executor.py` - 添加数据完成回调

**位置**：`_execute_single_request` 方法

**修改**：

```python
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    执行单个请求，处理offset分页
    
    Args:
        on_data_ready: 数据准备好的回调函数
                       - 如果提供，数据通过回调传递，返回空列表
                       - 如果不提供，返回数据列表（兼容旧逻辑）
    """
    offset_config = params.get("_offset_pagination", {})

    if not offset_config.get("enabled"):
        # 无 offset 分页，直接请求
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}
        data = make_request(interface_config, clean_params)
        if on_data_ready and data:
            on_data_ready(data)
            return []
        return data

    # offset 分页逻辑
    all_data = []
    limit = offset_config["limit"]
    offset = 0
    base_params = {k: v for k, v in params.items() if not k.startswith("_")}
    interface_name = interface_config.get("name", "unknown")

    logger.info(f"[{interface_name}] Offset分页开始 - 配置限额: limit={limit}")
    page_num = 0

    while True:
        request_params = base_params.copy()
        request_params["limit"] = limit
        request_params["offset"] = offset

        data = make_request(interface_config, request_params)
        if not data:
            break

        all_data.extend(data)
        page_num += 1
        data_count = len(data)
        logger.info(f"[{interface_name}] 第{page_num}页完成 - offset={offset}, 返回={data_count}条")

        if data_count < limit:
            break

        offset += limit
        if offset > limit * 10000:
            break

    logger.info(f"[{interface_name}] Offset分页结束 - 总页数={page_num}, 总记录数={len(all_data)}")

    # 【关键】通过回调传递数据，不累积返回
    if on_data_ready and all_data:
        on_data_ready(all_data)
        return []
    
    return all_data
```

### 修改点2：`pagination_executor.py` - 顺序执行使用回调

**位置**：`_execute_sequential` 方法

**修改**：

```python
def _execute_sequential(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    顺序执行多个请求
    
    Args:
        on_data_ready: 数据准备好的回调，每个请求完成后立即调用
    """
    all_data = []
    consecutive_empty = 0
    stop_on_empty = self._get_stop_on_empty_config(interface_config)

    for idx, params in enumerate(params_list):
        if progress_callback:
            progress_callback(idx + 1, len(params_list))

        if coverage_manager and self._should_skip_by_coverage(interface_config, params, coverage_manager):
            continue

        # 【关键】传入回调，每个请求完成后立即处理数据
        data = self._execute_single_request(
            interface_config, params, make_request, on_data_ready
        )

        if data:
            # 兼容旧逻辑：无回调时累积
            all_data.extend(data)
            consecutive_empty = 0
        else:
            consecutive_empty += self._estimate_empty_days(params)
            if stop_on_empty > 0 and consecutive_empty >= stop_on_empty:
                logger.info(f"Stopping after {consecutive_empty} consecutive empty days")
                break

    return all_data
```

### 修改点3：`pagination_executor.py` - 并发执行使用回调

**位置**：`_execute_concurrent` 方法

**修改**：

```python
def _execute_concurrent(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    并发执行多个请求
    
    Args:
        on_data_ready: 数据准备好的回调，每个请求完成后立即调用
    """
    all_data = []
    max_workers = self._get_max_workers(interface_config)

    filtered_params = [
        p for p in params_list
        if not (coverage_manager and self._should_skip_by_coverage(interface_config, p, coverage_manager))
    ]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 【关键】每个任务传入回调
        future_to_params = {
            executor.submit(
                self._execute_single_request, 
                interface_config, p, make_request, on_data_ready
            ): p
            for p in filtered_params
        }

        completed = 0
        for future in as_completed(future_to_params):
            completed += 1
            if progress_callback:
                progress_callback(completed, len(filtered_params))
            try:
                data = future.result()
                if data:
                    # 兼容旧逻辑：无回调时累积
                    all_data.extend(data)
            except Exception as e:
                logger.error(f"Task failed: {e}")

    return all_data
```

### 修改点4：`pagination_executor.py` - execute 方法传递回调

**位置**：`execute` 方法

**修改**：

```python
def execute(
    self,
    interface_config: Dict[str, Any],
    base_params: Dict[str, Any],
    context: PaginationContext,
    make_request: Callable,
    coverage_manager: Optional[Any] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    on_data_ready: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    执行分页请求（统一入口）
    
    Args:
        on_data_ready: 数据准备好的回调 (interface_name, data) -> None
                       提供此参数时，每个请求单元完成后立即调用，不累积返回
    """
    composer = PaginationComposer(context)
    params_list = list(composer.compose(base_params))

    # 检测 period_range 模式且 periods_per_batch=1，使用逐个保存模式
    periods_per_batch = None
    if params_list:
        periods_per_batch = params_list[0].get("_periods_per_batch")
        if periods_per_batch is not None:
            periods_per_batch = int(periods_per_batch)

    if periods_per_batch == 1 and on_data_ready:
        return self._execute_period_range_sequential(
            interface_config, params_list, make_request,
            coverage_manager, progress_callback, on_data_ready
        )

    if len(params_list) <= 1:
        if params_list:
            if coverage_manager and self._should_skip_by_coverage(
                interface_config, params_list[0], coverage_manager
            ):
                logger.info(f"Skipping request due to coverage check")
                return []
            
            # 包装回调，添加 interface_name
            def single_callback(data):
                if on_data_ready:
                    interface_name = interface_config.get("name", "unknown")
                    on_data_ready(interface_name, data)
            
            return self._execute_single(
                interface_config, params_list[0], make_request, single_callback
            )
        return []

    # 包装回调
    def wrapped_callback(data):
        if on_data_ready:
            interface_name = interface_config.get("name", "unknown")
            on_data_ready(interface_name, data)

    stop_on_empty = self._get_stop_on_empty_config(context.interface_config)
    if self._should_use_concurrency(interface_config):
        return self._execute_concurrent(
            interface_config, params_list, make_request,
            coverage_manager, progress_callback, wrapped_callback
        )
    else:
        return self._execute_sequential(
            interface_config, params_list, make_request,
            coverage_manager, progress_callback, wrapped_callback
        )
```

### 修改点5：`downloader.py` - download 方法支持回调

**位置**：`download` 方法

```python
def download(
    self,
    interface_name: str,
    params: Optional[Dict[str, Any]] = None,
    on_data_ready: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    下载数据
    
    Args:
        on_data_ready: 数据准备好的回调，用于流式处理
    """
    # ... 现有验证逻辑 ...
    
    result = self.executor.execute(
        interface_config=interface_config,
        base_params=validated_params,
        context=context,
        make_request=self._make_request,
        coverage_manager=self.coverage_manager,
        on_data_ready=on_data_ready,
    )
    
    return result
```

### 修改点6：`main.py` - 调用时提供回调

**位置**：下载数据的地方

```python
def create_data_ready_callback(storage_manager):
    """创建数据准备好的回调：立即保存并释放内存"""
    def on_data_ready(interface_name: str, data: List[Dict[str, Any]]):
        if data:
            # 保存数据
            storage_manager.save_data(interface_name, data, async_write=True)
            # 显式释放引用
            del data
    return on_data_ready

# 下载时传入回调
callback = create_data_ready_callback(storage_manager)
data = components.downloader.download(
    interface_name,
    result.params,
    on_data_ready=callback
)
# data 为空（已通过回调保存），内存已释放
```

---

## 各模式的内存释放时序

### stock_loop 模式（如 cyq_chips）

```
每只股票:
  API请求（多页 offset）→ all_data 累积
  → on_data_ready(all_data) 回调
      → save_data() 保存
      → del all_data
  → return [] → GC 回收
下一只股票...
```

### period_range 模式（如 income_vip）

```
每个报告期:
  API请求 → data
  → on_data_ready(data) 回调
      → save_data() 保存
      → del data
  → return [] → GC 回收
下一个报告期...
```

### reverse_date_range + is_date_anchor 模式（如 cyq_perf）

```
每个日期:
  API请求 → data
  → on_data_ready(data) 回调
      → save_data() 保存
      → del data
  → return [] → GC 回收
下一个日期...
```

---

## 调试验证指南

代码修改完成后，使用以下工具验证内存释放效果。

### 工具文件

```
p/2026-3-2/memorydebug/
├── memory_inspector.py      # 内存探查模块
└── memory_debug_main.py     # 带内存调试的 main.py
```

### 使用方法

#### 方法一：快速验证（推荐）

```bash
# 进入 app4 目录
cd /home/quan/testdata/aspipe_v4/app4

# 复制调试工具到 app4 目录
cp ../p/2026-3-2/memorydebug/memory_inspector.py .
cp ../p/2026-3-2/memorydebug/memory_debug_main.py .

# 启用内存调试模式运行
python memory_debug_main.py --interface cyq_chips --memory-debug

# 启用详细内存追踪（使用 tracemalloc）
python memory_debug_main.py --interface cyq_chips --memory-debug --memory-trace

# 调整内存检查间隔（默认5秒）
python memory_debug_main.py --interface cyq_chips --memory-debug --memory-interval 2.0
```

#### 支持的参数

| 参数 | 说明 |
|------|------|
| `--memory-debug` | 启用内存调试模式 |
| `--memory-trace` | 启用 tracemalloc 详细追踪（显示内存分配位置） |
| `--memory-interval` | 设置内存检查间隔（秒），默认 5.0 |

所有 `main.py` 原有的参数也都支持。

#### 方法二：外部监控

```bash
# 启动下载进程
python app4/main.py --interface cyq_chips &
pid=$!

# 监控内存变化
while kill -0 $pid 2>/dev/null; do
    rss=$(ps -o rss= -p $pid | awk '{printf "%.0f", $1/1024}')
    echo "$(date '+%H:%M:%S'): ${rss}MB"
    sleep 2
done
```

### 输出示例

```
============================================================
[MemoryInspector] 检查点: cyq_chips_batch_1_start
============================================================
总对象数: 1,234,567
总内存占用: 512.34 MB

Top 10 内存占用类型:
  dict: 500,000 个, 256.00 MB
  list: 100,000 个, 128.00 MB
  str: 200,000 个, 64.00 MB

与上一个检查点 'program_start' 对比:
  时间间隔: 5.23s
  对象数变化: +50,000
  内存变化: +128.00 MB

[DataLeakDetector] ✓ 所有数据都已正确释放
============================================================
```

### 预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 内存曲线 | 线性增长到 20GB+ | 锯齿状波动 |
| 每个请求单元后 | 内存不变或继续增长 | 内存下降 |
| 峰值内存 | 20GB+ | 2-4GB |
| DataLeakDetector | ⚠ 发现未释放数据 | ✓ 所有数据正确释放 |

### 如何解读报告

#### 健康状态

```
[DataLeakDetector] ✓ 所有数据都已正确释放
```

表示所有被跟踪的数据对象都已被垃圾回收，内存释放机制生效。

#### 异常状态

```
[DataLeakDetector] ⚠ 发现未释放的数据:
  - downloaded_data: id=140234567890, 原始大小=10000, 存活时间=30.5s
```

表示有数据对象在保存后仍然存在于内存中，说明：
1. 回调机制可能未正确实施
2. 数据仍被其他变量引用
3. 需要检查修改是否完整

### 常见问题排查

#### 问题 1：数据保存后内存没有下降

**可能原因：**
- 回调机制未正确传递
- 数据被缓存或队列引用

**排查方法：**
```python
# 确认回调被正确传入
data = downloader.download(interface_name, params, on_data_ready=callback)
```

#### 问题 2：list/dict 数量持续增长

**可能原因：**
- 并发执行时多个任务同时累积
- 缓冲区未及时处理

**排查方法：**
查看报告中 "增长最多的类型"，定位具体问题。

### 性能影响

| 模式 | 性能损失 |
|------|---------|
| `--memory-debug` | 约 5-10% |
| `--memory-trace` | 约 20-30% |

建议仅在调试时使用，生产环境关闭。

### 内存报告文件

运行后自动生成：

- `log/memory_report_{interface_name}_{timestamp}.txt` - 单个接口报告
- `log/memory_final_report_{timestamp}.txt` - 完整运行报告

---

## 实施检查清单

- [ ] 修改 `pagination_executor.py` 的 `_execute_single_request` 方法
- [ ] 修改 `pagination_executor.py` 的 `_execute_sequential` 方法
- [ ] 修改 `pagination_executor.py` 的 `_execute_concurrent` 方法
- [ ] 修改 `pagination_executor.py` 的 `execute` 方法
- [ ] 修改 `downloader.py` 的 `download` 方法
- [ ] 修改 `main.py` 调用处使用回调
- [ ] 运行 `memory_debug_main.py --interface cyq_chips --memory-debug` 验证
- [ ] 确认内存呈锯齿状波动而非线性增长
- [ ] 确认 DataLeakDetector 显示 "✓ 所有数据都已正确释放"