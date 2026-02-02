# Primary Key 有效性验证测试报告

生成时间: 2026-02-02 12:33:40

## 汇总

- 测试接口总数: 16
- ✅ 通过 (无重复): 6
- ⚠️ 通过 (有重复但无冲突): 1
- ❌ 失败 (主键不完整): 7
- ⚠️ 错误/无数据: 2

## 失败的接口详情

### balancesheet_vip

- 当前主键: `['ts_code', 'ann_date', 'end_date']`
- 总记录数: 151
- 重复组数: 38
- 问题组数: 38

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20140307', 'end_date': '20131231'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['0', '1']

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20141027', 'end_date': '20140930'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['0', '1']

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20160314', 'end_date': '20151231'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['0', '1']

### cashflow_vip

- 当前主键: `['ts_code', 'ann_date', 'end_date']`
- 总记录数: 95
- 重复组数: 15
- 问题组数: 15

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20180821', 'end_date': '20180630'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['1', '0']

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20251031', 'end_date': '20250930'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['1', '0']

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20200318', 'end_date': '20191231'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['1', '0']

### dividend

- 当前主键: `['ts_code', 'end_date', 'ann_date']`
- 总记录数: 57
- 重复组数: 7
- 问题组数: 7

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'end_date': '20191231', 'ann_date': '20200318'}`
- 记录数: 3
- 冲突字段:
  - `div_proc`: ['实施', '预案', '股东大会通过']
  - `cash_div`: [0.0, 1.0166131]
  - `cash_div_tax`: [1.016613, 1.0166131, 1.045]

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'end_date': '20241231', 'ann_date': '20250401'}`
- 记录数: 2
- 冲突字段:
  - `div_proc`: ['预案', '股东大会通过']

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'end_date': '20211231', 'ann_date': '20220331'}`
- 记录数: 4
- 冲突字段:
  - `div_proc`: ['预案', '股东大会通过', '实施']
  - `cash_div`: [0.0, 0.9761257]
  - `cash_div_tax`: [0.97, 0.976125, 0.9761257]

### fina_indicator_vip

- 当前主键: `['ts_code', 'ann_date', 'end_date']`
- 总记录数: 219
- 重复组数: 105
- 问题组数: 100

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20021028', 'end_date': '20020930'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['0', '1']

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20120424', 'end_date': '20120331'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['0', '1']

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '19960828', 'end_date': '19960630'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['1', '0']

### forecast_vip

- 当前主键: `['ts_code', 'ann_date', 'end_date']`
- 总记录数: 23
- 重复组数: 3
- 问题组数: 3

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20260131', 'end_date': '20251231'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['1', '0']

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20250127', 'end_date': '20241231'}`
- 记录数: 2
- 冲突字段:
  - `summary`: ['预计:净利润-4500000', '预计净利润-4500000万']
  - `update_flag`: ['0', '1']

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20240710', 'end_date': '20240630'}`
- 记录数: 2
- 冲突字段:
  - `update_flag`: ['0', '1']

### pledge_detail

- 当前主键: `['ts_code', 'ann_date', 'holder_name', 'start_date']`
- 总记录数: 148
- 重复组数: 51
- 问题组数: 18

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20170328', 'holder_name': '深圳市钜盛华股份有限公司', 'start_date': '20151103'}`
- 记录数: 2
- 冲突字段:
  - `pledge_amount`: [1513.9, 7586.1]

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20181018', 'holder_name': '深圳市钜盛华股份有限公司', 'start_date': '20170309'}`
- 记录数: 2
- 冲突字段:
  - `pledge_amount`: [4713.7576, 13486.2424]
  - `is_release`: ['0', '1']

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'ann_date': '20220909', 'holder_name': '深圳盈嘉众实业合伙企业(有限合伙)', 'start_date': '20210902'}`
- 记录数: 2
- 冲突字段:
  - `pledge_amount`: [7368.4211, 12631.5789]
  - `release_date`: ['20220906', '20220907']

### stk_rewards

- 当前主键: `['ts_code', 'name', 'ann_date']`
- 总记录数: 1498
- 重复组数: 80
- 问题组数: 35

**问题样本:**

样本 1:
- Primary Key: `{'ts_code': '000002.SZ', 'name': '郁亮', 'ann_date': '20170327'}`
- 记录数: 2
- 冲突字段:
  - `end_date`: ['20161231', '20151231']
  - `reward`: [9790000.0, 9988000.0]

样本 2:
- Primary Key: `{'ts_code': '000002.SZ', 'name': '张力', 'ann_date': '20080321'}`
- 记录数: 2
- 冲突字段:
  - `end_date`: ['20061231', '20071231']
  - `reward`: [1500000.0, 2280000.0]

样本 3:
- Primary Key: `{'ts_code': '000002.SZ', 'name': '王石', 'ann_date': '20170327'}`
- 记录数: 2
- 冲突字段:
  - `end_date`: ['20151231', '20161231']
  - `reward`: [9988000.0, 9990000.0]

## 所有接口结果

| 接口 | 状态 | 主键 | 总记录 | 重复组 | 问题组 |
|------|------|------|--------|--------|--------|
| balancesheet_vip | ❌ 失败 | ts_code, ann_date, end_date | 151 | 38 | 38 |
| cashflow_vip | ❌ 失败 | ts_code, ann_date, end_date | 95 | 15 | 15 |
| disclosure_date | ✅ 通过 | ts_code, end_date | 104 | 0 | 0 |
| dividend | ❌ 失败 | ts_code, end_date, ann_date | 57 | 7 | 7 |
| express_vip | ✅ 通过 | ts_code, ann_date, end_date | 1 | 0 | 0 |
| fina_audit | ✅ 通过 | ts_code, ann_date, end_date | 26 | 0 | 0 |
| fina_indicator_vip | ❌ 失败 | ts_code, ann_date, end_date | 219 | 105 | 100 |
| fina_mainbz_vip | ✅ 通过 | ts_code, end_date, bz_item | 1027 | 0 | 0 |
| forecast_vip | ❌ 失败 | ts_code, ann_date, end_date | 23 | 3 | 3 |
| income_vip | ✅ 通过 | ts_code, ann_date, end_date, update_flag | 124 | 0 | 0 |
| pledge_detail | ❌ 失败 | ts_code, ann_date, holder_name, start_date | 148 | 51 | 18 |
| pledge_stat | ⚠️ 有重复 | ts_code, end_date | 724 | 112 | 0 |
| stk_factor_pro | ✅ 通过 | ts_code, trade_date | 8282 | 0 | 0 |
| stk_rewards | ❌ 失败 | ts_code, name, ann_date | 1498 | 80 | 35 |
| top10_floatholders | ⚠️ 错误 | ts_code, period, holder_name | 804 | 0 | 0 |
| top10_holders | ⚠️ 错误 | ts_code, period, holder_name | 193 | 0 | 0 |

## 修复建议

对于失败的接口，根据冲突字段分析，可能需要将以下字段添加到 primary_key 中:

**balancesheet_vip**: 考虑添加 `total_share, update_flag`

**cashflow_vip**: 考虑添加 `update_flag`

**dividend**: 考虑添加 `cash_div, cash_div_tax, div_proc`

**fina_indicator_vip**: 考虑添加 `update_flag`

**forecast_vip**: 考虑添加 `summary, update_flag`

**pledge_detail**: 考虑添加 `is_buyback, is_release, pledge_amount, release_date`

**stk_rewards**: 考虑添加 `end_date, hold_vol, reward, title`

