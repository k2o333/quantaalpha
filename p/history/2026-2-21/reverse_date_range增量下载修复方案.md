# reverse_date_range + is_date_anchor 模式增量下载修复方案

## 问题描述

`reverse_date_range` 模式的参数转换逻辑已实现，但**缺少增量下载（跳过已下载日期）功能**。

### 当前行为

```
用户命令: python app4/main.py --update --interface cyq_perf --start_date 20260205 --end_date 20260220

执行流程:
1. pagination._apply_date_anchor_range() 生成参数:
   [{trade_date: "20260220"}, {trade_date: "20260219"}, ..., {trade_date: "20260205"}]
   
2. pagination_executor._execute_sequential() 执行请求
   - 每个请求都会被发送，即使数据已存在
   - 已有代码尝试跳过，但未正确生效
```

### 问题定位

`pagination_executor.py:399-414` 中已有跳过逻辑：

```python
if date_anchor_param:
    if date_anchor_param in clean_params:
        return coverage_manager.should_skip(api_name, clean_params, strategy='period')
```

**调用了 `period` 策略**，但 `coverage_manager._check_period_existence` 只检查 `period` 参数：

```python
def _check_period_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
    period = params.get('period')  # ← 只检查 'period' 参数！
    if not period:
        ...
        return False  # trade_date 参数不会被检测
```

---

## 解决方案：修改 `_check_period_existence` 支持任意日期锚定参数

### 修改文件

`app4/core/coverage_manager.py`

### 修改内容

```python
def _check_period_existence(
    self, interface_name: str, params: Dict[str, Any]
) -> bool:
    """
    检查日期锚定值是否存在（全市场维度）

    支持任意日期锚定参数：period, trade_date, ann_date, end_date 等
    
    对于 period_range 模式，检测的是整个报告期是否有数据
    对于 reverse_date_range + is_date_anchor 模式，检测单个日期值是否存在

    Args:
        interface_name: 接口名称
        params: 请求参数，应包含 period / trade_date / ann_date 等日期锚定参数

    Returns:
        True 表示已存在（应跳过），False 表示不存在（应下载）
    """
    # 获取接口配置和日期列
    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get("duplicate_detection", {})
    date_column = detection_config.get("date_column", "trade_date")
    
    # 尝试从多个可能的日期锚定参数中获取值
    anchor_value = None
    anchor_param_name = None
    
    # 按优先级检查日期锚定参数
    for param_name in ['period', 'trade_date', 'ann_date', 'end_date', 'f_ann_date']:
        if params.get(param_name):
            anchor_value = params.get(param_name)
            anchor_param_name = param_name
            break
    
    if anchor_value:
        # 单个日期锚定值：检查是否存在
        return self._check_single_period_existence_with_column(
            interface_name, anchor_value, date_column
        )
    
    # 没有单个日期锚定值，检查 start_date/end_date 范围
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    if start_date and end_date:
        # 计算日期范围内的所有报告期
        periods = self._convert_date_range_to_periods(start_date, end_date)
        if not periods:
            logger.info(f"No completed periods in range {start_date}-{end_date}, skipping")
            return True

        # 检查所有报告期是否都已存在
        logger.debug(f"Checking {len(periods)} periods for {interface_name}: {periods}")
        for p in periods:
            if not self._check_single_period_existence_with_column(
                interface_name, p, date_column
            ):
                logger.debug(f"Period {p} does not exist, need to download")
                return False

        logger.info(f"All {len(periods)} periods exist for {interface_name}, skipping")
        return True

    logger.debug(
        f"No date anchor parameter found for {interface_name}, skipping period check"
    )
    return False


def _check_single_period_existence_with_column(
    self, interface_name: str, anchor_value: str, date_column: str
) -> bool:
    """
    检查单个日期锚定值是否存在

    Args:
        interface_name: 接口名称
        anchor_value: 日期锚定值，如 '20260220' 或 '20260331'
        date_column: 数据文件中的日期列名

    Returns:
        True 表示已存在（应跳过），False 表示不存在（应下载）
    """
    try:
        cache_key = f"{interface_name}:dates:{date_column}"

        with self._cache_lock:
            if cache_key not in self._cache:
                logger.debug(f"Loading all dates for {interface_name} using column {date_column}")
                df = self.storage_manager.read_interface_data(
                    interface_name, columns=[date_column]
                )

                if not df.is_empty():
                    dates_set = set()
                    for date_val in df[date_column]:
                        if isinstance(date_val, str):
                            dates_set.add(date_val)
                        elif hasattr(date_val, "strftime"):
                            dates_set.add(date_val.strftime("%Y%m%d"))
                        else:
                            dates_set.add(str(date_val))
                    self._cache[cache_key] = dates_set
                    logger.info(
                        f"Loaded {len(self._cache[cache_key])} existing dates for {interface_name}"
                    )
                else:
                    self._cache[cache_key] = set()
                    logger.debug(f"No existing dates found for {interface_name}")

                result = anchor_value in self._cache[cache_key]

        logger.debug(
            f"Date {anchor_value} {'exists' if result else 'does not exist'} for {interface_name}"
        )
        return result

    except Exception as e:
        logger.warning(f"Date existence check failed for {interface_name}: {e}")
        return False
```

### 同步修改：删除原有的 `_check_single_period_existence` 方法

将原有的 `_check_single_period_existence` 方法重命名/替换为 `_check_single_period_existence_with_column`，并添加 `date_column` 参数。

---

## 修改影响范围

### 受影响的接口

| 接口 | 模式 | is_date_anchor | 影响 |
|------|------|----------------|------|
| cyq_perf | reverse_date_range | true (trade_date) | **主要受益**：增量下载生效 |
| income_vip 等 | period_range | false | 无影响（走 start_date/end_date 分支） |

### 不受影响的接口

| 接口 | 原因 |
|------|------|
| stock_loop 模式接口 | 走 stock 策略，不调用 period 策略 |
| 普通 date_range 接口 | 走 date_range 策略 |

---

## 验证测试

### 测试 1: cyq_perf 增量下载

```bash
# 第一次下载
python app4/main.py --update --interface cyq_perf --start_date 20260205 --end_date 20260220

# 第二次下载（应跳过已有数据）
python app4/main.py --update --interface cyq_perf --start_date 20260205 --end_date 20260220

# 预期日志：
# [cyq_perf] Date 20260220 exists, skipping
# [cyq_perf] Date 20260219 exists, skipping
# ...
```

### 测试 2: period_range 模式不受影响

```bash
python app4/main.py --update --interface income_vip --start_date 20260101 --end_date 20260220

# 预期行为与修改前一致
```

---

## 实施清单

- [ ] 修改 `coverage_manager.py` 的 `_check_period_existence` 方法
- [ ] 重命名 `_check_single_period_existence` 为 `_check_single_period_existence_with_column`
- [ ] 运行测试验证

---

## 文档信息

| 版本 | 说明 |
|------|------|
| v1 | 初始版本 - 复用现有 period 策略机制 |

- **创建时间**: 2026-02-23
- **适用版本**: aspipe_v4
- **修改类型**: Bug 修复
- **修改文件**: `app4/core/coverage_manager.py`（约 30 行修改）
