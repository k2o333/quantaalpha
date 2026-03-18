# reverse_date_range 模式优化方案 - 移除不必要的股票循环

## 问题分析

### 当前行为

观察日志，`suspend_d` 接口使用 `reverse_date_range` 模式：

```
2026-03-01 13:41:47,918 - __main__ - INFO - Downloading data for suspend_d, pagination mode: reverse_date_range
2026-03-01 13:41:47,919 - core.downloader - INFO - 从内存缓存或Data目录获取到 5484 只股票
```

然后进行了大量 Coverage 检测：
```
2026-03-01 13:41:47,922 - core.coverage_manager - INFO - Coverage for suspend_d (20260105-20260213): 16.67% (5/30)
...
```

最终下载了 **20 个请求**，总计 **10253 条记录**，但处理后：
```
2026-03-01 13:42:00,119 - core.processor - INFO - Filtered 10148 records with null primary keys for interface suspend_d, kept 105/10253
2026-03-01 13:42:00,132 - core.processor - INFO - Processed 105 records for suspend_d
2026-03-01 13:42:00,143 - __main__ - INFO - Deduplication completed for suspend_d: input=105, compared=72, output=33, removed=72, dedup_rate=68.57%
```

### 问题根源

`reverse_date_range` 模式在 `migrate_legacy_config()` 函数中（`pagination.py:718-727`）被转换为：

```python
elif mode == "reverse_date_range":
    new_config["mode"] = "reverse_date_range"
    new_config["time_range"] = {
        "enabled": True,
        "window": window_str,
        "reverse": True,
        "stop_on_empty": old_pagination.get("empty_threshold_days", 90),
    }
```

**没有启用 `stock_loop`**，这是正确的。但问题在于：

1. **主流程仍然获取了股票列表**：`downloader.py` 中 `_get_stock_list()` 在每次下载时都会被调用
2. **Coverage 检测按股票维度进行**：这导致对每个时间窗口检查 30 天覆盖率，但实际不需要股票维度

### 核心问题

`reverse_date_range` 模式的接口（如 `suspend_d`, `block_trade`, `new_share` 等）有以下特点：

1. **不按股票代码分页** - API 返回当天所有股票的停牌信息
2. **仅需 `trade_date` 作为时间锚点** - 不需要遍历股票代码
3. **API 参数中 `ts_code` 是可选的** - 不传则返回所有股票

但当前实现仍然：
1. 预加载 5484 只股票列表（浪费内存和时间）
2. Coverage 检测可能误判（虽然最终行为正确，但产生了不必要的计算）

## 解决方案

### 方案设计

为 `reverse_date_range` 模式增加一个配置标识，明确表示该接口不需要股票循环：

```yaml
# suspend_d.yaml
pagination:
  mode: reverse_date_range
  window_size_days: 30
  no_stock_required: true  # 新增：标识该接口不需要股票列表
```

### 代码修改

#### 1. 修改 `pagination.py` - `migrate_legacy_config()` 函数

```python
# 文件: app4/core/pagination.py
# 位置: migrate_legacy_config() 函数，约 L718

elif mode == "reverse_date_range":
    new_config["mode"] = "reverse_date_range"
    new_config["time_range"] = {
        "enabled": True,
        "window": window_str,
        "reverse": True,
        "stop_on_empty": old_pagination.get("empty_threshold_days", 90),
    }
    # 新增：标记不需要股票循环
    new_config["no_stock_required"] = old_pagination.get("no_stock_required", True)
```

#### 2. 修改 `pagination.py` - `PaginationComposer.compose()` 方法

在 `compose()` 方法开头检查 `no_stock_required` 配置：

```python
def compose(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """组合所有启用的分页维度"""
    params_stream = [base_params]
    
    # 检查是否需要跳过股票列表加载
    no_stock_required = self.config.get("no_stock_required", False)
    
    # ... 其余逻辑不变 ...
    
    # 2. 股票维度 - 仅在需要时启用
    if self._is_enabled("stock_loop") and not no_stock_required:
        params_stream = list(self._apply_stock_loop(params_stream))
```

#### 3. 修改 `downloader.py` - `_execute_pagination()` 方法

```python
def _execute_pagination(
    self, interface_config: Dict[str, Any], params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """执行分页/循环逻辑 - 控制器"""
    pagination_config = interface_config.get("pagination", {})
    
    # 检查是否需要股票列表
    no_stock_required = pagination_config.get("no_stock_required", False)
    
    # 仅在需要时获取股票列表
    stock_list = None if no_stock_required else self._get_stock_list()
    
    # 创建上下文
    pagination_context = create_context_with_legacy_support(
        interface_config=interface_config,
        trade_calendar=trade_calendar,
        stock_list=stock_list,  # 传入 None 而不是加载全部股票
        coverage_manager=self.coverage_manager,
    )
    # ...
```

#### 4. 修改 `coverage_manager.py` - 覆盖率检测逻辑

对于 `no_stock_required` 的接口，使用日期维度覆盖率检测：

```python
def _get_coverage_strategy(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> str:
    """确定覆盖率检测策略"""
    pagination = interface_config.get("pagination", {})
    
    # 如果接口标记为不需要股票，使用日期维度覆盖率
    if pagination.get("no_stock_required", False):
        return "date_only"
    
    # 原有逻辑...
```

### 配置文件更新

需要更新的接口配置文件（`reverse_date_range` 模式且不需要股票循环的接口）：

| 接口 | 文件 | 说明 |
|------|------|------|
| `suspend_d` | `config/interfaces/suspend_d.yaml` | 每日停复牌信息 |
| `block_trade` | `config/interfaces/block_trade.yaml` | 大宗交易 |
| `new_share` | `config/interfaces/new_share.yaml` | 新股上市 |
| `stk_surv` | `config/interfaces/stk_surv.yaml` | 股票调查 |
| `namechange` | `config/interfaces/namechange.yaml` | 股票更名 |

配置示例：
```yaml
pagination:
  mode: reverse_date_range
  window_size_days: 30
  no_stock_required: true  # 新增
```

### 实施步骤

1. **Step 1**: 修改 `pagination.py` - 在 `migrate_legacy_config()` 中默认设置 `no_stock_required: true`
2. **Step 2**: 修改 `downloader.py` - 根据配置跳过股票列表加载
3. **Step 3**: 修改 `coverage_manager.py` - 调整覆盖率检测策略
4. **Step 4**: 更新相关接口配置文件
5. **Step 5**: 测试验证

### 预期效果

修改后，`suspend_d` 接口的运行日志应该变为：

```
2026-03-01 13:41:47,918 - __main__ - INFO - Downloading data for suspend_d, pagination mode: reverse_date_range
2026-03-01 13:41:47,918 - core.downloader - INFO - Skipping stock list loading for no_stock_required interface: suspend_d
# 不再显示 "从内存缓存或Data目录获取到 5484 只股票"
# Coverage 检测按日期维度进行
2026-03-01 13:41:47,920 - core.coverage_manager - INFO - Coverage for suspend_d date range (20260105-20260213): 100%
```

### 影响范围

- **无影响**: `stock_loop` 模式的接口（如 `daily_basic`, `moneyflow` 等）
- **无影响**: `period_range` 模式的接口（如 `balancesheet_vip` 等）
- **优化**: `reverse_date_range` 模式且不需要股票的接口

### 兼容性

- **向后兼容**: 不配置 `no_stock_required` 时，默认行为不变
- **自动推断**: 对于 `reverse_date_range` 模式，默认设置 `no_stock_required: true`，除非明确配置 `stock_loop.enabled: true`

## 总结

| 项目 | 当前行为 | 优化后行为 |
|------|----------|------------|
| 股票列表加载 | 总是加载 5484 只股票 | 按需加载 |
| Coverage 检测 | 可能包含股票维度 | 纯日期维度 |
| 内存占用 | 较高 | 降低 |
| 启动速度 | 较慢 | 提升 |

这个优化方案可以显著减少不必要的资源消耗，特别是对于 `suspend_d` 这类不需要按股票遍历的接口。
