# aspipe_v4 - 配置驱动架构

## 概述

aspipe_v4 是一个现代化的、配置驱动的金融数据管道系统，专为高效下载和处理 TuShare Pro 金融数据而设计。系统采用声明式配置，实现零代码添加新接口的能力。

## 核心特性

- **配置驱动**：所有接口行为通过 YAML 配置文件定义，无需修改代码即可添加新接口
- **多种分页模式**：支持 offset、date_range、reverse_date_range、stock_loop、period_range、quarterly_range 等多种分页策略
- **智能增量更新**：支持缺口检测、断点续传、覆盖率检查，避免重复下载
- **高性能处理**：使用 Polars 进行数据处理和去重，多线程并发下载
- **异步存储**：生产者-消费者模式的异步数据持久化
- **内存缓存**：LRU 缓存机制提升重复查询性能
- **数据去重**：基于主键的统一去重机制，支持内部和外部去重

## 架构组件

```
app4/
├── main.py                    # CLI 入口点
├── core/                      # 核心组件
│   ├── config_loader.py       # YAML 配置加载器
│   ├── downloader.py          # 通用下载引擎
│   ├── pagination.py          # 分页参数组合器
│   ├── pagination_executor.py # 分页执行器
│   ├── scheduler.py           # 任务调度器（含限流器）
│   ├── storage.py             # 异步存储管理器
│   ├── processor.py           # 数据处理器（Polars）
│   ├── coverage_manager.py    # 覆盖率/去重管理器
│   ├── dedup.py               # 去重模块
│   ├── schema_manager.py      # Schema 管理器
│   ├── cache_warmer.py        # 缓存预热器
│   ├── performance_monitor.py # 性能监控器
│   └── constants.py           # 常量定义
├── update/                    # 增量更新模块
│   ├── update_manager.py      # 更新管理器
│   ├── interface_selector.py  # 接口选择器
│   ├── date_calculator.py     # 日期计算器
│   ├── checkpoint_manager.py  # 断点管理器
│   ├── update_reporter.py     # 更新报告生成器
│   └── models.py              # 数据模型
└── config/                    # 配置文件
    ├── settings.yaml          # 全局配置
    └── interfaces/            # 接口配置（40+ 接口）
```

## 分页模式

系统支持多种分页模式，通过接口配置文件的 `pagination.mode` 指定：

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| `offset` | 偏移量分页 | 股票列表、基础数据 |
| `date_range` | 日期范围分页 | 日线数据、行情数据 |
| `reverse_date_range` | 反向日期范围（从新到旧） | 资金流向、实时数据 |
| `stock_loop` | 股票代码循环 | 股东数据、财务数据 |
| `period_range` | 报告期范围 | 财务报表数据 |
| `quarterly_range` | 季度范围 | 季报、年报数据 |
| `date_range_daily` | 每日范围 | 逐日数据下载 |

### 反向日期范围分页 (reverse_date_range)

特性：
- 从最近日期开始下载，优先获取最新数据
- 支持可配置的窗口大小（默认 30 天）
- 连续 N 天无数据时自动停止（默认 90 天）
- 支持覆盖率检查，跳过已下载窗口

```yaml
pagination:
  enabled: true
  mode: reverse_date_range
  window_size_days: 30
  empty_threshold_days: 90
```

## 配置系统

### 全局配置 (settings.yaml)

```yaml
app:
  name: "aspipe_v4"
  version: "4.0.0"

tushare:
  token: "${TUSHARE_TOKEN}"    # 从环境变量读取
  base_url: "http://api.tushare.pro"

concurrency:
  max_workers: 4
  max_queue_size: 1000

storage:
  base_dir: "../data"
  format: "parquet"
  batch_size: 10000

# 性能监控
performance:
  enabled: true
  auto_generate_report: true
  output_format: "markdown"

# 缺口检测
gap_detection:
  enabled: true
  min_gap_size: 3
  max_gaps: 50

# 接口分组
groups:
  daily:
    - daily
    - daily_basic
    - moneyflow
  financial_vip:
    - income_vip
    - balancesheet_vip
    - cashflow_vip
```

### 接口配置示例

```yaml
name: moneyflow
api_name: moneyflow
description: 个股资金流向

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 6000

pagination:
  enabled: true
  mode: reverse_date_range
  window_size_days: 1
  empty_threshold_days: 90

parameters:
  ts_code:
    type: string
    required: false
    description: "股票代码"
  start_date:
    type: string
    required: false
    description: "开始日期"
  end_date:
    type: string
    required: false
    description: "结束日期"

output:
  primary_key: ["ts_code", "trade_date"]  # 去重主键
  sort_by: ["trade_date"]

# 衍生字段（自动类型转换）
derived_fields:
  trade_date_dt:
    source: trade_date
    type: date
    format: '%Y%m%d'
    description: "日期类型的trade_date"
```

## 使用方式

### 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export TUSHARE_TOKEN="your_token_here"
export TUSHARE_POINTS="2000"
```

### 基础下载

```bash
# 下载所有可用接口
python app4/main.py --start_date 20230101 --end_date 20231231

# 下载指定接口
python app4/main.py --interface moneyflow --start_date 20230101 --end_date 20231231

# 下载指定分组
python app4/main.py --group financial_vip --start_date 20230101 --end_date 20231231

# 下载指定股票
python app4/main.py --interface moneyflow --ts_code 000001.SZ
```

### 增量更新模式（推荐）

```bash
# 全量增量更新
python app4/main.py --update

# 更新指定接口
python app4/main.py --update --update-interface moneyflow --update-interface daily

# 更新指定分组
python app4/main.py --update --update-group financial_vip

# 强制更新（忽略已有数据）
python app4/main.py --update --update-force

# 预览模式（不实际执行）
python app4/main.py --update --update-dry-run
```

### 高级功能

```bash
# 下载股东数据（需要股票循环）
python app4/main.py --holders-data

# 下载全历史数据（1990年至今）
python app4/main.py --tscode-historical

# 设置并发数
python app4/main.py --concurrency 8

# 调试日志
python app4/main.py --log-level DEBUG
```

## 增量更新机制

### 1. 覆盖率检测

系统自动检测已有数据的覆盖范围，避免重复下载：

- **日期范围覆盖**：检查目标日期范围内的交易日是否已存在
- **股票级别覆盖**：为每只股票检测数据缺口
- **缺口检测**：自动识别数据缺失的时间段并仅下载缺口

### 2. 断点续传

支持更新过程的断点续传：

- 自动保存更新进度到检查点文件
- 异常中断后可恢复未完成接口
- 支持按接口粒度的断点记录

### 3. 更新流程

```
1. 选择接口 → 2. 计算日期范围 → 3. 检测覆盖率/缺口
→ 4. 执行下载 → 5. 数据去重 → 6. 保存数据
→ 7. 更新检查点 → 8. 生成报告
```

## 数据去重机制

### 主键去重

系统基于配置的 `primary_key` 进行去重：

```yaml
output:
  primary_key: ["ts_code", "trade_date"]
```

### 去重流程

1. **批次内去重**：同一批次数据按主键去重，保留最新记录
2. **历史数据去重**：与已有数据对比，过滤重复记录
3. **确定性去重**：基于 `_update_time` 字段确保保留最新数据

## 性能监控

系统自动收集性能指标：

- 请求时间（P50/P90/P99）
- 记录数统计
- 成功率
- 重试次数
- 限流等待时间

生成报告位置：`log/reports/performance_report_YYYYMMDD_HHMMSS.md`

## 注意事项

### 接口特殊处理

1. **pledge_stat**：此接口不支持增量更新，建议全量下载
2. **dividend**：该接口在大量交易日记录为0，日期范围重叠时会反复下载
3. **stock_basic/trade_cal**：基础数据，建议单独更新

### 积分限制

不同接口需要不同的 TuShare 积分：

- **120+ 分**：基础接口（trade_cal 等）
- **2000+ 分**：标准接口（daily、moneyflow、财务数据等）
- **5000+ 分**：高级接口（cyq_chips、stk_factor 等）
- **8000+ 分**：专业接口（VIP财务数据等）

系统会根据 `TUSHARE_POINTS` 环境变量自动过滤可用接口。

### 存储格式

数据以 Parquet Dataset 格式存储：

```
data/
├── moneyflow/
│   ├── moneyflow_20230101_20230131_12345678.parquet
│   └── moneyflow_20230201_20230228_87654321.parquet
├── daily/
│   └── ...
└── ...
```

每个文件包含时间戳和 UUID，支持原子写入和确定性去重。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进项目。
