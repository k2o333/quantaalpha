from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_short_uat_profile_bounds_cycle_limits() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
        mining=SimpleNamespace(
            evolution=SimpleNamespace(max_rounds=3),
            orchestration=SimpleNamespace(
                max_steps_per_cycle=6,
                nodes=[
                    SimpleNamespace(params={}),
                    SimpleNamespace(params={"max_tasks_per_run": 3}),
                ],
            ),
        ),
    )
    _apply_uat_profile(config, "short")
    assert config.cycle_budget_seconds == 900
    assert config.validation.max_revalidation_per_run == 1
    assert config.validation.max_mining_per_run == 1
    assert config.mining.evolution.max_rounds == 1
    assert config.mining.orchestration.max_steps_per_cycle == 1
    assert config.mining.orchestration.nodes[1].params["max_tasks_per_run"] == 1


def test_unknown_uat_profile_fails_fast() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
    )
    with pytest.raises(ValueError, match="unsupported continuous UAT profile"):
        _apply_uat_profile(config, "nightly")


def test_expanded_data_uat_profile_adds_admitted_optional_fields() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
        mining=SimpleNamespace(
            evolution=SimpleNamespace(max_rounds=3),
            orchestration=SimpleNamespace(max_steps_per_cycle=6, nodes=[]),
            agent_loop=SimpleNamespace(step_model_routing={"construct": "litellm_minimax"}),
            ensemble=SimpleNamespace(),
        ),
        factor=SimpleNamespace(backtest_noqlib={"standard_frame": {"daily_interface": "daily", "adjustment": "raw"}}),
    )

    _apply_uat_profile(config, "expanded-data")

    assert config.factor.backtest_noqlib["market_data_source"] == "app5_standard_frame"
    standard_frame = config.factor.backtest_noqlib["standard_frame"]
    assert config.cycle_budget_seconds == 900
    assert config.validation.max_revalidation_per_run == 0
    assert standard_frame["admission_profile"] == "expanded-data"
    assert config.factor.backtest_noqlib["factor_coder_runtime"] == "dual_h5_parquet"
    assert len(standard_frame["optional_fields"]) >= 3
    assert "$daily_basic_turnover_rate" in {item["feature_name"] for item in standard_frame["optional_fields"]}
    assert config.mining.agent_loop.step_model_routing["construct"] == "litellm_mistral"
    assert config.mining.ensemble.models[0].name == "litellm_mistral"


def test_expanded_data_uat_profile_loads_yaml_admission_when_configured(tmp_path) -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    profile_path.write_text(
        """
version: 1
profiles:
  mini:
    fields:
      - feature_name: "$daily_basic_pe"
        source_kind: daily_panel
        source_interface: daily_basic
        source_field: pe
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [expression, backtest_standard_frame]
""",
        encoding="utf-8",
    )
    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
        mining=SimpleNamespace(
            evolution=SimpleNamespace(max_rounds=3),
            orchestration=SimpleNamespace(max_steps_per_cycle=6, nodes=[]),
            agent_loop=SimpleNamespace(step_model_routing={}),
            ensemble=SimpleNamespace(),
        ),
        factor=SimpleNamespace(
            backtest_noqlib={
                "standard_frame": {
                    "daily_interface": "daily",
                    "admission_profile_path": str(profile_path),
                    "admission_profile": "mini",
                }
            }
        ),
    )

    _apply_uat_profile(config, "expanded-data")

    standard_frame = config.factor.backtest_noqlib["standard_frame"]
    assert "optional_fields" not in standard_frame
    assert [item["base"]["feature_name"] for item in standard_frame["admitted_fields"]] == ["$daily_basic_pe"]
    assert standard_frame["admission_profile"] == "mini"


def test_validate_admission_cli_prints_profile_report(tmp_path, monkeypatch, capsys) -> None:
    from quantaalpha.continuous import main as continuous_main

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    profile_path.write_text(
        """
version: 1
profiles:
  mini:
    fields:
      - feature_name: "$daily_basic_pe"
        source_kind: daily_panel
        source_interface: daily_basic
        source_field: pe
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [expression, backtest_standard_frame]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "python -m quantaalpha.continuous.main",
            "validate-admission",
            "--profile",
            str(profile_path),
            "--profile-name",
            "mini",
        ],
    )

    continuous_main.main()

    out = capsys.readouterr().out
    assert '"profile_name": "mini"' in out
    assert "$daily_basic_pe" in out


def test_mining_scheduler_uses_explicit_cycle_budget() -> None:
    from quantaalpha.continuous.mining_scheduler import DefaultMiningScheduler

    captured: dict[str, int | None] = {}
    scheduler = object.__new__(DefaultMiningScheduler)
    scheduler._pipeline_mode = True
    scheduler._state_cfg = {"cycle_budget_seconds": 999}
    scheduler._update_next_run = lambda: None

    def fake_pipeline_mining(*, budget_seconds: int | None = None) -> dict:
        captured["budget_seconds"] = budget_seconds
        return {
            "factors_generated": 0,
            "factors_validated": 0,
            "factors_added": 0,
            "factor_ids": [],
            "errors": [],
        }

    scheduler._run_pipeline_mining = fake_pipeline_mining

    result = scheduler.run_mining(budget_seconds=7)

    assert captured["budget_seconds"] == 7
    assert result.errors == []
