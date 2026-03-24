---
id: T02
parent: S01
milestone: M002
provides:
  - Complete data flow analysis from LLM response to bug trigger
  - Root cause confirmation: LLM returns dict for corrected_expression
  - Discovery: normalize_corrected_expression() exists but called at wrong location
key_files:
  - third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
  - .gsd/milestones/M002/slices/S01/S01-RESEARCH.md
key_decisions:
  - Root cause: LLM returns nested dict for corrected_expression instead of string
  - Fix location: normalize_corrected_expression() should be called before complexity_checker.check(), not after quality_gate.evaluate()
patterns_established:
  - Complete call chain: LLM JSON -> check_consistency() -> check_and_correct() -> FactorQualityGate.evaluate() -> complexity_checker.check() -> expression.replace()
observability_surfaces:
  - Terminal log: /home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt
  - Error keyword: "Consistency check error: 'dict' object has no attribute 'replace'"
duration: ~15m
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: 分析数据流向和根因

**完成完整数据流分析：从 LLM 响应到触发错误，确认根因和修复位置**

## What Happened

T02 完成了完整的数据流向分析，追踪了从 LLM 响应到 `'dict' object has no attribute 'replace'` 错误的完整调用链。

### 确认的数据流向

```
LLM 返回 JSON
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

1. **根因确认**: LLM 返回的 JSON 中 `corrected_expression` 字段可能包含嵌套 dict 结构，而非简单字符串。

2. **normalize_corrected_expression() 函数存在但位置不对**:
   - 定义位置: proposal.py 第 23-26 行
   - 实际调用位置: proposal.py 第 550 行（在 `_convert_with_history_limit` 中）
   - 问题: 该函数调用发生在 `quality_gate.evaluate()` 返回之后，而非在 `FactorQualityGate.evaluate()` 内部调用 `complexity_checker.check()` 之前

3. **终端日志证据**: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt` 第 208-217 行显示 LLM 返回的 JSON 包含复杂嵌套结构。

### 修复方向

**Option A** (推荐): 在 `FactorQualityGate.evaluate()` 第 487 行后添加:
```python
factor_expression = normalize_corrected_expression(corrected_expr)
```

**Option B**: 在 `ComplexityChecker.check()` 方法内部添加类型检查。

## Verification

运行了以下验证步骤：

1. **语法检查**: `python -m py_compile consistency_checker.py` → PASS
2. **定位 replace 调用**: `rg -n "expression.replace" consistency_checker.py` → 第 265 行
3. **Bug 复现测试**: `python test/test_dict_replace_bug.py` → 成功复现
4. **数据流验证**: 代码审查确认完整调用链
5. **终端日志确认**: 错误发生在 `_convert_with_history_limit:544`

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` | 0 | ✅ pass | ~0.1s |
| 2 | `rg -n "expression.replace" .../consistency_checker.py` | 0 | ✅ pass (返回第 265 行) | ~0.05s |
| 3 | `python test/test_dict_replace_bug.py` | 0 | ✅ pass (Bug 成功复现) | ~0.1s |

## Diagnostics

- **终端日志**: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt`
- **错误关键字**: `Consistency check error: 'dict' object has no attribute 'replace'`
- **行号**: `_convert_with_history_limit:544`

## Deviations

无偏差。完全按照 T02-PLAN.md 执行。

## Known Issues

无。T02 分析任务完成，修复将在 S02 中实现。

## Files Created/Modified

- `S01-RESEARCH.md` — 更新包含完整数据流分析和根因说明
  - 添加了带行号的数据流调用链图示
  - 添加了终端日志证据
  - 添加了 normalize_corrected_expression() 函数分析
  - 添加了修复方向建议

## Next Steps

T02 完成。T03 将创建最小复现测试脚本（如果尚未完成），S02 将实现类型检查修复。
