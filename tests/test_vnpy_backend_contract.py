from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _tiny_market(rows: int = 80) -> pd.DataFrame:
    payload = []
    dates = pd.date_range("2020-01-01", periods=rows, freq="D")
    for day_index, dt in enumerate(dates):
        for stock_index, instrument in enumerate(["A", "B", "C", "D", "E"]):
            close = 10 + day_index * 0.1 + stock_index * 0.2
            payload.append(
                {
                    "trade_date": dt.strftime("%Y%m%d"),
                    "ts_code": instrument,
                    "open": close * 0.99,
                    "high": close * 1.01,
                    "low": close * 0.98,
                    "close": close,
                    "vol": 1000 + stock_index,
                    "amount": close * (1000 + stock_index),
                    "pct_chg": 0.1 + stock_index * 0.01,
                }
            )
    return pd.DataFrame(payload)


def _write_vnpy_config(tmp_path: Path, market_path: Path, factors_path: Path) -> Path:
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "backtest_runtime": {
                    "backend": "vnpy",
                    "noqlib": {"market_data_path": str(market_path)},
                    "vnpy": {"expression_translation": "shared_polars"},
                },
                "factor_source": {"type": "custom", "custom": {"json_files": [str(factors_path)]}},
                "data": {"start_time": "2020-01-01", "end_time": "2020-03-20", "market": "all"},
                "dataset": {
                    "label": "Ref($close, -2) / Ref($close, -1) - 1",
                    "segments": {
                        "train": ["2020-01-01", "2020-02-10"],
                        "valid": ["2020-02-11", "2020-02-20"],
                        "test": ["2020-02-21", "2020-03-20"],
                    },
                },
                "model": {"type": "lgb", "params": {"learning_rate": 0.05, "num_leaves": 7, "num_boost_round": 5, "verbose": -1}},
                "backtest": {
                    "strategy": {"kwargs": {"topk": 3, "n_drop": 1}},
                    "backtest": {
                        "start_time": "2020-02-21",
                        "end_time": "2020-03-15",
                        "benchmark": "mean",
                        "exchange_kwargs": {"open_cost": 0.0, "close_cost": 0.0},
                    },
                },
                "experiment": {
                    "name": "vnpy_tmp",
                    "recorder": "tmp",
                    "output_dir": str(tmp_path / "out"),
                    "output_metrics_file": "metrics.json",
                },
            }
        ),
        encoding="utf-8",
    )
    return cfg_path


def test_resolve_backend_accepts_vnpy_and_triple_parity() -> None:
    from quantaalpha.backtest.facade import resolve_backend

    assert resolve_backend({"backtest_runtime": {"backend": "vnpy"}}) == "vnpy"
    assert resolve_backend({"backtest_runtime": {"backend": "triple_parity"}}) == "triple_parity"
    with pytest.raises(ValueError):
        resolve_backend({"backtest_runtime": {"backend": "unknown"}})


def test_vnpy_facade_construction_does_not_import_qlib(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quantaalpha.backtest.facade import BacktestFacade

    cfg_path = tmp_path / "backtest.yaml"
    cfg_path.write_text(json.dumps({"backtest_runtime": {"backend": "vnpy"}}), encoding="utf-8")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "qlib" or name.startswith("qlib."):
            raise AssertionError(f"vnpy facade imported qlib: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    facade = BacktestFacade(str(cfg_path), backend="vnpy")
    assert facade.backend == "vnpy"


def test_vnpy_projection_is_reversible() -> None:
    from quantaalpha.backtest.vnpy.data_provider import VnpyMarketDataProvider

    market = pd.DataFrame(
        {
            "datetime": [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-01")],
            "instrument": ["000001.SZ", "A"],
            "close": [1.0, 2.0],
            "volume": [10.0, 20.0],
            "open": [1.0, 2.0],
            "high": [1.0, 2.0],
            "low": [1.0, 2.0],
        }
    )
    provider = VnpyMarketDataProvider(market)
    vnpy_frame = provider.to_vnpy_frame()
    restored = provider.restore_instrument(vnpy_frame)
    assert {"datetime", "vt_symbol", "close", "volume"} <= set(vnpy_frame.columns)
    assert restored.get_column("instrument").to_list() == ["000001.SZ", "A"]
    assert provider.mapping["A"] == "A.LOCAL"


def test_vnpy_projection_missing_columns_fail_fast() -> None:
    from quantaalpha.backtest.vnpy.data_provider import VnpyMarketDataProvider

    with pytest.raises(ValueError, match="missing columns"):
        VnpyMarketDataProvider(pd.DataFrame({"datetime": ["2020-01-01"], "instrument": ["A"]})).to_vnpy_frame()


def test_vnpy_backend_runs_tiny_csv_without_qlib(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quantaalpha.backtest.facade import BacktestFacade

    market_path = tmp_path / "market.csv"
    _tiny_market().to_csv(market_path, index=False)
    factors_path = tmp_path / "factors.json"
    factors_path.write_text(
        json.dumps({"factors": {"f1": {"factor_name": "CloseFactor", "factor_expression": "$close"}}}),
        encoding="utf-8",
    )
    cfg_path = _write_vnpy_config(tmp_path, market_path, factors_path)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "qlib" or name.startswith("qlib."):
            raise AssertionError(f"vnpy backend imported qlib: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = BacktestFacade(str(cfg_path), backend="vnpy").run()
    assert {"IC", "Rank IC", "annualized_return", "information_ratio"} <= set(result)
    assert result["backend"] == "vnpy"
    assert (tmp_path / "out" / "metrics.json").exists()
