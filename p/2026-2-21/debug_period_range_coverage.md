# 调试方案：period_range 模式下载前去重检查

## 问题现象

代码修改已应用，但仍然会重复下载。日志中没有看到任何关于 period 检查的信息。

## 需要添加的调试日志

在 `app4/core/pagination_executor.py` 的以下位置添加 INFO 级别日志：

### 1. execute() 方法中（行 82-85 附近）

```python
if len(params_list) <= 1:
    if params_list:
        # 调试日志：显示参数内容
        logger.info(f"[DEBUG] params_list[0] = {params_list[0]}")
        if coverage_manager and self._should_skip_by_coverage(
            interface_config, params_list[0], coverage_manager
        ):
            logger.info(f"[DEBUG] Coverage check passed, skipping download")
            return []
```

### 2. _should_skip_by_coverage() 方法中（行 369-380 附近）

```python
api_name = interface_config.get("api_name", "")
logger.info(f"[DEBUG] _should_skip_by_coverage called, params = {params}")
if "_time_window" in params:
    strategy = "date_range"
elif "_period_query" in params:
    strategy = "period"
    logger.info(f"[DEBUG] Detected _period_query, using period strategy")
# ... 后续代码

# 在调用 coverage_manager.should_skip() 前
logger.info(f"[DEBUG] Calling should_skip with strategy={strategy}, clean_params={clean_params}")
result = coverage_manager.should_skip(api_name, clean_params, strategy=strategy)
logger.info(f"[DEBUG] should_skip returned: {result}")
return result
```

### 3. coverage_manager.py 的 should_skip() 方法中（行 282-286 附近）

```python
# 根据策略执行检测
result = False
logger.info(f"[DEBUG] should_skip: strategy={strategy}")
if strategy == "date_range":
    result = self._check_range_coverage(interface_name, params)
elif strategy == "period":
    logger.info(f"[DEBUG] Calling _check_period_existence with params={params}")
    result = self._check_period_existence(interface_name, params)
```

### 4. _check_period_existence() 方法中（行 412-417 附近）

```python
period = params.get('period')
logger.info(f"[DEBUG] _check_period_existence: period={period}")
if not period:
    logger.warning(f"[DEBUG] Missing period parameter for {interface_name}")
    return False
```

## 预期调试日志输出

如果一切正常，应该看到：
```
[DEBUG] params_list[0] = {'period': '20260331', '_period_query': True}
[DEBUG] _should_skip_by_coverage called, params = {'period': '20260331', '_period_query': True}
[DEBUG] Detected _period_query, using period strategy
[DEBUG] Calling should_skip with strategy=period, clean_params={'period': '20260331'}
[DEBUG] should_skip: strategy=period
[DEBUG] Calling _check_period_existence with params={'period': '20260331'}
[DEBUG] _check_period_existence: period=20260331
```

## 可能的问题点

1. `_period_query` 标记没有正确设置
2. `coverage_manager` 为 None
3. 异常被空 except 捕获
4. 缓存返回了错误的结果
