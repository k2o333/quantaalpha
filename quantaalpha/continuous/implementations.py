"""Compatibility facade for default continuous orchestration implementations."""

from __future__ import annotations

import sys
import types

from .data_monitor import DefaultDataMonitor
from .implementation_shared import RETURN_ALIAS_EXPRESSION, _translate_factor_expression, logger
from .mining_scheduler import DefaultMiningScheduler
from .revalidation_scheduler import DefaultRevalidationScheduler

__all__ = [
    "RETURN_ALIAS_EXPRESSION",
    "_translate_factor_expression",
    "DefaultDataMonitor",
    "DefaultRevalidationScheduler",
    "DefaultMiningScheduler",
    "logger",
]


class _ImplementationFacadeModule(types.ModuleType):
    """Propagate compatibility monkeypatches from the facade to split modules."""

    _LOGGER_MODULES = (
        "quantaalpha.continuous.data_monitor",
        "quantaalpha.continuous.implementation_shared",
        "quantaalpha.continuous.mining_generation",
        "quantaalpha.continuous.mining_orchestration",
        "quantaalpha.continuous.mining_pipeline",
        "quantaalpha.continuous.mining_scheduler",
        "quantaalpha.continuous.mining_setup",
        "quantaalpha.continuous.mining_validation",
        "quantaalpha.continuous.revalidation_scheduler",
    )

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "logger":
            for module_name in self._LOGGER_MODULES:
                module = sys.modules.get(module_name)
                if module is not None:
                    setattr(module, name, value)


sys.modules[__name__].__class__ = _ImplementationFacadeModule
