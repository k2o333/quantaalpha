# S05: 因子生命周期状态机

**Goal:** 实现完整的因子生命周期状态机，支持 active / seasonal / degraded / archived 状态及自动转换规则。
**Demo:** 因子跨周期验证后，系统根据通过周期数自动分配正确的生命周期状态。

## Must-Haves
- `status_rules.py` 或 `library.py` 中实现完整状态转换逻辑:
  - 所有周期通过 → `stable_active`
  - 大部分周期通过 → `seasonal` (附带有效周期标记)
  - 少数周期通过 → `degraded`
  - 全部失败 → `archived`
- `degraded → active` 恢复规则 (重新验证通过时恢复)
- `archived → active` 重新激活规则 (手动触发)
- 因子条目中 `evaluation.status` 支持新增的 `seasonal` 和 `archived` 值
- 单元测试覆盖所有状态转换路径

## Proof Level
- This slice proves: **contract**
- Real runtime required: no
- Human/UAT required: no

## Verification
- `python -m py_compile quantaalpha/factors/status_rules.py`
- `pytest quantaalpha/tests/test_factor_lifecycle.py -v`
- `grep "seasonal\|archived" quantaalpha/factors/status_rules.py` returns >= 4

## Tasks

- [x] **T01: 状态机定义与转换函数实现** `est:30m`
  - Why: 状态机逻辑是本 Slice 核心
  - Files: `quantaalpha/factors/status_rules.py`
  - Do: 定义状态枚举、转换条件函数 `determine_lifecycle_status(period_results)` 和 `transition_status(current, trigger)`；实现 seasonal 有效周期标记
  - Verify: py_compile 通过
  - Done when: 所有状态转换路径有对应函数

- [x] **T02: 集成到 library.py + 单元测试** `est:25m`
  - Why: 状态机需要接入因子库的实际流程
  - Files: `quantaalpha/factors/library.py`, `quantaalpha/tests/test_factor_lifecycle.py`
  - Do: 在 apply_validation_result() 中调用状态转换函数；编写覆盖所有路径的测试
  - Verify: pytest 通过
  - Done when: 12+ 测试通过，覆盖所有转换路径

## Files Likely Touched
- `quantaalpha/factors/status_rules.py` (modify)
- `quantaalpha/factors/library.py` (modify)
- `quantaalpha/tests/test_factor_lifecycle.py` (new)

---
estimated_steps: 8
estimated_files: 3
