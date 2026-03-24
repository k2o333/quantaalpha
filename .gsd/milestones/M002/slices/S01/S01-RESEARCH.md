# S01: 定位数据类型 Bug 触发位置 Research

**Date:** 2026-03-23
**Updated:** 2026-03-23 (T02 - Complete data flow analysis)

## Summary

定位到触发 `'dict' object has no attribute 'replace'` 的确切代码位置。错误发生在 `consistency_checker.py` 的 `ComplexityChecker.check()` 方法第 265 行，当 `expression` 参数是 dict 类型时触发。

## Bug 位置

**文件**: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
**行号**: 265
**代码**: `expr_clean = expression.replace(" ", "")`
**方法**: `ComplexityChecker.check()`

## 完整数据流向分析

### 数据流调用链（带行号）

```
LLM 返回 JSON 响应
    ↓
consistency_checker.py:114  result_dict.get("corrected_expression")
    ↓ (如果 LLM 返回嵌套 dict)
    ↓ 例如: {"corrected_expression": {"summary": "...", "suggestions": [...]}}
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
consistency_checker.py:265  expr_clean = expression.replace(" ", "")  # 💥 错误!
```

### 关键代码位置详解

#### 1. LLM JSON 响应解析 (consistency_checker.py:114)

```python
result = ConsistencyCheckResult(
    ...
    corrected_expression=result_dict.get("corrected_expression"),  # 行 114
    ...
)
```

**问题**: `result_dict.get("corrected_expression")` 直接从 LLM JSON 获取，如果 LLM 返回嵌套 dict 结构，这里就会得到 dict 类型。

#### 2. check_and_correct() 返回值 (consistency_checker.py:168-172)

```python
if result.corrected_expression and result.corrected_expression != current_expression:
    logger.info(f"Corrected: {result.corrected_expression}")
    current_expression = result.corrected_expression  # 行 172
```

**问题**: `result.corrected_expression` 直接赋值给 `current_expression`，类型未验证。

#### 3. FactorQualityGate.evaluate() 调用 (consistency_checker.py:477-487)

```python
consistency_result, corrected_expr, corrected_desc = self.consistency_checker.check_and_correct(...)
...
results["corrected_expression"] = corrected_expr  # 行 486
...
factor_expression = corrected_expr  # 行 487 (dict!)
...
complexity_passed, complexity_feedback = self.complexity_checker.check(factor_expression)  # 行 489
```

**问题**: `factor_expression` 可能是 dict，但在调用 `complexity_checker.check()` 前未进行类型检查。

#### 4. 错误触发点 (consistency_checker.py:265)

```python
expr_clean = expression.replace(" ", "")  # 行 265
```

**问题**: `expression` 可能是 dict 类型，dict 没有 `.replace()` 方法。

### 终端日志证据

文件: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt`

```
2026-03-21 21:47:50.607 | INFO     | LLM Response:
{
  "is_consistent": false,
  "severity": "major",
  "hypothesis_to_description": {...},
  ...
}

2026-03-21 21:47:50.617 | WARNING  | Consistency check error: 'dict' object has no attribute 'replace'
                              at _convert_with_history_limit:544
```

**观察**: LLM 返回的 JSON 中包含复杂嵌套结构，`corrected_expression` 字段可能包含 dict 而非简单字符串。

## 根因总结

| 步骤 | 位置 | 问题 |
|------|------|------|
| 1 | LLM 返回 JSON | 可能返回嵌套 dict 结构的 `corrected_expression` |
| 2 | consistency_checker.py:114 | 直接使用 `result_dict.get("corrected_expression")`，未类型检查 |
| 3 | consistency_checker.py:172 | dict 类型继续传递到 `current_expression` |
| 4 | consistency_checker.py:487 | dict 赋值给 `factor_expression` |
| 5 | consistency_checker.py:265 | `expression.replace()` 调用时 dict 无此方法 |

## 已有修复函数但未使用

### normalize_corrected_expression() 存在但位置不对

**定义位置**: proposal.py 第 23-26 行

```python
def normalize_corrected_expression(expression) -> str:
    """Normalize quality-gate corrected expressions to a parser-safe string."""
    if isinstance(expression, dict):
        return expression.get("expression") or str(expression)
    return expression
```

**使用位置**: proposal.py 第 550 行（在 `_convert_with_history_limit` 中）

```python
expr = normalize_corrected_expression(results["corrected_expression"])
```

**问题**: 该函数在 `_convert_with_history_limit` 中调用是在 `quality_gate.evaluate()` 返回之后，而不是在 `FactorQualityGate.evaluate()` 内部调用 `complexity_checker.check()` 之前。

### 正确修复位置

修复应该在以下两个位置之一：

1. **Option A**: `FactorQualityGate.evaluate()` 调用 `complexity_checker.check()` 前（约第 489 行前）
   ```python
   factor_expression = normalize_corrected_expression(corrected_expr)
   ```

2. **Option B**: `ComplexityChecker.check()` 方法内部（约第 265 行前）
   ```python
   if not isinstance(expression, str):
       raise TypeError(f"Expected str, got {type(expression).__name__}")
   ```

## 验证命令

```bash
# 定位所有 corrected_expression 使用
rg -n "corrected_expression" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py

# 确认 normalize_corrected_expression 存在
rg -n "normalize_corrected_expression" third_party/quantaalpha/quantaalpha/factors/proposal.py
```

## T02 验证结果

| 验证项 | 命令/检查 | 结果 |
|--------|-----------|------|
| 数据流分析 | 代码审查 + 终端日志 | ✅ 完成 |
| 根因确认 | LLM 返回 dict 类型 | ✅ 确认 |
| normalize 函数 | 函数存在性检查 | ✅ 存在于 proposal.py:23-26 |
| 函数调用位置 | 检查调用链 | ✅ 发现：函数在 proposal.py:550 调用，但位置不对 |
    ↓
complexity_checker.check(factor_expression)  # factor_expression 是 dict!
    ↓
expression.replace(" ", "")  # 触发 AttributeError!
```

## 根因

LLM 的 JSON 响应中 `corrected_expression` 字段可能返回嵌套 dict 结构：
```json
{
  "corrected_expression": {
    "code": "some_expression",
    "note": "from LLM"
  }
}
```

而代码假设它是字符串类型，导致调用 `.replace()` 方法时抛出 `'dict' object has no attribute 'replace'` 错误。

## 终端日志证据

文件: `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt`
行号: 208
日志:
```
2026-03-21 21:47:50.617 | WARNING  | quantaalpha.factors.proposal:_convert_with_history_limit:544 - Consistency check error: 'dict' object has no attribute 'replace'
```

## 已有防护函数

在 `proposal.py` 中存在 `normalize_corrected_expression()` 函数（第 23-26 行），可以处理 dict 类型：
```python
def normalize_corrected_expression(expression) -> str:
    """Normalize quality-gate corrected expressions to a parser-safe string."""
    if isinstance(expression, dict):
        return expression.get("expression") or str(expression)
    return expression
```

但该函数在 `quality_gate.evaluate()` 内部被调用前未被使用，导致错误直接触发。

## 修复方向

1. **S01（当前）**: 定位 bug，验证触发条件
2. **S02**: 在 `ComplexityChecker.check()` 中添加类型检查，或在 `FactorQualityGate.evaluate()` 调用前使用 `normalize_corrected_expression()`

## Recommendation

在进入 `.replace()` 方法前添加类型检查逻辑，确保 `expression` 是字符串类型。如果类型为 dict，需要先进行类型转换（提取 `dict.get("expression")` 或 `str(dict)`）。

## Implementation Landscape

### Key Files

- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — 包含 bug 的文件
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — 包含 `normalize_corrected_expression()` 函数

### Build Order

1. 定位错误位置 (T01)
2. 分析数据流向 (T02)
3. 创建复现测试 (T03)
4. S02 添加类型检查修复

### Verification Approach

通过构造最小复现用例，确认修复后的代码能够正确处理 dict 类型数据。

## T01 验证结果 (2026-03-23)

### 验证命令

| # | 命令 | 结果 |
|---|------|------|
| 1 | `python -m py_compile consistency_checker.py` | ✅ 语法检查通过 |
| 2 | `rg -n "expression.replace" consistency_checker.py` | ✅ 返回第 265 行 |
| 3 | `python test/test_dict_replace_bug.py` | ✅ Bug 成功复现 |

### 复现测试输出

```
Test 1: Normal string expression (should work)
  ✓ Passed: 'close / open' -> 'close/open'

Test 2: Dict expression (reproducing bug)
  ✓ Bug reproduced: 'dict' object has no attribute 'replace'

Test 3: Validating fix with normalize_corrected_expression()
  ✓ Fix works!

Test 4: Simulating data flow from LLM to bug trigger
  ✓ Bug triggered: 'dict' object has no attribute 'replace'
```

### 结论

T01 完成。所有 must-haves 验证通过：
- ✅ 确认 `complexity_checker.check()` 第 265 行是触发点
- ✅ 确认 `expression` 参数来自 `FactorQualityGate.evaluate()` 的 `factor_expression`
- ✅ 确认调用链完整
