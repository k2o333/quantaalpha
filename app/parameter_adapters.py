"""
参数适配器基础框架
定义参数适配器基类，实现参数验证和标准化功能
"""
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod
import logging
from datetime import datetime
import pandas as pd


class ParameterAdapterBase(ABC):
    """
    参数适配器基类，定义参数验证和标准化的通用接口
    """

    def __init__(self, interface_name: str):
        self.interface_name = interface_name
        self.logger = logging.getLogger(f"{__name__}.{interface_name}")

    @abstractmethod
    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证参数并返回标准化的参数字典
        """
        pass

    @abstractmethod
    def get_required_parameters(self) -> List[str]:
        """
        获取必需的参数列表
        """
        pass

    @abstractmethod
    def get_optional_parameters(self) -> List[str]:
        """
        获取可选的参数列表
        """
        pass

    def normalize_dates(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化日期格式参数
        """
        normalized = params.copy()

        # 检查常见的日期参数名
        date_params = ['start_date', 'end_date', 'trade_date', 'ann_date', 'period', 'report_date']
        for param_name in date_params:
            if param_name in normalized:
                value = normalized[param_name]
                if value:
                    # 确保日期格式为YYYYMMDD
                    normalized[param_name] = self._format_date(value)

        return normalized

    def _format_date(self, date_value: Union[str, datetime]) -> str:
        """
        将日期值格式化为YYYYMMDD格式
        """
        if isinstance(date_value, datetime):
            return date_value.strftime('%Y%m%d')
        elif isinstance(date_value, str):
            # 如果已经是8位数字格式，直接返回
            if len(date_value) == 8 and date_value.isdigit():
                return date_value
            # 尝试解析不同的日期格式
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y%m%d']:
                try:
                    parsed_date = datetime.strptime(date_value, fmt)
                    return parsed_date.strftime('%Y%m%d')
                except ValueError:
                    continue
            # 如果都不能解析，返回原值
            return date_value
        else:
            return str(date_value)

    def validate_and_adapt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证并适配参数（标准化 + 验证）
        """
        # 首先标准化日期
        normalized_params = self.normalize_dates(params)

        # 然后验证参数
        validated_params = self.validate_parameters(normalized_params)

        return validated_params

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        获取默认参数值
        """
        return {}


class DailyDataParameterAdapter(ParameterAdapterBase):
    """
    日度数据参数适配器
    适用于 daily, daily_basic, moneyflow 等接口
    """

    def __init__(self):
        super().__init__('daily')

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证日度数据参数
        """
        validated = params.copy()

        # 检查日期参数
        if 'start_date' in validated and validated['start_date']:
            validated['start_date'] = self._format_date(validated['start_date'])
        if 'end_date' in validated and validated['end_date']:
            validated['end_date'] = self._format_date(validated['end_date'])
        if 'trade_date' in validated and validated['trade_date']:
            validated['trade_date'] = self._format_date(validated['trade_date'])

        # 检查股票代码参数
        if 'ts_code' in validated:
            # 如果传入的是列表，转换为逗号分隔的字符串
            if isinstance(validated['ts_code'], list):
                validated['ts_code'] = ','.join(validated['ts_code'])

        # 如果同时提供了日期范围和单个日期，优先使用日期范围
        if 'start_date' in validated and 'end_date' in validated and validated['start_date'] and validated['end_date']:
            if 'trade_date' in validated and validated['trade_date']:
                # 日期范围优先，忽略单个日期
                del validated['trade_date']

        return validated

    def get_required_parameters(self) -> List[str]:
        """
        日度数据接口通常不需要必需参数（可以获取所有股票）
        """
        return []

    def get_optional_parameters(self) -> List[str]:
        """
        日度数据接口的可选参数
        """
        return ['ts_code', 'start_date', 'end_date', 'trade_date', 'exchange', 'adj', 'freq']

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        获取默认参数
        """
        return {
            'exchange': '',
            'adj': '',
            'freq': ''
        }


class FinancialDataParameterAdapter(ParameterAdapterBase):
    """
    财务数据参数适配器
    适用于 income, balancesheet, cashflow 等接口
    """

    def __init__(self):
        super().__init__('financial')

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证财务数据参数
        """
        validated = params.copy()

        # 检查报告期参数
        if 'period' in validated and validated['period']:
            validated['period'] = self._format_date(validated['period'])
            # 确保报告期是月末日期格式
            period = validated['period']
            if len(period) == 6:  # 如果是YYYYMM格式，补全为月末日期
                try:
                    year = int(period[:4])
                    month = int(period[4:6])
                    from datetime import datetime, timedelta
                    import calendar
                    last_day = calendar.monthrange(year, month)[1]
                    validated['period'] = f"{year}{month:02d}{last_day:02d}"
                except ValueError:
                    pass  # 如果解析失败，保持原值

        # 检查日期范围
        if 'start_date' in validated and validated['start_date']:
            validated['start_date'] = self._format_date(validated['start_date'])
        if 'end_date' in validated and validated['end_date']:
            validated['end_date'] = self._format_date(validated['end_date'])

        # 检查股票代码参数
        if 'ts_code' in validated:
            if isinstance(validated['ts_code'], list):
                validated['ts_code'] = ','.join(validated['ts_code'])

        return validated

    def get_required_parameters(self) -> List[str]:
        """
        财务数据接口通常不需要必需参数
        """
        return []

    def get_optional_parameters(self) -> List[str]:
        """
        财务数据接口的可选参数
        """
        return ['ts_code', 'period', 'report_type', 'start_date', 'end_date', 'comp_type']

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        获取默认参数
        """
        return {
            'report_type': '',
            'comp_type': '1'
        }


class StaticDataParameterAdapter(ParameterAdapterBase):
    """
    静态数据参数适配器
    适用于 stock_basic, trade_cal, namechange 等接口
    """

    def __init__(self):
        super().__init__('static')

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证静态数据参数
        """
        validated = params.copy()

        # 检查日期参数
        if 'start_date' in validated and validated['start_date']:
            validated['start_date'] = self._format_date(validated['start_date'])
        if 'end_date' in validated and validated['end_date']:
            validated['end_date'] = self._format_date(validated['end_date'])

        # 检查交易所参数
        if 'exchange' in validated:
            exchange = validated['exchange']
            if exchange and exchange not in ['SSE', 'SZSE', 'BSE', '']:
                self.logger.warning(f"无效的交易所代码: {exchange}, 使用默认值")
                validated['exchange'] = ''

        # 检查股票代码参数
        if 'ts_code' in validated:
            if isinstance(validated['ts_code'], list):
                validated['ts_code'] = ','.join(validated['ts_code'])

        return validated

    def get_required_parameters(self) -> List[str]:
        """
        静态数据接口通常不需要必需参数
        """
        return []

    def get_optional_parameters(self) -> List[str]:
        """
        静态数据接口的可选参数
        """
        return ['ts_code', 'exchange', 'is_hs', 'list_status', 'delist_date', 'start_date', 'end_date']

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        获取默认参数
        """
        return {
            'exchange': '',
            'is_hs': '',
            'list_status': 'L',
            'delist_date': ''
        }


class MoneyFlowParameterAdapter(ParameterAdapterBase):
    """
    资金流数据参数适配器
    适用于 moneyflow, moneyflow_dc 等接口
    """

    def __init__(self):
        super().__init__('moneyflow')

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证资金流数据参数
        """
        validated = params.copy()

        # 检查日期参数
        if 'trade_date' in validated and validated['trade_date']:
            validated['trade_date'] = self._format_date(validated['trade_date'])
        if 'start_date' in validated and validated['start_date']:
            validated['start_date'] = self._format_date(validated['start_date'])
        if 'end_date' in validated and validated['end_date']:
            validated['end_date'] = self._format_date(validated['end_date'])

        # 检查股票代码参数
        if 'ts_code' in validated:
            if isinstance(validated['ts_code'], list):
                validated['ts_code'] = ','.join(validated['ts_code'])

        return validated

    def get_required_parameters(self) -> List[str]:
        """
        资金流数据接口通常不需要必需参数
        """
        return []

    def get_optional_parameters(self) -> List[str]:
        """
        资金流数据接口的可选参数
        """
        return ['ts_code', 'trade_date', 'start_date', 'end_date']

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        获取默认参数
        """
        return {}


class TechnicalFactorParameterAdapter(ParameterAdapterBase):
    """
    技术因子数据参数适配器
    适用于 stk_factor, stk_factor_pro 等接口
    """

    def __init__(self):
        super().__init__('technical_factor')

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证技术因子数据参数
        """
        validated = params.copy()

        # 检查日期参数
        if 'trade_date' in validated and validated['trade_date']:
            validated['trade_date'] = self._format_date(validated['trade_date'])
        if 'start_date' in validated and validated['start_date']:
            validated['start_date'] = self._format_date(validated['start_date'])
        if 'end_date' in validated and validated['end_date']:
            validated['end_date'] = self._format_date(validated['end_date'])

        # 检查股票代码参数
        if 'ts_code' in validated:
            if isinstance(validated['ts_code'], list):
                validated['ts_code'] = ','.join(validated['ts_code'])

        # 检查因子参数
        valid_factors = ['pe', 'pb', 'ps', 'pcf', 'dv_ratio', 'dv_ttm', 'total_share', 'float_share', 'free_share', 'total_mv', 'circ_mv']
        if 'factor' in validated:
            factor = validated['factor']
            if factor and factor not in valid_factors:
                self.logger.warning(f"无效的技术因子: {factor}, 使用默认值")
                validated['factor'] = ''

        return validated

    def get_required_parameters(self) -> List[str]:
        """
        技术因子数据接口通常不需要必需参数
        """
        return []

    def get_optional_parameters(self) -> List[str]:
        """
        技术因子数据接口的可选参数
        """
        return ['ts_code', 'trade_date', 'start_date', 'end_date', 'factor']

    def get_default_parameters(self) -> Dict[str, Any]:
        """
        获取默认参数
        """
        return {
            'factor': ''
        }


class ParameterAdapterManager:
    """
    参数适配器管理器，根据接口名获取对应的参数适配器
    """

    def __init__(self):
        self.adapters = {
            'daily': DailyDataParameterAdapter(),
            'daily_basic': DailyDataParameterAdapter(),
            'moneyflow': MoneyFlowParameterAdapter(),
            'moneyflow_dc': MoneyFlowParameterAdapter(),
            'moneyflow_ths': MoneyFlowParameterAdapter(),
            'moneyflow_ind_dc': MoneyFlowParameterAdapter(),
            'moneyflow_mkt_dc': MoneyFlowParameterAdapter(),
            'moneyflow_cnt_ths': MoneyFlowParameterAdapter(),
            'moneyflow_ind_ths': MoneyFlowParameterAdapter(),
            'stk_factor': TechnicalFactorParameterAdapter(),
            'stk_factor_pro': TechnicalFactorParameterAdapter(),
            'cyq_perf': DailyDataParameterAdapter(),
            'cyq_chips': DailyDataParameterAdapter(),
            'pro_bar': DailyDataParameterAdapter(),  # pro_bar使用日度数据适配器
            'income': FinancialDataParameterAdapter(),
            'balancesheet': FinancialDataParameterAdapter(),
            'cashflow': FinancialDataParameterAdapter(),
            'fina_indicator': FinancialDataParameterAdapter(),
            'dividend': FinancialDataParameterAdapter(),
            'forecast': FinancialDataParameterAdapter(),
            'express': FinancialDataParameterAdapter(),
            'top10_holders': FinancialDataParameterAdapter(),
            'top10_floatholders': FinancialDataParameterAdapter(),
            'stock_basic': StaticDataParameterAdapter(),
            'trade_cal': StaticDataParameterAdapter(),
            'new_share': StaticDataParameterAdapter(),
            'stock_company': StaticDataParameterAdapter(),
            'stock_st': StaticDataParameterAdapter(),
            'bak_basic': StaticDataParameterAdapter(),
            'stk_surv': FinancialDataParameterAdapter(),
            'stk_rewards': StaticDataParameterAdapter(),
            'stk_managers': StaticDataParameterAdapter(),
            'namechange': StaticDataParameterAdapter(),
            'report_rc': FinancialDataParameterAdapter(),
            'broker_recommend': StaticDataParameterAdapter(),
        }
        self.logger = logging.getLogger(__name__)

    def get_adapter(self, interface_name: str) -> Optional[ParameterAdapterBase]:
        """
        根据接口名获取对应的参数适配器
        """
        adapter = self.adapters.get(interface_name)
        if adapter is None:
            self.logger.warning(f"未找到接口 {interface_name} 的参数适配器，使用默认适配器")
            # 返回一个通用适配器
            return GenericParameterAdapter(interface_name)
        return adapter

    def adapt_parameters(self, interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        适配指定接口的参数
        """
        adapter = self.get_adapter(interface_name)
        return adapter.validate_and_adapt(params)

    def validate_parameters(self, interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证指定接口的参数
        """
        adapter = self.get_adapter(interface_name)
        return adapter.validate_parameters(params)


class GenericParameterAdapter(ParameterAdapterBase):
    """
    通用参数适配器，用于没有特定适配器的接口
    """

    def __init__(self, interface_name: str):
        super().__init__(interface_name)

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        通用参数验证 - 主要进行日期标准化
        """
        return self.normalize_dates(params)

    def get_required_parameters(self) -> List[str]:
        """
        通用适配器无必需参数
        """
        return []

    def get_optional_parameters(self) -> List[str]:
        """
        通用适配器的可选参数
        """
        return []


# 全局参数管理器实例
parameter_manager = ParameterAdapterManager()


def get_parameter_adapter(interface_name: str) -> Optional[ParameterAdapterBase]:
    """
    获取指定接口的参数适配器
    """
    return parameter_manager.get_adapter(interface_name)


def adapt_interface_parameters(interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    适配指定接口的参数
    """
    return parameter_manager.adapt_parameters(interface_name, params)


def validate_interface_parameters(interface_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    验证指定接口的参数
    """
    return parameter_manager.validate_parameters(interface_name, params)


def get_required_parameters(interface_name: str) -> List[str]:
    """
    获取指定接口的必需参数
    """
    adapter = get_parameter_adapter(interface_name)
    if adapter:
        return adapter.get_required_parameters()
    return []


def get_optional_parameters(interface_name: str) -> List[str]:
    """
    获取指定接口的可选参数
    """
    adapter = get_parameter_adapter(interface_name)
    if adapter:
        return adapter.get_optional_parameters()
    return []