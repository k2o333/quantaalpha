# ruff: noqa: D103

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest


def test_llm_runtime_config_accepts_nested_embedding_block() -> None:
    from quantaalpha.continuous.scheduler import PipelineConfig

    cfg = PipelineConfig.from_yaml_dict(
        {
            "llm": {
                "embedding": {
                    "version": 1,
                    "remote_enabled": False,
                    "use_cache": True,
                    "dump_cache": True,
                    "fatal_on_failure": False,
                    "max_attempts": 1,
                    "model": "codestral-embed",
                    "base_url": "http://embed.example/v1",
                    "fallback": ["local_jaccard", "none"],
                }
            }
        }
    )

    assert cfg.llm.embedding.remote_enabled is False
    assert cfg.llm.embedding.use_cache is True
    assert cfg.llm.embedding.dump_cache is True
    assert cfg.llm.embedding.fatal_on_failure is False
    assert cfg.llm.embedding.max_attempts == 1
    assert cfg.llm.embedding.model == "codestral-embed"
    assert cfg.llm.embedding.base_url == "http://embed.example/v1"
    assert cfg.llm.embedding_model == "codestral-embed"
    assert cfg.llm.embedding_base_url == "http://embed.example/v1"

    round_trip = PipelineConfig.from_yaml_dict(cfg.to_dict())
    assert round_trip.llm.embedding.model == "codestral-embed"
    assert round_trip.llm.embedding.fatal_on_failure is False


def test_apply_pipeline_llm_config_sets_embedding_runtime_semantics(monkeypatch) -> None:
    from quantaalpha.continuous.scheduler import LLMRuntimeConfig
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    cfg = LLMRuntimeConfig.from_dict(
        {
            "embedding": {
                "remote_enabled": False,
                "use_cache": True,
                "dump_cache": True,
                "fatal_on_failure": False,
                "max_attempts": 2,
                "fallback": ["local_jaccard"],
            }
        }
    )
    monkeypatch.setattr(LLM_SETTINGS, "embedding_remote_enabled", True)
    monkeypatch.setattr(LLM_SETTINGS, "embedding_max_attempts", 9)

    apply_pipeline_llm_config(cfg)

    assert LLM_SETTINGS.embedding_remote_enabled is False
    assert LLM_SETTINGS.use_embedding_cache is True
    assert LLM_SETTINGS.dump_embedding_cache is True
    assert LLM_SETTINGS.embedding_fatal_on_failure is False
    assert LLM_SETTINGS.embedding_max_attempts == 2
    assert LLM_SETTINGS.embedding_fallback == ["local_jaccard"]


def test_llm_runtime_config_preserves_flat_embedding_fields() -> None:
    from quantaalpha.continuous.scheduler import PipelineConfig

    cfg = PipelineConfig.from_yaml_dict(
        {
            "llm": {
                "embedding_model": "legacy-embed",
                "embedding_base_url": "http://legacy.example/v1",
            }
        }
    )

    assert cfg.llm.embedding_model == "legacy-embed"
    assert cfg.llm.embedding_base_url == "http://legacy.example/v1"
    assert cfg.llm.embedding.model == "legacy-embed"
    assert cfg.llm.embedding.base_url == "http://legacy.example/v1"


def test_tool_choice_thinking_mode_error_is_tool_call_capability_failure() -> None:
    from quantaalpha.llm.client_shared import _is_tool_call_capability_failure

    error = Exception(
        "InternalError.Algo.InvalidParameter: The tool_choice parameter does not support "
        "being set to required or object in thinking mode"
    )

    assert _is_tool_call_capability_failure(error) is True


def test_call_structured_strips_forced_tool_choice_for_deepseek_v4_flash(monkeypatch) -> None:
    from quantaalpha.llm.client_shared import call_structured
    from quantaalpha.llm.config import LLM_SETTINGS

    captured: dict[str, object] = {}

    class FakeBackend:
        chat_model = "deepseek-v4-flash"
        reasoning_model = ""
        chat_stream = False
        _max_retry_override = 1

    backend = FakeBackend()

    def fake_raw_call(**kwargs):
        captured.update(kwargs)
        return '{"ok": true}'

    backend.__dict__["_try_create_chat_completion_or_embedding"] = fake_raw_call
    monkeypatch.setattr(LLM_SETTINGS, "use_tool_calling", True, raising=False)
    monkeypatch.setattr(LLM_SETTINGS, "structured_streaming_mode", False, raising=False)

    result = call_structured(
        backend,
        [{"role": "user", "content": "return json"}],
        tools=[{"type": "function", "function": {"name": "emit", "parameters": {"type": "object"}}}],
        tool_choice="required",
    )

    assert result == {"ok": True}
    assert captured["tools"]
    assert captured["tool_choice"] is None


def test_noqlib_standard_frame_rejects_legacy_coder_runtime() -> None:
    from quantaalpha.pipeline.loop import validate_factor_coder_runtime_contract

    with pytest.raises(RuntimeError, match="polars_parquet"):
        validate_factor_coder_runtime_contract(
            backtest_backend="noqlib",
            backtest_noqlib_config={"standard_frame": {"data_root": "data/app5"}},
        )


def test_noqlib_standard_frame_allows_direct_polars_coder_runtime() -> None:
    from quantaalpha.pipeline.loop import validate_factor_coder_runtime_contract

    runtime = validate_factor_coder_runtime_contract(
        backtest_backend="noqlib",
        backtest_noqlib_config={
            "enabled": True,
            "factor_coder_runtime": "polars_parquet",
            "standard_frame": {"data_root": "data/app5"},
        },
    )

    assert runtime == "polars_parquet"


def test_embedding_failure_degrades_when_non_fatal(monkeypatch) -> None:
    from quantaalpha.llm.client import APIBackend
    from quantaalpha.llm.config import LLM_SETTINGS

    backend = object.__new__(APIBackend)
    backend.embedding_model = "codestral-embed"
    backend.embedding_base_url = "http://embed.example/v1"
    backend._max_retry_override = 1
    backend.retry_wait_seconds = 0
    monkeypatch.setattr(LLM_SETTINGS, "embedding_remote_enabled", True, raising=False)
    monkeypatch.setattr(LLM_SETTINGS, "embedding_fatal_on_failure", False, raising=False)
    monkeypatch.setattr(LLM_SETTINGS, "max_retry", 1)
    monkeypatch.setattr(LLM_SETTINGS, "retry_wait_seconds", 0)

    def fail_once(*_args, **_kwargs):
        raise RuntimeError("429 RateLimitError")

    monkeypatch.setattr(backend, "_create_chat_completion_or_embedding_once", fail_once)

    result = backend._try_create_chat_completion_or_embedding(
        embedding=True,
        input_content_list=["alpha"],
        max_retry=1,
    )

    assert result == [None]
    assert backend.embedding_degraded is True
    assert "429" in backend.embedding_degraded_reason


def test_open_circuit_breaker_skips_mining_before_workspace_allocation(monkeypatch) -> None:
    from quantaalpha.continuous.circuit_breaker import ContinuousCircuitBreaker
    from quantaalpha.continuous.implementations import DefaultMiningScheduler

    scheduler = DefaultMiningScheduler(pipeline_mode=True)
    scheduler.set_circuit_breaker(
        ContinuousCircuitBreaker.open_until(
            datetime.now() + timedelta(minutes=10),
            reason="zero_pass_cooldown",
        )
    )

    called = {"pipeline": 0}

    def fail_if_called(*_args, **_kwargs):
        called["pipeline"] += 1
        raise AssertionError("pipeline mining should be skipped during cooldown")

    monkeypatch.setattr(scheduler, "_run_pipeline_mining", fail_if_called)

    result = scheduler.run_mining()

    assert called["pipeline"] == 0
    assert result.factors_generated == 0
    assert result.errors == []
    assert result.governance_events[0]["reason"] == "zero_pass_cooldown"


def test_quality_overlay_emits_fine_grained_reason_codes() -> None:
    from quantaalpha.factors.failure_tracker import QualityFailureReason
    from quantaalpha.pipeline.quality_overlay import infer_failure_attribution

    event = infer_failure_attribution(
        metrics={"rank_ic_test": 0.05},
        diagnostics={"lookahead_risk": "critical"},
    )

    assert event["primary_failure_reason"] == "lookahead_risk"
    assert event["primary_quality_failure_reason"] == QualityFailureReason.LOOKAHEAD_DETECTED.value
    assert event["quality_failure_reasons"] == [QualityFailureReason.LOOKAHEAD_DETECTED.value]
    assert event["reason_code"] == QualityFailureReason.LOOKAHEAD_DETECTED.value
    assert event["reason_group"] == "data_leakage"
    assert event["reason_severity"] == "high"


def test_validate_training_evidence_reads_production_source(tmp_path) -> None:
    import polars as pl

    from quantaalpha.factor_ops.commands import FactorOpsCommands

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from training.diagnostics.production_evidence import (
        ProductionEvidenceWriteRequest,
        write_production_evidence,
    )

    diagnostics = pl.DataFrame(
        {
            "factor_name": ["alpha"],
            "coverage": [0.99],
            "missing_rate": [0.01],
            "zero_rate": [0.0],
            "mean_rank_ic": [0.03],
            "rank_ic_ir": [0.8],
            "rank_ic_tstat": [2.1],
            "ic_stability": [0.7],
            "positive_ic_ratio": [0.65],
            "turnover": [0.4],
            "exposure_r2_before_neutral": [0.2],
            "exposure_r2_after_neutral": [0.05],
            "max_corr_to_selected": [0.3],
            "selected_frequency": [0.8],
            "final_selected": [True],
        }
    )
    write_result = write_production_evidence(
        diagnostics_frame=diagnostics,
        request=ProductionEvidenceWriteRequest(
            root=tmp_path,
            evidence_date="2026-05-28",
            run_id="uat",
            schema_version="v1",
            factor_name_to_id={"alpha": "factor_001"},
        ),
    )
    assert write_result.path is not None

    result = FactorOpsCommands().validate_training_evidence(str(write_result.path))

    assert result["status"] == "ok"
    assert result["evidence_source"] == "production"
    assert result["rows"] == 1
