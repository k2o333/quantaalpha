# aspipe_v4 代码重构方案

## 概述

本方案旨在重构 aspipe_v4 项目中的代码结构，将 CLI 参数解析和下载逻辑分离，同时解决 `pro_bar` 接口的下载问题。重构后代码将更加模块化，便于维护和扩展。

## 问题背景

1. `pro_bar` 接口无法通过标准HTTP方式调用（在SDK层有特殊处理，无法通过HTTP调用）
2. 代码职责混杂，CLI参数解析、下载逻辑混合在 main.py 中
3. 可扩展性差，难以添加新的API类型

## 重构目标

1. 分离CLI参数解析逻辑，创建独立的 `cli.py` 模块
2. 分离下载逻辑，创建API下载器和SDK下载器
3. 保持与现有功能的兼容性
4. 支持通过配置文件指定接口类型

## 详细设计方案

### 1. CLI参数分离 (cli.py)

创建 `app4/cli.py` 文件，专门处理命令行参数解析：

```python
# app4/cli.py
#!/usr/bin/env python3
"""
命令行参数解析模块
"""
import argparse
import sys
import os

def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(description="aspipe_v4 融合重构版 - 配置驱动架构")

    # 保持与原版的参数兼容性
    parser.add_argument('--start_date', type=str, default='20230101',
                        help='起始日期 (YYYYMMDD)')
    parser.add_argument('--end_date', type=str, default=None,
                        help='结束日期 (YYYYMMDD)')
    parser.add_argument('--use_legacy', action='store_true',
                        help='传统下载方式 (已移除，保留向后兼容)')
    parser.add_argument('--holders-data', action='store_true',
                        help='下载股东数据')
    parser.add_argument('--pro-bar-only', action='store_true',
                        help='仅下载pro_bar数据')
    parser.add_argument('--tscode-historical', action='store_true',
                        help='全历史数据下载')

    # 新增通用参数
    parser.add_argument('--interface', type=str,
                        help='指定接口名称')
    parser.add_argument('--group', type=str,
                        help='指定接口组名称')
    parser.add_argument('--concurrency', type=int, default=4,
                        help='并发数')
    parser.add_argument('--log-level', type=str, default='INFO',
                        help='日志级别')
    parser.add_argument('--ts_code', type=str,
                        help='指定股票代码 (如: 000001.SZ)')
    parser.add_argument('--force', action='store_true',
                        help='强制覆盖已存在的数据')
    parser.add_argument('--incremental', action='store_true',
                        help='增量模式 - 只下载缺失的时间段')

    return parser

def parse_arguments():
    """解析命令行参数"""
    parser = create_parser()
    args = parser.parse_args()
    return args

def validate_and_adjust_date(start_date: str, end_date: str = None):
    """
    日期验证和调整函数
    """
    import re
    from datetime import datetime

    DATE_PATTERN = re.compile(r'^\d{8}$')

    # 处理 end_date 为 None 的情况
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    # 格式验证
    if not DATE_PATTERN.match(start_date):
        raise ValueError(f"Invalid start_date format: {start_date}, expected YYYYMMDD")
    if not DATE_PATTERN.match(end_date):
        raise ValueError(f"Invalid end_date format: {end_date}, expected YYYYMMDD")

    # 日期有效性验证
    try:
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
    except ValueError as e:
        raise ValueError(f"Invalid date: {e}")

    # start_date <= end_date 检查
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    # 调整未来日期
    today = datetime.now()
    if end_dt > today:
        end_date = today.strftime('%Y%m%d')

    return start_date, end_date
```

### 2. 基础下载器类 (core/base_downloader.py)

创建 `app4/core/base_downloader.py`，定义基础下载器抽象类：

```python
# app4/core/base_downloader.py
"""
基础下载器类
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from .config_loader import ConfigLoader
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

class BaseDownloader(ABC):
    """基础下载器抽象类"""

    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()
        self.performance_monitor = PerformanceMonitor()

    @abstractmethod
    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        下载指定接口的数据
        """
        pass

    def _record_failure_metrics(self, interface_config: Dict[str, Any], start_time: float,
                              params: Dict[str, Any], retry_count: int = 0):
        """
        记录失败请求的性能指标
        """
        import time
        duration = time.time() - start_time
        self.performance_monitor.record_request(
            interface=interface_config['name'],
            duration=duration,
            record_count=0,
            retry_count=retry_count,
            window_start=params.get('start_date'),
            window_end=params.get('end_date')
        )
```

### 3. API下载器 (core/api_downloader.py)

创建 `app4/core/api_downloader.py`，处理标准的HTTP API接口：

```python
# app4/core/api_downloader.py
"""
标准HTTP API下载器
处理标准的 /api/data 接口
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import logging
import random
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import OrderedDict
from .config_loader import ConfigLoader
from .base_downloader import BaseDownloader

logger = logging.getLogger(__name__)

class LRUCache(OrderedDict):
    """
    Least Recently Used (LRU) cache implementation.
    """
    def __init__(self, maxsize: int = 1000):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)

        if len(self) > self.maxsize:
            oldest_key = next(iter(self))
            super().__delitem__(oldest_key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def put(self, key, value):
        self[key] = value

class APIDownloader(BaseDownloader):
    """标准HTTP API下载器 - 用于处理标准的 /api/data 接口"""

    def __init__(self, config_loader: ConfigLoader):
        super().__init__(config_loader)
        # 创建具有重试策略的会话
        self.session = self._create_session_with_retries()

    def _create_session_with_retries(self):
        """创建配置了重试策略的 Session"""
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
        )

        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'aspipe_v4/4.0.0'
        })

        return session

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        下载指定接口的数据
        """
        try:
            # 1. 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 2. 校验参数
            validated_params = self._validate_parameters(interface_config, params)

            # 3. 执行API请求
            data = self._make_request(interface_config, validated_params)

            return data

        except Exception as e:
            logger.error(f"Error downloading data from {interface_name}: {str(e)}")
            return None

    def _validate_parameters(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """校验并处理参数"""
        validated_params = {}
        parameter_config = interface_config.get('parameters', {})

        for param_name, param_value in params.items():
            if param_name in parameter_config:
                param_def = parameter_config[param_name]
                param_type = param_def.get('type')

                # 类型检查和转换
                if param_type == 'string':
                    validated_params[param_name] = str(param_value)
                elif param_type == 'int':
                    validated_params[param_name] = int(param_value)
                elif param_type == 'float':
                    validated_params[param_name] = float(param_value)
                else:
                    validated_params[param_name] = param_value
            else:
                # 如果参数未在配置中定义，仍然传递
                validated_params[param_name] = param_value

        # 添加默认值
        for param_name, param_def in parameter_config.items():
            if param_name not in validated_params and 'default' in param_def:
                validated_params[param_name] = param_def['default']

        return validated_params

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """发起实际的 API 请求"""
        api_name = interface_config['api_name']

        # 读取重试配置
        req_config = self.global_config.get('request', {})
        max_retries = req_config.get('retries', 3)

        # 随机延迟，错开多个线程的请求时刻
        time.sleep(random.uniform(
            req_config.get('jitter_min', 0.1),
            req_config.get('jitter_max', 0.5)
        ))

        start_time = time.time()
        retry_count = 0

        # 重试循环
        for attempt in range(max_retries + 1):
            try:
                request_config = interface_config.get('request', {})
                method = request_config.get('method', 'POST')
                timeout_val = request_config.get('timeout', 60)
                timeout = (10, timeout_val)

                # 获取 API URL
                import os
                proxy_url = os.getenv('PROXY_URL', '')
                tushare_config = self.global_config.get('tushare', {})

                if proxy_url:
                    api_url = proxy_url
                else:
                    api_url = tushare_config.get('api_url', 'http://api.tushare.pro/api')

                # 确保URL正确
                if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
                    if not api_url.endswith('/'):
                        api_url += '/api'

                # 添加额外路径（如果有）
                extra_path = request_config.get('extra_path', '')
                if extra_path:
                    api_url += extra_path

                # 添加 token
                token_placeholder = tushare_config.get('token', '')
                if '${TUSHARE_TOKEN}' in token_placeholder:
                    token = os.getenv('TUSHARE_TOKEN', '')
                else:
                    token = token_placeholder

                # 获取接口配置中的 fields
                config_fields = interface_config.get('fields', [])

                if config_fields:
                    req_params = {
                        'api_name': interface_config['api_name'],
                        'token': token,
                        'params': params,
                        'fields': ','.join(config_fields)
                    }
                else:
                    req_params = {
                        'api_name': interface_config['api_name'],
                        'token': token,
                        'params': params,
                        'fields': ''  # 空字符串，返回默认字段
                    }

                if attempt > 0:
                    retry_count = attempt

                logger.debug(f"Making {method} request to {api_url} for {api_name} (attempt {attempt+1})")

                if method.upper() == 'POST':
                    response = self.session.post(api_url, json=req_params, timeout=timeout)
                else:
                    response = self.session.get(api_url, json=req_params, timeout=timeout)

                response.raise_for_status()
                result = response.json()

                # 检查 API 返回是否成功
                if result.get('code') != 0:
                    msg = result.get('msg', '')
                    if '频繁' in msg or 'limit' in msg.lower():
                        if attempt < max_retries:
                            random_delay = self._calculate_retry_delay(req_config, attempt)
                            logger.warning(f"Rate limit hit for {api_name}. Retrying in {random_delay:.2f}s...")
                            time.sleep(random_delay)
                            retry_count = attempt + 1
                            continue

                    logger.error(f"API error for {api_name}: {msg}")
                    self._record_failure_metrics(interface_config, start_time, params, retry_count)
                    return []

                # 数据转换逻辑
                fields = result.get('data', {}).get('fields', [])
                items = result.get('data', {}).get('items', [])

                converted_data = []
                for item in items:
                    row_dict = {}
                    for i, field_name in enumerate(fields):
                        if i < len(item):
                            field_name = str(field_name) if field_name is not None else f"field_{i}"
                            row_dict[field_name] = item[i]
                    converted_data.append(row_dict)

                duration = time.time() - start_time

                # 记录指标
                self.performance_monitor.record_request(
                    interface=interface_config['name'],
                    duration=duration,
                    record_count=len(converted_data),
                    retry_count=retry_count,
                    window_start=params.get('start_date'),
                    window_end=params.get('end_date')
                )

                return converted_data

            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.error(f"Request error for {api_name}: {str(e)}")
                if attempt < max_retries:
                    random_delay = self._calculate_retry_delay(req_config, attempt)
                    logger.warning(f"Retrying {api_name} in {random_delay:.2f}s due to: {type(e).__name__}")
                    time.sleep(random_delay)
                    retry_count = attempt + 1
                    continue
                self._record_failure_metrics(interface_config, start_time, params, retry_count)
                return []
            except Exception as e:
                logger.error(f"Unexpected error for {api_name}: {str(e)}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    retry_count = attempt + 1
                    continue
                self._record_failure_metrics(interface_config, start_time, params, retry_count)
                return []

    def _calculate_retry_delay(self, req_config: Dict[str, Any], attempt: int) -> float:
        """
        计算重试延迟时间
        """
        base_delay = (req_config.get('retry_delay', 2) *
                     (req_config.get('retry_backoff', 2) ** attempt))
        random_delay = base_delay + random.uniform(0, 2)
        return random_delay
```

### 4. SDK下载器 (core/sdk_downloader.py)

创建 `app4/core/sdk_downloader.py`，处理需要特殊处理的接口如 `pro_bar`：

```python
# app4/core/sdk_downloader.py
"""
SDK接口下载器
处理需要特殊处理的接口如 pro_bar

重要说明：
- SDK方式（如tushare的pro.bar）不支持HTTP代理配置
- Token通过环境变量或配置文件获取，只需设置一次
- 与HTTP API方式相比，SDK方式的认证机制不同
"""
import logging
import os
import time
from typing import Dict, Any, Optional, List
from .base_downloader import BaseDownloader

logger = logging.getLogger(__name__)


class SDKDownloader(BaseDownloader):
    """SDK接口下载器 - 用于处理需要特殊SDK处理的接口如 pro_bar"""

    def __init__(self, config_loader: 'ConfigLoader'):
        super().__init__(config_loader)
        self._pro_api = None
        self._token = None
        self._sdk_initialized = False

    def _check_proxy_config(self) -> None:
        """检查代理配置并发出警告（SDK不支持代理）"""
        proxy_url = os.getenv('PROXY_URL')
        if proxy_url:
            logger.warning("=" * 60)
            logger.warning("代理配置警告")
            logger.warning("=" * 60)
            logger.warning(f"检测到 PROXY_URL={proxy_url}")
            logger.warning("但是 Tushare SDK (pro.bar) 不支持HTTP代理配置")
            logger.warning("SDK将直接连接Tushare服务器，忽略代理设置")
            logger.warning("如果需要使用代理，请联系Tushare官方支持")
            logger.warning("=" * 60)

    def _get_token(self) -> str:
        """
        从config_loader获取token（不修改config_loader.py）

        Token获取优先级：
        1. 环境变量 TUSHARE_TOKEN
        2. 配置文件 settings.yaml 中的 tushare.token
        3. 配置文件中使用了 ${TUSHARE_TOKEN} 占位符

        Returns:
            token字符串，如果未找到则返回空字符串
        """
        # 从config_loader获取全局配置
        global_config = self.config_loader.get_global_config()

        # 获取tushare配置部分
        tushare_config = global_config.get('tushare', {})

        # 获取token（config_loader已经处理了环境变量替换）
        token = tushare_config.get('token', '')

        if not token:
            logger.error("未找到Tushare token配置")
            logger.error("请确保以下之一：")
            logger.error("1. 设置环境变量 TUSHARE_TOKEN")
            logger.error("2. 在 config/settings.yaml 中配置 tushare.token")
            logger.error("3. 在配置文件中使用 ${TUSHARE_TOKEN} 占位符并设置环境变量")

        return token

    def _ensure_sdk_initialized(self) -> bool:
        """
        确保SDK已初始化

        Returns:
            成功返回True，失败返回False
        """
        if self._sdk_initialized and self._pro_api is not None:
            return True

        try:
            import tushare as ts

            # 获取token
            self._token = self._get_token()
            if not self._token:
                logger.error("无法初始化Tushare SDK：token未配置")
                return False

            # 检查代理配置并警告
            self._check_proxy_config()

            # 设置token
            logger.debug(f"设置Tushare token: {self._token[:10]}...")
            ts.set_token(self._token)

            # 初始化pro API
            logger.info("初始化Tushare Pro SDK...")
            self._pro_api = ts.pro_api()

            self._sdk_initialized = True
            logger.info("Tushare SDK初始化成功")
            return True

        except ImportError:
            logger.error("未安装tushare库，请执行: pip install tushare")
            return False
        except Exception as e:
            logger.error(f"Tushare SDK初始化失败: {str(e)}")
            return False

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        下载指定接口的数据

        Args:
            interface_name: 接口名称
            params: 请求参数

        Returns:
            数据列表，失败返回None
        """
        try:
            # 1. 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 2. 检查是否为SDK接口
            api_type = interface_config.get('api_type', 'http')
            if api_type != 'sdk':
                logger.error(f"接口 {interface_name} 未配置为SDK接口")
                return None

            # 3. 确保SDK已初始化
            if not self._ensure_sdk_initialized():
                return None

            # 4. 根据配置执行相应的SDK调用
            sdk_config = interface_config.get('sdk', {})
            sdk_method = sdk_config.get('method', 'tushare_pro_bar')

            if sdk_method == 'tushare_pro_bar':
                return self._download_pro_bar(interface_config, params)
            else:
                logger.error(f"不支持的SDK方法: {sdk_method}")
                return None

        except Exception as e:
            logger.error(f"从 {interface_name} 下载数据时出错: {str(e)}")
            import traceback
            logger.debug(f"详细错误信息:\n{traceback.format_exc()}")
            return None

    def _download_pro_bar(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        专门处理 pro_bar 接口的下载

        通过调用tushare SDK的pro.bar()方法实现

        Args:
            interface_config: 接口配置
            params: 请求参数

        Returns:
            数据列表
        """
        import time
        from datetime import datetime

        start_time = time.time()
        retry_count = 0
        max_retries = 3

        # 准备pro.bar()的参数
        # pro.bar()接受的参数: ts_code, start_date, end_date, freq, asset, adj, ma, factors
        sdk_params = {}

        # 映射参数
        if 'ts_code' in params and params['ts_code']:
            sdk_params['ts_code'] = params['ts_code']

        if 'start_date' in params and params['start_date']:
            sdk_params['start_date'] = params['start_date']

        if 'end_date' in params and params['end_date']:
            sdk_params['end_date'] = params['end_date']
        else:
            # 如果没有end_date，使用今天
            sdk_params['end_date'] = datetime.now().strftime('%Y%m%d')

        # 资产类别（默认股票E）
        sdk_params['asset'] = params.get('asset', 'E')

        # 数据频率（默认日线D）
        sdk_params['freq'] = params.get('freq', 'D')

        # 复权类型
        if 'adj' in params:
            sdk_params['adj'] = params['adj']

        # 均线（如果提供）
        if 'ma' in params and params['ma']:
            sdk_params['ma'] = params['ma']

        # 因子（如果提供）
        if 'factors' in params and params['factors']:
            sdk_params['factors'] = params['factors']

        logger.info(f"调用pro.bar()参数: {sdk_params}")

        # 进行重试循环
        for attempt in range(max_retries + 1):
            try:
                # 调用tushare pro_bar接口
                logger.debug(f"执行pro.bar() (attempt {attempt + 1})")

                # 使用pro.bar()方法
                df = self._pro_api.bar(**sdk_params)

                # 检查结果
                if df is not None and not df.empty:
                    # 转换为字典列表
                    data = df.to_dict('records')

                    duration = time.time() - start_time

                    # 记录性能指标
                    self.performance_monitor.record_request(
                        interface=interface_config['name'],
                        duration=duration,
                        record_count=len(data),
                        retry_count=retry_count,
                        window_start=params.get('start_date'),
                        window_end=params.get('end_date')
                    )

                    logger.info(f"成功下载 {len(data)} 条pro_bar记录")
                    return data
                else:
                    logger.warning("pro.bar()返回空结果")

                    # 记录性能指标（空结果）
                    duration = time.time() - start_time
                    self.performance_monitor.record_request(
                        interface=interface_config['name'],
                        duration=duration,
                        record_count=0,
                        retry_count=retry_count,
                        window_start=params.get('start_date'),
                        window_end=params.get('end_date')
                    )
                    return []

            except Exception as e:
                error_msg = str(e)
                logger.error(f"调用pro.bar()失败: {error_msg}")

                # 检查是否是token相关的错误
                if any(keyword in error_msg.lower() for keyword in ['token', '权限', 'permission', 'unauthorized']):
                    logger.error("Token认证失败，请检查token配置")
                    # Token错误不重试
                    return []

                # 检查是否是网络相关的错误
                if any(keyword in error_msg.lower() for keyword in ['network', 'timeout', '连接', 'connection']):
                    if attempt < max_retries:
                        retry_count = attempt + 1
                        wait_time = min(2 ** attempt, 30)  # 指数退避，最多30秒
                        logger.warning(f"网络错误，{wait_time}秒后重试 (attempt {retry_count})")
                        time.sleep(wait_time)
                        continue

                # 其他错误，重试
                if attempt < max_retries:
                    retry_count = attempt + 1
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warning(f"错误: {error_msg}，{wait_time}秒后重试 (attempt {retry_count})")
                    time.sleep(wait_time)
                    continue
                else:
                    # 达到最大重试次数
                    duration = time.time() - start_time
                    self.performance_monitor.record_request(
                        interface=interface_config['name'],
                        duration=duration,
                        record_count=0,
                        retry_count=retry_count,
                        window_start=params.get('start_date'),
                        window_end=params.get('end_date')
                    )
                    return []

        return []

    def __del__(self):
        """清理资源"""
        if hasattr(self, '_pro_api') and self._pro_api is not None:
            # tushare SDK没有明确的关闭方法
            pass
```

### 5. 更新通用下载器 (core/downloader.py)

更新 `app4/core/downloader.py`，使其作为通用下载器：

```python
# app4/core/downloader.py
"""
通用下载器
根据接口配置决定使用API下载器还是SDK下载器
"""
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config_loader import ConfigLoader
from .coverage_manager import CoverageManager
from .processor import DataProcessor
from .schema_manager import SchemaManager
from .pagination import (
    ParameterGenerator,
    PaginationContext,
    get_window_size_for_interface
)
from .pagination_executor import PaginationExecutor
from .api_downloader import APIDownloader
from .sdk_downloader import SDKDownloader
import polars as pl

# Import the new PerformanceMonitor class
from .performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

class LRUCache(OrderedDict):
    """
    Least Recently Used (LRU) cache implementation.
    Automatically removes least recently used items when size exceeds maxsize.
    """
    def __init__(self, maxsize: int = 1000):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        # Move accessed item to end (marking it as most recently used)
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        # Move existing key to end or add new key
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)

        # Remove oldest item if size exceeds limit
        if len(self) > self.maxsize:
            oldest_key = next(iter(self))
            super().__delitem__(oldest_key)

    def get(self, key, default=None):
        """Get value with optional default, mark as recently used."""
        try:
            return self[key]
        except KeyError:
            return default

    def put(self, key, value):
        """Alias for __setitem__"""
        self[key] = value

class APIErrorType(Enum):
    SUCCESS = "success"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    NETWORK_ERROR = "network_error"

class GenericDownloader:
    """通用下载器 - 根据配置自动选择合适的下载器"""

    def __init__(self, config_loader: ConfigLoader, storage_manager=None,
                 trade_calendar_cache=None, stock_list_cache=None, force_download=False, incremental_mode=False):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()

        # 初始化各种下载器
        self.api_downloader = APIDownloader(config_loader)
        self.sdk_downloader = SDKDownloader(config_loader)

        # 存储管理器（外部传入）
        self.storage_manager = storage_manager

        # 数据处理器和模式管理器
        self.data_processor = DataProcessor()
        self.schema_manager = SchemaManager()

        # 下载模式标志
        self.force_download = force_download
        self.incremental_mode = incremental_mode

        # 初始化性能监控器（使用API下载器的监控器以保持一致性）
        self.performance_monitor = self.api_downloader.performance_monitor

        # [新增] 运行时简易缓存，替代原有的 CacheManager
        self._memory_cache = {
            'trade_cal': LRUCache(maxsize=100),      # Trade calendar cache - typically small set of keys
            'stock_list': None,                      # Will be stored separately if needed
            'coverage': LRUCache(maxsize=1000),      # Coverage info for various interfaces
            'api_responses': LRUCache(maxsize=500)   # API responses cache
        }
        self._cache_lock = threading.RLock()  # 确保线程安全

        # 使用传入的缓存（如果不为None）
        if trade_calendar_cache is not None:
            with self._cache_lock:
                self._memory_cache['trade_cal'][('global',)] = trade_calendar_cache

        if stock_list_cache is not None:
            with self._cache_lock:
                self._memory_cache['stock_list'] = stock_list_cache

        # [新增] 覆盖率管理器
        if storage_manager:
            self.coverage_manager = CoverageManager(storage_manager, config_loader, downloader=self)
        else:
            self.coverage_manager = None

        # [新增] 分页执行器
        self.pagination_executor = PaginationExecutor()

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        根据接口配置选择合适的下载器下载数据
        """
        try:
            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 检查接口类型
            api_type = interface_config.get('api_type', 'http')

            if api_type == 'sdk':
                logger.info(f"Using SDK downloader for {interface_name}")
                return self.sdk_downloader.download(interface_name, params)
            else:
                logger.info(f"Using HTTP API downloader for {interface_name}")
                return self.api_downloader.download(interface_name, params)

        except Exception as e:
            logger.error(f"Error in generic downloader for {interface_name}: {str(e)}")
            return None

    def download_single_stock(self, interface_config: Dict[str, Any], stock: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """下载单只股票的数据 - 原子化方法供调度器调用"""
        try:
            stock_params = params.copy()
            stock_params['ts_code'] = stock['ts_code']

            # 设置日期范围
            if 'start_date' not in stock_params:
                # 如果没有指定起始日期，使用该股票的上市日期
                list_date = stock.get('list_date', '20050101')
                stock_params['start_date'] = list_date
            if 'end_date' not in stock_params:
                from datetime import datetime
                stock_params['end_date'] = datetime.now().strftime('%Y%m%d')

            # [新增] 检查覆盖率，如果已存在则跳过
            should_skip = False
            if self.coverage_manager and not self.force_download:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    stock_params,
                    strategy='stock'
                )
                if should_skip:
                    logger.info(f"Skipping stock {stock['ts_code']} for {interface_config['api_name']} (already exists)")
                    return []

            logger.info(f"Downloading data for stock {stock['ts_code']}, date range: {stock_params.get('start_date')} - {stock_params.get('end_date')}")

            # 创建分页上下文
            pagination_config = interface_config.get('pagination', {})
            context = PaginationContext(
                interface_config=interface_config,
                force_download=self.force_download
            )

            # 为单个股票执行分页下载 - 使用分页执行器
            # 对于股票循环模式，通常会使用日期范围分页来获取单个股票的历史数据
            pagination_config = interface_config.get('pagination', {})

            if pagination_config.get('enabled', False):
                mode = pagination_config.get('mode', 'offset')

                if mode == 'date_range':
                    stock_data = self.pagination_executor.execute_date_range_pagination(
                        interface_config, stock_params, context, self._make_request,
                        coverage_manager=self.coverage_manager, force_download=self.force_download,
                        get_trade_calendar_callback=self.get_trade_calendar
                    )
                elif mode == 'offset':
                    stock_data = self.pagination_executor.execute_offset_pagination(
                        interface_config, stock_params, context, self._make_request
                    )
                else:
                    # 对于其他模式或未知模式，直接请求
                    stock_data = self._make_request(interface_config, stock_params)
            else:
                # 如果分页未启用，直接请求
                stock_data = self._make_request(interface_config, stock_params)

            if stock_data:
                logger.info(f"Downloaded {len(stock_data)} records for {stock['ts_code']}")

                # [新增] 如果有storage_manager，将数据添加到缓存
                if hasattr(self, 'storage_manager') and self.storage_manager:
                    self.storage_manager.add_to_buffer(interface_config['api_name'], stock_data)

            return stock_data or []
        except Exception as e:
            # [新增] 捕获异常，避免影响其他股票
            logger.error(f"Error downloading stock {stock['ts_code']}: {str(e)}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return []  # 返回空列表，让其他股票继续下载

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        通过适当的下载器发起请求
        """
        api_name = interface_config['api_name']

        # 检查接口类型
        api_type = interface_config.get('api_type', 'http')

        if api_type == 'sdk':
            logger.debug(f"Using SDK downloader for {api_name}")
            result = self.sdk_downloader.download(api_name, params)
        else:
            logger.debug(f"Using HTTP API downloader for {api_name}")
            result = self.api_downloader.download(api_name, params)

        return result or []

    def _get_stock_list(self) -> Optional[List[Dict[str, Any]]]:
        """获取股票列表的统一方法"""
        # 从内存缓存获取
        stock_list = self._get_stock_list_from_memory_cache()

        if stock_list is None:
            logger.info("内存中未找到股票列表，正在从Data目录获取...")
            stock_list = self._get_stock_list_from_data_dir()

        if stock_list is None:
            logger.info("Data目录中未找到股票列表，正在从API获取...")
            stock_params = {'list_status': 'L'}
            stock_list = self._make_request(
                self.config_loader.get_interface_config('stock_basic'),
                stock_params
            )
            if stock_list:
                logger.info(f"从API获取到 {len(stock_list)} 只股票")
                with self._cache_lock:
                    self._memory_cache['stock_list'] = stock_list
            else:
                logger.warning("未能从API获取股票列表")
        else:
            logger.info(f"从内存缓存或Data目录获取到 {len(stock_list)} 只股票")

        return stock_list

    def _get_stock_list_from_memory_cache(self) -> Optional[List[Dict[str, Any]]]:
        """从内存缓存获取股票列表"""
        with self._cache_lock:
            return self._memory_cache['stock_list']

    def _get_stock_list_from_data_dir(self) -> Optional[List[Dict[str, Any]]]:
        """从Data目录获取股票列表"""
        try:
            storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
            dir_path = os.path.join(storage_dir, 'stock_basic')

            if not os.path.exists(dir_path):
                return None

            # 读取目录下所有 parquet 文件
            df = pl.read_parquet(dir_path)

            if df.is_empty():
                return None

            # [修复] 必须去重，因为 Dataset 模式下可能有重复数据
            # 按 ts_code 去重，保留最后一次出现的数据
            deduplicated_df = df.unique(subset=['ts_code'], keep='last')

            # [新增] 添加日志输出
            stock_count = len(deduplicated_df)
            logger.info(f"从本地获取了 {stock_count} 只股票")

            return deduplicated_df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read stock list from Data dir: {e}")
            return None

    def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取交易日历，优先使用预热缓存
        """
        # 使用全局缓存键
        cache_key = ('global',)  # 改为固定键

        with self._cache_lock:
            if cache_key in self._memory_cache['trade_cal']:
                # 从全局缓存过滤日期范围
                all_days = self._memory_cache['trade_cal'][cache_key]
                if all_days:
                    return [d for d in all_days if start_date <= d['cal_date'] <= end_date]

        # 回退到原有逻辑
        trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)
        if not trade_calendar:
            # 3. 请求 API
            logger.info(f"Trade calendar not found locally, fetching from API: {start_date}-{end_date}")
            calendar_params = {
                'start_date': start_date,
                'end_date': end_date,
                'exchange': 'SSE'
            }
            # 使用 _make_request 直接请求，避免递归调用
            trade_calendar = self._make_request(
                self.config_loader.get_interface_config('trade_cal'),
                calendar_params
            )

            # 更新内存缓存
            if trade_calendar:
                with self._cache_lock:
                    cache_key = (start_date, end_date)  # 保持原有缓存键
                    self._memory_cache['trade_cal'][cache_key] = trade_calendar

        return trade_calendar

    def _get_trade_calendar_from_data_dir(self, start_date, end_date):
        """从 Data 目录查询交易日历 (Source of Truth) - 优化版本"""
        # 假设存储目录为 data/trade_cal/
        storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
        dir_path = os.path.join(storage_dir, 'trade_cal')

        if not os.path.exists(dir_path):
            return None

        try:
            # 读取目录下所有 parquet 文件 (Dataset 模式)
            try:
                df = pl.read_parquet(dir_path)
            except Exception:
                return None

            if df.is_empty():
                return None

            # 构建过滤条件
            conditions = [
                (pl.col('cal_date') >= start_date),
                (pl.col('cal_date') <= end_date),
                (pl.col('is_open') == 1)
            ]

            # [修复] 检查 exchange 列是否存在
            if 'exchange' in df.columns:
                conditions.append(pl.col('exchange') == 'SSE')

            # 过滤日期范围并去重
            # 必须去重，因为 Dataset 模式下可能有重复数据
            filtered_df = df.filter(
                pl.all_horizontal(conditions)
            ).unique(subset=['cal_date'], keep='last').sort('cal_date')

            if filtered_df.is_empty():
                return None

            return filtered_df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read trade calendar from Data dir: {e}")
            return None

    def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行分页/循环逻辑 - 控制器
        """
        pagination_config = interface_config.get('pagination', {})
        if not pagination_config.get('enabled', False):
            return self._make_request(interface_config, params)

        mode = pagination_config.get('mode', 'offset')
        context = PaginationContext(
            interface_config=interface_config,
            force_download=self.force_download
        )

        # 委托给分页执行器，传递回调函数而非self实例
        if mode == 'offset':
            return self.pagination_executor.execute_offset_pagination(
                interface_config, params, context, self._make_request
            )
        elif mode == 'date_range':
            return self.pagination_executor.execute_date_range_pagination(
                interface_config, params, context, self._make_request,
                coverage_manager=self.coverage_manager, force_download=self.force_download,
                get_trade_calendar_callback=self.get_trade_calendar
            )
        elif mode == 'stock_loop':
            return self.pagination_executor.execute_stock_loop_pagination(
                interface_config, params, context, self._make_request,
                get_stock_list_callback=self._get_stock_list,
                coverage_manager=self.coverage_manager, force_download=self.force_download
            )
        elif mode == 'period_range':
            return self.pagination_executor.execute_period_range_pagination(
                interface_config, params, context, self._make_request,
                coverage_manager=self.coverage_manager, force_download=self.force_download
            )
        elif mode == 'quarterly_range':
            return self.pagination_executor.execute_quarterly_pagination(
                interface_config, params, context, self._make_request
            )
        elif mode == 'periodic_range':
            return self.pagination_executor.execute_periodic_pagination(
                interface_config, params, context, self._make_request
            )
        else:
            return self._make_request(interface_config, params)
```

### 6. 更新配置文件 (pro_bar.yaml)

更新 `app4/config/interfaces/pro_bar.yaml`，添加接口类型配置：

```yaml
# app4/config/interfaces/pro_bar.yaml
api_name: pro_bar
description: A股复权行情 (通过SDK调用)
api_type: sdk
sdk:
  method: tushare_pro_bar
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date（关联trade_cal.cal_date_dt）
    format: '%Y%m%d'
    source: trade_date
    type: date
name: pro_bar
output:
  dedup_enabled: true
  primary_key:
  - ts_code
  - trade_date
  sort_by:
  - trade_date
pagination:
  date_pagination: true
  default_limit: 6000
  enabled: true
  limit_key: limit
  mode: stock_loop
  offset_key: offset
  window_size_days: 5000
parameters:
  adj:
    default: qfq
    description: 复权类型
    options:
    - qfq
    - hfq
    - null
    required: false
    type: string
  asset:
    default: E
    description: 资产类别
    required: false
    type: string
  end_date:
    description: 结束日期 YYYYMMDD
    required: false
    type: string
  factors:
    description: 股票因子（asset='E'有效）支持 tor换手率 vr量比
    options:
    - tor
    - vr
    required: false
    type: list
  freq:
    default: D
    description: 数据频度
    required: false
    type: string
  ma:
    description: 均线
    required: false
    type: list
  start_date:
    description: 开始日期 YYYYMMDD
    required: false
    type: string
  ts_code:
    description: 证券代码
    required: false
    type: string
permissions:
  min_points: 0
  query_limit: 6000
  rate_limit: 200
request:
  extra_path: /api/pro_bar
  method: POST
  timeout: 60
```

## 实施步骤

1. 创建 `app4/cli.py` 文件，分离参数解析逻辑
2. 创建 `app4/core/base_downloader.py`，定义基础下载器类
3. 创建 `app4/core/api_downloader.py`，实现标准API下载逻辑
4. 创建 `app4/core/sdk_downloader.py`，处理特殊接口如 `pro_bar`
5. 更新 `app4/core/downloader.py`，作为通用下载器，不再使用 `_make_request` 回调
6. 更新 `app4/config/interfaces/pro_bar.yaml` 配置文件
7. 简化 `app4/main.py`，移除参数解析逻辑，导入 `cli.py`

## 重构优势

1. **模块化**: CLI参数解析、API下载、SDK下载、通用下载逻辑分离到不同模块
2. **可扩展**: 轻松添加新的API类型或SDK接口
3. **可维护**: 每个模块职责单一，便于维护
4. **兼容性**: 保持与原有配置的兼容性
5. **清晰性**: 通过配置文件决定接口类型，逻辑更清晰
6. **无回调**: API和SDK下载器不进行回调，结构更清晰

## 风险评估

1. **兼容性风险**: 通过保留原有参数和接口，风险较低
2. **功能风险**: 通过配置驱动，可选择性启用新功能，风险可控
3. **性能风险**: 无显著性能影响

## 验证步骤

1. 确保现有功能正常工作
2. 测试 `pro_bar` 接口是否能正常下载
3. 测试其他接口是否正常工作
4. 验证CLI参数解析功能