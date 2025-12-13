# ASPipe v4 统一重构方案

## 1. 项目现状与问题分析

### 1.1 当前架构概述

ASPip v4 是一个基于 TuShare API 的中国股市数据自动化下载平台，根据用户的 TuShare 积分级别自动下载所有可用的金融数据，并将其保存为高效的 Parquet 格式。

### 1.2 项目结构现状

```
aspipe_v4/app/
├── main.py                      # 主入口程序
├── config.py                    # 配置管理
├── tushare_api.py              # TuShare API 集成（新架构）
├── data_storage.py             # 数据存储管理
├── date_range_downloader.py    # 日期范围下载器（主要下载逻辑）
├── score_based_downloader.py   # 积分基础下载器（旧下载逻辑）
├── enhanced_main_downloader.py # 增强主下载器（中间层）
├── error_handler.py            # 错误处理和重试
├── score_config.py             # 积分配置定义
├── download_config.py          # 下载配置
└── interfaces/                 # 数据接口模块（新的模块化设计）
    ├── base.py                 # 基础接口类
    ├── basic_data.py           # 基础数据接口
    ├── daily_data.py           # 日线数据接口
    ├── financial_data.py       # 财务数据接口
    ├── holders_data.py         # 股东信息接口
    ├── market_flow.py          # 市场资金流向接口
    ├── technical_factors.py    # 技术因子接口
    ├── market_structure.py     # 市场结构接口
    └── research_data.py        # 研究数据接口
```

### 1.3 当前存在的问题

#### 1.3.1 功能重叠的下载器
- **DateRangeDownloader**：主要下载逻辑，按日期范围下载数据
- **ScoreBasedDownloader**：旧的下载逻辑，基于积分下载数据
- **EnhancedMainDownloader**：中间层下载器，协调不同下载逻辑
- **ParallelDownloader**：DateRangeDownloader 内部的并行下载类
- 多个下载器之间功能重叠，代码重复，维护成本高

#### 1.3.2 新旧架构并存
- **旧架构**：直接在下载器中调用 API（如 ScoreBasedDownloader）
- **新架构**：通过 interfaces/ 目录下的模块化接口调用（如 tushare_api.py）
- 两种架构混合使用，导致代码混乱

#### 1.3.3 复杂的代理机制
- tushare_api.py 中使用 __getattr__ 动态代理到各个子模块
- 代理逻辑复杂，难以调试和维护
- 方法查找顺序不明确，容易导致意外行为

#### 1.3.4 配置文件分散
- 配置分散在多个文件中：config.py、score_config.py、download_config.py
- 缺乏统一的配置管理机制
- 配置加载逻辑重复

#### 1.3.5 代码冗余
- 日期范围生成、分页下载、重试机制等功能重复实现
- 日志记录和错误处理逻辑分散
- API 调用逻辑重复

## 2. 重构目标

### 2.1 架构优化
- 建立清晰的分层架构
- 明确各模块职责
- 提高代码的可维护性和扩展性

### 2.2 功能整合
- 移除冗余的下载器类
- 统一 API 调用逻辑
- 整合配置管理
- 提取通用功能模块

### 2.3 性能提升
- 优化并行下载逻辑
- 改进缓存机制
- 优化内存使用

### 2.4 向后兼容
- 确保重构后的代码兼容现有功能
- 支持现有配置和调用方式

## 3. 重构方案设计

### 3.1 分层架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     业务逻辑层                           │
│  - main.py（主入口）                                      │
└─────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────┐
│                     下载逻辑层                           │
│  - DownloadManager（统一下载管理器）                       │
│  - DateRangeProcessor（日期范围处理）                     │
│  - ScoreBasedSelector（积分基础数据选择）                  │
└─────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────┐
│                     API 调用层                           │
│  - TuShareAPIManager（统一 API 管理器）                    │
│  - Interfaces/（模块化接口实现）                           │
└─────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────┐
│                     基础设施层                           │
│  - ConfigManager（统一配置管理）                          │
│  - ErrorHandler（统一错误处理）                           │
│  - DataStorage（数据存储管理）                           │
│  - UtilityTools（通用工具函数）                           │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心类设计

| 类名 | 职责 | 文件位置 |
|------|------|----------|
| ConfigManager | 统一配置管理，加载和管理所有配置 | app/config_manager.py |
| TuShareAPIManager | 统一 API 调用管理，处理令牌切换和速率限制 | app/api_manager.py |
| DownloadManager | 统一下载管理器，协调所有下载任务 | app/download_manager.py |
| DateRangeProcessor | 日期范围处理，生成交易日历和日期批次 | app/utils/date_processor.py |
| ScoreBasedSelector | 基于积分选择可用的数据类型 | app/utils/score_selector.py |
| ParallelDownloader | 并行下载管理器，优化下载性能 | app/utils/parallel_downloader.py |
| RetryHandler | 统一重试机制，处理 API 调用失败 | app/utils/retry_handler.py |

## 4. 重构实施计划

### 4.1 第一步：整合配置管理

创建 `config_manager.py`，将所有配置统一管理：

```python
# app/config_manager.py
"""
统一配置管理器
"""
import os
import logging
from dotenv import load_dotenv
from pathlib import Path
import json
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_file: str = None):
        """初始化配置管理器"""
        load_dotenv('/home/quan/testdata/aspipe_v4/.env')

        # 基础配置
        self.tushare_token = self._get_token()
        self.primary_token = os.getenv('tushare_token')
        self.secondary_token = os.getenv('tushare2_token')

        # 积分相关配置
        self.tushare_points = self._get_points()
        self.proxy_url = self._get_proxy_url()

        # API限制配置
        self.api_limits = self._get_api_limits()

        # 数据目录配置
        self.data_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / 'data'
        self.data_dir.mkdir(exist_ok=True)

        # 默认参数配置
        self.default_start_date = os.getenv('DEFAULT_START_DATE', '20100101')
        self.default_end_date = os.getenv('DEFAULT_END_DATE', '20231231')
        self.stock_limit = int(os.getenv('STOCK_LIMIT', '50'))

        # 下载配置
        self.download_config = self._get_download_config()

        # 评分配置
        self.score_requirements = self._get_score_requirements()

    def _get_token(self):
        """获取当前使用的token"""
        token = os.getenv('tushare_token')
        secondary_token = os.getenv('tushare2_token')

        if not token:
            if secondary_token:
                return secondary_token
            else:
                raise ValueError("No TUSHARE_TOKEN found in environment variables")

        return token

    def _get_points(self):
        """获取当前积分"""
        token = os.getenv('tushare_token')
        secondary_token = os.getenv('tushare2_token')

        if token and token == os.getenv('tushare_token'):
            return int(os.getenv('tushare_points', '120'))
        elif secondary_token:
            return int(os.getenv('tushare2_points', '2000'))

        return 120  # 默认积分

    def _get_proxy_url(self):
        """获取代理URL"""
        return os.getenv('PROXY_URL', '')

    def _get_api_limits(self):
        """获取API限制配置"""
        return {
            'daily': {'calls_per_minute': 500 if self.tushare_points >= 5000 else 200},
            'stock_basic': {'calls_per_minute': 200},
            'daily_basic': {'calls_per_minute': 500 if self.tushare_points >= 5000 else 200},
            'income': {'calls_per_minute': 200 if self.tushare_points >= 5000 else 100},
            'balancesheet': {'calls_per_minute': 200 if self.tushare_points >= 5000 else 100},
            'cashflow': {'calls_per_minute': 200 if self.tushare_points >= 5000 else 100},
            'fina_indicator': {'calls_per_minute': 200 if self.tushare_points >= 5000 else 100},
        }

    def _get_download_config(self):
        """获取下载配置"""
        # 从下载配置文件加载或使用默认值
        return {}

    def _get_score_requirements(self):
        """获取评分要求"""
        # 从评分配置文件加载
        return {}

    def get_available_data_types(self):
        """获取当前积分下可用的数据类型"""
        available_types = {
            'basic': set(),
            'daily': set(),
            'financial': set(),
            'holders': set(),
            'events': set(),
            'market_structure': set(),
            'funds': set(),
            'research': set(),
            'others': set()
        }

        # 根据当前积分获取可用数据类型
        # 从SCORE_REQUIREMENTS获取数据
        # ...

        # Convert sets back to lists
        for category in available_types:
            available_types[category] = list(available_types[category])

        return available_types
```

### 4.2 第二步：统一API调用层

创建 `api_manager.py`，移除复杂的代理机制：

```python
# app/api_manager.py
"""
统一API管理器
"""
import tushare as ts
import time
import logging
from typing import Optional, Dict, Any
import pandas as pd
from .config_manager import ConfigManager
from .utils.retry_handler import RetryHandler
from .interfaces.basic_data import BasicDataDownloader
from .interfaces.daily_data import DailyDataDownloader
from .interfaces.financial_data import FinancialDataDownloader
from .interfaces.holders_data import HoldersDataDownloader
from .interfaces.market_flow import MarketFlowDownloader
from .interfaces.technical_factors import TechnicalFactorsDownloader
from .interfaces.market_structure import MarketStructureDownloader
from .interfaces.research_data import ResearchDataDownloader

class TuShareAPIManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.primary_token = self.config.primary_token
        self.secondary_token = self.config.secondary_token
        self.current_token = self.config.tushare_token
        self.current_points = self.config.tushare_points
        self.current_proxy = self.config.proxy_url

        # 设置代理
        if self.current_proxy:
            import os
            os.environ["HTTP_PROXY"] = self.current_proxy
            os.environ["HTTPS_PROXY"] = self.current_proxy

        # 初始化API
        self.pro = ts.pro_api(self.current_token)

        # API限制和调用时间记录
        self.api_limits = self.config.api_limits
        self.last_call_times = {}

        self.logger = logging.getLogger(__name__)

        # 初始化各个接口模块
        self.basic_data = BasicDataDownloader(self.pro, self.config)
        self.daily_data = DailyDataDownloader(self.pro, self.config)
        self.financial_data = FinancialDataDownloader(self.pro, self.config)
        self.market_flow = MarketFlowDownloader(self.pro, self.config)
        self.holders_data = HoldersDataDownloader(self.pro, self.config)
        self.technical_factors = TechnicalFactorsDownloader(self.pro, self.config)
        self.market_structure = MarketStructureDownloader(self.pro, self.config)
        self.research_data = ResearchDataDownloader(self.pro, self.config)

        # 重试处理器
        self.retry_handler = RetryHandler()

    def switch_token(self):
        """切换到备用token"""
        if self.primary_token and self.secondary_token:
            if self.current_token == self.primary_token:
                # 切换到备用token
                self.current_token = self.secondary_token
                self.current_points = int(os.getenv('tushare2_points', '2000'))
                self.current_proxy = os.getenv('PROXY_URL2', '')
                self.logger.info("Switching to secondary token")
            else:
                # 切换回主token
                self.current_token = self.primary_token
                self.current_points = int(os.getenv('tushare_points', '120'))
                self.current_proxy = os.getenv('PROXY_URL', '')
                self.logger.info("Switching to primary token")

            # 更新代理设置
            if self.current_proxy:
                import os
                os.environ["HTTP_PROXY"] = self.current_proxy
                os.environ["HTTPS_PROXY"] = self.current_proxy
            else:
                # 清除代理
                if "HTTP_PROXY" in os.environ:
                    del os.environ["HTTP_PROXY"]
                if "HTTPS_PROXY" in os.environ:
                    del os.environ["HTTPS_PROXY"]

            # 重新初始化API
            self.pro = ts.pro_api(self.current_token)
            # 更新API限制
            self.api_limits = self._get_updated_api_limits()

    def _rate_limit(self, api_name: str) -> None:
        """实现速率限制"""
        current_time = time.perf_counter()

        # 获取此API的速率限制
        api_config = self.api_limits.get(api_name, {'calls_per_minute': 200})
        calls_per_minute = api_config['calls_per_minute']

        # 添加随机性以避免被识别为自动化脚本
        import random
        min_interval = (60.0 / calls_per_minute) * random.uniform(0.8, 1.2)

        # 检查是否最近调用过此API
        if api_name in self.last_call_times:
            elapsed = current_time - self.last_call_times[api_name]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                self.logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
                time.sleep(min_interval)

        self.last_call_times[api_name] = current_time

    @retry_on_failure(max_retries=3, delay=1.0, backoff=2.0)
    def download_with_retry(self, api_func, *args, max_retries: int = 3, **kwargs):
        """
        下载数据带重试机制
        """
        api_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown_api'

        for attempt in range(max_retries + 1):
            try:
                # 实现速率限制
                self._rate_limit(api_name)

                # 调用API
                result = api_func(*args, **kwargs)

                self.logger.info(f"Successfully called {api_name}, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                return result

            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {api_name}: {str(e)}")

                # 检查是否与token认证相关
                error_msg = str(e).lower()
                if "token" in error_msg or "auth" in error_msg:
                    # 尝试切换到另一个token
                    if self.primary_token and self.secondary_token:
                        self.switch_token()
                        self.logger.info(f"Switched token due to authentication error. Retrying {api_name}...")
                        # 用新token重试
                        try:
                            result = api_func(*args, **kwargs)
                            self.logger.info(f"Successfully called {api_name} after token switch, got {len(result) if hasattr(result, '__len__') else 'unknown'} records")
                            return result
                        except Exception as retry_e:
                            self.logger.warning(f"Retry with switched token failed for {api_name}: {str(retry_e)}")

                if attempt == max_retries:
                    self.logger.error(f"All {max_retries + 1} attempts failed for {api_name}")

                # 指数退避：每次重试等待更长时间
                wait_time = 2 ** attempt
                self.logger.info(f"Waiting {wait_time}s before next attempt...")
                time.sleep(wait_time)
```

### 4.3 第三步：重构下载逻辑层

创建 `download_manager.py`，整合所有下载逻辑：

```python
# app/download_manager.py
"""
统一下载管理器
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional, Tuple
from .api_manager import TuShareAPIManager
from .config_manager import ConfigManager
from .utils.date_processor import DateRangeProcessor
from .utils.score_selector import ScoreBasedSelector
from .utils.parallel_downloader import ParallelDownloader
from .utils.retry_handler import RetryHandler
from .data_storage import DataStorage

class DownloadManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.api_manager = TuShareAPIManager(config_manager)
        self.date_processor = DateRangeProcessor()
        self.score_selector = ScoreBasedSelector(config_manager)
        self.parallel_downloader = ParallelDownloader(config_manager)
        self.data_storage = DataStorage(config_manager)
        self.retry_handler = RetryHandler()

        self.logger = logging.getLogger(__name__)
        self.available_types = self.score_selector.get_available_data_types()

    def download_all_available_data(self, start_date: str, end_date: str = None) -> Dict[str, Any]:
        """下载所有可用数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')

        self.logger.info(f"开始下载日期范围 {start_date} 到 {end_date} 的所有可用数据")

        # 创建下载任务列表
        download_tasks = self._create_download_task_list(start_date, end_date)

        # 跟踪失败尝试和已完成任务
        failed_attempts = {}
        completed_tasks = set()
        original_task_count = len(download_tasks)

        # 智能下载循环
        while len(completed_tasks) < original_task_count and download_tasks:
            # 检查是否所有任务都已达到最大重试次数
            all_max_retries_reached = True
            for task_name, _, max_retries in download_tasks:
                if failed_attempts.get(task_name, 0) < max_retries:
                    all_max_retries_reached = False
                    break

            if all_max_retries_reached:
                self.logger.info("所有剩余任务都已达到最大重试次数，退出。")
                break

            if not download_tasks:  # 确保任务队列不为空
                break

            task_name, download_func, max_retries = download_tasks[0]

            # 检查此任务是否已达到最大重试次数
            if failed_attempts.get(task_name, 0) >= max_retries:
                self.logger.info(f"{task_name} 已达到最大重试次数 {max_retries}，跳过任务")
                download_tasks.pop(0)  # 直接移除不再尝试
                continue

            task_completed = False

            try:
                self.logger.info(f"开始下载数据类型: {task_name}")
                result = download_func()

                if result is not None:  # 空dict或0也算成功
                    yield {task_name: result}  # 返回结果，可能需要根据实际需求调整
                    task_completed = True
                    self.logger.info(f"✅ {task_name} 下载成功")
                else:
                    self.logger.warning(f"{task_name} 返回空结果")
                    task_completed = True  # 空结果也视为完成，不是失败

            except Exception as e:
                failed_attempts[task_name] = failed_attempts.get(task_name, 0) + 1
                self.logger.error(f"❌ {task_name} 下载失败 (尝试 {failed_attempts[task_name]}/{max_retries}): {e}")

                if failed_attempts[task_name] >= max_retries:
                    self.logger.warning(f"{task_name} 达到最大重试次数 {max_retries}，不再重试")
                    download_tasks.pop(0)  # 达到重试上限，直接移除任务
                else:
                    # 任务失败但仍需重试，移到队列末尾
                    download_tasks.append(download_tasks.pop(0))

            finally:
                if task_completed:
                    completed_tasks.add(task_name)
                    if download_tasks:  # 确保列表不为空
                        download_tasks.pop(0)  # 移除已完成的任务

        self.logger.info("日期范围数据下载完成")

    def _create_download_task_list(self, start_date: str, end_date: str) -> List[Tuple[str, callable, int]]:
        """创建下载任务列表"""
        tasks = []

        # 日度数据 - 高优先级
        daily_types = self._get_daily_types()
        for data_type in daily_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type,
                             lambda dt=data_type: self._download_daily_type_for_range(dt, start_date, end_date),
                             3))

        # 静态数据 - 高优先级
        static_types = self._get_static_types()
        for data_type in static_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type,
                             lambda dt=data_type: self._download_static_type(dt),
                             3))

        # 财务数据 - 中等优先级
        financial_types = self._get_financial_types()
        for data_type in financial_types:
            if self._is_data_type_available(data_type):
                tasks.append((data_type,
                             lambda dt=data_type: self._download_financial_type_for_range(dt, start_date, end_date),
                             3))

        return tasks

    def _is_data_type_available(self, data_type: str) -> bool:
        """检查数据类型是否在用户积分范围内可用"""
        for category_types in self.available_types.values():
            if data_type in category_types:
                return True
        return False

    # ... 其他下载方法的实现
```

### 4.4 第四步：创建通用工具模块

创建 `utils/` 目录及其中的工具模块：

```python
# app/utils/date_processor.py
"""
日期处理工具
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import List
import logging

class DateRangeProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_trading_days(self, start_date: str, end_date: str, api_manager) -> List[str]:
        """获取指定日期范围内的交易日列表"""
        try:
            # 先下载交易日历数据
            trade_cal = api_manager.basic_data.download_trade_cal(
                start_date=start_date,
                end_date=end_date
            )

            # 过滤出交易日（is_open=1）
            trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            trading_days.sort()

            self.logger.info(f"获取到 {len(trading_days)} 个交易日")
            return trading_days

        except Exception as e:
            self.logger.error(f"获取交易日历失败: {e}")
            # 如果无法获取交易日历，返回日期范围内的所有日期作为备选
            return self._generate_date_range(start_date, end_date)

    def _generate_date_range(self, start_date: str, end_date: str) -> List[str]:
        """生成日期范围内的所有日期（作为备选方案）"""
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')

        date_list = []
        current = start
        while current <= end:
            date_list.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)

        return date_list
```

### 4.5 第五步：优化接口设计

简化 `interfaces/` 目录下的接口设计，明确各接口职责：

```python
# app/interfaces/daily_data.py (示例)
"""
日度数据接口实现
"""
from .base import BaseDownloader
import pandas as pd

class DailyDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api)
        self.config = config_manager

    def download_daily_data(self, ts_code=None, start_date=None, end_date=None):
        """下载日线数据"""
        return self.safe_download(
            self.pro.daily,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

    def download_daily_basic(self, trade_date=None):
        """下载每日指标数据"""
        return self.safe_download(
            self.pro.daily_basic,
            trade_date=trade_date
        )
```

## 5. 实施策略

### 5.1 渐进式重构计划

1. **第一阶段：配置整合**
   - 创建 `config_manager.py`
   - 将现有配置文件整合到新模块中
   - 更新所有引用旧配置文件的代码

2. **第二阶段：API层重构**
   - 创建 `api_manager.py`
   - 移除 `tushare_api.py` 中的复杂代理机制
   - 将API调用统一到新管理器中

3. **第三阶段：下载逻辑重构**
   - 创建 `download_manager.py`
   - 移除冗余下载器类
   - 整合下载逻辑到统一管理器

4. **第四阶段：工具模块提取**
   - 创建 `utils/` 目录
   - 提取通用功能到相应工具模块

5. **第五阶段：接口优化**
   - 简化 `interfaces/` 目录下的接口设计

### 5.2 风险控制措施

1. **保留旧代码备份**：在重构过程中保留原始代码作为备份
2. **渐进式替换**：逐步替换旧模块，而非一次性全部替换
3. **全面测试**：为重构后的代码编写全面的测试用例
4. **向后兼容**：确保重构后的代码兼容现有功能

### 5.3 代码质量提升措施

1. **减少代码行数**：通过消除重复代码和功能重叠，预计减少30%以上
2. **提高可维护性**：清晰的模块职责划分，便于后续维护
3. **性能优化**：改进并行下载逻辑，提高下载效率
4. **内存优化**：优化数据处理，减少内存使用

## 6. 预期效果

通过以上重构，ASPip v4 项目将实现：

1. **架构清晰**：分层架构明确，模块职责清晰
2. **代码精简**：消除冗余代码，减少维护成本
3. **性能提升**：优化后的并行下载和内存管理
4. **易于扩展**：模块化设计便于添加新的数据类型

重构后的代码将更加清晰、高效、易于维护，为后续的功能扩展和性能优化奠定基础。

## 7. 结论

当前ASPip v4项目存在多个下载器类功能重叠、架构混乱、代码冗余等问题，影响了代码的可维护性和性能。通过本次重构，我们将建立清晰的分层架构，整合冗余功能，优化API调用和下载逻辑，提高代码的可维护性和扩展性。重构后的代码将更加清晰、高效、易于维护，为后续的功能扩展和性能优化奠定基础。

## 8. 后续建议

1. 建立代码审查机制，确保代码质量
2. 定期进行性能测试，优化系统性能
3. 完善监控和日志系统，便于问题排查
4. 建立文档更新机制，确保文档与代码同步
5. 考虑引入自动化测试，提高测试效率
6. 探索更高效的数据存储格式和压缩算法
7. 考虑支持分布式下载，进一步提高下载速度