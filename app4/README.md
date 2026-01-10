# aspipe_v4 App4 - 配置驱动架构

aspipe_v4 是一个综合性的金融数据管道系统，从 TuShare API 下载股票市场数据并将其存储为 Parquet 格式。App4 架构代表了从代码驱动到配置驱动数据下载的范式转变，提供更高的灵活性、更强的性能和更好的可维护性。

## 架构特点

### 零代码接口添加
- 通过创建 YAML 配置文件添加新接口
- 无需编写任何代码即可扩展功能

### 通用下载器
- 单个通用下载器根据配置处理所有接口
- 支持多种分页策略

### 多策略分页
- **Offset 分页**: 适用于支持 offset 和 limit 参数的接口
- **日期范围分页**: 适用于按日期范围查询的接口
- **股票循环分页**: 适用于需要逐个股票查询的接口
- **期间范围分页**: 适用于财务数据的期间查询
- **季度范围分页**: 适用于季度财务数据
- **周期性范围分页**: 适用于定期数据查询

### 异步架构
- 生产者-消费者模式，支持非阻塞 I/O
- 高性能数据处理

## 核心组件

### 1. 配置加载器 (`core/config_loader.py`)
- 从 YAML 文件加载全局设置和接口配置
- 支持环境变量替换（`${VAR}` 语法）
- 执行配置验证和完整性检查

### 2. 通用下载器 (`core/downloader.py`)
- 通用下载引擎，根据配置处理任何接口
- 实现多种分页策略（offset, date_range, stock_loop, period_range, quarterly_range, periodic_range）
- 特色智能缓存与交易日历派生策略
- 监控性能指标（请求时间、数据大小、重试次数）
- 包含覆盖率管理以避免冗余下载

### 3. 任务调度器 (`core/scheduler.py`)
- 管理线程池以进行并发任务执行
- 实现令牌桶算法进行 API 速率限制
- 支持批量任务提交和随机延迟

### 4. 缓存管理器 (`core/cache_manager.py`)
- 基于 TTL 的数据缓存，使用基于哈希的文件名
- 支持 pickle 和 parquet 存储格式
- 原子写入操作防止并发文件损坏
- 智能交易日历派生以优化缓存命中率

### 5. 存储管理器 (`core/storage.py`)
- 使用生产者-消费者模式的异步数据持久化
- 批处理和追加操作到现有 parquet 文件
- 线程安全操作与队列管理
- 数据集模式存储以提高效率

### 6. 数据处理器 (`core/processor.py`)
- 使用 Polars 进行高性能数据验证和转换
- 主键处理和去重
- 数据质量检查和类型转换

### 7. Schema 管理器 (`core/schema_manager.py`)
- 预定义数据类型 schema 以避免运行时推理开销
- 为高频金融数据接口优化的 schema

### 8. 覆盖率管理器 (`core/coverage_manager.py`)
- 实现重复检测以避免冗余下载
- 支持多种策略：日期范围、期间和股票基础检测
- 使用内存缓存进行高效覆盖率检查

## 配置结构

### 全局配置 (`config/settings.yaml`)

```yaml
app:
  name: "aspipe_v4"
  version: "4.0.0"

tushare:
  token: "${TUSHARE_TOKEN}"
  base_url: "http://api.tushare.pro"
  points_thresholds: # 积分权限映射
    basic: 120
    standard: 2000
    advanced: 5000
    professional: 8000

concurrency:
  max_workers: 4  # [修改] 从 8 改为 4
  max_queue_size: 1000

request:
  max_retries: 3
  retry_delay: 1.0
  timeout: 30

cache:
  directory: "cache"
  ttl_hours: 24
  max_size_gb: 10

storage:
  base_dir: "../data"  # [修改] 从 "data" 改为 "../data"
  format: "parquet"
  batch_size: 10000  # [优化] 从 1000 增大到 10000

logging:
  level: "INFO"
  file: "log/app4.log"
  max_size_mb: 100
  backup_count: 5

groups:
  tscode_historical:
    - "stk_rewards"
    - "top10_holders"
    - "pledge_detail"
    - "fina_audit"
    - "top10_floatholders"
    - "stk_holdertrade"
  holders:
    - "top10_holders"
    - "top10_floatholders"
    - "stk_rewards"
    - "pledge_detail"
    - "fina_audit"
    - "stk_holdertrade"
  daily:
    - "daily"
    - "daily_basic"
    - "adj_factor"
    - "moneyflow"
  financial:
    - "income"
    - "balancesheet"
    - "cashflow"
    - "fina_indicator"
    - "fina_audit"
    - "fina_mainbz"
  basic:
    - "stock_basic"
    - "trade_cal"
    - "namechange"
    - "stock_company"
```

### 接口配置 (`config/interfaces/*.yaml`)

每个接口都有自己的 YAML 配置，定义：
- API 元数据（名称、描述、权限）
- 请求参数和验证规则
- 分页策略和参数
- 输出 schema 和主键
- 速率限制和缓存设置
- 重复检测配置

示例接口配置：

```yaml
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 500  # [修改] 提高速率限制
  query_limit: 5000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  start_date:
    type: string
    required: true
    description: "开始日期"
  end_date:
    type: string
    required: true
    description: "结束日期"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    open: {type: float, required: false}
    high: {type: float, required: false}
    low: {type: float, required: false}
    close: {type: float, required: false}
    pre_close: {type: float, required: false}
    change: {type: float, required: false}
    pct_chg: {type: float, required: false}
    vol: {type: float, required: false}
    amount: {type: float, required: false}

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
```

## 接口组

App4 将接口组织成逻辑组以便于管理：

- **daily**: 日线市场数据（daily, daily_basic, adj_factor, moneyflow）
- **financial**: 财务报表（income, balancesheet, cashflow, fina_indicator, fina_audit, fina_mainbz）
- **holders**: 股东数据（top10_holders, top10_floatholders, stk_rewards, pledge_detail, stk_holdertrade）
- **market**: 市场指标（moneyflow, cyq_chips, stk_factor, moneyflow_ind_dc, moneyflow_cnt_ths）
- **basic**: 基本信息（stock_basic, trade_cal, namechange, stock_company）
- **tscode_historical**: 需要股票代码循环的接口（stk_rewards, top10_holders, pledge_detail, fina_audit, top10_floatholders, stk_holdertrade）

## 主要特性

1. **零代码接口添加**: 通过简单创建 YAML 配置文件添加新接口
2. **声明式配置**: 所有接口行为在配置文件中定义
3. **灵活分页**: 多种分页模式处理不同的 API 行为
4. **异步存储**: 非阻塞 I/O 操作以提高吞吐量
5. **智能缓存**: 交易日历派生策略优化缓存利用率
6. **性能监控**: 关键指标实时跟踪与警报
7. **向后兼容**: 保持与旧 CLI 参数的兼容性
8. **高并发**: 基于线程池的并发处理
9. **速率限制保护**: 令牌桶算法防止 API 限流
10. **类型安全**: 全面的参数验证和类型检查
11. **覆盖率管理**: 智能重复检测避免冗余下载
12. **内存高效缓存**: 频繁访问数据的运行时缓存
13. **数据集模式存储**: 使用 Parquet 数据集格式的高效存储
14. **季度和周期性范围分页**: 支持财务数据的 period_range、quarterly_range 和 periodic_range 分页模式
15. **券商推荐处理**: 对 broker_recommend 接口的特殊处理，使用基于月份的请求

## 使用方法

### 环境设置
```bash
# 安装依赖
pip install -r requirements.txt

# 在 .env 文件中设置环境变量：
# tushare_token=your_token
# tushare_points=your_points
# tushare2_token=secondary_token (可选)
# tushare2_points=secondary_points (可选)
```

### 运行系统
```bash
# 基本用法 - 下载所有可用接口
python main.py --start_date 20230101 --end_date 20231231

# 下载特定接口
python main.py --start_date 20230101 --end_date 20231231 --interface daily

# 下载接口组
python main.py --start_date 20230101 --end_date 20231231 --group financial

# 设置并发级别
python main.py --concurrency 4  # [修改] 默认并发数从 8 改为 4

# 设置日志级别
python main.py --log-level DEBUG

# 列出可用接口
python main.py --list-interfaces

# 检查接口配置
python main.py --show-config daily

# 指定 ts_code 下载
python main.py --start_date 20230101 --end_date 20231231 --interface daily --ts_code 000001.SZ

# 下载股票循环接口（股东数据）
python main.py --holders-data

# 仅下载 pro_bar 数据
python main.py --pro-bar-only

# 为股票循环接口下载完整历史数据
python main.py --tscode-historical
```

## App4 架构优势

- **零代码扩展性**: 无需编写代码即可添加接口
- **声明式配置**: 所有行为在 YAML 文件中定义
- **类型安全**: 全面的参数验证
- **高性能**: Polars 用于数据处理，异步 I/O
- **智能缓存**: 交易日历派生策略
- **生产就绪**: 全面的错误处理和监控
- **覆盖率管理**: 通过重复检测避免冗余下载
- **内存高效**: 频繁访问数据的运行时缓存
- **数据集存储**: 使用 Parquet 数据集格式的高效数据访问