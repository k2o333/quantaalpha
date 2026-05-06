from __future__ import annotations

from .implementation_shared import MiningScheduler
from .mining_generation import MiningGenerationMixin
from .mining_orchestration import MiningOrchestrationMixin
from .mining_pipeline import MiningPipelineMixin
from .mining_setup import MiningSetupMixin
from .mining_validation import MiningValidationMixin


class DefaultMiningScheduler(
    MiningSetupMixin,
    MiningGenerationMixin,
    MiningValidationMixin,
    MiningPipelineMixin,
    MiningOrchestrationMixin,
    MiningScheduler,
):
    """Default mining scheduler using RAG, LLM generation, validation, and orchestration."""
