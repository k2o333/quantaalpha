# S05 Research: 移除 proposal.yaml prompt 配置歧义

## Summary

**What exists:**
- `quantaalpha/factors/proposal.py` — single 827-line module
- `quantaalpha/factors/prompts/proposal.yaml` — prompt config (older version)
- `quantaalpha/factors/prompts/prompts.yaml` — prompt config (current, actively used)
- Vendored copy at `third_party/quantaalpha/quantaalpha/factors/proposal.py` — byte-identical to main copy

**What is broken:**
Line 159 contains dead code that loads `proposal.yaml` into `qa_prompt_dict`. This assignment is immediately shadowed at line 305, where `qa_prompt_dict` is reassigned to `prompts.yaml`. All downstream uses (lines 339–706) reference the second assignment — meaning `proposal.yaml` is **never loaded at runtime**.

## Precise Code Layout

```
proposal.py
├── Line 159 (DEAD):  qa_prompt_dict = Prompts(..., "proposal.yaml")   ← NEVER used
│   (followed by class definitions)
│
├── Line 305:         qa_prompt_dict = Prompts(..., "prompts.yaml")   ← ACTUAL assignment
│
├── Lines 339–706:   ALL downstream uses reference qa_prompt_dict[...], all
│                     pointing to prompts.yaml keys (hypothesis_gen,
│                     hypothesis2experiment, expression_duplication, etc.)
│
└── Vendored copy:    identical to above (diff confirms zero differences)
```

## Root Cause

The original code at line 159 loaded `proposal.yaml`. At some later point, the team migrated to `prompts.yaml` but added the new assignment at line 305 without removing the old one. Python's name resolution means the later assignment wins — the first is dead code. This creates confusion: developers see two YAML files and two `qa_prompt_dict` assignments with no indication which is live.

## What to Fix

1. **Remove the dead assignment at line 159** (both files):
   ```python
   # DELETE THIS LINE:
   qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "proposal.yaml")
   ```
   The class definitions between line 159 and line 305 are unaffected — they do not reference this variable.

2. **Archive `proposal.yaml`** — rename to `proposal.yaml.archived`:
   - It contains older prompt templates without the complexity constraints added to `prompts.yaml`
   - Not loaded at runtime; safe to archive
   - Preserves history if needed for reference

3. **Sync vendored copy** — the two `proposal.py` files are byte-identical; the same single-line deletion applies to both.

## Implementation

Single edit in `proposal.py` (line ~159), applied to both:
```diff
 QlibFactorHypothesis = Hypothesis
-qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "proposal.yaml")
 
 class AlphaAgentHypothesis(Hypothesis):
```

Then archive the YAML file:
```bash
mv quantaalpha/factors/prompts/proposal.yaml quantaalpha/factors/prompts/proposal.yaml.archived
mv third_party/.../factors/prompts/proposal.yaml third_party/.../factors/prompts/proposal.yaml.archived
```

## Verification

| Check | Command | Expected |
|-------|---------|----------|
| No `proposal.yaml` in prompts/ | `ls prompts/` | `proposal.yaml.archived` (not `.yaml`) |
| `qa_prompt_dict` is single assignment | `rg -c "qa_prompt_dict = Prompts" proposal.py` | `1` (only line 305) |
| `proposal.py` syntax valid | `python -m py_compile proposal.py` | No errors |
| All downstream keys exist in `prompts.yaml` | grep each key | All found |
| Both files stay in sync | `diff proposal.py third_party/.../proposal.py` | No differences |

## Downstream Key Audit

All keys accessed by the live `qa_prompt_dict` (lines 339–706):
- `potential_direction_transformation` — prompts.yaml ✅
- `function_lib_description` — prompts.yaml ✅
- `hypothesis_output_format` — prompts.yaml ✅
- `factor_hypothesis_specification` — prompts.yaml ✅
- `hypothesis_gen.system_prompt` — prompts.yaml ✅
- `hypothesis_gen.user_prompt` — prompts.yaml ✅
- `factor_experiment_output_format` — prompts.yaml ✅
- `hypothesis2experiment.system_prompt` — prompts.yaml ✅
- `hypothesis2experiment.user_prompt` — prompts.yaml ✅
- `expression_duplication` — prompts.yaml ✅

All keys exist in `prompts.yaml`. No references to `proposal.yaml` keys remain.

## Effort Assessment

- **Risk:** Low — single dead-line deletion; no runtime behavior changes
- **Scope:** 1 file (proposal.py), 2 locations (main + vendored), 1 archive operation
- **Verification:** Grep + py_compile + diff — all trivially fast

## Relationship to Requirements

- **R020** (P2 — proposal.yaml 被遮蔽造成配置歧义) → ✅ Fixed by removing dead assignment + archiving `proposal.yaml`
