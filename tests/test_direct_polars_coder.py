from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import polars as pl
import pytest


def _standard_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "datetime": [
                pd.Timestamp("2020-01-01"),
                pd.Timestamp("2020-01-01"),
                pd.Timestamp("2020-01-02"),
                pd.Timestamp("2020-01-02"),
            ],
            "instrument": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
            "$open": [10.0, 20.0, 11.0, 18.0],
            "$high": [10.5, 20.5, 11.5, 18.5],
            "$low": [9.5, 19.5, 10.5, 17.5],
            "$close": [12.0, 19.0, 13.0, 20.0],
            "$volume": [100.0, 200.0, 110.0, 180.0],
            "$vwap": [11.0, 19.5, 12.0, 19.0],
            "$return": [0.0, 0.0, 0.1, -0.05],
        }
    )


def _write_runtime_data(tmp_path, monkeypatch) -> tuple[object, object]:
    from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
    from quantaalpha.factors.coder.runtime_data import write_standard_frame_runtime_data

    data_root = tmp_path / "data"
    debug_root = tmp_path / "debug"
    write_standard_frame_runtime_data(frame=_standard_frame(), target_root=data_root)
    write_standard_frame_runtime_data(frame=_standard_frame(), target_root=debug_root)
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))
    return data_root, debug_root


def _task(name: str, expression: str | None):
    from quantaalpha.factors.coder.factor import FactorTask

    return FactorTask(
        factor_name=name,
        factor_description="fixture",
        factor_formulation="fixture",
        factor_expression=expression,
    )


def test_direct_polars_coder_computes_from_expression_and_uses_unique_factor_py(tmp_path, monkeypatch) -> None:
    from quantaalpha.core.conf import RD_AGENT_SETTINGS
    from quantaalpha.core.experiment import Experiment
    from quantaalpha.factors.coder.direct_polars_coder import DirectPolarsCoder

    _write_runtime_data(tmp_path, monkeypatch)
    monkeypatch.setattr(RD_AGENT_SETTINGS, "workspace_path", tmp_path / "workspace")
    monkeypatch.setenv("QUANTAALPHA_FACTOR_CODER_RUNTIME", "polars_parquet")
    exp = Experiment(
        [
            _task("spread_a", "$close - $open"),
            _task("spread_b", "$close - $open + 1"),
        ]
    )

    result = DirectPolarsCoder(SimpleNamespace()).develop(exp)

    assert len(result.sub_workspace_list) == 2
    assert all(workspace is not None for workspace in result.sub_workspace_list)
    first, second = result.sub_workspace_list
    assert first.code_dict["factor.py"] != second.code_dict["factor.py"]
    assert "factor_expression = '$close - $open'" in first.code_dict["factor.py"]
    assert "factor_expression = '$close - $open + 1'" in second.code_dict["factor.py"]
    message, frame = first.execute("All")
    assert "Expected parquet output file found." in message
    assert frame.loc[(pd.Timestamp("2020-01-01"), "000001.SZ"), "spread_a"] == pytest.approx(2.0)


def test_direct_polars_coder_marks_bad_expression_as_none(tmp_path, monkeypatch) -> None:
    from quantaalpha.core.conf import RD_AGENT_SETTINGS
    from quantaalpha.core.experiment import Experiment
    from quantaalpha.factors.coder.direct_polars_coder import DirectPolarsCoder

    _write_runtime_data(tmp_path, monkeypatch)
    monkeypatch.setattr(RD_AGENT_SETTINGS, "workspace_path", tmp_path / "workspace")
    monkeypatch.setenv("QUANTAALPHA_FACTOR_CODER_RUNTIME", "polars_parquet")
    exp = Experiment([_task("bad", "UNSUPPORTED($close, 2)")])

    result = DirectPolarsCoder(SimpleNamespace()).develop(exp)

    assert result.sub_workspace_list == [None]
    evidence_path = result.polars_expression_admission_evidence_path
    payload = json.loads(Path(evidence_path).read_text())
    assert payload["schema_version"] == 1
    assert payload["rejected_count"] == 1
    assert payload["entries"][0]["admission"]["reason_code"] == "unsupported_function"


def test_direct_polars_coder_workspaces_are_consumed_by_runner(tmp_path, monkeypatch) -> None:
    from quantaalpha.core.conf import RD_AGENT_SETTINGS
    from quantaalpha.factors.coder.direct_polars_coder import DirectPolarsCoder
    from quantaalpha.factors.experiment import QlibFactorExperiment
    from quantaalpha.factors.runner import QlibFactorRunner

    _write_runtime_data(tmp_path, monkeypatch)
    monkeypatch.setattr(RD_AGENT_SETTINGS, "workspace_path", tmp_path / "workspace")
    monkeypatch.setenv("QUANTAALPHA_FACTOR_CODER_RUNTIME", "polars_parquet")
    exp = DirectPolarsCoder(SimpleNamespace()).develop(QlibFactorExperiment([_task("spread", "$close - $open")]))

    combined = QlibFactorRunner(SimpleNamespace()).process_factor_data(exp)

    assert list(combined.columns) == ["spread"]
    assert combined.loc[(pd.Timestamp("2020-01-02"), "000002.SZ"), "spread"] == pytest.approx(2.0)


def test_direct_polars_coder_selection_bypasses_configured_coder_for_polars(monkeypatch) -> None:
    from quantaalpha.factors.coder.direct_polars_coder import DirectPolarsCoder
    from quantaalpha.pipeline import loop as loop_module

    def fail_import_class(_path):
        raise AssertionError("configured CoSTEER coder should not be imported for polars_parquet")

    monkeypatch.setattr(loop_module, "import_class", fail_import_class)
    setting = SimpleNamespace(coder="configured.Coder")

    coder = loop_module._create_factor_coder(setting, SimpleNamespace(), " polars_parquet ")

    assert isinstance(coder, DirectPolarsCoder)


def test_direct_polars_coder_selection_keeps_configured_coder_for_other_runtimes(monkeypatch) -> None:
    from quantaalpha.pipeline import loop as loop_module

    class ConfiguredCoder:
        def __init__(self, scen):
            self.scen = scen

    monkeypatch.setattr(loop_module, "import_class", lambda path: ConfiguredCoder)
    scen = SimpleNamespace()
    setting = SimpleNamespace(coder="configured.Coder")

    coder = loop_module._create_factor_coder(setting, scen, "h5")

    assert isinstance(coder, ConfiguredCoder)
    assert coder.scen is scen
