# tscode-historical 模式优化方案（改进版）

## 项目概述

将 `--tscode-historical` 下载参数升级为与日期范围模式**完全共享**同一套架构，使其支持缓存、异步下载和异步存储。

**核心原则**：不创建新的调度器，而是扩展现有的 `DownloadScheduler`，让 `--tscode-historical` 模式使用与日期范围模式完全相同的组件。

## 当前状态分析

### 日期范围模式（默认）
- ✅ 使用 `DownloadScheduler`（生产者-消费者模式）
- ✅ 使用 `ParallelDownloader` 并行下载
- ✅ 使用 `StorageWorker` 异步存储
- ✅ 使用 `is_interface_data_cached()` / `load_interface_cached_data()` 接口级缓存
- ✅ 调度方法：`_schedule_daily_interface()`, `_schedule_financial_interface()`, `_schedule_static_interface()`

### tscode-historical 模式（当前）
- ❌ 使用 `HoldersDataFullHistoryDownloader` 顺序同步下载
- ❌ 直接调用 `save_to_parquet()` 同步存储
- ❌ 无缓存机制
- ❌ **不共享任何组件**

### 为什么不能直接使用现有的 DownloadScheduler？

**关键问题**：现有的调度方法不适合 `--tscode-historical` 模式的接口

| 接口 | 当前归类 | 当前调度方法 | 实际需求 | 不匹配原因 |
|------|---------|-------------|---------|-----------|
| `top10_holders` | 财务数据 | `_schedule_financial_interface()` | 按股票代码遍历 | 当前按报告期调度，但该接口需要 `ts_code` 参数，日期参数虽然可以传递却不是我们需要的 |
| `stk_rewards` | 静态数据 | `_schedule_static_interface()` | 按股票代码遍历 | 当前单次调度，但该接口需要 `ts_code` 参数，日期参数虽然可以传递却不是我们需要的 |
| `pledge_detail` | - | - | 按股票代码遍历 | 未在现有调度方法中支持 |
| `fina_audit` | - | - | 按股票代码遍历 | 未在现有调度方法中支持 |
| `pro_bar` | 日度数据 | `_schedule_daily_interface()` | 按股票代码遍历 | 当前按日期调度，但该接口需要 `ts_code` 参数，日期参数虽然可以传递却不是我们需要的 |

**结论**：需要添加新的调度方法 `_schedule_tscode_interface()` 来支持需要 `ts_code` 参数且按股票代码遍历的接口。

## 可行性分析

✅ **完全可以实现**，只需扩展现有 `DownloadScheduler`：

1. `DownloadScheduler` 已有完整的缓存、异步下载、异步存储机制
2. 已有 `_schedule_daily_interface()`, `_schedule_financial_interface()`, `_schedule_static_interface()` 三种调度方法
3. 只需添加第四种调度方法 `_schedule_tscode_interface()` 用于需要 `ts_code` 参数的接口
4. 修改 `main.py` 让 `--tscode-historical` 模式调用 `DownloadScheduler`

## 实现方案

### 方案架构

```
--tscode-historical 模式
    ↓
DownloadScheduler（扩展现有，不新建）
    ↓
├─ _schedule_tscode_interface()（新增方法）
├─ ParallelDownloader（复用）
├─ StorageWorker（复用）
├─ 缓存机制（复用）
└─ 任务队列管理器（复用）
```

### 核心设计

#### 1. 扩展 DownloadScheduler

在 `app/download_scheduler.py` 中添加新方法：

```python
def _schedule_tscode_interface(self, interface_name: str, priority: TaskPriority) -> str:
    """
    调度需要 ts_code 参数的接口下载任务

    Args:
        interface_name: 接口名称（如 'stk_rewards', 'top10_holders', 'pro_bar'）
        priority: 任务优先级

    Returns:
        任务ID
    """
    # 获取股票列表（使用StockListManager避免重复代码）
    stock_list = self._get_stock_list()

    if not stock_list:
        self.logger.warning(f"无法获取股票列表，跳过接口 {interface_name}")
        return None

    # 将股票列表分批，每批处理一定数量的股票
    batch_size = 50  # 每批50只股票，可根据接口特性调整
    task_ids = []

    for i in range(0, len(stock_list), batch_size):
        batch_stocks = stock_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(stock_list) - 1) // batch_size + 1

        # 创建任务参数
        task_params = {
            'interface_name': interface_name,
            'ts_codes': batch_stocks,
            'batch_num': batch_num,
            'total_batches': total_batches
        }

        # 提交任务
        task_id = self.task_manager.add_task(
            task_type='download',
            target_func=self._execute_tscode_download,
            priority=priority,
            kwargs=task_params,
            max_retries=3,
            metadata={
                'interface': interface_name,
                'batch': f"{batch_num}/{total_batches}",
                'stock_count': len(batch_stocks)
            }
        )
        if task_id:
            task_ids.append(task_id)

    # 返回第一个任务ID作为代表
    return task_ids[0] if task_ids else None


def _get_stock_list(self) -> List[str]:
    """
    获取股票列表（带缓存，使用StockListManager避免重复代码）

    Returns:
        股票代码列表
    """
    # 检查缓存（使用线程锁保证线程安全）
    with self._trading_days_lock:  # 复用现有的锁
        if hasattr(self, '_stock_list_cache') and self._stock_list_cache is not None:
            return self._stock_list_cache

    try:
        # 使用现有的StockListManager获取股票列表（避免重复代码）
        from stock_list_manager import init_stock_manager
        stock_manager = init_stock_manager(
            self.downloader, "cache", max_cache_age_hours=24
        )
        stock_list = stock_manager.get_stock_list()

        if not stock_list:
            self.logger.warning("无法获取股票列表")
            return []

        # 缓存结果（使用线程锁保证线程安全）
        with self._trading_days_lock:  # 复用现有的锁
            self._stock_list_cache = stock_list

        self.logger.info(f"获取到 {len(stock_list)} 只股票")
        return stock_list

    except Exception as e:
        self.logger.error(f"获取股票列表失败: {e}")
        return []


def _execute_tscode_download(self, **kwargs) -> pd.DataFrame:
    """
    执行需要 ts_code 参数的接口下载
    支持缓存检查、并行下载、异步存储

    Args:
        interface_name: 接口名称
        ts_codes: 股票代码列表
        batch_num: 批次号
        total_batches: 总批次数

    Returns:
        下载的数据
    """
    interface_name = kwargs.get('interface_name')
    ts_codes = kwargs.get('ts_codes', [])
    batch_num = kwargs.get('batch_num', 1)
    total_batches = kwargs.get('total_batches', 1)

    self.logger.info(f"开始下载 {interface_name} (批次 {batch_num}/{total_batches})，股票数量: {len(ts_codes)}")

    # 使用现有的ParallelDownloader进行并行处理（避免重复实现）
    try:
        # 为每个股票创建下载参数
        download_params_list = []
        for ts_code in ts_codes:
            params = {'ts_code': ts_code}
            download_params_list.append(params)

        # 使用ParallelDownloader的批处理功能
        batch_results = self.parallel_downloader.download_interface_batches(
            interface_name=interface_name,
            batch_params_list=download_params_list
        )

        # 合并所有批次的结果
        all_data = []
        for result_df in batch_results.values():
            if result_df is not None and not result_df.empty:
                all_data.append(result_df)

        if all_data:
            result = pd.concat(all_data, ignore_index=True)

            with self.stats_lock:
                self.stats['total_downloaded'] += len(result)

            self.logger.info(f"完成下载 {interface_name} (批次 {batch_num}/{total_batches})，获得 {len(result)} 条记录")

            # 提交异步存储任务（与日期范围模式完全相同）
            filename = f"{interface_name}_batch_{batch_num:04d}"
            subdir = f"tscode_historical/{interface_name}"

            self.task_manager.add_storage_task(
                data=result,
                filename=filename,
                subdir=subdir,
                priority=TaskPriority.MEDIUM
            )

            return result
        else:
            self.logger.warning(f"批次 {batch_num}/{total_batches} 没有下载到任何数据")
            return pd.DataFrame()

    except Exception as e:
        self.logger.error(f"执行tscode下载失败: {e}")
        return pd.DataFrame()


def _is_tscode_interface(self, interface_name: str) -> bool:
    """
    检查是否是需要 ts_code 参数的接口（使用配置而非硬编码）

    Args:
        interface_name: 接口名称

    Returns:
        bool: 是否是需要ts_code参数的接口
    """
    # 使用现有的配置系统而不是硬编码接口列表
    from enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
    config = DOWNLOAD_PIPELINE_CONFIG.get(interface_name)
    return config and getattr(config, 'requires_tscode', False)
```

#### 2. 修改 schedule_download_tasks 方法

在 `app/download_scheduler.py` 的 `schedule_download_tasks()` 方法中添加对 tscode 接口的支持：

```python
def schedule_download_tasks(self, interfaces: List[str] = None, mode: str = 'date_range') -> List[str]:
    """
    为指定接口调度下载任务

    Args:
        interfaces: 要下载的接口列表，如果为None则下载所有可用接口
        mode: 下载模式 ('date_range' 或 'tscode_historical')

    Returns:
        任务ID列表
    """
    if interfaces is None:
        available_interfaces = get_all_available_interfaces()
        interfaces = list(available_interfaces.keys())

    task_ids = []

    for interface_name in interfaces:
        # 获取接口策略和优先级
        from config_adapter import get_interface_priority as get_config_priority
        priority = get_config_priority(interface_name)

        # 根据接口类型和下载模式选择合适的调度策略
        if mode == 'tscode_historical':
            # tscode-historical 模式：需要 ts_code 参数的接口
            # 使用配置系统而不是硬编码接口列表
            if self._is_tscode_interface(interface_name):
                task_id = self._schedule_tscode_interface(interface_name, priority)
                if task_id:
                    task_ids.append(task_id)
            else:
                self.logger.warning(f"接口 {interface_name} 不支持 tscode-historical 模式")
        else:
            # 日期范围模式（原有逻辑）
            if interface_name in ['daily', 'daily_basic', 'moneyflow', 'moneyflow_dc', 'moneyflow_ths',
                                 'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths',
                                 'moneyflow_ind_ths', 'stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']:
                # 日度数据接口，按日期分批调度
                task_id = self._schedule_daily_interface(interface_name, priority)
            elif interface_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                                   'dividend', 'forecast', 'express', 'top10_holders',
                                   'top10_floatholders', 'stk_surv']:
                # 财务数据接口，按报告期调度
                task_id = self._schedule_financial_interface(interface_name, priority)
            elif interface_name in ['stock_basic', 'trade_cal', 'new_share', 'stock_company',
                                   'stock_st', 'bak_basic', 'namechange', 'stk_rewards',
                                   'stk_managers', 'broker_recommend']:
                # 静态数据接口，单次调度
                task_id = self._schedule_static_interface(interface_name, priority)
            else:
                # 未知类型接口，按日度数据处理
                task_id = self._schedule_daily_interface(interface_name, priority)

            if task_id:
                task_ids.append(task_id)

    self.logger.info(f"调度了 {len(task_ids)} 个下载任务 (模式: {mode})")
    return task_ids
```

#### 3. 修改 run_download_schedule 函数

在 `app/download_scheduler.py` 中修改 `run_download_schedule()` 函数：

```python
def run_download_schedule(start_date: str, end_date: str, interfaces: List[str] = None, mode: str = 'date_range') -> Dict[str, Any]:
    """
    运行下载调度（便捷函数）

    Args:
        start_date: 开始日期 (YYYYMMDD) - tscode_historical 模式下忽略
        end_date: 结束日期 (YYYYMMDD) - tscode_historical 模式下忽略
        interfaces: 要下载的接口列表，如果为None则下载所有可用接口
        mode: 下载模式 ('date_range' 或 'tscode_historical')

    Returns:
        下载统计结果
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"创建下载调度器实例 (模式: {mode})")
    scheduler = create_download_scheduler(start_date, end_date)
    logger.info("下载调度器创建成功")

    try:
        logger.info("开始调度下载任务")
        # 调度下载任务
        scheduler.schedule_download_tasks(interfaces, mode=mode)
        logger.info("下载任务调度完成，等待执行")

        logger.info("开始执行调度的任务")
        # 执行所有任务
        results = scheduler.execute_scheduled_tasks(wait_for_completion=True)
        logger.info("任务执行完成")

        return results
    except Exception as e:
        logger.error(f"执行下载调度时出错: {e}")
        import traceback
        logger.error(f"错误追踪: {traceback.format_exc()}")
        raise
    finally:
        logger.info("关闭下载调度器")
        scheduler.shutdown()
```

#### 4. 修改 main.py 集成

在 `app/main.py` 中修改 `--tscode-historical` 模式的处理逻辑：

```python
# 在 main() 函数中修改
if args.holders_data or args.pro_bar_only or (effective_tscode_historical and not (args.holders_data or args.pro_bar_only)):
    logger.info("开始下载指定的全历史数据...")

    # 确定要下载的接口
    interfaces_to_download = []

    if download_holders_data:
        interfaces_to_download.extend(['stk_rewards', 'top10_holders'])
        if TUSHARE_POINTS >= 5000:
            interfaces_to_download.append('pledge_detail')
        if TUSHARE_POINTS >= 500:
            interfaces_to_download.append('fina_audit')

    if download_pro_bar_only:
        interfaces_to_download.append('pro_bar')

    # 使用 DownloadScheduler（与日期范围模式完全相同的架构）
    if args.tscode_historical:
        logger.info("使用 DownloadScheduler (tscode-historical 模式)")
        results = run_download_schedule(
            start_date='20230101',  # tscode_historical 模式下忽略此参数
            end_date=datetime.now().strftime('%Y%m%d'),  # tscode_historical 模式下忽略此参数
            interfaces=interfaces_to_download,
            mode='tscode_historical'  # 指定为 tscode_historical 模式
        )
    else:
        # 回退到传统方式
        results = download_with_legacy_fallback(args.start_date, args.end_date)
```

### 文件结构

```
app/
├── download_scheduler.py          # 修改：添加 _schedule_tscode_interface() 等方法
├── main.py                        # 修改：集成 tscode_historical 模式
├── storage_worker.py              # 复用：无需修改
├── parallel_downloader.py         # 复用：无需修改
├── data_storage.py                # 复用：无需修改
├── stock_list_manager.py          # 复用：用于获取股票列表
└── interfaces/
    └── holders_data_downloader.py # 保留：作为回退选项
```

## 实施步骤

### 阶段一：扩展 DownloadScheduler（核心功能）

1. **添加 `_schedule_tscode_interface()` 方法**
   - 获取股票列表
   - 分批处理股票（每批50只）
   - 创建下载任务

2. **添加 `_get_stock_list()` 方法**
   - 使用 `StockListManager` 获取股票列表（避免重复代码）
   - 实现缓存机制（使用线程锁保证线程安全）

3. **添加 `_execute_tscode_download()` 方法**
   - 使用 `ParallelDownloader` 进行并行下载（避免重复实现）
   - 合并数据
   - 提交异步存储任务

4. **添加 `_is_tscode_interface()` 方法**
   - 使用配置系统判断接口类型（避免硬编码）

### 阶段二：修改调度逻辑

1. **修改 `schedule_download_tasks()` 方法**
   - 添加 `mode` 参数
   - 根据 mode 选择调度策略
   - 使用配置系统判断接口类型

2. **修改 `run_download_schedule()` 函数**
   - 添加 `mode` 参数
   - 传递 mode 给调度器

### 阶段三：集成到 main.py

1. **修改参数处理逻辑**
   - 在 `--tscode-historical` 模式下使用 `run_download_schedule(mode='tscode_historical')`
   - 保留传统方式作为回退选项

2. **添加结果统计**
   - 统计下载记录数
   - 统计缓存命中率
   - 统计任务完成情况

### 阶段四：测试和优化

1. **功能测试**
   - 测试 `--tscode-historical` 参数
   - 测试缓存功能
   - 测试异步下载和存储

2. **性能测试**
   - 对比优化前后的下载速度
   - 测试并发性能
   - 测试内存使用

3. **错误处理测试**
   - 测试网络错误重试
   - 测试存储错误重试
   - 测试异常情况处理

## 技术细节

### 共享的组件

| 组件 | 日期范围模式 | tscode-historical 模式 | 共享程度 |
|------|-------------|---------------------|---------|
| `DownloadScheduler` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `ParallelDownloader` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `StorageWorker` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `is_interface_data_cached()` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `load_interface_cached_data()` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `save_interface_data_to_cache()` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `acquire_tokens()` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `task_manager.add_task()` | ✅ 使用 | ✅ 使用 | **100% 共享** |
| `task_manager.add_storage_task()` | ✅ 使用 | ✅ 使用 | **100% 共享** |

### 新增的方法

| 方法 | 功能 | 说明 |
|------|------|------|
| `_schedule_tscode_interface()` | 调度需要 ts_code 参数的接口 | 类似 `_schedule_daily_interface()` |
| `_get_stock_list()` | 获取股票列表（带缓存，使用StockListManager） | 复用现有组件 |
| `_execute_tscode_download()` | 执行 tscode 接口下载 | 使用ParallelDownloader |
| `_is_tscode_interface()` | 判断是否是tscode接口 | 使用配置系统 |

### 缓存策略（与日期范围模式完全相同）

1. **缓存键生成**
   - 使用 `CacheKeyGenerator.generate_cache_path()`
   - 参数格式：`{interface_name}/{ts_code}.parquet`

2. **缓存检查**
   ```python
   if is_interface_data_cached(interface_name, ts_code=ts_code):
       cached_data = load_interface_cached_data(interface_name, ts_code=ts_code)
   ```

3. **缓存保存**
   ```python
   save_interface_data_to_cache(result, interface_name, ts_code=ts_code)
   ```

### 并发控制（与日期范围模式完全相同）

1. **批次大小**
   - 默认每批 50 只股票
   - 可根据接口特性调整

2. **线程池大小**
   - 使用 `ParallelDownloader` 的并发控制
   - 每个接口独立配置并发数

3. **速率限制**
   - 使用 `acquire_tokens()` 申请令牌
   - 每个接口独立速率限制

### 存储策略（与日期范围模式完全相同）

1. **存储路径**
   ```
   data/
   └── tscode_historical/
       ├── stk_rewards/
       │   ├── batch_0001.parquet
       │   └── batch_0002.parquet
       ├── top10_holders/
       └── pro_bar/
   ```

2. **存储任务**
   - 通过 `task_manager.add_storage_task()` 提交
   - `StorageWorker` 异步处理

## 预期效果

### 性能提升

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 下载速度 | 串行 | 并行（使用ParallelDownloader） | ~3-4x |
| 存储速度 | 同步 | 异步 | ~2x |
| 缓存命中率 | 0% | >80% | 显著提升 |
| 总耗时 | 基准 | ~1/6 | ~6x |

### 功能增强

- ✅ 支持缓存，避免重复下载
- ✅ 支持异步下载，提高并发性能
- ✅ 支持异步存储，不阻塞下载
- ✅ 支持错误重试，提高稳定性
- ✅ 支持进度跟踪，实时查看状态
- ✅ **与日期范围模式 100% 共享架构**

### 架构优势

- ✅ **代码复用**：无需创建新的调度器，直接扩展现有 `DownloadScheduler`
- ✅ **架构统一**：两种模式使用完全相同的组件和机制
- ✅ **维护简单**：只需维护一套调度逻辑
- ✅ **向后兼容**：保留传统下载方式作为回退

## 风险和注意事项

### 潜在风险

1. **内存占用**
   - 并发下载可能增加内存使用
   - 建议：控制批次大小和并发数

2. **API 限流**
   - 并发请求可能触发限流
   - 建议：使用速率限制器控制请求频率

3. **缓存一致性**
   - 缓存数据可能过期
   - 建议：设置合理的 TTL（24小时）

### 注意事项

1. **向后兼容**
   - 保留传统下载方式作为回退
   - 添加 `--use-legacy` 参数强制使用传统方式

2. **错误处理**
   - 单个股票下载失败不影响其他股票
   - 失败任务自动重试（最多3次）

3. **日志记录**
   - 详细记录缓存命中情况
   - 记录下载和存储进度
   - 记录错误和重试信息

## 总结

本方案通过**扩展现有的 `DownloadScheduler`**，为 `--tscode-historical` 模式提供了与日期范围模式**完全相同**的优化特性：

- ✅ 缓存支持（100% 共享）
- ✅ 异步下载（100% 共享）
- ✅ 异步存储（100% 共享）

**核心优势**：
- 不创建新的调度器，直接扩展现有架构
- 两种模式使用完全相同的组件和机制
- 代码复用率高，维护成本低
- 实施后，`--tscode-historical` 模式的下载速度预计提升 6 倍以上

**改进建议总结**：
1. **复用现有组件**：使用 `StockListManager` 避免重复代码
2. **线程安全**：使用现有锁机制保护缓存
3. **配置驱动**：使用配置系统而非硬编码接口列表
4. **统一架构**：复用 `ParallelDownloader` 和 `StorageWorker`
5. **日志规范**：保持与现有代码一致的日志风格