# S03: P0 配置解锁优化

**触发决策**: D014 (ADR-001 Phase 1)

**问题**: P0 配置修改可以立即产生战略价值，但当前 backtest.yaml 未激活这些功能。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md` 第 1.1 节

---

## 目标

完成 P0 配置的修改，包括：
1. 排除北交所股票
2. 激活多周期回测
3. 配置跨牛熊的回测时间段

---

## 成功标准

- [ ] backtest.yaml stock_filter.enabled 改为 true
- [ ] exclude_markets 包含 "bj"
- [ ] multi_period_validation.enabled 改为 true
- [ ] 配置 4 个跨牛熊的回测时间段
- [ ] universe.py 的 filter_by_market 正确调用
- [ ] 回测时排除北交所股票
- [ ] 多周期验证计算稳定性分数

---

## 任务拆分

### T01: 修改 backtest.yaml 股票过滤
**文件**: `configs/backtest.yaml`
**估算**: 0.5h

```yaml
data:
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]
    exclude_st: true
    min_list_days: 60
```

**验收**:
- [ ] enabled: true
- [ ] exclude_markets 包含 "bj"
- [ ] 其他选项合理配置

### T02: 修改 backtest.yaml 多周期回测
**文件**: `configs/backtest.yaml`
**估算**: 0.5h

```yaml
multi_period_validation:
  enabled: true
  fail_fast: false
  periods:
    - name: "2017_2018_去杠杆"
      train: ["2015-01-01", "2016-12-31"]
      valid: ["2017-01-01", "2017-06-30"]
      test: ["2017-07-01", "2018-12-31"]
    - name: "2019_2020_结构牛"
      train: ["2017-01-01", "2018-12-31"]
      valid: ["2019-01-01", "2019-06-30"]
      test: ["2019-07-01", "2020-12-31"]
    - name: "2021_2022_震荡熊"
      train: ["2019-01-01", "2020-12-31"]
      valid: ["2021-01-01", "2021-06-30"]
      test: ["2021-07-01", "2022-12-31"]
    - name: "2023_2025_复苏"
      train: ["2021-01-01", "2022-12-31"]
      valid: ["2023-01-01", "2023-06-30"]
      test: ["2023-07-01", "2025-12-26"]
```

**验收**:
- [ ] enabled: true
- [ ] fail_fast: false
- [ ] 4 个时间段覆盖不同市场环境

### T03: 验证配置生效
**估算**: 1h

```bash
# 检查北交所排除
grep -A 5 "stock_filter" configs/backtest.yaml

# 运行回测，检查日志
./run.sh "挖掘日频横截面因子" 2>&1 | grep -i "multi_period\|filter\|bj"

# 检查稳定性分数计算
```

**验收**:
- [ ] 回测日志显示多周期验证
- [ ] 北交所股票被排除
- [ ] 稳定性分数正常计算

---

## 依赖

无前置依赖，可与其他切片并行。
