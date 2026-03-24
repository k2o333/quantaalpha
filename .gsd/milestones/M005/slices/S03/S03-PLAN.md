# S03: 收紧 consistency prompt 输出约束

**Goal:** 在 system prompt 和 user prompt 中强化对输出格式的约束。
**Demo:** 以后 LLM 生成的 consistency check 输出将严格遵守单行规则。

## Must-Haves
- System prompt 包含 "Return ONLY a SINGLE-LINE factor expression." 及其相关约束。
- User prompt 也包含相同的再三叮嘱。

## Tasks

- [ ] **T01: 更新 consistency_prompts.yaml**
  修改 prompt 文件内容。

## Files Likely Touched
- `quantaalpha/factors/regulator/consistency_prompts.yaml`
- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_prompts.yaml`
