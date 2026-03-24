---
id: T01
parent: S05
milestone: M005
provides:
  - 删除 proposal.py 中指向 proposal.yaml 的死赋值 qa_prompt_dict
  - 归档 proposal.yaml 避免运行时误用
key_files:
  - quantaalpha/factors/proposal.py
  - quantaalpha/factors/prompts/proposal.yaml.archived
key_decisions: []
patterns_established: []
observability_surfaces: none
duration: ~1 min
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T01: 删除死赋值并归档 proposal.yaml

**删除 proposal.py 中指向 proposal.yaml 的死赋值 qa_prompt_dict；归档 proposal.yaml**

## What Happened

定位到 `quantaalpha/factors/proposal.py` 第 159 行的死赋值（指向 `proposal.yaml`）并删除。该行与第 304 行的有效赋值（指向 `prompts.yaml`）功能重复，`proposal.yaml` 从未被运行时使用，但其存在造成维护混淆。删除后 `proposal.yaml` 归档为 `.archived`，保留历史参考。

## Verification

运行了 slice plan 定义的 4 项验证：
- `rg -c "qa_prompt_dict = Prompts" proposal.py` → `1`
- `ls proposal.yaml` → "No such file"（已归档）
- `ls proposal.yaml.archived` → 文件存在
- `python -m py_compile proposal.py` → 退出码 0，语法正确

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -c "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py` | 0 | ✅ pass | <1s |
| 2 | `ls quantaalpha/factors/prompts/proposal.yaml` | 2 | ✅ pass | <1s |
| 3 | `ls quantaalpha/factors/prompts/proposal.yaml.archived` | 0 | ✅ pass | <1s |
| 4 | `python -m py_compile quantaalpha/factors/proposal.py` | 0 | ✅ pass | ~1s |

## Diagnostics

验证剩余赋值位置：第 304 行（删除后行号从 305 变为 304），指向 `prompts.yaml`。

## Deviations

无。

## Known Issues

无。

## Files Created/Modified

- `quantaalpha/factors/proposal.py` — 删除第 159 行死赋值
- `quantaalpha/factors/prompts/proposal.yaml` → `proposal.yaml.archived` — 归档
