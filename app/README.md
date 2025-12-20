# ASPipe v4 - 中国股市数据下载平台

## 项目简介

ASPipe v4 是一个基于 TuShare API 的中国股市数据自动化下载平台。该系统能够根据用户的 TuShare 积分级别自动下载所有可用的金融数据，并将其保存为高效的 Parquet 格式，便于后续的数据分析和处理。

## 核心特性

- 🚀 **积分自动适配**：根据 TuShare 积分级别自动下载所有可用数据
- 📊 **全面数据覆盖**：支持股票基本信息、日线数据、财务报表、股东信息、资金流向等
- 💾 **高效存储**：使用 Parquet 格式存储数据，支持快速查询和分析
- 🔄 **自动重试**：内置错误处理和重试机制，确保数据完整性
- 📝 **详细日志**：提供详细的中文日志，实时跟踪下载进度
- 🔧 **模块化设计**：清晰的模块划分，易于维护和扩展
- 🧠 **智能缓存**：股票列表智能缓存，避免重复下载
- 🔄 **令牌切换**：支持主备令牌自动切换，提高下载稳定性
- ⚡ **并发下载**：支持多线程并发下载，提高下载效率

## 安装与配置

### 1. 环境要求

- Python 3.7+
- 足够的磁盘空间（数据量较大）

### 2. 安装依赖

```bash
# 进入项目目录
cd /home/quan/testdata/aspipe_v4

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 配置 TuShare Token

编辑 `.env` 文件，配置您的 TuShare API Token：

```env
# 主要 Token（高积分）
tushare_token=YOUR_TUSHARE_TOKEN
tushare_points=YOUR_TUSHARE_POINTS
PROXY_URL=YOUR_PROXY_URL  # 可选

# 备用 Token（低积分）
tushare2_token=YOUR_SECONDARY_TOKEN
tushare2_points=YOUR_SECONDARY_POINTS
PROXY_URL2=  # 可选
```

> 💡 **提示**：您可以在 [TuShare 官网](https://tushare.pro/) 注册并获取 API Token。

## 使用方法

### 基本用法

```bash
# 使用默认参数下载数据（从 2023-01-01 到今天）
python app/main.py

# 指定日期范围下载数据
python app/main.py --start_date 20230101 --end_date 20231231

# 下载最近一年的数据
python app/main.py --start_date $(date -d "1 year ago" +%Y%m%d)
```

### 支持的数据类型

根据您的 TuShare 积分，系统会自动下载以下类型的数据：

#### 120 积分
- 新股列表 (new_share)
- 交易日历 (trade_cal)
- 股票曾用名 (namechange)

#### 2000 积分（包含所有 120 积分数据）
- **基础数据**：股票基本信息 (stock_basic)、上市公司基本信息 (stock_company)
- **日线数据**：日线行情 (daily)、每日指标 (daily_basic)
- **财务数据**：利润表 (income)、资产负债表 (balancesheet)、现金流量表 (cashflow)、财务指标 (fina_indicator)
- **股东信息**：前十大股东 (top10_holders)、前十大流通股东 (top10_floatholders)
- **公司事件**：分红送股 (dividend)、业绩预告 (forecast)、业绩快报 (express)
- **其他数据**：管理层薪酬 (stk_rewards)、上市公司管理层 (stk_managers)、个股资金流向 (moneyflow)、券商每月荐股 (broker_recommend)

#### 3000 积分（包含所有 2000 积分数据）
- **基础数据**：ST股票列表 (stock_st)
- **股东信息**：前十大流通股东 (top10_floatholders)
- **其他数据**：沪深港通股票列表 (stock_hsgt)

#### 5000 积分（包含所有 2000+3000 积分数据）
- **日线数据**：复权行情 (pro_bar)、备用行情 (bak_daily)、股票技术因子 (stk_factor)、股票技术面因子(专业版) (stk_factor_pro)
- **财务数据**：利润表VIP (income_vip)、资产负债表VIP (balancesheet_vip)、现金流量表VIP (cashflow_vip)、财务指标VIP (fina_indicator_vip)、主营业务构成 (fina_mainbz)、财务审计意见 (fina_audit)
- **市场结构**：每日筹码及胜率 (cyq_perf)、每日筹码分布 (cyq_chips)
- **资金流向**：个股资金流向(东财) (moneyflow_dc)、个股资金流向(同花顺) (moneyflow_ths)、行业/概念资金流向（东财）(moneyflow_ind_dc)、大盘资金流向（东财）(moneyflow_mkt_dc)、概念板块资金流向（同花顺）(moneyflow_cnt_ths)、行业板块资金流向（同花顺）(moneyflow_ind_ths)
- **股东信息**：股权质押统计 (pledge_stat)、股权质押明细 (pledge_detail)、股票回购 (repurchase)、限售股解禁 (share_float)、大宗交易 (block_trade)、股东增减持 (stk_holdertrade)
- **研究数据**：机构调研表 (stk_surv)、卖方盈利预测数据 (report_rc)、券商每月荐股 (broker_recommend)
- **公司事件**：每日停复牌信息 (suspend_d)
- **其他数据**：财报披露计划 (disclosure_date)

## 项目结构

```
aspipe_v4/app/
├── main.py                      # 主入口程序
├── config.py                    # 配置管理
├── tushare_api.py              # TuShare API 集成
├── data_storage.py             # 数据存储管理
├── date_range_downloader.py    # 日期范围下载器
├── score_based_downloader.py   # 积分基础下载器
├── enhanced_main_downloader.py # 增强主下载器
├── error_handler.py            # 错误处理和重试
├── score_config.py             # 积分配置定义
├── download_config.py          # 下载配置
├── stock_list_manager.py       # 股票列表管理器（避免重复下载）
├── interfaces/                 # 数据接口模块
│   ├── __init__.py
│   ├── base.py                 # 基础接口类
│   ├── basic_data.py           # 基础数据接口
│   ├── daily_data.py           # 日线数据接口
│   ├── financial_data.py       # 财务数据接口
│   ├── holders_data.py         # 股东信息接口
│   ├── market_flow.py          # 市场资金流向接口
│   ├── technical_factors.py    # 技术因子接口
│   ├── market_structure.py     # 市场结构接口
│   ├── research_data.py        # 研究数据接口
│   ├── cyq_chips.py            # 筹码分布接口
│   └── market_structure/       # 市场结构子模块
├── utils/                      # 工具函数
│   └── date_utils.py           # 日期处理工具
└── cache/                      # 缓存目录
```

## 配置文件

系统支持通过 `download_config.py` 文件控制哪些数据接口被下载。您可以修改此文件来启用或禁用特定的数据接口：

```python
# 下载配置文件
# true表示下载，false表示不下载
DOWNLOAD_CONFIG = {
    # 设置为false的接口（不下载）
    'moneyflow_ths': False,
    'moneyflow_cnt_ths': False,
    'moneyflow_ind_ths': False,
    'broker_recommend': False,
    'report_rc': False,
    'cyq_chips': False,  # 暂时禁用：cyq_chips接口因性能问题已重构优化

    # 设置为true的接口（下载）
    'daily': True,
    'daily_basic': True,
    'moneyflow': True,
    'moneyflow_dc': True,
    'moneyflow_ind_dc': True,
    'moneyflow_mkt_dc': True,
    'stk_factor': True,
    'stk_factor_pro': True,
    'cyq_perf': True,
    # ... 其他配置
}
```

## 数据存储

所有下载的数据保存在 `../data/` 目录下，按数据类型和日期组织：

```
data/
├── basic/                       # 基础数据
│   ├── stock_basic.parquet      # 股票基本信息
│   ├── trade_cal.parquet        # 交易日历
│   └── ...
├── daily/                       # 日线数据（按年月分区）
│   ├── 2023/01/
│   │   ├── daily_2023-01.parquet
│   │   └── daily_basic_2023-01.parquet
│   └── ...
├── financial/                   # 财务数据（按报告期分区）
│   ├── income/
│   │   ├── income_20231231.parquet
│   │   └── ...
│   ├── balancesheet/
│   └── cashflow/
├── holders/                     # 股东信息
│   ├── top10_holders_20231231.parquet
│   └── ...
├── funds/                       # 资金流向数据
│   ├── moneyflow_2023-01.parquet
│   └── ...
├── research/                    # 研究数据
│   ├── stk_surv_20231231.parquet
│   └── ...
└── ...                          # 其他数据类型
```

## 运行日志

系统会生成详细的运行日志，保存在 `../log/aspipe_v4.log`：

```
2025-12-12 10:00:00 - INFO - 🚀 统一数据下载系统启动
2025-12-12 10:00:01 - INFO - 积分: 5000
2025-12-12 10:00:01 - INFO - 可用数据类型: 45 种
2025-12-12 10:00:01 - INFO -   basic: 3 种
2025-12-12 10:00:01 - INFO -   daily: 4 种
...
2025-12-12 10:05:30 - INFO - ✅ 数据下载完成！
2025-12-12 10:05:30 - INFO - 📊 下载统计:
2025-12-12 10:05:30 - INFO -   • stock_basic: 1 个时间分区
2025-12-12 10:05:30 - INFO -     总记录数: 5456
...
```

## 常见问题

### Q: 如何查看我的 TuShare 积分？
A: 登录 [TuShare 官网](https://tushare.pro/)，在个人中心可以查看您的积分。

### Q: 下载速度很慢怎么办？
A: 系统已经内置了 API 限频控制，这是 TuShare 的限制。您可以考虑：
- 使用积分更高的 Token
- 缩小下载日期范围
- 使用代理服务器（在 .env 中配置 PROXY_URL）

### Q: 数据下载中断了怎么办？
A: 系统支持断点续传，重新运行相同的命令会从中断处继续下载。

### Q: 如何读取下载的 Parquet 数据？
A: 使用 pandas 可以轻松读取：

```python
import pandas as pd

# 读取股票基本信息
df = pd.read_parquet('data/basic/stock_basic.parquet')

# 读取指定月份的日线数据
df = pd.read_parquet('data/daily/2023/01/daily_2023-01.parquet')

# 读取财务数据
df = pd.read_parquet('data/financial/income/income_20231231.parquet')
```

### Q: 如何配置下载哪些数据类型？
A: 修改 `app/download_config.py` 文件中的 `DOWNLOAD_CONFIG` 字典，将需要下载的接口设为 `True`，不需要的设为 `False`。

## 技术架构

- **API 集成**：使用官方 TuShare Python SDK
- **数据处理**：Pandas + Polars 双引擎支持
- **存储格式**：Apache Parquet 列式存储
- **错误处理**：指数退避重试机制
- **并发控制**：API 限频和请求管理
- **日志系统**：结构化中文日志输出
- **缓存机制**：智能股票列表缓存，避免重复下载
- **令牌管理**：主备令牌自动切换机制

## 许可证

本项目仅供学习和研究使用。使用时请遵守 TuShare 的使用条款和相关法律法规。

## 更新日志

### v4.0.0
- 全新的积分自动适配系统
- 模块化的数据接口架构
- 支持 5000 积分的高级数据类型
- 优化的数据存储格式
- 增强的错误处理和重试机制

### v4.1.0
- 新增智能股票列表缓存机制
- 支持主备令牌自动切换
- 优化多线程并发下载
- 改进数据存储结构，按年月分区
- 新增更详细的下载配置选项

---

如有问题或建议，欢迎提交 Issue 或 Pull Request！