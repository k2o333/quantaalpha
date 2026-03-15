# 最小版数据能力注册表

Status: completed
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: partial
Phase: 1
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前数据能力描述散落在 prompt、说明文字和少量工具函数里，同一类数据在不同任务中的表述不一致。对人来说这会增加维护成本，对模型来说则会制造“能力边界不清”的问题。

首版不需要做复杂的数据目录治理，只要先把“系统到底能提供什么字段、频率、滞后和适用场景”沉淀成结构化注册表。

---

## Goal

建立一份最小版数据能力注册表，供 hypothesis 生成、因子构造和评估环节复用：

- 统一数据能力描述来源
- 用结构化方式注入 prompt 或场景上下文
- 让新增数据维度只需改一处定义

---

## Non-goals

- 不实现数据血缘追踪。
- 不实现数据质量监控或 freshness 审计。
- 不改变现有 Qlib 数据加载逻辑。
- 不在首版做自动字段发现。

---

## Acceptance Criteria

1. 数据能力描述来自统一注册表，而不是散落在多个 prompt 片段里。
2. 未启用注册表时，旧逻辑仍可工作。
3. prompt 中能稳定看到字段、频率、滞后、对齐方式和典型用途。
4. 新增一个数据维度时，只需修改注册表定义和对应渲染逻辑。

---

## Design Decision

### 注册表结构

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
        "lag_days": 45,
        "join_mode": "forward_fill",
        "factor_hints": ["quality", "value"],
    },
}
```

### 建议字段

| 字段 | 说明 |
|------|------|
| `fields` | 对模型可见的字段列表 |
| `freq` | 数据频率 |
| `lag_days` | 估计可用滞后 |
| `join_mode` | 与日频行情对齐方式 |
| `factor_hints` | 适合构造的典型因子方向 |

### 渲染原则

- prompt 使用渲染后的说明文本，不直接暴露 Python 字典字符串。
- 对模型可见的描述必须和真实可取字段一致。
- 长度受控，避免把无关字段全部灌进 prompt。

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/factors/qlib_utils.py`
- `third_party/quantaalpha/quantaalpha/factors/experiment.py`
- 如需新增模块，可使用 `third_party/quantaalpha/quantaalpha/factors/data_capability.py`

---

## Implementation Plan

1. 提取当前散落的数据说明，收敛成统一注册表常量。
2. 提供渲染函数，把注册表转成给模型看的精简文本。
3. 在 `factors/experiment.py` 里把注册表说明注入 hypothesis 或 source-data 场景。
4. 增加 fallback：未配置注册表时继续走旧的 `get_data_folder_intro()` 或等价逻辑。
5. 用最少两个维度完成首版验证，例如 `price_volume` 和 `financial`。

---

## Test Plan

### 单元测试

1. 注册表渲染函数能稳定输出字段、频率、滞后和提示信息。
2. 注册表缺失某个可选字段时，渲染函数会使用保守默认值而不是崩溃。
3. 未启用注册表时，fallback 函数行为与旧版一致。

### 集成测试

4. hypothesis 生成链路可看到注册表渲染后的数据能力说明。
5. 新增一个维度后，prompt 内容随之变化，且无需修改多处 prompt 文件。
6. 注册表内容与真实数据字段不一致时，日志会给出明确告警。

### 手工验收

7. 对比接入前后的 prompt，确认模型收到的是更清晰的数据能力描述而不是更长的噪声文本。

---

## Risk Points

1. 注册表描述如果和真实数据不一致，会系统性误导模型。
2. 注入信息过多会稀释 prompt 重点。
3. 若没有统一渲染函数，后续仍会回到多处重复维护。

---

## Rollback Plan

- 保留旧的数据说明函数作为 fallback。
- 通过配置关闭注册表注入，快速回到旧 prompt。
- 若部分维度描述不稳定，可先只开放已验证的维度。

---

## Final Result

- 已做出最小版数据能力注册表与渲染逻辑。
- 但“把数据能力说明注入 factor coding 主 prompt”这一步没有保留在当前主运行路径。
- 原因是首版接入后放大了 prompt 体积和调试成本，后续排障时已从 `factors/experiment.py` 主链路回退。
- 当前保留结果是：
  - 数据能力注册表代码仍可作为后续复用基础
  - 但默认运行流程不依赖它，不应把它视为当前 prompt 真相来源

---

## Validation Evidence

- 曾完成注册表与渲染逻辑接线。
- 后续在实际运行排障中，为降低 prompt 体积与超时风险，已去掉主链路注入。
- 当前有效运行链路应以实际日志和代码路径为准，而不是以此文档最初设计为准。

---

## Lessons Learned

- “统一描述来源”是对的，但不代表必须进入主 prompt。
- 结构化注册表适合作为后续受控注入的基础，不适合在首版无节制灌入所有场景。
