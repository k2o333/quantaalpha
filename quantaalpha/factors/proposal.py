"""Compatibility facade for factor proposal generation and expression construction."""

from .proposal_expression import AlphaAgentHypothesis2FactorExpression, BacktestHypothesis2FactorExpression
from .proposal_generation import (
    CONSTRUCT_FACTORS_TOOL,
    DEFAULT_HISTORY_LIMIT,
    FEEDBACK_TOOL,
    MAX_FEEDBACK_ITEMS,
    MAX_FEEDBACK_TOTAL_CHARS,
    MIN_HISTORY_LIMIT,
    PROPOSE_FACTORS_TOOL,
    AlphaAgentHypothesis,
    AlphaAgentHypothesisGen,
    EmptyHypothesisGen,
    EnsembleHypothesisBundle,
    QlibFactorHypothesis,
    QlibFactorHypothesis2Experiment,
    QlibFactorHypothesisGen,
    _bound_feedback_accumulation,
    build_ensemble_hypothesis_bundle,
    build_financial_pit_context_hint,
    is_input_length_error,
    normalize_corrected_expression,
    qa_prompt_dict,
    render_hypothesis_and_feedback,
)

__all__ = [name for name in globals() if not name.startswith("__")]
