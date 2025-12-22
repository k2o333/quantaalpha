# 并行下载和存储优化方案

## 问题概述

在 `app/date_range_downloader.py` 文件中，存在接口下载和数据存储的串行问题。虽然在单个数据类型内部使用了并行下载机制，但不同数据类型之间是串行处理的，导致整体下载效率低下。

## 当前架构问题分析

### 1. 串行处理架构
- 主循环 `download_all_available_data` 方法中，不同数据类型是按顺序逐一处理的
- 每个数据类型任务必须等待前一个任务完成后才开始
- 无法充分利用TuShare API的并发能力

### 2. 并行机制局限性
- 现有并行机制仅限于单个数据类型内部（如一天内的数据并行下载）
- 不同数据类型之间缺乏并行处理
- 没有使用并行下载器（ParallelDownloader）来提升整体效率

### 3. 存储环节串行
- 数据下载完成后立即存储，而不是批量异步存储
- 存储操作阻塞主线程，影响下载效率

## 解决方案

### 方案一：使用ParallelDownloader优化（推荐）

修改 `download_all_available_data` 方法，使用并行下载器处理不同的数据类型：

```python
def download_all_available_data_parallel(self) -> Dict[str, any]:
    """
    并行下载所有可用数据，提升下载效率
    """
    results = {}

    self.logger.info(f"开始并行下载日期范围 {self.start_date} 到 {self.end_date} 的所有可用数据")

    # 创建下载任务列表
    download_tasks = self._create_download_task_list()

    # 分离不同类型的任务，便于并行处理
    task_groups = self._group_tasks_by_type(download_tasks)

    # 使用并行下载器处理不同组的任务
    parallel_downloader = ParallelDownloader(max_workers=6)  # 可根据需要调整

    for group_name, tasks in task_groups.items():
        self.logger.info(f"并行下载任务组: {group_name}")

        # 提取数据类型名称
        data_types = [task[0] for task in tasks]

        # 并行下载该组的所有数据类型
        group_results = parallel_downloader.download_daily_types_batched(
            data_types,
            self.start_date,
            self.end_date
        )

        results.update(group_results)

    self.logger.info("日期范围数据并行下载完成")
    return results

def _group_tasks_by_type(self, tasks):
    """
    按数据类型分组任务，便于并行处理
    """
    groups = {
        'high_priority': [],  # 高优先级接口 - daily, daily_basic等
        'financial': [],      # 财务数据接口
        'market_flow': [],    # 资金流向接口
        'other': []           # 其他接口
    }

    for task in tasks:
        task_name = task[0]
        if task_name in ['daily', 'daily_basic', 'moneyflow']:
            groups['high_priority'].append(task)
        elif task_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator']:
            groups['financial'].append(task)
        elif task_name in ['moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc',
                          'moneyflow_mkt_dc', 'moneyflow_cnt_ths', 'moneyflow_ind_ths']:
            groups['market_flow'].append(task)
        else:
            groups['other'].append(task)

    # 过滤空组
    return {k: v for k, v in groups.items() if v}

def download_all_available_data_improved(self) -> Dict[str, any]:
    """
    改进的下载方法，结合原有逻辑和并行处理
    """
    results = {}

    self.logger.info(f"开始改进版下载日期范围 {self.start_date} 到 {self.end_date} 的所有可用数据")

    # 创建下载任务列表
    download_tasks = self._create_download_task_list()

    # 尝试使用并行处理高优先级任务
    high_priority_tasks = []
    other_tasks = []

    for task in download_tasks:
        task_name = task[0]
        if task_name in ['daily', 'daily_basic', 'moneyflow']:
            high_priority_tasks.append(task)
        else:
            other_tasks.append(task)

    # 并行下载高优先级任务
    if high_priority_tasks:
        self.logger.info(f"并行下载 {len(high_priority_tasks)} 个高优先级任务")

        # 提取任务名称用于并行下载器
        high_priority_types = [task[0] for task in high_priority_tasks]
        parallel_downloader = ParallelDownloader(max_workers=min(4, len(high_priority_types)))

        high_priority_results = parallel_downloader.download_daily_types_batched(
            high_priority_types,
            self.start_date,
            self.end_date
        )

        results.update(high_priority_results)

    # 串行处理剩余任务（使用原有的改进逻辑）
    remaining_tasks = other_tasks
    failed_attempts = {}
    completed_tasks = set()
    original_task_count = len(remaining_tasks)

    # 智能下载循环 - 为每个任务设置最大重试次数
    while len(completed_tasks) < original_task_count and remaining_tasks:
        # 检查是否所有任务都已达到最大重试次数
        all_max_retries_reached = True
        for task_name, _, max_retries in remaining_tasks:
            if failed_attempts.get(task_name, 0) < max_retries:
                all_max_retries_reached = False
                break

        if all_max_retries_reached:
            self.logger.info("所有剩余任务都已达到最大重试次数，退出。")
            break

        if not remaining_tasks:  # 确保任务队列不为空
            break

        task_name, download_func, max_retries = remaining_tasks[0]

        # 检查此任务是否已达到最大重试次数
        if failed_attempts.get(task_name, 0) >= max_retries:
            self.logger.info(f"{task_name} 已达到最大重试次数 {max_retries}，跳过任务")
            remaining_tasks.pop(0)  # 直接移除不再尝试
            continue

        task_completed = False
        should_remove_task = False  # 标记是否应该移除任务

        try:
            self.logger.info(f"开始下载数据类型: {task_name}")
            result = download_func()

            if result is not None:  # 空dict或0也算成功
                results[task_name] = result
                task_completed = True
                should_remove_task = True
                self.logger.info(f"✅ {task_name} 下载成功")
            else:
                self.logger.warning(f"{task_name} 返回空结果")
                task_completed = True  # 空结果也视为完成，不是失败
                should_remove_task = True

        except Exception as e:
            failed_attempts[task_name] = failed_attempts.get(task_name, 0) + 1
            self.logger.error(f"❌ {task_name} 下载失败 (尝试 {failed_attempts[task_name]}/{max_retries}): {e}")

            if failed_attempts[task_name] >= max_retries:
                self.logger.warning(f"{task_name} 达到最大重试次数 {max_retries}，不再重试")
                should_remove_task = True  # 标记应该移除任务
            else:
                # 任务失败但仍需重试，移到队列末尾
                self.logger.info(f"将 {task_name} 移至队列末尾，稍后重试")
                remaining_tasks.append(remaining_tasks.pop(0))

        finally:
            if task_completed:
                completed_tasks.add(task_name)

            if should_remove_task:
                if remaining_tasks and remaining_tasks[0][0] == task_name:
                    remaining_tasks.pop(0)  # 移除已完成或达到重试上限的任务

    self.logger.info("日期范围数据下载完成")
    return results
```

### 方案二：异步下载和存储优化

实现真正的异步处理，将下载和存储分离：

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

class AsyncDateRangeDownloader(DateRangeDownloader):
    def __init__(self, start_date: str, end_date: str = None):
        super().__init__(start_date, end_date)
        self.download_queue = asyncio.Queue()
        self.storage_queue = asyncio.Queue()
        self.storage_lock = threading.Lock()

    async def download_all_available_data_async(self) -> Dict[str, any]:
        """
        异步下载所有数据，分离下载和存储操作
        """
        results = {}

        self.logger.info(f"开始异步下载日期范围 {self.start_date} 到 {self.end_date} 的所有可用数据")

        # 创建下载任务列表
        download_tasks = self._create_download_task_list()

        # 启动存储协程
        storage_task = asyncio.create_task(self._storage_worker())

        # 为每个任务创建下载协程
        download_coroutines = []
        for task_name, download_func, max_retries in download_tasks:
            coro = self._download_single_task_async(task_name, download_func, max_retries)
            download_coroutines.append(coro)

        # 并行执行所有下载任务
        download_results = await asyncio.gather(*download_coroutines, return_exceptions=True)

        # 等待存储队列清空
        await self.storage_queue.join()

        # 取消存储worker
        storage_task.cancel()

        # 处理下载结果
        for i, result in enumerate(download_results):
            if isinstance(result, Exception):
                self.logger.error(f"下载任务 {download_tasks[i][0]} 失败: {result}")
            else:
                task_name, data = result
                results[task_name] = data

        self.logger.info("异步下载完成")
        return results

    async def _download_single_task_async(self, task_name: str, download_func, max_retries: int):
        """
        异步下载单个任务
        """
        failed_attempts = 0
        task_completed = False

        while not task_completed and failed_attempts < max_retries:
            try:
                self.logger.info(f"开始下载数据类型: {task_name}")
                result = download_func()

                if result is not None:
                    # 将结果加入存储队列
                    await self.storage_queue.put((task_name, result))
                    task_completed = True
                    self.logger.info(f"✅ {task_name} 下载成功")
                else:
                    self.logger.warning(f"{task_name} 返回空结果")
                    await self.storage_queue.put((task_name, result))  # 也存储空结果
                    task_completed = True

            except Exception as e:
                failed_attempts += 1
                self.logger.error(f"❌ {task_name} 下载失败 (尝试 {failed_attempts}/{max_retries}): {e}")

                if failed_attempts >= max_retries:
                    self.logger.warning(f"{task_name} 达到最大重试次数，不再重试")
                    task_completed = True

        return task_name, result if 'result' in locals() else None

    async def _storage_worker(self):
        """
        存储协程 - 从队列中取出数据并存储
        """
        while True:
            try:
                task_name, data = await self.storage_queue.get()

                # 存储数据
                if data is not None:
                    # 根据数据类型选择合适的存储方式
                    if isinstance(data, dict):
                        # 如果是按日期分组的数据
                        for date_key, date_data in data.items():
                            if isinstance(date_data, int):  # 记录数统计
                                self.logger.info(f"存储 {task_name}_{date_key}: {date_data} 条记录")
                            elif hasattr(date_data, '__len__'):  # DataFrame或其他可计数对象
                                self.logger.info(f"存储 {task_name}_{date_key}: {len(date_data)} 条记录")
                    else:
                        # 直接存储数据
                        self.logger.info(f"存储 {task_name}: {len(data) if hasattr(data, '__len__') else 'unknown'} 条记录")

                self.storage_queue.task_done()

            except asyncio.CancelledError:
                self.logger.info("存储工作器被取消")
                break
            except Exception as e:
                self.logger.error(f"存储任务失败: {e}")
                self.storage_queue.task_done()
```

## 实施建议

### 优先级：高
1. **立即实施方案一**：修改现有代码，使用 `ParallelDownloader` 处理高优先级任务
2. **保留原有错误处理逻辑**：确保修复后的任务完成逻辑得到保留
3. **分阶段实施**：先并行处理高优先级数据类型，再逐步扩展到所有类型

### 优先级：中
1. **性能测试**：对比串行和并行下载的性能差异
2. **API配额管理**：确保并行下载不会超出TuShare API的调用限制
3. **错误恢复机制**：增强并行下载时的错误处理和重试机制

## 预期效果

1. **下载效率提升**：通过并行处理不同数据类型，预计整体下载时间可减少 40-60%
2. **API利用率提高**：更好地利用TuShare API的并发能力
3. **资源利用率优化**：减少等待时间，提高CPU和网络带宽的利用率

## 潜在风险

1. **API限制**：并发下载可能触发TuShare的频率限制
2. **内存使用增加**：并行处理会增加内存使用量
3. **错误处理复杂性**：并行环境下的错误处理更加复杂

## 监控指标

1. **下载时间对比**：比较并行前后下载时间
2. **API调用成功率**：监控并行下载时的API调用成功率
3. **系统资源使用**：监控CPU、内存、网络使用情况