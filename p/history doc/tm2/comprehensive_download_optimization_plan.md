# 综合下载优化方案 (Comprehensive Download Optimization Plan)

本文档结合 `improvement_suggestions.md` 和 `parallel_download_solution.md` 的思想，并基于对现有代码（`date_range_downloader.py`, `tushare_api.py`, `download_config.py`, `data_storage.py`）的分析，提出一个统一、可执行的下载模块重构和优化方案。

## 1. 核心问题 (Core Issues)

1.  **串行执行**: `DateRangeDownloader.download_all_available_data` 按顺序下载不同数据类型，无法利用多核CPU和网络带宽，效率低下。
2.  **逻辑高度耦合**: `date_range_downloader.py` 中存在大量基于 `data_type` 的 `if/elif` 判断，新增或修改接口需要改动核心代码，违反“开闭原则”。
3.  **下载与存储阻塞**: 下载线程在获取数据后立即执行 `save_to_parquet`，磁盘I/O操作会阻塞后续的下载任务，在并行场景下严重影响吞吐量。
4.  **配置能力薄弱**: `download_config.py` 仅提供布尔开关，无法定义任务优先级、重试策略、资源分配等高级配置。
5.  **API频率控制不完善**: `tushare_api.py` 中的速率限制是实例级的，在多线程或多实例场景下，无法保证全局API调用不超频。

## 2. 目标架构 (Target Architecture)

我们将采用一个**配置驱动**的、基于**策略模式**和**生产者-消费者模式**的并行下载架构。

![Target Architecture Diagram](https://i.imgur.com/example.png)  <!-- 这是一个占位符，实际可以用工具生成图表 -->

**核心组件:**

1.  **`DownloadScheduler` (下载调度器)**: 系统的总入口，取代现有的 `DateRangeDownloader` 主逻辑。它负责：
    *   读取增强后的配置文件。
    *   根据配置初始化一个**任务队列** (`task_queue`)。
    *   创建一个**存储队列** (`storage_queue`)。
    *   启动并管理下载工作者（生产者）和存储工作者（消费者）。

2.  **`DownloaderStrategy` (下载策略接口)**: 一个定义了 `download()` 方法的抽象基类。
    *   **`ConcreteDownloader` (具体下载策略)**: 每个 `ConcreteDownloader` 实现 `DownloaderStrategy` 接口，封装特定数据类型（如 `daily`, `financial`）的下载逻辑。它知道调用哪个 `tushare_api` 函数以及如何传递参数。

3.  **`DownloadWorker` (下载工作者 - 生产者)**:
    *   从 `task_queue` 中获取下载任务。
    *   使用**策略模式**，找到并执行对应的 `DownloaderStrategy`。
    *   在执行下载前，向**全局速率限制器**请求许可。
    *   将下载到的数据（DataFrame）和元信息（文件名、子目录等）打包成一个“存储对象”，放入 `storage_queue`。

4.  **`StorageWorker` (存储工作者 - 消费者)**:
    *   从 `storage_queue` 中获取“存储对象”。
    *   调用 `data_storage.py` 中的函数将数据写入磁盘。

5.  **`GlobalRateLimiter` (全局速率限制器)**:
    *   采用令牌桶算法，在**全局（进程级）**范围内控制API调用频率，确保所有线程/进程共享同一个限制。

6.  **`EnhancedConfig` (增强配置)**:
    *   使用 YAML 或扩展的 Python 字典，为每个接口定义详细参数，如 `enabled`, `priority`, `downloader_strategy`, `max_retries`, `required_points`。

## 3. 实施步骤 (Implementation Steps)

### 第1步：增强配置 (`download_config.py`)

将 `download_config.py` 升级为更结构化的配置。

**`app/download_config.py` (示例):**
```python
# app/download_config.py

# 定义策略类名称的映射，这将在后续步骤中创建
STRATEGY_MAPPING = {
    "daily": "DailyDataDownloaderStrategy",
    "daily_basic": "DailyBasicDataDownloaderStrategy",
    "financial": "FinancialDataDownloaderStrategy",
    "static": "StaticDataDownloaderStrategy",
    # ... etc.
}

DOWNLOAD_PIPELINE_CONFIG = {
    # 日线行情
    'daily': {
        'enabled': True,
        'priority': 10,
        'strategy': STRATEGY_MAPPING["daily"],
        'max_retries': 3,
        'required_points': 0,
    },
    # 日线基础指标
    'daily_basic': {
        'enabled': True,
        'priority': 10,
        'strategy': STRATEGY_MAPPING["daily_basic"],
        'max_retries': 5, # 此接口较慢，增加重试
        'required_points': 0,
    },
    # 财务数据 (VIP接口)
    'income_vip': {
        'enabled': True,
        'priority': 5,
        'strategy': STRATEGY_MAPPING["financial"],
        'api_name': 'income_vip', # 传递给策略的具体API
        'max_retries': 3,
        'required_points': 5000,
    },
    # 静态数据
    'stock_basic': {
        'enabled': True,
        'priority': 100, # 最高优先级
        'strategy': STRATEGY_MAPPING["static"],
        'api_name': 'download_stock_basic',
        'max_retries': 2,
        'required_points': 0,
    },
    # ... 为所有接口添加类似配置
}

def get_active_download_tasks(user_points: int):
    """根据用户积分和配置过滤出激活的任务"""
    active_tasks = []
    for data_type, config in DOWNLOAD_PIPELINE_CONFIG.items():
        if (config['enabled'] and user_points >= config['required_points']):
            active_tasks.append((data_type, config))
    # 按优先级排序
    active_tasks.sort(key=lambda x: x[1]['priority'], reverse=True)
    return active_tasks
```

### 第2步：定义下载策略 (`app/download_strategies.py`)

创建新的文件 `app/download_strategies.py` 来存放所有策略类。

```python
# app/download_strategies.py
from abc import ABC, abstractmethod
import pandas as pd
from app.tushare_api import TuShareDownloader

class DownloadStrategy(ABC):
    """下载策略接口"""
    def __init__(self, downloader: TuShareDownloader):
        self.downloader = downloader

    @abstractmethod
    def download(self, **kwargs) -> pd.DataFrame:
        pass

class DailyDataDownloaderStrategy(DownloadStrategy):
    """日线行情下载策略 (针对 daily, moneyflow 等)"""
    def download(self, trade_date: str, **kwargs) -> pd.DataFrame:
        api_name = kwargs.get('api_name', 'daily') # 'daily', 'moneyflow' 等
        api_method = getattr(self.downloader.daily_data, f"download_{api_name}")
        return api_method(trade_date=trade_date)

class FinancialDataDownloaderStrategy(DownloadStrategy):
    """财务数据下载策略"""
    def download(self, period: str, **kwargs) -> pd.DataFrame:
        api_name = kwargs.get('api_name') # 'income_vip', 'balancesheet_vip'
        api_method = getattr(self.downloader.financial_data, f"download_{api_name}")
        return api_method(period=period)

class StaticDataDownloaderStrategy(DownloadStrategy):
    """静态数据下载策略"""
    def download(self, **kwargs) -> pd.DataFrame:
        api_name = kwargs.get('api_name') # 'download_stock_basic'
        api_method = getattr(self.downloader.basic_data, api_name)
        return api_method()

# ... 为其他数据类型实现对应的策略类
# 例如，处理分页的策略
class PaginatedDownloadStrategy(DownloadStrategy):
    def download(self, trade_date: str, **kwargs) -> pd.DataFrame:
        api_name = kwargs.get('api_name') # 'cyq_chips_paginated'
        api_method = getattr(self.downloader.cyq_chips, f"download_{api_name}")
        return api_method(trade_date=trade_date)

# 策略工厂
def get_strategy(strategy_name: str, downloader: TuShareDownloader) -> DownloadStrategy:
    strategies = {
        "DailyDataDownloaderStrategy": DailyDataDownloaderStrategy,
        "FinancialDataDownloaderStrategy": FinancialDataDownloaderStrategy,
        "StaticDataDownloaderStrategy": StaticDataDownloaderStrategy,
        "PaginatedDownloadStrategy": PaginatedDownloadStrategy,
    }
    strategy_class = strategies.get(strategy_name)
    if not strategy_class:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    return strategy_class(downloader)

```

### 第3步：实现全局速率限制器 (`app/rate_limiter.py`)

创建一个线程安全的全局速率限制器。

```python
# app/rate_limiter.py
import time
import threading

class GlobalRateLimiter:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, calls_per_minute: int = 500):
        with self._lock:
            if not hasattr(self, '_initialized'):
                self.calls_per_minute = calls_per_minute
                self.min_interval = 60.0 / self.calls_per_minute
                self.last_call_time = 0
                self._initialized = True

    def acquire(self):
        with self._lock:
            current_time = time.perf_counter()
            elapsed = current_time - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_call_time = time.perf_counter()

# 在 tushare_api.py 中使用
# from app.rate_limiter import GlobalRateLimiter
# self.rate_limiter = GlobalRateLimiter()
# ...
# self.rate_limiter.acquire()
# # API call
```
**修改 `tushare_api.py`**：移除旧的 `_rate_limit` 方法，转而使用这个全局单例。

### 第4步：重构 `DateRangeDownloader` 为 `DownloadScheduler`

重命名并重构 `date_range_downloader.py` 为 `download_scheduler.py`。

```python
# app/download_scheduler.py
import logging
from queue import Queue
from threading import Thread
from app.tushare_api import TuShareDownloader
from app.data_storage import save_to_parquet
from app.download_config import get_active_download_tasks
from app.download_strategies import get_strategy

class DownloadScheduler:
    def __init__(self, start_date: str, end_date: str, max_download_workers: int = 4, max_storage_workers: int = 2):
        self.start_date = start_date
        self.end_date = end_date
        self.logger = logging.getLogger(__name__)
        self.downloader = TuShareDownloader() # 包含 rate_limiter
        
        self.task_queue = Queue()
        self.storage_queue = Queue()

        self.max_download_workers = max_download_workers
        self.max_storage_workers = max_storage_workers

    def _populate_task_queue(self):
        # 伪代码：根据日期范围和配置生成所有具体的下载任务
        # 例如，对于日度数据，每天都是一个任务
        trading_days = self.downloader.basic_data.download_trade_cal(...)
        active_tasks_config = get_active_download_tasks(self.downloader.current_points)

        for data_type, config in active_tasks_config:
            # 简化示例：假设所有任务都是按天
            for day in trading_days:
                task_info = {
                    "data_type": data_type,
                    "config": config,
                    "params": {"trade_date": day}, # 传递给策略的参数
                    "save_info": {"subdir": f"daily/{day[:4]}/{day[4:6]}", "filename": f"{data_type}_{day}"}
                }
                self.task_queue.put(task_info)
        self.logger.info(f"Populated task queue with {self.task_queue.qsize()} tasks.")


    def _download_worker(self):
        """生产者：执行下载任务"""
        while not self.task_queue.empty():
            try:
                task = self.task_queue.get_nowait()
                data_type = task['data_type']
                config = task['config']
                strategy_name = config['strategy']
                
                self.logger.info(f"Starting download for {data_type} with params {task['params']}")

                # 获取策略并执行
                strategy = get_strategy(strategy_name, self.downloader)
                # 传递给 download 方法的参数应包含 api_name
                download_params = {**task['params'], 'api_name': config.get('api_name')}
                df = strategy.download(**download_params)

                if df is not None and not df.empty:
                    storage_task = {"data": df, "save_info": task['save_info']}
                    self.storage_queue.put(storage_task)
                    self.logger.info(f"✅ Success: {data_type} for {task['params']}. Added to storage queue.")
                else:
                    self.logger.warning(f"No data for {data_type} with params {task['params']}")

            except Exception as e:
                self.logger.error(f"Error in download worker: {e}", exc_info=True)
            finally:
                self.task_queue.task_done()

    def _storage_worker(self):
        """消费者：执行存储任务"""
        while True: # 持续运行直到收到哨兵信号
            storage_task = self.storage_queue.get()
            if storage_task is None: # 哨兵值，表示任务结束
                break
            
            try:
                df = storage_task["data"]
                save_info = storage_task["save_info"]
                save_to_parquet(df, save_info['filename'], save_info['subdir'])
            except Exception as e:
                self.logger.error(f"Error saving file {save_info['filename']}: {e}", exc_info=True)
            finally:
                self.storage_queue.task_done()

    def run(self):
        self.logger.info("Starting download scheduler...")
        self._populate_task_queue()

        # 启动存储工作者
        storage_threads = []
        for _ in range(self.max_storage_workers):
            t = Thread(target=self._storage_worker)
            t.start()
            storage_threads.append(t)

        # 启动下载工作者
        download_threads = []
        for _ in range(self.max_download_workers):
            t = Thread(target=self._download_worker)
            t.start()
            download_threads.append(t)
        
        # 等待所有下载任务完成
        self.task_queue.join()
        self.logger.info("All download tasks have been processed.")

        # 等待所有存储任务完成
        self.storage_queue.join()
        self.logger.info("All storage tasks have been processed.")

        # 发送哨兵信号停止存储线程
        for _ in range(self.max_storage_workers):
            self.storage_queue.put(None)

        # 等待所有线程结束
        for t in download_threads + storage_threads:
            t.join()

        self.logger.info("Download scheduler finished.")
```

### 第5步：更新项目入口 (`main.py`)

修改 `main.py`，使用新的 `DownloadScheduler`。

```python
# app/main.py
# from app.date_range_downloader import main_download_by_date_range (旧)
from app.download_scheduler import DownloadScheduler # (新)

def main():
    # ... (解析命令行参数)
    scheduler = DownloadScheduler(start_date, end_date, max_download_workers=8, max_storage_workers=4)
    scheduler.run()

if __name__ == "__main__":
    main()
```

## 4. 预期收益 (Expected Benefits)

1.  **性能**：通过并行下载和异步存储，下载总耗时预计将大幅缩短（>50%）。
2.  **可维护性**: 新增/修改数据接口只需实现一个新的策略类并更新配置，无需触碰核心调度逻辑，代码更清晰、健壮。
3.  **可扩展性**: 架构清晰，未来可以轻松引入更复杂的调度逻辑（如基于API成本的调度）、分布式工作者或不同的存储后端。
4.  **稳定性**: 全局速率限制器能有效防止API超频。解耦的设计使得存储环节的失败不会影响下载，健壮性更高。

此方案提供了一个从混乱到有序的清晰路径，将当前系统重构为一个现代、高效、可维护的数据管道。
