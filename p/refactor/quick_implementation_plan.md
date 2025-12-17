# A股数据下载系统修复执行计划

## 问题核心
系统拥有5000积分权限，但只下载了基础数据，未利用完整权限下载日线、财务、股东等高价值数据。

## 修复步骤

### 步骤1: 修复下载管理器 (2-3小时)
修改 `app/download_manager.py`：
- 编辑 `download_all_score_appropriate_data` 方法
- 添加对所有数据类别的支持：daily, financial, holders, funds, market_structure, research, events, others
- 实现类别调度逻辑

### 步骤2: 补充接口方法 (4-5小时)
完善各接口模块：
- `interfaces/daily_data.py`: 添加 pro_bar, bak_daily, stk_factor, stk_factor_pro 方法
- `interfaces/holders_data.py`: 添加 pledge_stat, pledge_detail, repurchase 等方法
- `interfaces/market_flow.py`: 添加资金流相关方法
- `interfaces/technical_factors.py`, `interfaces/market_structure.py`, `interfaces/research_data.py`: 添加缺失的接口方法

### 步骤3: 优化下载逻辑 (2-3小时)
- 实现日期范围处理逻辑，批量下载日线数据
- 优化并行处理，提升下载效率
- 完善错误处理和重试机制

## 预期结果
系统将充分利用5000积分权限，下载所有可用A股数据接口的数据，特别是：
- 日线行情数据：daily, pro_bar, stk_factor 等
- 财务数据：income_vip, balancesheet_vip 等
- 股东数据：pledge_detail, block_trade 等
- 资金流数据：moneyflow_dc, moneyflow_ths 等

## 数据量提升
从目前的几十万记录提升至数千万甚至上亿记录，真正发挥5000积分的价值。