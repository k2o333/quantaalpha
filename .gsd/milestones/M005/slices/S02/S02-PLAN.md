# S02: 强化 normalize_corrected_expression

**Goal:** 函数 `normalize_corrected_expression()` 能正确处理 dict payload、fenced code blocks、`//` 和 `#` 注释、多行输出、变量赋值伪代码，并提取有效单行 DSL 表达式。

**Demo:** `normalize_corrected_expression("```\nSTD(close/open)\n```")` 返回 `"STD(close/open)"`；`normalize_corrected_expression("factor = STD(close/open)")` 返回 `"STD(close/open)"`（提取 RHS，不删除赋值行）；所有 12 个测试用例通过。

## Must-Haves

- `quantaalpha/factors/proposal.py:23-27` 的 `normalize_corrected_expression` 替换为处理 fenced blocks、// 注释、# 注释、赋值语句、多行输出的强化版本
- `tests/test_normalize_corrected_expression.py` 包含 12 个用例覆盖所有脏字符串模式
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` 存在并与主文件 byte-identical（函数体一致）
- 所有 pytest 测试通过；两份文件语法检查通过；diff 确认两份文件一致

## Proof Level

- **This slice proves:** contract — the normalization function's input/output contract
- **Real runtime required:** no — unit-test isolation via source-level import
- **Human/UAT required:** no

## Verification

- `python -m pytest tests/test_normalize_corrected_expression.py -v` — 12/12 tests pass
- `python -m py_compile quantaalpha/factors/proposal.py` — 无语法错误
- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` — 无语法错误
- `diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py` — 无差异

## Tasks

- [ ] **T01: 替换 normalize_corrected_expression 并创建测试文件** `est:30m`
  - Why: 生产函数需要硬化以处理 LLM 返回的各类脏字符串；测试文件验证所有边界情况
  - Files: `quantaalpha/factors/proposal.py`, `tests/test_normalize_corrected_expression.py`
  - Do: 替换 lines 23-27 的函数体为强化版本（fenced blocks → regex、`//` / `#` 注释剥离、赋值行 RHS 提取、多行取首个 DSL 模式）；创建测试文件通过 exec() 直接加载函数源码
  - Verify: `python -m pytest tests/test_normalize_corrected_expression.py -v`
  - Done when: 12/12 测试通过；py_compile 无错误

- [ ] **T02: 建立 vendored proposal.py 并同步文件** `est:15m`
  - Why: S01 建立了 `log/__init__.py` 的双文件同步；`proposal.py` 同理需要 vendored 副本保持同步
  - Files: `quantaalpha/factors/proposal.py`, `third_party/quantaalpha/quantaalpha/factors/proposal.py`
  - Do: 创建 vendored 目录结构（`factors/`）；复制主 `proposal.py` 到 vendored 路径；确认两份文件 byte-identical
  - Verify: `diff -q quantaalpha/factors/proposal.py third_party/quantaalpha/quantaalpha/factors/proposal.py` 无输出
  - Done when: vendored 文件存在且与主文件完全一致

## Files Likely Touched

- `quantaalpha/factors/proposal.py`
- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
- `tests/test_normalize_corrected_expression.py`

---
estimated_steps: 6
estimated_files: 3
skills_used:
  - test
  - review
  - systematic-debugging
