# aspipe_v4 下载器优化指南

本文档总结了基于日志分析结果提出的优化建议，主要涵盖数据验证、网络重试机制、缓存优化和性能监控等方面。

## 1. 增强数据验证

### 问题描述
在日志中发现数据截断和重复日期问题：
```
WARNING - Window 19931008-20180605 returned 6000 records, which may be truncated (API limit: 6000)
WARNING - Window 19931008-20180605 for 000031.SZ has duplicate dates: 6000 records, 2 unique dates
```

### 修复方案
在 `app4/core/downloader.py` 的 `GenericDownloader` 类中添加 `_validate_and_deduplicate_data` 方法，并在 `_execute_date_range_pagination` 方法中调用它：

```python
from typing import Dict, Any, List

class GenericDownloader:
    # ... 现有代码 ...

    def _validate_and_deduplicate_data(self, data: List[Dict[str, Any]], ts_code: str) -> List[Dict[str, Any]]:
        """
        验证数据完整性并去除重复记录
        """
        if not data:
            return data

        # 检查重复数据
        seen_keys = set()
        unique_data = []
        duplicates = 0

        for record in data:
            date = record.get('trade_date')
            key = (ts_code, date)  # 使用 ts_code 和 trade_date 作为唯一标识

            if key in seen_keys:
                logger.debug(f"Duplicate record found for {ts_code} on {date}")
                duplicates += 1
            else:
                seen_keys.add(key)
                unique_data.append(record)

        if duplicates > 0:
            logger.warning(f"Found {duplicates} duplicate records for {ts_code}, removed from {len(data)} to {len(unique_data)} records")

        # 检查数据完整性
        unique_dates = set(record.get('trade_date') for record in unique_data)
        if len(unique_dates) != len(unique_data):
            logger.error(f"Inconsistent data for {ts_code}: {len(unique_data)} records but {len(unique_dates)} unique dates")

        return unique_data

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # ... 现有代码 ...

        for i in range(0, len(trade_days), window_size):
            window_trade_days = trade_days[i:i+window_size]
            if not window_trade_days:
                continue
            window_start = window_trade_days[0]['cal_date']
            window_end = window_trade_days[-1]['cal_date']

            window_params = params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            logger.info(f"Downloading data for window {i//window_size + 1}: {window_start} - {window_end}")

            # 下载该窗口的数据
            window_data = self._make_request(interface_config, window_params)
            if window_data:
                # 检查数据完整性
                query_limit = interface_config.get('permissions', {}).get('query_limit', 6000)
                if len(window_data) >= query_limit:
                    logger.warning(f"Window {window_start}-{window_end} returned {len(window_data)} records, which may be truncated (API limit: {query_limit})")

                # 检查数据质量并去重
                window_data = self._validate_and_deduplicate_data(window_data, params.get('ts_code', 'unknown'))

                all_data.extend(window_data)
                logger.info(f"Downloaded {len(window_data)} records for date range {window_start}-{window_end} (after deduplication)")
            else:
                logger.warning(f"No data returned for window {window_start}-{window_end}")

        return all_data
```

## 2. 改进网络重试机制

### 问题描述
在日志中发现网络连接中断问题：
```
ERROR - Request error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
WARNING - Network error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response')). Retrying in 1.73s (attempt 1/3)
```

### 修复方案
在 `app4/core/downloader.py` 中增强连接管理：

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class GenericDownloader:
    def __init__(self, config_loader: ConfigLoader, cache_manager: CacheManager):
        self.config_loader = config_loader
        self.cache_manager = cache_manager
        self.global_config = config_loader.get_global_config()

        # 创建具有重试策略的会话
        self.session = self._create_session_with_retries()

    def _create_session_with_retries(self):
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,  # 指数退避
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]  # 允许重试的HTTP方法
        )

        # 配置连接池
        adapter = HTTPAdapter(
            pool_connections=5,      # 连接池大小
            pool_maxsize=10,         # 最大连接数
            max_retries=retry_strategy
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置默认请求头
        session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'aspipe_v4/4.0.0'
        })

        return session

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """发起实际的 API 请求 - 优化后的版本"""
        api_name = interface_config['api_name']

        # 读取重试配置
        req_config = self.global_config.get('request', {})
        max_retries = req_config.get('retries', 3)

        # 随机延迟，错开多个线程的请求时刻
        time.sleep(random.uniform(
            req_config.get('jitter_min', 0.1),
            req_config.get('jitter_max', 0.5)
        ))

        # 重试循环
        for attempt in range(max_retries + 1):
            try:
                request_config = interface_config.get('request', {})
                method = request_config.get('method', 'POST')
                timeout = request_config.get('timeout', 60)  # 增加默认超时时间

                # 获取 API URL，优先使用代理 URL
                import os
                proxy_url = os.getenv('PROXY_URL', '')
                tushare_config = self.global_config.get('tushare', {})
                if proxy_url:
                    api_url = proxy_url
                else:
                    api_url = tushare_config.get('api_url', 'http://api.tushare.pro/api')

                # 添加额外路径（如果有）
                extra_path = request_config.get('extra_path', '')
                if extra_path:
                    api_url += extra_path
                else:
                    # 如果没有额外路径，添加 /api
                    if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
                        if api_url.endswith('/'):
                            api_url += 'api'
                        else:
                            api_url += '/api'

                # 添加 token
                token_placeholder = tushare_config.get('token', '')
                if '${TUSHARE_TOKEN}' in token_placeholder:
                    token = os.getenv('TUSHARE_TOKEN', '')
                else:
                    token = token_placeholder

                # 调试信息
                logger.info(f"API URL: {api_url}")
                logger.info(f"Request timeout: {timeout}s")

                # 根据TuShare API格式构建请求体
                req_params = {
                    'api_name': interface_config['api_name'],
                    'token': token,
                    'params': params,
                    'fields': ''  # 可以从配置中读取，这里暂时为空
                }

                params = req_params

                logger.info(f"Making {method} request to {api_url} with api_name: {interface_config['api_name']}")
                logger.info(f"Starting request to {api_url}...")

                # 增加请求超时和连接超时分别设置
                request_kwargs = {
                    'timeout': (10, timeout)  # (连接超时, 读取超时)
                }

                if method.upper() == 'POST':
                    response = self.session.post(api_url, json=params, **request_kwargs)
                else:
                    response = self.session.get(api_url, json=params, **request_kwargs)

                logger.info(f"Response status: {response.status_code}")
                response.raise_for_status()
                result = response.json()
                logger.debug(f"API response received, code: {result.get('code', 'unknown')}")

                # 检查 API 返回是否成功
                if result.get('code') != 0:
                    msg = result.get('msg', '')
                    # 如果是频率限制，执行退避重试
                    if '频繁' in msg or 'limit' in msg.lower():
                        if attempt < max_retries:
                            base_delay = (req_config.get('retry_delay', 2) *
                                         (req_config.get('retry_backoff', 2) ** attempt))
                            random_delay = base_delay + random.uniform(0, 1)  # 添加 0-1 秒的随机延迟
                            logger.warning(f"Rate limit hit. Retrying in {random_delay:.2f}s (attempt {attempt + 1}/{max_retries})...")
                            time.sleep(random_delay)
                            continue
                    # 其他错误直接返回空
                    logger.error(f"API error: {msg}")
                    return []

                # 将TuShare的字段/数据分离格式转换为字典列表格式
                fields = result.get('data', {}).get('fields', [])
                items = result.get('data', {}).get('items', [])

                # 将二维数组转换为字典列表
                converted_data = []
                for item in items:
                    row_dict = {}
                    for i, field_name in enumerate(fields):
                        if i < len(item):
                            # 确保字段名是字符串类型
                            field_name = str(field_name) if field_name is not None else f"field_{i}"
                            row_value = item[i]
                            row_dict[field_name] = row_value
                    converted_data.append(row_dict)

                return converted_data

            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {str(e)}")
                if attempt < max_retries:
                    # 指数退避 + 随机抖动
                    base_delay = (req_config.get('retry_delay', 2) *
                                 (req_config.get('retry_backoff', 2) ** attempt))
                    random_delay = base_delay + random.uniform(0, 2)  # 增加随机延迟范围
                    logger.warning(f"Connection error: {e}. Retrying in {random_delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(random_delay)
                    continue
                return []

            except requests.RequestException as e:
                logger.error(f"Request error: {str(e)}")
                if attempt < max_retries:
                    base_delay = (req_config.get('retry_delay', 2) *
                                 (req_config.get('retry_backoff', 2) ** attempt))
                    random_delay = base_delay + random.uniform(0, 2)  # 增加随机延迟范围
                    logger.warning(f"Network error: {e}. Retrying in {random_delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(random_delay)
                    continue
                return []
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                if attempt < max_retries:
                    base_delay = (req_config.get('retry_delay', 2) *
                                 (req_config.get('retry_backoff', 2) ** attempt))
                    random_delay = base_delay + random.uniform(0, 2)  # 增加随机延迟范围
                    logger.warning(f"JSON decode error: {e}. Retrying in {random_delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(random_delay)
                    continue
                return []
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                if attempt < max_retries:
                    base_delay = (req_config.get('retry_delay', 2) *
                                 (req_config.get('retry_backoff', 2) ** attempt))
                    random_delay = base_delay + random.uniform(0, 2)  # 增加随机延迟范围
                    logger.warning(f"Unexpected error: {e}. Retrying in {random_delay:.2f}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(random_delay)
                    continue
                return []

        return []
```

## 3. 优化交易历缓存

### 问题描述
虽然系统已有预加载的全局交易日历，但日志中仍存在"Cache miss for trade calendar"，这是因为不同股票的日期范围不同，导致缓存命中率不高。每个股票的上市日期不同，需要查询不同的交易日历范围。

### 修复方案
优化现有缓存策略，优先利用预加载的完整交易日历，通过派生子集来提高缓存命中率：

```python
# 修改 app4/core/cache_manager.py 中的 CacheManager 类，优化 get_trade_calendar 方法

# 在 CacheManager 类中修改 get_trade_calendar 方法，实现派生策略
def get_trade_calendar(self, start_date, end_date):
    """优化的交易日历获取方法 - 优先使用预加载的完整日历进行派生"""

    # 首先尝试精确缓存
    cache_key = f"calendar_{start_date}_{end_date}"
    cached = self.get(cache_key)
    if cached:
        logger.debug(f"Cache hit for trade calendar {start_date}-{end_date}")
        return cached

    logger.debug(f"Cache miss for trade calendar {start_date}-{end_date}, trying to derive from full calendar")

    # 从预加载的完整日历中派生
    full_calendar_key = "calendar_19900101_20251231"  # 预加载的完整日历
    full_calendar = self.get(full_calendar_key)

    if full_calendar:
        # 从完整日历中过滤出指定范围
        filtered_calendar = [
            day for day in full_calendar
            if start_date <= day.get('cal_date', '') <= end_date
            and day.get('is_open', 0) == 1  # 只保留交易日
        ]

        if filtered_calendar:
            # 缓存派生的子集以供后续使用
            self.set(cache_key, filtered_calendar)
            logger.debug(f"Derived and cached {len(filtered_calendar)} trade days for {start_date}-{end_date}")
            return filtered_calendar

    logger.debug(f"Full calendar not available, returning None for API fetch in downloader")
    return None  # 让下载器处理API请求

# 同时优化 app4/core/downloader.py 中的 _execute_date_range_pagination 方法
# 以更好地配合优化的缓存策略
```

# 优化预加载策略 - 在 main.py 中增强预加载功能
```python
def preload_global_trade_calendar(downloader, start_date='19900101', end_date=None):
    """预加载全局交易日历，并优化缓存策略（增强版）"""
    if end_date is None:
        from datetime import datetime
        end_date = datetime.now().strftime('%Y%m%d')

    logger.info(f"Preloading global trade calendar: {start_date} - {end_date}")

    # 使用最广泛的日期范围进行预加载
    cache_key = f"calendar_{start_date}_{end_date}"
    trade_calendar = downloader.cache_manager.get(cache_key)

    if trade_calendar is not None:
        logger.info(f"Global trade calendar already cached: {len(trade_calendar)} trade days")
        return trade_calendar

    # 请求完整范围的交易日历
    calendar_params = {
        'start_date': start_date,
        'end_date': end_date,
        'exchange': 'SSE'
    }

    trade_calendar = downloader._make_request(
        downloader.config_loader.get_interface_config('trade_cal'),
        calendar_params
    )

    if trade_calendar:
        # 过滤出交易日并缓存
        trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]
        trade_days = sorted(trade_days, key=lambda x: x['cal_date'])

        # 同时缓存完整范围和一些常用的子范围以提高命中率
        downloader.cache_manager.set(cache_key, trade_days)

        # 预缓存一些常见的子范围 - 这将显著提高后续请求的缓存命中率
        common_sub_ranges = [
            ('20050101', '20251231'),  # 许多股票的默认查询范围
            ('19950101', '20201231'),  # 历史数据查询范围
            ('20100101', '20251231'),  # 近期数据查询范围
            ('20000101', '20101231'),  # 早期数据查询范围
        ]

        for sub_start, sub_end in common_sub_ranges:
            if sub_start >= start_date and sub_end <= end_date:
                sub_calendar = [
                    day for day in trade_days
                    if sub_start <= day['cal_date'] <= sub_end
                ]
                if sub_calendar:
                    sub_key = f"calendar_{sub_start}_{sub_end}"
                    downloader.cache_manager.set(sub_key, sub_calendar)
                    logger.debug(f"Pre-cached common range {sub_start}-{sub_end}: {len(sub_calendar)} days")

        logger.info(f"Preloaded {len(trade_days)} trade days with enhanced caching strategy")
        return trade_days
    else:
        logger.warning("Failed to preload trade calendar")
        return None
```

## 4. 增加性能监控

### 问题描述
需要增加监控和告警机制，以便及时发现性能问题。

### 修复方案
在关键位置添加性能指标监控：

```python
# 在 app4/core/downloader.py 中添加性能监控

import time
import threading
from collections import defaultdict, deque

class PerformanceMonitor:
    """
    性能监控器，用于跟踪关键指标
    """
    def __init__(self):
        self._metrics = defaultdict(lambda: deque(maxlen=100))  # 保留最近100个指标
        self._lock = threading.Lock()
        self._alert_thresholds = {
            'request_time': 30.0,  # 请求时间超过30秒告警
            'data_size': 6000,     # 单次请求数据量超过6000条告警
            'retry_count': 2       # 重试次数超过2次告警
        }

    def record_metric(self, metric_name: str, value: float, context: Dict[str, Any] = None):
        """
        记录性能指标
        """
        with self._lock:
            self._metrics[metric_name].append({
                'value': value,
                'timestamp': time.time(),
                'context': context or {}
            })

    def get_average_metric(self, metric_name: str) -> float:
        """
        获取指标的平均值
        """
        with self._lock:
            if not self._metrics[metric_name]:
                return 0.0
            values = [item['value'] for item in self._metrics[metric_name]]
            return sum(values) / len(values)

    def check_alerts(self, metric_name: str, value: float, context: Dict[str, Any] = None):
        """
        检查是否超过告警阈值
        """
        threshold = self._alert_thresholds.get(metric_name)
        if threshold and value > threshold:
            logger.warning(f"ALERT: {metric_name} exceeded threshold: {value} > {threshold} for {context or {}}")
            return True
        return False

# 全局性能监控器实例
performance_monitor = PerformanceMonitor()

class GenericDownloader:
    # ... 现有代码 ...

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        # ... 现有代码 ...

        for i in range(0, len(trade_days), window_size):
            window_trade_days = trade_days[i:i+window_size]
            if not window_trade_days:
                continue
            window_start = window_trade_days[0]['cal_date']
            window_end = window_trade_days[-1]['cal_date']

            window_params = params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            # 记录开始时间
            start_time = time.time()

            logger.info(f"Downloading data for window {i//window_size + 1}: {window_start} - {window_end}")

            # 下载该窗口的数据
            window_data = self._make_request(interface_config, window_params)

            # 记录请求耗时
            elapsed_time = time.time() - start_time
            performance_monitor.record_metric('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'window': f"{window_start}-{window_end}",
                'ts_code': params.get('ts_code', 'unknown')
            })

            # 检查是否超时
            performance_monitor.check_alerts('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'window': f"{window_start}-{window_end}",
                'ts_code': params.get('ts_code', 'unknown')
            })

            if window_data:
                # 检查数据完整性
                query_limit = interface_config.get('permissions', {}).get('query_limit', 6000)

                # 记录数据量指标
                performance_monitor.record_metric('data_size', len(window_data), {
                    'interface': interface_config['api_name'],
                    'window': f"{window_start}-{window_end}",
                    'ts_code': params.get('ts_code', 'unknown')
                })

                if len(window_data) >= query_limit:
                    logger.warning(f"Window {window_start}-{window_end} returned {len(window_data)} records, which may be truncated (API limit: {query_limit})")
                    # 检查数据量告警
                    performance_monitor.check_alerts('data_size', len(window_data), {
                        'interface': interface_config['api_name'],
                        'window': f"{window_start}-{window_end}",
                        'ts_code': params.get('ts_code', 'unknown')
                    })

                # 检查数据质量并去重
                window_data = self._validate_and_deduplicate_data(window_data, params.get('ts_code', 'unknown'))

                all_data.extend(window_data)
                logger.info(f"Downloaded {len(window_data)} records for date range {window_start}-{window_end} (after deduplication)")
            else:
                logger.warning(f"No data returned for window {window_start}-{window_end}")

        return all_data

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        修改 _make_request 方法以支持性能监控
        """
        # 记录重试次数
        retry_count = 0

        # ... 现有代码 ...

        # 重试循环
        for attempt in range(max_retries + 1):
            # ... 现有代码 ...

            try:
                # ... 现有请求代码 ...

                # 记录重试次数（如果发生重试）
                if attempt > 0:
                    retry_count = attempt
                    performance_monitor.record_metric('retry_count', retry_count, {
                        'interface': interface_config['api_name'],
                        'params': str(params)[:100]  # 只记录前100个字符的参数
                    })
                    performance_monitor.check_alerts('retry_count', retry_count, {
                        'interface': interface_config['api_name'],
                        'params': str(params)[:100]
                    })

                # ... 现有代码 ...

            except requests.RequestException as e:
                # 记录重试次数
                retry_count = attempt + 1
                performance_monitor.record_metric('retry_count', retry_count, {
                    'interface': interface_config['api_name'],
                    'error': str(e),
                    'params': str(params)[:100]
                })
                performance_monitor.check_alerts('retry_count', retry_count, {
                    'interface': interface_config['api_name'],
                    'error': str(e),
                    'params': str(params)[:100]
                })

                # ... 现有代码 ...

        return []
```

同时，可以在主模块中添加性能监控报告：

```python
# 在 app4/main.py 中添加以下代码

def print_performance_report():
    """
    打印性能监控报告
    """
    print("\n=== 性能监控报告 ===")
    avg_request_time = performance_monitor.get_average_metric('request_time')
    avg_data_size = performance_monitor.get_average_metric('data_size')
    avg_retry_count = performance_monitor.get_average_metric('retry_count')

    print(f"平均请求时间: {avg_request_time:.2f}s")
    print(f"平均数据量: {avg_data_size:.2f} 条")
    print(f"平均重试次数: {avg_retry_count:.2f} 次")

    if avg_request_time > 30:
        print("⚠️  警告: 平均请求时间过长，可能需要优化网络连接")
    if avg_retry_count > 1:
        print("⚠️  警告: 重试次数较多，可能需要优化请求频率")
    if avg_data_size >= 5800:  # 接近6000条限制
        print("⚠️  警告: 数据量接近API限制，可能需要减小窗口大小")

# 在主程序结束时调用
if __name__ == "__main__":
    # ... 现有主程序代码 ...

    # 程序结束时打印性能报告
    print_performance_report()
```

## 总结

通过以上优化措施，可以显著改善系统的稳定性：

1. **数据验证**：增加了去重和完整性检查，防止数据质量问题
2. **网络重试**：增强了连接管理和重试策略，提高网络稳定性
3. **缓存优化**：实现全局交易历缓存，减少重复API调用
4. **性能监控**：添加了全面的性能指标和告警机制，便于及时发现和解决问题

这些改进将有效减少日志中的错误和警告，提高下载效率和数据质量。