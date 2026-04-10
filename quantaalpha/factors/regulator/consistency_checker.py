"""
Factor Consistency Checker: semantic consistency between hypothesis, description, formulation, expression, code.
"""

import json
import re
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
from jinja2 import Environment, StrictUndefined

from quantaalpha.core.prompts import Prompts
from quantaalpha.llm.client import APIBackend, call_structured
from quantaalpha.llm.tool_schemas import CONSISTENCY_CHECK_TOOL
from quantaalpha.log import logger

consistency_prompts = Prompts(file_path=Path(__file__).parent / "consistency_prompts.yaml")

UNSUPPORTED_CORRECTION_FUNCTIONS = {
    "WEIGHTED_SUM",
    "ARRAY",
    "TERCILE_WEIGHTS",
}


@dataclass
class ConsistencyCheckResult:
    """Result of consistency check (hypothesis->description->formulation->expression)."""
    is_consistent: bool
    hypothesis_to_description: str
    description_to_formulation: str
    formulation_to_expression: str
    overall_feedback: str
    corrected_expression: Optional[str] = None
    corrected_description: Optional[str] = None
    severity: str = "none"  # none, minor, major, critical
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_consistent": self.is_consistent,
            "hypothesis_to_description": self.hypothesis_to_description,
            "description_to_formulation": self.description_to_formulation,
            "formulation_to_expression": self.formulation_to_expression,
            "overall_feedback": self.overall_feedback,
            "corrected_expression": self.corrected_expression,
            "corrected_description": self.corrected_description,
            "severity": self.severity
        }


class FactorConsistencyChecker:
    """Checks logical consistency between hypothesis, description, formulation, expression; corrects if needed."""

    def __init__(
        self,
        scen=None,
        max_correction_attempts: int = 3,
        enabled: bool = True,
        strict_mode: bool = False,
        allowed_inconsistent_severities: Tuple[str, ...] = ("none", "minor"),
    ):
        """scen: scenario; max_correction_attempts: max correction tries; enabled; strict_mode (reject on any inconsistency)."""
        self.scen = scen
        self.max_correction_attempts = max_correction_attempts
        self.enabled = enabled
        self.strict_mode = strict_mode
        self.allowed_inconsistent_severities = allowed_inconsistent_severities

    @staticmethod
    def _expression_complexity_score(expression: Optional[str]) -> int:
        if not expression:
            return 0
        text = str(expression)
        return (
            len(text)
            + 8 * text.count("?")
            + 4 * text.count(":")
            + 3 * text.count("(")
            + 2 * sum(text.count(token) for token in ("+", "-", "*", "/", "&&", "||"))
        )

    @staticmethod
    def _requires_supported_proxy(
        hypothesis: str,
        correction_history: Optional[List[Dict[str, Any]]],
    ) -> bool:
        signal_text = " ".join(
            [
                hypothesis or "",
                *[
                    " ".join(
                        str(item.get(key, ""))
                        for key in ("feedback", "corrected_expression", "expression")
                    )
                    for item in (correction_history or [])
                ],
            ]
        ).lower()
        proxy_markers = (
            "regime",
            "branch",
            "conditional",
            "too expressive",
            "unsupported",
            "?",
        )
        return any(marker in signal_text for marker in proxy_markers)

    def _last_resort_guidance(
        self,
        hypothesis: str,
        current_expression: str,
        correction_history: Optional[List[Dict[str, Any]]],
    ) -> str:
        guidance_lines = [
            "This is the final correction attempt. Simplify aggressively and prefer a supported "
            "single-expression approximation over a more complex but brittle formula.",
        ]

        if self._requires_supported_proxy(hypothesis, correction_history):
            guidance_lines.append(
                "Use a supported proxy with a single-window, single-branch expression. "
                "Avoid regime switches, conditional trees, or multi-path logic."
            )

        current_score = self._expression_complexity_score(current_expression)
        rejected_scores = [
            self._expression_complexity_score(item.get("corrected_expression") or item.get("expression"))
            for item in (correction_history or [])
        ]
        if rejected_scores and max(rejected_scores) >= current_score:
            guidance_lines.append(
                "Reduce complexity relative to the rejected candidates. Choose an expression "
                "simpler than the rejected candidates and avoid adding branches, extra windows, "
                "or nested operators."
            )

        return "\n".join(guidance_lines)
    
    def check_consistency(
        self,
        hypothesis: str,
        factor_name: str,
        factor_description: str,
        factor_formulation: str,
        factor_expression: str,
        variables: Dict[str, str] = None,
        correction_history: Optional[List[Dict[str, Any]]] = None,
        last_resort: bool = False,
    ) -> ConsistencyCheckResult:
        """Check consistency between hypothesis, description, formulation, expression; return result or corrected fields."""
        if not self.enabled:
            return ConsistencyCheckResult(
                is_consistent=True,
                hypothesis_to_description="Consistency check disabled",
                description_to_formulation="Consistency check disabled",
                formulation_to_expression="Consistency check disabled",
                overall_feedback="Consistency check is disabled, skipping.",
                severity="none"
            )
        
        logger.info(f"Starting consistency check: {factor_name}")
        
        try:
            system_prompt = (
                Environment(undefined=StrictUndefined)
                .from_string(consistency_prompts["consistency_check_system"])
                .render()
            )
            
            user_prompt = (
                Environment(undefined=StrictUndefined)
                .from_string(consistency_prompts["consistency_check_user"])
                .render(
                    hypothesis=hypothesis,
                    factor_name=factor_name,
                    factor_description=factor_description,
                    factor_formulation=factor_formulation,
                    factor_expression=factor_expression,
                    variables=variables or {}
                )
            )

            if correction_history:
                history_lines = [
                    "",
                    "**Previous Correction Attempts:**",
                ]
                for item in correction_history:
                    history_lines.extend(
                        [
                            f"- Attempt {item.get('attempt')}: severity={item.get('severity', 'unknown')}",
                            f"  Feedback: {item.get('feedback', '')}",
                            f"  Rejected expression: {item.get('corrected_expression') or item.get('expression') or ''}",
                        ]
                    )
                history_lines.append(
                    "Do not repeat previously rejected expressions. Address the recorded feedback directly."
                )
                user_prompt += "\n" + "\n".join(history_lines)

            if last_resort:
                user_prompt += (
                    "\n\n**Last Resort Instruction:**\n"
                    + self._last_resort_guidance(
                        hypothesis=hypothesis,
                        current_expression=factor_expression,
                        correction_history=correction_history,
                    )
                )
            
            api = APIBackend()
            messages = api.build_messages(user_prompt=user_prompt, system_prompt=system_prompt)

            result_dict = call_structured(
                api,
                messages,
                tools=[CONSISTENCY_CHECK_TOOL],
                tool_choice="required",
            )
            is_consistent = result_dict.get("is_consistent", False)
            severity = result_dict.get("severity", "none")
            
            result = ConsistencyCheckResult(
                is_consistent=is_consistent,
                hypothesis_to_description=result_dict.get("hypothesis_to_description", ""),
                description_to_formulation=result_dict.get("description_to_formulation", ""),
                formulation_to_expression=result_dict.get("formulation_to_expression", ""),
                overall_feedback=result_dict.get("overall_feedback", ""),
                corrected_expression=result_dict.get("corrected_expression"),
                corrected_description=result_dict.get("corrected_description"),
                severity=severity
            )
            
            if is_consistent:
                logger.info(f"Consistency check passed: {factor_name}")
            else:
                logger.warning(f"Consistency check failed: {factor_name}, severity: {severity}")
                logger.warning(f"Feedback: {result.overall_feedback}")
            
            return result
        
        except Exception as e:
            logger.error(f"Consistency check error: {e}")
            return ConsistencyCheckResult(
                is_consistent=False,
                hypothesis_to_description=f"Error during check: {str(e)}",
                description_to_formulation="",
                formulation_to_expression="",
                overall_feedback=f"Consistency check failed with error: {str(e)}",
                severity="critical"
            )

    def _validate_corrected_expression(self, expression: Optional[str]) -> Tuple[bool, str]:
        if not expression:
            return False, "Empty corrected expression"

        upper_expression = expression.upper()
        for func_name in UNSUPPORTED_CORRECTION_FUNCTIONS:
            if re.search(rf"\b{re.escape(func_name)}\s*\(", upper_expression):
                return False, f"unsupported function in corrected expression: {func_name}"

        if "OPTION A" in upper_expression or "OPTION B" in upper_expression:
            return False, "multi-candidate corrected expression is not allowed"

        return True, ""

    @staticmethod
    def _is_metadata_only_inconsistency(
        result: ConsistencyCheckResult,
        current_expression: str,
        current_description: str,
    ) -> bool:
        has_expression_change = bool(
            result.corrected_expression and result.corrected_expression != current_expression
        )
        has_description_change = bool(
            result.corrected_description and result.corrected_description != current_description
        )
        return not has_expression_change and has_description_change

    def check_and_correct(
        self,
        hypothesis: str,
        factor_name: str,
        factor_description: str,
        factor_formulation: str,
        factor_expression: str,
        variables: Dict[str, str] = None
    ) -> Tuple[ConsistencyCheckResult, str, str]:
        """Check consistency and attempt correction. Returns (result, final_expr, final_desc)."""
        current_expression = factor_expression
        current_description = factor_description
        correction_history: List[Dict[str, Any]] = []
        
        for attempt in range(self.max_correction_attempts):
            result = self.check_consistency(
                hypothesis=hypothesis,
                factor_name=factor_name,
                factor_description=current_description,
                factor_formulation=factor_formulation,
                factor_expression=current_expression,
                variables=variables,
                correction_history=correction_history,
                last_resort=attempt == self.max_correction_attempts - 1,
            )
            
            if result.is_consistent:
                return result, current_expression, current_description
            
            if self.strict_mode:
                logger.warning(f"Strict mode: factor {factor_name} failed, no correction")
                return result, current_expression, current_description

            correction_history.append(
                {
                    "attempt": attempt + 1,
                    "expression": current_expression,
                    "description": current_description,
                    "feedback": result.overall_feedback,
                    "severity": result.severity,
                    "corrected_expression": result.corrected_expression,
                    "corrected_description": result.corrected_description,
                }
            )

            if self._is_metadata_only_inconsistency(result, current_expression, current_description):
                logger.info(
                    f"Reporting metadata-only inconsistency for {factor_name} without auto-correction"
                )
                result.severity = "minor"
                result.overall_feedback = (
                    f"{result.overall_feedback}\n"
                    "Metadata-only inconsistency reported; keeping expression and description unchanged."
                ).strip()
                return result, current_expression, current_description

            if result.corrected_expression and result.corrected_expression != current_expression:
                is_valid_correction, rejection_reason = self._validate_corrected_expression(result.corrected_expression)
                if not is_valid_correction:
                    logger.warning(f"Rejected corrected expression for {factor_name}: {rejection_reason}")
                    result.overall_feedback = (
                        f"{result.overall_feedback}\nRejected corrected expression: {rejection_reason}"
                    ).strip()
                    break
                logger.info(f"Attempting expression correction ({attempt + 1}/{self.max_correction_attempts})")
                logger.info(f"Original: {current_expression}")
                logger.info(f"Corrected: {result.corrected_expression}")
                current_expression = result.corrected_expression
            elif result.corrected_description and result.corrected_description != current_description:
                logger.info(f"Attempting description correction ({attempt + 1}/{self.max_correction_attempts})")
                current_description = result.corrected_description
            else:
                logger.warning(f"Cannot correct factor {factor_name}, giving up")
                break
        
        if correction_history and current_expression == factor_expression and not result.is_consistent:
            return result, current_expression, current_description

        final_result = self.check_consistency(
            hypothesis=hypothesis,
            factor_name=factor_name,
            factor_description=current_description,
            factor_formulation=factor_formulation,
            factor_expression=current_expression,
            variables=variables,
            correction_history=correction_history,
            last_resort=True,
        )
        
        return final_result, current_expression, current_description
    
    def batch_check(
        self,
        hypothesis: str,
        factors: List[Dict[str, Any]]
    ) -> List[Tuple[Dict[str, Any], ConsistencyCheckResult]]:
        """Batch check consistency for multiple factors."""
        results = []
        
        for factor in factors:
            result, corrected_expr, corrected_desc = self.check_and_correct(
                hypothesis=hypothesis,
                factor_name=factor.get("name", "Unknown"),
                factor_description=factor.get("description", ""),
                factor_formulation=factor.get("formulation", ""),
                factor_expression=factor.get("expression", ""),
                variables=factor.get("variables", {})
            )
            
            updated_factor = factor.copy()
            updated_factor["expression"] = corrected_expr
            updated_factor["description"] = corrected_desc
            updated_factor["consistency_check"] = result.to_dict()
            
            results.append((updated_factor, result))
        
        return results
    
    def should_proceed_to_backtest(self, result: ConsistencyCheckResult) -> bool:
        """Whether to proceed to backtest based on consistency result."""
        if not self.enabled:
            return True
        
        if result.is_consistent:
            return True
        
        if self.strict_mode:
            return False
        
        if result.severity in self.allowed_inconsistent_severities:
            return True
        
        return False


class ComplexityChecker:
    """Factor complexity checker: validates expression complexity."""
    
    # Known bad patterns that should be rejected regardless of other metrics
    BAD_PATTERNS = [
        "1/1",           # Trivial
        "$close/$close", # Identity
        "0*$",           # Zeroing out
        "($high-$low)/0" # Division by zero (static)
    ]

    def __init__(
        self,
        enabled: bool = True,
        symbol_length_threshold: int = 220,     # Tightened from 250
        base_features_threshold: int = 5,       # Tightened from 6
        free_args_ratio_threshold: float = 0.45 # Tightened from 0.5
    ):
        """Args: enabled, symbol_length_threshold, base_features_threshold, free_args_ratio_threshold."""
        self.enabled = enabled
        self.symbol_length_threshold = symbol_length_threshold
        self.base_features_threshold = base_features_threshold
        self.free_args_ratio_threshold = free_args_ratio_threshold
    
    def check(self, expression) -> Tuple[bool, str]:
        """Check expression complexity. Returns (passed, feedback)."""
        if not self.enabled:
            return True, "Complexity check disabled"
        
        # Defensive: Handle dict input (e.g., from LLM corrected_expression)
        if isinstance(expression, dict):
            expression = expression.get("code") or expression.get("expression") or str(expression)
        
        # Check for known bad patterns
        expr_clean = expression.replace(" ", "")
        for pattern in self.BAD_PATTERNS:
            if pattern in expr_clean:
                return False, f"Expression contains prohibited trivial or invalid pattern: {pattern}"

        try:
            from quantaalpha.factors.coder.factor_ast import (
                calculate_symbol_length, 
                count_base_features,
                count_free_args,
                count_all_nodes
            )
            
            feedback_parts = []
            passed = True
            
            symbol_length = calculate_symbol_length(expression)
            if symbol_length > self.symbol_length_threshold:
                passed = False
                feedback_parts.append(
                    f"Symbol Length (SL) Check Failed: {symbol_length} > {self.symbol_length_threshold}. "
                    f"Expression is too complex and may lead to overfitting."
                )
            
            num_base_features = count_base_features(expression)
            if num_base_features > self.base_features_threshold:
                passed = False
                feedback_parts.append(
                    f"Base Features (ER) Check Failed: {num_base_features} > {self.base_features_threshold}. "
                    f"Using too many raw features."
                )
            
            num_free_args = count_free_args(expression)
            num_all_nodes = count_all_nodes(expression)
            if num_all_nodes > 0:
                free_args_ratio = num_free_args / num_all_nodes
                if free_args_ratio > self.free_args_ratio_threshold:
                    passed = False
                    feedback_parts.append(
                        f"Free Args Ratio Check Failed: {free_args_ratio:.2%} > {self.free_args_ratio_threshold:.2%}. "
                        f"Factor is over-parameterized."
                    )
            
            if passed:
                return True, "Complexity check passed"
            else:
                return False, "\n".join(feedback_parts)
        
        except Exception as e:
            logger.warning(f"Complexity check failed with error: {e}")
            return True, f"Complexity check skipped due to error: {e}"


class RedundancyChecker:
    """Redundancy checker: detects duplication with existing factors."""
    
    def __init__(
        self,
        enabled: bool = True,
        duplication_threshold: int = 5,
        factor_zoo_path: str = None
    ):
        """Args: enabled, duplication_threshold, factor_zoo_path."""
        self.enabled = enabled
        self.duplication_threshold = duplication_threshold
        self.factor_zoo_path = factor_zoo_path
        self._factor_regulator = None
    
    @property
    def factor_regulator(self):
        """Lazy-load FactorRegulator."""
        if self._factor_regulator is None:
            from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
            self._factor_regulator = FactorRegulator(
                factor_zoo_path=self.factor_zoo_path,
                duplication_threshold=self.duplication_threshold
            )
        return self._factor_regulator
    
    def check(self, expression) -> Tuple[bool, str, Dict[str, Any]]:
        """Check expression redundancy. Returns (passed, feedback, details)."""
        if not self.enabled:
            return True, "Redundancy check disabled", {}
        
        # Defensive: Handle dict input (e.g., from LLM corrected_expression)
        if isinstance(expression, dict):
            expression = expression.get("code") or expression.get("expression") or str(expression)
        
        try:
            if not self.factor_regulator.is_parsable(expression):
                return False, f"Expression cannot be parsed: {expression}", {}
            
            success, eval_dict = self.factor_regulator.evaluate(expression)
            if not success:
                return False, f"Failed to evaluate expression", {}
            
            duplicated_size = eval_dict.get('duplicated_subtree_size', 0)
            if duplicated_size > self.duplication_threshold:
                matched_alpha = eval_dict.get('matched_alpha', 'Unknown')
                duplicated_subtree = eval_dict.get('duplicated_subtree', '')
                return False, (
                    f"Redundancy Check Failed: Duplicated subtree size ({duplicated_size}) "
                    f"exceeds threshold ({self.duplication_threshold}). "
                    f"Matched with: {matched_alpha}. Duplicated subtree: {duplicated_subtree}"
                ), eval_dict
            
            return True, "Redundancy check passed", eval_dict
        
        except Exception as e:
            logger.warning(f"Redundancy check failed with error: {e}")
            return True, f"Redundancy check skipped due to error: {e}", {}


class DataQualityChecker:
    """Reject bad sample profiles before entering expensive backtest stages."""

    def __init__(
        self,
        enabled: bool = True,
        nan_ratio_threshold: float = 0.2,
        valid_ratio_threshold: float = 0.6,
    ):
        self.enabled = enabled
        self.nan_ratio_threshold = nan_ratio_threshold
        self.valid_ratio_threshold = valid_ratio_threshold

    def check(
        self, data_profile: Optional[Dict[str, Any]]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.enabled:
            return True, "Data quality check disabled", {}
        if not data_profile:
            return True, "No data profile provided", {}

        details: Dict[str, Any] = {}
        failures = []

        nan_ratio = data_profile.get("nan_ratio")
        if nan_ratio is not None:
            details["nan_ratio"] = nan_ratio
            if float(nan_ratio) > self.nan_ratio_threshold:
                failures.append(
                    f"nan_ratio {float(nan_ratio):.2f} exceeds {self.nan_ratio_threshold:.2f}"
                )

        has_inf = bool(data_profile.get("has_inf", False))
        details["has_inf"] = has_inf
        if has_inf:
            failures.append("contains inf values")

        is_constant = bool(data_profile.get("is_constant", False))
        details["is_constant"] = is_constant
        if is_constant:
            failures.append("factor values are constant")

        valid_ratio = data_profile.get("valid_ratio")
        if valid_ratio is not None:
            details["valid_ratio"] = valid_ratio
            if float(valid_ratio) < self.valid_ratio_threshold:
                failures.append(
                    f"valid_ratio {float(valid_ratio):.2f} below {self.valid_ratio_threshold:.2f}"
                )

        if failures:
            return False, "; ".join(failures), details
        return True, "Data quality check passed", details


class FactorQualityGate:
    """Factor quality gate: integrates consistency/complexity/redundancy checks to decide if factor can proceed to backtest."""
    
    def __init__(
        self,
        consistency_checker: FactorConsistencyChecker = None,
        complexity_checker: ComplexityChecker = None,
        redundancy_checker: RedundancyChecker = None,
        data_quality_checker: DataQualityChecker = None,
        consistency_enabled: bool = False,
        complexity_enabled: bool = True,
        redundancy_enabled: bool = True,
        data_quality_enabled: bool = True,
    ):
        """Args: consistency_checker, complexity_checker, redundancy_checker, *_enabled flags."""
        self.consistency_checker = consistency_checker or FactorConsistencyChecker(enabled=consistency_enabled)
        self.complexity_checker = complexity_checker or ComplexityChecker(enabled=complexity_enabled)
        self.redundancy_checker = redundancy_checker or RedundancyChecker(enabled=redundancy_enabled)
        self.data_quality_checker = data_quality_checker or DataQualityChecker(enabled=data_quality_enabled)
        
        self.consistency_checker.enabled = consistency_enabled
        self.complexity_checker.enabled = complexity_enabled
        self.redundancy_checker.enabled = redundancy_enabled
        self.data_quality_checker.enabled = data_quality_enabled
    
    def evaluate(
        self,
        hypothesis: str,
        factor_name: str,
        factor_description: str,
        factor_formulation: str,
        factor_expression: str,
        variables: Dict[str, str] = None,
        data_profile: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluate if factor passes quality gate. Returns (passed, overall_feedback, results)."""
        results = {
            "consistency": None,
            "complexity": None,
            "redundancy": None,
            "data_quality": None,
            "corrected_expression": factor_expression,
            "corrected_description": factor_description
        }
        feedbacks = []
        all_passed = True
        
        if self.consistency_checker.enabled:
            consistency_result, corrected_expr, corrected_desc = self.consistency_checker.check_and_correct(
                hypothesis=hypothesis,
                factor_name=factor_name,
                factor_description=factor_description,
                factor_formulation=factor_formulation,
                factor_expression=factor_expression,
                variables=variables
            )
            results["consistency"] = consistency_result.to_dict()
            results["corrected_expression"] = corrected_expr
            results["corrected_description"] = corrected_desc
            
            if not self.consistency_checker.should_proceed_to_backtest(consistency_result):
                all_passed = False
                feedbacks.append(f"[Consistency] {consistency_result.overall_feedback}")
            
            factor_expression = corrected_expr
        
        if self.complexity_checker.enabled:
            complexity_passed, complexity_feedback = self.complexity_checker.check(factor_expression)
            results["complexity"] = {
                "passed": complexity_passed,
                "feedback": complexity_feedback
            }
            
            if not complexity_passed:
                all_passed = False
                feedbacks.append(f"[Complexity] {complexity_feedback}")
        
        if self.redundancy_checker.enabled:
            redundancy_passed, redundancy_feedback, redundancy_details = self.redundancy_checker.check(factor_expression)
            results["redundancy"] = {
                "passed": redundancy_passed,
                "feedback": redundancy_feedback,
                "details": redundancy_details
            }
            
            if not redundancy_passed:
                all_passed = False
                feedbacks.append(f"[Redundancy] {redundancy_feedback}")

        if self.data_quality_checker.enabled:
            data_quality_passed, data_quality_feedback, data_quality_details = (
                self.data_quality_checker.check(data_profile)
            )
            results["data_quality"] = {
                "passed": data_quality_passed,
                "feedback": data_quality_feedback,
                "details": data_quality_details,
            }
            if not data_quality_passed:
                all_passed = False
                feedbacks.append(f"[DataQuality] {data_quality_feedback}")
        
        if all_passed:
            overall_feedback = f"Factor '{factor_name}' passed all quality gates."
            logger.info(overall_feedback)
        else:
            overall_feedback = f"Factor '{factor_name}' failed quality gates:\n" + "\n".join(feedbacks)
            logger.warning(overall_feedback)
        
        return all_passed, overall_feedback, results
