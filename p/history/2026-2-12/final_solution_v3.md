# Stock Loop 模式智能增量下载方案 - 最终整合版 v3

**版本**: v3.0  
**日期**: 2026-02-12  
**状态**: 已根据 Tushare 文档和实际配置修正

---

## 一、接口分类分析

根据 Tushare 文档和配置文件分析，stock_loop 模式接口分为三类：

### 类型 A：交易日历接口

| 接口 | 查询参数 | 数据日期字段 | 特点 |
|------|---------|-------------|------|
| `cyq_chips` | `start_date`, `end_date` | `trade_date` | 按交易日存储 |
| `moneyflow_dc` | `start_date`, `end_date` | `trade_date` | 按交易日存储 |

**缺口检测方式**：使用交易日历，检测缺失的交易日

### 类型 B：报告期接口（财报类）

| 接口 | 查询参数 | 数据日期字段 | 特点 |
|------|---------|-------------|------|
| `income_vip` | `start_date`, `end_date` | `end_date` | 按报告期存储（季末） |
| `balancesheet_vip` | `start_date`, `end_date` | `end_date` | 按报告期存储 |
| `cashflow_vip` | `start_date`, `end_date` | `end_date` | 按报告期存储 |
| `fina_indicator_vip` | `start_date`, `end_date` | `end_date` | 按报告期存储 |

**缺口检测方式**：使用报告期列表（0331、0630、0930、1231），检测缺失的报告期

### 类型 C：日期锚定接口（不支持范围查询）

| 接口 | 查询参数 | 数据日期字段 | 特点 |
|------|---------|-------------|------|
| `disclosure_date` | `end_date` (单个) | `end_date` | 只能按单个报告期查询 |
| `top10_holders` | `period` (单个) | `end_date` | 只能按单个报告期查询 |
| `dividend` | `ann_date` (单个) | `ann_date` | 只能按单个公告日期查询 |

**缺口检测方式**：遍历所有可能的锚点值，逐个查询缺失的

---

## 二、核心实现

### 2.1 扩展 CoverageManager

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
    
    if gap_mode == 'trade_date':
        # 类型 A：交易日历检测
        return self._detect_trade_date_gaps(
            interface_name, ts_code, start_date, end_date, date_column
        )
    elif gap_mode == 'report_period':
        # 类型 B：报告期检测
        return self._detect_report_period_gaps(
            interface_name, ts_code, start_date, end_date, date_column, interface_config
        )
    elif gap_mode == 'date_anchor':
        # 类型 C：日期锚定遍历
        return self._detect_date_anchor_gaps(
            interface_name, ts_code, start_date, end_date, date_column, interface_config
        )
    else:
        # 未知类型，返回完整范围
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]


def _determine_gap_mode(self, interface_config: Dict[str, Any]) -> str:
    """
    判断接口的缺口检测模式
    
    Returns:
        'trade_date' - 交易日历模式
        'report_period' - 报告期模式
        'date_anchor' - 日期锚定模式
    """
    detection_config = interface_config.get('duplicate_detection', {})
    pagination_config = interface_config.get('pagination', {})
    parameters = interface_config.get('parameters', {})
    
    # 1. 检查是否有日期锚定参数
    for param_name, param_def in parameters.items():
        if param_def.get('is_date_anchor', False):
            return 'date_anchor'
    
    # 2. 检查 date_column 或数据特征
    date_column = detection_config.get('date_column', 'trade_date')
    
    if date_column == 'trade_date':
        return 'trade_date'
    elif date_column in ['end_date', 'period']:
        return 'report_period'
    
    # 3. 默认使用交易日历
    return 'trade_date'


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
    
    适用于：cyq_chips, moneyflow_dc 等按交易日存储的接口
    """
    logger.info(f"[{interface_name}/{ts_code}] 交易日历缺口检测 ({start_date} ~ {end_date})")
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    
    if not existing_dates:
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    # 获取交易日历
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
    
    # 合并为连续区间
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
    date_column: str,
    interface_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    类型 B：报告期缺口检测
    
    适用于：income_vip, balancesheet_vip 等财报类接口
    报告期为季度末：0331, 0630, 0930, 1231
    """
    logger.info(f"[{interface_name}/{ts_code}] 报告期缺口检测 ({start_date} ~ {end_date})")
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    
    # 生成期望的报告期列表
    expected_periods = self._generate_report_periods(start_date, end_date)
    
    if not existing_dates:
        logger.info(f"[{ts_code}] 无现有数据，需要下载 {len(expected_periods)} 个报告期")
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    # 找出缺失的报告期
    missing_periods = [p for p in expected_periods if p not in existing_dates]
    
    if not missing_periods:
        logger.info(f"[{ts_code}] 报告期数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_periods)} 个报告期: {missing_periods}")
    
    # 财报接口支持 start_date/end_date 范围查询，返回一个范围即可
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
    
    适用于：disclosure_date, top10_holders 等不支持范围查询的接口
    需要遍历所有可能的锚点值，逐个查询
    """
    logger.info(f"[{interface_name}/{ts_code}] 日期锚定缺口检测 ({start_date} ~ {end_date})")
    
    # 找到锚定参数
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
    
    # 生成需要遍历的锚点值列表
    anchor_values = self._generate_anchor_values(
        interface_name, start_date, end_date, anchor_param
    )
    
    # 找出缺失的锚点值
    missing_anchors = [a for a in anchor_values if a not in existing_dates]
    
    if not missing_anchors:
        logger.info(f"[{ts_code}] 锚点数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_anchors)} 个锚点值")
    
    # 每个缺失的锚点值生成一个查询任务
    return [
        {'ts_code': ts_code, anchor_param: anchor}
        for anchor in missing_anchors
    ]


def _generate_report_periods(self, start_date: str, end_date: str) -> List[str]:
    """
    生成报告期列表（季度末）
    
    Returns:
        ['20230331', '20230630', '20230930', '20231231', ...]
    """
    periods = []
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    quarter_ends = ['0331', '0630', '0930', '1231']
    
    for year in range(start_year - 1, end_year + 2):  # 扩大范围确保覆盖
        for qe in quarter_ends:
            period = f"{year}{qe}"
            if start_date <= period <= end_date:
                periods.append(period)
    
    return sorted(periods)


def _generate_anchor_values(
    self,
    interface_name: str,
    start_date: str,
    end_date: str,
    anchor_param: str
) -> List[str]:
    """
    生成锚点值列表
    
    根据锚点参数类型生成不同的值列表
    """
    # 对于 end_date 或 period，生成报告期列表
    if anchor_param in ['end_date', 'period']:
        return self._generate_report_periods(start_date, end_date)
    
    # 对于 ann_date，可能需要生成日期范围
    # 这里简化处理，返回报告期
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

### 2.2 修改 PaginationComposer

在 `/home/quan/testdata/aspipe_v4/app4/core/pagination.py` 中修改：

```python
def _apply_stock_loop(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    应用股票循环维度 - 增强版（支持三种缺口检测模式）
    """
    stock_list = self.context.stock_list
    if not stock_list:
        logger.error("Stock list not provided")
        return
    
    stock_loop_config = self.config.get('stock_loop', {})
    skip_existing = stock_loop_config.get('skip_existing', False)
    
    # 股票级别缺口检测配置
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
                
                # 统一缺口检测入口
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
                
                # 为每个缺口生成参数
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

## 三、配置设计

### 3.1 类型 A：交易日历接口

```yaml
# cyq_chips.yaml
api_name: cyq_chips

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  # 新增
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop
```

### 3.2 类型 B：报告期接口

```yaml
# income_vip.yaml
api_name: income_vip

duplicate_detection:
  enabled: true
  date_column: "end_date"          # 报告期字段
  key_column: "period"
  # 新增
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop
```

### 3.3 类型 C：日期锚定接口

```yaml
# disclosure_date.yaml
api_name: disclosure_date

duplicate_detection:
  enabled: true
  date_column: "end_date"
  key_columns: [ts_code, end_date]
  # 新增
  stock_level_detection: true

pagination:
  enabled: true
  mode: stock_loop
  date_anchor:
    reverse: true

parameters:
  end_date:
    is_date_anchor: true           # 标记为锚定参数
```

---

## 四、执行流程对比

### 类型 A（交易日历）

```
cyq_chips, moneyflow_dc

检测缺口 → 获取交易日历 → 对比已有日期 → 合并连续缺口 → 生成范围参数
                                    ↓
                        {'ts_code': '000001.SZ', 'start_date': '20250101', 'end_date': '20250115'}
```

### 类型 B（报告期）

```
income_vip, balancesheet_vip

检测缺口 → 生成报告期列表 → 对比已有报告期 → 返回范围参数
                                    ↓
                        {'ts_code': '000001.SZ', 'start_date': '20200101', 'end_date': '20260212'}
```

### 类型 C（日期锚定）

```
disclosure_date, top10_holders

检测缺口 → 生成锚点值列表 → 对比已有锚点 → 逐个生成查询参数
                                    ↓
                        {'ts_code': '000001.SZ', 'end_date': '20231231'}
                        {'ts_code': '000001.SZ', 'end_date': '20240630'}
                        ...
```

---

## 五、总结

### 修正内容

| 原方案问题 | 修正方案 |
|-----------|---------|
| 所有接口使用交易日历 | 根据接口类型选择检测方式 |
| 财报接口误用交易日 | 使用报告期列表（0331/0630/0930/1231） |
| 锚定接口生成范围参数 | 逐个锚点值生成查询参数 |

### 接口类型判断逻辑

```python
def _determine_gap_mode(interface_config):
    # 1. 检查 is_date_anchor 参数
    for param in parameters:
        if param.is_date_anchor:
            return 'date_anchor'
    
    # 2. 根据 date_column 判断
    if date_column == 'trade_date':
        return 'trade_date'
    elif date_column in ['end_date', 'period']:
        return 'report_period'
```

### 适用范围

| 类型 | 接口 | 缺口检测方式 |
|------|------|-------------|
| A | cyq_chips, moneyflow_dc | 交易日历 |
| B | income_vip, balancesheet_vip, cashflow_vip, fina_indicator_vip | 报告期列表 |
| C | disclosure_date, top10_holders, dividend | 锚点遍历 |
