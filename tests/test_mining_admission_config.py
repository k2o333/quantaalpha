from __future__ import annotations

from pathlib import Path

import pytest


def _write_profile(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_load_profile_returns_resolved_fields_and_daily_panel_projection(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    base_standard_frame:
      daily_interface: stk_factor_pro
      adjustment: qfq
    fields:
      - feature_name: "$daily_basic_turnover_rate"
        rationale: "liquidity smoke field"
        admitted_by: "FDR-2026-0025"
        source_kind: daily_panel
        source_interface: daily_basic
        source_field: turnover_rate
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [expression, backtest_standard_frame]
""",
    )

    profile = load_mining_admission_profile(profile_path, "test")

    assert profile.base_standard_frame["daily_interface"] == "stk_factor_pro"
    assert profile.expression_feature_names() == ("$daily_basic_turnover_rate",)
    assert profile.fields[0].source_kind == "daily_panel"
    assert profile.fields[0].base.feature_name == "$daily_basic_turnover_rate"
    assert profile.fields[0].rationale == "liquidity smoke field"
    assert profile.daily_panel_optional_fields()[0].source_interface == "daily_basic"


def test_unknown_source_kind_fails_with_remediation(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$bad"
        source_kind: raw_parquet
        source_interface: daily_basic
        source_field: turnover_rate
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [expression]
""",
    )

    with pytest.raises(ValueError, match="unsupported source_kind.*raw_parquet.*add a registry entry"):
        load_mining_admission_profile(profile_path, "test")


def test_source_kind_must_match_app5_primary_class(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$bad"
        source_kind: event_window
        source_interface: daily_basic
        event_date_column: ann_date
        visibility_column: ann_date
        window_days: 30
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: event_visible_window_no_lookahead
        missing_policy: zero
        allowed_usage: [expression]
""",
    )

    with pytest.raises(ValueError, match="source_kind.*event_window.*primary_class.*daily_panel"):
        load_mining_admission_profile(profile_path, "test")


def test_dimension_asof_expression_usage_is_blocked(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$share_float_asof"
        source_kind: dimension_asof
        source_interface: share_float
        source_field: float_share
        effective_date_column: ann_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: effective_date_asof_no_lookahead
        missing_policy: nan
        allowed_usage: [expression, backtest_standard_frame]
""",
    )

    with pytest.raises(ValueError, match="dimension_asof.*not expression-safe"):
        load_mining_admission_profile(profile_path, "test")


def test_canonical_financial_field_is_checked_against_registry(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    registry_path = tmp_path / "field_registry.yaml"
    registry_path.write_text("[]\n", encoding="utf-8")
    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$inc_n_income_attr_p_asof"
        source_kind: canonical_financial_asof
        canonical_table: financial_report
        source_interface: income_vip
        source_field: inc_n_income_attr_p
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: ann_date_asof_no_lookahead
        missing_policy: nan
        allowed_usage: [expression]
""",
    )

    with pytest.raises(ValueError, match="canonical registry.*financial_report.*inc_n_income_attr_p"):
        load_mining_admission_profile(profile_path, "test", registry_path=registry_path)


def test_standard_frame_request_from_mapping_accepts_admitted_field_dicts() -> None:
    from quantaalpha.backtest.standard_frame import request_from_mapping

    request = request_from_mapping(
        {
            "admitted_fields": [
                {
                    "base": {
                        "source_interface": "daily_basic",
                        "source_field": "turnover_rate",
                        "feature_name": "$daily_basic_turnover_rate",
                        "dtype": "float64",
                        "join_key": ["datetime", "instrument"],
                        "time_policy": "same_trade_date_no_lookahead",
                        "missing_policy": "nan",
                        "allowed_usage": ["expression", "backtest_standard_frame"],
                    },
                    "source_kind": "daily_panel",
                    "payload": {"source_interface": "daily_basic", "source_field": "turnover_rate"},
                }
            ]
        }
    )

    assert request.admitted_fields[0].feature_name == "$daily_basic_turnover_rate"


def test_validate_admission_profile_reports_routes_and_prompt_visibility(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import validate_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$daily_basic_turnover_rate"
        source_kind: daily_panel
        source_interface: daily_basic
        source_field: turnover_rate
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [expression, backtest_standard_frame]
      - feature_name: "$share_float_asof"
        source_kind: dimension_asof
        source_interface: share_float
        source_field: float_share
        effective_date_column: ann_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: effective_date_asof_no_lookahead
        missing_policy: nan
        allowed_usage: [context, backtest_standard_frame]
""",
    )

    report = validate_admission_profile(profile_path, "test")

    assert report["profile_name"] == "test"
    assert report["accepted_fields"] == ["$daily_basic_turnover_rate", "$share_float_asof"]
    assert report["prompt_groups"]["daily_panel_features"] == ["$daily_basic_turnover_rate"]
    assert report["routes"]["$daily_basic_turnover_rate"]["materializer"] == "_join_daily_panel_batch"
    assert report["routes"]["$share_float_asof"]["prompt_visible"] is False
