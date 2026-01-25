# 分页代码拆分方案（最终版）

## 背景分析

基于对 `/home/quan/testdata/aspipe_v4/app4/core/downloader.py` 的深入分析（1413行代码）。

### 当前分页代码统计（约837行，占比59%）

| 方法名 | 职责 |
|--------|------|
| `_execute_pagination` | 分页调度入口 |
| `_execute_offset_pagination` | Offset分页 |
| `_execute_date_range_pagination` | 日期范围分页（智能调度）|
| `_execute_date_range_pagination_concurrent` | 并发日期分页（核心）|
| `_make_request_with_offset_check` | 带offset检查的请求 |
| `_execute_stock_loop_pagination` | 股票循环分页 |
| `_execute_period_range_pagination` | 报告期范围分页 |
| `_execute_quarterly_pagination` | 季度周期分页 |
| `_execute_periodic_pagination` | 周期性时间分页 |
| `_generate_quarter_end_dates` | 生成季度末日期 |
| `_generate_quarterly_ranges` | 生成季度范围 |
| `_generate_time_ranges` | 生成时间范围 |
| `_get_window_size_for_interface` | 智能窗口大小 |
| `_is_stock_data_exists` | 股票数据存在检查 |

### 现有方案对比

| 特性 | 原方案（回调模式） | 改进方案（参数生成器） |
|------|-------------------|------------------------|
| **依赖关系** | ❌ 双向依赖（循环引用） | ✅ 单向依赖 |
| **职责分离** | ❌ PaginationManager仍执行请求 | ✅ 分页只生成参数 |
| **测试难度** | ❌ 需要mock回调函数 | ✅ 纯函数，易测试 |
| **调试复杂度** | ❌ 跨模块调用栈 | ✅ 线性调用栈 |

**结论**：采用**参数生成器模式**，并修正之前方案的问题。

---

## 设计哲学

```
分页模块（纯逻辑） → 生成请求参数迭代器
         ↓（单向依赖，无回调）
下载器（执行控制） → 遍历参数并执行请求
```

**核心原则**：
- **零回调**：分页模块不执行请求，只生成参数
- **单向依赖**：downloader 依赖 pagination，反之不依赖
- **职责清晰**：pagination = 参数生成器，downloader = 执行引擎
- **易于测试**：纯函数，无需mock

---

## 拆分后的架构

```
app4/core/
├── downloader.py          (~600行) - 执行控制
│   ├── download()                     # 主入口
│   ├── _execute_pagination()          # 分页调度（简化版）
│   ├── _execute_xxx_pagination()      # 6种分页执行方法
│   ├── _make_request()                # 请求执行
│   ├── _make_request_with_offset_check()  # 带offset检查
│   ├── get_trade_calendar()           # 交易日历
│   ├── _is_stock_data_exists()        # 股票数据检查（保留）
│   └── ...                            # 其他核心方法
│
└── pagination.py          (~500行) - 参数生成器
    ├── PaginationContext              # 分页上下文（dataclass）
    ├── ParameterGenerator             # 参数生成器类
    │   ├── generate_offset_params()   # 生成offset参数
    │   ├── generate_date_range_params() # 生成日期范围参数
    │   ├── generate_stock_params()    # 生成股票循环参数
    │   ├── generate_period_params()   # 生成报告期参数
    │   ├── generate_quarterly_params() # 生成季度参数
    │   └── generate_periodic_params() # 生成周期性参数
    └── Helper functions               # 辅助函数
        ├── generate_quarter_end_dates()
        ├── generate_quarterly_ranges()
        ├── generate_time_ranges()
        └── get_window_size_for_interface()
```

---

## 详细实现方案

### 1. 创建 `app4/core/pagination.py`

```python
"""
分页参数生成器 - 纯逻辑模块，不执行任何网络请求

职责：
- 根据分页策略生成请求参数迭代器
- 不持有任何外部引用
- 所有方法都是纯函数或生成器
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Iterator, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PaginationContext:
    """
    分页上下文 - 传递必要的配置和数据
    
    注意：这是一个数据容器，不持有外部服务引用
    """
    interface_config: Dict[str, Any]
    trade_calendar: Optional[List[Dict[str, Any]]] = None
    stock_list: Optional[List[Dict[str, Any]]] = None
    force_download: bool = False
    
    @property
    def interface_name(self) -> str:
        return self.interface_config.get('name', '')
    
    @property
    def pagination_config(self) -> Dict[str, Any]:
        return self.interface_config.get('pagination', {})


class ParameterGenerator:
    """
    请求参数生成器
    
    职责：根据分页策略生成请求参数迭代器
    不执行任何网络请求，只负责参数生成
    
    使用方式：
        context = PaginationContext(interface_config=config, trade_calendar=calendar)
        generator = ParameterGenerator(context)
        for params, identifier in generator.generate_date_range_params(base_params, start, end):
            result = downloader._make_request(config, params)
            # 处理结果...
    """

    def __init__(self, context: PaginationContext):
        """
        初始化参数生成器
        
        Args:
            context: 分页上下文，包含接口配置和必要数据
        """
        self.context = context

    # ==================== 参数生成方法 ====================

    def generate_offset_params(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        生成offset分页参数（无限生成器）
        
        注意：这是一个无限生成器，调用者需要根据返回数据判断是否继续
        
        Args:
            base_params: 基础请求参数
            
        Yields:
            每一页的请求参数
            
        Example:
            for page_params in generator.generate_offset_params(params):
                data = make_request(page_params)
                if not data or len(data) < limit:
                    break
        """
        offset = 0
        limit_key = self.context.pagination_config.get('limit_key', 'limit')
        offset_key = self.context.pagination_config.get('offset_key', 'offset')
        default_limit = self.context.pagination_config.get('default_limit', 5000)

        while True:
            page_params = base_params.copy()
            page_params[limit_key] = default_limit
            page_params[offset_key] = offset

            yield page_params

            offset += default_limit

    def generate_date_range_params(
        self,
        base_params: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> Iterator[Tuple[Dict[str, Any], Tuple[str, str]]]:
        """
        生成日期范围分页参数（基于交易日历的智能窗口）
        
        Args:
            base_params: 基础参数
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        
        Yields:
            (窗口参数, (window_start, window_end)) 元组
        """
        if not self.context.trade_calendar:
            logger.warning("Trade calendar not provided, yielding single request")
            yield base_params.copy(), (start_date, end_date)
            return

        # 过滤交易日
        trade_days = [
            day for day in self.context.trade_calendar
            if day.get('is_open', 0) == 1 and
               start_date <= day['cal_date'] <= end_date
        ]

        if not trade_days:
            logger.warning(f"No trade days found in range {start_date} - {end_date}")
            return

        # 排序
        trade_days.sort(key=lambda x: x['cal_date'])

        # 智能窗口大小
        window_size = get_window_size_for_interface(self.context.interface_name)

        logger.info(f"Generating windows for {len(trade_days)} trade days with window size {window_size}")

        # 生成分窗
        for i in range(0, len(trade_days), window_size):
            window_days = trade_days[i:i + window_size]
            if not window_days:
                continue

            window_start = window_days[0]['cal_date']
            window_end = window_days[-1]['cal_date']

            window_params = base_params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            yield window_params, (window_start, window_end)

    def generate_stock_params(
        self,
        base_params: Dict[str, Any],
        existing_stocks_checker: Optional[callable] = None
    ) -> Iterator[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        生成股票循环分页参数
        
        Args:
            base_params: 基础参数
            existing_stocks_checker: 可选的回调函数，用于检查股票数据是否存在
                                     签名: (interface_name: str, ts_code: str) -> bool
        
        Yields:
            (股票参数, 股票信息) 元组
        """
        if not self.context.stock_list:
            logger.error("Stock list not provided for stock loop pagination")
            return

        for stock in self.context.stock_list:
            ts_code = stock['ts_code']

            # 前置去重检查（如果提供了检查函数）
            if not self.context.force_download and existing_stocks_checker:
                if existing_stocks_checker(self.context.interface_name, ts_code):
                    logger.debug(f"Skipping stock {ts_code} (data exists)")
                    continue

            stock_params = base_params.copy()
            stock_params['ts_code'] = ts_code

            # 设置日期范围
            if 'start_date' not in stock_params:
                list_date = stock.get('list_date', '20050101')
                stock_params['start_date'] = list_date
            if 'end_date' not in stock_params:
                stock_params['end_date'] = datetime.now().strftime('%Y%m%d')

            yield stock_params, stock

    def generate_period_params(
        self,
        base_params: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> Iterator[Tuple[Dict[str, Any], str]]:
        """
        生成报告期分页参数
        
        Args:
            base_params: 基础参数
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
        
        Yields:
            (期参数, period) 元组
        """
        periods = generate_quarter_end_dates(start_date, end_date)

        if not periods:
            logger.warning(f"No report periods found in range {start_date} - {end_date}")
            return

        logger.info(f"Generating {len(periods)} report periods")

        for period in periods:
            period_params = base_params.copy()
            period_params.pop('start_date', None)
            period_params.pop('end_date', None)
            period_params['period'] = period

            yield period_params, period

    def generate_quarterly_params(
        self,
        base_params: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> Iterator[Tuple[Dict[str, Any], Tuple[str, str]]]:
        """
        生成季度范围分页参数
        
        Yields:
            (季度参数, (range_start, range_end)) 元组
        """
        ranges = generate_quarterly_ranges(start_date, end_date)

        for range_start, range_end in ranges:
            range_params = base_params.copy()
            range_params['start_date'] = range_start
            range_params['end_date'] = range_end

            yield range_params, (range_start, range_end)

    def generate_periodic_params(
        self,
        base_params: Dict[str, Any],
        start_date: str,
        end_date: str,
        period_type: str = 'month'
    ) -> Iterator[Tuple[Dict[str, Any], Tuple[str, str]]]:
        """
        生成周期性时间范围分页参数
        
        Args:
            period_type: 周期类型 ('week', 'month', 'quarter', 'year')
        
        Yields:
            (周期参数, (range_start, range_end)) 元组
        """
        ranges = generate_time_ranges(start_date, end_date, period_type)

        for range_start, range_end in ranges:
            range_params = base_params.copy()
            range_params['start_date'] = range_start
            range_params['end_date'] = range_end

            yield range_params, (range_start, range_end)


# ==================== 辅助函数（模块级别） ====================

def get_window_size_for_interface(interface_name: str) -> int:
    """
    根据接口类型确定窗口大小
    
    不同接口的数据量差异很大，需要使用不同的窗口大小
    以避免单次请求数据过大或请求次数过多
    """
    data_volume_config = {
        'small': ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date'],
        'medium': ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend',
                  'repurchase', 'concept_detail', 'share_float', 'stk_holdertrade'],
        'large': ['stk_factor', 'stk_factor_pro', 'moneyflow_hsgt', 'moneyflow_north',
                 'moneyflow_stock', 'block_trade', 'stk_rewards', 'pledge_stat'],
        'financial': ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']
    }

    for typ, interfaces in data_volume_config.items():
        if interface_name in interfaces:
            if typ == 'small':
                return 3650  # 10年
            elif typ == 'medium':
                return 1825  # 5年
            elif typ == 'financial':
                return 36500  # 100年，全量
            else:
                return 365  # 1年

    return 365  # 默认1年


def generate_quarter_end_dates(start_date: str, end_date: str) -> List[str]:
    """生成季度末日期列表"""
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')

    quarter_ends = [(3, 31), (6, 30), (9, 30), (12, 31)]
    periods = []

    current_year = start_dt.year
    current_quarter_idx = 0

    # 找到第一个季度
    for q_idx, (month, day) in enumerate(quarter_ends):
        quarter_end = datetime(current_year, month, day)
        if quarter_end >= start_dt:
            current_quarter_idx = q_idx
            break
    else:
        current_year += 1
        current_quarter_idx = 0

    # 生成所有季度
    while True:
        month, day = quarter_ends[current_quarter_idx]
        quarter_end = datetime(current_year, month, day)

        if quarter_end > end_dt:
            break

        periods.append(quarter_end.strftime('%Y%m%d'))

        current_quarter_idx += 1
        if current_quarter_idx >= len(quarter_ends):
            current_quarter_idx = 0
            current_year += 1

    return periods


def generate_quarterly_ranges(start_date: str, end_date: str) -> List[Tuple[str, str]]:
    """生成季度分割范围"""
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')

    quarterly_ranges = []
    current = start_dt

    while current <= end_dt:
        # 确定季度结束日期
        if current.month <= 3:
            quarter_end = datetime(current.year, 3, 31)
        elif current.month <= 6:
            quarter_end = datetime(current.year, 6, 30)
        elif current.month <= 9:
            quarter_end = datetime(current.year, 9, 30)
        else:
            quarter_end = datetime(current.year, 12, 31)

        if quarter_end > end_dt:
            quarter_end = end_dt

        # 确定范围开始日期
        if current.month in [1, 4, 7, 10] and current.day == 1:
            range_start = current.strftime('%Y%m%d')
        else:
            if current.month <= 3:
                range_start = datetime(current.year, 1, 1).strftime('%Y%m%d')
            elif current.month <= 6:
                range_start = datetime(current.year, 4, 1).strftime('%Y%m%d')
            elif current.month <= 9:
                range_start = datetime(current.year, 7, 1).strftime('%Y%m%d')
            else:
                range_start = datetime(current.year, 10, 1).strftime('%Y%m%d')

        range_end = quarter_end.strftime('%Y%m%d')
        quarterly_ranges.append((range_start, range_end))

        # 移动到下一季度
        if quarter_end.month == 3:
            current = datetime(quarter_end.year, 4, 1)
        elif quarter_end.month == 6:
            current = datetime(quarter_end.year, 7, 1)
        elif quarter_end.month == 9:
            current = datetime(quarter_end.year, 10, 1)
        else:
            current = datetime(quarter_end.year + 1, 1, 1)

    return quarterly_ranges


def generate_time_ranges(start_date: str, end_date: str, period_type: str) -> List[Tuple[str, str]]:
    """生成时间分割范围"""
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')

    time_ranges = []
    current = start_dt

    while current <= end_dt:
        if period_type == 'week':
            days_until_sunday = 6 - current.weekday()
            period_end = current + timedelta(days=days_until_sunday)
        elif period_type == 'month':
            if current.month == 12:
                period_end = datetime(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = datetime(current.year, current.month + 1, 1) - timedelta(days=1)
        elif period_type == 'quarter':
            if current.month <= 3:
                period_end = datetime(current.year, 3, 31)
            elif current.month <= 6:
                period_end = datetime(current.year, 6, 30)
            elif current.month <= 9:
                period_end = datetime(current.year, 9, 30)
            else:
                period_end = datetime(current.year, 12, 31)
        elif period_type == 'year':
            period_end = datetime(current.year, 12, 31)
        else:
            # 默认按月
            if current.month == 12:
                period_end = datetime(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = datetime(current.year, current.month + 1, 1) - timedelta(days=1)

        if period_end > end_dt:
            period_end = end_dt

        range_start = current.strftime('%Y%m%d')
        range_end = period_end.strftime('%Y%m%d')
        time_ranges.append((range_start, range_end))

        # 移动到下一周期
        if period_type == 'week':
            current = period_end + timedelta(days=1)
        elif period_type == 'month':
            if period_end.month == 12:
                current = datetime(period_end.year + 1, 1, 1)
            else:
                current = datetime(period_end.year, period_end.month + 1, 1)
        elif period_type == 'quarter':
            if period_end.month == 3:
                current = datetime(period_end.year, 4, 1)
            elif period_end.month == 6:
                current = datetime(period_end.year, 7, 1)
            elif period_end.month == 9:
                current = datetime(period_end.year, 10, 1)
            else:
                current = datetime(period_end.year + 1, 1, 1)
        elif period_type == 'year':
            current = datetime(period_end.year + 1, 1, 1)

    return time_ranges
```

---

### 2. 修改 `app4/core/downloader.py`

#### 2.1 导入新模块

```python
# 在文件顶部添加
from .pagination import (
    ParameterGenerator, 
    PaginationContext,
    get_window_size_for_interface
)
```

#### 2.2 修改 `_execute_pagination` 方法

```python
def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    执行分页/循环逻辑 - 控制器
    
    职责：
    1. 创建分页上下文
    2. 根据模式选择执行方法
    3. 调用具体执行方法
    """
    pagination_config = interface_config.get('pagination', {})
    if not pagination_config.get('enabled', False):
        return self._make_request(interface_config, params)

    mode = pagination_config.get('mode', 'offset')

    # 创建分页上下文（不包含交易日历和股票列表，在各方法内按需获取）
    context = PaginationContext(
        interface_config=interface_config,
        force_download=self.force_download
    )

    if mode == 'offset':
        return self._execute_offset_pagination(interface_config, params, context)
    elif mode == 'date_range':
        return self._execute_date_range_pagination(interface_config, params, context)
    elif mode == 'stock_loop':
        return self._execute_stock_loop_pagination(interface_config, params, context)
    elif mode == 'period_range':
        return self._execute_period_range_pagination(interface_config, params, context)
    elif mode == 'quarterly_range':
        return self._execute_quarterly_pagination(interface_config, params, context)
    elif mode == 'periodic_range':
        return self._execute_periodic_pagination(interface_config, params, context)
    else:
        return self._make_request(interface_config, params)
```

#### 2.3 重写各分页执行方法

**Offset分页**：

```python
def _execute_offset_pagination(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    context: PaginationContext
) -> List[Dict[str, Any]]:
    """执行offset分页"""
    all_data = []
    limit = context.pagination_config.get('default_limit', 5000)
    
    param_gen = ParameterGenerator(context)
    
    for page_params in param_gen.generate_offset_params(params):
        page_data = self._make_request(interface_config, page_params)
        
        if not page_data:
            break
        
        all_data.extend(page_data)
        
        # 判断是否是最后一页
        if len(page_data) < limit:
            break
    
    return all_data
```

**日期范围分页**：

```python
def _execute_date_range_pagination(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    context: PaginationContext
) -> List[Dict[str, Any]]:
    """执行日期范围分页（并发）"""
    interface_name = interface_config['name']
    
    # 财务接口全量返回
    if interface_name in ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']:
        logger.info(f"财务接口{interface_name}使用全量请求")
        return self._make_request(interface_config, params)
    
    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
    
    # 获取交易日历
    trade_calendar = self.get_trade_calendar(start_date, end_date)
    if not trade_calendar:
        logger.warning("Failed to get trade calendar, using offset fallback")
        offset_config = interface_config.get('offset_pagination', {})
        if offset_config.get('enabled', False):
            return self._execute_offset_pagination(interface_config, params, context)
        return self._make_request(interface_config, params)
    
    # 更新上下文
    context.trade_calendar = trade_calendar
    
    # 确定并发数
    if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
        max_workers = 1
    elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
        max_workers = 2
    else:
        max_workers = 4
    
    # 创建参数生成器并收集窗口
    param_gen = ParameterGenerator(context)
    windows = []
    window_params_list = []
    
    for window_params, window_id in param_gen.generate_date_range_params(params, start_date, end_date):
        windows.append(window_id)
        window_params_list.append(window_params)
    
    # 并发执行
    all_data = []
    results_by_window = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_window = {}
        
        for idx, window_params in enumerate(window_params_list):
            window_start, window_end = windows[idx]
            
            # 覆盖率检查
            should_skip = False
            if self.coverage_manager and not self.force_download:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    window_params,
                    strategy='date_range'
                )
            
            if should_skip:
                logger.info(f"Skipping window {window_start} - {window_end}")
                results_by_window[(window_start, window_end)] = []
            else:
                offset_config = interface_config.get('offset_pagination', {})
                if offset_config.get('enabled', False):
                    future = executor.submit(
                        self._make_request_with_offset_check,
                        interface_config,
                        window_params
                    )
                else:
                    future = executor.submit(
                        self._make_request,
                        interface_config,
                        window_params
                    )
                future_to_window[future] = (window_start, window_end)
        
        # 收集结果
        for future in as_completed(future_to_window):
            window_start, window_end = future_to_window[future]
            try:
                result = future.result()
                results_by_window[(window_start, window_end)] = result
            except Exception as e:
                logger.error(f"Error fetching window {window_start} to {window_end}: {e}")
                results_by_window[(window_start, window_end)] = []
    
    # 合并结果（保持顺序）
    for window_start, window_end in windows:
        window_data = results_by_window.get((window_start, window_end), [])
        all_data.extend(window_data)
    
    return all_data
```

#### 2.4 删除的方法

从 `downloader.py` 中删除以下方法（已移至 `pagination.py`）：
- `_generate_quarter_end_dates`
- `_generate_quarterly_ranges`
- `_generate_time_ranges`
- `_get_window_size_for_interface`

#### 2.5 保留的方法

- `_is_stock_data_exists` — 保留在 `downloader.py`，因为需要访问存储路径
- `_make_request`
- `_make_request_with_offset_check`
- `get_trade_calendar`
- `_get_trade_calendar_from_data_dir`
- `_get_stock_list_from_memory_cache`
- `_get_stock_list_from_data_dir`
- `download_single_stock`
- 其他核心方法

---

## 关键设计决策

### 1. `_is_stock_data_exists` 保留在 downloader.py

**原因**：
- 该方法需要访问 `storage_dir` 配置
- 需要使用 `polars` 读取 parquet 文件
- 符合"分页只生成参数"的原则

**使用方式**：
```python
# 在 _execute_stock_loop_pagination 中
for stock_params, stock_info in param_gen.generate_stock_params(
    params,
    existing_stocks_checker=lambda name, code: self._is_stock_data_exists(name, code)
):
    # 处理...
```

### 2. 线程安全

- `ParameterGenerator` 是无状态的生成器，每次调用创建新实例
- 原有的 `_cache_lock` 保持不变
- 并发执行逻辑保留在 `downloader.py` 中

### 3. 无限生成器的处理

`generate_offset_params` 是无限生成器，调用者必须：
```python
for page_params in param_gen.generate_offset_params(params):
    data = self._make_request(interface_config, page_params)
    if not data or len(data) < limit:
        break  # 必须有终止条件
    all_data.extend(data)
```

---

## 实施步骤

### 第1步：创建 pagination.py

```bash
# 创建文件
touch app4/core/pagination.py

# 复制上面的完整代码到文件中
```

### 第2步：修改 downloader.py

1. 添加导入语句
2. 替换 `_execute_pagination` 方法
3. 替换6个分页执行方法
4. 删除4个辅助方法（已移至 pagination.py）
5. 保留 `_is_stock_data_exists`

### 第3步：测试

```bash
# 1. 导入测试
python -c "from app4.core.pagination import ParameterGenerator, PaginationContext; print('Import OK')"

# 2. 单元测试
python -c "
from app4.core.pagination import generate_quarter_end_dates
periods = generate_quarter_end_dates('20240101', '20241231')
print(f'Periods: {periods}')
assert periods == ['20240331', '20240630', '20240930', '20241231']
print('Unit test passed')
"

# 3. 集成测试
python -c "
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

downloader = GenericDownloader(ConfigLoader())
data = downloader.download('daily', {'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240131'})
print(f'Downloaded {len(data) if data else 0} records')
"
```

### 第4步：验证功能

- [ ] Offset分页正常工作
- [ ] 日期范围分页正常工作
- [ ] 股票循环分页正常工作
- [ ] 报告期分页正常工作
- [ ] 季度分页正常工作
- [ ] 周期性分页正常工作
- [ ] 覆盖率检查正常工作
- [ ] 性能监控正常工作

---

## 单元测试示例

```python
# tests/test_pagination.py
import pytest
from app4.core.pagination import (
    ParameterGenerator, 
    PaginationContext,
    generate_quarter_end_dates,
    generate_quarterly_ranges,
    get_window_size_for_interface
)


class TestParameterGenerator:
    """测试参数生成器"""
    
    def test_generate_offset_params(self):
        """测试offset参数生成"""
        context = PaginationContext(
            interface_config={
                'name': 'test',
                'pagination': {
                    'limit_key': 'limit',
                    'offset_key': 'offset',
                    'default_limit': 100
                }
            }
        )
        
        gen = ParameterGenerator(context)
        params_iter = gen.generate_offset_params({'field': 'value'})
        
        # 获取前3页
        page1 = next(params_iter)
        page2 = next(params_iter)
        page3 = next(params_iter)
        
        assert page1['offset'] == 0
        assert page1['limit'] == 100
        assert page2['offset'] == 100
        assert page3['offset'] == 200
    
    def test_generate_date_range_params_no_calendar(self):
        """测试没有交易日历时的行为"""
        context = PaginationContext(
            interface_config={'name': 'daily', 'pagination': {}},
            trade_calendar=None
        )
        
        gen = ParameterGenerator(context)
        params_list = list(gen.generate_date_range_params({}, '20240101', '20240131'))
        
        # 应该返回单个请求
        assert len(params_list) == 1
    
    def test_generate_date_range_params_with_calendar(self):
        """测试有交易日历时的窗口生成"""
        # 模拟10个交易日
        trade_calendar = [
            {'cal_date': f'2024010{i}', 'is_open': 1}
            for i in range(1, 10)
        ]
        
        context = PaginationContext(
            interface_config={'name': 'daily', 'pagination': {}},
            trade_calendar=trade_calendar
        )
        
        gen = ParameterGenerator(context)
        windows = list(gen.generate_date_range_params({}, '20240101', '20240110'))
        
        assert len(windows) > 0
        for params, (start, end) in windows:
            assert 'start_date' in params
            assert 'end_date' in params


class TestHelperFunctions:
    """测试辅助函数"""
    
    def test_generate_quarter_end_dates(self):
        """测试季度末日期生成"""
        periods = generate_quarter_end_dates('20240101', '20241231')
        assert periods == ['20240331', '20240630', '20240930', '20241231']
    
    def test_generate_quarter_end_dates_partial_year(self):
        """测试部分年份"""
        periods = generate_quarter_end_dates('20240401', '20240831')
        assert periods == ['20240630']
    
    def test_get_window_size_for_interface(self):
        """测试窗口大小计算"""
        # 小数据量接口
        assert get_window_size_for_interface('fina_audit') == 3650
        
        # 中等数据量接口
        assert get_window_size_for_interface('dividend') == 1825
        
        # 大数据量接口
        assert get_window_size_for_interface('stk_factor') == 365
        
        # 财务接口
        assert get_window_size_for_interface('balancesheet_vip') == 36500
        
        # 未知接口
        assert get_window_size_for_interface('unknown') == 365
```

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 遗漏边缘情况 | 完整的单元测试 + 集成测试 |
| 性能退化 | 保持并发逻辑不变，基准测试对比 |
| 覆盖率检查失效 | 保留原有调用位置，增加测试用例 |
| 线程安全问题 | 无状态生成器 + 保留原有锁机制 |

---

## 总结

本方案通过**参数生成器模式**实现了真正的职责分离：

- **pagination.py**：纯参数生成逻辑，约500行
  - `PaginationContext`：数据容器
  - `ParameterGenerator`：参数生成器
  - 辅助函数：日期范围生成等

- **downloader.py**：执行控制，约600行
  - 分页执行方法
  - 请求执行
  - 错误处理
  - 并发调度

**关键改进**：
1. ✅ 零回调，避免循环依赖
2. ✅ 单向依赖，代码更清晰
3. ✅ 纯函数易测试
4. ✅ 线性调用栈易调试
5. ✅ `_is_stock_data_exists` 保留在正确位置
6. ✅ 明确的无限生成器使用说明
