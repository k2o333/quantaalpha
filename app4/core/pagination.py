"""
分页参数组合器 - 将多个分页维度组合成一个参数流
支持向后兼容，自动转换旧配置
"""

import logging
from typing import Dict, Any, List, Iterator, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

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
    coverage_manager: Optional[Any] = None
    force_download: bool = False
    user_provided_dates: bool = False  # 用户是否显式提供了日期
    
    @property
    def pagination_config(self) -> Dict[str, Any]:
        return self.interface_config.get('pagination', {})
    
    @property
    def interface_name(self) -> str:
        return self.interface_config.get('name', '')


class PaginationComposer:
    """
    分页组合器 - 将多个分页维度组合成一个参数流
    
    支持的分页维度：
    1. time_range - 时间窗口递归
    2. stock_loop - 股票代码遍历
    3. type_split - 字段分类分割
    4. offset - 记录偏移分页
    
    执行顺序（从内到外）：time → stock → type → offset
    """
    
    # 窗口大小单位映射（转换为天数）
    WINDOW_UNITS = {
        'd': 1, 'w': 7, 'm': 30, 'q': 90, 'y': 365
    }
    
    def __init__(self, context: PaginationContext):
        """
        初始化分页组合器
        
        Args:
            context: 分页上下文，包含接口配置和必要数据
        """
        self.context = context
        self.config = context.pagination_config
        self.interface_config = context.interface_config
    
    def compose(self, base_params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        组合所有启用的分页维度
        
        Args:
            base_params: 基础请求参数
            
        Yields:
            组合后的请求参数
        """
        params_stream = [base_params]
        
        # 检查是否是日期锚定接口（类型 C）
        # 日期锚定接口不支持 start_date/end_date 参数，应跳过 time_range 处理
        is_date_anchor_interface = self._is_date_anchor_interface()
        
        # 1. 时间维度（最内层）- 日期锚定接口跳过
        if self._is_enabled('time_range') and not is_date_anchor_interface:
            params_stream = list(self._apply_time_range(params_stream))
        
        # 2. 股票维度
        if self._is_enabled('stock_loop'):
            params_stream = list(self._apply_stock_loop(params_stream))
        
        # 3. 分类维度
        if self._is_enabled('type_split'):
            params_stream = list(self._apply_type_split(params_stream))
        
        # 4. 偏移量维度（最外层）
        if self._is_enabled('offset'):
            params_stream = list(self._apply_offset(params_stream))
        
        yield from params_stream
    
    def _is_date_anchor_interface(self) -> bool:
        """
        检查是否是日期锚定接口（类型 C）
        
        日期锚定接口的特点：有参数标记为 is_date_anchor: true
        这类接口不支持 start_date/end_date 范围查询
        
        Returns:
            True 表示是日期锚定接口
        """
        parameters = self.interface_config.get('parameters', {})
        return any(p.get('is_date_anchor', False) for p in parameters.values())
    
    def _is_enabled(self, dimension: str) -> bool:
        """
        检查某个维度是否启用
        
        Args:
            dimension: 维度名称
            
        Returns:
            是否启用
        """
        dim_config = self.config.get(dimension, {})
        return dim_config.get('enabled', False) if dim_config else False
    
    def _apply_time_range(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """
        应用时间范围维度
        
        Args:
            params_stream: 参数流
            
        Yields:
            应用时间范围后的参数
        """
        time_config = self.config['time_range']
        window_str = time_config.get('window', '365d')
        reverse = time_config.get('reverse', False)
        window_days = self._parse_window(window_str)
        
        for params in params_stream:
            start_date = params.get('start_date', '20050101')
            end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
            trade_days = self._get_trade_days(start_date, end_date)
            
            if not trade_days:
                yield params
                continue
            
            trade_days.sort(key=lambda x: x['cal_date'], reverse=reverse)
            
            for i in range(0, len(trade_days), window_days):
                window_days_list = trade_days[i:i + window_days]
                window_dates = [d['cal_date'] for d in window_days_list]
                window_start, window_end = min(window_dates), max(window_dates)
                
                window_params = params.copy()
                window_params['start_date'] = window_start
                window_params['end_date'] = window_end
                window_params['_time_window'] = (window_start, window_end)
                yield window_params
    
    def _apply_stock_loop(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """
        应用股票循环维度 - 增强版（支持四种缺口检测模式）
        
        Args:
            params_stream: 参数流
            
        Yields:
            应用股票循环后的参数
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

                    # 从 context 获取 user_provided_dates 标记，支持向后兼容从 params 获取
                    user_provided_dates = self.context.user_provided_dates or params.get('_user_provided_dates', False)

                    gap_tasks = self.context.coverage_manager.detect_stock_gaps(
                        self.interface_config.get('api_name', ''),
                        ts_code,
                        start_date,
                        end_date,
                        self.interface_config,
                        user_provided_dates=user_provided_dates,
                        stock_info=stock
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
    
    def _apply_type_split(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """
        应用分类分割维度
        
        Args:
            params_stream: 参数流
            
        Yields:
            应用分类分割后的参数
        """
        type_config = self.config['type_split']
        field = type_config.get('field', 'type')
        values = type_config.get('values', [])
        
        if not values:
            yield from params_stream
            return
        
        for params in params_stream:
            for val in values:
                type_params = params.copy()
                type_params[field] = val
                type_params['_type_field'] = field
                type_params['_type_value'] = val
                yield type_params
    
    def _apply_offset(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
        """
        应用偏移量维度
        
        Args:
            params_stream: 参数流
            
        Yields:
            应用偏移量后的参数
        """
        offset_config = self.config['offset']
        limit = offset_config.get('limit', 5000)
        
        for params in params_stream:
            params['_offset_pagination'] = {
                'enabled': True,
                'limit': limit,
                'current_offset': 0
            }
            yield params
    
    def _parse_window(self, window_str: str) -> int:
        """
        解析窗口大小字符串为天数
        
        Args:
            window_str: 窗口大小字符串，如 '30d', '1m', '1y'
            
        Returns:
            天数
        """
        if not window_str:
            return 365
        window_str = str(window_str).lower().strip()
        if window_str[-1] in self.WINDOW_UNITS:
            return int(window_str[:-1]) * self.WINDOW_UNITS[window_str[-1]]
        return int(window_str)
    
    def _get_trade_days(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        获取交易日列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            交易日列表
        """
        if not self.context.trade_calendar:
            return []
        return [
            day for day in self.context.trade_calendar
            if day.get('is_open', 0) == 1 and start_date <= day['cal_date'] <= end_date
        ]
    
    def _stock_data_exists(self, ts_code: str) -> bool:
        """
        检查股票数据是否已存在
        
        Args:
            ts_code: 股票代码
            
        Returns:
            是否存在
        """
        if self.context.coverage_manager:
            # 使用 should_skip 方法检查股票数据是否存在
            stock_params = {'ts_code': ts_code}
            return self.context.coverage_manager.should_skip(
                self.context.interface_config.get('api_name', ''),
                stock_params,
                strategy='stock'
            )
        return False


class ParameterGenerator:
    def __init__(self, context: PaginationContext):
        self.context = context
        self.interface_config = context.interface_config
        self.pagination_config = self.interface_config.get('pagination', {})
        self.parameter_config = self.interface_config.get('parameters', {})

    def generate_stock_date_anchor_params(self, base_params: Dict[str, Any], existing_stocks_checker=None):
        start_date = base_params.get('start_date')
        end_date = base_params.get('end_date')
        date_anchor_param = base_params.get('_date_anchor_param')

        if not start_date or not end_date or not date_anchor_param:
            logger.error("Missing required parameters for date anchor generation")
            return []

        stock_list = self.context.stock_list
        if not stock_list:
            logger.error("Stock list not provided")
            return []

        window_size_days = self._get_window_size_days()
        date_points = self._generate_date_points_by_type(start_date, end_date, date_anchor_param, window_size_days)

        if not date_points:
            logger.warning("No date points generated for date anchor parameters")
            return []

        generated = []
        for stock in stock_list:
            ts_code = stock.get('ts_code')
            if not ts_code:
                continue
            if existing_stocks_checker and existing_stocks_checker(self.context.interface_name, ts_code):
                continue

            for date_point in date_points:
                params = {k: v for k, v in base_params.items() if not k.startswith('_')}
                params.pop('start_date', None)
                params.pop('end_date', None)
                params['ts_code'] = ts_code
                params[date_anchor_param] = date_point
                params['_stock_info'] = stock
                generated.append((params, stock))

        return generated

    def _get_window_size_days(self) -> int:
        window_size_days = self.pagination_config.get('window_size_days', 365)
        try:
            return int(window_size_days)
        except Exception:
            return 365

    def _generate_date_points_by_type(self, start_date: str, end_date: str, date_anchor_param: str, window_size_days: int) -> List[str]:
        if not date_anchor_param:
            return []

        if date_anchor_param == 'period' or self._is_report_period_anchor(date_anchor_param):
            date_points = self._generate_quarter_end_dates(start_date, end_date)
        elif date_anchor_param == 'trade_date':
            date_points = self._get_trade_dates(start_date, end_date)
        else:
            date_points = self._generate_window_end_dates(start_date, end_date, window_size_days)

        if self.pagination_config.get('date_anchor', {}).get('reverse', False):
            date_points = list(reversed(date_points))

        return date_points

    def _is_report_period_anchor(self, date_anchor_param: str) -> bool:
        if date_anchor_param != 'end_date':
            return False
        param_def = self.parameter_config.get('end_date', {})
        description = str(param_def.get('description', ''))
        if '报告期' in description or '季度' in description:
            return True
        return self.interface_config.get('name') == 'disclosure_date'

    def _generate_quarter_end_dates(self, start_date: str, end_date: str) -> List[str]:
        try:
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
        except Exception:
            return []

        quarter_ends = []
        for year in range(start_dt.year, end_dt.year + 1):
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                try:
                    q_dt = datetime(year, month, day)
                except ValueError:
                    continue
                if start_dt <= q_dt <= end_dt:
                    quarter_ends.append(q_dt.strftime('%Y%m%d'))
        return quarter_ends

    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        trade_days = self._get_trade_days(start_date, end_date)
        if trade_days:
            trade_days.sort(key=lambda x: x['cal_date'])
            return [d['cal_date'] for d in trade_days]
        return self._generate_daily_dates(start_date, end_date)

    def _generate_window_end_dates(self, start_date: str, end_date: str, window_size_days: int) -> List[str]:
        trade_days = self._get_trade_days(start_date, end_date)
        if trade_days:
            trade_days.sort(key=lambda x: x['cal_date'])
            dates = [d['cal_date'] for d in trade_days]
        else:
            dates = self._generate_daily_dates(start_date, end_date)

        if not dates:
            return []

        step = max(1, window_size_days)
        window_ends = []
        for i in range(0, len(dates), step):
            window_ends.append(dates[min(i + step, len(dates)) - 1])
        return window_ends

    def _get_trade_days(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        if not self.context.trade_calendar:
            return []
        return [
            day for day in self.context.trade_calendar
            if day.get('is_open', 0) == 1 and start_date <= day['cal_date'] <= end_date
        ]

    def _generate_daily_dates(self, start_date: str, end_date: str) -> List[str]:
        try:
            current = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
        except Exception:
            return []

        dates = []
        while current <= end_dt:
            dates.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)
        return dates


def migrate_legacy_config(interface_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    将旧版分页配置迁移为新版配置
    
    Args:
        interface_config: 接口配置
        
    Returns:
        新的分页配置
    """
    old_pagination = interface_config.get('pagination', {})
    
    # 如果已经是新配置格式，直接返回
    if any(key in old_pagination for key in ['time_range', 'stock_loop', 'type_split', 'offset']):
        return old_pagination
    
    mode = old_pagination.get('mode', 'offset')
    new_config = {'enabled': old_pagination.get('enabled', True)}
    window_size_days = old_pagination.get('window_size_days', 365)
    window_str = f"{window_size_days}d"
    
    if mode == 'offset':
        new_config['offset'] = {
            'enabled': True,
            'limit': old_pagination.get('default_limit', 5000)
        }
    elif mode == 'date_range':
        new_config['time_range'] = {
            'enabled': True, 'window': window_str, 'reverse': False
        }
    elif mode == 'reverse_date_range':
        new_config['time_range'] = {
            'enabled': True,
            'window': window_str,
            'reverse': True,
            'stop_on_empty': old_pagination.get('empty_threshold_days', 90)
        }
    elif mode == 'stock_loop':
        new_config['stock_loop'] = {'enabled': True, 'skip_existing': True}
        new_config['time_range'] = {'enabled': True, 'window': window_str, 'reverse': False}
    elif mode == 'type_split':
        new_config['type_split'] = {
            'enabled': True,
            'field': 'type',
            'values': interface_config.get('type_values', ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK'])
        }
    elif mode == 'period_range':
        new_config['time_range'] = {'enabled': True, 'window': '1q', 'reverse': False}
    elif mode == 'quarterly_range':
        new_config['time_range'] = {'enabled': True, 'window': '1q', 'reverse': False}
    elif mode == 'periodic_range':
        period_type = old_pagination.get('period_type', 'month')
        window_map = {'week': '7d', 'month': '1m', 'quarter': '1q', 'year': '1y'}
        new_config['time_range'] = {
            'enabled': True,
            'window': window_map.get(period_type, '1m'),
            'reverse': False
        }
    elif mode == 'date_range_daily':
        new_config['time_range'] = {'enabled': True, 'window': '1d', 'reverse': False}
    else:
        new_config['offset'] = {'enabled': True, 'limit': 5000}
    
    return new_config

def normalize_pagination_config(pagination_config: Dict[str, Any]) -> Dict[str, Any]:
    if not pagination_config:
        return pagination_config
    normalized = dict(pagination_config)
    time_range = dict(normalized.get('time_range', {}) or {})
    stock_loop = dict(normalized.get('stock_loop', {}) or {})
    has_time_range_keys = any(k in time_range for k in ['window', 'reverse', 'stop_on_empty'])
    if time_range or has_time_range_keys:
        if 'enabled' not in time_range:
            time_range['enabled'] = True
        if 'window' not in time_range:
            window_size_days = normalized.get('window_size_days')
            if window_size_days:
                time_range['window'] = f"{window_size_days}d"
        if 'reverse' not in time_range and stock_loop.get('enabled', False):
            time_range['reverse'] = True
        normalized['time_range'] = time_range
    if stock_loop:
        normalized['stock_loop'] = stock_loop
    return normalized



def create_context_with_legacy_support(interface_config: Dict[str, Any], **kwargs) -> PaginationContext:
    """
    创建分页上下文，自动处理旧版配置
    
    Args:
        interface_config: 接口配置
        **kwargs: 其他参数
        
    Returns:
        分页上下文
    """
    config = interface_config.copy()
    if 'pagination' in config:
        config['pagination'] = normalize_pagination_config(migrate_legacy_config(config))
    return PaginationContext(interface_config=config, **kwargs)
