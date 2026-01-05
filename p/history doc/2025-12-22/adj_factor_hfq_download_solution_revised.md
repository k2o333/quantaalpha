# 后复权因子下载功能实现方案（修订版）

## 项目概述

实现一个完整的后复权因子（`adj_factor`）下载功能，支持通过 `main.py --adj_factor_hfq` 命令下载所有股票的后复权因子数据。该功能将与现有系统架构保持一致，支持缓存、异步下载和异步存储。

**重要说明**：`adj_factor` 是 `stk_factor` 接口的一个字段，不是独立接口。本方案将复用现有的 `stk_factor` 下载机制，从返回的数据中提取 `adj_factor` 字段。

## 需求分析

### 功能需求
1. 添加提取 `adj_factor` 字段的方法（基于现有的 `stk_factor` 接口）
2. 通过 `--adj_factor_hfq` 参数触发后复权因子下载
3. 遍历所有股票，逐个下载每只股票的历史后复权因子
4. 与现有系统保持一致：缓存、异步下载、异步存储

### 技术要求
1. 与现有架构模式保持一致
2. 支持现有缓存机制
3. 支持异步下载和存储
4. 遵循现有错误处理和重试机制
5. **复用现有的策略、适配器和配置机制**

## 实现方案

### 1. 接口方法扩展

在 `app/interfaces/technical_factors.py` 的 `TechnicalFactorsDownloader` 类中添加方法：

```python
def download_adj_factor_all(self, ts_code: str = None, trade_date: str = None) -> pd.DataFrame:
    """
    下载复权因子数据
    TuShare接口：pro.stk_factor (通过获取adj_factor字段)
    权限：需要5000积分以上
    描述：获取股票复权因子信息，用于前复权、后复权处理
    """
    if TUSHARE_POINTS < 5000:
        self.logger.warning("adj_factor via stk_factor requires 5000+ points, skipping download")
        return pd.DataFrame()

    try:
        kwargs = {}
        if ts_code:
            kwargs['ts_code'] = ts_code
        if trade_date:
            kwargs['trade_date'] = trade_date

        result = self.download_with_retry(
            self.pro.stk_factor,
            **kwargs
        )

        # 从stk_factor结果中提取adj_factor字段
        if result is not None and not result.empty:
            # 选择只包含ts_code, trade_date, adj_factor的列
            adj_factor_cols = ['ts_code', 'trade_date', 'adj_factor']
            available_cols = [col for col in adj_factor_cols if col in result.columns]
            result = result[available_cols]

            # 过滤掉adj_factor为null的行
            if 'adj_factor' in result.columns:
                result = result.dropna(subset=['adj_factor'])

        self.logger.info(f"Successfully downloaded adj_factor for {ts_code or 'all stocks'}: {len(result) if result is not None else 0} records")
        return result
    except Exception as e:
        self.logger.error(f"Failed to download adj_factor for {ts_code or 'all stocks'}: {e}")
        ErrorHandler.handle_api_error(e, f"download_adj_factor for {ts_code or 'all stocks'}")
        raise

def download_adj_factor_range(self, start_date: str, end_date: str) -> pd.DataFrame:
    """
    按日期范围下载复权因子数据
    通过stk_factor接口按日期范围获取复权因子
    """
    if TUSHARE_POINTS < 5000:
        self.logger.warning("adj_factor via stk_factor requires 5000+ points, skipping download")
        return pd.DataFrame()

    try:
        # 获取交易日历
        from .basic_data import BasicDataDownloader
        basic_downloader = BasicDataDownloader(self.pro)
        trade_cal = basic_downloader.download_trade_cal(start_date=start_date, end_date=end_date)
        trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        trading_days.sort()

        all_data = []
        self.logger.info(f"Starting to download adj_factor for {len(trading_days)} trading days")

        for i, trade_date in enumerate(trading_days):
            if (i + 1) % 10 == 0:  # Log progress every 10 days
                self.logger.info(f"Processed {i + 1}/{len(trading_days)} trading days...")

            try:
                df = self.download_adj_factor_all(trade_date=trade_date)
                if df is not None and not df.empty:
                    all_data.append(df)
                    self.logger.debug(f"Got {len(df)} adj_factor records for {trade_date}")
                else:
                    self.logger.debug(f"No adj_factor data for {trade_date}")
            except Exception as e:
                self.logger.warning(f"Failed to download adj_factor for {trade_date}: {e}")
                continue  # Continue with next day even if one fails

        # Combine all data
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Successfully downloaded adj_factor for date range: {len(result)} records")
            return result
        else:
            self.logger.warning("No adj_factor data could be downloaded for the date range")
            return pd.DataFrame()
    except Exception as e:
        self.logger.error(f"Failed to download adj_factor for date range: {e}")
        ErrorHandler.handle_api_error(e, "download_adj_factor_range")
        raise

def download_all_stocks_adj_factor(self) -> pd.DataFrame:
    """
    下载所有股票的复权因子数据
    遍历所有股票，逐个获取其复权因子数据
    """
    if TUSHARE_POINTS < 5000:
        self.logger.warning("adj_factor via stk_factor requires 5000+ points, skipping download")
        return pd.DataFrame()

    try:
        # 获取股票列表
        from .basic_data import BasicDataDownloader
        basic_downloader = BasicDataDownloader(self.pro)
        stock_list = basic_downloader.download_stock_basic()

        all_data = []
        total_stocks = len(stock_list) if stock_list is not None else 0
        self.logger.info(f"开始下载 {total_stocks} 只股票的复权因子数据")

        for index, stock in stock_list.iterrows():
            ts_code = stock['ts_code']
            try:
                df = self.download_adj_factor_all(ts_code=ts_code)
                if df is not None and not df.empty:
                    all_data.append(df)
                    self.logger.info(f"已下载 {ts_code} 的复权因子数据: {len(df)} 条记录")
                else:
                    self.logger.debug(f"No adj_factor data for {ts_code}")
            except Exception as e:
                self.logger.warning(f"Failed to download adj_factor for {ts_code}: {e}")
                continue

        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            self.logger.info(f"Successfully downloaded adj_factor for all stocks: {len(result)} records")
            return result
        else:
            self.logger.warning("No adj_factor data could be downloaded")
            return pd.DataFrame()
    except Exception as e:
        self.logger.error(f"Failed to download adj_factor for all stocks: {e}")
        ErrorHandler.handle_api_error(e, "download_all_stocks_adj_factor")
        raise
```

### 2. 主程序扩展

在 `app/main.py` 中添加命令行参数支持：

```python
# 在命令行参数中添加（约第273行附近）
parser.add_argument('--adj_factor_hfq', dest='adj_factor_hfq', action='store_true',
                    help='下载所有股票的后复权因子数据')

# 在主处理逻辑中添加（约第293行附近，在if args.holders_data or args.pro_bar_only...条件之前）
if args.adj_factor_hfq:
    logger.info("开始下载后复权因子数据...")
    from tushare_api import TuShareDownloader

    try:
        downloader = TuShareDownloader()

        # 下载所有股票的复权因子数据
        adj_factor_data = downloader.technical_factors.download_all_stocks_adj_factor()

        if not adj_factor_data.empty:
            # 保存数据
            from data_storage import save_to_parquet
            save_to_parquet(adj_factor_data, 'adj_factor_all_stocks', subdir='adj_factor')

            logger.info(f"已保存 {len(adj_factor_data)} 条后复权因子数据")
            results['adj_factor_hfq'] = len(adj_factor_data)

            # 标记为已完成历史下载
            mark_interfaces_as_historical_downloaded(['stk_factor'])
        else:
            logger.warning("没有获取到后复权因子数据")
    except Exception as e:
        logger.error(f"下载后复权因子数据失败: {e}")
        raise
```

### 3. 缓存机制

复权因子数据将使用现有的缓存机制：
- 通过 `data_storage.py` 中的缓存功能
- 缓存路径：`cache/stk_factor/{ts_code}/stk_factor_{start_date}_{end_date}.parquet`
- 缓存键生成：使用缓存键生成器 `cache_key_generator.py`

**注意**：由于 `adj_factor` 是 `stk_factor` 的一个字段，缓存将基于 `stk_factor` 接口进行，避免重复下载。

## 实现步骤

### 阶段1：接口方法实现
1. 在 `app/interfaces/technical_factors.py` 中实现 `download_adj_factor_all` 方法
2. 实现批量下载方法 `download_all_stocks_adj_factor`
3. 实现日期范围下载方法 `download_adj_factor_range`
4. 确保错误处理和重试机制正常工作

### 阶段2：主程序集成
1. 在 `app/main.py` 中添加命令行参数 `--adj_factor_hfq`
2. 实现参数处理逻辑
3. 确保与现有下载模式兼容

### 阶段3：测试验证
1. 单元测试：验证新接口方法
2. 集成测试：验证命令行参数处理
3. 功能测试：验证缓存和异步机制
4. 性能测试：验证下载效率

## 技术细节

### 数据结构
复权因子数据包含以下字段：
- `ts_code`: 股票代码
- `trade_date`: 交易日期
- `adj_factor`: 复权因子

### 缓存策略
- 基于 `stk_factor` 接口进行缓存（因为 `adj_factor` 是其字段）
- 按股票代码和日期范围缓存
- 缓存有效期：24小时（可配置）
- 智能缓存匹配：支持精确匹配和范围匹配

### 任务调度
- 支持单股票和全市场两种模式
- 按股票逐个处理，避免单次API调用超载
- 支持中断恢复和错误重试

### 复用的现有机制
1. **下载策略**：使用现有的 `DailyDataStrategy`（已支持 `stk_factor`）
2. **参数适配器**：使用现有的 `TechnicalFactorParameterAdapter`（已支持 `stk_factor`）
3. **配置管理**：使用现有的 `stk_factor` 配置（已存在于 `enhanced_download_config.py`）
4. **缓存机制**：使用现有的 `stk_factor` 缓存机制
5. **错误处理**：使用现有的 `ErrorHandler` 和重试机制

## 预期效果

执行 `python app/main.py --adj_factor_hfq` 命令后，系统将：

1. 自动获取所有股票列表
2. 逐个调用TuShare的 `stk_factor` 接口
3. 从返回数据中提取 `adj_factor` 字段
4. 使用现有缓存机制避免重复下载
5. 通过异步下载提高处理效率
6. 通过异步存储避免阻塞
7. 将结果保存到 `data/adj_factor/` 目录

## 注意事项

1. **API限制**：注意TuShare的API调用限制，需要适当的延时
2. **数据量**：复权因子数据量相对较小，但仍需处理异常情况
3. **兼容性**：确保与现有系统架构完全兼容
4. **错误处理**：处理股票退市等异常情况
5. **性能优化**：考虑批量处理和并发控制
6. **积分要求**：需要5000积分以上才能访问 `stk_factor` 接口

## 扩展性考虑

- 支持前复权因子下载（通过修改参数）
- 支持指定日期范围下载
- 支持增量更新模式
- 与其他复权数据接口的兼容性

## 关于adj_factor接口说明

根据TuShare文档分析，`adj_factor`字段存在于`stk_factor`和`stk_factor_pro`技术因子接口的输出参数中，而不是一个独立的接口。通过调用这些技术因子接口，我们可以获取包含复权因子在内的多种技术指标数据。

- `stk_factor`接口：基础技术因子接口，包含adj_factor（复权因子）字段
- `stk_factor_pro`接口：专业版技术因子接口，同样包含adj_factor（复权因子）字段

这种方式的优势在于可以同时获取复权因子和其他技术指标，提高了数据获取效率。该字段返回每只股票在每个交易日的复权因子，是进行前复权和后复权计算的基础数据。

## 与原方案的主要区别

| 方面 | 原方案 | 修订版方案 |
|-----|--------|-----------|
| 接口配置 | 添加独立的 `adj_factor` 配置 | 复用现有的 `stk_factor` 配置 |
| 下载策略 | 创建 `AdjFactorDownloadStrategy` | 复用现有的 `DailyDataStrategy` |
| 参数适配器 | 创建 `AdjFactorParameterAdapter` | 复用现有的 `TechnicalFactorParameterAdapter` |
| 实现复杂度 | 需要创建多个新类 | 只需添加方法到现有类 |
| 代码改动量 | 较大 | 较小 |
| 架构一致性 | 引入新的独立接口 | 保持现有架构 |

修订版方案的优势：
1. **最小化代码改动**：只添加必要的方法，不创建冗余的类
2. **保持架构一致性**：遵循现有的设计模式
3. **避免过度设计**：不将 `adj_factor` 视为独立接口
4. **易于维护**：复用现有机制，降低维护成本
