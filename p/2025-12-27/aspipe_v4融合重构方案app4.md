# aspipe_v4 融合重构方案 (App4) - 配置驱动架构

## 一、 项目现状分析

### 1.1 代码结构概览

```
aspipe_v4/app/
├── main.py                          # 主入口（532行）
├── enhanced_main_downloader.py      # 增强版下载器
├── score_based_downloader.py        # 积分管理下载器
├── config.py                        # 基础配置（token、积分）
├── config_adapter.py                # 配置适配器
├── download_config.py               # 简单布尔开关配置
├── enhanced_download_config.py      # 详细配置（优先级、重试、限流）
├── score_config.py                  # 积分配置
│
├── tushare_api.py                   # TuShare主下载器（Facade模式）
├── download_scheduler.py            # 下载调度器
├── date_range_downloader.py         # 日期范围下载器（遗留）
├── task_queue_manager.py            # 任务队列管理
├── storage_worker.py                # 存储工作线程
├── global_rate_limiter.py           # 全局限流器
├── parallel_downloader.py           # 并行下载器
│
├── download_strategies.py           # 下载策略
├── strategy_factory.py              # 策略工厂
│
├── interfaces/                      # 12个接口模块
│   ├── base.py
│   ├── basic_data.py
│   ├── daily_data.py
│   ├── financial_data.py
│   ├── market_flow.py
│   ├── holders_data.py
│   ├── holders_data_downloader.py
│   ├── technical_factors.py
│   ├── cyq_chips.py
│   ├── market_structure.py
│   └── research_data.py
│
├── cache_manager.py                 # 缓存管理
├── cache_key_generator.py           # 缓存键生成
├── cache_monitor.py                 # 缓存监控
├── stock_list_manager.py            # 股票列表管理器
├── error_handler.py                 # 错误处理
├── parameter_adapters.py            # 参数适配器
└── utils/                           # 工具函数
```

### 1.2 main.py参数功能清单（必须保留）

| 参数 | 功能 | 关联代码 | 优先级 |
|------|------|----------|--------|
| `--start_date` | 起始日期 | download_all_data_from_date | **必须保留** |
| `--end_date` | 结束日期 | download_all_data_from_date | **必须保留** |
| `--use_legacy` | 传统下载方式 | download_with_legacy_method | **必须保留** |
| `--holders-data` | 股东数据下载 | holders_data、stk_rewards、top10_holders | **必须保留** |
| `--pro-bar-only` | 仅pro_bar下载 | pro_bar接口 | **必须保留** |
| `--tscode-historical` | 全历史数据下载 | DownloadScheduler(tscode_historical模式) | **必须保留** |

### 1.3 现有问题汇总（从配置驱动角度）

#### 问题1：接口逻辑硬编码

**现状**：每个Tushare接口都有独立的Python类，接口特定逻辑（参数、分页、URL路径、主键等）散布在代码中。

**影响**：新增接口困难，维护成本高。

#### 问题2：配置系统碎片化

**现状**：存在4套独立配置（`config.py`, `download_config.py`, `enhanced_download_config.py`, `score_config.py`）。

**影响**：配置分散，维护困难。

#### 问题3：Facade模式过度使用

**现状**：`TuShareDownloader`使用`__getattr__`动态委托到12个接口模块。

**影响**：IDE无法追踪，类型不安全。

#### 问题4：策略模式复杂

**现状**：`download_strategies.py` 和 `strategy_factory.py` 增加了复杂度。

**影响**：策略逻辑与接口逻辑耦合。

#### 问题5：参数适配器冗余

**现状**：`parameter_adapters.py`包含多个适配器。

**影响**：每个接口都需要独立的适配器。

#### 问题6：接口分组硬编码

**现状**：接口分组硬编码在`main.py`中。

**影响**：无法灵活调整分组。

## 二、 融合重构目标

### 2.1 总体目标

1.  **全配置化接口**：新增接口只需编写YAML文件。
2.  **配置即代码**：剥离Python代码中的接口特定逻辑。
3.  **统一下载引擎**：`GenericDownloader` 根据YAML指令运行。
4.  **灵活控制**：YAML中控制分页、代理、限流。
5.  **标准化处理**：YAML定义输出字段、类型、主键。
6.  **极简维护**：维护者无需深入了解类结构。
7.  **完全兼容**：保持CLI参数兼容性。

## 三、 背景与目标

此方案 (`App4`) 旨在解决**接口扩展性**和**配置灵活性**问题。核心是**“配置即代码”**。

### 3.1 核心目标

1.  **全配置化接口**：接口逻辑全在YAML。
2.  **统一的下载引擎**：`GenericDownloader` 为通用执行器。
3.  **灵活的代理与分页**：YAML精细控制请求细节。
4.  **标准化数据处理**：YAML定义数据清洗规则。

## 四、 架构设计

### 4.1 目录结构

```
aspipe_v4/app4/
├── config/
│   ├── settings.yaml          # 全局配置（Token, 默认重试次数, 全局代理root等）
│   └── interfaces/            # 接口定义目录
│       ├── daily.yaml         # 日线行情配置
│       ├── pro_bar.yaml       # 复权行情配置
│       ├── stock_basic.yaml   # 股票列表配置
│       └── ... (其他接口)
├── core/
│   ├── __init__.py
│   ├── config_loader.py       # 配置加载器
│   ├── downloader.py          # 通用下载器
│   ├── processor.py           # 数据处理器
│   ├── storage.py             # 存储管理器
│   ├── cache_manager.py       # 缓存管理器
│   └── scheduler.py           # 任务调度器
├── main.py                    # 统一CLI入口
└── utils/
    └── logger.py
```

### 4.2 YAML 配置规范

每个接口的 YAML 配置文件必须包含以下 **6 大类核心信息**：

1.  **基础元数据 (Metadata)**: 标识接口身份。
2.  **权限与限制 (Permissions)**: 积分要求与流控。
3.  **请求配置 (Request)**: 代理路径、HTTP 方法等。
4.  **输入参数 (Parameters)**: 字段定义与校验。
5.  **分页策略 (Pagination)**: 定义如何切分任务。
6.  **输出配置 (Output)**: 主键定义与字段类型清洗。

#### 示例：`pro_bar.yaml` (完整版)

```yaml
# 1. 基础元数据
name: pro_bar
api_name: pro_bar
description: "A股复权行情"

# 2. 权限与限制
permissions:
  min_points: 0    # 最低积分要求
  rate_limit: 60   # 每分钟请求限制
  query_limit: 5000 # 单次请求最大返回行数

# 3. 请求配置
request:
  method: POST
  # 关键配置：接口的额外地址（用于代理服务器场景）
  extra_path: "/api/pro_bar" 
  timeout: 60

# 4. 输入参数定义
parameters:
  ts_code:
    type: string
    required: true
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期 YYYYMMDD"
  end_date:
    type: string
    required: false
    description: "结束日期 YYYYMMDD"
  adj:
    type: string
    required: false
    default: "qfq"
    options: ["qfq", "hfq", null]
    description: "复权类型"
  freq:
    type: string
    required: false
    default: "D"
    description: "数据频度"
  asset:
    type: string
    required: false
    default: "E"
    description: "资产类别"
  ma:
    type: list
    required: false
    description: "均线"

# 5. 分页与循环策略
pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 3650
  
# 6. 输出与存储配置
output:
  primary_key: 
    - ts_code
    - trade_date
    - adj
    
  sort_by: ["trade_date"]
  
  columns:
    ts_code:
      type: string
      required: true
    trade_date:
      type: date
      format: "%Y%m%d"
      required: true
    open:
      type: float
    close:
      type: float
    high:
      type: float
    low:
      type: float
    vol:
      type: float
    amount:
      type: float
```

#### 示例：`stock_basic.yaml` (简略版)

```yaml
name: stock_basic
api_name: stock_basic
description: "股票列表"

permissions:
  min_points: 2000

request:
  extra_path: "" 

parameters:
  exchange:
    type: string
  list_status:
    type: string
    default: "L"

pagination:
  enabled: true
  mode: "offset"
  limit_key: "limit"
  offset_key: "offset"
  default_limit: 5000

output:
  primary_key: ["ts_code"]
  columns:
    ts_code: {type: string}
    name: {type: string}
    list_date: {type: date}
```

### 4.3 核心组件逻辑

#### 1. ConfigLoader (配置加载器)
- **职责**：启动时加载 `config/interfaces/*.yaml`。
- **功能**：校验 YAML 格式，构建内存中的配置字典。

#### 2. CacheManager (缓存管理器) - 优雅的缓存策略
- **位置**：`app4/core/cache_manager.py`
- **实现方式**：
    - **配置驱动**：读取 `settings.yaml` 全局缓存策略及接口特定 YAML 配置。
    - **透明集成**：`GenericDownloader` 在请求前自动查询缓存。
    - **键值生成**：基于 YAML `parameters` 生成唯一哈希键 (e.g., `pro_bar_..._qfq`)。
    - **生命周期**：提供过期清理和完整性校验。

#### 3. TaskScheduler & Concurrency (任务调度与并发) - 高效的异步模型
- **位置**：`app4/core/scheduler.py`
- **实现方式**：
    - **全局并发**：`settings.yaml` 控制 `max_workers`。
    - **精细限流**：根据 YAML `permissions.rate_limit` 使用令牌桶/信号量限流。
    - **解耦执行**：调度器负责并发管理，`GenericDownloader` 专注单一任务。
    - **异步/多线程**：使用 `ThreadPoolExecutor` 执行任务。

#### 4. GenericDownloader (通用下载器) - 原子化的执行引擎
- **位置**：`app4/core/downloader.py`
- **职责**：
    - 接收接口名和参数。
    - 检查缓存。
    - 校验参数。
    - 执行分页/循环逻辑。
    - 发起请求。
    - 写入缓存。

#### 5. StorageManager (存储管理器) - 异步持久化
- **位置**：`app4/core/storage.py`
- **实现方式**：
    - **生产-消费**：下载数据推送到队列，异步写入。
    - **批量优化**：利用 `Processor` 定义的主键去重，批量写入 Parquet。

#### 6. Processor (处理器)
- **职责**：类型转换，主键检查，数据去重。

### 4.4 CLI 参数映射与兼容性

| 原有参数 | App4 对应策略 | 说明 |
| :--- | :--- | :--- |
| `--start_date` | 传递给 `GenericDownloader` | 通用查询参数。 |
| `--end_date` | 传递给 `GenericDownloader` | 同上。 |
| `--use_legacy` | **移除/忽略** | App4 为新架构。 |
| `--holders-data` | **接口组** | 映射到 `settings.yaml` 中的 `holders` 组。 |
| `--pro-bar-only` | **接口别名** | 等同于 `--interface pro_bar`。 |
| `--tscode-historical`| **下载模式** | 触发 `stock_loop` 或特定接口模式。 |

#### 新增通用参数
- `--interface <name>`: 指定接口。
- `--group <name>`: 指定接口组。
- `--concurrency <int>`: 覆盖并发数。

### 2.6 核心功能增强说明 (Core Features)

在 App4 中，缓存、并发下载和并发存储不仅仅是底层实现细节，而是通过配置系统直接暴露给用户的核心能力。

#### 1. 智能缓存系统 (Smart Caching)
- **功能定义**：自动管理本地数据生命周期，减少重复网络请求，加速回测和分析。
- **核心能力**：
    - **自动命中 (Auto-Hit)**：下载器在发起网络请求前，根据 YAML 生成的唯一 Key（如 `pro_bar_000001.SZ_qfq`）自动检查本地缓存。
    - **智能预热 (Smart Warming)**：支持配置“常用数据”，系统启动时自动在后台静默更新这些数据的缓存（如最近30天的日线）。
    - **生命周期管理 (TTL)**：支持按接口配置过期时间（如 `daily` 缓存24小时，`balance_sheet` 缓存30天），并自动清理过期文件。
    - **完整性校验**：定期扫描 Parquet 文件，自动剔除损坏或不完整的缓存文件。

#### 2. 异步并发下载 (Async Concurrent Downloading)
- **功能定义**：通过多线程和非阻塞 I/O 最大化利用网络带宽和 API 额度。
- **核心能力**：
    - **接口级隔离**：使用信号量 (Semaphore) 为每个接口独立控制并发数（如 `daily` 允许 4 并发，`pro_bar` 允许 8 并发）。
    - **精准限流**：内置令牌桶算法，严格遵守 YAML 中定义的 `rate_limit`（如 60次/分钟），避免触发 Tushare 封控。
    - **批量处理**：支持将大量小请求（如单只股票的历史数据）自动打包成批处理任务，通过线程池并行执行。
    - **任务调度**：支持优先级队列，高优先级任务（如实时行情）可抢占执行资源。

#### 3. 异步并发存储 (Async Concurrent Storage)
- **功能定义**：解耦下载与存储过程，消除 I/O 瓶颈，确保数据写入的高可靠性。
- **核心能力**：
    - **生产-消费模型**：下载器仅负责将数据推入内存队列，存储 Worker 在后台异步消费队列，实现“下载不等待写入”。
    - **批量写入 (Batch Write)**：支持积攒一定数量的数据块（如 10 个 DataFrames）后一次性触发磁盘写入，减少文件句柄开销。
    - **自动重试与容错**：写入失败时自动进入重试队列（指数退避策略），多次失败后自动记录错误日志并触发回调。
    - **非阻塞回调**：存储完成后通过回调函数通知主线程（如更新进度条或触发后续处理），不阻塞主下载流程。

## 三、 实施优势

1.  **极简维护**：维护者不需要懂 Python 类继承结构，只需修改 YAML 文本。
2.  **解耦**：下载逻辑与业务逻辑完全分离。
3.  **适应性强**：`pro_bar` 这种需要特殊处理的接口（如特殊的代理路径、参数组合）完全可以通过 YAML 配置描述，而无需硬编码 `if interface == 'pro_bar': ...`。
4.  **功能完备**：保留并增强了原有的缓存和并发能力，但将其配置化，更易于调整和优化。
5.  **文档化**：YAML 文件本身就是最好的接口文档。
6.  **完全兼容**：通过参数映射层，老用户可以继续使用熟悉的 CLI 参数，同时享受新架构的稳定性。
7.  **高性能**：通过全链路异步化（下载->处理->存储）和智能缓存，显著提升大数据量下的吞吐能力。

## 四、 迁移路线图


## 五、 实施优势

1.  **高内聚**：所有接口特定逻辑集中在 YAML，通用逻辑集中在 Core 组件。
2.  **低耦合**：下载器不依赖具体接口类，只依赖配置。
3.  **原子化**：下载、缓存、存储操作分离，可独立测试。
4.  **优雅简洁**：Python 代码量大幅减少，逻辑清晰。
5.  **完全兼容**：无缝迁移现有工作流。

## 六、 迁移路线图

### 阶段 1：基础框架搭建 (2天)
- 创建目录结构。
- 实现 `ConfigLoader`, `GenericDownloader` 原型。
- 移植 `CacheManager`。

### 阶段 2：并发与调度实现 (2天)
- 实现 `TaskScheduler` (线程池, 限流)。
- 编写 `settings.yaml`。

### 阶段 3：核心接口迁移 (2天)
- 编写 `stock_basic`, `daily`, `pro_bar` YAML。
- 调试下载全流程。

### 阶段 4：全量接口迁移与CLI (3天)
- 转化剩余接口 YAML。
- 实现 `main.py` 及参数映射。

### 阶段 5：测试与文档 (1天)
- 验证配置正确性。
- 压力与缓存测试。
- 更新文档。