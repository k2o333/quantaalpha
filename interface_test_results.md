# 测试结果总结

根据测试结果，以下5个接口都可以通过只传递股票代码参数（ts_code）来一次性返回该股票的历史所有记录：

| 接口 | 查询参数 | 数据日期字段 | 锚定参数 | `is_date_anchor` | 配置文件 | 是否支持仅股票代码查询 |
|------|---------|-------------|----------|-----------------|----------|----------------------|
| `disclosure_date` | `end_date` (单个) | `end_date` | `end_date` | `true` | disclosure_date.yaml | ✅ 是 |
| `top10_holders` | `period` (单个) | `end_date` | `period` | `true` | top10_holders.yaml | ✅ 是 |
| `dividend` | `ann_date` (单个) | `ann_date` | `ann_date` | `true` | dividend.yaml | ✅ 是 |
| `pledge_stat` | `end_date` (单个) | `end_date` | `end_date` | `true` | pledge_stat.yaml | ✅ 是 |
| `stk_rewards` | `end_date` (单个) | `end_date` | `end_date` | `true` | stk_rewards.yaml | ✅ 是 |

## 详细结果

1. **disclosure_date**: 返回104条记录，时间跨度从1998年到2025年
2. **top10_holders**: 返回329条记录，时间跨度从2005年到2025年
3. **dividend**: 返回50条记录，时间跨度从1996年到2025年
4. **pledge_stat**: 返回1047条记录，时间跨度从2014年到2026年
5. **stk_rewards**: 返回3575条记录，时间跨度从1993年到2024年

## 结论

所有这5个接口都支持仅通过传递股票代码参数（ts_code）来获取该股票的完整历史数据，无需指定任何日期范围参数。这意味着：

- 这些接口在设计上允许获取单个股票的完整历史记录
- 日期锚定参数（如end_date、period、ann_date）在没有明确指定时，API会自动返回所有可用的历史数据
- 这种设计使得批量获取单个股票的完整历史数据变得简单高效