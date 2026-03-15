# 统一股票池过滤入口

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Outcome: pending
Phase: 1
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## Background

当前 QuantaAlpha 的股票池定义分散在数据加载、标签生成、因子计算和组合回测链路中，容易出现同一实验不同阶段使用了不同 `universe` 的问题。最直接的风险不是“报错”，而是静默地产生不可复现结果。

首个要解决的问题不是增加更多过滤条件，而是把股票池解析收敛到一个统一入口。

---

## Goal

建立统一的股票池解析与过滤入口，确保以下链路使用同一份已解析的股票集合：

- label 计算
- factor 加载或计算
- dataset 构建
- portfolio backtest

同时把最终生效的股票池规则写入结果元数据，支持复盘与审计。

---

## Non-goals

- 不实现动态股票池轮换。
- 不重构 Qlib 原生数据加载器。
- 不改变现有回测算法、调仓逻辑或评价指标。
- 不在首版支持行业、市值、流动性等高维筛选器。

---

## Acceptance Criteria

1. 配置可显式启用或关闭统一股票池过滤。
2. 训练、验证、测试、回测阶段看到的股票集合一致。
3. 结果文件中能看到实际生效的 `stock_filter` 规则和过滤后股票数量。
4. 未配置过滤规则时，行为与当前版本兼容。

---

## Design Decision

### 统一入口

在 `quantaalpha/backtest/runner.py` 内新增统一入口，而不是在各子步骤各自判断：

- `_resolve_stock_universe()`: 读取基础市场 universe。
- `_apply_stock_filters()`: 对 universe 应用过滤规则。
- `_attach_universe_metadata()`: 将规则与样本数量写入结果。

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

### 输出元数据

```python
{
    "universe": {
        "market": "csi300",
        "filter_enabled": True,
        "rules": {
            "exclude_markets": ["bj"],
            "exclude_st": True,
            "min_list_days": 60,
        },
        "instrument_count_before": 300,
        "instrument_count_after": 274,
    }
}
```

### 首版约束

- `exclude_markets` 统一使用小写市场简称，例如 `bj`。
- `exclude_st` 基于股票名称或状态字段判断，具体取决于当前数据可用字段。
- `min_list_days` 必须只依赖当前截面可知信息，不能引入未来函数。

---

## Affected Modules

- `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- `third_party/quantaalpha/configs/backtest.yaml`
- 如需共享工具，可新增 `third_party/quantaalpha/quantaalpha/backtest/universe.py`

---

## Implementation Plan

1. 在 `runner.py` 增加统一的股票池解析入口，并让 dataset 构建和 backtest 共用其返回结果。
2. 在配置文件中加入 `data.stock_filter`，默认 `enabled: false`，保证兼容旧行为。
3. 将过滤前后样本数量和规则写入 metrics 或输出 JSON。
4. 为缺失字段场景增加保守降级策略，例如 ST 字段缺失时给出警告并跳过该过滤器。
5. 为所有过滤器补上可独立测试的纯函数，避免把逻辑埋在 I/O 代码里。

---

## Test Plan

### 单元测试

1. `enabled=false` 时返回的股票集合与旧逻辑一致。
2. `exclude_markets=["bj"]` 时，结果中不包含 `.BJ` 或等价市场标记。
3. `exclude_st=true` 时，只在具备 ST 判定字段时生效，缺字段则返回明确告警。
4. `min_list_days=60` 时，上市未满 60 天标的会被排除。

### 集成测试

5. label、feature、backtest 三处使用的股票集合完全一致。
6. 配置开启过滤后，回测输出包含 `universe` 元数据。
7. 配置关闭过滤后，老的回测命令无需改动即可继续运行。

### 手工验收

8. 选一个包含北交所和 ST 股票的数据区间，验证过滤前后样本数量变化符合预期。

---

## Risk Points

1. 如果过滤逻辑在训练集和测试集使用不同时间点信息，可能引入未来函数。
2. 如果把过滤写死在数据加载器内部，后续多周期验证会很难复用。
3. 过滤条件过严时，股票池可能小到影响模型训练稳定性。

---

## Rollback Plan

- 通过 `data.stock_filter.enabled: false` 完全关闭新逻辑。
- 保留旧路径，直到新旧结果完成对比。
- 若过滤器实现有争议，可先只保留统一入口，不启用具体过滤条件。

---

## Final Result

> 待实施后填写

---

## Validation Evidence

> 待实施后填写

---

## Lessons Learned

> 待实施后填写
