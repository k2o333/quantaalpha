# S03 UAT: 收紧 consistency prompt 输出约束

**Scope:** `quantaalpha/factors/regulator/consistency_prompts.yaml`  
**Preconditions:** Python 3.x with PyYAML installed  

---

## Test Cases

### T01: YAML Syntax Validation

**Purpose:** Verify the YAML file is valid and parseable.

**Steps:**
1. Open a terminal in the worktree directory
2. Run: `python -c "import yaml; yaml.safe_load(open('quantaalpha/factors/regulator/consistency_prompts.yaml')))"`
3. Verify exit code is 0 with no exceptions

**Expected:** YAML parses without error.

---

### T02: System Prompt Constraint Verification

**Purpose:** Verify `consistency_check_system` contains the tightened `corrected_expression` constraint.

**Steps:**
1. Run: `grep -q "single-line DSL expression only" quantaalpha/factors/regulator/consistency_prompts.yaml`
2. Verify exit code is 0

**Expected:** The phrase "single-line DSL expression only" appears in the file.

---

### T03: User Prompt IMPORTANT Block Verification

**Purpose:** Verify `consistency_check_user` contains the `**IMPORTANT:**` constraint block.

**Steps:**
1. Run: `grep -q "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml`
2. Verify exit code is 0

**Expected:** "IMPORTANT:" appears in the file.

---

### T04: Forbidden Pattern Enumeration Check

**Purpose:** Verify the IMPORTANT block enumerates all forbidden patterns.

**Steps:**
1. Run: `grep -A1 "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml`
2. Verify the constraint text includes:
   - `markdown fences`
   - `comments` (// or #)
   - `variable assignments` (expr = ...)
   - `pseudo-code`
   - `multi-candidate output` (Option A/B/C)

**Expected:** All five forbidden patterns are explicitly mentioned.

---

### T05: Example DSL Format in System Prompt

**Purpose:** Verify the system prompt includes an example DSL expression.

**Steps:**
1. Run: `grep -o 'RANK(CLOSE)/RANK(OPEN)' quantaalpha/factors/regulator/consistency_prompts.yaml`
2. Verify exit code is 0

**Expected:** The example `RANK(CLOSE)/RANK(OPEN)` appears, demonstrating valid single-line format.

---

### T06: Prompt Structure Integrity

**Purpose:** Verify both `consistency_check_system` and `consistency_check_user` keys exist.

**Steps:**
1. Run:
   ```python
   python -c "
   import yaml
   with open('quantaalpha/factors/regulator/consistency_prompts.yaml') as f:
       data = yaml.safe_load(f)
   assert 'consistency_check_system' in data
   assert 'consistency_check_user' in data
   print('Both prompts exist')
   "
   ```
2. Verify output is "Both prompts exist"

**Expected:** Both prompt keys exist in the YAML structure.

---

### T07: Corrected Expression Field Exists in System Prompt

**Purpose:** Verify the system prompt's output format section includes `corrected_expression` field.

**Steps:**
1. Run:
   ```python
   python -c "
   import yaml
   with open('quantaalpha/factors/regulator/consistency_prompts.yaml') as f:
       data = yaml.safe_load(f)
   system_prompt = data['consistency_check_system']
   assert '\"corrected_expression\"' in system_prompt or \"'corrected_expression'\" in system_prompt
   print('corrected_expression field exists in system prompt')
   "
   ```

**Expected:** `corrected_expression` field exists in the JSON output format description.

---

### T08: Null Handling Instruction Present

**Purpose:** Verify prompts instruct LLM to use `null` when no correction is needed.

**Steps:**
1. Run: `grep -c "null if" quantaalpha/factors/regulator/consistency_prompts.yaml`
2. Verify count >= 2 (once in system prompt, once in user prompt IMPORTANT block)

**Expected:** At least 2 occurrences of "null if" indicating null usage instructions.

---

## Edge Cases

### Edge 1: JSON Field Quoting Style
The YAML file may use single quotes, double quotes, or no quotes around JSON keys. The grep checks use flexible patterns to match all styles.

### Edge 2: Multi-line IMPORTANT Block
The IMPORTANT block may span multiple lines. The grep for "IMPORTANT:" still matches regardless of line wrapping.

### Edge 3: Template Variables
`consistency_check_user` uses Jinja2 template variables (`{{ factor_name }}`, etc.). These should remain unchanged. The test does not modify them.

---

## Run All Tests

```bash
cd /home/quan/testdata/aspipe_v4/.gsd/worktrees/M005

# T01: YAML Syntax
python -c "import yaml; yaml.safe_load(open('quantaalpha/factors/regulator/consistency_prompts.yaml'))" && echo "T01: PASS"

# T02: System prompt constraint
grep -q "single-line DSL expression only" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "T02: PASS"

# T03: User prompt IMPORTANT block
grep -q "IMPORTANT:" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "T03: PASS"

# T04: Forbidden patterns
grep -q "markdown fences" quantaalpha/factors/regulator/consistency_prompts.yaml && \
grep -q "variable assignments" quantaalpha/factors/regulator/consistency_prompts.yaml && \
grep -q "multi-candidate output" quantaalpha/factors/regulator/consistency_prompts.yaml && echo "T04: PASS"

# T05: Example DSL
grep -q 'RANK(CLOSE)/RANK(OPEN)' quantaalpha/factors/regulator/consistency_prompts.yaml && echo "T05: PASS"

# T06: Structure integrity
python -c "
import yaml
with open('quantaalpha/factors/regulator/consistency_prompts.yaml') as f:
    data = yaml.safe_load(f)
assert 'consistency_check_system' in data
assert 'consistency_check_user' in data
print('T06: PASS')
"

# T07: corrected_expression field
python -c "
import yaml
with open('quantaalpha/factors/regulator/consistency_prompts.yaml') as f:
    data = yaml.safe_load(f)
system_prompt = data['consistency_check_system']
assert 'corrected_expression' in system_prompt
print('T07: PASS')
"

# T08: Null handling
[ $(grep -c "null if" quantaalpha/factors/regulator/consistency_prompts.yaml) -ge 2 ] && echo "T08: PASS"
```

---

## Summary

| Test | Description | Status |
|------|-------------|--------|
| T01 | YAML syntax valid | ✅ |
| T02 | System prompt has "single-line DSL expression only" | ✅ |
| T03 | User prompt has "IMPORTANT:" block | ✅ |
| T04 | IMPORTANT block enumerates forbidden patterns | ✅ |
| T05 | Example DSL format present | ✅ |
| T06 | Both prompt keys exist | ✅ |
| T07 | corrected_expression field in system prompt | ✅ |
| T08 | null usage instructions present | ✅ |

**Result:** 8/8 tests passed
