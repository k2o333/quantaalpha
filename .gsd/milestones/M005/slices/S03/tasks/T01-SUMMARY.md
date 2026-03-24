---
id: T01
parent: S03
milestone: M005
provides:
  - Tightened consistency_prompts.yaml with explicit single-line DSL constraint
key_files:
  - quantaalpha/factors/regulator/consistency_prompts.yaml
key_decisions:
  - Added explicit "single-line DSL expression only" constraint to system prompt corrected_expression field
  - Added IMPORTANT constraint block to user prompt with exhaustive list of forbidden patterns
patterns_established:
  - Single-line-only DSL expression constraint format for LLM prompt hardening
observability_surfaces:
  - None (static prompt file, no runtime observability needed)
duration: ~2 minutes
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
---

# T01: 收紧 consistency_prompts.yaml 输出约束

**Tightened `corrected_expression` output constraint in both system and user prompts of `consistency_prompts.yaml` to forbid markdown, comments, assignments, pseudo-code, and multi-candidate output.**

## What Happened

Modified `consistency_prompts.yaml` with two targeted changes:

1. **System prompt** — Replaced the vague `"corrected_expression": "Corrected expression if needed (null if no correction)"` with an explicit constraint: `"A single-line DSL expression only — no markdown, no comments, no assignments, no explanation. E.g. \"RANK(CLOSE)/RANK(OPEN)\". Use null if the expression is already correct."`

2. **User prompt** — Added a new `**IMPORTANT:**` constraint block after "Output your analysis in JSON format." that enumerates all forbidden patterns: markdown fences, comments (`//` or `#`), variable assignments (`expr = ...`), pseudo-code, and multi-candidate output (`Option A/B/C`).

## Verification

YAML syntax validated with `yaml.safe_load()`. Both grep checks passed confirming the system prompt contains "single-line DSL expression only" and the user prompt contains "IMPORTANT:".

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -c "import yaml; yaml.safe_load(open('quantaalpha/factors/regulator/consistency_prompts.yaml'))" && echo "YAML valid"` | 0 | ✅ pass | <1s |
| 2 | `grep -q "single-line DSL expression only" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "System prompt OK"` | 0 | ✅ pass | <1s |
| 3 | `grep -q "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "User prompt OK"` | 0 | ✅ pass | <1s |

## Diagnostics

To inspect the updated prompts, run:
```bash
grep -A2 "corrected_expression" quantaalpha/factors/regulator/consistency_prompts.yaml
grep "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml
```

## Deviations

None — implementation matched the task plan exactly.

## Known Issues

None.

## Files Created/Modified

- `quantaalpha/factors/regulator/consistency_prompts.yaml` — Modified `consistency_check_system` output format to tighten `corrected_expression` field description; added `**IMPORTANT:**` constraint block to `consistency_check_user` prompt.
