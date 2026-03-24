# S05: 移除 proposal.yaml prompt 配置歧义

**Milestone:** M005
**Completed:** 2026-03-24
**Status:** ✅ Validated

## Goal

移除 `proposal.py` 中 `qa_prompt_dict` 的死赋值遮蔽，消除 prompt 配置歧义，确保所有 prompt 查找均指向单一有效配置文件 `prompts.yaml`。

## What Was Delivered

### T01: 删除死赋值并归档 proposal.yaml

**Changes:**
1. **proposal.py** — 删除第 159 行的死赋值 `qa_prompt_dict = Prompts(..., "proposal.yaml")`
2. **proposal.yaml** → **proposal.yaml.archived** — 归档而非删除，保留历史参考

**Verification Results (all passed):**

| Check | Command | Expected | Actual | Status |
|-------|---------|----------|--------|--------|
| 1 | `rg -c "qa_prompt_dict = Prompts" proposal.py` | 1 | 1 | ✅ |
| 2 | `ls proposal.yaml` | No such file | No such file | ✅ |
| 3 | `ls proposal.yaml.archived` | exists | exists | ✅ |
| 4 | `python -m py_compile proposal.py` | exit 0 | exit 0 | ✅ |

**Key Finding:** 原第 159 行死赋值与第 304 行有效赋值（指向 `prompts.yaml`）功能重复。`proposal.yaml` 从未被运行时使用，但其存在造成维护混淆。

## Patterns Established

- **归档而非删除**: 废弃配置文件归档为 `.archived` 而非直接删除，保留历史参考价值
- **单一配置源**: 消除重复的 prompt 配置指向，运行时应始终使用 `prompts.yaml`

## What the Next Slice Should Know

- **无运行时依赖**: `proposal.yaml` 从未被 `proposal.py` 实际使用，删除不影响功能
- **配置文件位置**: `quantaalpha/factors/prompts/prompts.yaml` 是唯一的有效 prompt 配置文件
- **归档文件**: `proposal.yaml.archived` 保留在原位置，可供历史参考

## Boundary Map

```
S05 → (无下游消费)
独立 slice，无后续 slice 依赖
```
