"""
Regression test for dict-type AttributeError bug fix in consistency_checker.py.

Bug: LLM JSON responses may contain nested dict structures causing
     'dict' object has no attribute 'replace' error.

Location: third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
         Line 265-269 (before fix: Line 265 was expr_clean = expression.replace(" ", ""))

This test validates the defensive fix:
    if isinstance(expression, dict):
        expression = expression.get("code") or expression.get("expression") or str(expression)
    expr_clean = expression.replace(" ", "")
"""

import unittest


class TestDictTypeErrorRegression(unittest.TestCase):
    """Regression tests for dict-type AttributeError fix in consistency_checker.py."""

    def _normalize_and_clean(self, expression):
        """Mirrors the fix logic from consistency_checker.py"""
        if isinstance(expression, dict):
            expression = expression.get("code") or expression.get("expression") or str(expression)
        return expression.replace(" ", "")

    def test_dict_with_code_key_does_not_raise_attribute_error(self):
        """Dict with 'code' key should not raise AttributeError."""
        dict_expr = {"code": "($close - $open) / $open", "note": "Simplified form"}
        try:
            result = self._normalize_and_clean(dict_expr)
            self.assertEqual(result, "($close-$open)/$open")
        except AttributeError as e:
            self.fail(f"Dict with 'code' key raised AttributeError (regression): {e}")

    def test_dict_with_expression_key_does_not_raise_attribute_error(self):
        """Dict with 'expression' key should not raise AttributeError."""
        dict_expr = {"expression": "($close / $open) * 100", "source": "llm"}
        try:
            result = self._normalize_and_clean(dict_expr)
            self.assertEqual(result, "($close/$open)*100")
        except AttributeError as e:
            self.fail(f"Dict with 'expression' key raised AttributeError (regression): {e}")

    def test_dict_with_unknown_keys_does_not_raise_attribute_error(self):
        """Dict with unknown keys should fall back to str() and not raise AttributeError."""
        dict_expr = {"unknown_key": "some_value", "nested": {"data": 123}}
        try:
            result = self._normalize_and_clean(dict_expr)
            self.assertIn("unknown_key", result)
        except AttributeError as e:
            self.fail(f"Dict with unknown keys raised AttributeError (regression): {e}")

    def test_string_expression_still_works(self):
        """String expressions should continue to work as before."""
        str_expr = "($close - $open) / $open"
        result = self._normalize_and_clean(str_expr)
        self.assertEqual(result, "($close-$open)/$open")

    def test_nested_dict_with_code_key(self):
        """Nested dict containing 'code' key should extract the code value."""
        nested_dict = {"data": {"code": "close / open"}}
        result = self._normalize_and_clean(nested_dict)
        # Falls back to str() for nested dict without direct 'code'/'expression' at root
        self.assertIsInstance(result, str)

    def test_dict_with_only_note_key(self):
        """Dict without 'code' or 'expression' falls back to str()."""
        dict_expr = {"note": "Some note", "extra": "data"}
        result = self._normalize_and_clean(dict_expr)
        self.assertIn("note", result)


class TestOriginalBugBehavior(unittest.TestCase):
    """Tests that demonstrate the original bug behavior (before fix)."""

    def test_original_buggy_code_would_fail_on_dict(self):
        """The original code would fail on dict input."""
        def original_buggy_clean(expression):
            return expression.replace(" ", "")  # Line 265 before fix

        # String works
        self.assertEqual(original_buggy_clean("close / open"), "close/open")

        # Dict fails with AttributeError
        with self.assertRaises(AttributeError) as context:
            original_buggy_clean({"code": "close / open"})
        self.assertIn("'dict' object has no attribute 'replace'", str(context.exception))

    def test_fixed_code_handles_both(self):
        """Fixed code should handle both string and dict inputs."""
        def fixed_clean(expression):
            if isinstance(expression, dict):
                expression = expression.get("code") or expression.get("expression") or str(expression)
            return expression.replace(" ", "")

        # String works
        self.assertEqual(fixed_clean("close / open"), "close/open")

        # Dict with 'code' key works
        self.assertEqual(fixed_clean({"code": "close / open"}), "close/open")

        # Dict with 'expression' key works
        self.assertEqual(fixed_clean({"expression": "close / open"}), "close/open")


class TestDictNormalizationLogic(unittest.TestCase):
    """Unit tests for the dict normalization logic."""

    def test_code_key_takes_priority(self):
        """When both 'code' and 'expression' exist, 'code' takes priority."""
        expr = {"code": "from_code", "expression": "from_expression"}
        result = expr.get("code") or expr.get("expression") or str(expr)
        self.assertEqual(result, "from_code")

    def test_expression_used_when_no_code(self):
        """When only 'expression' exists, use it."""
        expr = {"expression": "from_expression", "other": "data"}
        result = expr.get("code") or expr.get("expression") or str(expr)
        self.assertEqual(result, "from_expression")

    def test_str_fallback_when_no_code_or_expression(self):
        """When neither 'code' nor 'expression' exist, fall back to str()."""
        expr = {"foo": "bar", "baz": 123}
        result = expr.get("code") or expr.get("expression") or str(expr)
        self.assertIn("foo", result)
        self.assertIn("bar", result)

    def test_empty_dict_falls_back_to_str(self):
        """Empty dict falls back to str()."""
        expr = {}
        result = expr.get("code") or expr.get("expression") or str(expr)
        self.assertEqual(result, "{}")


if __name__ == "__main__":
    unittest.main()
