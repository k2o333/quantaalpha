# Stock Loop 模式智能增量下载 - 完整解决方案

## 目录

1. [问题分析](#一问题分析)
2. [方案架构](#二方案架构)
3. [核心代码实现](#三核心代码实现)
4. [接口配置示例](#四接口配置示例)
5. [集成步骤](#五集成步骤)
6. [测试验证](#六测试验证)

---

## 一、问题分析

### 1.1 不同接口的参数差异

根据 Tushare 文档分析，不同接口的参数要求差异很大：

| 接口类型 | 日期参数 | 示例接口 | data_date_column |
|---------|---------|---------|------------------|
| 日线数据 | `ts_code` + `start_date`/`end_date` | `daily`, `daily_basic` | `trade_date` |
| 交易日期 | `ts_code` + `trade_date` | `moneyflow`, `block_trade` | `trade_date` |
| 财报数据 | `ts_code` + `period`/`end_date` | `income_vip`, `balancesheet_vip` | `end_date` |
| 日期锚定 | `ts_code` + 锚定日期参数 | `disclosure_date` | `end_date` |
| 无日期参数 | 仅 `ts_code` | `stock_company`, `stock_basic` | - |

### 1.2 核心需求

在 stock loop 模式下，对于指定接口和股票代码：

1. **完全无数据** → 全历史下载
2. **有数据但缺失** → 检测缺口，生成正确参数下载缺损数据
3. **数据完整** → 跳过，不调用 API

---

## 二、方案架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    StockLoopDownloadPlanner                      │
│                     (股票级下载计划生成器)                        │
├─────────────────────────────────────────────────────────────────┤
│  1. 检测数据存在性                                               │
│     └─> 检查该股票是否已有数据                                    │
│                                                                         │
│  2. 分析接口参数模式                                             │
│     └─> 从 YAML 配置解析参数要求                                  │
│                                                                         │
│  3. 生成下载策略                                                 │
│     ├─> 完全无数据 → 全历史下载                                   │
│     ├─> 有数据但缺失 → 计算缺口并生成参数                         │
│     └─> 数据完整 → 跳过                                          │
│                                                                         │
│  4. 执行下载任务                                                 │
│     └─> 按生成的参数列表逐个下载                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 支持的参数模式

| 模式 | 说明 | 适用接口 |
|------|------|---------|
| `date_range` | `start_date` + `end_date` 范围查询 | daily, daily_basic |
| `trade_date` | 按单个交易日期查询 | moneyflow |
| `period` | 按报告期（季度）查询 | income_vip |
| `date_anchor` | 日期锚定参数遍历 | disclosure_date |
| `none` | 无日期参数 | stock_company |

---

## 三、核心代码实现

### 3.1 stock_loop_planner.py

```python
# app4/core/stock_loop_planner.py
"""
Stock Loop 模式智能增量下载计划生成器

根据接口配置和现有数据，生成最优的下载任务列表
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from .date_utils import DateRange, detect_date_column, format_date

logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    """单个下载任务"""
    ts_code: str
    params: Dict[str, Any]
    reason: str  # 下载原因：full_history | gap_fill | update


class StockLoopPlanner:
    """
    Stock Loop 模式下载计划生成器

    职责：
    1. 分析接口参数配置
    2. 检测现有数据覆盖情况
    3. 生成最优下载参数
    """

    def __init__(
        self,
        coverage_manager,
        trade_calendar_provider,
        config_loader
    ):
        self.coverage_manager = coverage_manager
        self.trade_calendar_provider = trade_calendar_provider
        self.config_loader = config_loader

    def plan_download(
        self,
        interface_name: str,
        ts_code: str,
        interface_config: Dict[str, Any],
        user_params: Optional[Dict[str, Any]] = None
    ) -> List[DownloadTask]:
        """
        生成单个股票的下载计划

        Args:
            interface_name: 接口名称
            ts_code: 股票代码
            interface_config: 接口配置
            user_params: 用户指定的参数（如 --start_date, --end_date）

        Returns:
            List[DownloadTask]: 下载任务列表
        """
        # 1. 获取接口日期参数配置
        date_config = self._get_date_config(interface_config)
        logger.info(f"[{interface_name}/{ts_code}] 日期参数模式: {date_config['mode']}")

        # 2. 检查现有数据
        existing_dates = self._get_existing_dates_for_stock(
            interface_name, ts_code, date_config['data_date_column']
        )
        logger.info(f"[{interface_name}/{ts_code}] 已有数据: {len(existing_dates)} 天")

        # 3. 根据参数模式生成任务
        if date_config['mode'] == 'none':
            return self._plan_no_date_params(ts_code, user_params)

        elif date_config['mode'] == 'date_range':
            return self._plan_date_range_mode(
                interface_name, ts_code, interface_config,
                date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'trade_date':
            return self._plan_trade_date_mode(
                interface_name, ts_code, date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'period':
            return self._plan_period_mode(
                interface_name, ts_code, date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'date_anchor':
            return self._plan_date_anchor_mode(
                interface_name, ts_code, interface_config,
                date_config, existing_dates, user_params
            )

        else:
            logger.warning(f"未知的日期参数模式: {date_config['mode']}")
            return []

    def _get_date_config(self, interface_config: Dict[str, Any]) -> Dict[str, Any]:
        """从接口配置中提取日期参数配置"""
        date_params = interface_config.get('date_params', {})

        # 检测日期列（用于数据存在性检查）
        data_date_column = date_params.get('data_date_column') or \
                          detect_date_column(interface_config) or \
                          'trade_date'

        # 确定参数模式
        parameters = interface_config.get('parameters', {})

        # 自动推断模式
        if date_params.get('mode'):
            mode = date_params['mode']
        elif 'start_date' in parameters and 'end_date' in parameters:
            if date_params.get('anchor_param'):
                mode = 'date_anchor'
            else:
                mode = 'date_range'
        elif 'trade_date' in parameters:
            mode = 'trade_date'
        elif 'period' in parameters:
            mode = 'period'
        else:
            mode = 'none'

        return {
            'mode': mode,
            'data_date_column': data_date_column,
            'input_mapping': date_params.get('input_mapping', {}),
            'anchor_param': date_params.get('anchor_param'),
            'enumerate_dates': date_params.get('enumerate_dates', False),
            'date_format': date_params.get('date_format', '%Y%m%d')
        }

    def _plan_no_date_params(
        self,
        ts_code: str,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """处理无日期参数的下载计划"""
        params = {'ts_code': ts_code}
        if user_params:
            params.update(user_params)

        return [DownloadTask(
            ts_code=ts_code,
            params=params,
            reason='full_history'
        )]

    def _plan_date_range_mode(
        self,
        interface_name: str,
        ts_code: str,
        interface_config: Dict[str, Any],
        date_config: Dict[str, Any],
        existing_dates: set,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """处理 start_date + end_date 模式的下载计划"""
        # 确定日期范围
        if user_params and 'start_date' in user_params:
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
            logger.info(f"[{interface_name}/{ts_code}] 使用用户指定范围: {start_date} ~ {end_date}")
        else:
            start_date, end_date = self._determine_date_range(
                interface_name, ts_code, existing_dates
            )
            logger.info(f"[{interface_name}/{ts_code}] 自动确定范围: {start_date} ~ {end_date}")

        # 如果没有现有数据，全历史下载
        if not existing_dates:
            return [DownloadTask(
                ts_code=ts_code,
                params={
                    'ts_code': ts_code,
                    'start_date': start_date,
                    'end_date': end_date
                },
                reason='full_history'
            )]

        # 检测缺失的日期段
        gaps = self._detect_date_gaps(
            interface_name, ts_code, start_date, end_date,
            existing_dates, date_config['data_date_column']
        )

        if not gaps:
            logger.info(f"[{interface_name}/{ts_code}] 数据已完整覆盖，无需下载")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 发现 {len(gaps)} 个缺失段")

        # 生成下载任务
        tasks = []
        for gap in gaps:
            tasks.append(DownloadTask(
                ts_code=ts_code,
                params={
                    'ts_code': ts_code,
                    'start_date': gap.start_date,
                    'end_date': gap.end_date
                },
                reason='gap_fill'
            ))

        return tasks

    def _plan_trade_date_mode(
        self,
        interface_name: str,
        ts_code: str,
        date_config: Dict[str, Any],
        existing_dates: set,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """处理按单个 trade_date 查询的模式"""
        if user_params and 'start_date' in user_params:
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
        else:
            start_date, end_date = self._determine_date_range(
                interface_name, ts_code, existing_dates
            )

        trade_days = self._get_trade_days(start_date, end_date)
        missing_days = [d for d in trade_days if d not in existing_dates]

        if not missing_days:
            logger.info(f"[{interface_name}/{ts_code}] 所有交易日数据已存在")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 缺失 {len(missing_days)} 个交易日")

        tasks = []
        for trade_date in missing_days:
            tasks.append(DownloadTask(
                ts_code=ts_code,
                params={
                    'ts_code': ts_code,
                    'trade_date': trade_date
                },
                reason='gap_fill'
            ))

        return tasks

    def _plan_period_mode(
        self,
        interface_name: str,
        ts_code: str,
        date_config: Dict[str, Any],
        existing_dates: set,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """处理按报告期（period）查询的模式"""
        if user_params and 'start_date' in user_params:
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
            periods = self._generate_report_periods(start_date, end_date)
        else:
            periods = self._determine_needed_periods(
                interface_name, ts_code, existing_dates
            )

        missing_periods = [p for p in periods if p not in existing_dates]

        if not missing_periods:
            logger.info(f"[{interface_name}/{ts_code}] 所有报告期数据已存在")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 缺失 {len(missing_periods)} 个报告期")

        tasks = []
        date_column = date_config['data_date_column']
        input_mapping = date_config.get('input_mapping', {})
        param_name = input_mapping.get('period', date_column)

        for period in missing_periods:
            tasks.append(DownloadTask(
                ts_code=ts_code,
                params={
                    'ts_code': ts_code,
                    param_name: period
                },
                reason='gap_fill'
            ))

        return tasks

    def _plan_date_anchor_mode(
        self,
        interface_name: str,
        ts_code: str,
        interface_config: Dict[str, Any],
        date_config: Dict[str, Any],
        existing_dates: set,
        user_params: Optional[Dict[str, Any]]
    ) -> List[DownloadTask]:
        """处理日期锚定模式的下载计划（如 disclosure_date）"""
        anchor_param = date_config['anchor_param']

        if user_params and 'start_date' in user_params:
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
            anchor_dates = self._generate_anchor_dates(
                interface_name, start_date, end_date
            )
        else:
            anchor_dates = self._determine_needed_anchors(
                interface_name, ts_code, existing_dates, date_config
            )

        missing_anchors = [d for d in anchor_dates if d not in existing_dates]

        if not missing_anchors:
            logger.info(f"[{interface_name}/{ts_code}] 所有锚点日期数据已存在")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 缺失 {len(missing_anchors)} 个锚点日期")

        tasks = []
        for anchor_date in missing_anchors:
            params = {'ts_code': ts_code, anchor_param: anchor_date}
            tasks.append(DownloadTask(
                ts_code=ts_code,
                params=params,
                reason='gap_fill'
            ))

        return tasks

    def _detect_date_gaps(
        self,
        interface_name: str,
        ts_code: str,
        start_date: str,
        end_date: str,
        existing_dates: set,
        date_column: str
    ) -> List[DateRange]:
        """检测指定股票在日期范围内的缺失段"""
        trade_days = self._get_trade_days(start_date, end_date)

        if not trade_days:
            logger.warning(f"[{interface_name}] 未获取到交易日列表")
            return [DateRange(start_date, end_date)]

        missing_days = [day for day in trade_days if day not in existing_dates]

        if not missing_days:
            return []

        return self._merge_to_ranges(missing_days)

    def _get_existing_dates_for_stock(
        self,
        interface_name: str,
        ts_code: str,
        date_column: str
    ) -> set:
        """获取指定股票已存在的所有日期"""
        try:
            df = self.coverage_manager.storage_manager.read_interface_data(
                interface_name,
                filters={'ts_code': ts_code},
                columns=[date_column]
            )

            if df.is_empty():
                return set()

            dates = set()
            for date_val in df[date_column]:
                formatted = format_date(date_val)
                if formatted:
                    dates.add(formatted)

            return dates

        except Exception as e:
            logger.warning(f"获取 {interface_name}/{ts_code} 的现有日期失败: {e}")
            return set()

    def _determine_date_range(
        self,
        interface_name: str,
        ts_code: str,
        existing_dates: set
    ) -> Tuple[str, str]:
        """自动确定下载的日期范围"""
        end_date = datetime.now().strftime('%Y%m%d')

        if existing_dates:
            latest = max(existing_dates)
            start_date = self._calculate_lookback(latest, interface_name)
            logger.info(f"[{interface_name}/{ts_code}] 从最新日期 {latest} 回溯至 {start_date}")
        else:
            start_date = self._get_default_start_date(interface_name)
            logger.info(f"[{interface_name}/{ts_code}] 无现有数据，使用默认起始日期 {start_date}")

        return start_date, end_date

    def _get_default_start_date(self, interface_name: str) -> str:
        """获取接口的默认起始日期"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            date_params = interface_config.get('date_params', {})
            if 'default_start_date' in date_params:
                return date_params['default_start_date']
        except:
            pass

        defaults = {
            'trade_cal': '19900101',
            'stock_basic': '19900101',
            'daily': '20000101',
            'daily_basic': '20000101',
        }

        for key, value in defaults.items():
            if key in interface_name:
                return value

        return '20000101'

    def _calculate_lookback(self, latest_date: str, interface_name: str) -> str:
        """计算回溯后的起始日期"""
        try:
            lookback_days = 7
            try:
                interface_config = self.config_loader.get_interface_config(interface_name)
                date_params = interface_config.get('date_params', {})
                lookback_days = date_params.get('lookback_days', 7)
            except:
                pass

            latest_dt = datetime.strptime(latest_date, '%Y%m%d')
            start_dt = latest_dt - __import__('datetime').timedelta(days=lookback_days)
            return start_dt.strftime('%Y%m%d')
        except:
            return latest_date

    def _get_trade_days(self, start_date: str, end_date: str) -> List[str]:
        """获取指定范围内的所有交易日"""
        try:
            trade_calendar = self.trade_calendar_provider(start_date, end_date)
            if trade_calendar:
                return [
                    day['cal_date']
                    for day in trade_calendar
                    if day.get('is_open', 0) == 1
                ]
        except Exception as e:
            logger.warning(f"获取交易日历失败: {e}")

        return self._generate_all_days(start_date, end_date)

    def _generate_all_days(self, start_date: str, end_date: str) -> List[str]:
        """生成两个日期之间的所有日期"""
        days = []
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        current = start

        while current <= end:
            days.append(current.strftime('%Y%m%d'))
            current += __import__('datetime').timedelta(days=1)

        return days

    def _merge_to_ranges(self, dates: List[str]) -> List[DateRange]:
        """将日期列表合并为连续的日期范围"""
        if not dates:
            return []

        sorted_dates = sorted(dates)
        ranges = []
        range_start = sorted_dates[0]
        range_end = sorted_dates[0]

        for date in sorted_dates[1:]:
            if self._is_consecutive(range_end, date):
                range_end = date
            else:
                ranges.append(DateRange(range_start, range_end))
                range_start = date
                range_end = date

        ranges.append(DateRange(range_start, range_end))
        return ranges

    def _is_consecutive(self, current: str, next_date: str) -> bool:
        """检查两个日期是否是连续的（考虑周末）"""
        from datetime import datetime, timedelta
        curr_dt = datetime.strptime(current, '%Y%m%d')
        next_dt = datetime.strptime(next_date, '%Y%m%d')
        return (next_dt - curr_dt).days <= 3

    def _generate_report_periods(self, start_date: str, end_date: str) -> List[str]:
        """生成指定范围内的所有报告期（季度末）"""
        periods = []
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        quarter_ends = ['0331', '0630', '0930', '1231']

        for year in range(start_year, end_year + 1):
            for qe in quarter_ends:
                period = f"{year}{qe}"
                if start_date <= period <= end_date:
                    periods.append(period)

        return periods

    def _determine_needed_periods(
        self,
        interface_name: str,
        ts_code: str,
        existing_dates: set
    ) -> List[str]:
        """自动确定需要查询的报告期"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_year = int(end_date[:4]) - 10
        start_date = f"{start_year}0101"

        return self._generate_report_periods(start_date, end_date)

    def _generate_anchor_dates(
        self,
        interface_name: str,
        start_date: str,
        end_date: str
    ) -> List[str]:
        """生成所有可能的锚点日期"""
        return self._generate_report_periods(start_date, end_date)

    def _determine_needed_anchors(
        self,
        interface_name: str,
        ts_code: str,
        existing_dates: set,
        date_config: Dict[str, Any]
    ) -> List[str]:
        """自动确定需要查询的锚点日期"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_year = int(end_date[:4]) - 10
        start_date = f"{start_year}0101"

        return self._generate_anchor_dates(interface_name, start_date, end_date)
```

### 3.2 修改 downloader.py

在 `GenericDownloader` 类中修改 `download_single_stock` 方法：

```python
def download_single_stock(
    self,
    interface_config: Dict[str, Any],
    stock: Dict[str, Any],
    params: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    下载单只股票的数据 - 智能增量版本
    """
    from .stock_loop_planner import StockLoopPlanner

    ts_code = stock['ts_code']
    interface_name = interface_config['api_name']

    # 检查是否需要使用新的智能增量逻辑
    date_params = interface_config.get('date_params', {})
    use_smart_incremental = bool(date_params)

    if not use_smart_incremental:
        # 使用原有逻辑（保持向后兼容）
        return self._download_single_stock_legacy(
            interface_config, stock, params
        )

    # 使用新的智能增量逻辑
    try:
        planner = StockLoopPlanner(
            coverage_manager=self.coverage_manager,
            trade_calendar_provider=self.get_trade_calendar,
            config_loader=self.config_loader
        )

        # 生成下载计划
        tasks = planner.plan_download(
            interface_name=interface_name,
            ts_code=ts_code,
            interface_config=interface_config,
            user_params=params
        )

        if not tasks:
            logger.info(f"[{interface_name}/{ts_code}] 无需下载，数据已完整")
            return []

        # 执行下载任务
        all_data = []
        for task in tasks:
            logger.info(f"[{interface_name}/{ts_code}] {task.reason}: {task.params}")

            data = self._execute_download_with_params(
                interface_config, task.params
            )

            if data:
                all_data.extend(data)

        # 保存数据
        if all_data and self.storage_manager:
            self.storage_manager.add_to_buffer(interface_name, all_data)

        return all_data

    except Exception as e:
        logger.error(f"智能增量下载失败 [{interface_name}/{ts_code}]: {e}")
        # 失败时回退到原有逻辑
        return self._download_single_stock_legacy(
            interface_config, stock, params
        )


def _execute_download_with_params(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """使用指定参数执行下载"""
    try:
        from .pagination import create_context_with_legacy_support
        from .pagination_executor import PaginationExecutor

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
        trade_calendar = self.get_trade_calendar(start_date, end_date)

        pagination_context = create_context_with_legacy_support(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
            stock_list=[{'ts_code': params.get('ts_code')}],
            coverage_manager=self.coverage_manager,
            force_download=self.force_download
        )

        executor = PaginationExecutor()
        data = executor.execute(
            interface_config=interface_config,
            base_params=params,
            context=pagination_context,
            make_request=self._make_request,
            coverage_manager=self.coverage_manager
        )

        return data

    except Exception as e:
        logger.error(f"下载失败: {e}")
        return None
```

---

## 四、接口配置示例

### 4.1 日线数据接口 (date_range 模式)

```yaml
# daily_basic.yaml
api_name: daily_basic
description: 每日指标

date_params:
  mode: "date_range"              # 使用 start_date + end_date 查询
  data_date_column: "trade_date"  # 数据中的日期字段名
  input_mapping:                  # 参数名映射
    start_date: "start_date"
    end_date: "end_date"
  default_start_date: "20000101"  # 默认起始日期
  lookback_days: 7                # 回溯天数（处理数据延迟）

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95

pagination:
  enabled: true
  mode: stock_loop

parameters:
  ts_code:
    type: string
    required: false
  start_date:
    type: string
    required: false
  end_date:
    type: string
    required: false
```

### 4.2 交易日期模式接口 (trade_date 模式)

```yaml
# moneyflow.yaml
api_name: moneyflow
description: 个股资金流向

date_params:
  mode: "trade_date"              # 按单个交易日期查询
  data_date_column: "trade_date"
  input_mapping:
    trade_date: "trade_date"
  default_start_date: "20000101"
  lookback_days: 7

duplicate_detection:
  enabled: true
  date_column: "trade_date"

pagination:
  enabled: true
  mode: stock_loop

parameters:
  ts_code:
    type: string
    required: false
  trade_date:
    type: string
    required: false
```

### 4.3 财报数据接口 (period 模式)

```yaml
# income_vip.yaml
api_name: income_vip
description: 利润表(VIP)

date_params:
  mode: "period"                  # 按报告期查询
  data_date_column: "end_date"    # 数据中的日期字段（报告期）
  input_mapping:
    period: "end_date"            # period 参数映射到 end_date
  default_start_date: "20100101"
  lookback_days: 0                # 财报数据不需要回溯

duplicate_detection:
  enabled: true
  key_columns: [ts_code, end_date]

pagination:
  enabled: true
  mode: stock_loop

parameters:
  ts_code:
    type: string
    required: false
  period:
    type: string
    required: false
```

### 4.4 日期锚定模式接口 (date_anchor 模式)

```yaml
# disclosure_date.yaml
api_name: disclosure_date
description: 财报披露计划

date_params:
  mode: "date_anchor"             # 日期锚定模式
  data_date_column: "end_date"
  anchor_param: "end_date"        # 锚定参数名
  enumerate_dates: true           # 需要遍历所有可能的日期值
  default_start_date: "20100101"

duplicate_detection:
  enabled: true
  key_columns: [ts_code, end_date]

pagination:
  enabled: true
  mode: stock_loop
  date_anchor:
    reverse: true

parameters:
  ts_code:
    type: string
    required: false
  end_date:
    type: string
    required: false
    is_date_anchor: true
```

### 4.5 无日期参数接口 (none 模式)

```yaml
# stock_company.yaml
api_name: stock_company
description: 上市公司基本信息

date_params:
  mode: "none"                    # 无日期参数

duplicate_detection:
  enabled: true
  key_column: "ts_code"

pagination:
  enabled: true
  mode: stock_loop

parameters:
  ts_code:
    type: string
    required: false
  exchange:
    type: string
    required: false
```

---

## 五、集成步骤

### 步骤 1: 复制核心文件

```bash
cp /home/quan/testdata/aspipe_v4/p/2026-2-12/stock_loop_planner.py \
   /home/quan/testdata/aspipe_v4/app4/core/stock_loop_planner.py
```

### 步骤 2: 修改 downloader.py

1. 在文件顶部添加导入：
```python
from .stock_loop_planner import StockLoopPlanner, DownloadTask
```

2. 替换 `download_single_stock` 方法（见 3.2 节代码）

### 步骤 3: 为接口添加 date_params 配置

编辑 `/home/quan/testdata/aspipe_v4/app4/config/interfaces/*.yaml`，添加 `date_params` 配置。

**优先配置的接口：**
1. 高频使用：`daily`, `daily_basic`, `moneyflow`
2. 财报类：`income_vip`, `balancesheet_vip`, `cashflow_vip`
3. 其他：`disclosure_date`, `block_trade`

---

## 六、测试验证

### 6.1 测试全历史下载

```bash
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface daily_basic --ts_code 000001.SZ
```

**预期输出：**
```
[daily_basic/000001.SZ] 日期参数模式: date_range
[daily_basic/000001.SZ] 已有数据: 0 天
[daily_basic/000001.SZ] 无现有数据，使用默认起始日期 20000101
[daily_basic/000001.SZ] 自动确定范围: 20000101 ~ 20260212
[daily_basic/000001.SZ] full_history: {'ts_code': '000001.SZ', 'start_date': '20000101', 'end_date': '20260212'}
```

### 6.2 测试增量下载

再次运行相同命令：

```bash
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface daily_basic --ts_code 000001.SZ
```

**预期输出：**
```
[daily_basic/000001.SZ] 日期参数模式: date_range
[daily_basic/000001.SZ] 已有数据: 5000 天
[daily_basic/000001.SZ] 从最新日期 20250201 回溯至 20250125
[daily_basic/000001.SZ] 自动确定范围: 20250125 ~ 20260212
[daily_basic/000001.SZ] 发现 1 个缺失段
[daily_basic/000001.SZ] gap_fill: {'ts_code': '000001.SZ', 'start_date': '20250202', 'end_date': '20260212'}
```

### 6.3 测试数据完整时跳过

```
[daily_basic/000001.SZ] 日期参数模式: date_range
[daily_basic/000001.SZ] 已有数据: 5800 天
[daily_basic/000001.SZ] 数据已完整覆盖，无需下载
```

---

## 七、配置字段说明

| 字段 | 说明 | 可选值 |
|------|------|--------|
| `mode` | 参数模式 | `date_range`, `trade_date`, `period`, `date_anchor`, `none` |
| `data_date_column` | 数据中的日期字段名 | `trade_date`, `end_date`, `ann_date`, `cal_date` |
| `input_mapping` | 参数名映射 | 如 `{period: end_date}` |
| `anchor_param` | 日期锚定参数名 | 如 `end_date` |
| `enumerate_dates` | 是否遍历所有日期 | `true`, `false` |
| `default_start_date` | 默认起始日期 | 如 `20000101` |
| `lookback_days` | 回溯天数 | 如 `7` |

---

## 八、优势总结

1. **智能参数生成**：根据接口配置自动生成正确的参数，无需硬编码
2. **精确缺口检测**：基于实际数据日期检测缺失，而非简单判断股票是否存在
3. **灵活配置**：通过 YAML 配置支持各种接口类型，无需修改代码
4. **向后兼容**：现有接口无需修改即可工作，新配置是可选的
