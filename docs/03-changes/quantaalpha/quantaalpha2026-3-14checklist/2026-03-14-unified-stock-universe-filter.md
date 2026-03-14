# 统一股票池过滤入口

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 1
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 QuantaAlpha 系统中，股票池过滤逻辑分散在多个位置：
- label 计算
- factor 加载
- portfolio backtest

这导致可能存在"训练股票池"和"交易股票池"不一致的隐性偏差，影响回测结果的可信度。

---

## Goal

新增统一股票池解析逻辑，确保以下环节使用同一套 universe：
- label 计算
- factor 加载
- portfolio backtest

将实际生效的过滤规则写入实验元数据和回测结果中，实现可追溯、可复现。

---

## Non-goals

- 不在本期实现复杂的动态股票池（如行业轮动、市值分档）
- 不修改现有数据源结构
- 不改变现有回测算法核心逻辑

---

## Acceptance Criteria

1. 能通过配置启用或关闭过滤
2. 训练与回测使用同一 universe
3. 回测结果可复现，元数据中有完整过滤规则
4. 不出现"训练股票池"和"交易股票池"不一致的隐性偏差

---

## Test Plan

### 单元测试

1. 配置关闭过滤时，股票池数量与现有逻辑一致
2. 配置排除北交所后，股票池数量下降且结果可运行
3. 配置排除 ST 后，训练、预测、回测均不报错

### 集成测试

4. label、factor、backtest 三处使用的股票集合一致
5. 实验输出中能看到生效的 `stock_filter` 配置

---

## Implementation Plan

### 主要修改点

- `quantaalpha/backtest/runner.py`
- `configs/backtest.yaml`

### 建议新增方法

```python
_resolve_stock_universe()
_apply_stock_filters()
```

### 配置结构

```yaml
data:
  market: "csi300"
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]
    exclude_st: true
    min_list_days: 60
```

### 首版过滤条件

- `exclude_markets` - 排除指定市场（如北交所）
- `exclude_st` - 排除 ST 股票
- `min_list_days` - 最低上市天数要求

---

## Risk Points

1. 历史回测结果与新版过滤结果不一致，需明确标注版本差异
2. 过滤条件过于严格可能导致股票池过小
3. 需要确保过滤逻辑不会引入未来函数

---

## Rollback Plan

- 通过配置 `stock_filter.enabled: false` 可完全禁用新逻辑
- 不删除原有过滤代码，仅新增统一入口
- 配置项向下兼容，未配置时行为与旧版一致

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
