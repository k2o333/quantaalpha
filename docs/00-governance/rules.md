# aspipe_v4 开发规则

## 项目概述

aspipe_v4 是一个配置驱动的金融数据下载系统，从 TuShare API 下载股票数据并存储为 Parquet 格式。

## 架构原则

### 1. 配置驱动优先

- **零代码添加接口**：新接口通过 YAML 配置添加，无需修改代码
- **声明式配置**：所有接口行为定义在 `app4/config/interfaces/*.yaml` 中
- **配置验证**：启动时通过 `ConfigLoader.validate_config()` 验证配置完整性

### 2. 目录结构约定

```
aspipe_v4/
├── app4/                      # 核心应用目录
│   ├── main.py                # CLI 入口
│   ├── core/                  # 核心组件
│   │   ├── config_loader.py   # 配置加载器
│   │   ├── downloader.py      # 通用下载引擎
│   │   ├── processor.py       # 数据处理器
│   │   ├── storage.py         # 异步存储管理器
│   │   ├── scheduler.py       # 任务调度器
│   │   ├── schema_manager.py  # Schema 管理器
│   │   ├── coverage_manager.py# 覆盖率管理器
│   │   ├── dedup.py           # 去重模块
│   │   ├── pagination.py      # 分页组合器
│   │   ├── pagination_executor.py
│   │   ├── params_builder.py  # 参数构建器
│   │   └── constants.py       # 常量定义
│   ├── config/
│   │   ├── settings.yaml      # 全局配置
│   │   └── interfaces/        # 接口配置 (40+ YAML)
│   └── update/                # 增量更新模块
├── data/                      # 数据存储目录
├── cache/                     # 缓存目录
├── log/                       # 日志目录
└── test/                      # 测试目录
```

### 3. 核心组件职责

| 组件 | 职责 | 关键方法 |
|------|------|----------|
| `ConfigLoader` | 加载 YAML 配置，环境变量替换 | `_load_global_config()`, `_load_interface_configs()` |
| `GenericDownloader` | API 请求引擎，分页执行 | `download()`, `_execute_pagination()`, `_make_request()` |
| `DataProcessor` | 数据类型转换，去重，验证 | `process_data()`, `_handle_primary_keys()`, `validate_data()` |
| `StorageManager` | 异步写入，buffer 管理 | `save_data()`, `add_to_buffer()`, `_process_worker()` |
| `TaskScheduler` | 线程池管理，限流 | `submit_tasks()`, `start()` |
| `SchemaManager` | Schema 推断，衍生字段应用 | `create_dataframe_safe()`, `apply_derived_fields()` |
| `CoverageManager` | 重复数据检测，缺口检测 | `should_skip()`, `detect_gaps()` |
| `PaginationComposer` | 分页参数组合 | `compose()`, `_apply_time_range()`, `_apply_stock_loop()` |

## 开发规范

### 1. 文档管理

所有文档管理相关规范参见 [doc-rules.md](./doc-rules.md)，包括：
- 文档类型定义（治理文档、模块文档、变更文档等）
- 目录结构约定
- 命名规则
- AI/Codex 使用规则

### 2. 临时文件目录

开发过程中产生的临时文件统一放置在项目根目录的 `.tmp/` 目录下，包括但不限于：
- 调试输出文件
- 临时测试数据
- 实验性脚本输出
- 其他开发时产生的非正式产物

`.tmp/` 目录应添加到 `.gitignore`，不应提交到版本控制。

### 3. 添加新接口

**步骤：**

1. 在 `app4/config/interfaces/` 创建 `<interface_name>.yaml`
2. 配置必需字段：
   - `name`, `api_name`, `description`
   - `permissions.min_points` (积分要求)
   - `pagination` (分页配置)
   - `output.primary_key` (主键定义)
   - `fields` (字段类型定义)
   - `derived_fields` (衍生字段，可选)

**示例配置：**
```yaml
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 500

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
  start_date:
    type: string
    required: true
  end_date:
    type: string
    required: true

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]

dedup_enabled: true

fields:
  ts_code: string
  trade_date: string
  close: Float64
  volume: Float64
```

### 2. 分页模式选择

| 模式 | 适用场景 | 配置示例 |
|------|----------|----------|
| `date_range` | 按日期范围查询 | `window_size_days: 365` |
| `period_range` | 财务报告期数据 | `periods_per_batch: 1` |
| `stock_loop` | 需要遍历股票 | 配合 `date_range` 使用 |
| `offset` | 传统分页 | `limit: 5000` |
| `quarterly_range` | 季度数据 | `quarters_per_batch: 4` |

### 3. 日期参数规范

**日期锚定参数 (`is_date_anchor`)：**
- 用于标识接口使用的日期字段
- 一个接口只能有一个日期锚定参数
- `start_date`/`end_date` 如未配置 `is_date_anchor: true`，则作为普通参数透传

**示例：**
```yaml
parameters:
  ann_date:
    type: string
    is_date_anchor: true  # 这是日期锚定参数
  end_date:
    type: string
    is_date_anchor: false  # 这是日期范围参数
```

### 4. 数据类型定义

**支持的类型映射：**
```yaml
fields:
  ts_code: string      # 字符串
  close: Float64       # 浮点数
  volume: Int64        # 整数
  is_open: Boolean     # 布尔值
  ann_date: string     # 日期 (保持字符串格式)

derived_fields:
  ann_date_dt:         # 衍生日期类型字段
    source: ann_date
    type: date
    format: '%Y%m%d'
```

### 5. 去重配置

```yaml
output:
  primary_key: ["ts_code", "trade_date"]  # 必须定义
  sort_by: ["trade_date"]

dedup_enabled: true  # 启用去重
```

**去重策略：**
- `first` - 保留第一次出现
- `last` - 保留最后一次出现
- `latest_date` - 保留日期最新的记录

## 代码规范

### 1. 日志级别使用

| 级别 | 使用场景 |
|------|----------|
| `DEBUG` | 详细调试信息 |
| `INFO` | 正常操作信息（下载记录数，去重统计） |
| `WARNING` | 可恢复的异常（去重警告，跳过记录） |
| `ERROR` | 错误但可继续（单接口失败） |
| `CRITICAL` | 严重错误（系统无法继续） |

### 2. 异常处理原则

```python
# 下载单只股票时，捕获异常返回空列表，不影响其他股票
try:
    stock_data = self._execute_paginated_download(...)
    return stock_data or []
except Exception as e:
    logger.error(f"Error downloading stock {ts_code}: {str(e)}")
    return []  # 返回空列表，让其他股票继续下载
```

### 3. 线程安全

- 使用 `threading.RLock()` 保护共享状态
- 缓存操作必须加锁：`with self._cache_lock:`
- Buffer 操作使用 `buffer_lock` 保护

### 4. 异步写入模式

```python
# 推荐：使用异步写入
storage_manager.save_data(interface_name, data, async_write=True)

# 同步写入（仅用于初始化数据）
storage_manager.save_data(interface_name, data, async_write=False)
```

## 常量定义 (`app4/core/constants.py`)

```python
DEFAULT_START_DATE = "20230101"      # 默认起始日期
HISTORICAL_START_DATE = "19900101"   # 全历史数据起始日期
DEFAULT_STOCK_START_DATE = "20050101" # 股票数据默认起始日期
MIN_TRADE_CAL_RECORDS = 5000         # 最小交易日历记录数
STORAGE_BUFFER_THRESHOLD = 5000      # 存储 buffer 刷新阈值
```

## 全局配置 (`app4/config/settings.yaml`)

### 关键配置项

```yaml
concurrency:
  max_workers: 4          # 并发线程数
  max_queue_size: 1000    # 任务队列大小

request:
  rate_limit: 250         # 每秒请求数限制
  max_retries: 3
  retry_delay: 1.0
  jitter_min: 0.05        # 随机延迟最小值
  jitter_max: 0.15        # 随机延迟最大值

storage:
  base_dir: "/path/to/data"
  batch_size: 10000       # 批量写入大小
  small_batch_threshold: 100  # 小批量立即处理阈值

gap_detection:
  enabled: true
  min_gap_size: 3         # 最小缺口大小（交易日数）
  max_gaps: 50            # 最大缺口数量
```

## 接口分组 (`settings.yaml` - `groups`)

| 组名 | 描述 | 包含接口 |
|------|------|----------|
| `tscode_historical` | 需要股票循环的历史数据 | stk_rewards, income_vip, balancesheet_vip... |
| `holders` | 股东数据 | top10_holders, pledge_detail... |
| `financial_vip` | VIP 财务数据 | income_vip, balancesheet_vip, cashflow_vip... |
| `daily` | 日线数据 | daily, daily_basic, pro_bar... |
| `moneyflow` | 资金流向 | moneyflow, moneyflow_ths... |
| `features` | 特色指标 | cyq_chips, cyq_perf, stk_factor... |

## 命令行参数

```bash
# 基础用法
python app4/main.py --start_date 20230101 --end_date 20231231

# 下载指定接口
python app4/main.py --interface daily

# 下载接口组
python app4/main.py --group financial_vip

# 增量更新模式
python app4/main.py --update

# 指定股票代码
python app4/main.py --interface daily --ts_code 000001.SZ

# 全历史数据下载
python app4/main.py --tscode-historical

# 并发控制
python app4/main.py --concurrency 4
```

## 数据流向

```
CLI (main.py)
    ↓
ConfigLoader (加载配置)
    ↓
CacheWarmer (预热交易日历/股票列表)
    ↓
GenericDownloader
    ├── PaginationComposer (生成参数流)
    ├── _make_request (API 请求)
    └── CoverageManager (覆盖率检查)
    ↓
DataProcessor (处理/去重/验证)
    ↓
StorageManager (异步写入)
    ├── process_queue (处理队列)
    └── data_queue (写入队列)
    ↓
Parquet Dataset (分区存储)
```

## 性能优化要点

1. **并发控制**：`max_workers=4`，避免超过 API 限制
2. **Buffer 机制**：数据累积到阈值后批量处理
3. **内存缓存**：LRU Cache 缓存交易日历/股票列表
4. **缺口检测**：只下载缺失的数据范围
5. **原子写入**：先写临时文件，再 rename

## 调试技巧

1. **启用详细日志**：`--log-level DEBUG`
2. **单接口测试**：`--interface <name>`
3. **预览模式**：`--update-dry-run`
4. **性能报告**：查看 `log/reports/performance_report_*.md`

## 常见问题

**Q: 如何确定接口的分页模式？**
A: 查看 TuShare API 文档，根据返回数据特点选择：
- 有明确日期范围 → `date_range`
- 按报告期发布 → `period_range`
- 需要遍历股票 → 添加 `stock_loop` 维度

**Q: 如何处理类型转换错误？**
A: `SchemaManager` 会自动处理，确保 `fields` 配置正确

**Q: 如何跳过已下载的数据？**
A: 使用 `--update` 模式，自动启用缺口检测

## 测试命令

```bash
# 配置验证
python -c "from app4.core.config_loader import ConfigLoader; c = ConfigLoader(); print(c.validate_config())"

# 单接口测试
python app4/main.py --interface daily --start_date 20231201 --end_date 20231231

# 运行测试
python -m pytest test/test_app4_*.py -v
```
