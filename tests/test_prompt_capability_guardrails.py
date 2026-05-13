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
