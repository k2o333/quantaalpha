# T01: 定位并确认 Bug 触发位置

**Slice:** S01 — 定位数据类型 Bug 触发位置
**Milestone:** M002

## Description

定位 `'dict' object has no attribute 'replace'` 错误的确切代码位置。确认触发点在 `consistency_checker.py` 的 `ComplexityChecker.check()` 方法中。

## Steps

0. **初始化 quantaalpha submodule（如未初始化）**
   - 如果 `third_party/quantaalpha/` 目录为空
   - 执行: `rm -rf third_party/quantaalpha && git clone git@github.com:k2o333/quantaalpha.git third_party/quantaalpha`
   - Checkout 到正确 commit: `cd third_party/quantaalpha && git checkout $(cd ../.. && git ls-tree HEAD third_party/quantaalpha | awk '{print $3}')`
   - 参考 `KNOWLEDGE.md` 中的 "Submodule + Worktree 使用指南"

1. **读取 consistency_checker.py 定位关键代码**
   - 打开 `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
   - 定位 `ComplexityChecker` 类（约第 220 行）
   - 找到 `check()` 方法中第 265 行的 `expression.replace(" ", "")` 调用

2. **确认调用链**
   - `FactorQualityGate.evaluate()` 调用 `complexity_checker.check(factor_expression)`
   - `factor_expression` 来自 `consistency_checker.check_and_correct()` 返回的 `corrected_expr`
   - 如果 LLM 返回的 `corrected_expression` 是 dict 类型，则会触发错误

3. **使用 grep 验证**
   - `rg -n "\.replace\(" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
   - 确认只有第 265 行有 `expression.replace()` 调用

4. **阅读上下文理解参数来源**
   - 查看 `FactorQualityGate.evaluate()` 方法签名
   - 确认 `factor_expression: str` 参数的文档说明
   - 追踪调用者

## Must-Haves

- [ ] 确认 `complexity_checker.check()` 方法第 265 行 `expr_clean = expression.replace(" ", "")` 是直接触发点
- [ ] 确认 `expression` 参数来自 `FactorQualityGate.evaluate()` 的 `factor_expression` 参数
- [ ] 确认调用链：`FactorQualityGate.evaluate()` → `complexity_checker.check()`

## Verification

- `rg -n "expression.replace" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` 返回第 265 行
- `python -c "import sys; sys.path.insert(0, 'third_party/quantaalpha'); from quantaalpha.factors.regulator.consistency_checker import ComplexityChecker; print('Import OK')"` 导入成功

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — Bug 所在文件（需先 clone submodule）

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — 代码审查记录（行号标记）
- 更新 `S01-RESEARCH.md` 添加触发位置章节
