from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"


def _ensure_stubs():
    if "pandas" not in sys.modules:
        stub = types.ModuleType("pandas")
        stub.Series = type("Series", (), {})
        stub.DataFrame = type("DataFrame", (), {})
        stub.read_hdf = lambda *a, **k: None
        stub.Timedelta = type("Timedelta", (), {})
        sys.modules["pandas"] = stub
    if "numpy" not in sys.modules:
        np_stub = types.ModuleType("numpy")
        np_stub.inf = float("inf")
        np_stub.nan = float("nan")
        np_stub.floating = (float,)
        np_stub.isnan = lambda x: False
        np_stub.isinf = lambda x: False
        sys.modules["numpy"] = np_stub
    if "fire" not in sys.modules:
        sys.modules["fire"] = types.ModuleType("fire")
    if "quantaalpha" not in sys.modules:
        sys.modules["quantaalpha"] = types.ModuleType("quantaalpha")

    for subpkg, subpath in [
        ("quantaalpha.backtest", PKG_ROOT / "backtest"),
        ("quantaalpha.pipeline", PKG_ROOT / "pipeline"),
        ("quantaalpha.factors", PKG_ROOT / "factors"),
        ("quantaalpha.core", PKG_ROOT / "core"),
    ]:
        if subpkg not in sys.modules:
            pkg = types.ModuleType(subpkg)
            pkg.__path__ = [str(subpath)]
            sys.modules[subpkg] = pkg

    for stub_name, stub_val in [
        (
            "quantaalpha.pipeline.settings",
            types.SimpleNamespace(FACTOR_BACK_TEST_PROP_SETTING={}),
        ),
        (
            "quantaalpha.pipeline.loop",
            types.SimpleNamespace(BacktestLoop=type("BacktestLoop", (), {})),
        ),
        (
            "quantaalpha.core.conf",
            types.SimpleNamespace(
                ExtendedBaseSettings=type("ExtendedBaseSettings", (), {}),
                ExtendedSettingsConfigDict=type("ExtendedSettingsConfigDict", (), {}),
            ),
        ),
    ]:
        if stub_name not in sys.modules:
            sys.modules[stub_name] = stub_val


_ensure_stubs()

import importlib.util

spec = importlib.util.spec_from_file_location(
    "quantaalpha.factors.library", PKG_ROOT / "factors" / "library.py"
)
library_mod = importlib.util.module_from_spec(spec)
sys.modules["quantaalpha.factors.library"] = library_mod
spec.loader.exec_module(library_mod)

spec2 = importlib.util.spec_from_file_location(
    "quantaalpha.backtest.runner", PKG_ROOT / "backtest" / "runner.py"
)
runner_mod = importlib.util.module_from_spec(spec2)
sys.modules["quantaalpha.backtest.runner"] = runner_mod
spec2.loader.exec_module(runner_mod)

spec3 = importlib.util.spec_from_file_location(
    "quantaalpha.pipeline.factor_backtest", PKG_ROOT / "pipeline" / "factor_backtest.py"
)
fb_mod = importlib.util.module_from_spec(spec3)
sys.modules["quantaalpha.pipeline.factor_backtest"] = fb_mod
spec3.loader.exec_module(fb_mod)


class TestRunRealBacktest(unittest.TestCase):
    def test_run_real_backtest_no_matching_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            cfg_path = Path(tmp) / "bt.yaml"
            cfg_path.write_text(
                "data:\n  provider_uri: /\n  start_time: '2020-01-01'\n  end_time: '2020-12-31'\n  market: cn\ndataset:\n  label: 'Ref($close, 5)/$close - 1'\n  segments:\n    train: ['2020-01-01', '2020-03-31']\n    test: ['2020-04-01', '2020-06-30']\nbacktest:\n  backtest:\n    start_time: '2020-04-01'\n    end_time: '2020-06-30'\n    account: 100000000\n    benchmark: SH000300\n    exchange_kwargs:\n      freq: day\n      limit_threshold: 0.095\n  strategy:\n    class: TopkDropoutStrategy\n    module_path: qlib.contrib.strategy.signal_strategy\n    kwargs:\n      topk: 50\n      n_drop: 5\nmodel:\n  type: lgb\n  params:\n    loss: mse\n    num_leaves: 31\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json",
                encoding="utf-8",
            )

            result = fb_mod.run_real_backtest(
                str(cfg_path),
                str(lib_path),
                status_filter="active",
            )
            self.assertEqual(result.get("error"), "no_matching_factors")
            self.assertEqual(result.get("factors_checked"), [])

    def test_run_real_backtest_factor_id_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            factors = {
                "f001": {
                    "factor_id": "f001",
                    "factor_name": "FactorOne",
                    "factor_expression": "$close/$open - 1",
                    "evaluation": {"status": "active"},
                },
                "f002": {
                    "factor_id": "f002",
                    "factor_name": "FactorTwo",
                    "factor_expression": "$volume",
                    "evaluation": {"status": "active"},
                },
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            cfg_path = Path(tmp) / "bt.yaml"
            cfg_path.write_text(
                "data:\n  provider_uri: /\n  start_time: '2020-01-01'\n  end_time: '2020-12-31'\n  market: cn\ndataset:\n  label: 'Ref($close, 5)/$close - 1'\n  segments:\n    train: ['2020-01-01', '2020-03-31']\n    test: ['2020-04-01', '2020-06-30']\nbacktest:\n  backtest:\n    start_time: '2020-04-01'\n    end_time: '2020-06-30'\n    account: 100000000\n    benchmark: SH000300\n    exchange_kwargs:\n      freq: day\n      limit_threshold: 0.095\n  strategy:\n    class: TopkDropoutStrategy\n    module_path: qlib.contrib.strategy.signal_strategy\n    kwargs:\n      topk: 50\n      n_drop: 5\nmodel:\n  type: lgb\n  params:\n    loss: mse\n    num_leaves: 31\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json",
                encoding="utf-8",
            )

            runner = runner_mod.BacktestRunner(str(cfg_path))
            with patch.object(runner, "run", return_value={"IC": 0.05}):
                result = runner.run_from_library(str(lib_path), factor_ids=["f001"])
            self.assertIn("f001", result.get("factors_backtested", []))
            self.assertNotIn("f002", result.get("factors_backtested", []))

    def test_run_from_library_loads_correct_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            factors = {
                "aaa1": {
                    "factor_id": "aaa1",
                    "factor_name": "ActiveFactor",
                    "factor_expression": "$close/$open",
                    "evaluation": {"status": "active"},
                },
                "bbb2": {
                    "factor_id": "bbb2",
                    "factor_name": "PendingFactor",
                    "factor_expression": "$volume/$open",
                    "evaluation": {"status": "pending_validation"},
                },
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            cfg_path = Path(tmp) / "bt.yaml"
            cfg_path.write_text(
                "data:\n  provider_uri: /\n  start_time: '2020-01-01'\n  end_time: '2020-12-31'\n  market: cn\ndataset:\n  label: 'Ref($close, 5)/$close - 1'\n  segments:\n    train: ['2020-01-01', '2020-03-31']\n    test: ['2020-04-01', '2020-06-30']\nbacktest:\n  backtest:\n    start_time: '2020-04-01'\n    end_time: '2020-06-30'\n    account: 100000000\n    benchmark: SH000300\n    exchange_kwargs:\n      freq: day\n      limit_threshold: 0.095\n  strategy:\n    class: TopkDropoutStrategy\n    module_path: qlib.contrib.strategy.signal_strategy\n    kwargs:\n      topk: 50\n      n_drop: 5\nmodel:\n  type: lgb\n  params:\n    loss: mse\n    num_leaves: 31\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json",
                encoding="utf-8",
            )

            runner = runner_mod.BacktestRunner(str(cfg_path))
            with patch.object(runner, "run", return_value={"IC": 0.05}):
                result = runner.run_from_library(str(lib_path), status_filter="active")
            self.assertIn("aaa1", result.get("factors_backtested", []))
            self.assertNotIn("bbb2", result.get("factors_backtested", []))

    def test_run_from_library_skips_empty_expression(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            factors = {
                "noexpr": {
                    "factor_id": "noexpr",
                    "factor_name": "NoExpression",
                    "factor_expression": "",
                    "evaluation": {"status": "active"},
                },
                "hasexpr": {
                    "factor_id": "hasexpr",
                    "factor_name": "HasExpression",
                    "factor_expression": "$close",
                    "evaluation": {"status": "active"},
                },
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            cfg_path = Path(tmp) / "bt.yaml"
            cfg_path.write_text(
                "data:\n  provider_uri: /\n  start_time: '2020-01-01'\n  end_time: '2020-12-31'\n  market: cn\ndataset:\n  label: 'Ref($close, 5)/$close - 1'\n  segments:\n    train: ['2020-01-01', '2020-03-31']\n    test: ['2020-04-01', '2020-06-30']\nbacktest:\n  backtest:\n    start_time: '2020-04-01'\n    end_time: '2020-06-30'\n    account: 100000000\n    benchmark: SH000300\n    exchange_kwargs:\n      freq: day\n      limit_threshold: 0.095\n  strategy:\n    class: TopkDropoutStrategy\n    module_path: qlib.contrib.strategy.signal_strategy\n    kwargs:\n      topk: 50\n      n_drop: 5\nmodel:\n  type: lgb\n  params:\n    loss: mse\n    num_leaves: 31\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json\nexperiment:\n  name: test\n  recorder: test_rec\n  output_dir: ./bt_out\n  output_metrics_file: test_metrics.json",
                encoding="utf-8",
            )

            runner = runner_mod.BacktestRunner(str(cfg_path))
            with patch.object(runner, "run", return_value={"IC": 0.05}):
                result = runner.run_from_library(str(lib_path))
            self.assertIn("hasexpr", result.get("factors_backtested", []))
            self.assertNotIn("noexpr", result.get("factors_backtested", []))


if __name__ == "__main__":
    unittest.main()
