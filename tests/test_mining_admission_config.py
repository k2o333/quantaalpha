from __future__ import annotations

from pathlib import Path
import builtins

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
      adjustment: hfq
    fields:
      - feature_name: "$daily_basic_turnover_rate"
        rationale: "liquidity smoke field"
        admitted_by: "FDR-2026-0025"
        semantic_type: ratio
        unit: percent
        scale: 1
        source_methodology: tushare_daily_basic
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
    assert profile.fields[0].semantic_type == "ratio"
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
        semantic_type: ratio
        unit: percent
        scale: 1
        source_methodology: invalid_source_kind_test
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
        semantic_type: count
        unit: records
        scale: 1
        source_methodology: invalid_source_kind_class_test
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
        semantic_type: shares
        unit: shares
        scale: 1
        source_methodology: tushare_share_float
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


def test_expression_field_requires_semantic_metadata(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

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
""",
    )

    with pytest.raises(ValueError, match="expression field.*missing semantic metadata.*semantic_type.*unit.*scale.*source_methodology"):
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
        semantic_type: amount
        unit: CNY
        scale: 1
        source_methodology: canonical_financial_report
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


def test_canonical_registry_import_failure_has_actionable_message(tmp_path: Path, monkeypatch) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$inc_total_revenue_asof"
        semantic_type: amount
        unit: CNY
        scale: 1
        source_methodology: canonical_financial_report
        source_kind: canonical_financial_asof
        canonical_table: financial_report
        source_interface: income_vip
        source_field: inc_total_revenue
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: ann_date_asof_no_lookahead
        missing_policy: nan
        allowed_usage: [expression]
""",
    )
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "app5.canonical.registry":
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(ValueError, match="app5 canonical registry is required.*PYTHONPATH"):
        load_mining_admission_profile(profile_path, "test")


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
        semantic_type: ratio
        unit: percent
        scale: 1
        source_methodology: tushare_daily_basic
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
    assert report["routes"]["$daily_basic_turnover_rate"]["semantic_type"] == "ratio"
    assert report["routes"]["$share_float_asof"]["prompt_visible"] is False
    assert report["coverage"]["accepted_field_count"] == 2
    assert report["coverage"]["prompt_visible_field_count"] == 1
    assert report["coverage"]["usage_counts"]["context"] == 1
    assert report["coverage"]["source_kind_counts"] == {"daily_panel": 1, "dimension_asof": 1}
    assert "daily_basic" in report["coverage"]["admitted_interfaces"]
    assert "stock_basic" in report["coverage"]["unadmitted_interfaces"]


def test_non_expression_runtime_source_kinds_validate_and_report_routes(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import validate_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$is_suspended_external"
        source_kind: tradability_mask
        source_interface: suspend_d
        source_field: suspend_type
        date_column: trade_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: tradability_state_no_lookahead
        missing_policy: zero
        allowed_usage: [tradability, context, backtest_standard_frame]
      - feature_name: "$benchmark_hs300_return"
        source_kind: benchmark_daily_context
        source_interface: index_daily
        source_field: pct_chg
        date_column: trade_date
        index_code: 000300.SH
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: benchmark_same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [benchmark, context, backtest_standard_frame]
      - feature_name: "$mkt_moneyflow_net_amount"
        source_kind: market_context_daily
        source_interface: moneyflow_mkt_dc
        source_field: net_amount
        date_column: trade_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_broadcast_no_lookahead
        missing_policy: nan
        allowed_usage: [context, backtest_standard_frame]
""",
    )

    report = validate_admission_profile(profile_path, "test")

    assert report["coverage"]["source_kind_counts"] == {
        "benchmark_daily_context": 1,
        "market_context_daily": 1,
        "tradability_mask": 1,
    }
    assert report["coverage"]["usage_counts"]["benchmark"] == 1
    assert report["coverage"]["usage_counts"]["tradability"] == 1
    assert report["coverage"]["prompt_visible_field_count"] == 0
    assert report["routes"]["$is_suspended_external"]["materializer"] == "_join_tradability_mask_batch"
    assert report["routes"]["$benchmark_hs300_return"]["materializer"] == "_join_benchmark_daily_context_batch"
    assert report["routes"]["$mkt_moneyflow_net_amount"]["materializer"] == "_join_market_context_daily_batch"


def test_non_expression_source_kinds_reject_expression_usage(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    fields:
      - feature_name: "$is_suspended_external"
        semantic_type: tradability_flag
        unit: bool
        scale: 1
        source_methodology: tushare_suspend_d
        source_kind: tradability_mask
        source_interface: suspend_d
        source_field: suspend_type
        date_column: trade_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: tradability_state_no_lookahead
        missing_policy: zero
        allowed_usage: [expression, backtest_standard_frame]
""",
    )

    with pytest.raises(ValueError, match="tradability_mask.*not expression-safe"):
        load_mining_admission_profile(profile_path, "test")


def test_validate_admission_profile_accounts_for_blocked_interfaces(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import validate_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    blocked_interfaces:
      stock_basic: "dimension context is handled in a separate profile"
    fields:
      - feature_name: "$daily_basic_turnover_rate"
        semantic_type: ratio
        unit: percent
        scale: 1
        source_methodology: tushare_daily_basic
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

    report = validate_admission_profile(profile_path, "test")

    assert report["coverage"]["blocked_interfaces"] == {
        "stock_basic": "dimension context is handled in a separate profile"
    }
    assert "stock_basic" in report["coverage"]["unadmitted_interfaces"]
    assert "stock_basic" not in report["coverage"]["unaccounted_interfaces"]


def test_blocked_interfaces_must_be_classified(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    _write_profile(
        profile_path,
        """
version: 1
profiles:
  test:
    blocked_interfaces:
      not_an_interface: "bad"
    fields: []
""",
    )

    with pytest.raises(ValueError, match="blocked interface is not classified.*not_an_interface"):
        load_mining_admission_profile(profile_path, "test")


def test_production_expanded_profile_exposes_audited_expression_interfaces() -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile = load_mining_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )

    expression_fields = [field for field in profile.fields if "expression" in field.allowed_usage]
    expression_interfaces = {field.source_interface for field in expression_fields}

    assert len(expression_interfaces) == 27
    assert "cyq_chips" not in expression_interfaces
    assert "cyq_chips_scalar" in expression_interfaces
    assert "stock_basic" not in expression_interfaces
    assert "trade_cal" not in expression_interfaces
    assert "index_weight" not in expression_interfaces
    assert "index_daily" not in expression_interfaces
    assert "suspend_d" not in expression_interfaces
    assert "stock_st" not in expression_interfaces
    assert "moneyflow_mkt_dc" not in expression_interfaces
    assert "daily" not in expression_interfaces
    assert "pledge_stat" not in expression_interfaces
    assert "disclosure_date" not in expression_interfaces


def test_production_expanded_profile_unblocks_company_and_hsgt_as_non_expression_context() -> None:
    from quantaalpha.backtest.mining_admission import validate_admission_profile

    report = validate_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )

    blocked = report["coverage"]["blocked_interfaces"]
    routes = report["routes"]

    assert "stock_company" not in blocked
    assert "stock_hsgt" not in blocked
    assert "stock_company" in report["coverage"]["admitted_interfaces"]
    assert "stock_hsgt" in report["coverage"]["admitted_interfaces"]
    assert blocked == {}
    assert routes["$stock_company_reg_capital_asof"]["prompt_visible"] is False
    assert routes["$stock_company_employees_asof"]["prompt_visible"] is False
    assert routes["$is_hsgt_external"]["prompt_visible"] is False
    assert routes["$stock_company_reg_capital_asof"]["materializer"] == "_join_dimension_asof_batch"
    assert routes["$is_hsgt_external"]["materializer"] == "_join_tradability_mask_batch"


def test_production_expanded_profile_unblocks_remaining_interfaces_as_context_only() -> None:
    from quantaalpha.backtest.mining_admission import validate_admission_profile

    report = validate_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )
    routes = report["routes"]

    assert report["coverage"]["blocked_interfaces"] == {}
    for interface in (
        "broker_recommend",
        "fina_mainbz_vip",
        "index_weight",
        "moneyflow_cnt_ths",
        "moneyflow_ind_dc",
        "moneyflow_ind_ths",
        "trade_cal",
    ):
        assert interface in report["coverage"]["admitted_interfaces"]
    assert routes["$trade_cal_is_open"]["materializer"] == "_join_tradability_mask_batch"
    assert routes["$benchmark_hs300_weight_sum"]["materializer"] == "_join_benchmark_weight_context_batch"
    assert routes["$moneyflow_ind_dc_net_amount_sum"]["materializer"] == "_join_daily_panel_aggregate_context_batch"
    assert routes["$moneyflow_ind_ths_net_amount_sum"]["materializer"] == "_join_daily_panel_aggregate_context_batch"
    assert routes["$moneyflow_cnt_ths_net_amount_sum"]["materializer"] == "_join_daily_panel_aggregate_context_batch"
    assert routes["$broker_recommend_count_asof"]["materializer"] == "_join_pit_panel_asof_batch"
    assert routes["$fina_mainbz_sales_sum_asof"]["materializer"] == "_join_pit_panel_asof_batch"
    for name in (
        "$trade_cal_is_open",
        "$benchmark_hs300_weight_sum",
        "$moneyflow_ind_dc_net_amount_sum",
        "$moneyflow_ind_ths_net_amount_sum",
        "$moneyflow_cnt_ths_net_amount_sum",
        "$broker_recommend_count_asof",
        "$fina_mainbz_sales_sum_asof",
        "$fina_mainbz_profit_sum_asof",
    ):
        assert routes[name]["prompt_visible"] is False


def test_production_expanded_profile_has_expression_field_semantics() -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile

    profile = load_mining_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )
    fields_by_name = {field.feature_name: field for field in profile.fields}
    expression_fields = [field for field in profile.fields if "expression" in field.allowed_usage]
    expression_names = {field.feature_name for field in expression_fields}

    assert "$daily_pct_chg" not in expression_names
    assert "$pledge_stat_amount_180d" not in fields_by_name
    assert "$pledge_stat_ratio_180d" in fields_by_name
    assert fields_by_name["$pledge_stat_ratio_180d"].allowed_usage == ("context", "backtest_standard_frame")
    assert "$new_share_amount_180d" not in fields_by_name
    assert "$new_share_vol_180d" in expression_names
    assert "$pledge_detail_amount_180d" not in fields_by_name
    assert "$pledge_detail_vol_180d" in expression_names
    assert "$stk_holdertrade_amount_180d" not in fields_by_name
    assert "$stk_holdertrade_vol_180d" in expression_names
    assert "$daily_basic_pe_ttm" in expression_names
    assert "$moneyflow_net_mf_amount" in expression_names
    assert "$cyq_perf_cost_5pct" in expression_names
    assert "$cyq_perf_cost_50pct" in expression_names
    assert "$cyq_perf_cost_95pct" in expression_names
    assert "$fina_indicator_debt_to_assets_asof" in expression_names
    assert "$namechange_count_365d" in expression_names
    assert "$stk_managers_count_365d" in expression_names
    assert fields_by_name["$is_suspended_external"].allowed_usage == ("tradability", "context", "backtest_standard_frame")
    assert fields_by_name["$is_st_external"].allowed_usage == ("tradability", "context", "backtest_standard_frame")
    assert fields_by_name["$benchmark_hs300_return"].allowed_usage == ("benchmark", "context", "backtest_standard_frame")
    assert fields_by_name["$mkt_moneyflow_net_amount"].allowed_usage == ("context", "backtest_standard_frame")
    assert fields_by_name["$stock_basic_market_asof"].allowed_usage == ("context", "backtest_standard_frame")
    assert fields_by_name["$stock_company_reg_capital_asof"].allowed_usage == ("context", "backtest_standard_frame")
    assert fields_by_name["$stock_company_employees_asof"].allowed_usage == ("context", "backtest_standard_frame")
    assert fields_by_name["$is_hsgt_external"].allowed_usage == ("tradability", "context", "backtest_standard_frame")

    for field in expression_fields:
        assert field.semantic_type
        assert field.unit
        assert field.scale is not None
        assert field.source_methodology


def test_production_expanded_profile_admits_only_first_cyq_perf_cost_tranche() -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile, validate_admission_profile

    profile = load_mining_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )
    report = validate_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )
    fields_by_name = {field.feature_name: field for field in profile.fields}
    cyq_perf_names = {
        field.feature_name
        for field in profile.fields
        if field.source_interface == "cyq_perf" and "expression" in field.allowed_usage
    }

    assert {
        "$cyq_perf_winner_rate",
        "$cyq_perf_cost_5pct",
        "$cyq_perf_cost_50pct",
        "$cyq_perf_cost_95pct",
    } <= cyq_perf_names
    assert "$cyq_perf_cost_15pct" not in cyq_perf_names
    assert "$cyq_perf_cost_85pct" not in cyq_perf_names
    assert "$cyq_perf_weight_avg" not in cyq_perf_names
    for name in ("$cyq_perf_cost_5pct", "$cyq_perf_cost_50pct", "$cyq_perf_cost_95pct"):
        field = fields_by_name[name]
        assert field.admitted_by == "REQ-2026-0015"
        assert field.source_kind == "daily_panel"
        assert field.source_interface == "cyq_perf"
        assert field.semantic_type == "chip_cost_percentile"
        assert report["routes"][name]["materializer"] == "_join_daily_panel_batch"
        assert report["routes"][name]["prompt_visible"] is True
    assert "cyq_chips" not in report["coverage"]["blocked_interfaces"]


def test_production_expanded_profile_admits_cyq_chips_scalar_not_raw_distribution() -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile, validate_admission_profile

    profile = load_mining_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )
    report = validate_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )
    cyq_chip_fields = {
        field.feature_name: field
        for field in profile.fields
        if field.feature_name.startswith("$cyq_chips_")
    }

    assert set(cyq_chip_fields) == {
        "$cyq_chips_chip_entropy",
        "$cyq_chips_peak_price",
        "$cyq_chips_peak_percent",
        "$cyq_chips_top5_concentration",
        "$cyq_chips_width_5_95",
    }
    assert all(field.source_interface == "cyq_chips_scalar" for field in cyq_chip_fields.values())
    assert all(field.source_kind == "daily_panel" for field in cyq_chip_fields.values())
    assert "cyq_chips" not in {field.source_interface for field in profile.fields}
    assert "cyq_chips" not in report["coverage"]["blocked_interfaces"]
    assert "cyq_chips_scalar" in report["coverage"]["admitted_interfaces"]
    for name in cyq_chip_fields:
        assert report["routes"][name]["materializer"] == "_join_daily_panel_batch"
        assert report["routes"][name]["prompt_visible"] is True


def test_real_hfq_expanded_profile_smoke_materializes_small_frame() -> None:
    from quantaalpha.backtest.mining_admission import load_mining_admission_profile
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    storage_root = Path("/home/quan/testdata/aspipe_v4/data")
    if not (storage_root / "stk_factor_pro" / "clean" / "active").exists():
        pytest.skip("local App5 real data is not available")
    profile = load_mining_admission_profile(
        Path("/home/quan/testdata/aspipe_v4/config/factor_mining_data_admission.yaml"),
        "expanded_app5_v1",
    )

    result = App5StandardFrameBuilder(storage_root=storage_root).build(
        StandardFrameRequest(
            start_date="20240102",
            end_date="20240110",
            instruments=("000001.SZ",),
            daily_interface="stk_factor_pro",
            adjustment="hfq",
            admitted_fields=profile.fields,
            storage_root=str(storage_root),
        )
    )

    assert result.frame.height > 0
    assert result.manifest["standard_frame"]["adjustment"] == "hfq"
    assert "$inc_total_revenue_asof" in result.frame.columns
    assert "$repurchase_count_30d" in result.frame.columns
    assert "$share_float_asof" in result.frame.columns


def test_mining_admission_profile_can_be_rebuilt_from_standard_frame_config() -> None:
    from quantaalpha.backtest.mining_admission import profile_from_standard_frame_config

    profile = profile_from_standard_frame_config(
        {
            "admission_profile": "mini",
            "admission_profile_hash": "sha256:test",
            "admitted_fields": [
                {
                    "base": {
                        "source_interface": "daily_basic",
                        "source_field": "pe",
                        "feature_name": "$daily_basic_pe",
                        "dtype": "float64",
                        "join_key": ["datetime", "instrument"],
                        "time_policy": "same_trade_date_no_lookahead",
                        "missing_policy": "nan",
                        "allowed_usage": ["expression", "backtest_standard_frame"],
                    },
                    "source_kind": "daily_panel",
                    "payload": {"source_interface": "daily_basic", "source_field": "pe"},
                }
            ],
        }
    )

    assert profile.name == "mini"
    assert profile.version_hash() == "sha256:test"
    assert profile.expression_feature_names() == ("$daily_basic_pe",)
