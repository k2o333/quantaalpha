---
id: T03
parent: S01
milestone: M002
provides:
  - Executable bug reproduction test script
  - Test validates dict-type triggers AttributeError
  - Test validates normalize_corrected_expression() fix approach
  - Complete data flow simulation test
key_files:
  - test/test_dict_replace_bug.py
patterns_established:
  - Bug trigger: dict.replace() raises AttributeError
  - Fix validation: normalize_corrected_expression() converts dict to string
observability_surfaces:
  - Test output: structured pass/fail per test case
  - Exit code: 0 if bug reproduced, 1 if bug not reproduced
duration: ~10m
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: 创建最小复现测试脚本

**执行 `test/test_dict_replace_bug.py` 验证 Bug 可复现**

## What Happened

T03 验证了已创建的测试脚本可以成功复现 `'dict' object has no attribute 'replace'` Bug。测试脚本 `test/test_dict_replace_bug.py` 包含 5 个测试用例，全部通过：

1. **Test 1 (baseline)**: 字符串类型的 expression 正常执行 `replace()` 方法
2. **Test 2 (bug reproduction)**: dict 类型的 expression 触发 `AttributeError: 'dict' object has no attribute 'replace'`
3. **Test 3 (fix validation)**: 验证 `normalize_corrected_expression()` 函数可以将 dict 转换为字符串
4. **Test 4 (data flow simulation)**: 模拟从 LLM 响应到 Bug 触发的完整数据流
5. **Test 5 (edge cases)**: 测试多种 dict 结构变体都能触发 Bug

## Verification

运行了以下验证步骤：

1. **语法检查**: `python -m py_compile test/test_dict_replace_bug.py` → PASS
2. **Bug 复现测试**: `python test/test_dict_replace_bug.py` → PASS (5/5 tests passed)
3. **终端日志诊断**: 确认生产环境中存在相同错误记录

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f test/test_dict_replace_bug.py` | 0 | ✅ pass | <0.01s |
| 2 | `python test/test_dict_replace_bug.py` | 0 | ✅ pass (5/5 tests) | ~0.1s |

## Diagnostics

- **测试脚本位置**: `test/test_dict_replace_bug.py`
- **Bug 位置**: `consistency_checker.py:265` — `expr_clean = expression.replace(" ", "")`
- **错误类型**: `AttributeError: 'dict' object has no attribute 'replace'`
- **修复方案**: 在 `complexity_checker.check()` 调用前应用 `normalize_corrected_expression()`

## Deviations

无偏差。测试脚本已存在（由 T01/T02 创建），T03 验证其可正常执行并成功复现 Bug。

## Known Issues

无。S01 所有任务已完成。

## Files Created/Modified

- `test/test_dict_replace_bug.py` — Bug 复现测试脚本（已存在，T03 验证通过）
- `.gsd/milestones/M002/slices/S01/tasks/T03-PLAN.md` — 更新了 Inputs 和 Observability Impact 部分
- `.gsd/milestones/M002/slices/S01/S01-PLAN.md` — 标记 T03 为完成，添加诊断验证命令

## Next Steps

S01 所有任务完成。S02 将实现类型检查修复：在 `complexity_checker.check()` 调用前调用 `normalize_corrected_expression()`。
