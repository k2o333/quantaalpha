---
id: T01
parent: S01
milestone: M002
provides:
  - Confirmed bug trigger location at line 265 in consistency_checker.py
  - Complete call chain mapping from LLM to bug
  - Bug reproduction test script
key_files:
  - third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
  - test/test_dict_replace_bug.py
key_decisions:
  - Bug root cause: LLM returns nested dict for 'corrected_expression' field instead of string
patterns_established:
  - Direct call chain: FactorQualityGate.evaluate() -> complexity_checker.check() -> expression.replace()
observability_surfaces:
  - Terminal logs at /home/quan/testdata/aspipe_v4/third_party/facotors/terminal/ showing error "Consistency check error: 'dict' object has no attribute 'replace'"
duration: ~15m
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: 定位并确认 Bug 触发位置

**确认 `ComplexityChecker.check()` 第 265 行是 `'dict' object has no attribute 'replace'` 错误的确切触发点**

## What Happened

通过代码审查和测试复现，精确确认了 Bug 的触发位置和数据流向：

**Bug 位置**: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` 第 265 行
```python
expr_clean = expression.replace(" ", "")
```

**完整调用链**:
```
LLM 返回 JSON (corrected_expression 可能是 dict)
    ↓
FactorConsistencyChecker.check_consistency() 
    → result_dict.get("corrected_expression") 
    → ConsistencyCheckResult.corrected_expression (可能是 dict)
    ↓
FactorConsistencyChecker.check_and_correct()
    → current_expression = result.corrected_expression (dict)
    ↓
FactorQualityGate.evaluate()
    → factor_expression = corrected_expr (dict)
    ↓
ComplexityChecker.check(factor_expression)  ← 触发点
    → expr_clean = expression.replace(" ", "")  ← 第 265 行，expression 是 dict
    → AttributeError: 'dict' object has no attribute 'replace'
```

**根因**: LLM 的 JSON 响应中 `corrected_expression` 字段可能返回嵌套 dict 结构：
```json
{
  "corrected_expression": {
    "code": "close / open",
    "note": "LLM suggests this form"
  }
}
```

而代码假设它是字符串类型，调用 `.replace()` 方法时抛出错误。

**已有修复函数但未使用**: `proposal.py` 第 23-26 行定义了 `normalize_corrected_expression()` 函数，但在 `FactorQualityGate.evaluate()` 调用 `complexity_checker.check()` 前未被调用。

## Verification

运行了以下验证步骤：

1. **语法检查**: `python -m py_compile consistency_checker.py` → PASS
2. **定位 replace 调用**: `rg -n "expression.replace" consistency_checker.py` → 第 265 行
3. **Bug 复现测试**: `python test/test_dict_replace_bug.py` → 成功复现
4. **终端日志验证**: 找到多处错误记录（如 `20260321_214610.txt:208`）

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` | 0 | ✅ pass | ~0.1s |
| 2 | `rg -n "expression.replace" .../consistency_checker.py` | 0 | ✅ pass (返回第 265 行) | ~0.05s |
| 3 | `python test/test_dict_replace_bug.py` | 0 | ✅ pass (Bug 成功复现) | ~0.1s |

## Diagnostics

- **终端日志**: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/`
- **错误关键字**: `Consistency check error: 'dict' object has no attribute 'replace'`
- **行号**: `_convert_with_history_limit:544` 或 `_convert_with_history_limit:551`

## Deviations

无偏差。完全按照 T01-PLAN.md 执行。

## Known Issues

无。待 S02 实现修复。

## Files Created/Modified

- `test/test_dict_replace_bug.py` — Bug 复现测试脚本，包含：
  - 直接测试 Bug 代码
  - 数据流模拟
  - normalize_corrected_expression() 修复验证
- `S01-RESEARCH.md` — 已存在（由上游任务创建），已包含 Bug 分析内容

## Next Steps

T01 完成。T02 将分析数据流向和根因，T03 将创建完整的复现测试脚本。
