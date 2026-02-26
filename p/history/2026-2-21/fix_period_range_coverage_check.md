# 修复 period_range 模式接口的下载前去重检查

## 问题描述

`period_range` 模式的接口（如 `income_vip`、`balancesheet_vip` 等）在下载前没有正确检查已有数据，导致：
- 即使数据已存在，仍然发起 API 请求
- 浪费 API 请求配额
- 下载后在存储阶段才去重（此时已产生无效请求）

## 受影响的接口（7个）

- income_vip
- balancesheet_vip
- cashflow_vip
- fina_indicator_vip
- forecast_vip
- express_vip
- fina_mainbz_vip

## 根本原因

**文件**: `app4/core/pagination_executor.py` 和 `app4/update/update_manager.py`

有**三个问题**：

### 问题1：`should_update_interface()` 传入的参数缺少 `period`（关键问题）

`update_manager.py:387-396`：

```python
params = {
    'start_date': date_range.start_date,
    'end_date': date_range.end_date
}
should_skip = self.coverage_manager.should_skip(interface_name, params, strategy='auto')
```

然后 `coverage_manager._check_period_existence()` 需要 `period` 参数：

```python
period = params.get('period')
if not period:
    return False  # ← 没有 period 参数，直接返回 False！
```

**这是最关键的问题！`should_update_interface()` 传入的参数不包含 `period`，导致检查无效。**

### 问题2：缺少 `_period_query` 检测（行 309-316）

`pagination_executor._should_skip_by_coverage()` 方法中缺少对 `_period_query` 标记的检测：

```python
# 当前代码（有问题）
if '_time_window' in params:
    strategy = 'date_range'
elif '_stock_info' in params:
    strategy = 'stock'
elif '_type_value' in params:
    strategy = 'type'
else:
    strategy = 'default'  # ← period_range 模式走到这里，检查无效
```

### 问题3：`_execute_single()` 没有覆盖率检查（行 82-87）

当 `params_list` 长度 <= 1 时，会调用 `_execute_single()`，但该方法**没有调用** `_should_skip_by_coverage()`：

```python
# 当前代码（有问题）
if len(params_list) <= 1:
    return (
        self._execute_single(interface_config, params_list[0], make_request)
        if params_list
        else []
    )
```

## 修复方案

### 修改文件
- `app4/core/pagination_executor.py`
- `app4/core/coverage_manager.py`

### 修改1：在 `_check_period_existence()` 中支持从 `start_date/end_date` 计算 `period`（关键修复）

**文件**: `app4/core/coverage_manager.py`

**位置**: `_check_period_existence()` 方法开头

```python
def _check_period_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
    period = params.get('period')
    
    # 新增：如果没有 period 参数，但有 start_date/end_date，则计算报告期列表
    if not period:
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date and end_date:
            # 计算 start_date 到 end_date 范围内的所有报告期
            periods = self._convert_date_range_to_periods(start_date, end_date)
            if not periods:
                return False
            # 检查所有报告期是否都已存在
            for p in periods:
                if not self._check_single_period_existence(interface_name, p):
                    return False  # 有一个不存在就需要下载
            return True  # 全部存在才跳过
        else:
            logger.debug(f"Missing period parameter for {interface_name}, skipping period check")
            return False
    
    # 原有逻辑：检查单个 period
    return self._check_single_period_existence(interface_name, period)

def _check_single_period_existence(self, interface_name: str, period: str) -> bool:
    """检查单个报告期是否存在"""
    # ... 原有的 _check_period_existence 逻辑移到这里
```

同时需要添加 `_convert_date_range_to_periods()` 方法（可以复用 `pagination.py` 中的逻辑）。

### 修改2：添加 `_period_query` 检测（行 309-316 附近）

在 `_should_skip_by_coverage()` 方法中添加对 `_period_query` 的检测：

```python
# 修改后
if '_time_window' in params:
    strategy = 'date_range'
elif '_period_query' in params:  # 新增
    strategy = 'period'
elif '_stock_info' in params:
    strategy = 'stock'
elif '_type_value' in params:
    strategy = 'type'
else:
    strategy = 'default'
```

### 修改3：在 `execute()` 方法中添加覆盖率检查（行 82-87）

```python
# 修改后
if len(params_list) <= 1:
    if params_list:
        # 添加覆盖率检查
        if coverage_manager and self._should_skip_by_coverage(
            interface_config, params_list[0], coverage_manager
        ):
            return []
        return self._execute_single(interface_config, params_list[0], make_request)
    return []
```

## 修复后的完整流程

1. 用户传入 `start_date=20260212, end_date=20260221`
2. `_apply_period_range()` 转换为 `period='20260331'`，并设置 `_period_query: True`
3. `params_list` 长度为 1，进入 `execute()` 的特殊分支
4. **新增**：在 `execute()` 中调用 `_should_skip_by_coverage()` 检查
5. `_should_skip_by_coverage()` 检测到 `_period_query` → `strategy = 'period'`
6. `_check_period_existence()` 检查 `period='20260331'` 是否已存在
7. 如果已存在 → 跳过请求，不消耗 API 配额
8. 如果不存在 → 正常下载

## 验证方法

```bash
# 1. 首次下载（应正常下载）
python app4/main.py --update --interface income_vip --start_date 20260212

# 2. 再次下载相同日期范围（应跳过，无实际下载）
python app4/main.py --update --interface income_vip --start_date 20260212

# 预期结果：
# - 日志显示 "Period 20260331 exists for income_vip" 或类似信息
# - 无 "Downloaded X records" 日志
# - 无新数据写入
```

## 相关代码路径

| 功能 | 文件 | 行号 |
|------|------|------|
| 问题1：缺少检测 | `app4/core/pagination_executor.py` | 366-375 |
| 问题2：单请求跳过检查 | `app4/core/pagination_executor.py` | 82-87 |
| period参数生成 | `app4/core/pagination.py` | 134-172 |
| 报告期检查逻辑 | `app4/core/coverage_manager.py` | 396-461 |
| 日期转报告期 | `app4/core/pagination.py` | 174-201 |

## 之前的方案遗漏

之前的方案只修复了问题2和问题3，没有发现问题1。实际上**问题1是最关键的问题**：

- `should_update_interface()` 传入的参数只有 `start_date/end_date`，没有 `period`
- `_check_period_existence()` 需要 `period` 参数，没有就直接返回 `False`
- 导致 `period_range` 模式的接口在 `update_manager` 层面的检查就失效了

**修复优先级**：
1. **问题1**：必须修复，否则任何层面的检查都无效
2. **问题2**：必须修复，确保 `pagination_executor` 层面的检查正确
3. **问题3**：必须修复，确保单请求情况下的检查生效
