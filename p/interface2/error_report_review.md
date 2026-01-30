# aspipe_v4 Interface2 错误报告审查

审查时间: 2026-01-30
审查人: AI助手
原始报告: error_report.md

---

## 审查结论

**总体评价**: 原错误报告基本准确，但存在若干遗漏和不准确之处。

---

## 发现的问题

### 一、遗漏的问题

#### 1. 数据未写入Parquet文件 (严重)

**涉及文件**: 
- [`balancesheet_vip.txt`](testdata/aspipe_v4/p/interface2/output/balancesheet_vip.txt)
- [`income_vip.txt`](testdata/aspipe_v4/p/interface2/output/income_vip.txt)

**问题描述**: 
这两个接口的数据处理完成后，没有写入parquet文件的记录。正常情况下应该有类似以下的日志：
```
Wrote XXX records to data/xxx/xxx.parquet
```

但在 [`balancesheet_vip.txt`](testdata/aspipe_v4/p/interface2/output/balancesheet_vip.txt:42) 和 [`income_vip.txt`](testdata/aspipe_v4/p/interface2/output/income_vip.txt:47) 中都缺少这条记录，直接显示 `Storage threads stopped`。

**影响**: 数据可能未成功持久化到存储中。

---

#### 2. API接口成功率0%问题 (中)

**涉及接口**: 
- disclosure_date (成功率 0.0%)
- dividend (成功率 0.0%)  
- pledge_stat (成功率 0.0%)
- stk_rewards (成功率 0.0%)

**问题描述**: 
虽然这些接口成功调用了API并获取到字段信息，但最终没有返回任何数据记录。在性能报告中明确显示**成功率: 0.0%**。

原报告虽然提到了 "No data downloaded"，但没有强调这是API层面的成功率问题。

**日志示例** (disclosure_date):
```
API returned 5 fields for disclosure_date
Returned fields: ['ts_code', 'ann_date', 'end_date', 'pre_date', 'actual_date']
Completed final batch, total records: 0
WARNING - No data downloaded for disclosure_date
```

---

#### 3. balancesheet_vip 的特殊性 (低)

**问题描述**: 
[`balancesheet_vip.txt`](testdata/aspipe_v4/p/interface2/output/balancesheet_vip.txt:3) 是唯一一个**没有出现**以下两个ERROR的文件：
- `scan_parquet() got an unexpected keyword argument 'extra_columns'`
- `expected a file path; 'data/stock_basic' is a directory`

而是显示为WARNING:
```
WARNING - 交易日历目录不存在: data/trade_cal
WARNING - 股票列表目录不存在: data/stock_basic
```

**分析**: 这可能是因为它是第一个运行的接口，当时的缓存策略不同。

---

### 二、报告中的不准确之处

#### 1. 重复记录统计准确

原报告中的重复记录统计是准确的：

| 接口名称 | 重复记录数 | 验证结果 |
|---------|----------|---------|
| fina_indicator_vip | 107 | ✓ 正确 |
| top10_floatholders | 541 | ✓ 正确 |
| top10_holders | 114 | ✓ 正确 |
| balancesheet_vip | 38 | ✓ 正确 |
| income_vip | 13 | ✓ 正确 |
| cashflow_vip | 13 | ✓ 正确 |
| forecast_vip | 9 | ✓ 正确 |
| pledge_detail | 3 | ✓ 正确 |
| fina_mainbz_vip | 3 | ✓ 正确 |

---

#### 2. ERROR/WARNING 级别统计修正

原报告统计:
- ERROR 级别: 30
- WARNING 级别: 46

**修正统计**:

**ERROR级别** (每个文件2个，共15个文件):
- 15个接口 × 2个ERROR = **30个ERROR** ✓ 原报告正确

**WARNING级别**:
1. "Failed to read stock list from Data dir" - 15个文件 × 1 = 15
2. "Failed to derive field delist_date_dt" - 16个文件 × 1 = 16  
3. "No data downloaded" - 4个文件 × 1 = 4
4. "Found X duplicate records" - 9个文件 × 1 = 9
5. "交易日历目录不存在" + "股票列表目录不存在" - 仅 balancesheet_vip 有 = 2

总计: 15 + 16 + 4 + 9 + 2 = **46个WARNING** ✓ 原报告正确

---

### 三、建议补充的信息

#### 1. 接口成功率详情

| 接口名称 | 请求数 | 记录数 | 成功率 | 状态 |
|---------|-------|-------|-------|------|
| trade_cal | 1 | 12827 | 100.0% | ✓ |
| stock_basic | 2 | 5477 | 100.0% | ✓ |
| balancesheet_vip | 1 | 153 | 100.0% | ✓ (但未写入文件) |
| cashflow_vip | 1 | 93 | 100.0% | ✓ |
| disclosure_date | 1 | 0 | 0.0% | ✗ |
| dividend | 1 | 0 | 0.0% | ✗ |
| express_vip | 1 | 1 | 100.0% | ✓ |
| fina_audit | 1 | 28 | 100.0% | ✓ |
| fina_indicator_vip | 1 | 223 | 100.0% | ✓ |
| fina_mainbz_vip | 1 | 427 | 100.0% | ✓ |
| forecast_vip | 1 | 78 | 100.0% | ✓ |
| income_vip | 1 | 122 | 100.0% | ✓ (但未写入文件) |
| pledge_detail | 1 | 9 | 100.0% | ✓ |
| pledge_stat | 1 | 0 | 0.0% | ✗ |
| stk_factor_pro | 1 | 8026 | 100.0% | ✓ |
| stk_rewards | 1 | 0 | 0.0% | ✗ |
| top10_floatholders | 1 | 781 | 100.0% | ✓ |
| top10_holders | 1 | 176 | 100.0% | ✓ |

#### 2. 数据持久化状态

| 接口名称 | 处理记录数 | 写入记录数 | 状态 |
|---------|----------|----------|------|
| balancesheet_vip | 115 | ? | ⚠️ 未确认写入 |
| cashflow_vip | 80 | 80 | ✓ |
| disclosure_date | 0 | 0 | N/A |
| dividend | 0 | 0 | N/A |
| express_vip | 1 | 1 | ✓ |
| fina_audit | 28 | 28 | ✓ |
| fina_indicator_vip | 116 | 116 | ✓ |
| fina_mainbz_vip | 424 | 424 | ✓ |
| forecast_vip | 69 | 69 | ✓ |
| income_vip | 109 | ? | ⚠️ 未确认写入 |
| pledge_detail | 6 | 6 | ✓ |
| pledge_stat | 0 | 0 | N/A |
| stk_factor_pro | 8026 | 8026 | ✓ |
| stk_rewards | 0 | 0 | N/A |
| top10_floatholders | 240 | 240 | ✓ |
| top10_holders | 62 | 62 | ✓ |

---

## 修正后的优先修复建议

### 高优先级
1. **调查 balancesheet_vip 和 income_vip 数据未写入问题** - 数据可能丢失
2. **修复 scan_parquet() 参数错误** - 影响15个接口的缓存预热
3. **修复股票列表路径错误** - 影响数据读取逻辑

### 中优先级
4. **调查4个接口API返回0条数据的问题** - disclosure_date, dividend, pledge_stat, stk_rewards
5. **处理重复记录** - 特别是 top10_floatholders (541条) 和 fina_indicator_vip (107条)
6. **修复 delist_date 字段缺失** - 影响所有接口的数据完整性

### 低优先级
7. **创建缺失目录** - 仅在首次运行时有影响

---

## 遗漏的错误类型

原报告已涵盖:
- [x] ERROR
- [x] WARNING
- [x] Exception (作为ERROR的一部分)

未发现其他类型的错误 (如 CRITICAL, FATAL 等)。

---

## 总结

原错误报告**质量良好**，主要问题都已捕获。主要遗漏是：
1. **balancesheet_vip 和 income_vip 可能存在数据未写入的严重问题**
2. **4个接口API成功率0%的问题需要更深入调查**
3. **未对各接口的数据持久化状态进行验证**

建议重新运行这两个接口(balancesheet_vip, income_vip)，确认数据是否正常写入。
