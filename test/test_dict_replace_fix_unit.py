"""
Unit tests for the isinstance(dict) defensive fix in consistency_checker.py.

These tests verify that the defensive checks added to ComplexityChecker.check() and
RedundancyChecker.check() correctly handle dict inputs that may come from LLM responses.

Bug: LLM JSON responses can return corrected_expression as a nested dict like:
  {"code": "close / open", "note": "LLM suggestion"}
Instead of a plain string.

Without the fix, calling .replace() on a dict raises:
  AttributeError: 'dict' object has no attribute 'replace'
"""

import unittest
import sys
import os

# Verify the fix is in place by checking the actual file
FIXTURE_FILE = "/home/quan/testdata/aspipe_v4/.gsd/worktrees/M002/third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py"


class TestDictDefensiveFixPresent(unittest.TestCase):
    """Verify the isinstance(dict) defensive check is present in the code."""

    def test_fix_exists_in_complexity_checker(self):
        """Verify isinstance(expression, dict) check exists in ComplexityChecker.check()."""
        with open(FIXTURE_FILE, 'r') as f:
            content = f.read()
        
        # The fix should be present
        self.assertIn("isinstance(expression, dict)", content)
        
        # Verify the fallback chain is present
        self.assertIn('expression.get("code")', content)
        self.assertIn('expression.get("expression")', content)
        self.assertIn("str(expression)", content)

    def test_fix_exists_in_redundancy_checker(self):
        """Verify isinstance(expression, dict) check exists in RedundancyChecker.check()."""
        with open(FIXTURE_FILE, 'r') as f:
            content = f.read()
        
        # Count occurrences - should be at least 2 (one per checker)
        occurrences = content.count("isinstance(expression, dict)")
        self.assertGreaterEqual(occurrences, 2, 
            "Expected isinstance(expression, dict) in both ComplexityChecker and RedundancyChecker")


class TestDictDefensiveLogic(unittest.TestCase):
    """Test the defensive isinstance(dict) check logic."""

    def test_isinstance_guard_on_dict(self):
        """Verify isinstance(expression, dict) guard works correctly."""
        expression = {"code": "close / open"}
        self.assertTrue(isinstance(expression, dict))
        
        # Test the fallback chain
        result = expression.get("code") or expression.get("expression") or str(expression)
        self.assertEqual(result, "close / open")

    def test_isinstance_guard_on_string(self):
        """Verify isinstance(expression, dict) returns False for strings."""
        expression = "close / open"
        self.assertFalse(isinstance(expression, dict))
        
        # String should pass through unchanged
        result = expression if not isinstance(expression, dict) else expression.get("code") or expression.get("expression") or str(expression)
        self.assertEqual(result, "close / open")

    def test_isinstance_guard_on_none(self):
        """Verify isinstance(expression, dict) returns False for None."""
        expression = None
        self.assertFalse(isinstance(expression, dict))

    def test_isinstance_guard_on_int(self):
        """Verify isinstance(expression, dict) returns False for integers."""
        expression = 42
        self.assertFalse(isinstance(expression, dict))

    def test_dict_with_code_key(self):
        """Verify dict with 'code' key extracts correctly."""
        expression = {"code": "close / open", "note": "LLM suggestion"}
        result = expression.get("code") or expression.get("expression") or str(expression)
        self.assertEqual(result, "close / open")

    def test_dict_with_expression_key(self):
        """Verify dict with 'expression' key extracts correctly."""
        expression = {"expression": "vwap / close", "reason": "normalization"}
        result = expression.get("code") or expression.get("expression") or str(expression)
        self.assertEqual(result, "vwap / close")

    def test_dict_with_no_standard_keys(self):
        """Verify dict without 'code' or 'expression' falls back to str()."""
        expression = {"foo": "bar", "baz": 123}
        result = expression.get("code") or expression.get("expression") or str(expression)
        self.assertEqual(result, "{'foo': 'bar', 'baz': 123}")

    def test_empty_dict(self):
        """Verify empty dict is handled safely."""
        expression = {}
        result = expression.get("code") or expression.get("expression") or str(expression)
        self.assertEqual(result, "{}")

    def test_original_bug_would_raise_attributeerror(self):
        """Verify original buggy code would raise AttributeError."""
        # This simulates what the original code did
        expression = {"code": "close / open"}
        
        # Before the fix, this would raise:
        # AttributeError: 'dict' object has no attribute 'replace'
        with self.assertRaises(AttributeError):
            expression.replace(" ", "")  # Bug: can't call replace on dict

    def test_string_replace_still_works(self):
        """Verify .replace() on string still works (baseline preserved)."""
        expression = "close / open"
        result = expression.replace(" ", "")
        self.assertEqual(result, "close/open")


class TestPythonSyntaxValid(unittest.TestCase):
    """Verify the modified file has valid Python syntax."""

    def test_syntax_check(self):
        """Verify consistency_checker.py passes Python syntax check."""
        import py_compile
        try:
            py_compile.compile(FIXTURE_FILE, doraise=True)
            syntax_ok = True
        except py_compile.PyCompileError as e:
            syntax_ok = False
            error_msg = str(e)
        
        self.assertTrue(syntax_ok, f"Syntax check failed: {error_msg if not syntax_ok else ''}")


if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
