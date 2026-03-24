---
id: T01
parent: S04
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - render_data_capabilities() output visible in LLM prompts
  - get_data_capabilities() registry accessible for inspection
  - auto_discover_capabilities() log-free (returns empty if path unreadable)
---

# T01: 扩展 auto_discover_capabilities() + render_data_capabilities()

**Status:** Completed

## Outcome

`data_capability.py` 扩展完成，新增：
- `available_from` 字段（数据起始日期）
- `join_mode` 字段（same_day / forward_fill，从 freq 推断）
- `auto_discover_capabilities()` 函数（扫描 Parquet 推断起始日期）
- `infer_available_from_from_parquet()` 辅助函数（防御性实现，异常返回 None）
- `_FREQ_TO_JOIN_MODE` 映射表（freq → 默认 join_mode）

## Implementation Details

**字段推断逻辑：**
- `available_from`: 在 `DATA_CAPABILITIES` 中硬编码已知起始日期；`auto_discover_capabilities()` 可从 Parquet 动态推断
- `join_mode`: 显式设置优先；未设置时根据 freq 推断（daily/weekly → same_day，quarterly/monthly/annual → forward_fill）

**render_data_capabilities() 输出样例：**
```
- financial: fields=$roa, $roe, $net_profit_margin; freq=quarterly; lag_days=45;
  available_from=2008-01-01; join_mode=forward_fill; typical_uses=quality, value
- price_volume: fields=$open, $close, $high, $low, $volume, $amount; freq=daily;
  lag_days=0; available_from=2010-01-01; join_mode=same_day;
  typical_uses=momentum, reversal, volatility, liquidity
```

**防御性设计：**
- `infer_available_from_from_parquet()` 使用 try/except 包裹，polars 不可用或文件损坏时返回 None
- `auto_discover_capabilities()` 对不存在路径返回原始 registry，不抛异常

## Verification Evidence

| Gate | Command | Exit | Result |
|------|---------|------|--------|
| Syntax | `python -m py_compile quantaalpha/factors/data_capability.py` | 0 | PASS |
| Fields present | `grep -c "available_from" ...` → 13 | 0 | PASS |
| Fields present | `grep -c "join_mode" ...` → 9 | 0 | PASS |
| Fields present | `grep -c "auto_discover_capabilities" ...` → 1 | 0 | PASS |
| Render output | `python -c "from quantaalpha.factors.data_capability import render_data_capabilities; print(render_data_capabilities())"` | 0 | PASS — both fields visible |

## Diagnostics

```bash
# 查看渲染输出
python -c "from quantaalpha.factors.data_capability import render_data_capabilities; print(render_data_capabilities())"

# 查看 normalized registry
python -c "from quantaalpha.factors.data_capability import get_data_capabilities; import json; print(json.dumps(get_data_capabilities(), indent=2))"

# 测试 auto_discover（无 parquet 时）
python -c "from quantaalpha.factors.data_capability import auto_discover_capabilities; import json; print(json.dumps(auto_discover_capabilities('/tmp'), indent=2))"
```
