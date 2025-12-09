# aspipe_v4 统一数据下载系统

基于Tushare积分的数据下载平台，根据用户积分自动下载相应级别的数据。

## 功能特性

- **积分控制**：根据TUSHARE积分自动确定可下载的数据类型
- **统一入口**：单一入口点下载所有可用数据
- **智能重试**：问题接口自动降级处理
- **进度监控**：实时下载进度和统计信息
- **文件存储**：Parquet格式高效存储

## 使用方法

### 基本用法

```bash
# 从默认日期（20230101）下载到今天
python -m app.main

# 指定起始日期
python -m app.main --start_date 20230101

# 指定起始和结束日期
python -m app.main --start_date 20230101 --end_date 20231231
```

或者直接运行：

```bash
cd /home/quan/testdata/aspipe_v4/app
python main.py --start_date 20230101 --end_date 20231231
```

## 积分与数据类型

| 积分 | 可用数据类型 | 示例接口 |
|------|-------------|----------|
| 120+ | 7种 | new_share, trade_cal, namechange |
| 2000+ | 19种 | stock_basic, daily_basic, income, balancesheet, cashflow, fina_indicator |
| 3000+ | 21种 | stock_st, stock_hsgt |
| 5000+ | 40+种 | *_vip接口, 技术指标, 资金流向等 |

## 数据存储

所有数据文件保存在：`/home/quan/testdata/aspipe_v4/data/`

## 配置

在 `/home/quan/testdata/aspipe_v4/.env` 中设置：

```
tushare_token=your_token_here
tushare_points=2000
```

## 目录结构

```
aspipe_v4/
├── .env                 # 配置文件
├── app/
│   ├── main.py          # 统一入口点
│   ├── score_config.py  # 积分配置
│   ├── tushare_api.py   # API接口
│   └── ...
├── data/               # 数据存储目录
└── log/                # 日志目录
```

## 数据类型说明

- **基础信息**: stock_basic, stock_company, trade_cal
- **每日数据**: daily, daily_basic, moneyflow
- **财务数据**: income, balancesheet, cashflow, fina_indicator 
- **股东数据**: top10_holders, stk_rewards, stk_managers
- **事件数据**: dividend, forecast, express