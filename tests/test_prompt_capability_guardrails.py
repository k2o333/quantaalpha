from __future__ import annotations

import pytest


def test_validate_factor_expression_uses_only_admitted_expression_fields() -> None:
    from quantaalpha.backtest.data_admission import build_daily_panel_allowlist, validate_factor_expression_against_allowlist

    allowlist = build_daily_panel_allowlist(
        [
            {
                "source_interface": "daily_basic",
                "source_field": "turnover_rate",
                "feature_name": "$daily_basic_turnover_rate",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression",),
            },
            {
                "source_interface": "moneyflow_mkt_dc",
                "source_field": "net_amount",
                "feature_name": "$moneyflow_mkt_dc_net_amount",
                "dtype": "float64",
                "join_key": ("datetime",),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("context",),
            },
        ]
    )

    validate_factor_expression_against_allowlist("TS_MEAN($daily_basic_turnover_rate, 5)", allowlist)
    with pytest.raises(ValueError, match="FIELD_USAGE_NOT_EXPRESSION"):
        validate_factor_expression_against_allowlist("$moneyflow_mkt_dc_net_amount + $daily_basic_turnover_rate", allowlist)
    with pytest.raises(ValueError, match="FIELD_NOT_ADMITTED"):
        validate_factor_expression_against_allowlist("$not_admitted + $daily_basic_turnover_rate", allowlist)
    with pytest.raises(ValueError, match="UNSUPPORTED_FUNCTION"):
        validate_factor_expression_against_allowlist("BADFUNC($daily_basic_turnover_rate)", allowlist)


def test_structured_rejection_feedback_is_prompt_safe() -> None:
    from quantaalpha.backtest.data_admission import build_structured_rejection_feedback

    feedback = build_structured_rejection_feedback(
        reason_code="FIELD_NOT_ADMITTED",
        expression="$raw_secret_field + $close",
        field="$raw_secret_field",
        message="field is not admitted",
    )

    assert feedback["reason_code"] == "FIELD_NOT_ADMITTED"
    assert feedback["field"] == "$raw_secret_field"
    assert "raw schema" not in feedback["remediation"].lower()


def test_standard_frame_optional_fields_render_as_daily_panel_capabilities() -> None:
    from quantaalpha.factors.data_capability import capabilities_from_standard_frame_optional_fields, render_data_capabilities

    capabilities = capabilities_from_standard_frame_optional_fields(
        [
            {
                "source_interface": "daily_basic",
                "source_field": "turnover_rate",
                "feature_name": "$daily_basic_turnover_rate",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "stock_basic",
                "source_field": "name",
                "feature_name": "$stock_basic_name",
                "allowed_usage": ("context",),
            },
        ],
        manifest_version="sha256:test",
    )

    assert capabilities["expanded_daily_panel"]["fields"] == ["$daily_basic_turnover_rate"]
    rendered = render_data_capabilities(capabilities)
    assert "expanded_daily_panel" in rendered
    assert "$daily_basic_turnover_rate" in rendered
    assert "$stock_basic_name" not in rendered


def test_construct_prompt_field_hint_includes_base_and_admitted_fields() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from quantaalpha.factors.proposal import AlphaAgentHypothesis2FactorExpression

    constructor = object.__new__(AlphaAgentHypothesis2FactorExpression)
    constructor.data_capabilities = {
        "expanded_daily_panel": {
            "fields": ["$daily_basic_turnover_rate", "$moneyflow_buy_sm_amount"],
            "layer": "daily_panel",
        }
    }
    trace = SimpleNamespace(scen=MagicMock())

    hint = constructor._render_allowed_expression_field_hint(trace)

    assert "$open" in hint
    assert "$return" in hint
    assert "$daily_basic_turnover_rate" in hint
    assert "$moneyflow_buy_sm_amount" in hint
