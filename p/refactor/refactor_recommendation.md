# ASPipe v4 重构建议

## 1. 当前代码分析总结

根据重构计划文档和代码分析，当前项目存在以下问题：

1. **架构混乱**：存在新旧架构并存（`ScoreBasedDownloader` vs `interfaces/`新架构）
2. **功能重叠**：多个下载器类（`DateRangeDownloader`、`ScoreBasedDownloader`、`EnhancedMainDownloader`）功能重叠
3. **复杂代理机制**：`tushare_api.py` 中使用 `__getattr__` 动态代理到子模块
4. **配置分散**：`config.py`、`score_config.py`、`download_config.py` 分散管理
5. **代码冗余**：多个文件中有重复的日期处理、分页下载、重试逻辑

## 2. 重构建议（按重构计划步骤）

### 2.1 第一步：整合配置管理

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

### 2.2 第二步：统一API调用层

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
```

### 2.3 第三步：重构下载逻辑层

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

### 2.4 第四步：创建通用工具模块

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

### 2.5 第五步：优化接口设计

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

## 3. 重构实施策略

### 3.1 渐进式重构计划

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

### 3.2 风险控制措施

1. **保留旧代码备份**：在重构过程中保留原始代码作为备份
2. **渐进式替换**：逐步替换旧模块，而非一次性全部替换
3. **全面测试**：为重构后的代码编写全面的测试用例
4. **向后兼容**：确保重构后的代码兼容现有功能

### 3.3 代码质量提升措施

1. **减少代码行数**：通过消除重复代码和功能重叠，预计减少30%以上
2. **提高可维护性**：清晰的模块职责划分，便于后续维护
3. **性能优化**：改进并行下载逻辑，提高下载效率
4. **内存优化**：优化数据处理，减少内存使用

## 4. 预期效果

通过以上重构，ASPip v4 项目将实现：

1. **架构清晰**：分层架构明确，模块职责清晰
2. **代码精简**：消除冗余代码，减少维护成本
3. **性能提升**：优化后的并行下载和内存管理
4. **易于扩展**：模块化设计便于添加新的数据类型

重构后的代码将更加清晰、高效、易于维护，为后续的功能扩展和性能优化奠定基础。