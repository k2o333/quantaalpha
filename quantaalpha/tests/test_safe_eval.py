import pytest
import numpy as np
import pandas as pd
import ast
from quantaalpha.backtest.safe_eval import (
    ALLOWED_NODE_TYPES, safe_eval, validate_expression, UnsafeExpressionError
)


class TestSafeEval:
    """安全求值器测试"""

    def _make_globals(self):
        """构造标准 exec_globals"""
        df = pd.DataFrame({
            '$close': [100, 101, 102],
            '$volume': [1000, 1100, 1200],
        })
        return {'df': df, 'np': np, 'pd': pd}

    # === 合法表达式（应正常执行） ===

    def test_allows_math(self):
        """合法数学表达式 1 + 2 * 3 应正常执行"""
        result = safe_eval("1 + 2 * 3", {})
        assert result == 7

    def test_allows_numpy(self):
        """np.log(df['$close']) 应正常执行"""
        g = self._make_globals()
        result = safe_eval("np.log(df['$close'])", g)
        assert len(result) == 3

    def test_simple_arithmetic(self):
        result = safe_eval("1 + 2 * 3", {})
        assert result == 7

    def test_dataframe_column_access(self):
        g = self._make_globals()
        result = safe_eval("df['$close']", g)
        assert len(result) == 3

    def test_numpy_function(self):
        g = self._make_globals()
        result = safe_eval("np.log(df['$close'])", g)
        assert len(result) == 3

    def test_method_call(self):
        g = self._make_globals()
        result = safe_eval("df['$close'].mean()", g)
        assert isinstance(result, float)

    def test_ternary_expression(self):
        result = safe_eval("1 if True else 0", {})
        assert result == 1

    def test_comparison(self):
        result = safe_eval("3 > 2", {})
        assert result is True

    def test_slice(self):
        g = self._make_globals()
        result = safe_eval("df['$close'].iloc[:2]", g)
        assert len(result) == 2

    # === 危险表达式（应被拦截） ===

    def test_blocks_import(self):
        """__import__('os') 应被拦截"""
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("__import__('os')", {})

    def test_blocks_open(self):
        """open('/etc/passwd') 应被拦截"""
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("open('/etc/passwd')", {})

    def test_blocks_nested_eval(self):
        """eval('1+1') 应被拦截（嵌套 eval）"""
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("eval('1+1')", {})

    def test_blocks_dunder_access(self):
        """''.__class__.__bases__ 应被拦截"""
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("''.__class__.__bases__", {})

    def test_blocks_exec(self):
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("exec('print(1)')", {})

    def test_blocks_eval(self):
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("eval('1+1')", {})

    def test_blocks_dunder_attr(self):
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("''.__class__.__bases__", {})

    def test_blocks_getattr(self):
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("getattr(df, '__class__')", self._make_globals())

    def test_blocks_globals(self):
        with pytest.raises(UnsafeExpressionError, match="Forbidden"):
            safe_eval("globals()", {})

    # === 边界情况 ===

    def test_syntax_error_passes_through(self):
        """语法错误应由 eval 本身处理，validator 不拦截"""
        with pytest.raises(SyntaxError):
            safe_eval("1 +", {})

    def test_empty_expression(self):
        with pytest.raises(SyntaxError):
            safe_eval("", {})


class TestValidateExpression:
    """validate_expression 单独测试"""

    def test_safe_expression_returns_empty(self):
        violations = validate_expression("1 + 2")
        assert violations == []

    def test_unsafe_expression_returns_violations(self):
        violations = validate_expression("__import__('os')")
        assert len(violations) > 0

    def test_nested_dunder(self):
        violations = validate_expression("x.__class__.__bases__[0]")
        assert any("__class__" in v for v in violations)

    def test_allowed_nodes_use_constant_not_legacy_num_or_str(self):
        allowed_type_names = {node.__name__ for node in ALLOWED_NODE_TYPES}

        assert ast.Constant in ALLOWED_NODE_TYPES
        assert "Num" not in allowed_type_names
        assert "Str" not in allowed_type_names
