# 最小版数据能力注册表

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 1
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前数据能力描述分散在多个 prompt 中手工维护：
- hypothesis generator 中临时拼接数据说明
- 不同模块对同一数据维度的描述可能不一致
- 新增数据维度时需要修改多处 prompt

---

## Goal

建立一份结构化的数据能力描述：
- 将其注入 scenario/source-data 侧
- 统一各模块的数据能力认知
- 简化数据维度扩展流程

---

## Non-goals

- 不实现数据血缘追踪
- 不实现数据质量监控
- 不改变现有数据加载逻辑

---

## Acceptance Criteria

1. 模型可见的数据能力描述从"文件说明"升级为"结构化能力说明"
2. 数据能力描述不依赖手工在多个 prompt 中重复维护
3. 对现有 hypothesis/factor 生成流程无破坏性影响

---

## Test Plan

### 单元测试

1. 数据能力注册表渲染函数输出格式正确

### 集成测试

2. scenario 初始化时能注入结构化数据能力说明
3. 未配置注册表时，旧的 `get_data_folder_intro()` 逻辑仍可工作
4. prompt 中能看到字段、频率、滞后等信息
5. 新增数据维度时，只需更新注册表即可被 prompt 感知

---

## Implementation Plan

### 主要修改点

- `quantaalpha/factors/qlib_utils.py`
- `quantaalpha/factors/experiment.py`
- 如有必要，新增 `quantaalpha/factors/data_capability.py`

### 数据结构

```python
DATA_CAPABILITIES = {
    "price_volume": {
        "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": ["momentum", "reversal", "volatility", "liquidity"],
    },
    "financial": {
        "fields": ["$roa", "$roe", "$net_profit_margin"],
        "freq": "quarterly",
        "lag_days": 45,  # 财报披露滞后
        "join_mode": "forward_fill",
        "factor_hints": ["quality", "value"],
    }
}
```

### 首版描述字段

| 字段 | 含义 |
|------|------|
| `fields` | 可用字段列表 |
| `freq` | 数据频率 |
| `lag_days` | 滞后天数 |
| `join_mode` | 对齐方式 |
| `factor_hints` | 适合构造的典型因子类别 |

---

## Risk Points

1. 数据能力描述与实际数据不一致会误导模型
2. 注册表维护成本需要控制
3. prompt 中注入过多信息可能影响生成质量

---

## Rollback Plan

- 保留 `get_data_folder_intro()` 作为 fallback
- 注册表为可选功能，未配置时使用旧逻辑
- 可通过配置禁用注册表注入

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
