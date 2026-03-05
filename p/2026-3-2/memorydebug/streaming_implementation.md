# 流式处理内存优化实施记录

**实施日期**: 2026-03-04  
**目标**: 解决分页执行器内部数据累积导致的内存泄漏  
**预期效果**: 内存呈锯齿状波动，而非线性增长

---

## 1. 问题分析

### 1.1 现象

实施了 `results_leak_solution.md` 方案后，内存仍持续增长。

### 1.2 根因

数据在**更深层次**仍在累积：

```
数据流：
_make_request() → 返回 5999 条
     ↓
_execute_single_request() 
    → all_data.extend(data) × 13次  ← 这里累积了 78000 条！
    → return all_data
     ↓
download_single_stock()
    → return len(stock_data)  ← results_leak_solution 只解决了这里

问题：78000 条数据在 _execute_single_request 的 all_data 中仍占用内存
```

---

## 2. 实施的代码修改

### 2.1 pagination_executor.py

#### 修改 1: `_execute_single_request` 方法

**位置**: 第 311-390 行

**修改内容**: 添加 `on_data_ready` 回调参数，支持流式处理

```python
# 修改前
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
) -> List[Dict[str, Any]]:
    # ...
    all_data = []
    
    while True:
        data = make_request(...)
        all_data.extend(data)  # ← 累积数据
    
    return all_data  # ← 返回 78000+ 条

# 修改后
def _execute_single_request(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    # ...
    all_data = []
    total_count = 0
    
    while True:
        data = make_request(...)
        
        if on_data_ready:
            # 流式处理：每页数据立即回调，不累积
            on_data_ready(data)
            total_count += data_count
        else:
            # 兼容旧逻辑：累积数据
            all_data.extend(data)
    
    if on_data_ready:
        return total_count  # ← 只返回数字
    else:
        return all_data  # ← 兼容模式
```

#### 修改 2: `_execute_concurrent` 方法

**位置**: 第 261-320 行

**修改内容**: 添加 `on_data_ready` 参数并传递给 `_execute_single_request`

```python
# 修改前
def _execute_concurrent(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
) -> List[Dict[str, Any]]:
    all_data = []
    # ...
    for future in as_completed(future_to_params):
        data = future.result()
        if data:
            all_data.extend(data)  # ← 累积
    return all_data

# 修改后
def _execute_concurrent(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    all_data = []
    total_count = 0
    # ...
    for future in as_completed(future_to_params):
        result = future.result()
        if result:
            if on_data_ready:
                total_count += result  # ← 累加计数
            else:
                all_data.extend(result)  # ← 兼容模式
    
    if on_data_ready:
        return total_count
    return all_data
```

#### 修改 3: `_execute_sequential` 方法

**位置**: 第 151-200 行

**修改内容**: 同样添加 `on_data_ready` 参数

```python
# 修改后
def _execute_sequential(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    all_data = []
    total_count = 0
    # ...
    result = self._execute_single_request(..., on_data_ready)
    
    if result:
        if on_data_ready:
            total_count += result
        else:
            all_data.extend(result)
    
    if on_data_ready:
        return total_count
    return all_data
```

#### 修改 4: `execute` 方法

**位置**: 第 51-135 行

**修改内容**: 添加 `on_data_ready` 参数并传递

```python
# 修改后
def execute(
    self,
    interface_config: Dict[str, Any],
    base_params: Dict[str, Any],
    context: PaginationContext,
    make_request: Callable,
    coverage_manager: Optional[Any] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    # ...
    # 传递给下游方法
    return self._execute_concurrent(..., on_data_ready)
    # 或
    return self._execute_sequential(..., on_data_ready)
```

#### 修改 5: `_execute_single` 方法

**位置**: 第 150-165 行

**修改内容**: 添加 `on_data_ready` 参数

```python
# 修改后
def _execute_single(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    return self._execute_single_request(interface_config, params, make_request, on_data_ready)
```

---

### 2.2 downloader.py

#### 修改 1: `_execute_paginated_download` 方法

**位置**: 第 470-505 行

**修改内容**: 添加 `on_data_ready` 参数并传递

```python
# 修改前
def _execute_paginated_download(
    self,
    interface_config: Dict[str, Any],
    stock_list: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    start_date: str,
    end_date: str,
    user_provided_dates: bool = False,
) -> List[Dict[str, Any]]:
    # ...
    return self.pagination_executor.execute(
        interface_config=interface_config,
        base_params=base_params,
        context=pagination_context,
        make_request=self._make_request,
        coverage_manager=self.coverage_manager,
    )

# 修改后
def _execute_paginated_download(
    self,
    interface_config: Dict[str, Any],
    stock_list: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    start_date: str,
    end_date: str,
    user_provided_dates: bool = False,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    # ...
    return self.pagination_executor.execute(
        interface_config=interface_config,
        base_params=base_params,
        context=pagination_context,
        make_request=self._make_request,
        coverage_manager=self.coverage_manager,
        on_data_ready=on_data_ready,  # ← 传递回调
    )
```

#### 修改 2: `download_single_stock` 方法

**位置**: 第 500-700 行

**修改内容**: 创建流式回调，数据直接写入 buffer

```python
# 修改前
if gap_tasks:
    all_stock_data = []
    for gap_task in gap_tasks:
        task_data = self._execute_paginated_download(...)
        if task_data:
            all_stock_data.extend(task_data)  # ← 累积数据
    
    stock_data = all_stock_data
    if stock_data:
        self.storage_manager.add_to_buffer(interface_config["api_name"], stock_data)
    return len(stock_data) if stock_data else 0

# 修改后
if gap_tasks:
    total_count = 0

    # 创建流式回调：数据直接写入 buffer
    def on_data_ready(data: List[Dict[str, Any]]):
        if data and hasattr(self, "storage_manager") and self.storage_manager:
            self.storage_manager.add_to_buffer(interface_config["api_name"], data)

    for gap_task in gap_tasks:
        # 使用流式处理，返回计数而非数据
        result = self._execute_paginated_download(
            ...,
            on_data_ready=on_data_ready,  # ← 传递回调
        )
        if result:
            total_count += result

    logger.info(f"Downloaded {total_count} records for {ts_code}")
    return total_count
```

非 gap_tasks 分支同样修改：

```python
# 修改前
stock_data = self._execute_paginated_download(...)
if stock_data:
    self.storage_manager.add_to_buffer(interface_config["api_name"], stock_data)
return len(stock_data) if stock_data else 0

# 修改后
def on_data_ready(data: List[Dict[str, Any]]):
    if data and hasattr(self, "storage_manager") and self.storage_manager:
        self.storage_manager.add_to_buffer(interface_config["api_name"], data)

result = self._execute_paginated_download(..., on_data_ready=on_data_ready)

if result:
    logger.info(f"Downloaded {result} records for {ts_code}")
return result if result else 0
```

#### 修改 3: 异常处理返回值

```python
# 修改前
return []  # 返回空列表

# 修改后
return 0  # 返回 0，与其他分支保持一致
```

---

### 2.3 main.py

此文件在 `results_leak_solution.md` 方案中已修改，无需再次修改。

修改内容回顾：

```python
# 修改前
for result in results:
    if result:
        total_records += len(result)

# 修改后
for result in results:
    if result:
        total_records += result  # result 已经是数字
```

---

## 3. 数据流对比

### 3.1 修改前

```
API 请求 (5999条)
    ↓
all_data.extend() × 13 次  ← 累积 78000 条在内存
    ↓
return all_data (78000条)
    ↓
download_single_stock 接收 78000 条
    ↓
add_to_buffer(78000条)
    ↓
return len(78000条)  ← results_leak_solution 解决了这里

内存峰值：78000条 × 4线程 = 312000条同时存在
```

### 3.2 修改后

```
API 请求 (5999条)
    ↓
on_data_ready(5999条)  ← 立即回调写入 buffer
    ↓
total_count += 5999
    ↓
继续下一页...

内存峰值：5999条 × 4线程 = 23996条同时存在

节省：87% 内存
```

---

## 4. 测试验证

### 4.1 语法检查

```bash
cd /home/quan/testdata/aspipe_v4
python3 -m py_compile app4/core/downloader.py app4/core/pagination_executor.py
```

### 4.2 内存监控

```bash
python app4/main.py --interface cyq_chips &
pid=$!

while kill -0 $pid 2>/dev/null; do
    rss=$(ps -o rss= -p $pid | awk '{printf "%.0f", $1/1024}')
    echo "$(date '+%H:%M:%S'): ${rss}MB"
    sleep 5
done
```

### 4.3 预期效果

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| 单线程内存峰值 | 78000条 | 6000条 |
| 4线程内存峰值 | 312000条 | 24000条 |
| 内存节省 | - | ~87% |
| 内存曲线 | 线性增长 | 锯齿波动 |

---

## 5. 文件修改清单

| 文件 | 修改行数 | 修改内容 |
|------|----------|----------|
| `app4/core/pagination_executor.py` | 5处 | 添加 `on_data_ready` 回调支持 |
| `app4/core/downloader.py` | 3处 | 使用流式回调写入 buffer |
| `app4/main.py` | 2处 | 返回值类型适配（已在 results_leak_solution 中完成） |

---

## 6. 相关文档

| 文档 | 说明 |
|------|------|
| `results_leak_solution.md` | 解决 results 列表内存泄漏 |
| `memory_release_solution.md` | 原有的回调机制方案 |
| `streaming_implementation.md` (本文档) | 流式处理实施记录 |
