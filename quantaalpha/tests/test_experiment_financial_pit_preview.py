"""Tests for financial PIT panel preview injection into experiment source data."""

import importlib
import json
import sys
import tempfile
import types
from pathlib import Path

import polars as pl


def _install_experiment_import_stubs():
    fake_factor_mod = types.ModuleType("rdagent.scenarios.qlib.experiment.factor_experiment")

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

    fake_factor_mod.QlibFactorScenario = _Dummy
    fake_factor_mod.FactorExperiment = _Dummy
    fake_factor_mod.FactorTask = _Dummy
    fake_factor_mod.FactorFBWorkspace = _Dummy
    fake_factor_mod.QlibFactorExperiment = _Dummy

    fake_tpl_mod = types.ModuleType("rdagent.utils.agent.tpl")

    class _DummyT:
        def __init__(self, *_args, **_kwargs):
            pass

        def r(self, **_kwargs):
            return ""

    fake_tpl_mod.T = _DummyT

    fake_workspace_mod = types.ModuleType("quantaalpha.factors.workspace")
    fake_workspace_mod.QlibFBWorkspace = _Dummy

    sys.modules["rdagent.scenarios.qlib.experiment.factor_experiment"] = fake_factor_mod
    sys.modules["rdagent.utils.agent.tpl"] = fake_tpl_mod
    sys.modules["quantaalpha.factors.workspace"] = fake_workspace_mod


def _write_pit_parquet(path: Path) -> None:
    df = pl.DataFrame(
        {
            "instrument": ["000001.SZ", "000001.SZ", "000002.SZ"],
            "report_period": ["20231231", "20240630", "20231231"],
            "disclosure_date": ["2024-03-28", "2024-08-29", "2024-03-29"],
            "alias": ["$basic_eps", "$n_income", "$basic_eps"],
            "value": [1.3, 10.0, 0.8],
            "source_interface": ["income_vip", "income_vip", "income_vip"],
            "source_field": ["basic_eps", "n_income", "basic_eps"],
            "revision_seq": [1, 0, 0],
            "next_disclosure_date": [None, None, None],
            "is_latest": [True, True, True],
        }
    )
    df.write_parquet(path)


def test_build_source_data_description_includes_financial_pit_preview():
    _install_experiment_import_stubs()
    experiment = importlib.import_module("quantaalpha.factors.experiment")

    with tempfile.TemporaryDirectory() as tmpdir:
        pit_path = Path(tmpdir) / "income_vip.parquet"
        _write_pit_parquet(pit_path)
        capabilities = {
            "income_vip": {
                "fields": ["$basic_eps", "$n_income"],
                "freq": "quarterly",
                "lag_days": 45,
                "join_mode": "forward_fill",
                "factor_hints": ["fundamental"],
                "layer": "financial_pit",
                "storage_kind": "financial_pit_parquet",
                "storage_path": str(pit_path),
                "versioned": True,
            }
        }

        text = experiment._build_source_data_description(
            use_local=True,
            registry_enabled=True,
            capabilities=capabilities,
        )

        assert "Financial PIT panel preview" in text
        assert "income_vip" in text
        assert "$basic_eps" in text
        assert "000001.SZ" in text
