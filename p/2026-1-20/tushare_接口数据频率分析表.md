# TuShare接口数据频率分析表

## 接口数据频率分析表

### 字段说明

**日期字段说明：**
- `trade_date` - 交易日期，最常用的日期字段
- `start_date/end_date` - 查询的开始/结束日期范围
- `ann_date` - 公告日期
- `end_date/period` - 报告期（如季度末）
- `f_ann_date` - 实际公告日期
- `ipo_date/issue_date` - IPO发行/上市日期
- `list_date` - 上市日期
- `record_date/ex_date` - 股权登记/除权除息日
- `float_date` - 解禁日期
- `pre_date` - 预计披露日期
- `actual_date` - 实际披露日期
- `modify_date` - 披露日期修正记录
- `first_ann_date` - 首次公告日期
- `report_date` - 报告日期
- `quarter` - 预测报告期
- `month` - 月度数据
- `setup_date` - 注册日期
- `begin_date` - 开始生效日期
- `close_date` - 结束日期
- `surv_date` - 调研日期
- `exp_date` - 过期日期
- `pay_date` - 派息日
- `div_listdate` - 红股上市日
- `imp_ann_date` - 实施公告日

**股票代码字段说明：**
- `ts_code` - TuShare标准股票代码（如000001.SZ）
- `sub_code` - 申购代码
- `exchange` - 交易所代码（SSE/SZSE/BSE）
- `o_code/n_code` - 旧代码/新代码
- 无 - 部分接口（如trade_cal、moneyflow_mkt_dc）不包含股票代码字段

### 接口数据频率分析表

| 接口名称 | 接口描述 | 是否每个交易日都有数据 | 数据更新频率 | 日期字段 | 股票代码字段 | 备注 |
|---------|---------|-------------------|------------|----------|------------|------|
| **基础数据** | | | | | | |
| stock_basic | 基础信息 | ❌ 不是 | 一次性获取，变化时更新 | list_date, delist_date | ts_code | 静态数据，股票基本信息很少变化 |
| stk_premarket | 股本情况（盘前） | ✅ 是 | 每日开盘前更新 | trade_date, start_date, end_date | ts_code | 每个交易日盘前更新股本信息 |
| trade_cal | 交易日历 | ❌ 不是 | 一次性获取 | cal_date, start_date, end_date, pretrade_date | 无 | 历史交易日历，静态数据 |
| stock_st | ST股票列表 | ✅ 是 | 每日上午9:20更新 | trade_date, start_date, end_date | ts_code | 每个交易日更新ST股票状态 |
| stock_hsgt | 沪深港通股票列表 | ✅ 是 | 每日上午9:20更新 | trade_date, start_date, end_date | ts_code | 每个交易日更新沪深港通标的 |
| namechange | 股票曾用名 | ❌ 不是 | 不定期 | start_date, end_date, ann_date | ts_code | 仅在股票更名时更新 |
| stock_company | 上市公司基本信息 | ❌ 不是 | 不定期 | setup_date | ts_code, exchange | 公司基本信息变化时更新 |
| stk_managers | 上市公司管理层 | ❌ 不是 | 不定期 | ann_date, start_date, end_date, begin_date, end_date | ts_code | 管理层变动时更新 |
| stk_rewards | 管理层薪酬和持股 | ❌ 不是 | 季度/年度 | ann_date, end_date | ts_code | 按报告期更新，非每日 |
| bse_mapping | 北交所新旧代码对照 | ❌ 不是 | 一次性获取 | list_date | o_code, n_code | 静态映射数据 |
| new_share | IPO新股列表 | ❌ 不是 | 不定期 | ipo_date, issue_date, start_date, end_date | ts_code, sub_code | 有新股上市时更新 |
| bak_basic | 股票历史列表 | ❌ 不是 | 每日（历史数据） | trade_date, start_date, end_date, list_date | ts_code | 从2016年开始的历史快照 |

| **财务数据** | | | | | | |
| income | 利润表 | ❌ 不是 | 季度更新 | ann_date, start_date, end_date, f_ann_date, end_date, period | ts_code | 按季度发布财报 |
| balancesheet | 资产负债表 | ❌ 不是 | 季度更新 | ann_date, start_date, end_date, end_date, period | ts_code | 按季度发布财报 |
| cashflow | 现金流量表 | ❌ 不是 | 季度更新 | ann_date, start_date, end_date, f_ann_date, end_date, period | ts_code | 按季度发布财报 |
| forecast | 业绩预告 | ❌ 不是 | 不定期 | ann_date, start_date, end_date, period, first_ann_date | ts_code | 公司发布预告时更新 |
| express | 业绩快报 | ❌ 不是 | 不定期 | ann_date, start_date, end_date, end_date | ts_code | 公司发布快报时更新 |
| dividend | 分红送股 | ❌ 不是 | 不定期 | ann_date, record_date, ex_date, imp_ann_date, pay_date, div_listdate | ts_code | 分红时更新 |
| fina_indicator | 财务指标 | ❌ 不是 | 季度更新 | ann_date, start_date, end_date, end_date, period | ts_code | 基于财报计算的财务指标 |
| fina_audit | 财务审计意见 | ❌ 不是 | 年度更新 | ann_date, start_date, end_date, period | ts_code | 年报审计意见 |
| fina_mainbz | 主营业务构成 | ❌ 不是 | 季度更新 | start_date, end_date, period, end_date | ts_code | 按财报期更新 |
| disclosure_date | 财报披露计划 | ❌ 不是 | 不定期 | end_date, pre_date, ann_date, actual_date, modify_date | ts_code | 披露计划变更时更新 |

| **行情数据** | | | | | | |
| daily | A股日线行情 | ✅ 是 | 每日15-16点更新 | trade_date, start_date, end_date | ts_code | 每个交易日更新 |
| pro_bar | A股复权行情 | ✅ 是 | 每日15-16点更新 | start_date, end_date | ts_code | 每个交易日更新 |
| daily_basic | 每日指标 | ✅ 是 | 每日15-17点更新 | trade_date, start_date, end_date | ts_code | 每个交易日更新基本面指标 |
| suspend_d | 每日停复牌信息 | ✅ 是 | 不定期 | trade_date, start_date, end_date | ts_code | 有停复牌时更新 |
| bak_daily | 备用行情 | ✅ 是 | 每日更新 | trade_date, start_date, end_date | ts_code | 从2017年开始的日线行情 |

| **参考数据** | | | | | |
| top10_floatholders | 前十大流通股东 | ❌ 不是 | 季度更新 | ann_date, period, start_date, end_date, end_date | ts_code | 按季度报告期更新 |
| top10_holders | 前十大股东 | ❌ 不是 | 季度更新 | ann_date, period, start_date, end_date, end_date | ts_code | 按季度报告期更新 |
| pledge_stat | 股权质押统计数据 | ❌ 不是 | 每周更新 | end_date | ts_code | 股权质押汇总统计 |
| pledge_detail | 股权质押明细 | ❌ 不是 | 不定期 | ann_date, start_date, end_date | ts_code | 质押发生时更新 |
| repurchase | 股票回购 | ❌ 不是 | 不定期 | ann_date, start_date, end_date, exp_date | ts_code | 回购时更新 |
| share_float | 限售股解禁 | ❌ 不是 | 不定期 | ann_date, float_date, start_date, end_date | ts_code | 解禁时更新 |
| block_trade | 大宗交易 | ✅ 是 | 每日更新 | trade_date, start_date, end_date | ts_code | 每个交易日大宗交易数据 |
| stk_holdertrade | 股东增减持 | ❌ 不是 | 不定期 | ann_date, start_date, end_date, begin_date, close_date | ts_code | 增减持发生时更新 |

| **特色数据** | | | | | |
| report_rc | 卖方盈利预测数据 | ✅ 是 | 每日19-22点更新 | report_date, start_date, end_date, quarter | ts_code | 券商研报数据，每日更新 |
| cyq_perf | 每日筹码及胜率 | ✅ 是 | 每日17-18点更新 | trade_date, start_date, end_date | ts_code | 筹码分布技术指标 |
| cyq_chips | 每日筹码分布 | ✅ 是 | 每日17-18点更新 | trade_date, start_date, end_date | ts_code | 筹码分布详细数据 |
| stk_factor | 股票技术因子 | ✅ 是 | 每日更新 | trade_date, start_date, end_date | ts_code | 技术指标数据 |
| stk_factor_pro | 股票技术面因子(专业版) | ✅ 是 | 每日更新 | trade_date, start_date, end_date | ts_code | 增强版技术指标 |
| stk_surv | 机构调研表 | ❌ 不是 | 不定期 | surv_date, start_date, end_date | ts_code | 机构调研发生时更新 |
| broker_recommend | 券商每月荐股 | ❌ 不是 | 月度更新 | month | ts_code | 每月更新券商金股 |

| **资金流向** | | | | | |
| moneyflow | 个股资金流向 | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | ts_code | 个股大单小单资金流向 |
| moneyflow_ths | 个股资金流向（THS） | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | ts_code | 同花顺版本资金流向 |
| moneyflow_dc | 个股资金流向（DC） | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | ts_code | 东方财富版本资金流向 |
| moneyflow_cnt_ths | 同花顺概念板块资金流向 | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | ts_code | 概念板块资金流向 |
| moneyflow_ind_ths | 同花顺行业资金流向 | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | ts_code | 行业板块资金流向 |
| moneyflow_ind_dc | 东财概念及行业板块资金流向 | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | ts_code | 东财版本板块资金流向 |
| moneyflow_mkt_dc | 大盘资金流向（DC） | ✅ 是 | 每日盘后更新 | trade_date, start_date, end_date | 无 | 大盘整体资金流向 |

## 总结

**每个交易日都有数据的接口（共22个）：**

### 1. 行情类（5个）
- daily（日线行情）
- pro_bar（复权行情）
- daily_basic（每日指标）
- suspend_d（停复牌信息）
- bak_daily（备用行情）

### 2. 基础信息类（3个）
- stk_premarket（盘前股本）
- stock_st（ST股票列表）
- stock_hsgt（沪深港通列表）

### 3. 资金流向类（7个）
- moneyflow（个股资金流向）
- moneyflow_ths（个股资金流向-THS）
- moneyflow_dc（个股资金流向-DC）
- moneyflow_cnt_ths（概念板块资金流向）
- moneyflow_ind_ths（行业资金流向）
- moneyflow_ind_dc（东财板块资金流向）
- moneyflow_mkt_dc（大盘资金流向）

### 4. 特色数据类（5个）
- report_rc（卖方盈利预测）
- cyq_perf（每日筹码及胜率）
- cyq_chips（每日筹码分布）
- stk_factor（股票技术因子）
- stk_factor_pro（技术面因子专业版）

### 5. 其他交易数据（1个）
- block_trade（大宗交易）

**不是每个交易日都有数据的接口（共26个）：**
主要是财务数据（季度/年度更新）、股东信息（季度更新）、公司基本信息（不定期更新）等。

## 建议

对于5000积分权限，建议重点关注22个每日更新接口，这些是构建完整A股日线数据集的核心接口。根据您的需求（只要沪深A股相关数据，日线行情），可以优先考虑以下核心接口：

**必选核心接口（8个）：**
1. daily - A股日线行情
2. daily_basic - 每日基本面指标
3. moneyflow - 个股资金流向
4. stk_premarket - 盘前股本信息
5. stock_st - ST股票状态
6. stock_hsgt - 沪深港通标的
7. suspend_d - 停复牌信息
8. report_rc - 卖方盈利预测

**可选增强接口（14个）：**
- 剩余的资金流向接口
- 技术因子和筹码分布接口
- 其他辅助性接口

**需要注意的限制：**
- 某些接口有更高的积分要求（如report_rc需要8000积分正式权限）
- 部分接口有频率限制，需要合理规划下载节奏
- 建议按接口类型分组，避免同时请求过多高权限接口