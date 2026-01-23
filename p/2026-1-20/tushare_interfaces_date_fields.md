# TuShare接口日期字段汇总表

基于 `/home/quan/testdata/aspipe_v4/p/tu.md` 文档分析，整理出所有output参数中包含日期字段的接口。

## 接口日期字段汇总表

| 接口名 | 日期字段1 | 日期字段2 | 日期字段3 | 说明 |
|--------|-----------|-----------|-----------|------|
| **基础数据** |
| stock_basic | list_date | delist_date | | 上市日期、退市日期 |
| stk_premarket | trade_date | | | 交易日期 |
| trade_cal | cal_date | pretrade_date | | 日历日期、上一个交易日 |
| stock_st | trade_date | | | 交易日期 |
| stock_hsgt | trade_date | | | 交易日期 |
| namechange | start_date | end_date | ann_date | 开始日期、结束日期、公告日期 |
| stock_company | setup_date | | | 注册日期 |
| stk_managers | ann_date | birthday | begin_date | end_date | 公告日期、出生年月、上任日期、离任日期 |
| stk_rewards | ann_date | end_date | | 公告日期、截止日期 |
| bse_mapping | list_date | | | 上市日期 |
| new_share | ipo_date | issue_date | | 上网发行日期、上市日期 |
| bak_basic | trade_date | list_date | | 交易日期、上市日期 |
| **财务数据** |
| income | ann_date | f_ann_date | end_date | 公告日期、实际公告日期、报告期 |
| balancesheet | ann_date | f_ann_date | end_date | 公告日期、实际公告日期、报告期 |
| cashflow | ann_date | f_ann_date | end_date | 公告日期、实际公告日期、报告期 |
| forecast | ann_date | end_date | first_ann_date | 公告日期、报告期、首次公告日 |
| express | ann_date | end_date | | 公告日期、报告期 |
| dividend | ann_date | end_date | record_date | ex_date | pay_date | div_listdate | imp_ann_date | base_date | 公告日期、分红年度、股权登记日、除权除息日、派息日、红股上市日、实施公告日、基准日 |
| fina_indicator | ann_date | end_date | | 公告日期、报告期 |
| fina_audit | ann_date | end_date | | 公告日期、报告期 |
| fina_mainbz | end_date | | | 报告期 |
| disclosure_date | ann_date | end_date | pre_date | actual_date | modify_date | 最新披露公告日、报告期、预计披露日期、实际披露日期、披露日期修正记录 |
| **行情数据** |
| daily | trade_date | | | 交易日期 |
| daily_basic | trade_date | | | 交易日期 |
| pro_bar | trade_date | | | 交易日期（作为通用行情接口） |
| suspend_d | trade_date | | | 停复牌日期 |
| bak_daily | trade_date | | | 交易日期 |
| **参考数据** |
| top10_floatholders | ann_date | end_date | | 公告日期、报告期 |
| top10_holders | ann_date | end_date | | 公告日期、报告期 |
| pledge_stat | end_date | | | 截止日期 |
| pledge_detail | ann_date | start_date | end_date | release_date | 公告日期、质押开始日期、质押结束日期、解押日期 |
| repurchase | ann_date | end_date | exp_date | 公告日期、截止日期、过期日期 |
| share_float | ann_date | float_date | | 公告日期、解禁日期 |
| block_trade | trade_date | | | 交易日历 |
| stk_holdertrade | ann_date | begin_date | close_date | 公告日期、增减持开始日期、增减持结束日期 |
| **特色数据** |
| report_rc | report_date | | | 研报日期 |
| cyq_perf | trade_date | | | 交易日期 |
| cyq_chips | trade_date | | | 交易日期 |
| stk_factor | trade_date | | | 交易日期 |
| stk_factor_pro | trade_date | | | 交易日期 |
| stk_surv | surv_date | | | 调研日期 |
| broker_recommend | month | | | 月度（YYYYMM格式） |
| moneyflow | trade_date | | | 交易日期 |
| moneyflow_ths | trade_date | | | 交易日期（同花顺个股资金流向） |
| moneyflow_dc | trade_date | | | 交易日期（东方财富个股资金流向） |
| moneyflow_cnt_ths | trade_date | | | 交易日期（同花顺概念板块资金流向） |
| moneyflow_ind_ths | trade_date | | | 交易日期（同花顺行业资金流向） |
| moneyflow_ind_dc | trade_date | | | 交易日期（东方财富板块资金流向） |
| moneyflow_mkt_dc | trade_date | | | 交易日期（东方财富大盘资金流向） |

## 说明

1. **日期字段类型**：
   - `trade_date`: 交易日期，格式通常为YYYYMMDD
   - `ann_date`: 公告日期，格式通常为YYYYMMDD
   - `end_date`: 报告期或截止日期，通常为季度末日期（如20181231）
   - `start_date`: 开始日期
   - `list_date`: 上市日期
   - `setup_date`: 注册日期
   - `month`: 月度，格式为YYYYMM

2. **特殊接口**：
   - `pro_bar`: 通用行情接口，支持多种资产类别的复权行情
   - `dividend`: 包含最多日期字段（8个），涉及分红的各个重要日期节点
   - `pledge_detail`: 包含质押相关的完整日期信息
   - `moneyflow`系列: 7个资金流向相关接口，都包含trade_date字段，涵盖个股、板块、大盘等不同维度的资金流向数据

3. **日期格式**：
   - 大部分日期字段使用YYYYMMDD格式
   - 月度字段使用YYYYMM格式
   - 部分接口支持日期范围查询

4. **数据用途**：
   - 交易日期主要用于行情和交易相关数据
   - 公告日期主要用于信息披露相关数据
   - 报告期主要用于财务报告数据
   - 上市/注册日期主要用于基础信息数据

*本表格基于TuShare Pro API文档整理，具体字段格式和可用性请参考官方最新文档。*