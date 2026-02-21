# period_range 模式下载前去重检查 - 完整修复方案

## 一、问题总结

`period_range` 模式的接口（如 `income_vip`）在下载前没有正确检查已有数据，导致重复下载已存在的数据，浪费 API 请求配额。

### 受影响的接口（7个）

| 接口名称 | 配置文件 | pagination.mode |
|---------|----------|-----------------|
| income_vip | income_vip.yaml | period_range |
| balancesheet_vip | balancesheet_vip.yaml | period_range |
| cashflow_vip | cashflow_vip.yaml | period_range |
| fina_indicator_vip | fina_indicator_vip.yaml | period_range |
| forecast_vip | forecast_vip.yaml | period_range |
| express_vip | express_vip.yaml | period_range |
| fina_mainbz_vip | fina_mainbz_vip.yaml | period_range |

---

## 二、问题根因分析

### 2.1 执行流程追踪

```
用户请求: python main.py --update --interface income_vip --start_date 20260212
    │
    ▼
update_manager.update_interface()
    │
    ├─► should_update_interface()  [问题1在这里]
    │       │
    │       ▼
    │   params = {start_date: '20260212', end_date: '20260221'}  # 没有 period!
    │       │
    │       ▼
    │   coverage_manager.should_skip(interface_name, params, strategy='auto')
    │       │
    │       ▼
    │   _check_period_existence(interface_name, params)
    │       │
    │       ▼
    │   period = params.get('period')  # None!
    │       │
    │       ▼
    │   return False  # 直接返回 False，检查无效
    │
    ▼
_execute_download()  [问题2、3在这里]
    │
    ▼
pagination_executor.execute()
    │
    ├─► params_list = composer.compose(base_params)
    │       │
    │       ▼
    │   _apply_period_range() 添加 period='20260331' 和 _period_query=True
    │       │
    │       ▼
    │   params_list = [{period: '20260331', _period_query: True}]
    │
    ├─► len(params_list) == 1, 进入单请求分支
    │       │
    │       ▼
    │   _should_skip_by_coverage()  [问题2：没有检测 _period_query]
    │       │
    │       ▼
    │   strategy = 'default'  # 没有检测到 _period_query
    │       │
    │       ▼
    │   return False  # 返回不跳过
    │
    ▼
_execute_single()  [问题3：没有调用覆盖率检查]
    │
    ▼
执行 API 请求，下载数据
```

### 2.2 三个问题的详细说明

#### 问题1：`should_update_interface()` 参数缺少 `period`（最关键）

**文件**: `app4/update/update_manager.py:387-396`

```python
def should_update_interface(...):
    params = {
        'start_date': date_range.start_date,  # 只有 start_date
        'end_date': date_range.end_date       # 只有 end_date
    }
    # 没有 period 参数！

    should_skip = self.coverage_manager.should_skip(
        interface_name, params, strategy='auto'
    )
```

**影响**: `_check_period_existence()` 需要 `period` 参数，没有就返回 `False`。

#### 问题2：`_should_skip_by_coverage()` 没有检测 `_period_query` 标记

**文件**: `app4/core/pagination_executor.py:366-379`

```python
def _should_skip_by_coverage(...):
    if '_time_window' in params:
        strategy = 'date_range'
    elif '_stock_info' in params:
        strategy = 'stock'
    elif '_type_value' in params:
        strategy = 'type'
    else:
        strategy = 'default'  # ← _period_query 没有被检测！
```

**影响**: 即使 `params` 中有 `_period_query: True`，也无法识别为 `period` 策略。

#### 问题3：单请求分支没有调用覆盖率检查

**文件**: `app4/core/pagination_executor.py:82-91`

```python
if len(params_list) <= 1:
    if params_list:
        # 问题：直接执行请求，没有调用 _should_skip_by_coverage()
        return self._execute_single(
            interface_config, params_list[0], make_request
        )
    return []
```

**影响**: `period_range` 模式通常只生成 1-4 个报告期参数，很容易触发这个条件，完全绕过覆盖率检查。

---

## 三、修复方案

### 3.1 修复问题1：在 `_check_period_existence()` 中支持从日期范围计算报告期

**文件**: `app4/core/coverage_manager.py`

**位置**: `_check_period_existence()` 方法（约第 396 行）

**修改前**:
```python
def _check_period_existence(
    self, interface_name: str, params: Dict[str, Any]
) -> bool:
    period = params.get('period')
    if not period:
        logger.debug(
            f"Missing period parameter for {interface_name}, skipping period check"
        )
        return False
    # ... 后续检查逻辑
```

**修改后**:
```python
def _check_period_existence(
    self, interface_name: str, params: Dict[str, Any]
) -> bool:
    period = params.get('period')

    # 新增：如果没有 period 参数，但有 start_date/end_date，则计算报告期列表
    if not period:
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date and end_date:
            # 计算日期范围内的所有报告期
            periods = self._convert_date_range_to_periods(start_date, end_date)
            if not periods:
                logger.debug(f"No periods found in range {start_date}-{end_date}")
                return False

            # 检查所有报告期是否都已存在
            logger.debug(f"Checking {len(periods)} periods for {interface_name}: {periods}")
            for p in periods:
                if not self._check_single_period_existence(interface_name, p):
                    logger.debug(f"Period {p} does not exist, need to download")
                    return False  # 有一个不存在就需要下载

            logger.info(f"All {len(periods)} periods exist for {interface_name}, skipping")
            return True  # 全部存在才跳过
        else:
            logger.debug(
                f"Missing period parameter for {interface_name}, skipping period check"
            )
            return False

    # 原有逻辑：检查单个 period
    return self._check_single_period_existence(interface_name, period)


def _check_single_period_existence(
    self, interface_name: str, period: str
) -> bool:
    """
    检查单个报告期是否存在

    Args:
        interface_name: 接口名称
        period: 报告期，如 '20260331'

    Returns:
        True 表示已存在（应跳过），False 表示不存在（应下载）
    """
    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get("duplicate_detection", {})
    date_column = detection_config.get("date_column", "end_date")

    try:
        cache_key = f"{interface_name}_periods_{date_column}"

        with self._cache_lock:
            if cache_key not in self._cache:
                logger.debug(f"Loading all periods for {interface_name} using column {date_column}")
                df = self.storage_manager.read_interface_data(
                    interface_name, columns=[date_column]
                )

                if not df.is_empty():
                    periods_set = set()
                    for date_val in df[date_column]:
                        if isinstance(date_val, str):
                            periods_set.add(date_val)
                        elif hasattr(date_val, "strftime"):
                            periods_set.add(date_val.strftime("%Y%m%d"))
                        else:
                            periods_set.add(str(date_val))
                    self._cache[cache_key] = periods_set
                    logger.info(
                        f"Loaded {len(self._cache[cache_key])} existing periods for {interface_name}"
                    )
                else:
                    self._cache[cache_key] = set()
                    logger.debug(f"No existing periods found for {interface_name}")

            result = period in self._cache[cache_key]

        logger.debug(
            f"Period {period} {'exists' if result else 'does not exist'} for {interface_name}"
        )
        return result

    except Exception as e:
        logger.warning(f"Period existence check failed for {interface_name}: {e}")
        return False


def _convert_date_range_to_periods(
    self, start_date: str, end_date: str
) -> List[str]:
    """
    将日期区间转换为报告期列表

    规则：只有当报告期日期在用户日期区间内时，才包含该报告期

    Args:
        start_date: 用户传入的开始日期，如 '20260212'
        end_date: 用户传入的结束日期，如 '20260221'

    Returns:
        报告期列表，如 ['20260331']
    """
    periods = []
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])

    quarter_ends = ["0331", "0630", "0930", "1231"]

    for year in range(start_year, end_year + 1):
        for qe in quarter_ends:
            period = f"{year}{qe}"
            if start_date <= period <= end_date:
                periods.append(period)

    return periods
```

### 3.2 修复问题2：添加 `_period_query` 检测

**文件**: `app4/core/pagination_executor.py`

**位置**: `_should_skip_by_coverage()` 方法（约第 366 行）

**修改前**:
```python
api_name = interface_config.get("api_name", "")
if "_time_window" in params:
    strategy = "date_range"
elif "_stock_info" in params:
    strategy = "stock"
elif "_type_value" in params:
    strategy = "type"
else:
    strategy = "default"
```

**修改后**:
```python
api_name = interface_config.get("api_name", "")
if "_time_window" in params:
    strategy = "date_range"
elif "_period_query" in params:  # 新增：检测 period_range 模式
    strategy = "period"
elif "_stock_info" in params:
    strategy = "stock"
elif "_type_value" in params:
    strategy = "type"
else:
    strategy = "default"
```

### 3.3 修复问题3：单请求分支添加覆盖率检查

**文件**: `app4/core/pagination_executor.py`

**位置**: `execute()` 方法（约第 82 行）

**修改前**:
```python
if len(params_list) <= 1:
    if params_list:
        return self._execute_single(
            interface_config, params_list[0], make_request
        )
    return []
```

**修改后**:
```python
if len(params_list) <= 1:
    if params_list:
        # 新增：覆盖率检查
        if coverage_manager and self._should_skip_by_coverage(
            interface_config, params_list[0], coverage_manager
        ):
            logger.info(f"Skipping request due to coverage check")
            return []
        return self._execute_single(
            interface_config, params_list[0], make_request
        )
    return []
```

---

## 四、修复后的执行流程

```
用户请求: python main.py --update --interface income_vip --start_date 20260212
    │
    ▼
update_manager.update_interface()
    │
    ├─► should_update_interface()
    │       │
    │       ▼
    │   params = {start_date: '20260212', end_date: '20260221'}
    │       │
    │       ▼
    │   coverage_manager.should_skip(strategy='auto')
    │       │
    │       ▼
    │   _check_period_existence()
    │       │
    │       ▼
    │   period = None, 但有 start_date/end_date
    │       │
    │       ▼
    │   periods = _convert_date_range_to_periods() = ['20260331']
    │       │
    │       ▼
    │   _check_single_period_existence('20260331')
    │       │
    │       ▼
    │   从已存在数据中检查 '20260331' 是否存在
    │       │
    │       ├─► 存在 → return True → should_skip = True → 跳过下载 ✓
    │       │
    │       └─► 不存在 → return False → should_skip = False → 继续下载
    │
    ▼ (如果需要下载)
_execute_download()
    │
    ▼
pagination_executor.execute()
    │
    ├─► params_list = [{period: '20260331', _period_query: True}]
    │
    ├─► len(params_list) == 1, 进入单请求分支
    │       │
    │       ▼
    │   _should_skip_by_coverage()
    │       │
    │       ▼
    │   检测到 _period_query → strategy = 'period'
    │       │
    │       ▼
    │   coverage_manager.should_skip(strategy='period')
    │       │
    │       ▼
    │   _check_single_period_existence('20260331')
    │       │
    │       ▼
    │   return True/False
    │
    ▼
执行 API 请求（如果需要）
```

---

## 五、需要修改的文件清单

| 文件 | 修改内容 | 行号范围 |
|------|----------|----------|
| `app4/core/coverage_manager.py` | 修改 `_check_period_existence()` 方法 | 396-461 |
| `app4/core/coverage_manager.py` | 新增 `_check_single_period_existence()` 方法 | 新增 |
| `app4/core/coverage_manager.py` | 新增 `_convert_date_range_to_periods()` 方法 | 新增 |
| `app4/core/pagination_executor.py` | 修改 `_should_skip_by_coverage()` 方法 | 366-379 |
| `app4/core/pagination_executor.py` | 修改 `execute()` 方法 | 82-91 |

---

## 六、验证方法

```bash
# 1. 首次下载（应正常下载）
python app4/main.py --update --interface income_vip --start_date 20260212

# 预期日志：
# - "Loaded X existing periods for income_vip"
# - "Period 20260331 does not exist, need to download"
# - "Downloaded 13 records for income_vip"

# 2. 再次下载相同日期范围（应跳过）
python app4/main.py --update --interface income_vip --start_date 20260212

# 预期日志：
# - "Checking 1 periods for income_vip: ['20260331']"
# - "All 1 periods exist for income_vip, skipping"
# - 无 "Downloaded X records" 日志
# - 无 API 请求

# 3. 测试跨多个报告期的日期范围
python app4/main.py --update --interface income_vip --start_date 20240101 --end_date 20240630

# 预期：
# - 检查 20240331 和 20240630 两个报告期
# - 只下载不存在的报告期
```

---

## 七、注意事项

1. **缓存一致性**：修改后需要考虑缓存失效的情况，确保在数据更新后能够重新检查。

2. **性能考虑**：`_convert_date_range_to_periods()` 方法是简单的日期计算，性能开销很小。

3. **向后兼容**：修改不影响现有的 `date_range` 和 `stock_loop` 模式接口。

4. **测试覆盖**：建议对三种场景进行测试：
   - 单个报告期检查
   - 多个报告期检查（部分存在、全部存在、全部不存在）
   - 空日期范围处理
