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
            # 无日期参数，一次性下载
            return self._plan_no_date_params(ts_code, user_params)

        elif date_config['mode'] == 'date_range':
            # start_date + end_date 模式
            return self._plan_date_range_mode(
                interface_name, ts_code, interface_config,
                date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'trade_date':
            # 按单个交易日期查询
            return self._plan_trade_date_mode(
                interface_name, ts_code, date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'period':
            # 按报告期查询（季度）
            return self._plan_period_mode(
                interface_name, ts_code, date_config, existing_dates, user_params
            )

        elif date_config['mode'] == 'date_anchor':
            # 日期锚定模式（如 disclosure_date）
            return self._plan_date_anchor_mode(
                interface_name, ts_code, interface_config,
                date_config, existing_dates, user_params
            )

        else:
            logger.warning(f"未知的日期参数模式: {date_config['mode']}")
            return []

    def _get_date_config(self, interface_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        从接口配置中提取日期参数配置
        """
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
        """
        处理无日期参数的下载计划
        """
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
        """
        处理 start_date + end_date 模式的下载计划
        """
        # 确定日期范围
        if user_params and 'start_date' in user_params:
            # 用户指定了日期范围
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
            logger.info(f"[{interface_name}/{ts_code}] 使用用户指定范围: {start_date} ~ {end_date}")
        else:
            # 自动确定范围
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

        # 合并缺口，生成下载任务
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
        """
        处理按单个 trade_date 查询的模式

        这类接口通常一次只能查一个交易日，需要遍历多个日期
        """
        # 确定日期范围
        if user_params and 'start_date' in user_params:
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
        else:
            start_date, end_date = self._determine_date_range(
                interface_name, ts_code, existing_dates
            )

        # 获取所有需要查询的交易日
        trade_days = self._get_trade_days(start_date, end_date)

        # 过滤已存在的日期
        missing_days = [d for d in trade_days if d not in existing_dates]

        if not missing_days:
            logger.info(f"[{interface_name}/{ts_code}] 所有交易日数据已存在")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 缺失 {len(missing_days)} 个交易日")

        # 生成任务（每个缺失日期一个任务）
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
        """
        处理按报告期（period）查询的模式

        财报类接口通常使用 period 或 end_date 作为查询参数
        """
        # 确定报告期范围
        if user_params and 'start_date' in user_params:
            # 将日期范围转换为报告期列表
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))
            periods = self._generate_report_periods(start_date, end_date)
        else:
            # 自动生成需要查询的报告期
            periods = self._determine_needed_periods(
                interface_name, ts_code, existing_dates
            )

        # 过滤已存在的报告期
        missing_periods = [p for p in periods if p not in existing_dates]

        if not missing_periods:
            logger.info(f"[{interface_name}/{ts_code}] 所有报告期数据已存在")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 缺失 {len(missing_periods)} 个报告期")

        # 生成任务
        tasks = []
        date_column = date_config['data_date_column']
        input_mapping = date_config.get('input_mapping', {})

        # 确定参数名（period 或 end_date）
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
        """
        处理日期锚定模式的下载计划（如 disclosure_date）

        这类接口特点：
        - 使用某个日期参数作为锚点（如 end_date）
        - 需要遍历所有可能的锚点值来获取完整数据
        """
        anchor_param = date_config['anchor_param']

        if user_params and 'start_date' in user_params:
            # 用户指定了范围
            start_date = user_params['start_date']
            end_date = user_params.get('end_date', datetime.now().strftime('%Y%m%d'))

            # 生成所有可能的锚点日期（如所有报告期）
            anchor_dates = self._generate_anchor_dates(
                interface_name, start_date, end_date
            )
        else:
            # 自动确定需要查询的锚点日期
            anchor_dates = self._determine_needed_anchors(
                interface_name, ts_code, existing_dates, date_config
            )

        # 过滤已存在的日期
        missing_anchors = [
            d for d in anchor_dates
            if d not in existing_dates
        ]

        if not missing_anchors:
            logger.info(f"[{interface_name}/{ts_code}] 所有锚点日期数据已存在")
            return []

        logger.info(f"[{interface_name}/{ts_code}] 缺失 {len(missing_anchors)} 个锚点日期")

        # 生成任务（可以批量或单个）
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
        """
        检测指定股票在日期范围内的缺失段
        """
        # 获取期望的交易日列表
        trade_days = self._get_trade_days(start_date, end_date)

        if not trade_days:
            logger.warning(f"[{interface_name}] 未获取到交易日列表")
            return [DateRange(start_date, end_date)]

        # 找出缺失的交易日
        missing_days = [
            day for day in trade_days
            if day not in existing_dates
        ]

        if not missing_days:
            return []

        # 合并连续的缺失日期为范围
        return self._merge_to_ranges(missing_days)

    def _get_existing_dates_for_stock(
        self,
        interface_name: str,
        ts_code: str,
        date_column: str
    ) -> set:
        """
        获取指定股票已存在的所有日期
        """
        try:
            # 从 storage 读取该股票的数据
            df = self.coverage_manager.storage_manager.read_interface_data(
                interface_name,
                filters={'ts_code': ts_code},
                columns=[date_column]
            )

            if df.is_empty():
                return set()

            # 提取并格式化日期
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
        """
        自动确定下载的日期范围
        """
        # 结束日期：今天
        end_date = datetime.now().strftime('%Y%m%d')

        # 起始日期：根据接口配置或默认值
        if existing_dates:
            # 有数据，从最新数据日期开始（留一定回溯）
            latest = max(existing_dates)
            start_date = self._calculate_lookback(latest, interface_name)
            logger.info(f"[{interface_name}/{ts_code}] 从最新日期 {latest} 回溯至 {start_date}")
        else:
            # 无数据，使用接口默认起始日期
            start_date = self._get_default_start_date(interface_name)
            logger.info(f"[{interface_name}/{ts_code}] 无现有数据，使用默认起始日期 {start_date}")

        return start_date, end_date

    def _get_default_start_date(self, interface_name: str) -> str:
        """
        获取接口的默认起始日期
        """
        # 从配置中获取
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            date_params = interface_config.get('date_params', {})
            if 'default_start_date' in date_params:
                return date_params['default_start_date']
        except:
            pass

        # 预定义默认值
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
        """
        计算回溯后的起始日期
        """
        try:
            # 从配置获取回溯天数
            lookback_days = 7  # 默认7天
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
        """
        获取指定范围内的所有交易日
        """
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

        # 如果获取失败，生成所有日期（包含周末）
        return self._generate_all_days(start_date, end_date)

    def _generate_all_days(self, start_date: str, end_date: str) -> List[str]:
        """
        生成两个日期之间的所有日期（包含首尾）
        """
        days = []
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        current = start

        while current <= end:
            days.append(current.strftime('%Y%m%d'))
            current += __import__('datetime').timedelta(days=1)

        return days

    def _merge_to_ranges(self, dates: List[str]) -> List[DateRange]:
        """
        将日期列表合并为连续的日期范围
        """
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
        """
        检查两个日期是否是连续的（考虑周末）
        """
        from datetime import datetime, timedelta
        curr_dt = datetime.strptime(current, '%Y%m%d')
        next_dt = datetime.strptime(next_date, '%Y%m%d')
        # 简化处理：日期差 <= 3天认为是连续的（考虑周末）
        return (next_dt - curr_dt).days <= 3

    def _generate_report_periods(self, start_date: str, end_date: str) -> List[str]:
        """
        生成指定范围内的所有报告期（季度末）
        """
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
        """
        自动确定需要查询的报告期
        """
        # 默认查询最近10年的报告期
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
        """
        生成所有可能的锚点日期

        默认生成报告期列表，子类可覆盖
        """
        return self._generate_report_periods(start_date, end_date)

    def _determine_needed_anchors(
        self,
        interface_name: str,
        ts_code: str,
        existing_dates: set,
        date_config: Dict[str, Any]
    ) -> List[str]:
        """
        自动确定需要查询的锚点日期
        """
        end_date = datetime.now().strftime('%Y%m%d')
        start_year = int(end_date[:4]) - 10
        start_date = f"{start_year}0101"

        return self._generate_anchor_dates(interface_name, start_date, end_date)
