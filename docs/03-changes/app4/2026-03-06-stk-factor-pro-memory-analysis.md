# stk_factor_pro 内存增长问题分析报告

## 问题概述

在执行 `python app4/main.py --update --interface stk_factor_vip --start_date 19900101` 命令时，内存占用从很低逐渐增加到 **16%**（约 12.4GB 内存的 16% ≈ 2GB）。

## 问题表现

1. **内存持续增长**：随着下载进行，内存占用不断增加
2. **不释放**：即使数据已保存到磁盘，内存仍然保持高位
3. **影响范围**：主要影响 `stk_factor_pro` 和类似的大数据量接口

## 根因分析

### 1. 接口特性

`stk_factor_pro` 接口具有以下特点：

- **字段极多**：约 **200+ 个字段**（包含大量技术指标：均线、MACD、KDJ、RSI、布林带等）
- **数据量大**：每个交易日返回全市场 5000+ 只股票的数据
- **时间跨度长**：从 1990-01-01 到 2026-03-07 有约 **9000+ 个交易日**

### 2. 分页配置

```yaml
# app4/config/interfaces/stk_factor_pro.yaml
pagination:
  enabled: true
  mode: reverse_date_range
  window_size_days: 1  # 每天一个请求
```

`window_size_days: 1` 表示每个交易日都会发起一个独立的 API 请求。

### 3. 核心问题代码

#### 问题 1：数据累积在内存中

**文件**: [app4/core/pagination_executor.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py#L199-L230)

```python
def _execute_sequential(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    顺序执行多个请求
    """
    all_data = []  # ← 问题：累积所有数据
    total_count = 0
    consecutive_empty = 0
    stop_on_empty = self._get_stop_on_empty_config(interface_config)
    interface_name = interface_config.get("name", "unknown")

    for idx, params in enumerate(params_list):
        # ...
        result = self._execute_single_request(interface_config, params, make_request, on_data_ready)

        if result:
            if on_data_ready:
                total_count += result
                consecutive_empty = 0
            else:
                # 兼容模式：result 是数据列表
                all_data.extend(result)  # ← 问题：数据不断追加到列表，即使已保存
                # 原子化保存：每次请求的分页完成后立即保存
                if save_callback:
                    save_callback(interface_name, result)
                    logger.info(
                        f"[{interface_name}] 已保存 {len(result)} 条记录 (第{idx+1}/{len(params_list)}批)"
                    )
                consecutive_empty = 0
```

**问题分析**：
- 即使使用了 `save_callback` 逐批保存数据到磁盘
- `all_data.extend(result)` 仍然会把所有数据保留在内存中
- 函数返回时才释放 `all_data`

#### 问题 2：DataFrame 创建开销

**文件**: [app4/core/processor.py](file:///home/quan/testdata/aspipe_v4/app4/core/processor.py#L35-L50)

```python
def process_data(self, data: List[Dict[str, Any]], interface_config: Dict[str, Any]) -> pl.DataFrame:
    # ...
    df = SchemaManager.create_dataframe_safe(data, interface_name)
```

**问题分析**：
- 每次保存都要创建 Polars DataFrame
- `stk_factor_pro` 有 200+ 个字段，DataFrame 内存开销大
- 即使数据已保存，DataFrame 临时对象也会占用内存

#### 问题 3：异步写入队列积压

**文件**: [app4/core/storage.py](file:///home/quan/testdata/aspipe_v4/app4/core/storage.py#L827-L870)

```python
def save_data(self, interface_name: str, data: List[Dict[str, Any]], async_write: bool = True):
    if async_write:
        try:
            self.data_queue.put(
                {"interface_name": interface_name, "data": data},
                block=False,
            )
        except queue.Full:
            logger.warning(f"Storage queue is full, dropping data for {interface_name}")
```

**问题分析**：
- 异步写入模式下，数据被放入队列
- 如果写入速度跟不上下载速度，队列会积压
- 队列中的数据占用内存

### 4. 内存占用估算

| 项目 | 估算值 |
|------|--------|
| 每只股票记录大小 | 200 字段 × 8 字节 ≈ 1.6 KB |
| 每日数据量 | 5000 只 × 1.6 KB ≈ 8 MB |
| 9000 天累积（理论） | 8 MB × 9000 ≈ 72 GB |
| 实际观察 | 约 2 GB（16% of 12.4GB） |

实际内存占用低于理论值，因为：
1. Python 垃圾回收机制
2. 数据被分批保存后部分释放
3. 但 `all_data` 列表仍然持有引用，阻止完全释放

## 解决方案

### 方案 1：修复数据累积问题（推荐）

**文件**: [app4/core/pagination_executor.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py)

修改 `_execute_sequential` 方法，当使用 `save_callback` 时不累积数据：

```python
def _execute_sequential(
    self,
    interface_config: Dict[str, Any],
    params_list: List[Dict[str, Any]],
    make_request: Callable,
    coverage_manager: Optional[Any],
    progress_callback: Optional[Callable],
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    顺序执行多个请求
    """
    # 当有 save_callback 时，不累积数据到 all_data
    if save_callback:
        all_data = None  # 不累积，节省内存
        total_count = 0
    else:
        all_data = []
    
    consecutive_empty = 0
    stop_on_empty = self._get_stop_on_empty_config(interface_config)
    interface_name = interface_config.get("name", "unknown")

    for idx, params in enumerate(params_list):
        if progress_callback:
            progress_callback(idx + 1, len(params_list))

        if coverage_manager:
            if self._should_skip_by_coverage(
                interface_config, params, coverage_manager
            ):
                continue

        result = self._execute_single_request(interface_config, params, make_request, on_data_ready)

        if result:
            if on_data_ready:
                # 流式模式：result 是计数
                total_count += result
                consecutive_empty = 0
            else:
                # 原子化保存：每次请求的分页完成后立即保存
                if save_callback:
                    save_callback(interface_name, result)
                    logger.info(
                        f"[{interface_name}] 已保存 {len(result)} 条记录 (第{idx+1}/{len(params_list)}批)"
                    )
                    # 不 extend 到 all_data，让垃圾回收释放内存
                    if all_data is None:
                        total_count += len(result)
                else:
                    all_data.extend(result)
                consecutive_empty = 0
        else:
            consecutive_empty += self._estimate_empty_days(params)
            if stop_on_empty > 0 and consecutive_empty >= stop_on_empty:
                logger.info(f"Stopping after {consecutive_empty} consecutive empty days")
                break

    if on_data_ready or (save_callback and all_data is None):
        return total_count
    return all_data
```

**效果**：
- 当使用 `save_callback` 时，数据保存后立即可被垃圾回收
- 内存占用保持在单批次数据量级别（约 8 MB）

### 方案 2：增大窗口大小

**文件**: [app4/config/interfaces/stk_factor_pro.yaml](file:///home/quan/testdata/aspipe_v4/app4/config/interfaces/stk_factor_pro.yaml)

```yaml
pagination:
  enabled: true
  mode: reverse_date_range
  window_size_days: 30  # 从 1 改为 30，减少请求次数
```

**效果**：
- 减少 API 请求次数
- 但每次请求数据量增加，总内存占用变化不大
- 主要优化 API 调用效率

### 方案 3：启用流式处理

**文件**: [app4/update/update_manager.py](file:///home/quan/testdata/aspipe_v4/app4/update/update_manager.py#L412-L470)

修改 `_execute_download` 方法，启用 `on_data_ready` 回调：

```python
def _execute_download(
    self,
    interface_name: str,
    interface_config: Dict[str, Any],
    date_range: DateRange,
    options: UpdateOptions
) -> int:
    # ...
    
    # 定义流式处理回调
    def on_data_ready(data):
        """流式处理：数据准备好后立即保存，不累积"""
        if data:
            self.storage_manager.save_data(interface_name, data, async_write=True)
    
    # 使用统一的分页执行入口，启用流式处理
    result_data = self.pagination_executor.execute(
        interface_config=interface_config,
        base_params=params,
        context=context,
        make_request=self.downloader._make_request,
        coverage_manager=self.coverage_manager,
        on_data_ready=on_data_ready  # 启用流式处理
    )

    # 流式模式下 result_data 是计数
    return result_data if isinstance(result_data, int) else len(result_data)
```

**效果**：
- 数据逐批处理，不累积
- 内存占用最低

### 方案 4：调整异步写入配置

**文件**: [app4/config/settings.yaml](file:///home/quan/testdata/aspipe_v4/app4/config/settings.yaml)

```yaml
storage:
  # 选项 1：改为同步写入
  async_write: false
  
  # 选项 2：或者减小缓冲区大小
  buffer_threshold: 1000  # 默认可能是 10000
```

**效果**：
- 同步写入：数据立即写入磁盘，不占用队列内存
- 减小缓冲区：减少队列积压

## 推荐实施顺序

1. **立即实施**：方案 1（修复数据累积问题）
   - 影响范围小，只修改一处
   - 效果显著，内存占用降低到单批次水平

2. **后续优化**：方案 3（启用流式处理）
   - 更彻底的解决方案
   - 需要更多测试验证

3. **配置调整**：方案 4（调整异步写入）
   - 根据实际硬件情况调整
   - 平衡性能和内存占用

## 验证方法

实施修复后，可以通过以下方法验证：

```bash
# 1. 使用 top/htop 监控内存
watch -n 1 "ps aux | grep 'python app4/main.py' | grep -v grep"

# 2. 使用 Python 内存分析工具
python -m memory_profiler app4/main.py --update --interface stk_factor_pro --start_date 20250101

# 3. 观察日志输出
# 修复前：内存持续增长
# 修复后：内存保持稳定（在单批次数据量级别）
```

## 相关文件

| 文件 | 说明 |
|------|------|
| [app4/core/pagination_executor.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination_executor.py) | 分页执行器，数据累积问题所在 |
| [app4/core/processor.py](file:///home/quan/testdata/aspipe_v4/app4/core/processor.py) | 数据处理器，DataFrame 创建 |
| [app4/core/storage.py](file:///home/quan/testdata/aspipe_v4/app4/core/storage.py) | 存储管理器，异步写入队列 |
| [app4/update/update_manager.py](file:///home/quan/testdata/aspipe_v4/app4/update/update_manager.py) | 更新管理器，调用分页执行器 |
| [app4/config/interfaces/stk_factor_pro.yaml](file:///home/quan/testdata/aspipe_v4/app4/config/interfaces/stk_factor_pro.yaml) | 接口配置 |

---

*报告生成时间：2026-03-07*
