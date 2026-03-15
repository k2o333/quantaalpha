# App4 空结果探测记录方案 第三批

## 范围

这一批是当前明确不建议实施同表空占位的接口和模式。

## 1. 大多数 reverse_date_range

接口包括：

- `daily`
- `daily_basic`
- `moneyflow`
- `moneyflow_cnt_ths`
- `moneyflow_ind_dc`
- `moneyflow_ind_ths`
- `moneyflow_mkt_dc`
- `moneyflow_ths`
- `block_trade`
- `repurchase`
- `share_float`
- `stk_holdertrade`
- `stk_managers`
- `stock_st`
- `suspend_d`
- `report_rc`
- `stk_surv`
- `new_share`
- `namechange`

## 不建议原因

- 当前跳过逻辑主要按范围覆盖率，不是单键存在
- 有些接口是全市场日级语义
- 如果写入只有 `trade_date` 的空占位，业务表污染风险高
- 如果硬改成 `ts_code + trade_date`，又和当前请求语义不完全一致

## 当前建议

这些接口先通过下面手段降低问题：

- 更小时间窗口
- 原子提交
- 覆盖率优化
- 接受少量重复下载

## 2. 当前 period_range

接口包括：

- `balancesheet_vip`
- `cashflow_vip`
- `fina_indicator_vip`
- `fina_mainbz_vip`
- `forecast_vip`
- `income_vip`
- `express_vip`
- `top10_holders`
- `top10_floatholders`
- `pledge_stat`
- `disclosure_date`

## 不建议原因

当前很多 `period_range` 的判断是：

- 全局 `period` / `end_date` 是否存在

而不是：

- `ts_code + period/end_date` 是否存在

在这个前提下，同表空占位无法稳定解决问题，反而可能进一步混淆：

- 全局 period 已存在，但个别股票缺失
- 某个股票空 probe 写入后，却被全局 period 判定吞掉

## 当前建议

除非先统一 period 语义，否则这一批不做空占位。

如果以后要做，必须先二选一：

1. 保持全局 `period`
2. 切到股票级 `ts_code + period`

在未完成这个选择前，不进入编码。

## 3. offset / type_split / trade_cal

接口包括：

- `stock_basic`
- `stock_company`
- `broker_recommend`
- `stock_hsgt`
- `trade_cal`

## 不建议原因

这类接口的主要问题不是“同一最小键反复空探测”。

更主要的问题是：

- 分页中断
- 范围刷新
- 全局基表稳定性
- 分类维度分页

给它们加同表空占位不会带来足够收益。

## 第三批的定位

第三批文档的目的不是否定未来可能性，而是明确：

- 当前版本不应为了“全接口统一”而强推空占位
- 只在与当前架构天然匹配的接口上先做

## 当前结论

第三批全部保持原样，不进入实施。

等第一批稳定、第二批有结果后，再决定是否继续扩展。
