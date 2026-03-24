# S05: 移除 proposal.yaml prompt 配置歧义

**Goal:** 删除 proposal.py 里的死代码，消除歧义。
**Demo:** 代码里不再引用 `proposal.yaml`，且该文件被删除/归档。

## Must-Haves
- 删除 `qa_prompt_dict = Prompts(...proposal.yaml)`。
- 删除/归档 `proposal.yaml`。

## Tasks

- [ ] **T01: 清理死代码与冗余文件**

## Files Likely Touched
- `quantaalpha/factors/proposal.py`
- `quantaalpha/factors/prompts/proposal.yaml`
- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
- `third_party/quantaalpha/quantaalpha/factors/prompts/proposal.yaml`
