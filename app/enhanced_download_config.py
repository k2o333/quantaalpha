"""
增强下载配置文件
包含优先级、重试次数、API参数等高级配置选项，同时保持与原有配置的兼容性
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

# 从原有配置中导入，保持向后兼容
from download_config import DOWNLOAD_CONFIG as ORIGINAL_DOWNLOAD_CONFIG


class DataTypePriority(Enum):
    """数据类型优先级枚举"""
    HIGH = 1      # 高优先级：关键数据，必须下载
    MEDIUM = 2    # 中等优先级：重要数据，建议下载
    LOW = 3       # 低优先级：可选数据，可跳过


class DownloadStrategy(Enum):
    """下载策略枚举"""
    BATCH = "batch"           # 批量下载
    PARALLEL = "parallel"     # 并行下载
    SEQUENTIAL = "sequential" # 顺序下载
    PAGINATED = "paginated"   # 分页下载


@dataclass
class InterfaceConfig:
    """单个接口配置"""
    enabled: bool = True                           # 是否启用此接口
    priority: DataTypePriority = DataTypePriority.MEDIUM  # 优先级
    max_retries: int = 3                         # 最大重试次数
    timeout: int = 30                            # 超时时间（秒）
    rate_limit: float = 2.0                      # 速率限制（请求/秒）
    strategy: DownloadStrategy = DownloadStrategy.SEQUENTIAL  # 下载策略
    batch_size: int = 100                        # 批处理大小
    concurrency: int = 1                         # 并发数量
    required_points: int = 0                     # 所需积分
    api_params: Dict[str, Any] = field(default_factory=dict)  # 特定API参数
    cache_enabled: bool = True                   # 是否启用缓存
    cache_ttl_hours: int = 24                    # 缓存有效时间（小时）
    requires_tscode: bool = False                # 是否需要ts_code参数


# 增强配置结构，支持优先级、重试次数等功能
DOWNLOAD_PIPELINE_CONFIG = {
    # 高优先级接口
    'trade_cal': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('trade_cal', True),
        priority=DataTypePriority.HIGH,
        max_retries=5,
        strategy=DownloadStrategy.BATCH,
        required_points=120
    ),
    'stock_basic': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stock_basic', True),
        priority=DataTypePriority.HIGH,
        max_retries=3,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000
    ),

    # 日度数据接口 - 高优先级
    'daily': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('daily', True),
        priority=DataTypePriority.HIGH,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=8,
        required_points=2000
    ),
    'daily_basic': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('daily_basic', True),
        priority=DataTypePriority.HIGH,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=2000
    ),

    # 资金流接口 - 中等优先级
    'moneyflow': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=6,
        required_points=2000
    ),
    'moneyflow_dc': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow_dc', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=6,
        required_points=5000
    ),
    'moneyflow_ind_dc': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow_ind_dc', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=5000
    ),
    'moneyflow_mkt_dc': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow_mkt_dc', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=5000
    ),

    # 技术因子接口 - 中等优先级
    'stk_factor': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stk_factor', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=5000,
        required_points=2000
    ),
    'stk_factor_pro': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stk_factor_pro', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=5000,
        required_points=5000
    ),
    'pro_bar': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('pro_bar', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=5000,
        requires_tscode=True
    ),

    # 芯片分布接口 - 低优先级（已暂时禁用）
    'cyq_perf': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('cyq_perf', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=5000
    ),
    'cyq_chips': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('cyq_chips', False),  # 暂时禁用
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=5000
    ),

    # 静态数据接口
    'new_share': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('new_share', True),
        priority=DataTypePriority.HIGH,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=120
    ),
    'stock_company': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stock_company', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000
    ),
    'stock_st': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stock_st', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=3000
    ),
    'bak_basic': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('bak_basic', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=5000
    ),

    # 财务数据接口 - 中等优先级
    'income': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('income', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=2000
    ),
    'balancesheet': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('balancesheet', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=2000
    ),
    'cashflow': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('cashflow', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=2000
    ),
    'fina_indicator': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('fina_indicator', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=3,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=2000
    ),
    'dividend': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('dividend', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000
    ),
    'forecast': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('forecast', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000
    ),
    'express': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('express', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000
    ),

    # 股东数据接口
    'top10_holders': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('top10_holders', True),
        priority=DataTypePriority.MEDIUM,
        max_retries=2,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=2000,
        requires_tscode=True
    ),
    'top10_floatholders': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('top10_floatholders', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=3000
    ),

    # 研究数据接口
    'stk_surv': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stk_surv', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=5000
    ),
    'stk_rewards': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stk_rewards', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000,
        requires_tscode=True
    ),
    'stk_managers': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('stk_managers', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=2000
    ),
    'namechange': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('namechange', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=120
    ),
    'pledge_detail': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('pledge_detail', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PAGINATED,
        batch_size=1000,
        required_points=5000,
        requires_tscode=True
    ),

    # 东财资金流接口 - 低优先级（已禁用）
    'moneyflow_ths': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow_ths', False),  # 已禁用
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=5000
    ),
    'moneyflow_cnt_ths': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow_cnt_ths', False),  # 已禁用
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=5000
    ),
    'moneyflow_ind_ths': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('moneyflow_ind_ths', False),  # 已禁用
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.PARALLEL,
        concurrency=4,
        required_points=5000
    ),

    # 研报接口 - 低优先级
    'report_rc': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('report_rc', False),  # 已禁用
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=5000
    ),
    'broker_recommend': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('broker_recommend', False),  # 已禁用
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=600
    ),
    'fina_audit': InterfaceConfig(
        enabled=ORIGINAL_DOWNLOAD_CONFIG.get('fina_audit', True),
        priority=DataTypePriority.LOW,
        max_retries=2,
        strategy=DownloadStrategy.SEQUENTIAL,
        required_points=500,
        requires_tscode=True
    )
}


def get_config_for_points(points: int) -> Dict[str, InterfaceConfig]:
    """
    根据用户积分动态过滤可用接口配置
    """
    filtered_config = {}
    for interface_name, config in DOWNLOAD_PIPELINE_CONFIG.items():
        if config.enabled and points >= config.required_points:
            filtered_config[interface_name] = config
    return filtered_config


def get_interface_config(interface_name: str) -> Optional[InterfaceConfig]:
    """
    获取特定接口的配置
    """
    return DOWNLOAD_PIPELINE_CONFIG.get(interface_name)


def get_interfaces_by_priority(priority: DataTypePriority) -> List[str]:
    """
    根据优先级获取接口列表
    """
    interfaces = []
    for interface_name, config in DOWNLOAD_PIPELINE_CONFIG.items():
        if config.priority == priority and config.enabled:
            interfaces.append(interface_name)
    return interfaces


def get_interfaces_by_strategy(strategy: DownloadStrategy) -> List[str]:
    """
    根据下载策略获取接口列表
    """
    interfaces = []
    for interface_name, config in DOWNLOAD_PIPELINE_CONFIG.items():
        if config.strategy == strategy and config.enabled:
            interfaces.append(interface_name)
    return interfaces


def get_high_priority_interfaces() -> List[str]:
    """
    获取高优先级接口列表
    """
    return get_interfaces_by_priority(DataTypePriority.HIGH)


def get_medium_priority_interfaces() -> List[str]:
    """
    获取中优先级接口列表
    """
    return get_interfaces_by_priority(DataTypePriority.MEDIUM)


def get_low_priority_interfaces() -> List[str]:
    """
    获取低优先级接口列表
    """
    return get_interfaces_by_priority(DataTypePriority.LOW)


def get_parallel_download_interfaces() -> List[str]:
    """
    获取支持并行下载的接口列表
    """
    return get_interfaces_by_strategy(DownloadStrategy.PARALLEL)


def get_paginated_download_interfaces() -> List[str]:
    """
    获取支持分页下载的接口列表
    """
    return get_interfaces_by_strategy(DownloadStrategy.PAGINATED)


# 为了保持向后兼容，提供一个函数将增强配置转换为原配置格式
def get_original_format_config() -> Dict[str, bool]:
    """
    获取兼容原有格式的配置（仅包含启用状态）
    """
    return {name: config.enabled for name, config in DOWNLOAD_PIPELINE_CONFIG.items()}


# 确保模块级别的兼容性
ENHANCED_DOWNLOAD_CONFIG = DOWNLOAD_PIPELINE_CONFIG