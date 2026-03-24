# S03: 收紧 consistency prompt 输出约束

**Completed:** 2026-03-24  
**Milestone:** M005 (Mining Pipeline 关键 Bug 修复)  
**Task Count:** 1  
**Verification:** All 3 checks passed

---

## What This Slice Delivered

Tightened the `corrected_expression` output constraints in `consistency_prompts.yaml` to explicitly require single-line DSL expressions and forbid common LLM output malformation patterns.

### Changes Made

| File | Change |
|------|--------|
| `quantaalpha/factors/regulator/consistency_prompts.yaml` | System prompt: tightened `corrected_expression` field; User prompt: added `**IMPORTANT:**` constraint block |

### Specific Modifications

**System Prompt (`consistency_check_system`):**
- Replaced vague `"Corrected expression if needed (null if no correction)"` with explicit:
  ```
  "A single-line DSL expression only — no markdown, no comments, no assignments, 
  no explanation. E.g. \"RANK(CLOSE)/RANK(OPEN)\". Use null if the expression 
  is already correct."
  ```

**User Prompt (`consistency_check_user`):**
- Added after "Output your analysis in JSON format.":
  ```
  **IMPORTANT: `corrected_expression` must be a single-line DSL expression only. 
  No markdown fences, no comments (// or #), no variable assignments (expr = ...), 
  no pseudo-code, no multi-candidate output (Option A/B/C). Use null if no 
  correction is needed.**
  ```

---

## Patterns Established

1. **Single-line-only DSL constraint format**: `corrected_expression` description now includes explicit enumeration of forbidden patterns (markdown, comments, assignments, explanations)
2. **IMPORTANT constraint block**: A bold block appended to user prompts that summarizes critical constraints separately from the main instruction

---

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| YAML Syntax | `python -c "import yaml; yaml.safe_load(open(...))"` | ✅ PASS |
| System Prompt | `grep -q "single-line DSL expression only"` | ✅ PASS |
| User Prompt | `grep -q "IMPORTANT:"` | ✅ PASS |

---

## Downstream Impact

- S03 is independent — no downstream slices consume its output
- R017 (prompt-constraint requirement) is now validated by this work

---

## What Future Slices Should Know

1. **Vendored directory missing**: `third_party/quantaalpha/quantaalpha/factors/regulator/` does not exist in this worktree. The prompt file lives in the primary `quantaalpha/` directory only.
2. **Static file change**: No runtime observability needed — this is a prompt hardening change verified at edit time.

---

## Relationship to Other Slices

- **Depends on:** S01 (logger compatibility) — no code dependency, but consistent with the M005 "prompt hardening" theme
- **Enables:** None (independent slice)
- **Complements:** S02 (normalize_corrected_expression) — S02 hardens the parsing side, S03 hardens the generation side

---

## Evidence

T01 verification: 3/3 checks passed in <1s each.
