"""Pytest collection facade for split large-file tests."""

from .continuous_runtime_hooks_core import test_factor_ops_cycle_hook_uses_app5_and_returns_structured_summary, TestRunFactorBacktest, TestValidateFactor, TestGenerateFactors, TestRetrieveContext, TestMutationGeneration, TestValidationResultContract, TestGeneratedFactorCandidateContract
from .continuous_runtime_hooks_bridge import TestBridgeDataIntegration, TestMinIcHardcoding, TestMutateTimeWindowsCascade, TestMutateSimpleVariationRemoval, TestMutationIsParsableFilter, TestMutationBugFixes, TestPerFactorTimeoutEnforcement
from .continuous_runtime_hooks_orchestration import TestPhase4RuntimeEvolution, TestPhase5OrchestrationTrace, TestPhase6LLMAdvisorRuntime
from .continuous_runtime_hooks_production import TestPhase7OrchestrationIntegration, TestPhase8ProductionReadiness, test_parquet_revalidation_respects_days_threshold_before_limit, TestValidationEnrichment

__all__ = [
    "test_factor_ops_cycle_hook_uses_app5_and_returns_structured_summary",
    "TestRunFactorBacktest",
    "TestValidateFactor",
    "TestGenerateFactors",
    "TestRetrieveContext",
    "TestMutationGeneration",
    "TestValidationResultContract",
    "TestGeneratedFactorCandidateContract",
    "TestBridgeDataIntegration",
    "TestMinIcHardcoding",
    "TestMutateTimeWindowsCascade",
    "TestMutateSimpleVariationRemoval",
    "TestMutationIsParsableFilter",
    "TestMutationBugFixes",
    "TestPerFactorTimeoutEnforcement",
    "TestPhase4RuntimeEvolution",
    "TestPhase5OrchestrationTrace",
    "TestPhase6LLMAdvisorRuntime",
    "TestPhase7OrchestrationIntegration",
    "TestPhase8ProductionReadiness",
    "test_parquet_revalidation_respects_days_threshold_before_limit",
    "TestValidationEnrichment",
]
