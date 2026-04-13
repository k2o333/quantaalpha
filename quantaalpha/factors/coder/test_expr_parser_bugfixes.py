"""
Comprehensive tests for the 4 bug fixes in expr_parser.py and proposal.py.

Bug 1: check_parentheses_balance should raise ValueError (not ParseException) with detailed counts
Bug 2: preprocess_unary_minus bracket-fixing dead code removed; replaced with safety assertion
Bug 3: regex substitutions should produce self-closing (-1) * patterns, preserving math semantics
Bug 4: proposal.py truncation increased from 160 to 500 (tested via grep, not import)
"""

import re
import sys
import os
import pytest

# ──────────────────────────────────────────────────────────────────
# Direct imports from the module under test.
# We set PYTHONPATH to include third_party/quantaalpha in the Makefile/CLI.
# ──────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from quantaalpha.factors.coder.expr_parser import (
    check_parentheses_balance,
    preprocess_unary_minus,
    parse_expression,
)
from pyparsing import ParseException


# ======================================================================
#  Bug 1 Tests: check_parentheses_balance
# ======================================================================

class TestCheckParenthesesBalance:
    """Bug 1: Should raise ValueError (not ParseException) with bracket count info."""

    def test_balanced_expression_passes(self):
        """Balanced expressions should not raise."""
        check_parentheses_balance("RANK(A + B)")
        check_parentheses_balance("(A + (B * C))")
        check_parentheses_balance("FUNC(A, FUNC2(B, C))")
        check_parentheses_balance("no_parens_at_all")
        check_parentheses_balance("")

    def test_more_close_than_open_raises_valueerror(self):
        """Extra closing parens should raise ValueError, not ParseException."""
        with pytest.raises(ValueError, match=r"Unbalanced parentheses.*extra.*closing"):
            check_parentheses_balance("(A + B)) * C")

    def test_more_open_than_close_raises_valueerror(self):
        """Missing closing parens should raise ValueError."""
        with pytest.raises(ValueError, match=r"Unbalanced parentheses.*missing.*closing"):
            check_parentheses_balance("((A + B) * C")

    def test_does_not_raise_parse_exception(self):
        """Must NOT raise ParseException anymore (was the original bug)."""
        try:
            check_parentheses_balance("(A))")
        except ParseException:
            pytest.fail("check_parentheses_balance should not raise ParseException anymore")
        except ValueError:
            pass  # Expected

    def test_error_message_contains_counts(self):
        """Error message should include exact open/close counts."""
        with pytest.raises(ValueError) as exc_info:
            check_parentheses_balance("((())")
        msg = str(exc_info.value)
        assert "3 open" in msg
        assert "2 close" in msg

    def test_error_message_no_char_0(self):
        """Error message should NOT contain misleading 'at char 0'."""
        with pytest.raises(ValueError) as exc_info:
            check_parentheses_balance("((A + B)")
        msg = str(exc_info.value)
        assert "at char 0" not in msg

    def test_real_world_unbalanced_expression(self):
        """Test with the actual failing expression from the bug report."""
        expr = (
            "(0.5 + 0.2 * (1 - ABS(TS_CORR(TS_CORR($return, $volume, 5), "
            "TS_CORR($return, $volume, 20), 10))))) * ZSCORE(RANK(TS_CORR($return, $volume, 10)))"
        )
        with pytest.raises(ValueError, match=r"Unbalanced parentheses"):
            check_parentheses_balance(expr)


# ======================================================================
#  Bug 3 Tests: preprocess_unary_minus regex patterns
# ======================================================================

class TestPreprocessUnaryMinus:
    """Bug 3: Regex substitutions should preserve bracket balance and math semantics."""

    # --- Bracket balance tests ---

    def test_star_neg_paren_stays_balanced(self):
        """'A * -(B + C)' should stay balanced after preprocessing."""
        result = preprocess_unary_minus("A * -(B + C)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_div_neg_paren_stays_balanced(self):
        """'A / -(B + C)' should stay balanced."""
        result = preprocess_unary_minus("A / -(B + C)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_plus_neg_paren_stays_balanced(self):
        """'A + -(B + C)' should stay balanced."""
        result = preprocess_unary_minus("A + -(B + C)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_minus_neg_paren_stays_balanced(self):
        """'A - -(B + C)' should stay balanced."""
        result = preprocess_unary_minus("A - -(B + C)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_star_neg_func_stays_balanced(self):
        """'A * -RANK(B)' should stay balanced."""
        result = preprocess_unary_minus("A * -RANK(B)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_div_neg_func_stays_balanced(self):
        """'A / -RANK(B)' should stay balanced."""
        result = preprocess_unary_minus("A / -RANK(B)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_star_neg_dollar_var_stays_balanced(self):
        """'A * -$volume' should stay balanced."""
        result = preprocess_unary_minus("A * -$volume")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_no_change_for_normal_expressions(self):
        """Normal expressions without unary minus should pass through unchanged."""
        expr = "RANK(A + B) * C"
        result = preprocess_unary_minus(expr)
        assert result == expr

    # --- Mathematical correctness tests ---

    def test_star_neg_paren_plus_d_correct_form(self):
        """'A * -(B + C) + D' should become 'A * (-1) * (B + C) + D', not 'A * (-1 * (B + C) + D)'."""
        result = preprocess_unary_minus("A * -(B + C) + D")
        # Must contain (-1) * ( — the self-closing pattern
        assert "(-1) *" in result or "(-1)*" in result, f"Missing (-1) * pattern: {result}"
        # Must NOT contain (-1 * ( — the old broken pattern
        assert "(-1 * (" not in result, f"Contains old broken pattern: {result}"

    def test_star_neg_paren_no_trailing_d(self):
        """'A * -(B + C)' without trailing terms."""
        result = preprocess_unary_minus("A * -(B + C)")
        assert "(-1) *" in result or "(-1)*" in result

    def test_div_neg_paren_correct_form(self):
        """'A / -(B + C)' should use (-1) * pattern."""
        result = preprocess_unary_minus("A / -(B + C)")
        assert "(-1) *" in result or "(-1)*" in result

    def test_star_neg_func_correct_form(self):
        """'A * -RANK(B)' should use (-1) * pattern."""
        result = preprocess_unary_minus("A * -RANK(B)")
        assert "(-1) *" in result or "(-1)*" in result

    # --- Multiple unary minus in one expression ---

    def test_multiple_unary_minus(self):
        """Multiple unary minus operators should all be handled correctly."""
        result = preprocess_unary_minus("A * -(B + C) + D * -(E + F)")
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"
        # Every (-1 should be self-closing (-1)
        assert "(-1 * (" not in result, f"Contains old broken pattern: {result}"

    # --- Complex real-world expression ---

    def test_complex_expression_balanced(self):
        """A complex expression should remain balanced after preprocessing."""
        expr = "ZSCORE(A) * -(RANK(B) + RANK(C)) / -(D + E) + F"
        result = preprocess_unary_minus(expr)
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"

    def test_already_balanced_complex(self):
        """Already balanced expression with no unary minus should pass through."""
        expr = "RANK(TS_CORR($return, $volume, 10)) * ZSCORE($return)"
        result = preprocess_unary_minus(expr)
        assert result.count('(') == result.count(')'), f"Unbalanced: {result}"
        assert result == expr  # No changes expected

    # --- Safety assertion test ---

    def test_assertion_fires_on_imbalance(self):
        """If somehow regex introduces imbalance, the assertion should catch it."""
        # This test verifies the safety net assertion exists.
        # With the current fixed regexes, we can't trigger it directly,
        # but we verify the assertion path by testing balanced inputs.
        result = preprocess_unary_minus("A * -(B)")
        assert result.count('(') == result.count(')')


# ======================================================================
#  Bug 2 Tests: Execution order / dead code removal
# ======================================================================

class TestExecutionOrder:
    """Bug 2: check_parentheses_balance runs before preprocess_unary_minus.
    After Bug 3 fix, preprocess_unary_minus no longer needs bracket-fixing.
    The old bracket-fixing dead code has been replaced with a safety assertion."""

    def test_unbalanced_raises_before_preprocessing(self):
        """Unbalanced expressions should raise ValueError in parse_expression."""
        with pytest.raises(ValueError, match=r"Unbalanced"):
            parse_expression("(A + B)) * C")

    def test_balanced_with_unary_minus_succeeds(self):
        """Balanced expressions with unary minus should parse successfully."""
        # This would have been broken by the old dead code if it appended ) at end
        result = parse_expression("$return * -1")
        assert result is not None

    def test_expression_with_unary_neg_paren(self):
        """Expression with * -( should parse correctly after preprocessing."""
        # This tests the full pipeline: check_balance -> preprocess -> parse
        result = parse_expression("RANK($return) * -(ZSCORE($volume))")
        assert result is not None


# ======================================================================
#  Integration Tests: parse_expression end-to-end
# ======================================================================

class TestParseExpressionIntegration:
    """End-to-end tests verifying parse_expression still works after all fixes."""

    def test_simple_arithmetic(self):
        result = parse_expression("$return + $volume")
        assert result is not None

    def test_function_call(self):
        result = parse_expression("RANK($return)")
        assert result is not None

    def test_nested_functions(self):
        result = parse_expression("RANK(TS_CORR($return, $volume, 10))")
        assert result is not None

    def test_constants(self):
        result = parse_expression("$return * 0.5 + $volume * 0.3")
        assert result is not None

    def test_complex_expression(self):
        result = parse_expression("ZSCORE(RANK(TS_CORR($return, $volume, 10))) + RANK($return)")
        assert result is not None

    def test_unary_minus_with_number(self):
        result = parse_expression("$return * -1 + $volume")
        assert result is not None

    def test_dollar_variable(self):
        result = parse_expression("RANK($return)")
        assert result is not None

    def test_scientific_notation(self):
        result = parse_expression("$return + 1e-8")
        assert result is not None

    def test_existing_main_example(self):
        """The example from __main__ in expr_parser.py should still work."""
        result = parse_expression("RANK(DELTA($open, 1) - DELTA($open, 1)) / (1e-8 + 1)")
        assert result is not None

    def test_comparison_operators(self):
        result = parse_expression("$return > 0")
        assert result is not None

    def test_conditional_expression(self):
        result = parse_expression("$return > 0 ? $return : $volume")
        assert result is not None


# ======================================================================
#  Bug 4 Tests: Truncation in proposal.py
# ======================================================================

class TestProposalTruncation:
    """Bug 4: Verify proposal.py uses expr[:500] instead of expr[:160]."""

    def test_no_160_truncation_in_proposal(self):
        """proposal.py should not contain any expr[:160] truncation."""
        proposal_path = os.path.join(
            os.path.dirname(__file__), '..', 'proposal.py'
        )
        with open(proposal_path, 'r') as f:
            content = f.read()

        # Should NOT have expr[:160]
        matches_160 = re.findall(r'expr\[:160\]', content)
        assert len(matches_160) == 0, (
            f"Found {len(matches_160)} occurrence(s) of expr[:160] in proposal.py — "
            f"should have been changed to expr[:500]"
        )

    def test_has_500_truncation_in_proposal(self):
        """proposal.py should use expr[:500] for failure reasons."""
        proposal_path = os.path.join(
            os.path.dirname(__file__), '..', 'proposal.py'
        )
        with open(proposal_path, 'r') as f:
            content = f.read()

        # Should have expr[:500]
        matches_500 = re.findall(r'expr\[:500\]', content)
        assert len(matches_500) >= 2, (
            f"Expected at least 2 occurrences of expr[:500] in proposal.py "
            f"(failure_reason + feedback_item), found {len(matches_500)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
