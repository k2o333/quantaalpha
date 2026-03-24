# T01: 收紧 consistency_prompts.yaml 输出约束

**Slice:** S03 — 收紧 consistency prompt 输出约束
**Milestone:** M005

## Description

Tighten the `consistency_check_system` and `consistency_check_user` prompts in `consistency_prompts.yaml` to explicitly require single-line DSL expressions for the `corrected_expression` field. This closes the root cause of malformed LLM output that downstream parsers cannot handle. S02's `normalize_corrected_expression()` provides defense-in-depth; this task hardens the first-pass prompt constraint.

## Steps

1. Read the current `quantaalpha/factors/regulator/consistency_prompts.yaml` to confirm the exact text of the two sections to modify.
2. In `consistency_check_system`, locate the line inside the **Output Format (JSON):** block that reads:
   `"corrected_expression": "Corrected expression if needed (null if no correction)",`
   Replace it with:
   `"corrected_expression": "A single-line DSL expression only — no markdown, no comments, no assignments, no explanation. E.g. \"RANK(CLOSE)/RANK(OPEN)\". Use null if the expression is already correct.",`
3. In `consistency_check_user`, locate the line:
   `Output your analysis in JSON format.`
   After it, insert a blank line and the new constraint block:
   ```
   **IMPORTANT: `corrected_expression` must be a single-line DSL expression only. No markdown fences, no comments (// or #), no variable assignments (expr = ...), no pseudo-code, no multi-candidate output (Option A/B/C). Use null if no correction is needed.**
   ```
4. Verify YAML syntax is still valid with `python -m yaml -c <file>`.

## Must-Haves

- [ ] `consistency_check_system` output format has the tightened `corrected_expression` field description with explicit "single-line DSL expression only" language
- [ ] `consistency_check_user` has the new `**IMPORTANT:**` constraint block appended after the existing "Output your analysis in JSON format." line
- [ ] YAML file parses without error

## Verification

```bash
# YAML syntax check
python -m yaml -c quantaalpha/factors/regulator/consistency_prompts.yaml && echo "YAML valid"

# Verify system prompt tightened
grep -q "single-line DSL expression only" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "System prompt OK"

# Verify user prompt has constraint block
grep -q "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "User prompt OK"
```

## Inputs

- `quantaalpha/factors/regulator/consistency_prompts.yaml` — the YAML file to modify

## Expected Output

- `quantaalpha/factors/regulator/consistency_prompts.yaml` — modified with tightened prompt constraints
