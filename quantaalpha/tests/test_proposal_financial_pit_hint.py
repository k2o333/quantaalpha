"""Tests for proposal-level financial PIT context hints."""

import importlib
import sys
import tempfile
import types
from pathlib import Path

import polars as pl


def _install_proposal_import_stub():
    fake_experiment_mod = types.ModuleType("quantaalpha.factors.experiment")

    class _DummyQlibFactorExperiment:
        def __init__(self, *args, **kwargs):
            pass

    fake_experiment_mod.QlibFactorExperiment = _DummyQlibFactorExperiment
    sys.modules["quantaalpha.factors.experiment"] = fake_experiment_mod


def _write_pit_parquet(path: Path) -> None:
    df = pl.DataFrame(
        {
            "instrument": ["000001.SZ", "000002.SZ"],
            "report_period": ["20231231", "20231231"],
            "disclosure_date": ["2024-03-28", "2024-03-29"],
            "alias": ["$basic_eps", "$basic_eps"],
            "value": [1.3, 0.8],
            "source_interface": ["income_vip", "income_vip"],
            "source_field": ["basic_eps", "basic_eps"],
            "revision_seq": [1, 0],
            "next_disclosure_date": [None, None],
            "is_latest": [True, True],
        }
    )
    df.write_parquet(path)


def test_build_financial_pit_context_hint_includes_preview():
    _install_proposal_import_stub()
    proposal = importlib.import_module("quantaalpha.factors.proposal")

    with tempfile.TemporaryDirectory() as tmpdir:
        pit_path = Path(tmpdir) / "income_vip.parquet"
        _write_pit_parquet(pit_path)
        capabilities = {
            "income_vip": {
                "fields": ["$basic_eps"],
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

        hint = proposal.build_financial_pit_context_hint(capabilities)
        assert "Financial PIT capability available: income_vip" in hint
        assert "use disclosure-date as-of semantics" in hint
        assert "Financial PIT panel preview" in hint
        assert "$basic_eps" in hint
        assert "000001.SZ" in hint
