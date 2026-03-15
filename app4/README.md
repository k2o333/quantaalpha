# App4 - 配置驱动的 TuShare 数据管道

## 概述

App4 是一个现代化的、配置驱动的金融数据管道系统，专为高效下载和处理 TuShare Pro 金融数据而设计。系统采用声明式配置，实现零代码添加新接口的能力。

## 核心特性

- **配置驱动**：所有接口行为通过 YAML 配置文件定义，无需修改代码即可添加新接口
- **多种分页模式**：支持 offset、date_range、reverse_date_range、stock_loop、period_range、type_split 等分页策略
- **智能增量更新**：支持缺口检测、断点续传、覆盖率检查，避免重复下载
- **高性能处理**：使用 Polars 进行数据处理和去重，多线程并发下载
- **异步存储**：生产者-消费者模式的异步数据持久化
- **内存缓存**：LRU 缓存机制提升重复查询性能
- **性能监控**：自动生成性能报告，支持 Markdown/JSON/HTML 格式

## 项目结构

```
app4/
├── main.py                    # CLI 入口点
├── core/                      # 核心组件 (16个模块)
│   ├── config_loader.py       # YAML 配置加载器
│   ├── downloader.py          # 通用下载引擎
│   ├── pagination.py          # 分页参数组合器
│   ├── pagination_executor.py # 分页执行器
│   ├── params_builder.py      # 参数构建器
│   ├── scheduler.py           # 任务调度器（含限流器）
│   ├── storage.py             # 异步存储管理器
│   ├── processor.py           # 数据处理器（Polars）
│   ├── coverage_manager.py    # 覆盖率/去重管理器
│   ├── dedup.py               # 去重模块
│   ├── schema_manager.py      # Schema 管理器
│   ├── cache_warmer.py        # 缓存预热器
│   ├── performance_monitor.py # 性能监控器
│   ├── date_utils.py          # 日期工具
│   ├── context.py             # 上下文管理
│   └── constants.py           # 常量定义
├── update/                    # 增量更新模块
│   ├── update_manager.py      # 更新管理器
│   ├── interface_selector.py  # 接口选择器
│   ├── date_calculator.py     # 日期计算器
│   ├── checkpoint_manager.py  # 断点管理器
│   ├── update_reporter.py     # 更新报告生成器
│   ├── models.py              # 数据模型
│   └── README.md              # 更新模块使用指南
├── config/                    # 配置文件
│   ├── settings.yaml          # 全局配置
│   └── interfaces/            # 接口配置 (43个接口)
├── tests/                     # 测试文件
├── factor/                    # 因子模块 (预留)
├── utils/                     # 工具模块
│   └── config_converter.py    # 配置转换器
└── cache/                     # 缓存目录
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
| `type_split` | 类型分割 | 沪深港通数据 |
| `no_pagination` | 无分页 | 一次性获取数据 |

## 使用方式

### 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
export TUSHARE_TOKEN="your_token_here"
export TUSHARE_POINTS="2000"
```

### 增量更新模式（推荐）

```bash
# 更新所有接口
python app4/main.py --update

# 更新指定接口
python app4/main.py --update --update-interface moneyflow --update-interface daily

# 更新指定分组
python app4/main.py --update --update-group financial_vip

# 强制更新（忽略已有数据）
python app4/main.py --update --update-force

# 预览模式（不实际执行）
python app4/main.py --update --update-dry-run

# 指定股票代码更新
python app4/main.py --update --ts_code 000001.SZ
```

### 标准下载模式

```bash
# 下载指定接口
python app4/main.py --interface moneyflow --start_date 20230101 --end_date 20231231

# 下载指定分组
python app4/main.py --group financial_vip --start_date 20230101 --end_date 20231231

# 下载股东数据
python app4/main.py --holders-data

# 下载全历史数据（1990年至今）
python app4/main.py --tscode-historical
```

### 高级选项

```bash
# 设置并发数
python app4/main.py --update --concurrency 8

# 调试日志
python app4/main.py --update --log-level DEBUG

# 禁用性能报告
python app4/main.py --update --no-performance-report

# 指定性能报告输出目录
python app4/main.py --update --performance-report-dir ./reports
```

## 配置系统

### 接口分组 (settings.yaml)

```yaml
groups:
  # 股票循环模式接口组
  stock_loop:
    - stk_rewards
    - cyq_chips
    - fina_audit
    - pledge_detail
  
  # 报告期范围模式接口组
  period_range:
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    # ...
  
  # 反向日期范围模式接口组
  reverse_date_range:
    - daily_basic
    - moneyflow
    - block_trade
    # ...
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
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
```

## 增量更新机制

### 断点续传

- 自动保存更新进度到检查点文件 (`data/.update_checkpoint.json`)
- 异常中断后可恢复未完成接口
- 支持按接口粒度的断点记录

### 更新流程

```
1. 选择接口 → 2. 计算日期范围 → 3. 检测覆盖率/缺口
→ 4. 执行下载 → 5. 数据去重 → 6. 保存数据
→ 7. 更新检查点 → 8. 生成报告
```

### 更新报告

更新完成后自动生成报告，位于 `log/update_reports/` 目录，包含：
- 成功/失败/跳过的接口统计
- 各接口的记录数和耗时
- 错误详情

## 性能监控

系统自动收集性能指标并生成报告：

- 请求时间（P50/P90/P99）
- 记录数统计
- 成功率
- 重试次数
- 限流等待时间

报告位置：`log/reports/performance_report_YYYYMMDD_HHMMSS.md`

## 已配置接口 (43个)

| 类别 | 接口 |
|------|------|
| 行情数据 | daily, daily_basic, moneyflow, moneyflow_*, block_trade, stk_factor_pro |
| 财务数据 | income_vip, balancesheet_vip, cashflow_vip, fina_indicator_vip, fina_mainbz_vip |
| 预测数据 | forecast_vip, express_vip, disclosure_date |
| 股东数据 | top10_holders, top10_floatholders, stk_rewards, stk_holdertrade |
| 质押数据 | pledge_stat, pledge_detail |
| 基础数据 | stock_basic, stock_company, trade_cal, namechange, new_share |
| 其他 | dividend, suspend_d, stock_st, repurchase, cyq_chips, cyq_perf, ... |

## 注意事项

### 积分限制

不同接口需要不同的 TuShare 积分：

- **120+ 分**：基础接口（trade_cal, stock_basic 等）
- **2000+ 分**：标准接口（daily, moneyflow, 财务数据等）
- **5000+ 分**：高级接口（cyq_chips, stk_factor_pro 等）
- **8000+ 分**：专业接口

系统会根据 `TUSHARE_POINTS` 环境变量自动过滤可用接口。

### 存储格式

数据以 Parquet 格式存储，支持：
- 列式存储，高效压缩
- 按主键去重
- 支持增量追加

### 特殊接口

- `pledge_stat`：不支持增量更新，建议全量下载
- `stock_basic/trade_cal`：基础数据，更新频率低
- `cyq_chips`：需要 5000+ 积分，按股票循环下载

## 测试

```bash
# 运行测试
cd app4
pytest tests/
```

## 相关文档

- [增量更新模块使用指南](update/README.md)
- [接口配置规范](../docs/02-modules/app4.md)