# Main.py 下载到存储的完整流程图（Mermaid版）

**日期**: 2026-02-14
**版本**: 4.0 (基于当前 App4 代码)

---

## 📊 完整数据流程图（Mermaid）

```mermaid
graph TD
    Start([开始: python app4/main.py]) --> Init[main.py: main函数]
    Init --> ParseArgs[main.py: 解析命令行参数]
    ParseArgs --> UpdateMode{--update 或 --incremental?}
    UpdateMode -->|是| RunUpdate[main.py: run_update_mode]
    UpdateMode -->|否| InitNormal[main.py: 初始化非更新模式]

    subgraph NormalInit["非更新模式初始化"]
        InitNormal --> ConfigLoader[创建ConfigLoader并校验配置]
        ConfigLoader --> SetupLogging[setup_logging]
        SetupLogging --> Scheduler[创建TaskScheduler]
        Scheduler --> StorageMgr[创建StorageManager]
        StorageMgr --> Processor[创建DataProcessor]
        Processor --> CacheWarmer[创建CacheWarmer并预热缓存]
        CacheWarmer --> Downloader[创建GenericDownloader]
        Downloader --> PreloadTradeCal[预加载交易日历]
        PreloadTradeCal --> StartScheduler[启动调度器]
        StartScheduler --> StartWriter[启动写入线程]
    end

    StartWriter --> SelectInterfaces[确定 interfaces_to_run]
    SelectInterfaces --> ForEachInterface[循环处理接口]
    ForEachInterface --> LoadConfig[获取接口配置并检查权限]
    LoadConfig --> BuildParams[生成请求参数]
    BuildParams --> CheckStockLoop{pagination.mode == stock_loop?}

    CheckStockLoop -->|是| PrepareStockList[准备 stock_list]
    PrepareStockList --> RunConcurrent[run_concurrent_stock_download]
    CheckStockLoop -->|否| DirectDownload[downloader.download]

    DirectDownload --> ProcessSave[process_and_save_data]
    ProcessSave --> SaveAsync[storage_manager.save_data async_write=True]
    SaveAsync --> WriterWorker[_writer_worker 写入文件]

    RunConcurrent --> SubmitTasks[提交任务到 TaskScheduler]
    SubmitTasks --> DownloadStock[downloader.download_single_stock]
    DownloadStock --> PaginationExec[PaginationExecutor.execute]
    PaginationExec --> MakeRequest[_make_request]
    MakeRequest --> AddToBuffer[storage_manager.add_to_buffer]
    AddToBuffer --> ProcessQueue[_process_worker 去重/验证]
    ProcessQueue --> WriteInterfaceData[_write_interface_data 写入文件]

    subgraph UpdateModeFlow["增量更新模式（run_update_mode）"]
        RunUpdate --> UpdateInit[初始化组件并预热缓存]
        UpdateInit --> UpdateSelect[确定 interfaces_to_update]
        UpdateSelect --> UpdateLoop[循环接口]
        UpdateLoop --> UpdateDates[计算/解析日期范围]
        UpdateDates --> UpdateStockLoop{pagination.mode == stock_loop?}
        UpdateStockLoop -->|是| UpdateStockList[准备 stock_list]
        UpdateStockList --> RunConcurrent
        UpdateStockLoop -->|否| UpdateDirect[downloader.download]
        UpdateDirect --> UpdateCount[记录成功/失败/跳过]
    end

    WriterWorker --> Finalize[finally 清理资源并停止线程]
    WriteInterfaceData --> Finalize
    UpdateCount --> Finalize
```

---

## 🔍 关键函数调用链详细说明

### 1. 入口函数：main.py

```mermaid
graph LR
    A[main.py: main函数] --> B[解析参数]
    B --> C{--update 或 --incremental?}
    C -->|是| D[run_update_mode]
    C -->|否| E[初始化组件]
    E --> F[创建GenericDownloader]
    F --> G[预热缓存并启动线程]
    G --> H[运行接口]
```

**文件位置**: `app4/main.py` (第 530 行开始)

---

### 2. 并发股票下载：run_concurrent_stock_download

```mermaid
graph TD
    A[main.py: run_concurrent_stock_download] --> B[初始化tasks=[]]
    B --> C[for stock in stock_list]
    C --> D[创建task并加入tasks]
    D --> E{tasks数量>=100?}
    E -->|否| C
    E -->|是| F[scheduler.submit_tasks]
    F --> G[汇总已完成记录数]
    G --> H[清空tasks]
```

**文件位置**: `app4/main.py` (第 151 行)

---

### 3. 任务提交：scheduler.submit_tasks

```mermaid
graph TD
    A[main.py: scheduler.submit_tasks] --> B[scheduler.py: submit_tasks]
    B --> C[分配给worker线程]
    C --> D[downloader.py: download_single_stock]
```

**文件位置**: 
- 调用: `app4/main.py` (第 171, 184 行)
- 实现: `app4/core/scheduler.py` (第 35 行)

---

### 4. 下载单只股票：download_single_stock

```mermaid
graph TD
    A[downloader.py: download_single_stock] --> B[准备股票参数]
    B --> C{CoverageManager启用?}
    C -->|是| D[检测缺口或跳过策略]
    C -->|否| E[继续下载]
    D --> E
    E --> F[PaginationExecutor.execute]
    F --> G[_make_request]
    G --> H[返回原始数据]
    H --> I{有storage_manager?}
    I -->|是| J[storage_manager.add_to_buffer]
    I -->|否| K[返回数据]
```

**文件位置**: `app4/core/downloader.py` (第 416 行)

---

### 5. API请求：_make_request

```mermaid
graph TD
    A[downloader.py: _make_request] --> B[构建请求参数]
    B --> C[调用TuShare API]
    C --> D[返回原始数据List[Dict]]
```

**文件位置**: `app4/core/downloader.py` (第 589 行)

---

### 6. Buffer机制：add_to_buffer

```mermaid
graph TD
    A[downloader.py: add_to_buffer] --> B[storage.py: add_to_buffer]
    B --> C[获取或创建buffer]
    C --> D[buffer['data'].extend data]
    D --> E[buffer['count'] += len data]
    E --> F{>=5000 或 <100?}
    F -->|否| G[返回]
    F -->|是| H[触发flush]
    H --> I[取出buffer['data']]
    I --> J[重置buffer]
    J --> K[process_queue.put task]
```

**文件位置**: 
- 调用: `app4/core/downloader.py` (第 551 行附近)
- 实现: `app4/core/storage.py` (第 441 行)

---

### 7. Process Worker处理：_process_worker

```mermaid
graph TD
    A[storage.py: _process_worker线程] --> B[从process_queue获取任务]
    B --> C{数据已处理?<br/>_update_time in data[0]?}
    C -->|是| D[直接_write_interface_data]
    C -->|否| E[完整处理流程]
    
    E --> F[获取interface_config]
    F --> G[processor.process_data]
    
    G --> H[processor.validate_data]
    H --> I[与现有数据去重]
    I --> J[_write_interface_data]
    
    D --> K[记录日志]
    J --> K
```

**文件位置**: `app4/core/storage.py` (第 532 行)

---

### 8. 数据处理：processor.process_data

```mermaid
graph TD
    A[processor.py: process_data] --> B[SchemaManager.create_dataframe_safe]
    B --> C[_apply_type_conversions]
    C --> D[_filter_primary_key_nulls]
    D --> E[_handle_primary_keys]
    
    E --> F[df.to_dicts]
    F --> G[_detect_duplicates_fast]
    G --> H[SchemaManager.load_schema]
    H --> I{有预定义schema?}
    I -->|是| J[pl.DataFrame with schema]
    I -->|否| K[pl.DataFrame infer_schema]
    
    J --> L[logger.info Processed X records]
    K --> L
    
    L --> M[_remove_duplicates]
    M --> N[_clean_data]
    N --> O[返回DataFrame]
```

**文件位置**: `app4/core/processor.py` (第 16 行)

---

### 9. 批量处理：process_and_save_data

```mermaid
graph TD
    A[main.py: process_and_save_data] --> B[检查data是否为空]
    B --> C[processor.process_data]
    C --> D[检查df是否为空]
    D --> E[processor.validate_data]
    E --> F[与现有数据去重]
    F --> G[logger.info Processed X records]
    G --> H[storage_manager.save_data async_write=True]
```

**文件位置**: `app4/main.py` (第 783 行)

---

### 10. 异步保存：save_data

```mermaid
graph TD
    A[storage.py: save_data] --> B{async_write?}
    B -->|否| C[_write_interface_data]
    B -->|是| D{数据已处理?<br/>_update_time in data[0]?}
    D -->|是| E[data_queue.put task]
    D -->|否| F[process_queue.put task]
    
    E --> G[_writer_worker处理]
    F --> H[_process_worker处理]
```

**文件位置**: `app4/core/storage.py` (第 706 行)

---

### 11. Writer Worker处理：_writer_worker

```mermaid
graph TD
    A[storage.py: _writer_worker线程] --> B[从data_queue获取任务]
    B --> C[_write_batch]
    C --> D[按接口分组数据]
    D --> E[_write_interface_data]
    
    E --> F[SchemaManager.create_dataframe_safe]
    F --> G[确定日期范围]
    G --> H[生成文件名]
    H --> I[原子写入<br/>写临时文件→重命名]
    I --> J[logger.info Wrote X records to file]
```

**文件位置**: `app4/core/storage.py` (第 147 行)

---

### 12. 写入接口数据：_write_interface_data

```mermaid
graph TD
    A[storage.py: _write_interface_data] --> B[SchemaManager.create_dataframe_safe]
    B --> C[确定日期范围<br/>优先级: period > trade_date > cal_date > ann_date]
    C --> D[生成文件名<br/>{interface}_{start}_{end}_{timestamp}_{uuid}.parquet]
    D --> E[写入临时文件]
    E --> F[重命名为正式文件]
    F --> G[logger.info Wrote X records to file]
```

**文件位置**: `app4/core/storage.py` (第 252 行)

---

## 📊 执行路径对比

### 路径1: stock_loop + buffer 处理

```mermaid
graph TD
    A[下载单只股票] --> B[add_to_buffer]
    B --> C[累积到buffer]
    C --> D{达到5000条?}
    D -->|是| E[flush到process_queue]
    D -->|否| F[继续累积]
    E --> G[_process_worker]
    G --> H[processor.process_data]
    H --> I[_write_interface_data]
    I --> J[写入数据]
    
    style A fill:#ffe6e6,stroke:#ff6666
    style B fill:#ffe6e6,stroke:#ff6666
    style C fill:#ffe6e6,stroke:#ff6666
    style D fill:#ffe6e6,stroke:#ff6666
    style E fill:#ffe6e6,stroke:#ff6666
    style F fill:#ffe6e6,stroke:#ff6666
    style G fill:#ffe6e6,stroke:#ff6666
    style H fill:#ffe6e6,stroke:#ff6666
    style I fill:#ffe6e6,stroke:#ff6666
    style J fill:#ffe6e6,stroke:#ff6666
```

**特点**:
- 实时处理，边下载边处理
- 内存占用低
- 适合大规模数据下载
- 可能产生较多小文件

---

### 路径2: 非 stock_loop 直接下载

```mermaid
graph TD
    A[downloader.download] --> B[process_and_save_data]
    B --> C[processor.process_data]
    C --> D[processor.validate_data]
    D --> E[与现有数据去重]
    E --> F[storage_manager.save_data async_write=True]
    F --> G[_writer_worker]
    G --> H[_write_interface_data]
    H --> I[写入数据]

    style A fill:#e6f7ff,stroke:#66aaff
    style B fill:#e6f7ff,stroke:#66aaff
    style C fill:#e6f7ff,stroke:#66aaff
    style D fill:#e6f7ff,stroke:#66aaff
    style E fill:#e6f7ff,stroke:#66aaff
    style F fill:#e6f7ff,stroke:#66aaff
    style G fill:#e6f7ff,stroke:#66aaff
    style H fill:#e6f7ff,stroke:#66aaff
    style I fill:#e6f7ff,stroke:#66aaff
```

**特点**:
- 简化流程，主线程直接处理与保存
- 适合非 stock_loop 接口
- 复用异步写入线程

---

## 📝 函数索引表

| 函数名 | 文件 | 行号 | 功能 | 路径 |
|--------|------|------|------|------|
| `main` | main.py | 530 | 程序入口 | 通用 |
| `run_concurrent_stock_download` | main.py | 151 | 并发股票下载 | 通用 |
| `download_single_stock` | downloader.py | 416 | 下载单只股票 | 通用 |
| `_make_request` | downloader.py | 589 | API请求 | 通用 |
| `add_to_buffer` | storage.py | 441 | 添加到Buffer | 路径1 |
| `_process_worker` | storage.py | 532 | 处理线程工作 | 路径1 |
| `process_data` | processor.py | 16 | 数据处理 | 路径1, 路径2 |
| `_handle_primary_keys` | processor.py | 210 | 主键处理 | 路径1, 路径2 |
| `process_and_save_data` | main.py | 783 | 处理与保存 | 路径2 |
| `save_data` | storage.py | 706 | 保存数据 | 路径2 |
| `_writer_worker` | storage.py | 147 | 写入线程工作 | 路径2 |
| `_write_interface_data` | storage.py | 252 | 写入接口数据 | 路径1, 路径2 |
| `submit_tasks` | scheduler.py | 35 | 批量提交任务 | 通用 |

---
