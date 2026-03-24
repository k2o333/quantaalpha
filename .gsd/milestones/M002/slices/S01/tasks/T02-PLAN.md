# T02: 分析数据流向和根因

**Slice:** S01 — 定位数据类型 Bug 触发位置
**Milestone:** M002

## Description

分析数据流向，理解为什么 dict 类型会传入 `ComplexityChecker.check()`。追踪从 LLM 响应到触发错误的全过程。

## Steps

1. **追踪 factor_expression 来源**
   - 阅读 `FactorQualityGate.evaluate()` 方法（约第 458 行）
   - 找到 `factor_expression = corrected_expr` 赋值（约第 486 行）
   - 确认 `corrected_expr` 来自 `consistency_checker.check_and_correct()` 返回值

2. **分析 check_and_correct() 返回值**
   - 阅读 `FactorConsistencyChecker.check_and_correct()` 方法（约第 148 行）
   - 找到 `current_expression = result.corrected_expression` 赋值（约第 172 行）
   - 确认 `result.corrected_expression` 来自 LLM JSON 响应

3. **分析 LLM JSON 响应解析**
   - 阅读 `check_consistency()` 方法（约第 86 行）
   - 找到 `corrected_expression=result_dict.get("corrected_expression")`（约第 114 行）
   - 确认如果 LLM 返回嵌套 dict，`result_dict.get("corrected_expression")` 会返回 dict 类型

4. **阅读终端日志确认错误上下文**
   - 读取 `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt`
   - 找到错误日志行：`Consistency check error: 'dict' object has no attribute 'replace'`
   - 确认错误发生在 `_convert_with_history_limit` 的 consistency check 阶段

5. **更新研究报告**
   - 在 `S01-RESEARCH.md` 中添加数据流分析
   - 包含调用链图示
   - 说明根因：LLM 可能返回嵌套 dict 结构的 `corrected_expression`

## Must-Haves

- [ ] 完成完整数据流分析：从 LLM 响应到触发错误
- [ ] 确认根因：LLM 返回 dict 类型的 `corrected_expression`
- [ ] 确认 `normalize_corrected_expression()` 函数存在但未被调用

## Verification

- `rg -n "corrected_expression" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` 找到所有相关行
- `rg -n "normalize_corrected_expression" third_party/quantaalpha/quantaalpha/factors/proposal.py` 确认函数存在

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — consistency checker 实现
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — 调用者代码
- `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260321_214610.txt` — 终端日志

## Expected Output

- 更新 `S01-RESEARCH.md` 添加数据流分析和根因说明
