# S01: 定位数据类型 Bug 触发位置

**Goal:** 定位 `'dict' object has no attribute 'replace'` 错误的确切触发位置和原因
**Demo:** 完成 S01 后，明确知道哪行代码触发错误，理解数据流向，并完成复现脚本

## Must-Haves

- [ ] 定位到 `consistency_checker.py` 中 `ComplexityChecker.check()` 方法里 `expression.replace()` 调用
- [ ] 分析数据流向：LLM 返回 → `result_dict` → `ConsistencyCheckResult` → `check_and_correct()` → `FactorQualityGate.evaluate()` → `complexity_checker.check()`
- [ ] 创建最小复现脚本，验证触发条件

## Proof Level

- This slice proves: **contract** — 代码审查和静态分析确认 bug 位置
- Real runtime required: **no** — 通过日志分析和代码审查可定位
- Human/UAT required: **no**

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — 语法检查通过
- `rg -n "expression.replace" third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — 确认 replace 调用位置
- `python test/test_dict_replace_bug.py` — 运行复现测试脚本
- `cat /home/quan/testdata/aspipe_v4/third_party/facotors/terminal/*.txt | grep "dict.*has no attribute"` — 诊断：确认生产日志中存在该错误（验证真实触发场景）

## Observability / Diagnostics

- Runtime signals: **none** — S01 是静态分析任务
- Inspection surfaces: 终端日志 `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/` 中的错误记录
- Failure visibility: 错误日志 `Consistency check error: 'dict' object has no attribute 'replace'`
- Redaction constraints: **none**

## Integration Closure

- Upstream surfaces consumed: 终端日志、consistency_checker.py 源码
- New wiring introduced in this slice: **none**
- What remains before the milestone is truly usable end-to-end: S02 实现类型检查修复

## Prerequisites

**重要**: 本工作树中的 `third_party/quantaalpha` 是 git submodule，在 worktree 模式下需要手动初始化：

```bash
# 如果目录为空，克隆并 checkout 到正确 commit
rm -rf third_party/quantaalpha
git clone git@github.com:k2o333/quantaalpha.git third_party/quantaalpha
cd third_party/quantaalpha
git checkout $(cd ../.. && git ls-tree HEAD third_party/quantaalpha | awk '{print $3}')
```

参考 `KNOWLEDGE.md` 中的 "Submodule + Worktree 使用指南" 获取详细说明。

## Tasks

- [x] **T01: 定位并确认 Bug 触发位置** `est:30m`
  - Why: 需要精确确认哪行代码触发 `'dict' object has no attribute 'replace'` 错误
  - Files: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
  - Do: 
    1. 读取 `consistency_checker.py` 定位 `ComplexityChecker.check()` 方法
    2. 确认第 265 行 `expr_clean = expression.replace(" ", "")` 是触发点
    3. 验证 `expression` 参数来自 `FactorQualityGate.evaluate()` 的 `factor_expression` 参数
  - Verify: `rg -n "\.replace\(" consistency_checker.py` 找到所有 replace 调用
  - Done when: 确认 `complexity_checker.check()` 第 265 行是直接触发点

- [x] **T02: 分析数据流向和根因** `est:30m`
  - Why: 需要理解 dict 类型数据从哪里来，为什么会传入
  - Files: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`, `third_party/quantaalpha/quantaalpha/factors/proposal.py`
  - Do:
    1. 追踪 `factor_expression` 来源：从 `FactorQualityGate.evaluate()` 的参数
    2. 分析 `check_and_correct()` 返回的 `corrected_expr` 如何赋值给 `factor_expression`
    3. 确认 LLM 返回的 JSON 可能包含嵌套 dict 结构的 `corrected_expression`
    4. 阅读终端日志 `20260321_214610.txt` 确认错误上下文
  - Verify: 文档化数据流图和根因分析
  - Done when: 完成 `S01-RESEARCH.md` 中的数据流分析和根因说明

- [x] **T03: 创建最小复现测试脚本** `est:30m`
  - Why: 需要一个可执行的测试用例来验证触发条件
  - Files: `test/test_dict_replace_bug.py` (新文件)
  - Do:
    1. 创建测试脚本，模拟 LLM 返回 dict 类型的 `corrected_expression`
    2. 调用 `ComplexityChecker.check()` 验证错误触发
    3. 验证 `normalize_corrected_expression()` 函数的存在和逻辑
    4. 运行测试确保复现成功
  - Verify: `python test/test_dict_replace_bug.py` 输出 "Bug reproduced: 'dict' object has no attribute 'replace'"
  - Done when: 测试脚本可运行并成功复现错误

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py` — Bug 位置
- `test/test_dict_replace_bug.py` — 新增复现测试

---

estimated_steps: 8
estimated_files: 3
skills_used:
  - systematic-debugging
  - test
