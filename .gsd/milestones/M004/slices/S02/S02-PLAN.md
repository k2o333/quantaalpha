# S02: 因子重验候选选择

**Goal:** 实现 `select_revalidation_candidates(days=21)` 方法，能自动筛选出超过指定天数未验证的 active 因子。
**Demo:** 调用方法返回需要复验的因子列表，每个因子包含 last_validated 时间戳。

## Must-Haves
- 因子条目新增 `last_validated` 时间戳字段（在 `_normalize_factor_entry()` 中初始化）
- `FactorLibraryManager` 新增 `select_revalidation_candidates(days: int, status: str)` 方法
- 筛选逻辑: `now - last_validated > timedelta(days=days)` 且 `evaluation.status == status`
- `apply_validation_result()` 调用时自动更新 `last_validated`
- 单元测试覆盖: 无候选、部分候选、全部候选、不同 status 过滤

## Proof Level
- This slice proves: **contract**
- Real runtime required: no
- Human/UAT required: no

## Observability / Diagnostics
- `select_revalidation_candidates(days=N)` 返回值可通过 `len(result)` 观察候选数量
- `_normalize_factor_entry()` 的 `last_validated` 初始化值可通过 `apply_validation_result()` 后的 `evaluation.last_validated` 验证时间戳格式（ISO 8601）
- `apply_validation_result()` 状态变化时追加审计条目，可通过 `get_audit_trail()` 检查 `trigger="apply_validation_result"` 条目
- `get_summary()` 返回 `last_validated` 字段反映最新验证时间

## Verification
- `python -m py_compile quantaalpha/factors/library.py`
- `pytest quantaalpha/tests/test_revalidation_candidates.py -v`
- `grep "select_revalidation_candidates" quantaalpha/factors/library.py` returns >= 1

## Tasks

- [x] **T01: 添加 last_validated 字段 + select_revalidation_candidates 方法** `est:30m`
  - Why: 核心功能实现
  - Files: `quantaalpha/factors/library.py`
  - Do: 在 _normalize_factor_entry() 中添加 last_validated 默认值；实现筛选方法；在 apply_validation_result() 中更新时间戳
  - Verify: py_compile 通过, grep 方法名
  - Done when: 方法可调用，时间戳自动更新

- [x] **T02: 单元测试** `est:20m`
  - Why: 验证筛选逻辑正确性
  - Files: `quantaalpha/tests/test_revalidation_candidates.py`
  - Do: Mock 因子库数据，测试各种筛选场景
  - Verify: pytest 通过
  - Done when: 8+ 测试通过

## Files Likely Touched
- `quantaalpha/factors/library.py` (modify)
- `quantaalpha/tests/test_revalidation_candidates.py` (new)

---
estimated_steps: 8
estimated_files: 2
