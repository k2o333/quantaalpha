# Stock Loop 模式智能增量下载方案 - 最终整合版 v4

**版本**: v4.0  
**日期**: 2026-02-12  
**状态**: 已根据 Tushare 文档和实际配置验证修正

---

## 一、接口分类详表

根据 Tushare 文档和配置文件分析，stock_loop 模式接口分为四类：

### 类型 A：交易日历接口（按交易日存储）

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

### 类型 B：报告期接口（支持范围查询）

这些接口按财务报告期存储数据，**同时拥有 `start_date` 和 `end_date` 参数**，支持范围查询。

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

**缺口检测方式**: 使用报告期列表（0331、0630、0930、1231），检测缺失的报告期

**参数生成**:
```python
{'ts_code': '000001.SZ', 'start_date': '20200101', 'end_date': '20260212'}
```

---

### 类型 C：日期锚定接口（不支持范围查询）

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
```

---

### 类型 D：无日期过滤接口

这些接口不支持任何日期参数过滤，只能按股票代码获取全部历史数据。

| 接口 | 查询参数 | 数据日期字段 | 特点 | 配置文件 |
|------|---------|-------------|------|----------|
| `pledge_detail` | `ts_code` (仅此一个) | `ann_date` (返回数据中) | 返回该股票所有质押明细 | pledge_detail.yaml |

**缺口检测方式**: 不适用（每次都获取全量数据）

**参数生成**:
```python
{'ts_code': '000001.SZ'}  # 只能传入股票代码
```

---

## 二、接口类型判断逻辑

### 2.1 判断流程图

```
                    接口配置
                       │
                       ▼
            ┌─────────────────────────┐
            │ 是否有参数标记          │
            │ is_date_anchor = true   │
            └─────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │ Yes                   │ No
           ▼                       ▼
      ┌─────────┐        ┌─────────────────────────┐
      │ 类型 C  │        │ 是否有 start_date 和    │
      │日期锚定 │        │ end_date 参数           │
      └─────────┘        └─────────────────────────┘
                                  │
                     ┌────────────┴────────────┐
                     │ Yes                     │ No
                     ▼                         ▼
           ┌─────────────────┐        ┌─────────────────────────┐
           │ 根据 date_column│        │ 是否有任何日期参数      │
           │ 区分类型 A 或 B │        └─────────────────────────┘
           └─────────────────┘                  │
                     │                ┌─────────┴─────────┐
          ┌──────────┴──────────┐    │ Yes               │ No
          │ trade_date          │    ▼                   ▼
          ▼                     ▼   类型 A/B        ┌─────────┐
     ┌─────────┐          ┌─────────┐              │ 类型 D  │
     │ 类型 A  │          │ 类型 B  │              │无日期过滤│
     │交易日历 │          │ 报告期  │              └─────────┘
     └─────────┘          └─────────┘
```

### 2.2 类型 B 判断逻辑

类型 B 接口有两个关键特征：

1. **同时拥有 `start_date` 和 `end_date` 参数**
2. **没有参数标记为 `is_date_anchor: true`**（即不属于类型 C）

> **注意**：判断顺序很重要。先排除类型 C（有 `is_date_anchor: true`），剩下的有 `start_date` + `end_date` 的接口就是类型 A 或 B。

```python
def _is_type_b(interface_config: Dict[str, Any]) -> bool:
    """
    判断是否为类型 B（报告期范围查询接口）
    
    前提：已确认不是类型 C（没有 is_date_anchor=true）
    
    类型 B 特征：
    1. 有 start_date 参数
    2. 有 end_date 参数
    3. date_column 不是 'trade_date'
    
    Returns:
        True 表示是类型 B
    """
    parameters = interface_config.get('parameters', {})
    date_column = interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')
    
    has_start = 'start_date' in parameters
    has_end = 'end_date' in parameters
    
    # 有 start_date + end_date，且 date_column 不是 trade_date
    return has_start and has_end and date_column != 'trade_date'
```

### 2.3 完整类型判断逻辑

```python
def _determine_gap_mode(self, interface_config: Dict[str, Any]) -> str:
    """
    判断接口的缺口检测模式
    
    判断顺序：
    1. 有 is_date_anchor=true → 类型 C
    2. 有 start_date + end_date → 类型 A 或 B（根据 date_column 区分）
    3. 无任何日期参数 → 类型 D
    4. 其他情况 → 根据 date_column 判断
    
    Returns:
        'trade_date'    - 类型 A：交易日历模式
        'report_period' - 类型 B：报告期模式
        'date_anchor'   - 类型 C：日期锚定模式
        'no_date_filter' - 类型 D：无日期过滤模式
    """
    parameters = interface_config.get('parameters', {})
    detection_config = interface_config.get('duplicate_detection', {})
    date_column = detection_config.get('date_column', 'trade_date')
    
    # 1. 检查是否有日期锚定参数（类型 C）
    if any(p.get('is_date_anchor', False) for p in parameters.values()):
        return 'date_anchor'
    
    # 2. 检查是否有 start_date 和 end_date 参数（类型 A 或 B）
    #    既然第1步已确认没有 is_date_anchor=true，这里必然是类型 A 或 B
    if 'start_date' in parameters and 'end_date' in parameters:
        return 'trade_date' if date_column == 'trade_date' else 'report_period'
    
    # 3. 检查是否有任何日期参数
    has_date_param = any(
        p in parameters 
        for p in ['start_date', 'end_date', 'trade_date', 'period', 'ann_date']
    )
    
    if not has_date_param:
        return 'no_date_filter'  # 类型 D
    
    # 4. 有日期参数但没有 start_date + end_date，根据 date_column 判断
    return 'trade_date' if date_column == 'trade_date' else 'report_period'
```

---

## 三、核心实现

### 3.1 扩展 CoverageManager

在 `/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py` 中添加：

```python
# ============================================================================
# 股票级别日期缺口检测（新增功能）
# ============================================================================

def get_stock_existing_dates(
    self,
    interface_name: str,
    ts_code: str,
    date_column: str = 'trade_date'
) -> Set[str]:
    """
    获取指定股票已存在的所有日期
    
    Args:
        interface_name: 接口名称
        ts_code: 股票代码
        date_column: 日期列名
        
    Returns:
        已存在的日期集合（YYYYMMDD格式）
    """
    cache_key = f"{interface_name}:{ts_code}:dates"
    
    with self._cache_lock:
        if cache_key in self._cache:
            return self._cache[cache_key]
    
    try:
        df = self.storage_manager.read_interface_data(
            interface_name,
            columns=[date_column, 'ts_code']
        )
        
        if df.is_empty():
            return set()
        
        import polars as pl
        filtered = df.filter(pl.col('ts_code') == ts_code)
        
        if filtered.is_empty():
            return set()
        
        dates = set()
        for date_val in filtered[date_column]:
            formatted = format_date(date_val)
            if formatted:
                dates.add(formatted)
        
        with self._cache_lock:
            self._cache[cache_key] = dates
        
        logger.debug(f"[{interface_name}/{ts_code}] 已有 {len(dates)} 条数据")
        return dates
        
    except Exception as e:
        logger.warning(f"获取 {interface_name}/{ts_code} 的现有日期失败: {e}")
        return set()


def detect_stock_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    interface_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    检测指定股票的数据缺口（统一入口）
    
    根据接口配置自动选择检测方式：
    - 类型 A：交易日历检测
    - 类型 B：报告期检测
    - 类型 C：日期锚定遍历
    - 类型 D：无日期过滤
    
    Args:
        interface_name: 接口名称
        ts_code: 股票代码
        start_date: 起始日期
        end_date: 结束日期
        interface_config: 接口配置
        
    Returns:
        下载任务参数列表
    """
    detection_config = interface_config.get('duplicate_detection', {})
    date_column = detection_config.get('date_column', 'trade_date')
    
    # 判断接口类型
    gap_mode = self._determine_gap_mode(interface_config)
    logger.info(f"[{interface_name}/{ts_code}] 缺口检测模式: {gap_mode}")
    
    if gap_mode == 'trade_date':
        # 类型 A：交易日历检测
        return self._detect_trade_date_gaps(
            interface_name, ts_code, start_date, end_date, date_column
        )
    elif gap_mode == 'report_period':
        # 类型 B：报告期检测
        return self._detect_report_period_gaps(
            interface_name, ts_code, start_date, end_date, date_column
        )
    elif gap_mode == 'date_anchor':
        # 类型 C：日期锚定遍历
        return self._detect_date_anchor_gaps(
            interface_name, ts_code, start_date, end_date, date_column, interface_config
        )
    elif gap_mode == 'no_date_filter':
        # 类型 D：无日期过滤
        return self._detect_no_date_filter_gaps(
            interface_name, ts_code, date_column
        )
    else:
        # 未知类型，返回完整范围
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]


def _determine_gap_mode(self, interface_config: Dict[str, Any]) -> str:
    """
    判断接口的缺口检测模式
    
    判断顺序：
    1. 有 is_date_anchor=true → 类型 C
    2. 有 start_date + end_date → 类型 A 或 B（根据 date_column 区分）
    3. 无任何日期参数 → 类型 D
    4. 其他情况 → 根据 date_column 判断
    
    Returns:
        'trade_date'    - 类型 A：交易日历模式
        'report_period' - 类型 B：报告期模式
        'date_anchor'   - 类型 C：日期锚定模式
        'no_date_filter' - 类型 D：无日期过滤模式
    """
    parameters = interface_config.get('parameters', {})
    detection_config = interface_config.get('duplicate_detection', {})
    date_column = detection_config.get('date_column', 'trade_date')
    
    # 1. 检查是否有日期锚定参数（类型 C）
    if any(p.get('is_date_anchor', False) for p in parameters.values()):
        return 'date_anchor'
    
    # 2. 检查是否有 start_date 和 end_date 参数（类型 A 或 B）
    #    既然第1步已确认没有 is_date_anchor=true，这里必然是类型 A 或 B
    if 'start_date' in parameters and 'end_date' in parameters:
        return 'trade_date' if date_column == 'trade_date' else 'report_period'
    
    # 3. 检查是否有任何日期参数
    has_date_param = any(
        p in parameters 
        for p in ['start_date', 'end_date', 'trade_date', 'period', 'ann_date']
    )
    
    if not has_date_param:
        return 'no_date_filter'  # 类型 D
    
    # 4. 有日期参数但没有 start_date + end_date，根据 date_column 判断
    return 'trade_date' if date_column == 'trade_date' else 'report_period'


def _detect_trade_date_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    date_column: str
) -> List[Dict[str, Any]]:
    """
    类型 A：交易日历缺口检测
    
    适用于：cyq_chips, moneyflow_dc, stk_factor_pro
    """
    logger.info(f"[{interface_name}/{ts_code}] 交易日历缺口检测 ({start_date} ~ {end_date})")
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    
    if not existing_dates:
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    if not self.downloader:
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
    if not trade_calendar:
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    trade_days = [
        d['cal_date'] for d in trade_calendar 
        if d.get('is_open', 0) == 1 and start_date <= d['cal_date'] <= end_date
    ]
    
    missing_days = [d for d in trade_days if d not in existing_dates]
    
    if not missing_days:
        logger.info(f"[{ts_code}] 交易日数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_days)} 个交易日")
    
    ranges = self._merge_dates_to_ranges(missing_days)
    
    return [
        {'ts_code': ts_code, 'start_date': r[0], 'end_date': r[1]}
        for r in ranges
    ]


def _detect_report_period_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    date_column: str
) -> List[Dict[str, Any]]:
    """
    类型 B：报告期缺口检测
    
    适用于：income_vip, balancesheet_vip, cashflow_vip 等
    """
    logger.info(f"[{interface_name}/{ts_code}] 报告期缺口检测 ({start_date} ~ {end_date})")
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    expected_periods = self._generate_report_periods(start_date, end_date)
    
    if not existing_dates:
        logger.info(f"[{ts_code}] 无现有数据，需要下载 {len(expected_periods)} 个报告期")
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    missing_periods = [p for p in expected_periods if p not in existing_dates]
    
    if not missing_periods:
        logger.info(f"[{ts_code}] 报告期数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_periods)} 个报告期: {missing_periods}")
    
    return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]


def _detect_date_anchor_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    date_column: str,
    interface_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    类型 C：日期锚定缺口检测
    
    适用于：disclosure_date, top10_holders, dividend 等
    """
    logger.info(f"[{interface_name}/{ts_code}] 日期锚定缺口检测 ({start_date} ~ {end_date})")
    
    parameters = interface_config.get('parameters', {})
    anchor_param = None
    for param_name, param_def in parameters.items():
        if param_def.get('is_date_anchor', False):
            anchor_param = param_name
            break
    
    if not anchor_param:
        logger.warning(f"[{interface_name}] 未找到日期锚定参数")
        return [{'ts_code': ts_code}]
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    anchor_values = self._generate_anchor_values(start_date, end_date, anchor_param)
    
    missing_anchors = [a for a in anchor_values if a not in existing_dates]
    
    if not missing_anchors:
        logger.info(f"[{ts_code}] 锚点数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_anchors)} 个锚点值")
    
    return [
        {'ts_code': ts_code, anchor_param: anchor}
        for anchor in missing_anchors
    ]


def _detect_no_date_filter_gaps(
    self,
    interface_name: str,
    ts_code: str,
    date_column: str
) -> List[Dict[str, Any]]:
    """
    类型 D：无日期过滤缺口检测
    
    适用于：pledge_detail
    """
    logger.info(f"[{interface_name}/{ts_code}] 无日期过滤模式")
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    
    if existing_dates:
        logger.info(f"[{ts_code}] 已有数据，跳过")
        return []
    
    logger.info(f"[{ts_code}] 无数据，需要获取全量")
    return [{'ts_code': ts_code}]


def _generate_report_periods(self, start_date: str, end_date: str) -> List[str]:
    """生成报告期列表（季度末）"""
    periods = []
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    quarter_ends = ['0331', '0630', '0930', '1231']
    
    for year in range(start_year - 1, end_year + 2):
        for qe in quarter_ends:
            period = f"{year}{qe}"
            if start_date <= period <= end_date:
                periods.append(period)
    
    return sorted(periods)


def _generate_anchor_values(
    self,
    start_date: str,
    end_date: str,
    anchor_param: str
) -> List[str]:
    """生成锚点值列表"""
    if anchor_param in ['end_date', 'period']:
        return self._generate_report_periods(start_date, end_date)
    
    return self._generate_report_periods(start_date, end_date)


def _merge_dates_to_ranges(self, dates: List[str]) -> List[Tuple[str, str]]:
    """将日期列表合并为连续区间"""
    if not dates:
        return []
    
    sorted_dates = sorted(dates)
    ranges = []
    range_start = sorted_dates[0]
    range_end = sorted_dates[0]
    
    for i in range(1, len(sorted_dates)):
        curr = sorted_dates[i]
        prev = sorted_dates[i-1]
        
        from datetime import datetime
        curr_dt = datetime.strptime(curr, '%Y%m%d')
        prev_dt = datetime.strptime(prev, '%Y%m%d')
        
        if (curr_dt - prev_dt).days <= 3:
            range_end = curr
        else:
            ranges.append((range_start, range_end))
            range_start = curr
            range_end = curr
    
    ranges.append((range_start, range_end))
    return ranges
```

### 3.2 修改 PaginationComposer

在 `/home/quan/testdata/aspipe_v4/app4/core/pagination.py` 中修改：

```python
def _apply_stock_loop(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    应用股票循环维度 - 增强版（支持四种缺口检测模式）
    """
    stock_list = self.context.stock_list
    if not stock_list:
        logger.error("Stock list not provided")
        return
    
    stock_loop_config = self.config.get('stock_loop', {})
    skip_existing = stock_loop_config.get('skip_existing', False)
    
    detection_config = self.interface_config.get('duplicate_detection', {})
    stock_level_detection = detection_config.get('stock_level_detection', False)
    
    for params in params_stream:
        for stock in stock_list:
            ts_code = stock.get('ts_code')
            if not ts_code:
                continue
            
            # === 股票级别缺口检测 ===
            if stock_level_detection and self.context.coverage_manager and not self.context.force_download:
                start_date = params.get('start_date', '20000101')
                end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
                
                gap_tasks = self.context.coverage_manager.detect_stock_gaps(
                    self.interface_config.get('api_name', ''),
                    ts_code,
                    start_date,
                    end_date,
                    self.interface_config
                )
                
                if not gap_tasks:
                    logger.debug(f"Skipping {ts_code}, data already complete")
                    continue
                
                for gap_params in gap_tasks:
                    task_params = params.copy()
                    task_params.update(gap_params)
                    task_params['_stock_info'] = stock
                    task_params['_gap_fill'] = True
                    yield task_params
                
                continue
            
            # === 原有逻辑 ===
            if skip_existing and not self.context.force_download:
                if self._stock_data_exists(ts_code):
                    continue
            
            stock_params = params.copy()
            stock_params['ts_code'] = ts_code
            stock_params['_stock_info'] = stock
            yield stock_params
```

---

## 四、配置设计

### 4.1 类型 A：交易日历接口

```yaml
# cyq_chips.yaml
api_name: cyq_chips

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop
```

### 4.2 类型 B：报告期接口

```yaml
# income_vip.yaml
api_name: income_vip

duplicate_detection:
  enabled: true
  date_column: "end_date"
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop

parameters:
  start_date:
    is_date_anchor: false
  end_date:
    is_date_anchor: false
```

### 4.3 类型 C：日期锚定接口

```yaml
# disclosure_date.yaml
api_name: disclosure_date

duplicate_detection:
  enabled: true
  date_column: "end_date"
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop

parameters:
  end_date:
    is_date_anchor: true
```

### 4.4 类型 D：无日期过滤接口

```yaml
# pledge_detail.yaml
api_name: pledge_detail

duplicate_detection:
  enabled: true
  date_column: "ann_date"
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop

parameters:
  ts_code:
    required: true
  # 无日期参数
```

---

## 五、执行流程对比

| 类型 | 接口示例 | 缺口检测 | 参数生成 |
|------|---------|---------|---------|
| A | cyq_chips | 交易日历 | `{'ts_code', 'start_date', 'end_date'}` |
| B | income_vip | 报告期列表 | `{'ts_code', 'start_date', 'end_date'}` |
| C | disclosure_date | 遍历锚点值 | `{'ts_code', 'end_date'}` (多个) |
| D | pledge_detail | 无 | `{'ts_code'}` |

---

## 六、总结

### 接口分类统计

| 类型 | 数量 | 接口列表 |
|------|------|---------|
| A: 交易日历 | 3 | `cyq_chips`, `moneyflow_dc`, `stk_factor_pro` |
| B: 报告期 | 8 | `income_vip`, `balancesheet_vip`, `cashflow_vip`, `fina_indicator_vip`, `fina_audit`, `fina_mainbz_vip`, `forecast_vip`, `top10_floatholders` |
| C: 日期锚定 | 5 | `disclosure_date`, `top10_holders`, `dividend`, `pledge_stat`, `stk_rewards` |
| D: 无日期过滤 | 1 | `pledge_detail` |

### 类型判断逻辑

```python
# 判断顺序（重要！）：
# 1. 有 is_date_anchor=true → 类型 C
# 2. 有 start_date + end_date → 类型 A 或 B（根据 date_column 区分）
# 3. 无任何日期参数 → 类型 D
# 4. 其他情况 → 根据 date_column 判断

parameters = interface_config.get('parameters', {})
date_column = interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')

# 1. 检查锚定参数
if any(p.get('is_date_anchor', False) for p in parameters.values()):
    return 'date_anchor'  # 类型 C

# 2. 有 start_date + end_date → 类型 A 或 B
if 'start_date' in parameters and 'end_date' in parameters:
    return 'trade_date' if date_column == 'trade_date' else 'report_period'

# 3. 无日期参数 → 类型 D
if not any(p in parameters for p in ['start_date', 'end_date', 'trade_date', 'period', 'ann_date']):
    return 'no_date_filter'

# 4. 其他情况
return 'trade_date' if date_column == 'trade_date' else 'report_period'
```
