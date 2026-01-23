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
- 保留 API 返回的原始数据格式，确保数据完整性
- 通过配置化的衍生字段提供优化类型（如日期类型、布尔类型等）
- 分离原始数据和转化字段，实现灵活的数据访问模式
- 为高频金融数据接口优化的 schema

### 8. 覆盖率管理器 (`core/coverage_manager.py`)
- 实现重复检测以避免冗余下载
- 支持多种策略：日期范围、期间和股票基础检测
- 使用内存缓存进行高效覆盖率检查
- 兼容新架构中的原始字段和衍生字段

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
- 输出配置（主键、排序字段）
- 衍生字段配置（用于类型转换和优化）
- 速率限制和缓存设置
- 去重配置（统一的 primary_key + dedup_enabled 方法）

**新的配置格式（统一的去重配置方法）：**

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
  # columns 部分已移除，原始数据保持API返回的原样

# 统一的去重配置 - 新方法
# 如果 output.primary_key 存在且 dedup_enabled 为 true，则自动启用去重
dedup_enabled: true  # 统一控制是否启用去重功能

# 旧的重复检测配置已被弃用，保留用于向后兼容
# duplicate_detection:  # 已弃用
#   enabled: true
#   date_column: "trade_date"
#   threshold: 0.95

# 新增：衍生字段配置
derived_fields:
  trade_date_dt:    # 衍生字段名称
    source: trade_date    # 源字段
    type: date    # 转换类型
    format: '%Y%m%d'    # 日期格式
    description: "日期类型的trade_date"
  # 可以添加更多衍生字段...
```

**从旧格式迁移到新格式：**

旧格式：
```yaml
duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
```

新格式：
```yaml
dedup_enabled: true  # 仅此一项即可启用去重
```

**新统一方法的优势：**
- 更简洁：只需 `primary_key` 和 `dedup_enabled: true` 即可实现去重
- 更统一：所有去重逻辑基于 primary_key 配置，无需额外的 duplicate_detection 配置
- 更直观：去重行为与 primary_key 密切相关，统一管理
- 向后兼容：保留旧的 duplicate_detection 配置格式，但建议使用新的统一方法

## 接口组

App4 将接口组织成逻辑组以便于管理：

- **tscode_historical**: 需要股票代码循环的接口（默认起始日期19900101）
  - 包括: stk_rewards, income_vip, balancesheet_vip, cashflow_vip, forecast_vip, express_vip, fina_indicator_vip, fina_audit, fina_mainbz_vip, disclosure_date, top10_floatholders, top10_holders, pledge_stat, pledge_detail, dividend, stk_factor, stk_factor_pro
- **holders**: 股东数据
  - 包括: top10_holders, top10_floatholders, stk_holdertrade, pledge_detail, pledge_stat, share_float, stk_rewards, stk_managers, stk_surv
- **financial_vip**: VIP财务数据（季度数据）
  - 包括: income_vip, balancesheet_vip, cashflow_vip, fina_indicator_vip, fina_mainbz_vip, express_vip, forecast_vip
- **financial_basic**: 基础财务数据
  - 包括: income, balancesheet, cashflow, fina_indicator, fina_mainbz, fina_audit, express, forecast
- **daily**: 日线市场数据
  - 包括: daily, daily_basic, pro_bar, trade_cal, block_trade, bak_daily, bak_basic, suspend_d
- **moneyflow**: 资金流向数据
  - 包括: moneyflow, moneyflow_ths, moneyflow_dc, moneyflow_ind_ths, moneyflow_ind_dc, moneyflow_cnt_ths, moneyflow_mkt_dc
- **features**: 特色指标数据
  - 包括: cyq_chips, cyq_perf, stk_factor, stk_factor_pro, stk_premarket
- **company_info**: 公司基本信息
  - 包括: stock_basic, stock_company, namechange, new_share, disclosure_date
- **others**: 其他数据
  - 包括: repurchase, stock_hsgt, stock_st, suspend_d, bak_basic, bak_daily, report_rc, broker_recommend, dividend, share_float, stk_holdertrade, stk_managers, stk_surv

## 分页配置

### date_range模式
适用于按时间序列的数据，使用window_size_days控制单次请求的时间范围。

```yaml
pagination:
  enabled: true
  mode: date_range
  window_size_days: 365  # 每次请求1年的数据
```

### stock_loop模式
适用于需要按股票代码循环的数据，每个股票独立请求。

```yaml
pagination:
  enabled: true
  mode: stock_loop
  window_size_days: 3650  # 每个股票单次请求10年的数据
```

### periodic_range模式
适用于按固定周期（日、周、月、季、年）的数据。

```yaml
pagination:
  enabled: true
  mode: periodic_range
  period_type: quarter  # 支持: day, week, month, quarter, year
```

### offset模式
适用于使用offset/limit分页的数据。

```yaml
pagination:
  enabled: true
  mode: offset
  default_limit: 5000    # 默认每页数量
  limit_key: limit       # API的limit参数名
  offset_key: offset     # API的offset参数名
```

### 禁用分页
对于不需要分页的接口，显式禁用分页配置。

```yaml
pagination:
  enabled: false
```

**注意**: 当前配置中，`broker_recommend`和`namechange`接口已正确设置`pagination.enabled: false`。

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
14. **原始数据+衍生字段架构**: 保持原始API数据格式，通过配置化衍生字段提供优化类型
15. **季度和周期性范围分页**: 支持财务数据的 period_range、quarterly_range 和 periodic_range 分页模式
16. **券商推荐处理**: 对 broker_recommend 接口的特殊处理，使用基于月份的请求
17. **统一去重配置**: 通过 primary_key + dedup_enabled 的统一配置方式实现数据去重，简化配置并提高一致性

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
- **原始数据+衍生字段架构**: 保持原始API返回格式，通过配置化衍生字段提供优化类型
- **统一去重配置**: 通过 primary_key + dedup_enabled 的统一配置方式实现数据去重，简化配置并提高一致性
- **类型安全**: 全面的参数验证
- **高性能**: Polars 用于数据处理，异步 I/O
- **智能缓存**: 交易日历派生策略
- **生产就绪**: 全面的错误处理和监控
- **覆盖率管理**: 通过重复检测避免冗余下载
- **内存高效**: 频繁访问数据的运行时缓存
- **数据集存储**: 使用 Parquet 数据集格式的高效数据访问
- **查询性能优化**: 衍生字段（如布尔类型）显著提升Polars查询性能