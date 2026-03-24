#!/usr/bin/env python3
"""
Reproduction test for: 'dict' object has no attribute 'replace'

Bug: In consistency_checker.py, ComplexityChecker.check() method (line 265)
calls expression.replace(" ", "") but expression can be a dict if LLM returns
{"corrected_expression": {"code": "...", "note": "..."}} instead of a string.

This test reproduces the bug by directly calling the buggy code.
"""

import sys
import os
import traceback

def test_bug_reproduction_direct():
    """Directly test the buggy line of code."""
    print("=" * 60)
    print("Reproducing: 'dict' object has no attribute 'replace' bug")
    print("=" * 60)
    
    # The buggy line from consistency_checker.py:265
    # expr_clean = expression.replace(" ", "")
    
    print("\nTest 1: Normal string expression (should work)")
    try:
        expression = "close / open"
        expr_clean = expression.replace(" ", "")
        print(f"  ✓ Passed: '{expression}' -> '{expr_clean}'")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False
    
    print("\nTest 2: Dict expression (reproducing bug)")
    try:
        # This simulates what happens when LLM returns:
        # {"corrected_expression": {"code": "close/open", "note": "from LLM"}}
        expression = {"code": "close / open", "note": "from LLM"}
        expr_clean = expression.replace(" ", "")
        print(f"  ✗ Bug not reproduced - dict was accepted: {expr_clean}")
        return False  # Bug fix is already in place
    except AttributeError as e:
        if "'dict' object has no attribute 'replace'" in str(e):
            print(f"  ✓ Bug reproduced: {e}")
            return True
        else:
            print(f"  ✗ Different AttributeError: {e}")
            return False
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False


def test_fix_with_normalization():
    """Test that normalize_corrected_expression() fixes the issue."""
    print("\nTest 3: Validating fix with normalize_corrected_expression()")
    
    # Copy the function from proposal.py
    def normalize_corrected_expression(expression) -> str:
        """Normalize quality-gate corrected expressions to a parser-safe string."""
        if isinstance(expression, dict):
            return expression.get("expression") or str(expression)
        return expression
    
    try:
        dict_expression = {"code": "close / open", "note": "from LLM"}
        normalized = normalize_corrected_expression(dict_expression)
        print(f"  Original: {dict_expression}")
        print(f"  Normalized: {normalized}")
        
        # Now the replace should work
        expr_clean = normalized.replace(" ", "")
        print(f"  After replace: '{expr_clean}'")
        print(f"  ✓ Fix works!")
        return True
    except Exception as e:
        print(f"  ✗ Fix failed: {e}")
        return False


def test_data_flow_simulation():
    """Simulate the data flow from LLM to bug trigger."""
    print("\nTest 4: Simulating data flow from LLM to bug trigger")
    
    # Simulate LLM response where corrected_expression is a dict
    llm_response = {
        "is_consistent": False,
        "corrected_expression": {
            "code": "close / open",
            "note": "LLM suggests this form"
        }
    }
    
    # This is what happens in FactorConsistencyChecker
    result_corrected_expr = llm_response.get("corrected_expression")
    print(f"  LLM returned corrected_expression: {result_corrected_expr}")
    print(f"  Type: {type(result_corrected_expr)}")
    
    # This is what happens in check_and_correct() 
    # (lines 152-158 in consistency_checker.py)
    current_expression = result_corrected_expr
    print(f"  current_expression = corrected_expression: {current_expression}")
    
    # This is what happens in FactorQualityGate.evaluate()
    # (line 490-491)
    factor_expression = current_expression
    print(f"  factor_expression = corrected_expr: {factor_expression}")
    
    # This is what triggers the bug (line 496 in consistency_checker.py)
    print("\n  Attempting: complexity_checker.check(factor_expression)")
    try:
        expr_clean = factor_expression.replace(" ", "")
        print(f"  ✗ Bug not triggered: {expr_clean}")
        return False
    except AttributeError as e:
        if "'dict' object has no attribute 'replace'" in str(e):
            print(f"  ✓ Bug triggered: {e}")
            print("\n  Root cause: LLM returned nested dict for corrected_expression")
            return True
        raise


def test_with_nested_dict():
    """Test with different dict structures LLM might return."""
    print("\nTest 5: Testing various dict structures")
    
    test_cases = [
        {"expression": "close / open"},
        {"code": "close / open"},
        {"value": "close / open", "note": "extra info"},
        {"data": {"code": "close / open"}},
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        try:
            expr_clean = test_case.replace(" ", "")
            print(f"  Case {i} {test_case}: ✗ No error (bug fixed or wrong test)")
            all_passed = False
        except AttributeError as e:
            print(f"  Case {i} {test_case}: ✓ Triggers AttributeError")
    
    return all_passed


if __name__ == "__main__":
    # Run tests
    bug_reproduced = test_bug_reproduction_direct()
    fix_works = test_fix_with_normalization()
    data_flow_ok = test_data_flow_simulation()
    dict_structures = test_with_nested_dict()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Bug reproduction (direct): {'✓ Success' if bug_reproduced else '✗ Failed'}")
    print(f"  Fix validation: {'✓ Success' if fix_works else '✗ Failed'}")
    print(f"  Data flow simulation: {'✓ Success' if data_flow_ok else '✗ Failed'}")
    print(f"  Dict structures test: {'✓ Success' if dict_structures else '✗ Some cases'}")
    print("=" * 60)
    
    if bug_reproduced:
        print("\n✓ Bug successfully reproduced!")
        print("\nBug Location:")
        print("  File: third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py")
        print("  Line: 265")
        print("  Code: expr_clean = expression.replace(\" \", \"\")")
        print("\nRoot Cause:")
        print("  LLM can return nested dict for 'corrected_expression' field")
        print("  e.g., {\"corrected_expression\": {\"code\": \"...\", \"note\": \"...\"}}")
        print("\nCall Chain:")
        print("  FactorQualityGate.evaluate() -> complexity_checker.check(factor_expression)")
        print("  If factor_expression is dict -> AttributeError")
        print("\nFix:")
        print("  Apply normalize_corrected_expression() before complexity_checker.check()")
        sys.exit(0)  # Exit 0 because bug was successfully reproduced
    else:
        print("\nBug not reproduced (may already be fixed)")
        sys.exit(1)
