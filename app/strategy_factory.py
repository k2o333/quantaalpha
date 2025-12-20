"""
策略工厂
提供统一的策略创建接口，支持策略注册和获取，实现策略缓存机制
"""
from typing import Dict, Type, Any, Optional, Union
from abc import ABC
import logging


class StrategyFactory:
    """
    策略工厂类，用于创建和管理不同的下载策略实例
    """

    def __init__(self):
        self._strategies: Dict[str, Optional[object]] = {}  # Use object to avoid forward reference
        self._strategy_types: Dict[str, Type] = {}  # Initialize empty, populate later
        self.logger = logging.getLogger(__name__)

        # 设置策略类型映射（使用字符串避免循环引用）
        self._setup_strategy_types()

    def _setup_strategy_types(self):
        """延迟设置策略类型映射"""
        from download_strategies import DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy
        self._strategy_types = {
            'daily': DailyDataStrategy,
            'daily_basic': DailyDataStrategy,
            'moneyflow': DailyDataStrategy,
            'moneyflow_dc': DailyDataStrategy,
            'moneyflow_ths': DailyDataStrategy,
            'moneyflow_ind_dc': DailyDataStrategy,
            'moneyflow_mkt_dc': DailyDataStrategy,
            'moneyflow_cnt_ths': DailyDataStrategy,
            'moneyflow_ind_ths': DailyDataStrategy,
            'stk_factor': DailyDataStrategy,
            'stk_factor_pro': DailyDataStrategy,
            'cyq_perf': DailyDataStrategy,
            'cyq_chips': DailyDataStrategy,
            'income': FinancialDataStrategy,
            'balancesheet': FinancialDataStrategy,
            'cashflow': FinancialDataStrategy,
            'fina_indicator': FinancialDataStrategy,
            'dividend': FinancialDataStrategy,
            'forecast': FinancialDataStrategy,
            'express': FinancialDataStrategy,
            'top10_holders': FinancialDataStrategy,
            'top10_floatholders': FinancialDataStrategy,
            'stk_surv': FinancialDataStrategy,
            'stock_basic': StaticDataStrategy,
            'trade_cal': StaticDataStrategy,
            'new_share': StaticDataStrategy,
            'stock_company': StaticDataStrategy,
            'stock_st': StaticDataStrategy,
            'bak_basic': StaticDataStrategy,
            'namechange': StaticDataStrategy,
            'stk_rewards': StaticDataStrategy,
            'stk_managers': StaticDataStrategy,
            'broker_recommend': StaticDataStrategy,
        }

    def register_strategy(self, interface_name: str, strategy_class: Type):
        """
        注册新的策略类型
        """
        self._strategy_types[interface_name] = strategy_class
        self.logger.info(f"注册策略: {interface_name} -> {strategy_class.__name__}")

    def create_strategy(self, interface_name: str, **kwargs):
        """
        根据接口名称创建相应的下载策略
        """
        # 延迟导入以避免循环引用
        from download_strategies import DailyDataStrategy
        strategy_class = self._strategy_types.get(interface_name)

        if strategy_class is None:
            self.logger.warning(f"未找到接口 {interface_name} 的专用策略，使用默认日度数据策略")
            strategy_class = DailyDataStrategy

        # 创建策略实例
        strategy = strategy_class(interface_name, **kwargs)

        # 缓存策略实例（使用接口名作为缓存键）
        cache_key = f"{interface_name}_{hash(frozenset(kwargs.items())) if kwargs else 0}"
        self._strategies[cache_key] = strategy

        return strategy

    def get_strategy(self, interface_name: str, **kwargs):
        """
        获取指定接口的下载策略（如果不存在则创建）
        """
        cache_key = f"{interface_name}_{hash(frozenset(kwargs.items())) if kwargs else 0}"

        # 先尝试从缓存中获取
        if cache_key in self._strategies:
            return self._strategies[cache_key]

        # 如果缓存中没有，则创建新实例
        return self.create_strategy(interface_name, **kwargs)

    def clear_cache(self):
        """
        清除策略缓存
        """
        self._strategies.clear()
        self.logger.info("策略缓存已清除")

    def get_available_interfaces(self) -> list:
        """
        获取所有已注册接口的列表
        """
        return list(self._strategy_types.keys())

    def is_interface_registered(self, interface_name: str) -> bool:
        """
        检查接口是否已注册
        """
        return interface_name in self._strategy_types


# 全局策略工厂实例
_global_strategy_factory = StrategyFactory()


def get_strategy_factory() -> StrategyFactory:
    """
    获取全局策略工厂实例
    """
    return _global_strategy_factory


def create_strategy(interface_name: str, **kwargs):
    """
    创建指定接口的下载策略
    """
    factory = get_strategy_factory()
    return factory.create_strategy(interface_name, **kwargs)


def get_strategy(interface_name: str, **kwargs):
    """
    获取指定接口的下载策略
    """
    factory = get_strategy_factory()
    return factory.get_strategy(interface_name, **kwargs)


def register_strategy_type(interface_name: str, strategy_class: Type):
    """
    注册新的策略类型
    """
    factory = get_strategy_factory()
    factory.register_strategy(interface_name, strategy_class)


def get_available_strategies() -> list:
    """
    获取所有可用策略接口列表
    """
    factory = get_strategy_factory()
    return factory.get_available_interfaces()


def is_strategy_available(interface_name: str) -> bool:
    """
    检查指定策略是否可用
    """
    factory = get_strategy_factory()
    return factory.is_interface_registered(interface_name)