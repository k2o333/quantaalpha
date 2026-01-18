"""
配置适配器
提供统一接口访问新旧配置，实现配置格式转换功能
"""
from typing import Dict, Any, Union, Optional
from pathlib import Path
import logging
import json

from download_config import DOWNLOAD_CONFIG as ORIGINAL_DOWNLOAD_CONFIG
from enhanced_download_config import (
    DOWNLOAD_PIPELINE_CONFIG,
    InterfaceConfig,
    DataTypePriority,
    DownloadStrategy,
    get_config_for_points,
    get_interface_config
)


class ConfigAdapter:
    """
    配置适配器，提供统一接口访问新旧配置格式
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.original_config = ORIGINAL_DOWNLOAD_CONFIG
        self.enhanced_config = DOWNLOAD_PIPELINE_CONFIG
        self.user_points = self._get_user_points()

    def _get_user_points(self) -> int:
        """
        获取用户积分（从配置或环境变量）
        """
        try:
            from config import TUSHARE_POINTS
            return TUSHARE_POINTS
        except ImportError:
            # 默认积分值
            return 2000

    def get_config(self, interface_name: str) -> Optional[Union[bool, InterfaceConfig]]:
        """
        获取接口配置，兼容新旧格式
        """
        # 首先尝试获取增强配置
        enhanced_cfg = get_interface_config(interface_name)
        if enhanced_cfg:
            return enhanced_cfg

        # 如果增强配置中没有，尝试获取原始配置
        if interface_name in self.original_config:
            return self.original_config[interface_name]

        return None

    def is_enabled(self, interface_name: str) -> bool:
        """
        检查接口是否启用（考虑用户积分限制）
        """
        config = self.get_config(interface_name)

        if config is None:
            return False

        # 如果是增强配置对象
        if isinstance(config, InterfaceConfig):
            # 检查是否启用且用户积分满足要求
            return config.enabled and self.user_points >= config.required_points

        # 如果是原始配置（布尔值）
        if isinstance(config, bool):
            return config

        return False

    def get_priority(self, interface_name: str) -> DataTypePriority:
        """
        获取接口优先级
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.priority

        # 默认返回中等优先级
        return DataTypePriority.MEDIUM

    def get_max_retries(self, interface_name: str) -> int:
        """
        获取最大重试次数
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.max_retries

        # 默认返回3次重试
        return 3

    def get_rate_limit(self, interface_name: str) -> float:
        """
        获取速率限制
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.rate_limit

        # 默认返回2.0请求/秒
        return 2.0

    def get_strategy(self, interface_name: str) -> DownloadStrategy:
        """
        获取下载策略
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.strategy

        # 默认返回顺序下载策略
        return DownloadStrategy.SEQUENTIAL

    def get_batch_size(self, interface_name: str) -> int:
        """
        获取批处理大小
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.batch_size

        # 默认返回100
        return 100

    def get_concurrency(self, interface_name: str) -> int:
        """
        获取并发数量
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.concurrency

        # 默认返回1（顺序下载）
        return 1

    def get_api_params(self, interface_name: str) -> Dict[str, Any]:
        """
        获取API特定参数
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.api_params

        # 默认返回空字典
        return {}

    def get_cache_settings(self, interface_name: str) -> Dict[str, Any]:
        """
        获取缓存设置
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return {
                'enabled': config.cache_enabled,
                'ttl_hours': config.cache_ttl_hours
            }

        # 默认返回启用缓存，24小时TTL
        return {
            'enabled': True,
            'ttl_hours': 24
        }

    def get_all_available_interfaces(self) -> Dict[str, InterfaceConfig]:
        """
        获取所有用户积分范围内可用的接口配置
        """
        return get_config_for_points(self.user_points)

    def get_interfaces_by_priority(self, priority: DataTypePriority) -> Dict[str, InterfaceConfig]:
        """
        根据优先级获取接口配置
        """
        available = self.get_all_available_interfaces()
        result = {}

        for name, config in available.items():
            if config.priority == priority:
                result[name] = config

        return result

    def get_interfaces_by_strategy(self, strategy: DownloadStrategy) -> Dict[str, InterfaceConfig]:
        """
        根据下载策略获取接口配置
        """
        available = self.get_all_available_interfaces()
        result = {}

        for name, config in available.items():
            if config.strategy == strategy:
                result[name] = config

        return result

    def validate_config(self) -> Dict[str, Any]:
        """
        验证配置的一致性
        """
        results = {
            'original_config_keys': set(self.original_config.keys()),
            'enhanced_config_keys': set(self.enhanced_config.keys()),
            'missing_in_enhanced': set(),
            'missing_in_original': set(),
            'validation_passed': True
        }

        # 检查原始配置中的接口是否在增强配置中都有对应
        results['missing_in_enhanced'] = results['original_config_keys'] - results['enhanced_config_keys']

        # 检查增强配置中的接口是否在原始配置中都有对应（可选）
        results['missing_in_original'] = results['enhanced_config_keys'] - results['original_config_keys']

        # 如果原始配置中的接口在增强配置中缺失，可能有问题
        if results['missing_in_enhanced']:
            self.logger.warning(f"增强配置中缺少以下原始配置接口: {results['missing_in_enhanced']}")
            results['validation_passed'] = False

        return results

    def get_default_values(self) -> Dict[str, Any]:
        """
        获取默认配置值
        """
        return {
            'max_retries': 3,
            'timeout': 30,
            'rate_limit': 2.0,
            'priority': DataTypePriority.MEDIUM,
            'strategy': DownloadStrategy.SEQUENTIAL,
            'batch_size': 100,
            'concurrency': 1,
            'cache_enabled': True,
            'cache_ttl_hours': 24
        }

    def convert_old_config(self, old_config: Dict[str, bool]) -> Dict[str, InterfaceConfig]:
        """
        将旧配置格式转换为新配置格式
        """
        converted = {}

        for interface_name, enabled in old_config.items():
            # 如果增强配置中已存在此接口，使用其详细配置
            if interface_name in self.enhanced_config:
                config = self.enhanced_config[interface_name]
                # 保持原有启用状态
                new_config = InterfaceConfig(
                    enabled=enabled,
                    priority=config.priority,
                    max_retries=config.max_retries,
                    timeout=config.timeout,
                    rate_limit=config.rate_limit,
                    strategy=config.strategy,
                    batch_size=config.batch_size,
                    concurrency=config.concurrency,
                    required_points=config.required_points,
                    api_params=config.api_params,
                    cache_enabled=config.cache_enabled,
                    cache_ttl_hours=config.cache_ttl_hours
                )
                converted[interface_name] = new_config
            else:
                # 如果是新接口，则使用默认配置
                converted[interface_name] = InterfaceConfig(
                    enabled=enabled,
                    priority=DataTypePriority.MEDIUM,
                    max_retries=3,
                    timeout=30,
                    rate_limit=2.0,
                    strategy=DownloadStrategy.SEQUENTIAL,
                    batch_size=100,
                    concurrency=1,
                    required_points=2000,  # 假设需要2000积分
                    cache_enabled=True,
                    cache_ttl_hours=24
                )

        return converted

    def get_required_points(self, interface_name: str) -> int:
        """
        获取接口所需的积分
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.required_points

        # 假设默认需要2000积分
        return 2000

    def interface_available_for_user(self, interface_name: str) -> bool:
        """
        检查特定接口对当前用户是否可用
        """
        config = self.get_config(interface_name)

        if isinstance(config, InterfaceConfig):
            return config.enabled and self.user_points >= config.required_points

        # 对于原始配置，只检查启用状态
        if isinstance(config, bool):
            return config

        return False


# 全局配置适配器实例
config_adapter = ConfigAdapter()


def get_config_adapter() -> ConfigAdapter:
    """
    获取全局配置适配器实例
    """
    return config_adapter


def is_interface_enabled(interface_name: str) -> bool:
    """
    检查接口是否启用（全局函数）
    """
    return config_adapter.is_enabled(interface_name)


def get_interface_priority(interface_name: str) -> DataTypePriority:
    """
    获取接口优先级（全局函数）
    """
    return config_adapter.get_priority(interface_name)


def get_interface_max_retries(interface_name: str) -> int:
    """
    获取接口最大重试次数（全局函数）
    """
    return config_adapter.get_max_retries(interface_name)


def get_interface_rate_limit(interface_name: str) -> float:
    """
    获取接口速率限制（全局函数）
    """
    return config_adapter.get_rate_limit(interface_name)


def get_interface_strategy(interface_name: str) -> DownloadStrategy:
    """
    获取接口下载策略（全局函数）
    """
    return config_adapter.get_strategy(interface_name)


def get_interface_batch_size(interface_name: str) -> int:
    """
    获取接口批处理大小（全局函数）
    """
    return config_adapter.get_batch_size(interface_name)


def get_interface_concurrency(interface_name: str) -> int:
    """
    获取接口并发数（全局函数）
    """
    return config_adapter.get_concurrency(interface_name)


def get_interface_api_params(interface_name: str) -> Dict[str, Any]:
    """
    获取接口API参数（全局函数）
    """
    return config_adapter.get_api_params(interface_name)


def get_interface_cache_settings(interface_name: str) -> Dict[str, Any]:
    """
    获取接口缓存设置（全局函数）
    """
    return config_adapter.get_cache_settings(interface_name)


def get_all_available_interfaces() -> Dict[str, InterfaceConfig]:
    """
    获取所有可用接口（全局函数）
    """
    return config_adapter.get_all_available_interfaces()


def get_high_priority_interfaces() -> Dict[str, InterfaceConfig]:
    """
    获取高优先级接口（全局函数）
    """
    return config_adapter.get_interfaces_by_priority(DataTypePriority.HIGH)


def get_medium_priority_interfaces() -> Dict[str, InterfaceConfig]:
    """
    获取中优先级接口（全局函数）
    """
    return config_adapter.get_interfaces_by_priority(DataTypePriority.MEDIUM)


def get_low_priority_interfaces() -> Dict[str, InterfaceConfig]:
    """
    获取低优先级接口（全局函数）
    """
    return config_adapter.get_interfaces_by_priority(DataTypePriority.LOW)


def get_parallel_interfaces() -> Dict[str, InterfaceConfig]:
    """
    获取并行下载接口（全局函数）
    """
    return config_adapter.get_interfaces_by_strategy(DownloadStrategy.PARALLEL)


def get_paginated_interfaces() -> Dict[str, InterfaceConfig]:
    """
    获取分页下载接口（全局函数）
    """
    return config_adapter.get_interfaces_by_strategy(DownloadStrategy.PAGINATED)