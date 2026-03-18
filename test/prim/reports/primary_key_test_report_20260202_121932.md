# Primary Key 有效性验证测试报告

生成时间: 2026-02-02 12:19:32

## 汇总

- 测试接口总数: 16
- ✅ 通过 (无重复): 3
- ⚠️ 通过 (有重复但无冲突): 0
- ❌ 失败 (主键不完整): 0
- ⚠️ 错误/无数据: 13

## 所有接口结果

| 接口 | 状态 | 主键 | 总记录 | 重复组 | 问题组 |
|------|------|------|--------|--------|--------|
| balancesheet_vip | ✅ 通过 | ts_code, ann_date, end_date | 113 | 0 | 0 |
| cashflow_vip | ✅ 通过 | ts_code, ann_date, end_date | 80 | 0 | 0 |
| disclosure_date | ⚠️ 无数据 | ts_code, end_date | 0 | 0 | 0 |
| dividend | ⚠️ 无数据 | ts_code, end_date, ann_date | 0 | 0 | 0 |
| express_vip | ⚠️ 无数据 | ts_code, ann_date, end_date | 0 | 0 | 0 |
| fina_audit | ⚠️ 无数据 | ts_code, ann_date, end_date | 0 | 0 | 0 |
| fina_indicator_vip | ⚠️ 无数据 | ts_code, ann_date, end_date | 0 | 0 | 0 |
| fina_mainbz_vip | ⚠️ 无数据 | ts_code, end_date, bz_item | 0 | 0 | 0 |
| forecast_vip | ⚠️ 无数据 | ts_code, ann_date, end_date | 0 | 0 | 0 |
| income_vip | ✅ 通过 | ts_code, ann_date, end_date, update_flag | 124 | 0 | 0 |
| pledge_detail | ⚠️ 无数据 | ts_code, ann_date, holder_name, start_date | 0 | 0 | 0 |
| pledge_stat | ⚠️ 无数据 | ts_code, end_date | 0 | 0 | 0 |
| stk_factor_pro | ⚠️ 无数据 | ts_code, trade_date | 0 | 0 | 0 |
| stk_rewards | ⚠️ 无数据 | ts_code, name, ann_date | 0 | 0 | 0 |
| top10_floatholders | ⚠️ 无数据 | ts_code, period, holder_name | 0 | 0 | 0 |
| top10_holders | ⚠️ 无数据 | ts_code, period, holder_name | 0 | 0 | 0 |

