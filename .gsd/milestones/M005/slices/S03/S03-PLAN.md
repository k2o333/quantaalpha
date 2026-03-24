# S03: 收紧 consistency prompt 输出约束

**Goal:** `consistency_check_system` and `consistency_check_user` prompts explicitly require single-line DSL expressions for `corrected_expression`, forbidding markdown, comments, assignments, pseudo-code, and multi-candidate output.

**Demo:** After this slice, the YAML prompts contain explicit single-line-only constraints for `corrected_expression` in both the system and user prompts.

## Must-Haves

- `consistency_check_system` output format description tightens `corrected_expression` to: single-line DSL only, no markdown, no comments, no assignments, no explanation, null if already correct
- `consistency_check_user` prompt appends an `**IMPORTANT:**` constraint block requiring single-line DSL only for `corrected_expression`

## Verification

- `python -m yaml -c quantaalpha/factors/regulator/consistency_prompts.yaml` — YAML is valid
- `grep -q "single-line DSL expression only" quantaalpha/factors/regulator/consistency_prompts.yaml` — system prompt tightened
- `grep -q "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml` — user prompt has new constraint block

## Tasks

- [x] **T01: 收紧 consistency_prompts.yaml 输出约束** `est:15m`
  - Why: Directly hardens the prompts that produce `corrected_expression`, closing the root cause of malformed output.
  - Files: `quantaalpha/factors/regulator/consistency_prompts.yaml`
  - Do: Edit the YAML file to make two targeted changes:
    1. In `consistency_check_system`, replace the `corrected_expression` line in the **Output Format (JSON):** block with the tightened description.
    2. In `consistency_check_user`, after the `Output your analysis in JSON format.` line, append the `**IMPORTANT:**` constraint block.
  - Verify: `python -m yaml -c <file>` + `grep` for tightened constraint text
  - Done when: Both `consistency_check_system` and `consistency_check_user` contain the new constraints; YAML parses without error.

## Files Likely Touched

- `quantaalpha/factors/regulator/consistency_prompts.yaml`

---
estimated_steps: 4
estimated_files: 1
skills_used:
  - review
  - lint
