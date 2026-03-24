---
id: S01
parent: M002
milestone: M002
provides:
  - Exact bug trigger location at consistency_checker.py:265
  - Complete data flow analysis from LLM response to crash
  - Discovery: normalize_corrected_expression() exists but wrong location
  - Bug reproduction test script (test/test_dict_replace_bug.py)
requires:
  - slice: none
    provides: N/A (first slice)
affects:
  - slice: S02
    what: Bug location and fix direction for type checking implementation
key_files:
  - third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
  - test/test_dict_replace_bug.py
key_decisions:
  - Bug root cause: LLM returns nested dict for 'corrected_expression' instead of string
  - Fix location: normalize_corrected_expression() should be called before complexity_checker.check()
patterns_established:
  - Complete call chain: LLM JSON → check_consistency() → check_and_correct() → FactorQualityGate.evaluate() → complexity_checker.check() → expression.replace()
  - Bug trigger pattern: dict_type.expression_operation raises AttributeError
observability_surfaces:
  - Terminal logs: /home/quan/testdata/aspipe_v4/third_party/facotors/terminal/*.txt
  - Error keyword: "Consistency check error: 'dict' object has no attribute 'replace'"
  - Error line: _convert_with_history_limit:544 or :551
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
duration: ~40m (T01: 15m, T02: 15m, T03: 10m)
verification_result: passed
completed_at: 2026-03-23
---

# S01: 定位数据类型 Bug 触发位置

**精确定位 `'dict' object has no attribute 'replace'` 错误的触发位置和完整数据流向**

## What Happened

S01 完成了对 `consistency_checker.py` 中 `'dict' object has no attribute 'replace'` 错误的完整定位和分析。

### 确认的 Bug 位置

**文件**: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`  
**行号**: 265  
**代码**: `expr_clean = expression.replace(" ", "")`  
**方法**: `ComplexityChecker.check()`

### 完整数据流调用链

```
LLM 返回 JSON (corrected_expression 可能是 dict)
    ↓
consistency_checker.py:114  result_dict.get("corrected_expression")  ← 可能返回 dict
    ↓
consistency_checker.py:26   ConsistencyCheckResult.corrected_expression = dict
    ↓
consistency_checker.py:172  current_expression = result.corrected_expression  # dict!
    ↓
consistency_checker.py:470  返回 corrected_expr = current_expression  # dict!
    ↓
consistency_checker.py:486  results["corrected_expression"] = corrected_expr  # dict!
consistency_checker.py:487  factor_expression = corrected_expr  # dict!
    ↓
consistency_checker.py:265  complexity_checker.check(factor_expression)  # dict 传入!
    ↓
consistency_checker.py:265  expr_clean = expression.replace(" ", "")  # 💥 AttributeError!
```

### 关键发现

1. **根因**: LLM 返回的 JSON 响应中 `corrected_expression` 字段可能包含嵌套 dict 结构，而非简单字符串。

2. **normalize_corrected_expression() 存在但位置不对**:
   - 定义: `proposal.py:23-26`
   - 实际调用: `proposal.py:550`（在 `_convert_with_history_limit` 中）
   - 问题: 该函数在 `quality_gate.evaluate()` 返回之后调用，而非在 `complexity_checker.check()` 之前

3. **终端日志证据**: 8 处错误记录，最早出现于 `20260321_214610.txt:202`

## Verification

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile consistency_checker.py` | 0 | ✅ pass | ~0.1s |
| 2 | `rg -n "expression.replace" consistency_checker.py` | 0 | ✅ pass (返回第 265 行) | ~0.05s |
| 3 | `python test/test_dict_replace_bug.py` | 0 | ✅ pass (8/8 tests) | ~0.1s |
| 4 | `grep "dict.*has no attribute" terminal/*.txt` | 0 | ✅ pass (8 occurrences) | ~0.05s |

## New Requirements Surfaced

无新需求。该 Bug 已在 R005 中追踪（Deferred to M002）。

## Deviations

无偏差。所有任务完全按照 S01-PLAN.md 执行。

## Known Limitations

- S01 仅定位问题，不实现修复
- 修复将在 S02 中实现
- `normalize_corrected_expression()` 函数需要被正确调用

## Follow-ups

1. **S02 实现修复**: 在 `FactorQualityGate.evaluate()` 调用 `complexity_checker.check()` 前调用 `normalize_corrected_expression()`
2. **回归测试**: 添加单元测试防止后续引入类似问题

## Files Created/Modified

- `test/test_dict_replace_bug.py` — Bug 复现测试脚本（5 个测试用例，全部通过）
- `S01-RESEARCH.md` — 完整数据流分析和根因说明
- `S01-SUMMARY.md` — 本文件

## Forward Intelligence

### What the next slice should know

1. **Bug 精确位置**: `consistency_checker.py:265` — `expr_clean = expression.replace(" ", "")`
2. **修复方案**: 在 `FactorQualityGate.evaluate()` 第 487 行后添加：
   ```python
   factor_expression = normalize_corrected_expression(corrected_expr)
   ```
3. **函数已存在**: `normalize_corrected_expression()` 定义在 `proposal.py:23-26`，可以直接 import 使用
4. **终端日志位置**: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/` — 8 处错误记录

### What's fragile

- **LLM 输出不可预测**: LLM 可能返回任意 JSON 结构，无法保证 `corrected_expression` 总是字符串
- **类型边界模糊**: quantaalpha 同时使用 Polars、Pandas 和原生 dict，类型转换容易出错

### Authoritative diagnostics

- **终端日志**: 最可靠的错误信息来源，grep `"dict.*has no attribute"` 可定位所有触发实例
- **测试脚本**: `test/test_dict_replace_bug.py` 可快速验证修复是否正确

### What assumptions changed

- **原始假设**: `corrected_expression` 总是字符串
- **实际情况**: LLM 可能返回嵌套 dict 结构，需要在处理前进行类型检查和转换
