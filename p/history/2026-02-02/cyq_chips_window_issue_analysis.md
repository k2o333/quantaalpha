# cyq_chips 接口窗口分块问题分析

## 问题描述

根据设计文档 `cyq_complete_solution.md`，cyq_chips 接口应该使用 `stock_loop` 模式，并且：
- **窗口大小**: 30天 (`window_size_days: 30`)
- **预期行为**: 对每只股票，应该分多个30天的窗口来获取数据

但实际运行结果显示：
```
2026-02-02 19:18:51,165 - core.downloader - INFO - Downloading data for stock 000002.SZ, params: {'ts_code': '000002.SZ', 'start_date': '19910129'}
2026-02-02 19:18:52,234 - core.downloader - INFO - API returned 4 fields for cyq_chips
2026-02-02 19:18:52,257 - core.downloader - INFO - Downloaded 6000 records for 000002.SZ
```

只发起了一次请求，获取了6000条记录，没有按30天分窗口。

## 根本原因分析

### 1. 配置层面

查看 `cyq_chips.yaml` 配置：
```yaml
pagination:
  enabled: true
  mode: stock_loop
  window_size_days: 30
```

配置是正确的，但问题在于 `stock_loop` 模式的实现逻辑。

### 2. 代码层面 - main.py 的处理逻辑

在 `main.py:618-641` 中，当检测到 `stock_loop` 模式时：

```python
if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
    logger.info(f"Using stock_loop mode for {interface_name}")

    # [修正] stock_loop 模式：不传递日期参数，让接口返回全历史
    params = {}
    if args.ts_code:
        params['ts_code'] = args.ts_code
    logger.info(f"Using stock_loop mode for {interface_name}, fetching full history")
```

**问题就在这里**：代码明确清空了日期参数 (`params = {}`)，目的是"让接口返回全历史"。

### 3. 代码层面 - downloader.py 的处理逻辑

在 `download_single_stock` 方法 (`downloader.py:432-525`) 中：

```python
# 根据接口配置决定是否设置日期参数
parameter_config = interface_config.get('parameters', {})

# [修正] 只设置 start_date（如果接口支持且用户未显式指定）
if 'start_date' in parameter_config and 'start_date' not in stock_params:
    list_date = stock.get('list_date', '20050101')
    stock_params['start_date'] = list_date
```

这里只设置了 `start_date`，没有设置 `end_date`。

### 4. 为什么窗口分块没有生效

`window_size_days: 30` 配置在 `stock_loop` 模式下**没有被使用**。

查看 `pagination.py:get_window_size_for_interface`：

```python
def get_window_size_for_interface(interface_name: str, config: Dict[str, Any] = None) -> int:
    if config:
        pagination_config = config.get('pagination', {})
        if pagination_config.get('enabled', False):
            mode = pagination_config.get('mode', 'offset')
            if mode == 'date_range_daily':
                return 1
            elif mode == 'stock_loop':
                # 可以根据需要调整，比如一次处理30天的数据
                return pagination_config.get('window_size_days', 30)
```

这个函数返回窗口大小，但问题在于：**谁在使用这个窗口大小？**

### 5. 关键问题：stock_loop 模式没有实现窗口分块逻辑

查看 `pagination_executor.py:152-211` 的 `execute_stock_loop_pagination` 方法：

```python
def execute_stock_loop_pagination(self, interface_config: Dict[str, Any],
                                params: Dict[str, Any],
                                context: PaginationContext,
                                make_request_callback: Callable,
                                get_stock_list_callback: Callable,
                                coverage_manager: Optional[Any] = None,
                                force_download: bool = False) -> List[Dict[str, Any]]:
    # 获取股票列表
    stock_list = get_stock_list_callback()
    
    # ... 并发下载每只股票 ...
    for stock_params, stock_info in param_gen.generate_stock_params(...):
        future = executor.submit(
            make_request_callback,
            interface_config,
            stock_params
        )
```

**关键发现**：`execute_stock_loop_pagination` 方法直接调用 `make_request_callback` 发起请求，没有对单只股票进行窗口分块！

而 `download_single_stock` 方法 (`downloader.py:432-525`) 中，对于单只股票：

```python
if pagination_config.get('enabled', False):
    mode = pagination_config.get('mode', 'offset')

    if mode == 'date_range':
        stock_data = self.pagination_executor.execute_date_range_pagination(...)
    elif mode == 'offset':
        stock_data = self.pagination_executor.execute_offset_pagination(...)
    else:
        # 对于其他模式或未知模式，直接请求
        stock_data = self._make_request(interface_config, stock_params)
else:
    stock_data = self._make_request(interface_config, stock_params)
```

**问题**：当 `mode == 'stock_loop'` 时，走到 `else` 分支，直接发起请求，没有进行窗口分块！

## 总结：为什么30天窗口没有生效

1. **设计意图**：`cyq_chips` 配置为 `stock_loop` 模式，期望每只股票按30天窗口分块获取
2. **实际行为**：`stock_loop` 模式的实现只是并发处理多只股票，对单只股票没有分窗口
3. **根本原因**：`download_single_stock` 方法中，对于 `stock_loop` 模式没有调用窗口分块逻辑
4. **结果**：单只股票一次性获取全历史数据（6000条记录）

## 修复方案

### 方案1：修改 download_single_stock 方法（推荐）

在 `downloader.py:492-509` 区域，添加对 `stock_loop` 模式的窗口分块支持：

```python
if mode == 'date_range':
    stock_data = self.pagination_executor.execute_date_range_pagination(...)
elif mode == 'stock_loop':
    # 新增：对单只股票进行日期范围分块
    stock_data = self.pagination_executor.execute_date_range_pagination(
        interface_config, stock_params, context, self._make_request,
        coverage_manager=self.coverage_manager, force_download=self.force_download,
        get_trade_calendar_callback=self.get_trade_calendar
    )
elif mode == 'offset':
    stock_data = self.pagination_executor.execute_offset_pagination(...)
```

### 方案2：修改 cyq_chips 配置

如果 `cyq_chips` 接口实际上不需要窗口分块（API支持大日期范围），可以修改配置：

```yaml
pagination:
  enabled: true
  mode: stock_loop
  # 移除 window_size_days，或者注释说明此配置当前未生效
```

### 方案3：修改 execute_stock_loop_pagination 方法

在 `pagination_executor.py` 中，对每只股票进行窗口分块处理。但这会改变 `stock_loop` 模式的语义，可能影响其他接口。

## 建议

**推荐方案1**，因为它：
1. 保持配置语义一致（`window_size_days: 30` 实际生效）
2. 不影响其他接口
3. 符合设计文档的预期行为

## 相关代码位置

- 配置: `app4/config/interfaces/cyq_chips.yaml`
- main.py 处理: `app4/main.py:618-641`
- 单只股票下载: `app4/core/downloader.py:432-525`
- stock_loop 实现: `app4/core/pagination_executor.py:152-211`
- 窗口大小获取: `app4/core/pagination.py:290-330`
