# App4 代码流程图 - aspipe_v4 配置驱动架构

## 1. 整体系统架构图

```mermaid
graph TB
    User[用户] --> CLI[main.py CLI入口]
    
    CLI --> ConfigLoader[配置加载器<br/>ConfigLoader]
    CLI --> Scheduler[任务调度器<br/>TaskScheduler]
    CLI --> Storage[存储管理器<br/>StorageManager]
    CLI --> Processor[数据处理器<br/>DataProcessor]
    CLI --> Downloader[通用下载器<br/>GenericDownloader]
    
    ConfigLoader --> GlobalConfig[全局配置<br/>settings.yaml]
    ConfigLoader --> InterfaceConfigs[接口配置<br/>interfaces/*.yaml]
    
    Downloader --> CoverageManager[覆盖率管理器<br/>CoverageManager]
    Downloader --> CacheManager[缓存管理器<br/>内存缓存]
    Downloader --> SchemaManager[Schema管理器<br/>SchemaManager]
    Downloader --> APISession[API会话<br/>requests.Session]
    
    Scheduler --> RateLimiter[速率限制器<br/>RateLimiter]
    
    Storage --> DataQueue[数据队列<br/>Queue]
    Storage --> ParquetWriter[Parquet写入器<br/>Dataset模式]
    
    Downloader --> TuShareAPI[TuShare API]
    TuShareAPI --> Response[API响应数据]
    
    Response --> Processor
    Processor --> Storage
    Storage --> ParquetFiles[Parquet文件<br/>../data/]
    
    PerformanceMonitor[性能监控器<br/>PerformanceMonitor] --> Downloader
    PerformanceMonitor --> Scheduler
    PerformanceMonitor --> Storage
```

## 2. 主流程图

```mermaid
graph TD
    Start[开始] --> ParseArgs[解析命令行参数]
    ParseArgs --> LoadEnv[加载环境变量<br/>.env文件]
    LoadEnv --> InitConfig[初始化配置加载器<br/>ConfigLoader]
    
    InitConfig --> LoadGlobal[加载全局配置<br/>settings.yaml]
    InitConfig --> LoadInterfaces[加载接口配置<br/>interfaces/*.yaml]
    LoadGlobal --> ValidateConfig[验证配置完整性]
    LoadInterfaces --> ValidateConfig
    
    ValidateConfig --> SetupLogging[设置日志系统]
    SetupLogging --> InitComponents[初始化核心组件]
    
    InitComponents --> InitScheduler[初始化调度器<br/>TaskScheduler]
    InitComponents --> InitStorage[初始化存储管理器<br/>StorageManager]
    InitComponents --> InitDownloader[初始化通用下载器<br/>GenericDownloader]
    InitComponents --> InitProcessor[初始化数据处理器<br/>DataProcessor]
    
    InitDownloader --> PreloadCalendar[预加载全局交易日历<br/>trade_cal]
    PreloadCalendar --> InitRateLimiter[初始化速率限制器<br/>RateLimiter]
    
    InitRateLimiter --> StartComponents[启动组件]
    StartComponents --> StartScheduler[启动调度器]
    StartComponents --> StartStorage[启动存储写入线程]
    
    StartStorage --> DetermineInterfaces[确定要执行的接口]
    
    DetermineInterfaces --> CheckArgs{检查命令行参数}
    
    CheckArgs -->|tscode_historical| LoadTSCodeGroup[加载tscode_historical接口组]
    CheckArgs -->|pro_bar_only| AddProBar[添加pro_bar接口]
    CheckArgs -->|holders_data| AddHoldersGroup[添加holders接口组]
    CheckArgs -->|interface| AddSingleInterface[添加单个接口]
    CheckArgs -->|group| AddGroup[添加接口组]
    CheckArgs -->|none| AddAllInterfaces[添加所有可用接口]
    
    LoadTSCodeGroup --> ProcessInterfaces[遍历处理接口]
    AddProBar --> ProcessInterfaces
    AddHoldersGroup --> ProcessInterfaces
    AddSingleInterface --> ProcessInterfaces
    AddGroup --> ProcessInterfaces
    AddAllInterfaces --> ProcessInterfaces
    
    ProcessInterfaces --> CheckPoints{检查积分权限}
    CheckPoints -->|积分不足| SkipInterface[跳过接口]
    CheckPoints -->|积分充足| ExecuteInterface[执行接口下载]
    
    ExecuteInterface --> GetInterfaceConfig[获取接口配置]
    GetInterfaceConfig --> CheckPaginationMode{检查分页模式}
    
    CheckPaginationMode -->|stock_loop| CheckProBar{检查是否为pro_bar}
    CheckPaginationMode -->|date_range| DownloadDateRange[下载日期范围数据]
    CheckPaginationMode -->|period_range| DownloadPeriodRange[下载期间范围数据]
    CheckPaginationMode -->|quarterly_range| DownloadQuarterlyRange[下载季度范围数据]
    CheckPaginationMode -->|periodic_range| DownloadPeriodicRange[下载周期性范围数据]
    CheckPaginationMode -->|broker_recommend| DownloadByMonth[按月份下载]
    
    CheckProBar -->|是| ProBarSpecial[pro_bar特殊处理]
    CheckProBar -->|否| GetStockList[获取股票列表]
    
    GetStockList --> ConcurrentDownload[并发下载股票数据]
    ProBarSpecial --> ConcurrentDownload
    
    ConcurrentDownload --> ProcessAndSave[处理并保存数据]
    DownloadDateRange --> ProcessAndSave
    DownloadPeriodRange --> ProcessAndSave
    DownloadQuarterlyRange --> ProcessAndSave
    DownloadPeriodicRange --> ProcessAndSave
    DownloadByMonth --> ProcessAndSave
    
    ProcessAndSave --> MoreInterfaces{还有更多接口?}
    MoreInterfaces -->|是| ProcessInterfaces
    MoreInterfaces -->|否| Cleanup[清理资源]
    
    SkipInterface --> MoreInterfaces
    
    Cleanup --> StopScheduler[停止调度器]
    Cleanup --> StopStorage[停止存储写入]
    Cleanup --> PrintReport[打印性能报告]
    
    StopScheduler --> End[结束]
    StopStorage --> End
    PrintReport --> End
```

## 3. 数据下载流程图

```mermaid
graph TD
    StartDownload[开始下载] --> GetConfig[获取接口配置]
    GetConfig --> ValidateParams[验证请求参数]
    
    ValidateParams --> CheckPagination{检查分页配置}
    
    CheckPagination -->|enabled| CheckMode{检查分页模式}
    CheckPagination -->|disabled| DirectRequest[直接请求API]
    
    CheckMode -->|offset| OffsetPagination[Offset分页<br/>offset+limit]
    CheckMode -->|date_range| DateRangePagination[日期范围分页<br/>按天/月/年]
    CheckMode -->|stock_loop| StockLoopPagination[股票循环分页<br/>逐个股票]
    CheckMode -->|period_range| PeriodRangePagination[期间范围分页<br/>财务期间]
    CheckMode -->|quarterly_range| QuarterlyRangePagination[季度范围分页<br/>Q1-Q4]
    CheckMode -->|periodic_range| PeriodicRangePagination[周期性范围分页<br/>定期数据]
    
    OffsetPagination --> CheckCache{检查缓存}
    DateRangePagination --> CheckCache
    StockLoopPagination --> CheckCache
    PeriodRangePagination --> CheckCache
    QuarterlyRangePagination --> CheckCache
    PeriodicRangePagination --> CheckCache
    DirectRequest --> CheckCache
    
    CheckCache -->|命中| ReturnCache[返回缓存数据]
    CheckCache -->|未命中| CheckCoverage{检查覆盖率}
    
    CheckCoverage -->|已覆盖| SkipDownload[跳过下载]
    CheckCoverage -->|未覆盖| RateLimitWait[等待速率限制令牌]
    
    RateLimitWait --> MakeRequest[发送API请求]
    MakeRequest --> RecordMetric[记录性能指标<br/>request_time]
    
    RecordMetric --> CheckResponse{检查响应}
    CheckResponse -->|成功| ProcessData[处理响应数据]
    CheckResponse -->|失败| Retry{重试次数<max_retries?}
    
    Retry -->|是| WaitRetry[等待retry_delay]
    WaitRetry --> MakeRequest
    Retry -->|否| ReturnError[返回错误]
    
    ProcessData --> ValidateSchema[验证数据模式]
    ValidateSchema --> ApplyDerivedFields[应用衍生字段转换]
    
    ApplyDerivedFields --> CheckDuplicates{检查重复数据}
    CheckDuplicates -->|有重复| RemoveDuplicates[去重]
    CheckDuplicates -->|无重复| SaveToCache[保存到缓存]
    
    RemoveDuplicates --> SaveToCache
    SaveToCache --> RecordDataMetric[记录数据指标<br/>data_size]
    
    RecordDataMetric --> CheckMore{还有更多分页?}
    CheckMore -->|是| NextPage[下一页/下一个范围]
    NextPage --> RateLimitWait
    
    CheckMore -->|否| ReturnData[返回所有数据]
    ReturnCache --> ReturnData
    SkipDownload --> ReturnData
    ReturnError --> ReturnData
    
    ReturnData --> EndDownload[结束下载]
```

## 4. 并发下载流程图

```mermaid
graph TD
    StartConcurrent[开始并发下载] --> GetStockList[获取股票列表<br/>从Data目录或API]
    
    GetStockList --> FilterStocks{是否指定ts_code?}
    FilterStocks -->|是| FilterByCode[按ts_code过滤]
    FilterStocks -->|否| UseAllStocks[使用所有股票]
    
    FilterByCode --> BuildTasks[构建任务列表]
    UseAllStocks --> BuildTasks
    
    BuildTasks --> CreateBatch{任务数>=100?}
    CreateBatch -->|是| SubmitBatch[提交批次任务]
    CreateBatch -->|否| AccumulateTasks[累积任务]
    
    SubmitBatch --> ExecuteTasks[执行任务<br/>带速率限制]
    AccumulateTasks --> CreateBatch
    
    ExecuteTasks --> WaitResults[等待结果<br/>as_completed]
    WaitResults --> CollectResults[收集结果数据]
    
    CollectResults --> CheckBatchSize{数据量>=batch_size?}
    CheckBatchSize -->|是| ProcessBatch[处理并保存批次]
    CheckBatchSize -->|否| MoreTasks{还有任务?}
    
    ProcessBatch --> ClearBatch[清空批次数据]
    ClearBatch --> MoreTasks
    
    MoreTasks -->|是| CreateBatch
    MoreTasks -->|否| ProcessRemaining[处理剩余数据]
    
    ProcessRemaining --> ReturnAllData[返回所有数据]
    ReturnAllData --> EndConcurrent[结束并发下载]
```

## 5. 存储管理流程图

```mermaid
graph TD
    StartStorage[开始存储] --> StartWriter[启动写入线程]
    
    StartWriter --> WaitData[等待数据<br/>queue.get]
    
    WaitData --> CheckSentinel{收到哨兵信号?}
    CheckSentinel -->|是| ProcessRemaining[处理剩余数据]
    CheckSentinel -->|否| AddToBatch[添加到批次]
    
    AddToBatch --> CheckBatchSize{批次大小>=batch_size?}
    CheckBatchSize -->|是| WriteBatch[写入批次数据]
    CheckBatchSize -->|否| WaitData
    
    WriteBatch --> ConvertData[转换数据格式<br/>dicts -> DataFrame]
    ConvertData --> CheckSchema{Schema已存在?}
    
    CheckSchema -->|是| AppendToFile[追加到现有Parquet文件]
    CheckSchema -->|否| WriteNewFile[写入新Parquet文件]
    
    AppendToFile --> SaveSchema[保存Schema信息]
    WriteNewFile --> SaveSchema
    
    SaveSchema --> ReturnWait[返回等待状态]
    ReturnWait --> WaitData
    
    ProcessRemaining --> CheckRemaining{还有剩余数据?}
    CheckRemaining -->|是| WriteRemaining[写入剩余数据]
    CheckRemaining -->|否| StopWriter[停止写入线程]
    
    WriteRemaining --> StopWriter
    StopWriter --> EndStorage[结束存储]
```

## 6. 缓存管理流程图

```mermaid
graph TD
    StartCache[开始缓存查询] --> CheckMemory{检查内存缓存}
    
    CheckMemory -->|命中| ReturnMemory[返回内存数据]
    CheckMemory -->|未命中| CheckDisk{检查Data目录}
    
    CheckDisk -->|命中| LoadDisk[从磁盘加载数据]
    CheckDisk -->|未命中| CallAPI[调用API获取数据]
    
    LoadDisk --> UpdateMemory[更新内存缓存]
    UpdateMemory --> ReturnDisk[返回磁盘数据]
    
    CallAPI --> ProcessResponse[处理API响应]
    ProcessResponse --> SaveToDisk[保存到Data目录]
    SaveToDisk --> SaveToMemory[保存到内存缓存]
    SaveToMemory --> ReturnAPI[返回API数据]
    
    ReturnMemory --> EndCache[结束缓存查询]
    ReturnDisk --> EndCache
    ReturnAPI --> EndCache
```

## 7. 数据处理器流程图

```mermaid
graph TD
    StartProcess[开始处理数据] --> ReceiveData[接收原始数据]
    
    ReceiveData --> ConvertToDF[转换为Polars DataFrame]
    ConvertToDF --> ApplyDerivedFields[应用衍生字段转换]
    
    ApplyDerivedFields --> CheckDerivedConfig{有衍生字段配置?}
    CheckDerivedConfig -->|是| ProcessEachDerived[遍历衍生字段]
    CheckDerivedConfig -->|否| ValidateData[直接验证数据]
    
    ProcessEachDerived --> CheckType{转换类型?}
    CheckType -->|date| ConvertDate[转换日期类型]
    CheckType -->|boolean| ConvertBool[转换布尔类型]
    CheckType -->|numeric| ConvertNumeric[转换数值类型]
    
    ConvertDate --> AddDerivedColumn[添加衍生列]
    ConvertBool --> AddDerivedColumn
    ConvertNumeric --> AddDerivedColumn
    
    AddDerivedColumn --> MoreDerived{更多衍生字段?}
    MoreDerived -->|是| ProcessEachDerived
    MoreDerived -->|否| ValidateData
    
    ValidateData --> CheckPrimaryKey{检查主键配置}
    CheckPrimaryKey -->|有配置| ValidateKey[验证主键完整性]
    CheckPrimaryKey -->|无配置| CheckDuplicates{检查重复数据}
    
    ValidateKey --> CheckDuplicates
    
    CheckDuplicates -->|有重复| RemoveDuplicates[去重处理]
    CheckDuplicates -->|无重复| CheckSchema[检查数据模式]
    RemoveDuplicates --> CheckSchema
    
    CheckSchema --> ValidateTypes[验证数据类型]
    ValidateTypes --> ReturnProcessed[返回处理后的DataFrame]
    
    ReturnProcessed --> EndProcess[结束数据处理]
```

## 8. 覆盖率管理流程图

```mermaid
graph TD
    StartCoverage[开始覆盖率检查] --> GetInterface[获取接口配置]
    
    GetInterface --> CheckDetection{启用重复检测?}
    CheckDetection -->|禁用| ReturnFalse[返回False<br/>不跳过]
    CheckDetection -->|启用| GetStrategy{获取检测策略}
    
    GetStrategy --> StrategyDate[date_range策略]
    GetStrategy --> StrategyPeriod[period_range策略]
    GetStrategy --> StrategyStock[stock_loop策略]
    GetStrategy --> StrategyQuarterly[quarterly_range策略]
    GetStrategy --> StrategyPeriodic[periodic_range策略]
    
    StrategyDate --> ReadExisting[读取现有数据]
    StrategyPeriod --> ReadExisting
    StrategyStock --> ReadExisting
    StrategyQuarterly --> ReadExisting
    StrategyPeriodic --> ReadExisting
    
    ReadExisting --> CheckData{数据存在且<br/>超过阈值?}
    CheckData -->|是| ReturnTrue[返回True<br/>跳过下载]
    CheckData -->|否| ReturnFalse
    
    ReturnFalse --> EndCoverage[结束覆盖率检查]
    ReturnTrue --> EndCoverage
```

## 9. 速率限制器流程图

```mermaid
graph TD
    StartRateLimit[开始速率限制] --> InitTokens[初始化令牌桶<br/>tokens = rate_limit]
    
    InitTokens --> WaitRequest[等待请求]
    
    WaitRequest --> CheckTokens{可用令牌数 >= 需要令牌?}
    CheckTokens -->|是| ConsumeTokens[消耗令牌]
    CheckTokens -->|否| CalculateWait[计算等待时间]
    
    CalculateWait --> SleepWait[等待 refill_time]
    SleepWait --> RefillTokens[补充令牌<br/>tokens = min(rate_limit, tokens + 补充值)]
    RefillTokens --> CheckTokens
    
    ConsumeTokens --> UpdateLastRefill[更新最后补充时间]
    UpdateLastRefill --> ProcessRequest[处理请求]
    
    ProcessRequest --> ReturnSuccess[返回成功]
    ReturnSuccess --> WaitRequest
```

## 10. 性能监控流程图

```mermaid
graph TD
    StartMonitor[开始监控] --> RecordMetric[记录指标<br/>request_time/data_size/retry_count]
    
    RecordMetric --> StoreMetric[存储到环形队列<br/>deque(maxlen=100)]
    
    StoreMetric --> CheckThreshold{检查阈值}
    CheckThreshold --> request_time_threshold{request_time > 30s?}
    CheckThreshold --> data_size_threshold{data_size > 6000?}
    CheckThreshold --> retry_count_threshold{retry_count > 2?}
    
    request_time_threshold -->|是| AlertRequestTime[警告: 请求时间过长]
    request_time_threshold -->|否| ContinueMonitor
    data_size_threshold -->|是| AlertDataSize[警告: 数据量接近限制]
    data_size_threshold -->|否| ContinueMonitor
    retry_count_threshold -->|是| AlertRetry[警告: 重试频率过高]
    retry_count_threshold -->|否| ContinueMonitor
    
    AlertRequestTime --> ContinueMonitor
    AlertDataSize --> ContinueMonitor
    AlertRetry --> ContinueMonitor
    
    ContinueMonitor --> GetAverage{需要平均值?}
    GetAverage -->|是| CalculateAverage[计算平均值<br/>sum(values)/len(values)]
    GetAverage -->|否| ContinueRecording[继续记录]
    
    CalculateAverage --> ReturnAverage[返回平均值]
    ReturnAverage --> ContinueRecording
    
    ContinueRecording --> WaitNext[等待下一个指标]
    WaitNext --> RecordMetric
```

## 核心组件说明

### 1. 配置驱动架构
- **零代码扩展**: 通过YAML配置文件添加新接口，无需修改代码
- **声明式配置**: 所有接口行为在配置文件中定义
- **环境变量替换**: 支持`${VAR}`语法，敏感信息通过环境变量管理

### 2. 多策略分页系统
- **Offset分页**: 适用于支持offset和limit参数的接口
- **日期范围分页**: 按天/月/年分割请求
- **股票循环分页**: 逐个股票查询
- **期间范围分页**: 财务数据的期间查询
- **季度范围分页**: 季度财务数据
- **周期性范围分页**: 定期数据查询

### 3. 三层缓存架构
- **内存缓存**: 运行时缓存，线程安全
- **磁盘缓存**: Data目录存储，持久化
- **智能回退**: Mem -> Disk -> API 的自动回退机制

### 4. 异步存储系统
- **生产者-消费者模式**: 数据队列 + 写入线程
- **批次处理**: 批量写入优化性能
- **原子操作**: 防止并发文件损坏
- **Dataset模式**: Parquet数据集格式，支持高效查询

### 5. 智能覆盖率管理
- **重复检测**: 避免冗余下载
- **多种策略**: 日期范围、期间、股票基础检测
- **内存缓存**: 频繁访问数据的运行时缓存
- **阈值控制**: 可配置的覆盖率阈值

### 6. 性能监控与告警
- **实时跟踪**: request_time, data_size, retry_count
- **阈值告警**: 超过阈值时发出警告
- **统计分析**: 计算平均值和趋势
- **环形队列**: 保留最近100个指标

### 7. 异常处理与资源管理
- **Try-Finally结构**: 确保资源正确释放
- **优雅退出**: 处理完当前批次后停止
- **错误重试**: 指数退避重试策略
- **日志记录**: 全面的错误日志和性能日志

## 数据流总结

1. **配置加载**: 启动时加载所有YAML配置
2. **参数验证**: 验证命令行参数和接口参数
3. **缓存检查**: 优先从缓存获取数据
4. **覆盖率检查**: 避免重复下载已覆盖的数据
5. **速率限制**: 令牌桶算法控制请求频率
6. **API请求**: 发送请求到TuShare API
7. **数据处理**: Polars高性能数据处理和转换
8. **数据验证**: 主键验证、类型检查、去重
9. **异步存储**: 队列+线程实现非阻塞存储
10. **性能监控**: 实时跟踪和告警

## 关键设计模式

- **配置驱动**: 所有接口行为通过YAML配置定义
- **策略模式**: 多种分页策略可插拔
- **生产者-消费者**: 异步存储系统
- **缓存模式**: 三层缓存架构
- **令牌桶**: 速率限制算法
- **观察者模式**: 性能监控和告警