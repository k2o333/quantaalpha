# 后复权因子下载功能完整实现方案

## 项目概述

实现一个完整的后复权因子（`adj_factor`）下载功能，支持通过 `main.py --adj_factor_hfq` 命令下载所有股票的后复权因子数据。该功能将与现有系统架构保持一致，支持缓存、异步下载和异步存储。

## 需求分析

### 功能需求
1. 添加 `adj_factor` 数据提取功能（基于现有的 `stk_factor` 接口）
2. 通过 `--adj_factor_hfq` 参数触发后复权因子下载
3. 遍历所有股票，获取每只股票的历史后复权因子
4. 与现有系统保持一致：缓存、异步下载、异步存储

### 技术要求
1. 与现有架构模式保持一致
2. 支持现有缓存机制
3. 支持异步下载和存储
4. 遵循现有错误处理和重试机制
5. 复用现有的策略、适配器和配置机制

## 实现方案

### 1. 接口配置扩展

**在 `app/enhanced_download_config.py` 中：**

不需要添加独立的 `adj_factor` 接口配置，复用现有的 `stk_factor` 接口配置，因为 `adj_factor` 是 `stk_factor` 接口输出的一部分。

### 2. 下载策略扩展

**在 `app/download_strategies.py` 中：**

修改 `DailyDataStrategy` 类以支持 `adj_factor` 字段提取：

```python
# 在 DownloadStrategy 类中添加方法
def extract_adj_factor_data(self, original_data: pd.DataFrame) -> pd.DataFrame:
    """
    从原始stk_factor数据中提取adj_factor字段
    """
    if original_data is None or original_data.empty:
        return pd.DataFrame()

    # 选择只包含ts_code, trade_date, adj_factor的列
    adj_factor_cols = ['ts_code', 'trade_date', 'adj_factor']
    available_cols = [col for col in adj_factor_cols if col in original_data.columns]
    result = original_data[available_cols]

    # 过滤掉adj_factor为null的行
    if 'adj_factor' in result.columns:
        result = result.dropna(subset=['adj_factor'])

    return result

# 在 DailyDataStrategy 类中添加专门的adj_factor下载方法
def download_adj_factor(self, **kwargs) -> pd.DataFrame:
    """
    专门用于下载adj_factor数据的方法
    """
    # 先调用正常的stk_factor下载
    original_data = self.download(**kwargs)

    # 从原始数据中提取adj_factor字段
    adj_factor_data = self.extract_adj_factor_data(original_data)

    self.logger.info(f"Successfully extracted adj_factor data: {len(adj_factor_data)} records")
    return adj_factor_data
```

### 3. 接口实现扩展

**在 `app/interfaces/technical_factors.py` 中：**

添加 adj_factor 相关方法：

```python
def download_adj_factor_with_cache(self, ts_code: str = None, trade_date: str = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    带缓存的adj_factor下载方法
    """
    from download_strategies import DownloadStrategy
    from strategy_factory import get_strategy

    # 创建策略实例
    strategy = get_strategy('stk_factor', downloader=self.downloader)

    # 准备参数
    params = {}
    if ts_code:
        params['ts_code'] = ts_code
    if trade_date:
        params['trade_date'] = trade_date
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    # 使用策略下载数据
    original_data = strategy.download_with_cache(**params)

    # 从原始数据中提取adj_factor字段
    if original_data is not None and not original_data.empty:
        adj_factor_cols = ['ts_code', 'trade_date', 'adj_factor']
        available_cols = [col for col in adj_factor_cols if col in original_data.columns]
        result = original_data[available_cols]
        if 'adj_factor' in result.columns:
            result = result.dropna(subset=['adj_factor'])
        return result
    else:
        return pd.DataFrame()
```

### 4. 异步下载实现

**在 `app/download_scheduler.py` 中：**

添加处理 adj_factor 任务的逻辑：

```python
def create_adj_factor_download_task(ts_code: str, priority: int = 2) -> dict:
    """
    创建adj_factor下载任务
    """
    return {
        'type': 'adj_factor_download',
        'interface': 'stk_factor',  # 复用stk_factor接口
        'params': {'ts_code': ts_code},
        'priority': priority,
        'extract_field': 'adj_factor'  # 标记需要提取adj_factor字段
    }
```

### 5. 主程序集成

**在 `app/main.py` 中：**

修改 `--adj_factor_hfq` 参数的处理逻辑，使用异步下载：

```python
if args.adj_factor_hfq:
    logger.info("开始下载后复权因子数据...")
    try:
        # 获取股票列表
        from interfaces.basic_data import BasicDataDownloader
        basic_downloader = BasicDataDownloader(downloader.pro)
        stock_list = basic_downloader.download_stock_basic()

        if stock_list is not None and not stock_list.empty:
            # 创建下载任务
            download_tasks = []
            for index, stock in stock_list.iterrows():
                ts_code = stock['ts_code']
                task = create_adj_factor_download_task(ts_code)
                download_tasks.append(task)

            # 提交到下载调度器
            from download_scheduler import run_download_schedule_with_tasks
            results = run_download_schedule_with_tasks(download_tasks, interface_name='stk_factor')

            if results:
                # 合并所有adj_factor数据
                all_adj_factor_data = pd.concat(results, ignore_index=True) if len(results) > 0 else pd.DataFrame()

                if not all_adj_factor_data.empty:
                    # 提交存储任务到异步存储队列
                    from task_queue_manager import get_download_task_manager
                    task_manager = get_download_task_manager()

                    task_manager.add_storage_task(
                        data=all_adj_factor_data,
                        filename='adj_factor_all_stocks',
                        subdir='adj_factor',
                        priority=TaskPriority.MEDIUM
                    )

                    logger.info(f"已提交 {len(all_adj_factor_data)} 条后复权因子数据存储任务")
                    results['adj_factor_hfq'] = len(all_adj_factor_data)

                    # 标记为已完成历史下载
                    from main import mark_interfaces_as_historical_downloaded
                    mark_interfaces_as_historical_downloaded(['stk_factor'])
                else:
                    logger.warning("没有获取到后复权因子数据")
        else:
            logger.warning("没有获取到股票列表")
    except Exception as e:
        logger.error(f"下载后复权因子数据失败: {e}")
        raise
```

### 6. 缓存机制

复用现有的 `stk_factor` 缓存机制，因为 `adj_factor` 是 `stk_factor` 接口的数据子集：

- 缓存路径：`cache/stk_factor/{ts_code}/stk_factor_{start_date}_{end_date}.parquet`
- 缓存键生成：使用 `cache_key_generator.py`
- 缓存TTL：复用 `stk_factor` 的缓存配置（24小时）

### 7. 异步存储

通过 `task_queue_manager.py` 和 `storage_worker.py` 实现异步存储：

1. 下载完成后，将数据提交到存储任务队列
2. 存储工作进程异步处理数据保存
3. 避免阻塞下载线程

## 实现步骤

### 阶段1：下载策略扩展
1. 在 `download_strategies.py` 中添加 adj_factor 相关方法
2. 确保策略复用现有的缓存机制
3. 测试策略与现有架构的兼容性

### 阶段2：接口方法实现
1. 在 `technical_factors.py` 中添加缓存下载方法
2. 确保正确调用现有的策略和缓存机制
3. 验证数据提取逻辑

### 阶段3：异步调度集成
1. 在 `download_scheduler.py` 中添加 adj_factor 任务处理
2. 实现任务队列管理
3. 确保与现有调度器兼容

### 阶段4：主程序集成
1. 修改 `main.py` 中的 `--adj_factor_hfq` 处理逻辑
2. 使用异步下载和存储机制
3. 确保与现有参数处理兼容

### 阶段5：测试验证
1. 单元测试：验证新接口方法
2. 集成测试：验证异步调度机制
3. 功能测试：验证缓存、异步下载和存储
4. 性能测试：验证下载效率提升

## 技术细节

### 数据结构
复权因子数据包含以下字段：
- `ts_code`: 股票代码
- `trade_date`: 交易日期
- `adj_factor`: 复权因子

### 缓存策略
- 基于 `stk_factor` 接口进行缓存（因为 `adj_factor` 是其字段）
- 按股票代码和日期范围缓存
- 缓存有效期：24小时（复用现有配置）
- 智能缓存匹配：支持精确匹配和范围匹配

### 任务调度
- 支持批量创建 adj_factor 下载任务
- 按股票逐个处理，避免单次API调用超载
- 支持中断恢复和错误重试

### 复用的现有机制
1. **下载策略**：使用现有的 `DailyDataStrategy`（已支持 `stk_factor`）
2. **参数适配器**：使用现有的 `TechnicalFactorParameterAdapter`（已支持 `stk_factor`）
3. **配置管理**：使用现有的 `stk_factor` 配置
4. **缓存机制**：使用现有的 `stk_factor` 缓存机制
5. **错误处理**：使用现有的 `ErrorHandler` 和重试机制
6. **异步下载**：使用现有的 `download_scheduler` 和任务队列
7. **异步存储**：使用现有的 `storage_worker` 机制

## 预期效果

执行 `python app/main.py --adj_factor_hfq` 命令后，系统将：

1. 自动获取所有股票列表
2. 为每只股票创建 `stk_factor` 下载任务
3. 通过异步下载机制并行下载多只股票的数据
4. 使用现有缓存机制避免重复下载
5. 从下载的数据中提取 `adj_factor` 字段
6. 通过异步存储机制保存结果
7. 将结果保存到 `data/adj_factor/adj_factor_all_stocks.parquet`

## 预期改进效果

1. **异步下载**：同时下载多只股票的数据，提高下载效率
2. **缓存利用**：复用已下载的 `stk_factor` 数据，避免重复API调用
3. **异步存储**：下载和存储并行进行，避免阻塞
4. **资源优化**：合理利用并发和缓存资源

## 注意事项

1. **API限制**：注意TuShare的API调用限制
2. **数据量**：复权因子数据量相对较小，但仍需处理异常情况
3. **兼容性**：确保与现有系统架构完全兼容
4. **错误处理**：处理股票退市等异常情况
5. **性能优化**：考虑批量处理和并发控制
6. **积分要求**：需要5000积分以上才能访问 `stk_factor` 接口