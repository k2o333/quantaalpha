# S05: 移除 proposal.yaml prompt 配置歧义

**Goal:** `proposal.py` 中无 `qa_prompt_dict` 遮蔽；所有 prompt 查找均指向单一有效配置文件 `prompts.yaml`。

**Demo:** After this: `proposal.yaml` 被归档为 `.archived`；`proposal.py` 仅含一个 `qa_prompt_dict` 赋值（指向 `prompts.yaml`）；`grep "qa_prompt_dict = Prompts" proposal.py` 返回 1 行。

## Must-Haves

- `quantaalpha/factors/proposal.py` 中第 159 行的死赋值 `qa_prompt_dict = Prompts(..., "proposal.yaml")` 被删除
- `quantaalpha/factors/prompts/proposal.yaml` 被归档为 `proposal.yaml.archived`
- 两份改动均通过 Python 语法检查

## Verification

- `rg -c "qa_prompt_dict = Prompts" quantaalpha/factors/proposal.py` returns `1`
- `ls quantaalpha/factors/prompts/proposal.yaml` → `No such file` (archived, not deleted)
- `ls quantaalpha/factors/prompts/proposal.yaml.archived` → file exists
- `python -m py_compile quantaalpha/factors/proposal.py` → no output / exit 0

## Tasks

- [x] **T01: 删除死赋值并归档 proposal.yaml** `est:5m`
  - Why: 移除配置歧义的唯一实现步骤 — 删除 line 159 的遮蔽赋值并归档无效 YAML
  - Files: `quantaalpha/factors/proposal.py`, `quantaalpha/factors/prompts/proposal.yaml`
  - Do: 用 `sed -i` 删除 line 159（含前导空行）；用 `mv` 将 `proposal.yaml` 归档为 `.archived`；验证语法
  - Verify: `rg -c "qa_prompt_dict = Prompts" proposal.py` = 1；`test -f proposal.yaml.archived`
  - Done when: grep 返回单行赋值，archived 文件存在，py_compile 通过

## Files Likely Touched

- `quantaalpha/factors/proposal.py`
- `quantaalpha/factors/prompts/proposal.yaml`

---
estimated_steps: 3
estimated_files: 2
skills_used:
  - lint
