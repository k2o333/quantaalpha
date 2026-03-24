from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _ensure_experiment_stubs() -> None:
    if "quantaalpha" not in sys.modules:
        pkg = types.ModuleType("quantaalpha")
        pkg.__path__ = [str(PKG_ROOT)]
        sys.modules["quantaalpha"] = pkg

    if "quantaalpha.factors" not in sys.modules:
        pkg = types.ModuleType("quantaalpha.factors")
        pkg.__path__ = [str(PKG_ROOT / "factors")]
        sys.modules["quantaalpha.factors"] = pkg

    if "quantaalpha.factors.workspace" not in sys.modules:
        workspace_mod = types.ModuleType("quantaalpha.factors.workspace")

        class QlibFBWorkspace:
            def __init__(self, *args, **kwargs) -> None:
                self.args = args
                self.kwargs = kwargs

        workspace_mod.QlibFBWorkspace = QlibFBWorkspace
        sys.modules["quantaalpha.factors.workspace"] = workspace_mod

    if "quantaalpha.factors.qlib_utils" not in sys.modules:
        qlib_utils_mod = types.ModuleType("quantaalpha.factors.qlib_utils")
        qlib_utils_mod.get_data_folder_intro = lambda use_local=True: f"base_source_data(use_local={use_local})"
        sys.modules["quantaalpha.factors.qlib_utils"] = qlib_utils_mod

    if "quantaalpha.log" not in sys.modules:
        log_mod = types.ModuleType("quantaalpha.log")
        log_mod.warning_calls = []

        class _Logger:
            def warning(self, *args, **kwargs) -> None:
                log_mod.warning_calls.append((args, kwargs))

        log_mod.logger = _Logger()
        sys.modules["quantaalpha.log"] = log_mod

    if "rdagent" not in sys.modules:
        sys.modules["rdagent"] = types.ModuleType("rdagent")

    if "rdagent.core" not in sys.modules:
        core_pkg = types.ModuleType("rdagent.core")
        core_pkg.__path__ = []
        sys.modules["rdagent.core"] = core_pkg

    if "rdagent.core.scenario" not in sys.modules:
        scenario_mod = types.ModuleType("rdagent.core.scenario")

        class Scenario:
            def __init__(self) -> None:
                pass

        scenario_mod.Scenario = Scenario
        sys.modules["rdagent.core.scenario"] = scenario_mod

    if "rdagent.utils" not in sys.modules:
        utils_pkg = types.ModuleType("rdagent.utils")
        utils_pkg.__path__ = []
        sys.modules["rdagent.utils"] = utils_pkg

    if "rdagent.utils.agent" not in sys.modules:
        agent_pkg = types.ModuleType("rdagent.utils.agent")
        agent_pkg.__path__ = []
        sys.modules["rdagent.utils.agent"] = agent_pkg

    if "rdagent.utils.agent.tpl" not in sys.modules:
        tpl_mod = types.ModuleType("rdagent.utils.agent.tpl")

        class _Template:
            def __init__(self, key: str) -> None:
                self.key = key

            def r(self, **kwargs) -> str:
                return f"{self.key}|{sorted(kwargs.items())}"

        tpl_mod.T = _Template
        sys.modules["rdagent.utils.agent.tpl"] = tpl_mod

    if "rdagent.scenarios" not in sys.modules:
        scenarios_pkg = types.ModuleType("rdagent.scenarios")
        scenarios_pkg.__path__ = []
        sys.modules["rdagent.scenarios"] = scenarios_pkg

    if "rdagent.scenarios.qlib" not in sys.modules:
        qlib_pkg = types.ModuleType("rdagent.scenarios.qlib")
        qlib_pkg.__path__ = []
        sys.modules["rdagent.scenarios.qlib"] = qlib_pkg

    if "rdagent.scenarios.qlib.experiment" not in sys.modules:
        exp_pkg = types.ModuleType("rdagent.scenarios.qlib.experiment")
        exp_pkg.__path__ = []
        sys.modules["rdagent.scenarios.qlib.experiment"] = exp_pkg

    if "rdagent.scenarios.qlib.experiment.factor_experiment" not in sys.modules:
        factor_exp_mod = types.ModuleType("rdagent.scenarios.qlib.experiment.factor_experiment")

        class QlibFactorScenario:
            def get_runtime_environment(self):
                return "stub-runtime"

            @property
            def source_data(self) -> str:
                return self._source_data

        class FactorExperiment:
            def __init__(self, *args, **kwargs) -> None:
                self.args = args
                self.kwargs = kwargs

        class FactorTask:
            pass

        class FactorFBWorkspace:
            pass

        class QlibFactorExperiment:
            def __init__(self, *args, **kwargs) -> None:
                self.args = args
                self.kwargs = kwargs

        factor_exp_mod.QlibFactorScenario = QlibFactorScenario
        factor_exp_mod.FactorExperiment = FactorExperiment
        factor_exp_mod.FactorTask = FactorTask
        factor_exp_mod.FactorFBWorkspace = FactorFBWorkspace
        factor_exp_mod.QlibFactorExperiment = QlibFactorExperiment
        sys.modules["rdagent.scenarios.qlib.experiment.factor_experiment"] = factor_exp_mod


def test_render_data_capabilities_uses_defaults_and_stable_order():
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    rendered = data_capability.render_data_capabilities(
        {
            "financial": {"fields": ["$roe"]},
            "price_volume": {
                "fields": ["$close"],
                "freq": "daily",
                "lag_days": 0,
                "join_mode": "same_day",
                "factor_hints": ["momentum"],
            },
        }
    )

    assert "Available data capabilities:" in rendered
    assert rendered.index("- financial:") < rendered.index("- price_volume:")
    assert "freq=unknown" not in rendered
    assert "lag_days=0" in rendered
    assert "join_mode=same_day" in rendered
    assert "typical_uses=general research" in rendered


def test_normalize_capability_spec_applies_conservative_defaults():
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    normalized = data_capability.normalize_capability_spec({"fields": ["$close"]})

    assert normalized == {
        "fields": ["$close"],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": [],
        "available_from": None,
    }


def test_normalize_capability_spec_treats_null_like_missing():
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    normalized = data_capability.normalize_capability_spec(
        {
            "fields": None,
            "freq": None,
            "lag_days": None,
            "join_mode": None,
            "factor_hints": None,
        }
    )

    assert normalized == {
        "fields": [],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": [],
        "available_from": None,
    }


def test_scenario_injects_registry_when_enabled():
    _ensure_experiment_stubs()
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )
    experiment = _load_module(
        "quantaalpha.factors.experiment",
        PKG_ROOT / "factors" / "experiment.py",
    )

    scenario = experiment.QlibAlphaAgentScenario(
        use_local=False,
        data_capability_registry_enabled=True,
        data_capabilities={"financial": {"fields": ["$roe"]}},
    )

    assert "base_source_data(use_local=False)" in scenario.source_data
    assert "Available data capabilities:" in scenario.source_data
    assert "financial" in scenario.source_data
    assert data_capability.render_data_capabilities({"financial": {"fields": ["$roe"]}}) in scenario.source_data


def test_scenario_skips_registry_when_disabled():
    _ensure_experiment_stubs()
    _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )
    experiment = _load_module(
        "quantaalpha.factors.experiment",
        PKG_ROOT / "factors" / "experiment.py",
    )

    scenario = experiment.QlibAlphaAgentScenario(
        use_local=True,
        data_capability_registry_enabled=False,
    )

    assert scenario.source_data == "base_source_data(use_local=True)"
    assert "Available data capabilities:" not in scenario.source_data


def test_scenario_falls_back_to_base_source_data_on_registry_failure():
    _ensure_experiment_stubs()
    log_mod = sys.modules["quantaalpha.log"]
    log_mod.warning_calls.clear()
    _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )
    experiment = _load_module(
        "quantaalpha.factors.experiment",
        PKG_ROOT / "factors" / "experiment.py",
    )

    scenario = experiment.QlibAlphaAgentScenario(
        use_local=True,
        data_capability_registry_enabled=True,
        data_capabilities={"price_volume": "invalid-spec"},
    )

    assert scenario.source_data == "base_source_data(use_local=True)"
    assert len(log_mod.warning_calls) == 1
    args, kwargs = log_mod.warning_calls[0]
    assert "Failed to inject data capability registry" in args[0]
    assert kwargs["exc_info"] is True
