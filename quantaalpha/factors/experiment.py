"""
QuantaAlpha factor experiment module: Scenario and Experiment classes.
Uses project QlibFBWorkspace (no ProcessInf / pandas 1.5.x issues).
"""

from copy import deepcopy
import os
from pathlib import Path
import sys
from typing import Any

import yaml

from rdagent.scenarios.qlib.experiment.factor_experiment import (  # type: ignore
    QlibFactorScenario,
    FactorExperiment,
    FactorTask,
    FactorFBWorkspace,
)
from rdagent.utils.agent.tpl import T

from quantaalpha.factors.workspace import QlibFBWorkspace
from rdagent.scenarios.qlib.experiment.factor_experiment import (
    QlibFactorExperiment as _OrigQlibFactorExperiment,
)
from quantaalpha.factors.data_capability import render_data_capabilities, render_financial_pit_panel_preview
from quantaalpha.log import logger


EXPERIMENT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "experiment.yaml"
DEFAULT_REGISTRY_ENABLED = True


def _infer_conda_env_name() -> str | None:
    candidates = [
        os.environ.get("CONDA_PREFIX"),
        sys.prefix,
        Path(sys.executable).resolve().parent.parent.as_posix(),
    ]
    for raw_path in candidates:
        if not raw_path:
            continue
        path = Path(raw_path)
        parts = path.parts
        try:
            envs_index = parts.index("envs")
        except ValueError:
            continue
        if envs_index + 1 < len(parts):
            return parts[envs_index + 1]
    return None


def _ensure_conda_default_env() -> str | None:
    env_name = os.environ.get("CONDA_DEFAULT_ENV")
    if env_name:
        return env_name

    inferred = _infer_conda_env_name()
    if inferred:
        os.environ["CONDA_DEFAULT_ENV"] = inferred
    return inferred


def _load_experiment_config(config_path: Path = EXPERIMENT_CONFIG_PATH) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _is_registry_enabled(
    registry_enabled: bool | None = None,
    config_path: Path = EXPERIMENT_CONFIG_PATH,
) -> bool:
    if registry_enabled is not None:
        return registry_enabled
    run_config = _load_experiment_config(config_path)
    registry_config = run_config.get("data_capability_registry", {})
    return bool(registry_config.get("enabled", DEFAULT_REGISTRY_ENABLED))


def _merge_source_data_with_registry(base_source_data: str, registry_text: str | None) -> str:
    if not registry_text:
        return base_source_data
    return f"{base_source_data}\n\n{registry_text}"


def _build_source_data_description(
    use_local: bool,
    registry_enabled: bool,
    capabilities: dict[str, dict[str, Any]] | None = None,
) -> str:
    from quantaalpha.factors.qlib_utils import get_data_folder_intro as local_get_data_folder_intro

    base_source_data = deepcopy(local_get_data_folder_intro(use_local=use_local))
    if not registry_enabled:
        return base_source_data

    registry_text = render_data_capabilities(capabilities)
    merged = _merge_source_data_with_registry(base_source_data, registry_text)

    if capabilities:
        for name, spec in capabilities.items():
            if spec.get("layer") != "financial_pit":
                continue
            preview = render_financial_pit_panel_preview(name, spec)
            if preview:
                merged = f"{merged}\n\n{preview}"
                break

    return merged


class QlibFactorExperiment(_OrigQlibFactorExperiment):
    """Override rdagent QlibFactorExperiment with project QlibFBWorkspace (correct config template)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        import rdagent.scenarios.qlib.experiment.factor_experiment as _fe_mod

        rdagent_template_path = Path(_fe_mod.__file__).parent / "factor_template"
        self.experiment_workspace = QlibFBWorkspace(
            template_folder_path=rdagent_template_path
        )


class QlibAlphaAgentScenario(QlibFactorScenario):
    """Scenario wrapper for AlphaAgent: accepts use_local; when True uses local get_data_folder_intro (no Docker)."""

    def __init__(self, use_local: bool = True, *args, **kwargs):
        from rdagent.core.scenario import Scenario

        _ensure_conda_default_env()

        registry_enabled = kwargs.pop("data_capability_registry_enabled", None)
        capabilities = kwargs.pop("data_capabilities", None)
        config_path = kwargs.pop("experiment_config_path", EXPERIMENT_CONFIG_PATH)
        self.data_capabilities = capabilities

        Scenario.__init__(self)
        tpl_prefix = "scenarios.qlib.experiment.prompts"

        self._background = deepcopy(
            T(f"{tpl_prefix}:qlib_factor_background").r(
                runtime_environment=self.get_runtime_environment(),
            )
        )
        resolved_registry_enabled = _is_registry_enabled(
            registry_enabled=registry_enabled,
            config_path=Path(config_path),
        )
        try:
            source_data = _build_source_data_description(
                use_local=use_local,
                registry_enabled=resolved_registry_enabled,
                capabilities=capabilities,
            )
        except Exception as exc:
            from quantaalpha.factors.qlib_utils import get_data_folder_intro as local_get_data_folder_intro

            logger.warning(
                f"Failed to inject data capability registry, falling back to basic source data: {exc}",
            )
            source_data = deepcopy(local_get_data_folder_intro(use_local=use_local))
        self._source_data = source_data
        self._output_format = deepcopy(T(f"{tpl_prefix}:qlib_factor_output_format").r())
        self._interface = deepcopy(T(f"{tpl_prefix}:qlib_factor_interface").r())
        self._strategy = deepcopy(T(f"{tpl_prefix}:qlib_factor_strategy").r())
        self._simulator = deepcopy(T(f"{tpl_prefix}:qlib_factor_simulator").r())
        self._rich_style_description = deepcopy(T(f"{tpl_prefix}:qlib_factor_rich_style_description").r())
        self._experiment_setting = deepcopy(T(f"{tpl_prefix}:qlib_factor_experiment_setting").r())
