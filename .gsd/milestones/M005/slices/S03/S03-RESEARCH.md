# S03: 收紧 consistency prompt 输出约束 — Research

## Summary

**Problem:** `consistency_check_system` and `consistency_check_user` prompts do not explicitly constrain the `corrected_expression` field, allowing LLM to emit multi-line, commented, assigned, or pseudo-code expressions that downstream parsers reject.

**Current state of `consistency_check_system` output format block:**
```json
{
  "corrected_expression": "Corrected expression if needed (null if no correction)",
  ...
}
```
No constraint that `corrected_expression` must be a single-line DSL expression. No prohibition on markdown, comments, assignments, or multi-candidate output.

**Fix:** Add explicit `corrected_expression` field constraints to both prompts.

---

## What to Change

### File
`/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/regulator/consistency_prompts.yaml`

(Only copy in vendored `third_party/quantaalpha`. No separate `quantaalpha/` copy exists in worktree — `consistency_prompts.yaml` is not present in `.gsd/worktrees/M005/quantaalpha/`.)

### Change 1: `consistency_check_system` — tighten output format

In the `**Output Format (JSON):**` section, replace the loose `corrected_expression` field description with:

```yaml
    "corrected_expression": "A single-line DSL expression only — no markdown, no comments, no assignments, no explanation. E.g. \"RANK(CLOSE)/RANK(OPEN)\". Use null if the expression is already correct."
```

### Change 2: `consistency_check_user` — add output constraint section

After the existing `Output your analysis in JSON format.` line, add:

```
**IMPORTANT: `corrected_expression` must be a single-line DSL expression only. No markdown fences, no comments (// or #), no variable assignments (expr = ...), no pseudo-code, no multi-candidate output (Option A/B/C). Use null if no correction is needed.**
```

### Verification
- `python -m py_compile` on any Python files that import from the yaml (no Python code changes, just YAML)
- After the change, grep for the tightened constraint text in the yaml file

---

## Forward Intelligence

1. **LLM can still ignore constraints.** S02's `normalize_corrected_expression()` provides a defense-in-depth fallback that strips markdown fences, comments, and assignment RHS extraction. The prompt tightening is a first-pass guard; S02 is the safety net.

2. **No Python code changes needed.** This slice only touches the YAML prompts file. No downstream Python code needs to be modified.

3. **The `expression_correction_system/user` prompts also emit `corrected_expression`** — they should be tightened too, but the roadmap is scoped to `consistency_check_system/user`. See Deferred Ideas in M005-CONTEXT.

4. **Two copies of `consistency_prompts.yaml` are not needed.** Unlike `proposal.py` (which has a main + vendored copy requiring sync), `consistency_prompts.yaml` only exists in `third_party/quantaalpha`. The path `quantaalpha/factors/regulator/consistency_prompts.yaml` in the roadmap refers to the vendored location.
