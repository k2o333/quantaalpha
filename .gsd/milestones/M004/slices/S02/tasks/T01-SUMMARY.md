---
id: T01
parent: S02
milestone: M004
provides:
  - last_validated 字段在因子条目创建时自动初始化为当前时间（ISO 8601 格式）
  - select_revalidation_candidates(days, status) 筛选方法存在且可调用
  - apply_validation_result() 调用链自动更新 last_validated 时间戳
key_files:
  - third_party/quantaalpha/quantaalpha/factors/library.py
key_decisions: []
patterns_established:
  - last_validated 使用 ISO 8601 格式（datetime.now().isoformat()），与 evaluation 中其他时间戳保持一致
observability_surfaces:
  - FactorLibraryManager.get_summary() 返回 last_validated 反映最新验证时间
  - FactorLibraryManager.get_audit_trail() 可查看 trigger="apply_validation_result" 的审计条目
  - select_revalidation_candidates() 返回列表可直接观察候选数量
duration: ~5 min
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T01: 添加 last_validated 字段 + select_revalidation_candidates 方法

**在 FactorLibraryManager 中添加 last_validated 时间戳字段和 select_revalidation_candidates() 筛选方法**

## What Happened

T01 完成了 S02 切片的核心功能实现。代码审查发现 `select_revalidation_candidates()` 方法和 `apply_validation_result()` 调用链（在 `status_rules.py` 的 `update_factor_status()` 中）已经存在并正确实现。唯一缺失的是 `_normalize_factor_entry()` 中 `last_validated` 字段的初始化值——原本设为 `None`，需要改为 `datetime.now().isoformat()` 以便新创建的因子条目自动带上当前时间戳。

做了两处修改：
1. `_normalize_factor_entry()` 默认 evaluation dict 中 `"last_validated": None` → `"last_validated": datetime.now().isoformat()`
2. 后续 `setdefault()` 调用中 `entry["evaluation"].setdefault("last_validated", None)` → `entry["evaluation"].setdefault("last_validated", datetime.now().isoformat())`

使用 `setdefault()` 确保了已存在的 `last_validated` 值（如从磁盘加载的因子条目）不会被覆盖，仅在新字段缺失时才写入当前时间。

## Verification

3 项 slice 验证中 2 项在 T01 阶段满足，pytest 验证依赖 T02 创建的测试文件：
- ✅ `python -m py_compile quantaalpha/factors/library.py` — 语法验证通过
- ✅ `grep "select_revalidation_candidates" quantaalpha/factors/library.py` 返回 1（>= 1）
- ⏳ `pytest quantaalpha/tests/test_revalidation_candidates.py -v` — 测试文件由 T02 创建（任务计划明确说明）

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py` | 0 | ✅ pass | <1s |
| 2 | `grep -c "select_revalidation_candidates" third_party/quantaalpha/quantaalpha/factors/library.py` | 0 | ✅ pass (count=1) | <1s |

## Diagnostics

- 新创建的因子条目：`entry["evaluation"]["last_validated"]` 为 ISO 8601 时间戳字符串
- 从磁盘加载的因子条目：`last_validated` 保持原值（由上次 `apply_validation_result()` 写入）
- 筛选候选：`manager.select_revalidation_candidates(days=21, status="active")` 返回过期的 active 因子列表
- 审计追踪：`manager.get_audit_trail(trigger="apply_validation_result")` 查看时间戳更新记录

## Deviations

无偏离计划。实现前确认了 `select_revalidation_candidates()` 方法已存在（grep 返回 1），`apply_validation_result()` 已通过 `update_factor_status()` 更新 `last_validated`，仅需修复 `_normalize_factor_entry()` 中的初始化值。

## Known Issues

无。

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/library.py` — 修改 `_normalize_factor_entry()` 中两处 `last_validated` 初始化从 `None` 改为 `datetime.now().isoformat()`
