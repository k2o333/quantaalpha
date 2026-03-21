from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"


def _ensure_stub_modules() -> None:
    if "pandas" not in sys.modules:
        pandas_stub = types.ModuleType("pandas")
        pandas_stub.Series = type("Series", (), {})
        pandas_stub.DataFrame = type("DataFrame", (), {})
        pandas_stub.read_hdf = lambda *args, **kwargs: None
        sys.modules["pandas"] = pandas_stub
    if "tiktoken" not in sys.modules:
        tiktoken_stub = types.ModuleType("tiktoken")
        tiktoken_stub.encoding_for_model = lambda model: object()
        sys.modules["tiktoken"] = tiktoken_stub
    if "fire" not in sys.modules:
        fire_stub = types.ModuleType("fire")
        fire_stub.Fire = lambda *args, **kwargs: None
        sys.modules["fire"] = fire_stub
    if "quantaalpha" not in sys.modules:
        pkg = types.ModuleType("quantaalpha")
        pkg.__path__ = [str(PKG_ROOT)]
        sys.modules["quantaalpha"] = pkg
    for name, rel in {
        "quantaalpha.backtest": "backtest",
        "quantaalpha.factors": "factors",
        "quantaalpha.llm": "llm",
        "quantaalpha.pipeline": "pipeline",
        "quantaalpha.pipeline.evolution": "pipeline/evolution",
        "quantaalpha.app": "app",
        "quantaalpha.app.utils": "app/utils",
    }.items():
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = [str(PKG_ROOT / rel)]
            sys.modules[name] = pkg
    for name in [
        "quantaalpha.pipeline.factor_mining",
        "quantaalpha.pipeline.factor_backtest",
        "quantaalpha.app.utils.health_check",
        "quantaalpha.app.utils.info",
    ]:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.main = lambda *args, **kwargs: None
            mod.health_check = lambda *args, **kwargs: None
            mod.collect_info = lambda *args, **kwargs: None
            sys.modules[name] = mod
    if "quantaalpha.core" not in sys.modules:
        core_pkg = types.ModuleType("quantaalpha.core")
        core_pkg.__path__ = [str(PKG_ROOT / "core")]
        sys.modules["quantaalpha.core"] = core_pkg
    if "quantaalpha.core.utils" not in sys.modules:
        utils_mod = types.ModuleType("quantaalpha.core.utils")
        utils_mod.LLM_CACHE_SEED_GEN = types.SimpleNamespace(get_next_seed=lambda: 42)
        utils_mod.SingletonBaseClass = object
        sys.modules["quantaalpha.core.utils"] = utils_mod
    if "quantaalpha.log" not in sys.modules:
        logger_stub = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None)
        log_mod = types.ModuleType("quantaalpha.log")
        log_mod.LogColors = types.SimpleNamespace(MAGENTA="", BOLD="", END="", CYAN="")
        log_mod.logger = logger_stub
        sys.modules["quantaalpha.log"] = log_mod
    if "quantaalpha.llm.config" not in sys.modules:
        llm_config_mod = types.ModuleType("quantaalpha.llm.config")
        llm_config_mod.LLM_SETTINGS = types.SimpleNamespace(
            chat_model="fallback",
            reasoning_model="",
            routing_default="",
            routing_tasks="{}",
            chat_model_map="{}",
            dump_chat_cache=False,
            use_chat_cache=False,
            dump_embedding_cache=False,
            use_embedding_cache=False,
            prompt_cache_path=":memory:",
            use_azure=False,
            use_gcr_endpoint=False,
            use_llama2=False,
            openai_api_key="",
            chat_openai_api_key="",
            embedding_openai_api_key="",
            openai_base_url="",
            embedding_base_url="",
            embedding_api_key="",
            chat_azure_api_base="",
            chat_azure_api_version="",
            embedding_azure_api_base="",
            embedding_azure_api_version="",
            chat_stream=False,
            chat_seed=None,
            chat_temperature=0.5,
            chat_max_tokens=1000,
            chat_frequency_penalty=0.0,
            chat_presence_penalty=0.0,
            max_retry=1,
            retry_wait_seconds=0,
            log_llm_chat_content=False,
            default_system_prompt="system",
            max_past_message_include=3,
            use_auto_chat_cache_seed_gen=False,
            embedding_model="",
            embedding_max_str_num=3,
            embedding_batch_wait_seconds=0.0,
        )
        sys.modules["quantaalpha.llm.config"] = llm_config_mod


def _load_module(name: str, path: Path):
    _ensure_stub_modules()
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


universe = _load_module("quantaalpha.backtest.universe", PKG_ROOT / "backtest" / "universe.py")
validation = _load_module("quantaalpha.backtest.validation", PKG_ROOT / "backtest" / "validation.py")
status_rules = _load_module("quantaalpha.factors.status_rules", PKG_ROOT / "factors" / "status_rules.py")
data_capability = _load_module("quantaalpha.factors.data_capability", PKG_ROOT / "factors" / "data_capability.py")
library = _load_module("quantaalpha.factors.library", PKG_ROOT / "factors" / "library.py")
trajectory = _load_module("quantaalpha.pipeline.evolution.trajectory", PKG_ROOT / "pipeline" / "evolution" / "trajectory.py")
llm_client = _load_module("quantaalpha.llm.client", PKG_ROOT / "llm" / "client.py")
cli = _load_module("quantaalpha.cli", PKG_ROOT / "cli.py")


class ContinuousFactorFeatureTests(unittest.TestCase):
    def test_stock_universe_filter_helpers(self):
        instruments = ["000001.SZ", "430001.BJ", "600001.SH"]
        self.assertEqual(universe.filter_by_market(instruments, ["bj"]), ["000001.SZ", "600001.SH"])
        filtered, warnings = universe.filter_stocks(
            ["000001.SZ", "600001.SH"],
            {
                "000001.SZ": {"name": "*ST Test", "list_date": "2026-01-01"},
                "600001.SH": {"name": "Normal", "list_date": "2020-01-01"},
            },
            exclude_st=True,
            min_list_days=60,
            as_of_date="2026-03-14",
        )
        self.assertEqual(filtered, ["600001.SH"])
        self.assertEqual(warnings, [])
        self.assertEqual(universe.normalize_stock_filter_config({"exclude_markets": ["BJ"]})["exclude_markets"], ["bj"])

    def test_multi_period_validation_helpers(self):
        config = validation.validate_multi_period_config(
            {
                "enabled": True,
                "periods": [
                    {"name": "recent", "train": ["2022-01-01", "2022-12-31"], "valid": ["2023-01-01", "2023-06-30"], "test": ["2023-07-01", "2023-12-31"]},
                    {"name": "hist", "train": ["2020-01-01", "2020-12-31"], "valid": ["2021-01-01", "2021-06-30"], "test": ["2021-07-01", "2021-12-31"]},
                ],
            }
        )
        built = validation.build_period_configs({"dataset": {"segments": {}}, "backtest": {"backtest": {}}}, config)
        self.assertEqual(built[0]["dataset"]["segments"]["test"], ["2023-07-01", "2023-12-31"])
        summary = validation.aggregate_period_metrics(
            [
                {"name": "a", "status": "success", "metrics": {"IC": 0.1, "Rank IC": 0.08, "annualized_return": 0.12, "information_ratio": 0.5, "max_drawdown": -0.1}},
                {"name": "b", "status": "success", "metrics": {"IC": 0.06, "Rank IC": 0.04, "annualized_return": 0.09, "information_ratio": 0.3, "max_drawdown": -0.15}},
            ]
        )
        self.assertEqual(summary["period_count"], 2)
        self.assertIsNotNone(summary["stability_score"])

    def test_factor_library_normalization_and_revalidation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            library_path = Path(tmp_dir) / "factorlib.json"
            library_path.write_text(json.dumps({"metadata": {"version": "1.0"}, "factors": {"f1": {"factor_id": "f1", "factor_name": "factor_one", "factor_expression": "$close/$open"}}}), encoding="utf-8")
            manager = library.FactorLibraryManager(str(library_path))
            factor = manager.data["factors"]["f1"]
            self.assertEqual(factor["evaluation"]["status"], "pending_validation")
            updated = manager.apply_validation_result(
                factor,
                {"status": "success", "period_results": [], "summary": {"stability_score": 0.8, "validation_summary": "ok"}},
                now=datetime(2026, 3, 14),
                persist=False,
            )
            self.assertEqual(updated["evaluation"]["status"], "active")
            manager.data["factors"]["f1"] = updated
            manager._save()
            result = cli.revalidate(str(library_path), status="active", no_write=True)
            self.assertEqual(result["success"], 1)

    def test_status_rules(self):
        entry = {
            "factor_id": "f2",
            "evaluation": {
                "status": "active",
                "last_validated": "2026-01-01T00:00:00",
                "stability_score": 0.7,
                "period_results": [],
                "validation_summary": "",
                "consecutive_failures": 0,
            },
        }
        # Stale check: 30 days threshold
        stale = status_rules.update_factor_status(entry, None, now=datetime(2026, 3, 14))
        self.assertEqual(stale["evaluation"]["status"], "stale")
        
        # Degraded check: stability score 0.34 (below solidified 0.35 threshold)
        degraded = status_rules.update_factor_status(
            entry,
            {"status": "success", "summary": {"stability_score": 0.34}, "period_results": []},
            now=datetime(2026, 3, 14),
        )
        self.assertEqual(degraded["evaluation"]["status"], "degraded")
        
        # Active check: stability score 0.56 (above solidified 0.55 threshold)
        active = status_rules.update_factor_status(
            entry,
            {"status": "success", "summary": {"stability_score": 0.56}, "period_results": []},
            now=datetime(2026, 3, 14),
        )
        self.assertEqual(active["evaluation"]["status"], "active")

    def test_data_capability_and_llm_routing_helpers(self):
        rendered = data_capability.render_data_capabilities()
        self.assertIn("price_volume", rendered)
        self.assertIn("lag_days", rendered)
        self.assertEqual(llm_client.parse_routing_tasks('{"hypothesis_generation":"model-a"}'), {"hypothesis_generation": "model-a"})
        backend = object.__new__(llm_client.APIBackend)
        backend.task_model_map = {"hypothesis_generation": "model-a"}
        backend.routing_default = "model-default"
        backend.chat_model_map = {"SomeTag": "legacy-model"}
        backend.chat_model = "fallback"
        self.assertEqual(backend.get_model_for_task("hypothesis_generation", "SomeTag"), "model-a")
        self.assertEqual(backend.get_model_for_task(None, "SomeTag"), "legacy-model")

    def test_evolution_selection_helpers(self):
        active = trajectory.StrategyTrajectory(
            trajectory_id="t1",
            direction_id=0,
            round_idx=0,
            phase=trajectory.RoundPhase.ORIGINAL,
            backtest_metrics={"RankIC": 0.05},
            extra_info={"evaluation": {"status": "active", "stability_score": 0.8}},
        )
        degraded = trajectory.StrategyTrajectory(
            trajectory_id="t2",
            direction_id=1,
            round_idx=0,
            phase=trajectory.RoundPhase.ORIGINAL,
            backtest_metrics={"RankIC": 0.08},
            extra_info={"evaluation": {"status": "degraded", "stability_score": 0.2}},
        )
        selected = trajectory.select_parent_factors([degraded, active], n=1)
        self.assertEqual(selected, [active])
        self.assertEqual(trajectory.route_factor_by_status(active), "evolution_pool")
        self.assertEqual(trajectory.route_factor_by_status(degraded), "repair_or_hold")


if __name__ == "__main__":
    unittest.main()
