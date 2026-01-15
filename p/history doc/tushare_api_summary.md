# Tushare接口参数分类汇总

## 一、财报周期参数接口（可按季度获取数据）

以下接口支持通过财报周期参数（如period、end_date）来获取特定季度的财务或股东数据：

### 1. stk_rewards - 管理层薪酬和持股
- **参数**: ts_code（必需）, end_date（报告期）
- **说明**: end_date参数是报告期，用于获取指定报告期的管理层薪酬和持股数据

### 2. income - 利润表
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报，20170630半年报，20170930三季报）

### 3. balancesheet - 资产负债表
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报，20170630半年报，20170930三季报）

### 4. cashflow - 现金流量表
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报，20170630半年报，20170930三季报）

### 5. forecast - 业绩预告
- **参数**: ts_code（可选）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报，20170630半年报，20170930三季报）
- **注意**: 不设置ts_code可获取全市场数据

### 6. express - 业绩快报
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报，20170630半年报，20170930三季报）

### 7. fina_indicator - 财务指标数据
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报）

### 8. fina_audit - 财务审计意见
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报）

### 9. fina_mainbz - 主营业务构成
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（每个季度最后一天的日期，如20171231表示年报）

### 10. disclosure_date - 财报披露计划
- **参数**: ts_code（可选）, end_date（财报周期）
- **说明**: end_date参数是财报周期（每个季度最后一天的日期，如20181231表示年报）
- **注意**: 不设置ts_code可获取全市场数据

### 11. top10_floatholders - 前十大流通股东
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（YYYYMMDD格式，一般为每个季度最后一天）

### 12. top10_holders - 前十大股东
- **参数**: ts_code（必需）, period（报告期）
- **说明**: period参数是报告期（YYYYMMDD格式，一般为每个季度最后一天）

---

## 二、交易日参数接口（可按单个交易日获取全市场数据）

以下接口支持通过交易日参数（如trade_date、ann_date）来获取全市场的数据：

### 1. daily - A股日线行情
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的日线行情数据

### 2. daily_basic - 每日指标
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的基本面指标数据

### 3. moneyflow - 个股资金流向
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的资金流向数据

### 4. moneyflow_ths - 个股资金流向（THS）
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的资金流向数据

### 5. moneyflow_dc - 个股资金流向（DC）
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的资金流向数据

### 6. suspend_d - 每日停复牌信息
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的停复牌信息

### 7. bak_daily - 备用行情
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的备用行情数据

### 8. block_trade - 大宗交易
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的大宗交易数据

### 9. stk_holdertrade - 股东增减持
- **参数**: ts_code（可选）, ann_date
- **说明**: 通过设置ann_date参数，不设置ts_code，可以获取某一天全市场的股东增减持数据

### 10. stock_st - ST股票列表
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的ST股票列表

### 11. repurchase - 股票回购
- **参数**: ann_date（可选）
- **说明**: 通过设置ann_date参数，可以获取某一天全市场的股票回购数据

### 12. share_float - 限售股解禁
- **参数**: ts_code（可选）, ann_date 或 float_date
- **说明**: 通过设置ann_date或float_date参数，不设置ts_code，可以获取某一天全市场的限售股解禁数据

### 13. cyq_perf - 每日筹码及胜率
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的筹码及胜率数据

### 14. cyq_chips - 每日筹码分布
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的筹码分布数据

### 15. stk_factor - 股票技术因子
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的技术因子数据

### 16. stk_factor_pro - 股票技术面因子(专业版)
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的技术因子数据

### 17. stk_surv - 机构调研表
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的机构调研数据

### 18. moneyflow_cnt_ths - 同花顺概念板块资金流向
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的概念板块资金流向数据

### 19. moneyflow_ind_ths - 同花顺行业资金流向
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的行业资金流向数据

### 20. moneyflow_ind_dc - 东财概念及行业板块资金流向
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的板块资金流向数据

### 21. moneyflow_mkt_dc - 大盘资金流向
- **参数**: trade_date
- **说明**: 通过设置trade_date参数，可以获取某一天大盘资金流向数据

### 22. stk_premarket - 股本情况（盘前）
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的股本情况

### 23. bak_basic - 股票历史列表
- **参数**: ts_code（可选）, trade_date
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的股票列表

### 24. stk_managers - 上市公司管理层
- **参数**: ts_code（可选）, ann_date
- **说明**: 通过设置ann_date参数，不设置ts_code，可以获取某一天全市场的管理层信息

### 25. stock_hsgt - 沪深港通股票列表
- **参数**: ts_code（可选）, trade_date, type
- **说明**: 通过设置trade_date参数，不设置ts_code，可以获取某一天全市场的沪深港通股票列表

---

## 三、TS代码参数接口（必须指定股票代码）

以下接口必须输入TS代码参数才能获取数据：

### 1. pledge_detail - 股权质押明细
- **参数**: ts_code（必需）
- **说明**: ts_code是必需参数，必须指定股票代码
- **代码示例**:
  ```python
  df = pro.pledge_detail(ts_code='000014.SZ')
  ```

### 2. pro_bar - 通用行情接口
- **参数**: ts_code（必需）, asset（必需）, freq（必需）
- **说明**: ts_code, asset, freq是必需参数
- **代码示例**:
  ```python
  #取000001的前复权行情
  df = ts.pro_bar(ts_code='000001.SZ', adj='qfq', start_date='20180101', end_date='20181011')
  
  #取上证指数行情数据
  df = ts.pro_bar(ts_code='000001.SH', asset='I', start_date='20180101', end_date='20181011')
  ```

---

## 四、日期范围参数接口（按日期范围获取数据）

以下接口通过日期范围参数获取数据：

### 1. trade_cal - 交易日历
- **参数**: start_date, end_date（可选）
- **说明**: 所有参数都是可选的，不输入任何参数可以获取默认的交易日历
- **代码示例**:
  ```python
  df = pro.trade_cal(exchange='', start_date='20180101', end_date='20181231')
  ```

### 2. new_share - IPO新股列表
- **参数**: start_date, end_date（可选）
- **说明**: 所有参数都是可选的，不输入任何参数可以获取全部新股信息
- **代码示例**:
  ```python
  df = pro.new_share(start_date='20180901', end_date='20181018')
  ```

### 3. namechange - 股票曾用名
- **参数**: start_date, end_date（可选）
- **说明**: 所有参数都是可选的，不输入任何参数可以获取全部股票曾用名
- **代码示例**:
  ```python
  df = pro.namechange(ts_code='600848.SH', fields='ts_code,name,start_date,end_date,change_reason')
  ```

### 4. report_rc - 卖方盈利预测数据
- **参数**: report_date, start_date, end_date（可选）
- **说明**: 所有参数都是可选的，不输入任何参数可以获取全部数据
- **代码示例**:
  ```python
  df = pro.report_rc(ts_code='', report_date='20220429')
  ```

---

## 五、特定参数接口（需要特定参数，如月份等）

以下接口需要特定类型的参数：

### 1. broker_recommend - 券商每月荐股
- **参数**: month（必需）
- **说明**: month是必需参数，必须指定月份
- **代码示例**:
  ```python
  #获取查询月份券商金股
  df = pro.broker_recommend(month='202106')
  ```

---

## 六、无特定参数接口（可不输入任何参数获取全量数据）

以下接口不需要输入任何特定参数即可获取全量数据：

### 1. stock_basic - 基础信息
- **参数**: 所有参数都是可选的
- **说明**: 所有参数都是可选的，不输入任何参数可以获取全部股票基础信息
- **代码示例**:
  ```python
  #查询当前所有正常上市交易的股票列表
  data = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
  ```

### 2. stock_company - 上市公司基本信息
- **参数**: 所有参数都是可选的
- **说明**: 所有参数都是可选的，不输入任何参数可以获取全部上市公司信息
- **代码示例**:
  ```python
  df = pro.stock_company(exchange='SZSE', fields='ts_code,chairman,manager,secretary,reg_capital,setup_date,province')
  ```



### 3. pledge_stat - 股权质押统计数据
- **参数**: 所有参数都是可选的
- **说明**: 所有参数都是可选的，不输入任何参数可以获取全部股票质押统计
- **代码示例**:
  ```python
  df = pro.pledge_stat(ts_code='000014.SZ')
  ```
