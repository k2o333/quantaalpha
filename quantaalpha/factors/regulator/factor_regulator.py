import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Any, Optional
from pathlib import Path
from quantaalpha.core.evaluation import Evaluator
from quantaalpha.log import logger
from quantaalpha.core.scenario import Scenario


class FactorRegulator(Evaluator):
    """
    FactorRegulator class to evaluate expressions for duplication and manage the factor zoo database.
    This class provides functionality to detect duplicated subtrees in factor expressions
    and ensure new factors maintain appropriate originality.
    """

    def __init__(self, factor_zoo_path: str = None, duplication_threshold: int = 8, symbol_length_threshold: int = 300, base_features_threshold: int = 6, similarity_engine=None):
        """
        Initialize the FactorRegulator with a reference to the factor zoo database.

        Args:
            factor_zoo_path (str): Path to the CSV file containing the factor zoo database,
                                   or path to a Parquet factor store directory.
            duplication_threshold (int): Threshold for duplication detection.
            symbol_length_threshold (int): Maximum allowed symbol length (SL) for expressions.
            base_features_threshold (int): Maximum allowed number of unique base features (ER).
            similarity_engine: Optional SimilarityEngine instance for computing ensemble similarity scores.
        """
        super().__init__(None)
        self.factor_zoo_path = factor_zoo_path
        if factor_zoo_path:
            self.alphazoo = self._load_factor_zoo(factor_zoo_path)
        else:
            self.alphazoo = pd.DataFrame()
        self.duplication_threshold = duplication_threshold
        self.symbol_length_threshold = symbol_length_threshold
        self.base_features_threshold = base_features_threshold
        self.new_factors = []
        self._similarity_engine = similarity_engine
        if similarity_engine:
            logger.info("SimilarityEngine injected into FactorRegulator")

    def _load_factor_zoo(self, path: str) -> pd.DataFrame:
        """Load factor zoo from CSV or Parquet store.

        Args:
            path: Path to CSV file or Parquet factor store directory.

        Returns:
            DataFrame with factor_name and factor_expression columns.
        """
        path_obj = Path(path)

        # Check if this is a Parquet store directory
        if path_obj.is_dir():
            return self._load_from_parquet_store(str(path_obj))

        # Legacy CSV path
        if path_obj.exists():
            return pd.read_csv(str(path_obj), index_col=None)

        return pd.DataFrame()

    def _load_from_parquet_store(self, store_path: str) -> pd.DataFrame:
        """Load factors from Parquet factor store via FactorStoreFacade.

        Args:
            store_path: Path to the Parquet factor store directory.

        Returns:
            DataFrame with factor_name, factor_expression columns.
        """
        try:
            from quantaalpha.factors.factor_store_facade import FactorStoreFacade

            facade = FactorStoreFacade(store_path=store_path)
            df = facade.to_factor_zoo_frame()

            if df.empty:
                logger.info("Parquet factor store is empty")
                return pd.DataFrame(columns=["factor_name", "factor_expression"])

            return df

        except FileNotFoundError:
            logger.warning(f"Parquet factor store directory not found at {store_path}, returning empty")
            return pd.DataFrame(columns=["factor_name", "factor_expression"])

        except Exception as e:
            logger.error(f"Unexpected error loading parquet store from {store_path}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return pd.DataFrame(columns=["factor_name", "factor_expression"])

    def parse_diagnostic(self, expression: str) -> tuple[bool, str | None]:
        """Diagnose whether an expression can be parsed and return structured feedback.

        Also validates known fixed-arity DSL function signatures (e.g. MEAN is single-arg).

        Args:
            expression: The factor expression to check.

        Returns:
            A tuple of (is_parsable, error_message).  error_message is None when
            the expression parses successfully, otherwise it contains the concrete
            parser error string (e.g. "Unclosed parentheses").
        """
        try:
            from quantaalpha.pipeline.quality_overlay import detect_expression_static_diagnostics

            static_diag = detect_expression_static_diagnostics(expression)
            if static_diag.get("severity") == "critical":
                message = f"{static_diag.get('failure_type')}: {static_diag.get('message')}"
                logger.warning(f"Expression static diagnostic violation: {expression}. Error: {message}")
                return False, message
        except Exception as exc:
            logger.warning(f"Expression static diagnostic check failed for {expression}: {exc}")

        try:
            from quantaalpha.factors.coder.expr_parser import parse_expression

            parse_expression(expression)
        except Exception as exc:
            message = str(exc)
            logger.warning(f"Failed to parse expression: {expression}. Error: {message}")
            return False, message

        # DSL function signature validation
        sig_error = self._validate_dsl_function_signatures(expression)
        if sig_error:
            logger.warning(f"DSL signature violation in expression: {expression}. Error: {sig_error}")
            return False, sig_error

        output_diag = self.expression_output_diagnostic(expression)
        if output_diag.get("reject"):
            message = str(output_diag.get("message") or "expression output type is not rankable")
            logger.warning(f"Expression output type violation: {expression}. Error: {message}")
            return False, message

        return True, None

    def expression_output_diagnostic(self, expression: str) -> dict[str, Any]:
        """Infer coarse expression output type for rank-alpha admission."""
        try:
            from quantaalpha.factors.coder.factor_ast import (
                BinaryOpNode,
                ConditionalNode,
                FunctionNode,
                NumberNode,
                VarNode,
                parse_expression,
            )

            tree = parse_expression(expression)
        except Exception as exc:
            return {
                "output_type": "unknown",
                "reject": False,
                "message": f"output type unavailable: {exc}",
            }

        def func_name(node: FunctionNode) -> str:
            name = node.name.name if isinstance(node.name, VarNode) else str(node.name)
            return name.upper()

        def constant_value(node) -> float | None:
            return float(node.value) if isinstance(node, NumberNode) else None

        if isinstance(tree, BinaryOpNode) and str(tree.op) in {">", "<", ">=", "<=", "==", "!=", "&&", "&", "||", "|"}:
            return {
                "output_type": "boolean_output",
                "reject": True,
                "message": "Expression output is boolean/comparison; rank-based alpha requires a continuous signal.",
            }
        if isinstance(tree, FunctionNode) and func_name(tree) in {"GREATER", "LESS", "IF"}:
            values = [constant_value(arg) for arg in tree.args[1:]] if func_name(tree) == "IF" else []
            if values and all(value in {0.0, 1.0} for value in values if value is not None):
                output_type = "constant_discrete"
            else:
                output_type = "boolean_output"
            return {
                "output_type": output_type,
                "reject": True,
                "message": f"Expression output is {output_type}; rank-based alpha requires a continuous signal.",
            }
        if isinstance(tree, ConditionalNode):
            true_value = constant_value(tree.true_expr)
            false_value = constant_value(tree.false_expr)
            if true_value is not None and false_value is not None:
                return {
                    "output_type": "constant_discrete",
                    "reject": True,
                    "message": "Conditional expression returns only constant discrete values; rank-based alpha requires a continuous signal.",
                }

        return {"output_type": "continuous", "reject": False, "message": ""}

    def simplify_expression(self, expression: str) -> dict[str, Any]:
        """Simplify conservative no-op expression patterns before complexity checks."""
        try:
            from quantaalpha.factors.coder.factor_ast import (
                BinaryOpNode,
                FunctionNode,
                NumberNode,
                UnaryOpNode,
                VarNode,
                parse_expression,
            )

            tree = parse_expression(expression)
        except Exception as exc:
            return {
                "original_expression": expression,
                "simplified_expression": expression,
                "changed": False,
                "rules_applied": [],
                "error": str(exc),
            }

        rules: list[str] = []

        def is_number(node, value: float) -> bool:
            return isinstance(node, NumberNode) and abs(float(node.value) - value) < 1e-12

        def name_of(node: FunctionNode) -> str:
            name = node.name.name if isinstance(node.name, VarNode) else str(node.name)
            return name.upper()

        def simplify(node):
            if isinstance(node, BinaryOpNode):
                left = simplify(node.left)
                right = simplify(node.right)
                if node.op == "+" and is_number(right, 0.0):
                    rules.append("remove_plus_zero")
                    return left
                if node.op == "+" and is_number(left, 0.0):
                    rules.append("remove_leading_zero_plus")
                    return right
                if node.op == "-" and is_number(right, 0.0):
                    rules.append("remove_minus_zero")
                    return left
                if node.op == "*" and is_number(right, 1.0):
                    rules.append("remove_times_one")
                    return left
                if node.op == "*" and is_number(left, 1.0):
                    rules.append("remove_leading_one_times")
                    return right
                if node.op == "/" and is_number(right, 1.0):
                    rules.append("remove_divide_one")
                    return left
                return BinaryOpNode(node.op, left, right)
            if isinstance(node, FunctionNode):
                args = [simplify(arg) for arg in node.args]
                simplified = FunctionNode(node.name, args)
                if len(args) == 1 and isinstance(args[0], FunctionNode) and name_of(simplified) in {"ABS", "RANK"}:
                    if name_of(args[0]) == name_of(simplified):
                        rules.append(f"collapse_nested_{name_of(simplified).lower()}")
                        return args[0]
                return simplified
            if isinstance(node, UnaryOpNode):
                return UnaryOpNode(node.op, simplify(node.operand))
            return node

        simplified_tree = simplify(tree)
        simplified_expression = str(simplified_tree)
        return {
            "original_expression": expression,
            "simplified_expression": simplified_expression,
            "changed": bool(simplified_expression != expression and rules),
            "rules_applied": sorted(set(rules)),
            "error": "",
        }

    def _validate_dsl_function_signatures(self, expression: str) -> str | None:
        """Validate known fixed-arity DSL function signatures using AST.

        Currently enforces:
        - MEAN(A) is single-argument only. Suggests explicit weighted addition or MEAN(A).
        - Does NOT reject TS_MEAN, CS_MEAN, or other prefixed variants.

        Args:
            expression: The factor expression to validate.

        Returns:
            Error message if violation detected, None otherwise.
        """
        try:
            from quantaalpha.factors.coder.factor_ast import parse_expression, FunctionNode

            tree = parse_expression(expression)
        except Exception:
            # If AST parsing fails, fall back to regex-based check
            return self._validate_dsl_function_signatures_regex(expression)

        violations = []
        self._collect_mean_violations(tree, violations)
        self._collect_known_arity_violations(tree, violations)
        self._collect_sequence_violations(tree, violations)
        if violations:
            return violations[0]
        return None

    def _collect_mean_violations(self, node, violations: list[str]) -> None:
        """Recursively walk AST and collect MEAN() calls with >1 argument."""
        try:
            from quantaalpha.factors.coder.factor_ast import FunctionNode, VarNode
        except ImportError:
            return

        if isinstance(node, FunctionNode):
            # FunctionNode.name is a VarNode, not a string
            func_name = node.name.name if isinstance(node.name, VarNode) else str(node.name)
            # Only reject exact "MEAN" name, not prefixed variants like TS_MEAN
            if func_name == "MEAN" and len(node.args) > 1:
                args_repr = ", ".join(str(arg) for arg in node.args)
                violations.append(f"MEAN() is a single-argument cross-sectional function in this DSL, but got {len(node.args)} arguments: MEAN({args_repr}). Use explicit weighted addition (e.g. 0.33*A + 0.33*B + 0.34*C) or MEAN(A) for a single expression.")
            # Recurse into all children
            for arg in node.args:
                self._collect_mean_violations(arg, violations)
        elif hasattr(node, "__iter__") and not isinstance(node, str):
            for child in node:
                if hasattr(child, "__dict__"):
                    self._collect_mean_violations(child, violations)

    def _collect_known_arity_violations(self, node, violations: list[str]) -> None:
        """Reject known DSL calls whose arity changes their intended semantics."""
        try:
            from quantaalpha.factors.coder.factor_ast import FunctionNode, VarNode
        except ImportError:
            return

        if isinstance(node, FunctionNode):
            func_name = node.name.name if isinstance(node.name, VarNode) else str(node.name)
            upper_name = func_name.upper()
            expected_arities = {"ZSCORE": (1,), "AND": (2,)}
            supported_arities = expected_arities.get(upper_name)
            if supported_arities is not None and len(node.args) not in supported_arities:
                alternatives = ' suggested_alternatives=["TS_ZSCORE"]' if upper_name == "ZSCORE" and len(node.args) == 2 else ""
                violations.append(f"reason_code=unsupported_arity function_name={upper_name} received_arity={len(node.args)} supported_arities={supported_arities}{alternatives}")
            for arg in node.args:
                self._collect_known_arity_violations(arg, violations)
        elif hasattr(node, "__iter__") and not isinstance(node, str):
            for child in node:
                if hasattr(child, "__dict__"):
                    self._collect_known_arity_violations(child, violations)

    def _collect_sequence_violations(
        self,
        node,
        violations: list[str],
        parent_function: str | None = None,
        parent_arg_index: int | None = None,
    ) -> None:
        """Reject SEQUENCE() outside regression helper argument B."""
        try:
            from quantaalpha.factors.coder.factor_ast import (
                BinaryOpNode,
                ConditionalNode,
                FunctionNode,
                UnaryOpNode,
                VarNode,
            )
        except ImportError:
            return

        if isinstance(node, FunctionNode):
            func_name = node.name.name if isinstance(node.name, VarNode) else str(node.name)
            upper_name = func_name.upper()
            if upper_name == "SEQUENCE":
                if parent_function not in {"REGBETA", "REGRESI"} or parent_arg_index != 1:
                    violations.append("SEQUENCE(n) may only be used as argument B of REGBETA(A, B, n) or REGRESI(A, B, n). Do not multiply, divide, add, subtract, or wrap SEQUENCE() in other functions.")
                    return
            for idx, arg in enumerate(node.args):
                self._collect_sequence_violations(arg, violations, upper_name, idx)
            return

        if isinstance(node, BinaryOpNode):
            self._collect_sequence_violations(node.left, violations, parent_function, parent_arg_index)
            self._collect_sequence_violations(node.right, violations, parent_function, parent_arg_index)
            return

        if isinstance(node, UnaryOpNode):
            self._collect_sequence_violations(node.operand, violations, parent_function, parent_arg_index)
            return

        if isinstance(node, ConditionalNode):
            self._collect_sequence_violations(node.condition, violations, parent_function, parent_arg_index)
            self._collect_sequence_violations(node.true_expr, violations, parent_function, parent_arg_index)
            self._collect_sequence_violations(node.false_expr, violations, parent_function, parent_arg_index)

    def _validate_dsl_function_signatures_regex(self, expression: str) -> str | None:
        """Fallback regex-based MEAN validation when AST parsing is unavailable."""
        import re

        # Match MEAN(...) but NOT TS_MEAN, CS_MEAN, etc.
        mean_pattern = re.compile(r"(?<![_A-Z])MEAN\s*\((.+)\)", re.DOTALL)
        match = mean_pattern.search(expression)
        if match:
            args_str = match.group(1).strip()
            if not args_str:
                return "MEAN() requires exactly one argument, got empty."
            # Count top-level commas (not inside nested parens)
            depth = 0
            arg_count = 1
            for ch in args_str:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                elif ch == "," and depth == 0:
                    arg_count += 1
            if arg_count > 1:
                return f"MEAN() is a single-argument cross-sectional function in this DSL, but got {arg_count} arguments. Use explicit weighted addition (e.g. 0.33*A + 0.33*B + 0.34*C) or MEAN(A) for a single expression."
        if "SEQUENCE" in expression.upper():
            return "SEQUENCE(n) may only be used as argument B of REGBETA(A, B, n) or REGRESI(A, B, n)."
        return None

    def is_parsable(self, expression: str) -> bool:
        """
        Checks if an expression can be successfully parsed.

        Args:
            expression (str): The factor expression to check.

        Returns:
            bool: True if the expression can be parsed, False otherwise.
        """
        ok, _ = self.parse_diagnostic(expression)
        return ok

    def evaluate(self, expression: str) -> Tuple[int, str, Optional[str]]:
        """
        Evaluates an expression for duplication with existing factors in the factor zoo.

        如果注入了 SimilarityEngine,还会计算融合相似度并添加到返回结果中。

        Args:
            expression (str): The factor expression to evaluate.

        Returns:
            Tuple containing:
                - duplicated_subtree_size (int): Size of the duplicated subtree
                - duplicated_subtree (str): The duplicated subtree expression
                - matched_alpha (str or None): Name of the matched alpha if available
        """
        try:
            # Lazy import to avoid circular dependency
            from quantaalpha.factors.coder.factor_ast import match_alphazoo, count_free_args, count_unique_vars, count_all_nodes, calculate_symbol_length, count_base_features

            simplification = self.simplify_expression(expression)
            evaluated_expression = str(simplification.get("simplified_expression") or expression)

            # Check for duplication
            duplicated_subtree_size, duplicated_subtree, matched_alpha = match_alphazoo(evaluated_expression, self.alphazoo)

            num_free_args = count_free_args(evaluated_expression)
            num_unique_vars = count_unique_vars(evaluated_expression)
            num_all_nodes = count_all_nodes(evaluated_expression)
            symbol_length = calculate_symbol_length(evaluated_expression)
            num_base_features = count_base_features(evaluated_expression)

            logger.info(f"""
                        Evaluated expr: {evaluated_expression}
                        Duplicated Size: {duplicated_subtree_size}
                        Duplicated Subtree: {duplicated_subtree}
                        # Free Args: {num_free_args}
                        # Unique Vars: {num_unique_vars}
                        Symbol Length (SL): {symbol_length}
                        # Base Features (ER): {num_base_features}
                        """)

            eval_dict = {
                "expr": evaluated_expression,
                "original_expr": expression,
                "simplification": simplification,
                "duplicated_subtree_size": duplicated_subtree_size,
                "duplicated_subtree": duplicated_subtree,
                "matched_alpha": matched_alpha,
                "num_free_args": num_free_args,
                "num_unique_vars": num_unique_vars,
                "num_all_nodes": num_all_nodes,
                "symbol_length": symbol_length,
                "num_base_features": num_base_features,
            }

            # 如果注入了 SimilarityEngine,计算与 factor_zoo 的融合相似度
            if self._similarity_engine is not None and not self.alphazoo.empty:
                try:
                    # 找到最相似的已有因子
                    best_score = 0.0
                    best_expr = None
                    for idx, row in self.alphazoo.iterrows():
                        expr_b = row.get("factor_expression", "")
                        if expr_b:
                            ensemble = self._similarity_engine.compute_pairwise(expression, expr_b)
                            if ensemble.final_score > best_score:
                                best_score = ensemble.final_score
                                best_expr = expr_b

                    eval_dict["ensemble_score"] = best_score
                    eval_dict["ensemble_redundant"] = best_score >= self._similarity_engine._rejection_threshold
                    eval_dict["ensemble_most_similar"] = best_expr

                except Exception as e:
                    logger.warning(f"SimilarityEngine evaluation failed: {e}, skipping ensemble scores")
                    eval_dict["ensemble_score"] = None
                    eval_dict["ensemble_redundant"] = None

            return True, eval_dict

        except Exception as e:
            logger.error(f"Failed to evaluate expression: {expression}. Error: {str(e)}")
            return False, None

    def is_expression_acceptable(self, eval_dict) -> bool:
        """
        Determines if an expression is acceptable based on the duplication threshold,
        the ratio of num_free_args and num_unique_vars to the total number of nodes,
        symbol length (SL), and base features count (ER).

        This implements the complexity regularization R_g(f, h) from the paper:
        R_g(f, h) = α₁·SL(f) + α₂·PC(f) + α₃·ER(f, h)

        Args:
            eval_dict (dict): Dictionary containing evaluation results of the expression.

        Returns:
            bool: True if the expression is acceptable, False otherwise.
        """
        # Condition 1: Check if the duplicated subtree size is within the threshold
        cond1 = eval_dict["duplicated_subtree_size"] <= self.duplication_threshold

        # Get the number of free arguments, unique variables, and total nodes
        num_free_args = eval_dict["num_free_args"]
        num_unique_vars = eval_dict["num_unique_vars"]
        num_all_nodes = eval_dict["num_all_nodes"]
        symbol_length = eval_dict.get("symbol_length", 0)
        num_base_features = eval_dict.get("num_base_features", 0)

        # Avoid division by zero and invalid ratios
        if num_all_nodes == 0:
            logger.warning(f"Expression has no nodes: {eval_dict['expr']}")
            return False

        # Calculate ratios
        free_args_ratio = float(num_free_args) / float(num_all_nodes)
        unique_vars_ratio = float(num_unique_vars) / float(num_all_nodes)

        # Ensure ratios are within valid range (0 <= ratio < 1)
        if free_args_ratio >= 1 or unique_vars_ratio >= 1:
            logger.warning(f"Invalid ratio detected: free_args_ratio={free_args_ratio}, unique_vars_ratio={unique_vars_ratio}")
            return False

        # Condition 2: Ensure the ratio of num_free_args to total nodes is not too high using -log(1 - ratio)
        # -log(1 - x) increases as x increases, so we set a threshold (e.g., -log(1 - 0.5) ≈ 0.693)
        # This ensures the ratio is not too high (e.g., x < 0.5)
        cond2 = -np.log(1 - free_args_ratio) < 0.693  # Threshold for x < 0.5

        # Condition 3: Ensure the ratio of num_unique_vars to total nodes is not too high using -log(1 - ratio)
        cond3 = -np.log(1 - unique_vars_ratio) < 0.693  # Threshold for x < 0.5

        # Condition 4: Check symbol length (SL) - expression should not be too long
        cond4 = symbol_length <= self.symbol_length_threshold

        # Condition 5: Check base features count (ER) - should not use too many raw features
        # Using log(1 + |F_f|) penalty as in the paper
        cond5 = num_base_features <= self.base_features_threshold

        # The expression is acceptable if all conditions are met
        return cond1 and cond2 and cond3 and cond4 and cond5

    def add_factor(self, factor_name: str, factor_expression: str) -> bool:
        """
        Adds a new factor to the in-memory factor zoo if it passes the duplication check.

        Args:
            factor_name (str): Name of the new factor.
            factor_expression (str): Expression of the new factor.

        Returns:
            bool: True if the factor was added, False otherwise.
        """
        new_factor = pd.DataFrame({"factor_name": factor_name, "factor_expression": factor_expression})

        self.alphazoo = pd.concat([self.alphazoo, new_factor])
        self.new_factors.append((factor_name, factor_expression))
        logger.info(f"Added new factor: {factor_name} with expression: {factor_expression}")

    def save_factor_zoo(self, output_path: Optional[str] = None) -> None:
        """
        Saves the updated factor zoo to a CSV file.

        Args:
            output_path (str, optional): Path to save the updated factor zoo.
                                         If None, updates the original file.
        """
        save_path = output_path if output_path else self.factor_zoo_path
        self.alphazoo.to_csv(save_path, index=False)
        logger.info(f"Saved updated factor zoo to {save_path}")

    def get_new_factors(self) -> List[Tuple[str, str]]:
        """
        Returns the list of new factors added during this session.

        Returns:
            List[Tuple[str, str]]: List of (factor_name, factor_expression) tuples.
        """
        return self.new_factors
