# Type A/B/C/D 接口功能测试

本目录用于测试四类接口的增量下载功能。

## 测试脚本

- `test_type_abcd.sh` - 主测试脚本

## 测试接口分类

### Type A: 交易日历模式 (trade_date)
- `stk_factor_pro` - 股票因子数据
- `cyq_chips` - 筹码分布数据
- `moneyflow_dc` - 资金流向数据

### Type B: 报告期模式 (report_period)
- `income_vip` - 利润表 VIP
- `top10_holders` - 十大股东
- `stk_rewards` - 高管薪酬

### Type C: 日期锚定模式 (date_anchor)
- `disclosure_date` - 披露日期

### Type D: 无日期过滤模式 (no_date_filter)
- `stock_basic` - 股票基本信息

## 测试内容

1. **全量下载** - 清空数据后下载小范围日期
2. **增量下载** - 扩展日期范围，验证增量去重
3. **强制覆盖** - 使用 --force 强制重新下载

## 运行测试

```bash
cd /home/quan/testdata/aspipe_v4/p/interface5
./test_type_abcd.sh
```

## 输出

测试结果将保存到 `output/` 目录，包含每个接口的输出日志。
