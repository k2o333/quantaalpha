"""
分页参数生成器 - 纯逻辑模块，不执行任何网络请求

职责：
- 根据分页策略生成请求参数迭代器
- 不持有任何外部引用
- 所有方法都是纯函数或生成器

注意：此模块仅负责参数生成，不执行任何请求。
请求执行由PaginationExecutor模块负责。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Iterator, Tuple, Optional, Callable
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
        existing_stocks_checker: Optional[Callable[[str, str], bool]] = None
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

            # 检查接口配置
            parameter_config = self.context.interface_config.get('parameters', {})

            # [修正] 只设置 start_date，不自动填充 end_date
            if 'start_date' in parameter_config and 'start_date' not in stock_params:
                list_date = stock.get('list_date', '20050101')
                stock_params['start_date'] = list_date

            # [修正] 不自动填充 end_date
            # if 'end_date' in parameter_config and 'end_date' not in stock_params:
            #     stock_params['end_date'] = datetime.now().strftime('%Y%m%d')

            # 移除不支持的参数
            if 'start_date' not in parameter_config:
                stock_params.pop('start_date', None)
            if 'end_date' not in parameter_config:
                stock_params.pop('end_date', None)

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

    def generate_reverse_date_range_params(
        self,
        base_params: Dict[str, Any],
        start_date: str,
        end_date: str
    ) -> Iterator[Tuple[Dict[str, Any], Tuple[str, str]]]:
        """
        生成反向日期范围分页参数（从最近日期往前）

        Args:
            base_params: 基础参数
            start_date: 开始日期 YYYYMMDD（最老的日期）
            end_date: 结束日期 YYYYMMDD（最近的日期）

        Yields:
            (窗口参数, (window_start, window_end)) 元组，按倒序排列
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

        # 按日期倒序排列（从最近到最远）
        trade_days.sort(key=lambda x: x['cal_date'], reverse=True)

        # 获取窗口大小
        window_size = get_window_size_for_interface(
            self.context.interface_name,
            self.context.interface_config
        )

        logger.info(f"Generating reverse windows for {len(trade_days)} trade days with window size {window_size}")

        # 生成倒序窗口
        for i in range(0, len(trade_days), window_size):
            window_days = trade_days[i:i + window_size]
            if not window_days:
                continue

            # 窗口内日期重新排序，确保start < end
            window_dates = [d['cal_date'] for d in window_days]
            window_start = min(window_dates)
            window_end = max(window_dates)

            window_params = base_params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            yield window_params, (window_start, window_end)


# ==================== 辅助函数（模块级别） ====================

def get_window_size_for_interface(interface_name: str, config: Dict[str, Any] = None) -> int:
    """
    根据接口类型确定窗口大小

    不同接口的数据量差异很大，需要使用不同的窗口大小
    以避免单次请求数据过大或请求次数过多
    """
    # 如果提供了配置，优先使用配置中的设置
    if config:
        pagination_config = config.get('pagination', {})
        if pagination_config.get('enabled', False):
            mode = pagination_config.get('mode', 'offset')
            if mode == 'date_range_daily':
                return 1  # 每次处理一天
            elif mode == 'reverse_date_range':
                # 反向日期范围模式，默认30天
                return pagination_config.get('window_size_days', 30)
            elif mode == 'stock_loop':
                # 可以根据需要调整，比如一次处理30天的数据
                return pagination_config.get('window_size_days', 30)
            else:
                return pagination_config.get('window_size_days', 365)

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