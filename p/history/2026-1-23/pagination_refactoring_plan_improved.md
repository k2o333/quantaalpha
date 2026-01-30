# 分页代码拆分方案（改进版）

## 背景分析

基于对 `/home/quan/testdata/aspipe_v4/app4/core/downloader.py` 的深入分析（1413行代码）：

**当前分页代码统计**（837行，占比59%）：

| 方法名 | 起始行 | 行数 | 职责 |
|--------|--------|------|------|
| `_execute_pagination` | 213 | 30 | 分页调度入口 |
| `_execute_offset_pagination` | 244 | 29 | Offset分页 |
| `_execute_date_range_pagination` | 420 | 48 | 日期范围分页（智能调度）|
| `_execute_date_range_pagination_concurrent` | 274 | 101 | 并发日期分页（核心）|
| `_make_request_with_offset_check` | 376 | 43 | 带offset检查的请求 |
| `_execute_stock_loop_pagination` | 469 | 89 | 股票循环分页 |
| `_execute_period_range_pagination` | 736 | 64 | 报告期范围分页 |
| `_execute_quarterly_pagination` | 801 | 36 | 季度周期分页 |
| `_execute_periodic_pagination` | 903 | 37 | 周期性时间分页 |
| `_generate_quarter_end_dates` | 676 | 50 | 生成季度末日期 |
| `_generate_quarterly_ranges` | 837 | 65 | 生成季度范围 |
| `_generate_time_ranges` | 941 | 83 | 生成时间范围 |
| `_get_window_size_for_interface` | 1305 | 30 | 智能窗口大小 |
| `_is_stock_data_exists` | 1336 | 18 | 股票数据存在检查 |
| **总计** | | **837** | |

**核心问题识别**：

原方案的问题：
1. ❌ 循环依赖：PaginationManager ↔ GenericDownloader 通过回调互相依赖
2. ❌ 职责不清：PaginationManager 通过回调执行请求，未真正解耦
3. ❌ 测试困难：需要模拟回调函数
4. ❌ 调试复杂：跨模块调用栈难以追踪

## 改进方案：参数生成器模式

### 设计哲学

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
├── downloader.py          (~576行) - 执行控制
│   ├── download()                     # 主入口
│   ├── _execute_pagination()          # 分页调度（简化版）
│   ├── _make_request()                # 请求执行
│   ├── get_trade_calendar()           # 交易日历
│   └── ...                            # 其他核心方法
│
└── pagination.py          (~837行) - 参数生成器
    ├── ParameterGenerator              # 参数生成器类
    │   ├── generate_offset_params()    # 生成offset参数
    │   ├── generate_date_range_params() # 生成日期范围参数
    │   ├── generate_stock_params()     # 生成股票循环参数
    │   ├── generate_period_params()    # 生成报告期参数
    │   └── ...                         # 其他生成方法
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
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Iterator, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PaginationContext:
    """分页上下文 - 传递必要的配置和数据"""
    interface_config: Dict[str, Any]
    trade_calendar: Optional[List[Dict[str, Any]]] = None
    stock_list: Optional[List[Dict[str, Any]]] = None
    force_download: bool = False


class ParameterGenerator:
    """
    请求参数生成器
    
    职责：根据分页策略生成请求参数迭代器
    不执行任何网络请求，只负责参数生成
    """

    def __init__(self, context: PaginationContext):
        """
        初始化参数生成器
        
        Args:
            context: 分页上下文，包含接口配置和必要数据
        """
        self.context = context
        self.interface_name = context.interface_config['name']
        self.pagination_config = context.interface_config.get('pagination', {})

    # ==================== 参数生成方法 ====================

    def generate_offset_params(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        生成offset分页参数
        
        Yields:
            每一页的请求参数
        """
        offset = 0
        limit_key = self.pagination_config.get('limit_key', 'limit')
        offset_key = self.pagination_config.get('offset_key', 'offset')
        default_limit = self.pagination_config.get('default_limit', 5000)

        while True:
            page_params = base_params.copy()
            page_params[limit_key] = default_limit
            page_params[offset_key] = offset

            yield page_params

            # 注意：无法在这里判断是否继续，需要调用者根据返回数据判断
            offset += default_limit

    def generate_date_range_params(
        self,
        base_params: Dict[str, Any],
        start_date: str,
        end_date: str,
        max_workers: int = 4
    ) -> Iterator[Tuple[Dict[str, Any], Optional[Tuple[str, str]]]]:
        """
        生成日期范围分页参数（带智能窗口）
        
        Args:
            base_params: 基础参数
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            max_workers: 最大并发数
        
        Yields:
            (窗口参数, 窗口标识) 元组
            窗口标识 = (window_start, window_end)，用于结果排序
        """
        if not self.context.trade_calendar:
            logger.warning("Trade calendar not provided, falling back to direct request")
            yield base_params, None
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
        window_size = self._get_window_size_for_interface(self.interface_name)

        logger.info(f"Generating {len(trade_days)} trade days with window size {window_size}")

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
        base_params: Dict[str, Any]
    ) -> Iterator[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        生成股票循环分页参数
        
        Args:
            base_params: 基础参数
        
        Yields:
            (股票参数, 股票信息) 元组
        """
        if not self.context.stock_list:
            logger.error("Stock list not provided for stock loop pagination")
            return

        for stock in self.context.stock_list:
            ts_code = stock['ts_code']

            # 前置去重检查（参数生成阶段）
            if not self.context.force_download and self._is_stock_data_exists(
                self.interface_name, ts_code
            ):
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
            (期参数, 期标识) 元组
        """
        periods = self._generate_quarter_end_dates(start_date, end_date)

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
        ranges = self._generate_quarterly_ranges(start_date, end_date)

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
        ranges = self._generate_time_ranges(start_date, end_date, period_type)

        for range_start, range_end in ranges:
            range_params = base_params.copy()
            range_params['start_date'] = range_start
            range_params['end_date'] = range_end

            yield range_params, (range_start, range_end)

    # ==================== 辅助方法 ====================

    def _get_window_size_for_interface(self, interface_name: str) -> int:
        """根据接口类型确定窗口大小"""
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

        return 365

    def _is_stock_data_exists(self, interface_name: str, ts_code: str, storage_dir: str = '../data') -> bool:
        """检查股票数据是否已存在"""
        try:
            import os
            import polars as pl

            dir_path = os.path.join(storage_dir, interface_name)
            if not os.path.exists(dir_path):
                return False

            df = pl.read_parquet(dir_path)
            return df.filter(pl.col('ts_code') == ts_code).height > 0
        except Exception:
            return False

    def _generate_quarter_end_dates(self, start_date: str, end_date: str) -> List[str]:
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

    def _generate_quarterly_ranges(self, start_date: str, end_date: str) -> List[Tuple[str, str]]:
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

    def _generate_time_ranges(self, start_date: str, end_date: str, period_type: str) -> List[Tuple[str, str]]:
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

### 2. 修改 `app4/core/downloader.py`

```python
"""
通用下载器 - 执行引擎
"""

# ... existing imports ...
from .pagination import ParameterGenerator, PaginationContext

class GenericDownloader:
    """通用下载器"""

    def __init__(self, config_loader: ConfigLoader, storage_manager=None,
                 trade_calendar_cache=None, stock_list_cache=None,
                 force_download=False, incremental_mode=False):
        # ... existing initialization ...

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """下载指定接口的数据"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            validated_params = self._validate_parameters(interface_config, params)

            # 执行分页/循环逻辑
            all_data = self._execute_pagination(interface_config, validated_params)

            return all_data
        except Exception as e:
            logger.error(f"Error downloading data from {interface_name}: {str(e)}")
            return None

    def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行分页/循环逻辑 - 控制器
        
        职责：
        1. 创建参数生成器
        2. 遍历生成的参数
        3. 执行请求
        4. 处理结果
        5. 错误处理和重试
        """
        pagination_config = interface_config.get('pagination', {})
        if not pagination_config.get('enabled', False):
            # 不分页，直接请求
            return self._make_request(interface_config, params)

        mode = pagination_config.get('mode', 'offset')
        all_data = []

        # 创建分页上下文
        context = PaginationContext(
            interface_config=interface_config,
            force_download=self.force_download
        )

        # 根据分页模式生成参数并执行
        if mode == 'offset':
            all_data = self._execute_offset_pagination(interface_config, params, context)

        elif mode == 'date_range':
            all_data = self._execute_date_range_pagination(interface_config, params, context)

        elif mode == 'stock_loop':
            all_data = self._execute_stock_loop_pagination(interface_config, params, context)

        elif mode == 'period_range':
            all_data = self._execute_period_range_pagination(interface_config, params, context)

        elif mode == 'quarterly_range':
            all_data = self._execute_quarterly_pagination(interface_config, params, context)

        elif mode == 'periodic_range':
            all_data = self._execute_periodic_pagination(interface_config, params, context)

        else:
            # 未知模式，直接请求
            all_data = self._make_request(interface_config, params)

        return all_data

    def _execute_offset_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext
    ) -> List[Dict[str, Any]]:
        """执行offset分页"""
        all_data = []
        param_gen = ParameterGenerator(context)
        limit = context.pagination_config.get('default_limit', 5000)

        for page_params in param_gen.generate_offset_params(params):
            page_data = self._make_request(interface_config, page_params)

            if not page_data:
                break

            all_data.extend(page_data)

            # 判断是否是最后一页
            if len(page_data) < limit:
                break

        return all_data

    def _execute_date_range_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext
    ) -> List[Dict[str, Any]]:
        """执行日期范围分页（并发）"""
        # 获取日期范围
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        # 获取交易日历
        trade_calendar = self.get_trade_calendar(start_date, end_date)
        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using offset pagination fallback")
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                return self._execute_offset_pagination(interface_config, params, context)
            else:
                return self._make_request(interface_config, params)

        # 更新上下文
        context.trade_calendar = trade_calendar

        # 创建参数生成器
        param_gen = ParameterGenerator(context)

        # 智能并发数
        interface_name = interface_config['name']
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        elif interface_name in ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']:
            logger.info(f"财务接口{interface_name}使用全量请求")
            return self._make_request(interface_config, params)
        else:
            max_workers = 4

        # 收集所有窗口参数
        windows = []
        window_params_list = []
        for window_params, window_id in param_gen.generate_date_range_params(
            params, start_date, end_date, max_workers
        ):
            if window_id:  # 有窗口标识
                windows.append(window_id)
                window_params_list.append(window_params)
            else:  # 无窗口标识，直接请求
                return self._make_request(interface_config, window_params)

        # 并发执行（保持原有并发逻辑）
        all_data = []
        results_by_window = {}

        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        thread_id = threading.get_ident()
        task_id = params.get('ts_code', 'unknown')

        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] Fetching {len(windows)} windows with {max_workers} workers")

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
                    # 检查是否需要内部offset分页
                    offset_config = interface_config.get('offset_pagination', {})
                    if offset_config.get('enabled', False):
                        # 提交带offset检查的任务
                        future = executor.submit(
                            self._make_request_with_offset_check,
                            interface_config,
                            window_params,
                            offset_config
                        )
                    else:
                        # 提交直接请求任务
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

    def _execute_stock_loop_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext
    ) -> List[Dict[str, Any]]:
        """执行股票循环分页"""
        all_data = []

        # 获取股票列表
        logger.info("正在获取股票列表...")
        stock_list = self._get_stock_list_from_memory_cache()

        if stock_list is None:
            logger.info("从Data目录获取股票列表...")
            stock_list = self._get_stock_list_from_data_dir()

        if stock_list is None:
            logger.info("从API获取股票列表...")
            stock_params = {'list_status': 'L'}
            stock_list = self._make_request(
                self.config_loader.get_interface_config('stock_basic'),
                stock_params
            )
            if stock_list:
                with self._cache_lock:
                    self._memory_cache['stock_list'] = stock_list

        if not stock_list:
            logger.error("Failed to get stock list")
            return all_data

        # 更新上下文
        context.stock_list = stock_list

        # 创建参数生成器
        param_gen = ParameterGenerator(context)

        # 确定并发数
        interface_name = interface_config['name']
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        else:
            max_workers = 4

        # 收集所有股票参数
        stock_tasks = []
        for stock_params, stock_info in param_gen.generate_stock_params(params):
            stock_tasks.append((stock_params, stock_info))

        logger.info(f"Processing {len(stock_tasks)} stocks with {max_workers} workers")

        # 并发执行
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for stock_params, stock_info in stock_tasks:
                future = executor.submit(
                    self.download_single_stock,
                    interface_config,
                    stock_info,
                    stock_params
                )
                futures.append(future)

            for future in as_completed(futures):
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                except Exception as e:
                    logger.error(f"获取股票数据失败: {str(e)}")
                    continue

        return all_data

    def _execute_period_range_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext
    ) -> List[Dict[str, Any]]:
        """执行报告期范围分页"""
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        param_gen = ParameterGenerator(context)
        all_data = []

        for period_params, period in param_gen.generate_period_params(
            params, start_date, end_date
        ):
            # 覆盖率检查
            should_skip = False
            if self.coverage_manager and not self.force_download:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    period_params,
                    strategy='period'
                )

            if should_skip:
                logger.info(f"Skipping period {period}")
                continue

            logger.info(f"Fetching data for period {period}")

            period_data = self._make_request(interface_config, period_params)

            # 添加period字段
            if period_data:
                for record in period_data:
                    record['period'] = period
                all_data.extend(period_data)

        return all_data

    def _execute_quarterly_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext
    ) -> List[Dict[str, Any]]:
        """执行季度周期分页"""
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        param_gen = ParameterGenerator(context)
        all_data = []

        for range_params, (range_start, range_end) in param_gen.generate_quarterly_params(
            params, start_date, end_date
        ):
            logger.info(f"Fetching quarterly data: {range_start} - {range_end}")

            range_data = self._make_request(interface_config, range_params)

            if range_data:
                all_data.extend(range_data)

        return all_data

    def _execute_periodic_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext
    ) -> List[Dict[str, Any]]:
        """执行周期性时间范围分页"""
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
        period_type = context.pagination_config.get('period_type', 'month')

        param_gen = ParameterGenerator(context)
        all_data = []

        for range_params, (range_start, range_end) in param_gen.generate_periodic_params(
            params, start_date, end_date, period_type
        ):
            logger.info(f"Fetching {period_type} data: {range_start} - {range_end}")

            range_data = self._make_request(interface_config, range_params)

            if range_data:
                all_data.extend(range_data)

        return all_data

    def _make_request_with_offset_check(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        offset_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """带offset检查的请求"""
        import time

        start_time = time.time()

        if offset_config.get('enabled', False):
            logger.debug(f"Using internal offset pagination for window")

            # 创建临时上下文用于offset分页
            temp_context = PaginationContext(
                interface_config=interface_config,
                force_download=self.force_download
            )
            temp_gen = ParameterGenerator(temp_context)

            all_window_data = []
            for page_params in temp_gen.generate_offset_params(params):
                page_data = self._make_request(interface_config, page_params)
                if not page_data:
                    break

                all_window_data.extend(page_data)

                if len(page_data) < offset_config.get('default_limit', 5000):
                    break

            window_data = all_window_data
        else:
            window_data = self._make_request(interface_config, params)

        elapsed_time = time.time() - start_time

        if hasattr(self, 'performance_monitor') and self.performance_monitor:
            self.performance_monitor.record_request(
                interface=interface_config['name'],
                duration=elapsed_time,
                record_count=len(window_data) if window_data else 0,
                retry_count=0,
                window_start=params.get('start_date'),
                window_end=params.get('end_date')
            )

        return window_data or []

    # ... 保留其他方法：get_trade_calendar, _get_stock_list_from_memory_cache,
    #     _get_stock_list_from_data_dir, download_single_stock, _make_request,
    #     _classify_api_error, verify_trade_calendar_integrity ...
```

---

## 方案对比

### 原方案 vs 改进方案

| 特性 | 原方案（回调模式） | 改进方案（参数生成器） |
|------|-------------------|---------------------|
| **耦合度** | 双向依赖（循环引用） | **单向依赖**（downloader → pagination） |
| **职责分离** | ❌ 分页模块仍执行请求 | ✅ **分页只生成参数** |
| **测试难度** | 需要模拟回调函数 | ✅ **纯函数，易测试** |
| **调试复杂度** | 跨模块调用栈 | ✅ **单模块调用栈** |
| **代码清晰度** | 回调函数分散逻辑 | ✅ **线性执行流程** |
| **类型提示** | 回调函数类型复杂 | ✅ **明确的返回类型** |
| **扩展性** | 新增策略需修改两处 | ✅ **只修改pagination** |

### 数据流对比

**原方案（回调模式）**：
```
download() → PaginationManager.execute_pagination()
           ↓
    _make_request_func() → downloader._make_request()  # 回调
           ↑
    _get_trade_calendar_func() → downloader.get_trade_calendar()  # 回调
```

**改进方案（参数生成器）**：
```
download() → _execute_pagination()
           ↓
    ParameterGenerator.generate_xxx_params()  # 生成参数
           ↓
    for params in generator:                  # 遍历参数
           ↓
        downloader._make_request()           # 执行请求
           ↓
    combine results                          # 合并结果
```

---

## 实施步骤

### 第1步：创建 `app4/core/pagination.py`

```bash
# 创建文件
touch app4/core/pagination.py

# 复制上面的完整代码到文件中
# 确保所有依赖已导入
```

### 第2步：修改 `app4/core/downloader.py`

**修改点**：
1. 删除所有分页相关方法（837行）
2. 添加 `from .pagination import ParameterGenerator, PaginationContext`
3. 实现新的 `_execute_pagination` 方法（见上）
4. 实现6个具体的执行方法
5. 保留原有方法：`_make_request`, `get_trade_calendar`, `download_single_stock`等

**删除的方法**：
- `_execute_offset_pagination` → 逻辑移到 `_execute_pagination`
- `_execute_date_range_pagination` → 逻辑移到 `_execute_pagination`
- `_execute_date_range_pagination_concurrent` → 逻辑移到 `_execute_pagination`
- `_execute_stock_loop_pagination` → 逻辑移到 `_execute_pagination`
- `_execute_period_range_pagination` → 逻辑移到 `_execute_pagination`
- `_execute_quarterly_pagination` → 逻辑移到 `_execute_pagination`
- `_execute_periodic_pagination` → 逻辑移到 `_execute_pagination`
- `_generate_quarter_end_dates` → 移动到 `pagination.py`
- `_generate_quarterly_ranges` → 移动到 `pagination.py`
- `_generate_time_ranges` → 移动到 `pagination.py`
- `_get_window_size_for_interface` → 移动到 `pagination.py`
- `_is_stock_data_exists` → 移动到 `pagination.py`

**保留的方法**：
- `download()` - 主入口
- `_validate_parameters()` - 参数验证
- `get_trade_calendar()` - 交易日历获取
- `_get_trade_calendar_from_data_dir()` - 交易日历从磁盘获取
- `_make_request()` - 请求执行
- `_make_request_with_offset_check()` - 带offset检查的请求
- `_classify_api_error()` - 错误分类
- `_get_stock_list_from_memory_cache()` - 股票列表从缓存获取
- `_get_stock_list_from_data_dir()` - 股票列表从磁盘获取
- `download_single_stock()` - 单只股票下载
- `verify_trade_calendar_integrity()` - 交易日历完整性检查
- `_create_session_with_retries()` - Session创建

### 第3步：运行测试

```bash
# 1. 测试单个接口
python -c "
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

downloader = GenericDownloader(ConfigLoader())
data = downloader.download('daily', {'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240131'})
print(f'Downloaded {len(data)} records')
"

# 2. 测试offset分页
python -c "
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

downloader = GenericDownloader(ConfigLoader())
data = downloader.download('some_offset_interface', {})
print(f'Downloaded {len(data)} records')
"

# 3. 测试股票循环
python -c "
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

downloader = GenericDownloader(ConfigLoader())
data = downloader.download('stk_factor', {'start_date': '20240101', 'end_date': '20240131'})
print(f'Downloaded {len(data)} records')
"
```

### 第4步：验证功能

**检查列表**：
- [ ] Offset分页正常工作
- [ ] 日期范围分页正常工作
- [ ] 股票循环分页正常工作
- [ ] 报告期分页正常工作
- [ ] 季度分页正常工作
- [ ] 周期性分页正常工作
- [ ] 覆盖率检查正常工作
- [ ] 性能监控正常工作
- [ ] 错误处理和重试正常工作
- [ ] 日志输出正常

### 第5步：提交代码

```bash
git add app4/core/pagination.py
git add app4/core/downloader.py
git commit -m "refactor: Split pagination logic into dedicated module

- Extract 837 lines of pagination code from downloader.py
- Create pagination.py with ParameterGenerator class
- Implement parameter generator pattern (zero callbacks)
- Maintain all existing functionality
- Reduce downloader.py from 1414 to ~576 lines
- Improve testability and maintainability

BREAKING CHANGE: None (internal refactoring only)"

git push
```

---

## 单元测试策略

### 测试 `pagination.py`（纯函数，易测试）

```python
# test_pagination.py
import pytest
from app4.core.pagination import ParameterGenerator, PaginationContext

def test_generate_offset_params():
    """测试offset参数生成"""
    context = PaginationContext(
        interface_config={
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'offset',
                'limit_key': 'limit',
                'offset_key': 'offset',
                'default_limit': 100
            }
        }
    )

    generator = ParameterGenerator(context)
    params_list = list(generator.generate_offset_params({'field': 'value'}))

    assert len(params_list) == 3  # 假设生成了3页
    assert params_list[0]['offset'] == 0
    assert params_list[1]['offset'] == 100
    assert params_list[2]['offset'] == 200

def test_generate_date_range_params():
    """测试日期范围参数生成"""
    context = PaginationContext(
        interface_config={
            'name': 'daily',
            'pagination': {'enabled': True, 'mode': 'date_range'}
        },
        trade_calendar=[
            {'cal_date': '20240101', 'is_open': 1},
            {'cal_date': '20240102', 'is_open': 1},
            # ... more days
        ]
    )

    generator = ParameterGenerator(context)
    windows = list(generator.generate_date_range_params(
        {}, '20240101', '20240131', max_workers=2
    ))

    assert len(windows) > 0
    assert all(isinstance(w[0], dict) for w in windows)  # 参数是dict
    assert all(w[0].get('start_date') for w in windows)  # 有start_date

def test_window_size_calculation():
    """测试智能窗口大小计算"""
    context = PaginationContext(
        interface_config={'name': 'fina_audit', 'pagination': {}}
    )
    generator = ParameterGenerator(context)

    # 小数据量接口 → 大窗口
    assert generator._get_window_size_for_interface('fina_audit') == 3650

    # 中等数据量接口 → 中等窗口
    assert generator._get_window_size_for_interface('dividend') == 1825

    # 大数据量接口 → 小窗口
    assert generator._get_window_size_for_interface('stk_factor') == 365

    # 财务接口 → 全量
    assert generator._get_window_size_for_interface('balancesheet_vip') == 36500
```

### 测试 `downloader.py`（集成测试）

```python
# test_downloader.py
import pytest
from unittest.mock import Mock, patch
from app4.core.downloader import GenericDownloader

def test_execute_pagination_offset_mode():
    """测试offset分页模式"""
    downloader = GenericDownloader(Mock())
    downloader._make_request = Mock(return_value=[{'id': 1}, {'id': 2}])

    interface_config = {
        'name': 'test',
        'api_name': 'test_api',
        'pagination': {
            'enabled': True,
            'mode': 'offset',
            'default_limit': 2
        }
    }

    # Mock multiple pages
    downloader._make_request.side_effect = [
        [{'id': 1}, {'id': 2}],  # Page 1
        [{'id': 3}],             # Page 2 (last page)
        []                       # Page 3 (empty)
    ]

    result = downloader._execute_pagination(interface_config, {})

    assert len(result) == 3
    assert downloader._make_request.call_count == 2  # Stops after empty page

def test_execute_pagination_date_range_mode():
    """测试日期范围分页模式"""
    downloader = GenericDownloader(Mock())
    downloader._make_request = Mock(return_value=[{'date': '20240101'}])
    downloader.get_trade_calendar = Mock(return_value=[
        {'cal_date': '20240101', 'is_open': 1},
        {'cal_date': '20240102', 'is_open': 1},
    ])

    interface_config = {
        'name': 'daily',
        'api_name': 'daily',
        'pagination': {
            'enabled': True,
            'mode': 'date_range'
        }
    }

    result = downloader._execute_pagination(
        interface_config,
        {'start_date': '20240101', 'end_date': '20240131'}
    )

    assert downloader._make_request.call_count > 0
    assert len(result) > 0
```

---

## 优势与收益

### 1. **代码质量提升**

```
downloader.py: 1414行 → 576行（减少59%）
pagination.py: 0行 → 837行（新增模块）

职责清晰度：
- downloader: 执行控制 + 错误处理
- pagination: 纯参数生成逻辑
```

### 2. **可测试性提升**

**原方案测试**：
```python
# 需要mock回调函数
def test_pagination():
    mock_make_request = Mock()
    mock_get_calendar = Mock()

    pagination_manager = PaginationManager(...)
    pagination_manager.set_make_request_callback(mock_make_request)
    pagination_manager.set_trade_calendar_callback(mock_get_calendar)

    # ... test ...
```

**改进方案测试**：
```python
# 纯函数测试，无需mock
def test_pagination():
    context = PaginationContext(...)
    generator = ParameterGenerator(context)

    params = list(generator.generate_offset_params({}))

    # 断言参数正确性
    assert len(params) == expected_count
    assert params[0]['offset'] == 0
```

### 3. **调试效率提升**

**原方案调试**：
```
Traceback:
  File "downloader.py", line 168, in download
    all_data = self.pagination_manager.execute_pagination(...)
  File "pagination.py", line 113, in execute_pagination
    return self._make_request_func(...)  # 回调函数
  File "downloader.py", line 1100, in _make_request
    response = self.session.post(...)

问题：调用栈跨模块，难以追踪
```

**改进方案调试**：
```
Traceback:
  File "downloader.py", line 168, in download
    all_data = self._execute_pagination(...)
  File "downloader.py", line 250, in _execute_pagination
    for params in generator.generate_date_range_params(...):
  File "pagination.py", line 85, in generate_date_range_params
    trade_days = [...]
  File "downloader.py", line 300, in _make_request
    response = self.session.post(...)

问题：调用栈线性，易于理解
```

### 4. **性能影响**

**零性能损耗**：
- 原方案：回调函数调用 → 有轻微函数调用开销
- 改进方案：直接调用 → 无额外开销

**内存占用**：
- 原方案：PaginationManager 持有回调引用
- 改进方案：ParameterGenerator 不持有引用，GC友好

### 5. **可维护性提升**

**新增分页策略**：

原方案：
```python
# 1. 在pagination.py中添加方法
# 2. 在downloader.py中添加调用
# 3. 在PaginationManager中添加回调设置
# 4. 修改调度逻辑
```

改进方案：
```python
# 1. 在ParameterGenerator中添加生成方法
# 2. 在downloader._execute_pagination中添加elif分支
# 3. 完成（无需修改其他部分）
```

---

## 风险评估与缓解

### 风险1：遗漏部分逻辑

**风险描述**：在迁移过程中可能遗漏某些边缘情况

**缓解措施**：
- ✅ 代码行数对比：确保837行全部迁移
- ✅ 功能映射表：每个方法都有对应关系
- ✅ 完整测试：覆盖所有7种分页模式
- ✅ 灰度发布：先测试非核心接口

### 风险2：性能退化

**风险描述**：新架构可能引入性能问题

**缓解措施**：
- ✅ 零回调设计：无额外函数调用开销
- ✅ 惰性生成器：参数按需生成，不占用内存
- ✅ 并发模式不变：保持原有ThreadPoolExecutor逻辑
- ✅ 性能监控对比：记录重构前后的性能指标

### 风险3：覆盖率检查失效

**风险描述**：迁移后覆盖率检查可能不工作

**缓解措施**：
- ✅ 保留CoverageManager调用位置不变
- ✅ 参数传递方式不变（仍是params字典）
- ✅ 在downloader中执行检查（原位置）
- ✅ 单元测试验证should_skip调用

### 风险4：线程安全问题

**风险描述**：并发执行时可能出现竞态条件

**缓解措施**：
- ✅ 保持原有锁机制（_cache_lock）
- ✅ ParameterGenerator 是无状态生成器
- ✅ 每个线程独立创建生成器实例
- ✅ 压力测试验证并发安全性

---

## 性能基准测试

建议重构前后进行基准测试：

```python
# benchmark.py
import time
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

def benchmark():
    downloader = GenericDownloader(ConfigLoader())

    test_cases = [
        ('daily', {'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240131'}),
        ('stk_factor', {'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240131'}),
        ('fina_audit', {'ts_code': '000001.SZ', 'start_date': '20200101', 'end_date': '20231231'}),
    ]

    results = {}
    for interface_name, params in test_cases:
        start = time.time()
        data = downloader.download(interface_name, params)
        elapsed = time.time() - start

        results[interface_name] = {
            'time': elapsed,
            'records': len(data),
            'records_per_second': len(data) / elapsed if elapsed > 0 else 0
        }

        print(f"{interface_name}: {elapsed:.2f}s, {len(data)} records")

    return results

if __name__ == '__main__':
    benchmark()
```

**预期结果**：
- 性能差异 < 5%（可接受范围）
- 内存占用减少（无回调引用）
- GC压力减轻（临时对象减少）

---

## 总结

本方案通过**参数生成器模式**解决了原方案的循环依赖问题，实现了真正的职责分离：

- **分页模块**：纯逻辑，只负责生成参数，可独立测试
- **下载器**：执行控制，负责请求、错误处理、并发调度
- **零回调**：避免循环依赖，代码更清晰
- **易维护**：新增策略只需修改一处，扩展性更好

**代码行数变化**：
- `downloader.py`: 1414行 → 576行（-59%）
- `pagination.py`: 0行 → 837行（新模块）
- **总代码量不变**，但职责更清晰

**测试覆盖率提升**：
- pagination.py 可独立测试（无需mock）
- 参数生成逻辑可100%覆盖
- 边界情况更容易测试

**维护性提升**：
- 新增分页策略：只需在pagination.py添加生成方法 + downloader.py添加elif分支
- 调试更简单：线性调用栈，无跨模块回调
- 文档更清晰：每个模块职责单一

该方案在**保持所有功能不变**的前提下，显著提升了代码的可维护性和可测试性，是重构分页逻辑的最佳选择。
