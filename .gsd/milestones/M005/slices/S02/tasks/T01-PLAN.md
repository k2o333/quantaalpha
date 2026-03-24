# T01: 替换 normalize_corrected_expression 并创建测试文件

**Slice:** S02 — 强化 normalize_corrected_expression
**Milestone:** M005

## Description

Replace `normalize_corrected_expression` in `quantaalpha/factors/proposal.py` with a hardened multi-pattern handler that strips fenced code blocks, `//` / `#` comments, extracts RHS from variable assignments, handles multi-line input, and falls back to DSL pattern extraction. Create a dedicated test file with 12 test cases covering all documented dirty-string patterns.

## Steps

1. **Read the current function** at `quantaalpha/factors/proposal.py` lines 23-27 to confirm exact content.

2. **Replace the function body** with the following hardened implementation. Replace only the `normalize_corrected_expression` function (lines 23-27), keep everything before and after unchanged:

   ```python
   def normalize_corrected_expression(expression) -> str:
       """Normalize quality-gate corrected expressions to a parser-safe string.
       
       Handles: dict payloads (code/expression key extraction),
       fenced code blocks, // and # comments, variable assignments
       (extracts RHS), multi-line input (picks first DSL line),
       and DSL pattern fallback.
       """
       import re
       
       # Handle non-string inputs
       if not isinstance(expression, str):
           return str(expression)
       
       # Handle dict payloads — extract code or expression key
       # (already handled at call site, but defensive here)
       # If the entire string looks like a JSON dict, try to parse it
       stripped = expression.strip()
       if stripped.startswith("{") and stripped.endswith("}"):
           try:
               parsed = json.loads(stripped)
               if isinstance(parsed, dict):
                   for key in ("code", "expression", "factor", "formula"):
                       if key in parsed:
                           expression = str(parsed[key])
                           break
                   else:
                       expression = str(parsed)
           except (json.JSONDecodeError, ValueError):
               pass  # Fall through to string processing
       
       # Step 1: Strip fenced code blocks (any fence variant)
       text = re.sub(r"```[\w]*\n?.*?```", "", expression, flags=re.DOTALL)
       text = re.sub(r"`([^`\n]+)`", r"\1", text)  # inline code
       
       # Step 2: Process each line
       lines = text.split("\n")
       valid_lines = []
       
       for line in lines:
           line = line.strip()
           if not line:
               continue
           
           # Skip pure comment lines
           if line.startswith("//") or line.startswith("#"):
               continue
           
           # Strip // comments (must be on the same line)
           if "//" in line:
               line = line[:line.index("//")]
               line = line.strip()
               if not line:
                   continue
           
           # Strip # comments
           if "#" in line:
               line = line[:line.index("#")]
               line = line.strip()
               if not line:
                   continue
           
           # Handle variable assignment: extract RHS
           # Match: identifier = expression
           # Valid LHS: starts with letter/underscore, contains only word chars and spaces before =
           assign_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_\s]*?)\s*=\s*(.+)$", line)
           if assign_match:
               lhs = assign_match.group(1).strip()
               rhs = assign_match.group(2).strip()
               # Only extract if LHS looks like a simple variable name (no operators)
               if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", lhs):
                   line = rhs
           
           if line:
               valid_lines.append(line)
       
       # Step 3: Return single-line result
       if not valid_lines:
           # Fallback: extract first DSL pattern FUNC(...) from original text
           dsl_match = re.search(r"\b([A-Z][A-Z_]*)\s*\([^)]+\)", expression)
           if dsl_match:
               return dsl_match.group(0)
           return expression.strip()
       
       # Prefer lines that look like DSL expressions (uppercase func)
       for candidate in valid_lines:
           if re.match(r"^[A-Z][A-Z_]*\s*\(", candidate):
               return candidate
       
       # Fall back to first valid line
       return valid_lines[0]
   ```

   **Important constraints:**
   - Import `json` and `re` inside the function (the module already has `json` imported at top; adding `re` inline is safe)
   - Do NOT delete or modify any other function in the file
   - Keep the function exactly at its current position (lines 23-27, will expand to ~80 lines)

3. **Verify syntax** immediately after the edit:
   ```bash
   python -m py_compile quantaalpha/factors/proposal.py
   ```

4. **Create test file** at `tests/test_normalize_corrected_expression.py` using the following content. The test must load the function by reading its source directly (not via `import`) because `proposal.py` has transitive jinja2 dependencies:
   
   ```python
   """Test normalize_corrected_expression — 12 cases covering all dirty-string patterns."""
   
   import ast
   import re
   import sys
   import os
   
   # ---------------------------------------------------------------------------
   # Load the function by reading its source directly (avoids jinja2 import chain)
   # ---------------------------------------------------------------------------
   PROPOSAL_PATH = os.path.join(os.path.dirname(__file__), "..", "quantaalpha", "factors", "proposal.py")
   
   def load_function_source():
       with open(PROPOSAL_PATH, "r", encoding="utf-8") as f:
           content = f.read()
       tree = ast.parse(content)
       for node in ast.walk(tree):
           if isinstance(node, ast.FunctionDef) and node.name == "normalize_corrected_expression":
               return ast.get_source_segment(content, node) or ""
       raise RuntimeError("normalize_corrected_expression not found in proposal.py")
   
   # Execute the function in isolation
   _func_src = load_function_source()
   exec_globals: dict = {}
   exec(_func_src, exec_globals)
   normalize_corrected_expression = exec_globals["normalize_corrected_expression"]
   
   # ---------------------------------------------------------------------------
   # Test cases
   # ---------------------------------------------------------------------------
   
   def test_dict_with_code_key():
       result = normalize_corrected_expression({"code": "STD(close/open)", "note": "correlation"})
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_dict_with_expression_key():
       result = normalize_corrected_expression({"expression": "STD(close/open)", "extra": "data"})
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_fenced_code_block():
       result = normalize_corrected_expression("```\nSTD(close/open)\n```")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_fenced_with_language_hint():
       result = normalize_corrected_expression("```python\nSTD(close/open)\n```")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_double_slash_comment():
       result = normalize_corrected_expression("STD(close/open) // correlation")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_hash_comment():
       result = normalize_corrected_expression("STD(close/open) # lagged")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_variable_assignment():
       result = normalize_corrected_expression("factor = STD(close/open)")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_variable_assignment_chained():
       result = normalize_corrected_expression("result = RANK(STD(close/open))")
       assert result == "RANK(STD(close/open))", f"Got: {result!r}"
   
   def test_multi_line_first_valid():
       result = normalize_corrected_expression("dispersion = STD(close/open)\nMEAN(volume)")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_pure_comment_then_valid():
       result = normalize_corrected_expression("// Wrong expression\nSTD(close)")
       assert result == "STD(close)", f"Got: {result!r}"
   
   def test_multi_candidate_option_a():
       result = normalize_corrected_expression("Option A: STD(close/open)\nOption B: ZSCORE(close)")
       assert result == "STD(close/open)", f"Got: {result!r}"
   
   def test_whitespace_stripping():
       result = normalize_corrected_expression("  STD(close)  \n")
       assert result == "STD(close)", f"Got: {result!r}"
   
   def test_none_input():
       result = normalize_corrected_expression(None)
       assert result == "None", f"Got: {result!r}"
   
   def test_int_input():
       result = normalize_corrected_expression(42)
       assert result == "42", f"Got: {result!r}"
   
   def test_plain_text_no_dsl():
       result = normalize_corrected_expression("plain text no DSL")
       assert result == "plain text no DSL", f"Got: {result!r}"
   
   def test_fenced_no_valid_inside_extracts_pattern():
       result = normalize_corrected_expression("```\nNo expression here\nSTD(alpha)\n```")
       assert result == "STD(alpha)", f"Got: {result!r}"
   ```

5. **Run the tests:**
   ```bash
   python -m pytest tests/test_normalize_corrected_expression.py -v
   ```
   All 16 tests must pass (12 primary + 4 extras for chained calls, None/int input, plain text pass-through, nested DSL extraction).

## Must-Haves

- [ ] `quantaalpha/factors/proposal.py` 中的 `normalize_corrected_expression` 函数体替换为硬化版本
- [ ] 测试文件 `tests/test_normalize_corrected_expression.py` 存在，包含 ≥12 个用例
- [ ] `python -m py_compile quantaalpha/factors/proposal.py` 无错误
- [ ] `python -m pytest tests/test_normalize_corrected_expression.py -v` 全部通过

## Verification

```bash
python -m py_compile quantaalpha/factors/proposal.py && echo "SYNTAX OK"
python -m pytest tests/test_normalize_corrected_expression.py -v
```

## Inputs

- `quantaalpha/factors/proposal.py` — 函数替换的目标文件

## Expected Output

- `quantaalpha/factors/proposal.py` — `normalize_corrected_expression` 已替换为硬化版本
- `tests/test_normalize_corrected_expression.py` — 16 个测试用例

## Observability Impact

- **Before:** LLM-corrected expressions with fenced blocks, comments, or assignments would pass through unchanged, causing `is_parsable` or `is_expression_acceptable` failures downstream
- **After:** All known dirty-string patterns are normalized; downstream calls in `AlphaAgentHypothesis2FactorExpression._convert_with_history_limit` receive clean DSL strings
- **Failure mode visible:** If the function regresses, `pytest tests/test_normalize_corrected_expression.py` will catch it — the calling code has no structured error output for normalization failures
- **Inspection:** Run `pytest tests/test_normalize_corrected_expression.py -v` to confirm all 16 cases still pass; no other runtime signals are emitted by this pure transform
