# Stock Loop 接口分类详表（修正版）

**日期**: 2026-02-12  
**版本**: v2.0（已根据 Tushare 文档和配置文件验证修正）

---

## 一、类型 A：交易日历接口（按交易日存储）

这些接口按实际交易日存储数据，支持 `start_date` 和 `end_date` 参数进行范围查询。

| 接口 | 查询参数 | 数据日期字段 | `is_date_anchor` | 配置文件 |
|------|---------|-------------|-----------------|----------|
| `cyq_chips` | `start_date`, `end_date` | `trade_date` | `false` | cyq_chips.yaml |
| `moneyflow_dc` | `start_date`, `end_date` | `trade_date` | `false` | moneyflow_dc.yaml |
| `stk_factor_pro` | `start_date`, `end_date` | `trade_date` | `false` | stk_factor_pro.yaml |

**缺口检测方式**: 使用交易日历，检测缺失的交易日

**参数生成**:
```python
{'ts_code': '000001.SZ', 'start_date': '20250101', 'end_date': '20250115'}
```

---

## 二、类型 B：报告期接口（支持范围查询）

这些接口按财务报告期存储数据，支持 `start_date` 和 `end_date` 参数进行范围查询。

| 接口 | 查询参数 | 数据日期字段 | `is_date_anchor` | 配置文件 |
|------|---------|-------------|-----------------|----------|
| `income_vip` | `start_date`, `end_date` | `end_date` | `false` | income_vip.yaml |
| `balancesheet_vip` | `start_date`, `end_date` | `end_date` | `false` | balancesheet_vip.yaml |
| `cashflow_vip` | `start_date`, `end_date` | `end_date` | `false` | cashflow_vip.yaml |
| `fina_indicator_vip` | `start_date`, `end_date` | `end_date` | `false` | fina_indicator_vip.yaml |
| `fina_audit` | `start_date`, `end_date` | `end_date` | `false` | fina_audit.yaml |
| `fina_mainbz_vip` | `start_date`, `end_date` | `end_date` | `false` | fina_mainbz_vip.yaml |
| `forecast_vip` | `start_date`, `end_date` | `end_date` | `false` | forecast_vip.yaml |
| `top10_floatholders` | `start_date`, `end_date` | `end_date` | `false` | top10_floatholders.yaml |

> ⚠️ **修正**: `top10_floatholders` 原分类为类型 C，经验证支持范围查询，改为类型 B

**缺口检测方式**: 使用报告期列表（0331、0630、0930、1231），检测缺失的报告期

**参数生成**:
```python
{'ts_code': '000001.SZ', 'start_date': '20200101', 'end_date': '20260212'}
```

---

## 三、类型 C：日期锚定接口（不支持范围查询）

这些接口不支持 `start_date`/`end_date` 范围查询，而是通过特定的日期锚定参数进行单次查询。

| 接口 | 查询参数 | 数据日期字段 | 锚定参数 | `is_date_anchor` | 配置文件 |
|------|---------|-------------|----------|-----------------|----------|
| `disclosure_date` | `end_date` (单个) | `end_date` | `end_date` | `true` | disclosure_date.yaml |
| `top10_holders` | `period` (单个) | `end_date` | `period` | `true` | top10_holders.yaml |
| `dividend` | `ann_date` (单个) | `ann_date` | `ann_date` | `true` | dividend.yaml |
| `pledge_stat` | `end_date` (单个) | `end_date` | `end_date` | `true` | pledge_stat.yaml |
| `stk_rewards` | `end_date` (单个) | `end_date` | `end_date` | `true` | stk_rewards.yaml |

**缺口检测方式**: 遍历所有可能的锚点值，逐个查询缺失的

**参数生成**:
```python
# 每个缺失的锚点值生成一个查询任务
{'ts_code': '000001.SZ', 'end_date': '20231231'}
{'ts_code': '000001.SZ', 'end_date': '20240630'}
...
```

---

## 四、类型 D：无日期过滤接口（新增）

这些接口不支持任何日期参数过滤，只能按股票代码获取全部历史数据。

| 接口 | 查询参数 | 数据日期字段 | 特点 | 配置文件 |
|------|---------|-------------|------|----------|
| `pledge_detail` | `ts_code` (仅此一个) | `ann_date` (返回数据中) | 返回该股票所有质押明细 | pledge_detail.yaml |

> ⚠️ **新增**: `pledge_detail` 无日期过滤参数，不适用增量下载策略

**缺口检测方式**: 不适用（每次都获取全量数据）

**参数生成**:
```python
{'ts_code': '000001.SZ'}  # 只能传入股票代码
```

---

## 五、分类判断逻辑

```python
def _determine_gap_mode(interface_config: Dict[str, Any]) -> str:
    """
    判断接口的缺口检测模式
    
    Returns:
        'trade_date'   - 类型 A：交易日历模式
        'report_period' - 类型 B：报告期模式
        'date_anchor'   - 类型 C：日期锚定模式
        'no_date_filter' - 类型 D：无日期过滤模式
    """
    parameters = interface_config.get('parameters', {})
    detection_config = interface_config.get('duplicate_detection', {})
    
    # 1. 检查是否有日期锚定参数（类型 C）
    for param_name, param_def in parameters.items():
        if param_def.get('is_date_anchor', False):
            return 'date_anchor'
    
    # 2. 检查是否无日期过滤参数（类型 D）
    has_date_param = any(
        p in parameters 
        for p in ['start_date', 'end_date', 'trade_date', 'period', 'ann_date']
    )
    if not has_date_param:
        return 'no_date_filter'
    
    # 3. 根据 date_column 判断类型 A 或 B
    date_column = detection_config.get('date_column', 'trade_date')
    
    if date_column == 'trade_date':
        return 'trade_date'      # 类型 A
    else:
        return 'report_period'   # 类型 B
```

---

## 六、各类型缺口检测策略

### 6.1 类型 A（交易日历）
```python
def _detect_trade_date_gaps(interface_name, ts_code, start_date, end_date, date_column):
    existing_dates = get_stock_existing_dates(interface_name, ts_code, date_column)
    trade_days = get_trade_calendar(start_date, end_date)
    missing_days = [d for d in trade_days if d not in existing_dates]
    ranges = merge_to_ranges(missing_days)
    return [{'ts_code': ts_code, 'start_date': r[0], 'end_date': r[1]} for r in ranges]
```

### 6.2 类型 B（报告期）
```python
def _detect_report_period_gaps(interface_name, ts_code, start_date, end_date, date_column):
    existing_dates = get_stock_existing_dates(interface_name, ts_code, date_column)
    expected_periods = generate_report_periods(start_date, end_date)  # 0331, 0630, 0930, 1231
    missing_periods = [p for p in expected_periods if p not in existing_dates]
    
    if not missing_periods:
        return []
    
    # 类型 B 支持范围查询，返回整个范围
    return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
```

### 6.3 类型 C（日期锚定）
```python
def _detect_date_anchor_gaps(interface_name, ts_code, start_date, end_date, date_column, anchor_param):
    existing_dates = get_stock_existing_dates(interface_name, ts_code, date_column)
    anchor_values = generate_anchor_values(start_date, end_date, anchor_param)
    missing_anchors = [a for a in anchor_values if a not in existing_dates]
    
    # 类型 C 需要逐个锚点值查询
    return [{'ts_code': ts_code, anchor_param: anchor} for anchor in missing_anchors]
```

### 6.4 类型 D（无日期过滤）
```python
def _detect_no_date_filter_gaps(interface_name, ts_code):
    # 类型 D 每次都获取全量数据，无法增量
    # 检查是否有任何数据
    existing_dates = get_stock_existing_dates(interface_name, ts_code, 'ann_date')
    
    if existing_dates:
        return []  # 已有数据，跳过
    else:
        return [{'ts_code': ts_code}]  # 无数据，获取全量
```

---

## 七、修正说明

| 接口 | 原分类 | 修正后 | 修正原因 |
|------|-------|--------|---------|
| `top10_floatholders` | 类型 C | **类型 B** | 配置中 `is_date_anchor: false`，Tushare 文档确认支持 `start_date/end_date` 范围查询 |
| `pledge_detail` | 类型 C | **类型 D** | 无任何日期参数，只能按 `ts_code` 获取全量数据 |

---

## 八、总结

| 类型 | 接口数量 | 特点 | 缺口检测 |
|------|---------|------|---------|
| A: 交易日历 | 3 | `trade_date` + 范围查询 | 交易日历 |
| B: 报告期 | 8 | `end_date` + 范围查询 | 报告期列表 |
| C: 日期锚定 | 5 | 单个锚定参数 | 遍历锚点值 |
| D: 无日期过滤 | 1 | 仅 `ts_code` | 全量获取 |
