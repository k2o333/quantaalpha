from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
import os


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


def test_ensure_conda_default_env_infers_name_from_sys_prefix(monkeypatch):
    _ensure_experiment_stubs()
    experiment = _load_module(
        "quantaalpha.factors.experiment",
        PKG_ROOT / "factors" / "experiment.py",
    )

    monkeypatch.delenv("CONDA_DEFAULT_ENV", raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setattr(experiment.sys, "prefix", "/root/miniforge3/envs/mining")
    monkeypatch.setattr(experiment.sys, "base_prefix", "/root/miniforge3")
    monkeypatch.setattr(experiment.sys, "executable", "/root/miniforge3/envs/mining/bin/python")

    resolved = experiment._ensure_conda_default_env()

    assert resolved == "mining"
    assert os.environ["CONDA_DEFAULT_ENV"] == "mining"


def test_ensure_conda_default_env_preserves_existing_env(monkeypatch):
    _ensure_experiment_stubs()
    experiment = _load_module(
        "quantaalpha.factors.experiment",
        PKG_ROOT / "factors" / "experiment.py",
    )

    monkeypatch.setenv("CONDA_DEFAULT_ENV", "already-set")
    monkeypatch.setattr(experiment.sys, "prefix", "/root/miniforge3/envs/mining")
    monkeypatch.setattr(experiment.sys, "base_prefix", "/root/miniforge3")
    monkeypatch.setattr(experiment.sys, "executable", "/root/miniforge3/envs/mining/bin/python")

    resolved = experiment._ensure_conda_default_env()

    assert resolved == "already-set"
    assert os.environ["CONDA_DEFAULT_ENV"] == "already-set"


# =============================================================================
# Tests for load_from_report() - report-driven capability loading
# =============================================================================

import json
import tempfile


def test_load_from_report_returns_correct_capability_shape(tmp_path):
    """load_from_report() must return the same shape expected by get_data_capabilities()."""
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    # Create a minimal valid report JSON
    report = {
        "version": "1.0",
        "generated_at": "2026-04-01T00:00:00",
        "interfaces": {
            "daily": {
                "mode": "date_range",
                "periods": {
                    "2020-2024": {
                        "date_saturation": 0.95,
                        "stock_coverage": 0.98,
                    }
                },
                "fields": ["ts_code", "trade_date", "open", "close"],
                "field_aliases": ["$open", "$close"],
                "freq": "daily",
                "lag_days": 0,
                "factor_hints": ["momentum", "reversal"],
            }
        },
    }
    report_path = tmp_path / ".data_capability_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = data_capability.load_from_report(report_path)

    # Must return a dict with capability name keys
    assert isinstance(result, dict)
    assert "daily" in result
    cap = result["daily"]
    # Must have the expected keys from get_data_capabilities() consumers
    assert "fields" in cap
    assert "freq" in cap
    assert "lag_days" in cap
    assert "available_from" in cap
    assert "join_mode" in cap
    assert "factor_hints" in cap


def test_load_from_report_fields_from_field_aliases(tmp_path):
    """fields must come from JSON field_aliases, not raw source fields."""
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    report = {
        "version": "1.0",
        "generated_at": "2026-04-01T00:00:00",
        "interfaces": {
            "daily": {
                "mode": "date_range",
                "periods": {
                    "2020-2024": {
                        "date_saturation": 0.95,
                    }
                },
                "fields": ["ts_code", "trade_date", "open", "close", "high", "low"],
                "field_aliases": ["$open", "$close", "$high", "$low"],
                "freq": "daily",
                "lag_days": 0,
                "factor_hints": ["momentum"],
            }
        },
    }
    report_path = tmp_path / ".data_capability_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = data_capability.load_from_report(report_path)

    # fields must be from field_aliases, not from raw fields
    assert result["daily"]["fields"] == ["$open", "$close", "$high", "$low"]
    assert "ts_code" not in result["daily"]["fields"]
    assert "trade_date" not in result["daily"]["fields"]


def test_load_from_report_fallback_to_data_capabilities_on_missing_report():
    """Must fallback to DATA_CAPABILITIES when report file does not exist."""
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    # Call with a path that definitely doesn't exist
    result = data_capability.load_from_report(Path("/nonexistent/path/report.json"))

    # Must return DATA_CAPABILITIES fallback
    assert isinstance(result, dict)
    assert "price_volume" in result
    assert "financial" in result


def test_load_from_report_respects_saturation_threshold(tmp_path):
    """Interfaces with date_saturation below threshold must be filtered out."""
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    report = {
        "version": "1.0",
        "generated_at": "2026-04-01T00:00:00",
        "interfaces": {
            "daily": {
                "mode": "date_range",
                "periods": {
                    "2020-2024": {
                        "date_saturation": 0.95,
                    }
                },
                "fields": ["open", "close"],
                "field_aliases": ["$open", "$close"],
                "freq": "daily",
                "lag_days": 0,
                "factor_hints": ["momentum"],
            },
            "sparse_data": {
                "mode": "date_range",
                "periods": {
                    "2020-2024": {
                        "date_saturation": 0.30,  # Below typical 0.5 threshold
                    }
                },
                "fields": ["some_field"],
                "field_aliases": ["$some_alias"],
                "freq": "daily",
                "lag_days": 0,
                "factor_hints": [],
            },
        },
    }
    report_path = tmp_path / ".data_capability_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = data_capability.load_from_report(report_path, saturation_threshold=0.5)

    # High saturation interface must be present
    assert "daily" in result
    # Low saturation interface must be filtered out
    assert "sparse_data" not in result


def test_load_from_report_filters_interfaces_without_field_aliases(tmp_path):
    """Interfaces without field_aliases must be filtered out."""
    data_capability = _load_module(
        "quantaalpha.factors.data_capability",
        PKG_ROOT / "factors" / "data_capability.py",
    )

    report = {
        "version": "1.0",
        "generated_at": "2026-04-01T00:00:00",
        "interfaces": {
            "daily": {
                "mode": "date_range",
                "periods": {
                    "2020-2024": {
                        "date_saturation": 0.95,
                    }
                },
                "fields": ["open", "close"],
                "field_aliases": ["$open", "$close"],
                "freq": "daily",
                "lag_days": 0,
                "factor_hints": ["momentum"],
            },
            "auxiliary": {
                "mode": "date_range",
                "periods": {
                    "2020-2024": {
                        "date_saturation": 0.99,
                    }
                },
                "fields": ["cal_date", "is_open"],
                "field_aliases": [],  # No aliases - should be filtered
                "freq": "daily",
                "lag_days": 0,
                "factor_hints": [],
            },
        },
    }
    report_path = tmp_path / ".data_capability_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    result = data_capability.load_from_report(report_path)

    assert "daily" in result
    assert "auxiliary" not in result
