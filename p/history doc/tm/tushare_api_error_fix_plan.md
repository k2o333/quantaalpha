# TuShare API 错误修复方案

## 问题概述

在 new2 分支中，TuShare API 调用出现权限错误和 `unknown_api` 调用问题。这些问题导致了大量无效的API请求和权限错误，影响了数据下载的正常运行。

## 问题根本原因分析

### 1. API 名称识别错误
- 在 `tushare_api.py` 的 `download_with_retry` 方法中，API名称提取逻辑存在问题
- 在策略模式下，`api_name` 参数可能被错误地设置为 `unknown_api` 并传递给API调用
- `kwargs.pop('api_name', 'unknown_api')` 逻辑导致API名称识别失败

### 2. 并行架构下的权限检查失效
- 新的生产者-消费者模式可能绕过了原有的权限检查
- 多线程环境下可能导致积分权限检查不一致
- API策略执行时可能未正确验证用户权限

### 3. 速率限制器与权限检查冲突
- 全局速率限制器可能在权限检查之前就获取了令牌
- 速率限制参数可能与API实际限制不匹配

## 解决方案设计

### 1. 修复 API 名称识别逻辑

#### 问题定位
在 `tushare_api.py` 中：

```python
def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
    # Extract api_name from kwargs to avoid passing it to the API function
    api_name = kwargs.pop('api_name', 'unknown_api')  # 问题：可能传入 'unknown_api'
    if api_name == 'unknown_api' and hasattr(api_func, '__name__'):
        api_name = api_func.__name__
```

#### 修复方案
创建一个更健壮的API名称提取函数：

```python
def _extract_api_name(self, api_func, kwargs):
    """
    安全地提取API名称，优先级：
    1. 从kwargs中获取api_name参数
    2. 从api_func的__name__属性获取
    3. 返回默认值
    """
    # 保留原始api_name但不从kwargs中移除，以便后续检查
    api_name = kwargs.get('api_name', None)

    # 如果api_name是'unknown_api'，尝试从函数名获取
    if api_name in [None, 'unknown_api'] and hasattr(api_func, '__name__'):
        api_name = api_func.__name__

    # 如果仍然无法确定，返回安全的默认值
    if api_name in [None, 'unknown_api']:
        api_name = getattr(api_func, '__name__', 'tushare_api_call')

    return api_name
```

### 2. 优化权限检查机制

#### 问题定位
- 在策略模式下，权限检查可能未在每个API调用前执行
- 不同API有不同的权限要求，需要动态检查

#### 修复方案
创建一个权限检查装饰器：

```python
def check_api_permission(min_points_required):
    """
    检查API调用权限的装饰器
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # 检查当前用户积分是否满足要求
            if self.current_points < min_points_required:
                self.logger.warning(f"Insufficient points for {func.__name__}. Required: {min_points_required}, Current: {self.current_points}")
                return pd.DataFrame()
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
```

### 3. 改进速率限制器

#### 问题定位
- 当前的全局速率限制器可能过于严格或不够灵活
- 没有根据API类别设置不同限制

#### 修复方案
创建一个更智能的速率限制器：

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional
import time
import threading

class ApiCategory(Enum):
    BASIC = "basic"
    DAILY = "daily"
    FINANCIAL = "financial"
    MARKET_FLOW = "market_flow"
    SPECIAL = "special"

@dataclass
class ApiLimitConfig:
    calls_per_minute: int
    min_points: int
    category: ApiCategory

class IntelligentRateLimiter:
    """
    智能速率限制器，根据API类别和用户积分动态调整限制
    """

    def __init__(self, user_points: int):
        self.user_points = user_points
        self._lock = threading.Lock()
        self._buckets: Dict[str, dict] = {}

        # 根据用户积分设置不同API的限制
        self.api_configs = self._create_api_configs()

    def _create_api_configs(self) -> Dict[str, ApiLimitConfig]:
        """
        根据用户积分创建API限制配置
        """
        base_limits = {
            'stock_basic': ApiLimitConfig(200, 0, ApiCategory.BASIC),
            'trade_cal': ApiLimitConfig(500, 0, ApiCategory.BASIC),
            'daily': ApiLimitConfig(500, 0, ApiCategory.DAILY),
            'daily_basic': ApiLimitConfig(200, 2000, ApiCategory.DAILY),
            'moneyflow': ApiLimitConfig(500, 0, ApiCategory.MARKET_FLOW),
            'income': ApiLimitConfig(200, 0, ApiCategory.FINANCIAL),
            'balancesheet': ApiLimitConfig(200, 0, ApiCategory.FINANCIAL),
            'cashflow': ApiLimitConfig(200, 0, ApiCategory.FINANCIAL),
        }

        # 根据用户积分调整限制
        adjusted_limits = {}
        for api_name, config in base_limits.items():
            adjusted_config = ApiLimitConfig(
                calls_per_minute=config.calls_per_minute,
                min_points=config.min_points,
                category=config.category
            )
            adjusted_limits[api_name] = adjusted_config

        return adjusted_limits

    def acquire(self, api_name: str, num_tokens: int = 1):
        """
        获取API调用权限
        """
        if api_name not in self.api_configs:
            # 未知API，使用默认限制
            calls_per_minute = 200
            min_points = 0
        else:
            config = self.api_configs[api_name]
            calls_per_minute = config.calls_per_minute
            min_points = config.min_points

        # 检查用户积分
        if self.user_points < min_points:
            raise PermissionError(f"Insufficient points. Required: {min_points}, Current: {self.user_points}")

        # 执行速率限制
        self._rate_limit_per_api(api_name, calls_per_minute, num_tokens)

    def _rate_limit_per_api(self, api_name: str, calls_per_minute: int, num_tokens: int = 1):
        """
        针对特定API的速率限制
        """
        with self._lock:
            if api_name not in self._buckets:
                tokens_per_second = calls_per_minute / 60.0
                max_tokens = calls_per_minute
                self._buckets[api_name] = {
                    'tokens_per_second': tokens_per_second,
                    'max_tokens': max_tokens,
                    'current_tokens': max_tokens,
                    'last_refill_time': time.time()
                }

            bucket = self._buckets[api_name]
            current_time = time.time()
            time_passed = current_time - bucket['last_refill_time']

            # 根据时间流逝补充令牌
            tokens_to_add = time_passed * bucket['tokens_per_second']
            bucket['current_tokens'] = min(
                bucket['max_tokens'],
                bucket['current_tokens'] + tokens_to_add
            )
            bucket['last_refill_time'] = current_time

            # 检查是否有足够的令牌
            if bucket['current_tokens'] >= num_tokens:
                # 有足够的令牌，直接扣除
                bucket['current_tokens'] -= num_tokens
                return

            # 令牌不足，计算需要等待的时间
            tokens_needed = num_tokens - bucket['current_tokens']
            wait_time = tokens_needed / bucket['tokens_per_second']

            # 等待直到有足够的令牌
            time.sleep(wait_time)

            # 更新令牌数量
            current_time = time.time()
            time_passed = current_time - bucket['last_refill_time']
            tokens_to_add = time_passed * bucket['tokens_per_second']
            bucket['current_tokens'] = min(
                bucket['max_tokens'],
                bucket['current_tokens'] + tokens_to_add
            )
            bucket['current_tokens'] -= num_tokens
            bucket['last_refill_time'] = current_time
```

### 4. 改进策略模式实现

#### 问题定位
- 策略模式中可能存在API名称和参数传递问题
- 权限检查未在策略层执行

#### 修复方案
创建带有权限检查的策略实现：

```python
class SecureDownloadStrategy(DownloadStrategy):
    """
    安全下载策略基类，包含权限检查
    """
    def __init__(self, downloader: TuShareDownloader):
        super().__init__(downloader)
        # 创建智能速率限制器
        self.rate_limiter = IntelligentRateLimiter(self.downloader.current_points)

    def _secure_download(self, api_func, api_name: str, min_points: int = 0, **params):
        """
        安全下载方法，包含权限检查、速率限制和错误处理
        """
        try:
            # 检查权限
            if self.downloader.current_points < min_points:
                self.downloader.logger.warning(f"Insufficient points for {api_name}. Required: {min_points}, Current: {self.downloader.current_points}")
                return pd.DataFrame()

            # 获取速率限制
            self.rate_limiter.acquire(api_name)

            # 执行下载
            result = api_func(**{k: v for k, v in params.items() if k != 'api_name'})

            return result
        except Exception as e:
            self.downloader.logger.error(f"Download failed for {api_name}: {e}")
            raise

class DailyDataDownloaderStrategy(SecureDownloadStrategy):
    """
    改进的日线数据下载策略
    """
    def download(self, **kwargs) -> pd.DataFrame:
        trade_date = kwargs.get('trade_date')
        api_name = kwargs.get('api_name', 'daily') or 'daily'  # 确保api_name不为None

        if api_name == 'daily':
            min_points = 0
            api_func = self.downloader.pro.daily_vip if self.downloader.current_points >= 5000 else self.downloader.pro.daily
            params = {
                'ts_code': kwargs.get('ts_code'),
                'start_date': trade_date,
                'end_date': trade_date
            }
        elif api_name == 'daily_basic':
            min_points = 2000
            api_func = self.downloader.pro.daily_basic
            params = {'trade_date': trade_date}
        elif api_name == 'moneyflow':
            min_points = 0
            api_func = self.downloader.pro.moneyflow
            params = {'trade_date': trade_date}
        else:
            # 默认处理
            api_func = getattr(self.downloader.pro, api_name, self.downloader.pro.daily)
            params = {'trade_date': trade_date}
            min_points = 0

        return self._secure_download(api_func, api_name, min_points, **params)
```

## 实施计划

### 第一阶段：API名称识别修复
1. 修改 `tushare_api.py` 中的 `download_with_retry` 方法
2. 创建 `_extract_api_name` 辅助方法
3. 更新 `download_strategies.py` 中的策略实现

### 第二阶段：权限检查增强
1. 实现智能速率限制器
2. 更新所有策略类以使用安全下载方法
3. 添加权限检查装饰器

### 第三阶段：系统集成与测试
1. 集成所有变更到 new2 分支
2. 进行功能测试
3. 验证修复效果

## 预期效果

1. **消除 `unknown_api` 调用**：确保所有API调用都有正确的名称标识
2. **修复权限错误**：确保只有有权限的用户才能访问相应API
3. **提高系统稳定性**：减少不必要的API调用和错误
4. **保持高性能**：维持并行下载的优势

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 速率限制过严 | 下载速度降低 | 根据实际API限制调整参数 |
| 权限检查过严 | 合法调用被拒绝 | 仔细验证每个API的权限要求 |
| 向后兼容性 | 现有功能失效 | 保持API接口签名不变 |

## 验证方法

1. **单元测试**：测试各个组件的API名称识别和权限检查
2. **集成测试**：运行小范围数据下载验证修复效果
3. **监控**：观察日志中是否存在 `unknown_api` 调用和权限错误