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
