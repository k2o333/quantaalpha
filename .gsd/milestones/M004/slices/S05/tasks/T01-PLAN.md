# T01: 状态机定义与转换函数实现

**Slice:** S05
**Milestone:** M004

## Goal
实现完整的因子生命周期状态机，支持 active / seasonal / degraded / archived 状态及自动转换规则。

## Must-Haves

### Truths
- 状态定义: stable_active, seasonal, degraded, archived
- 转换规则明确:
  - 所有周期通过 → stable_active
  - 大部分周期通过 → seasonal
  - 少数周期通过 → degraded
  - 全部失败 → archived
- `determine_lifecycle_status(period_results)` 函数实现
- `transition_status(current, trigger)` 函数实现

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py` — 状态机实现

### Key Links
- S05/T02 集成测试依赖本任务完成的状态机函数
- S02 的 `last_validated` 字段用于状态转换判断
- S03 的 `tags.market_environment` 可能影响 seasonal 判定

## Steps
1. 创建或修改 `status_rules.py`。
2. 定义状态枚举: `LifecycleStatus = Enum("LifecycleStatus", ["stable_active", "seasonal", "degraded", "archived"])`
3. 实现 `determine_lifecycle_status(period_results: List[dict])`:
   - 计算通过周期数
   - 根据 `pass_rate` 返回对应状态
4. 实现 `transition_status(current: str, trigger: str) -> str`:
   - 处理 degraded → active（重新验证通过）
   - 处理 archived → active（手动触发）
5. 实现 seasonal 的有效周期标记存储。
6. 用 `py_compile` 验证语法。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §C.3.4`
- S02 的 `select_revalidation_candidates()` 是状态机触发的前置条件
- seasonal 判定标准（"大部分周期通过"）的阈值可配置
