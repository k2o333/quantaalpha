from __future__ import annotations


def test_expression_admission_accepts_supported_composed_expression() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression("ts_mean(close, 2) + DELTA($close, 1)", available_fields=["close"])

    assert result.accepted
    assert result.canonical == "TS_MEAN($close, 2) + DELTA($close, 1)"


def test_expression_admission_classifies_unsupported_function() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression("SECTOR_RETURN($close)", available_fields=["close"])

    assert not result.accepted
    assert result.reason_code == "unsupported_function"
    assert result.function_name == "SECTOR_RETURN"
    assert result.arity == 1


def test_expression_admission_classifies_wrong_arity() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression("TS_MEAN($close)", available_fields=["close"])

    assert not result.accepted
    assert result.reason_code == "unsupported_arity"
    assert result.function_name == "TS_MEAN"
    assert result.arity == 1


def test_expression_admission_classifies_missing_field_from_runtime_columns() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression("TS_MEAN($missing, 2)", available_fields=["close", "open"])

    assert not result.accepted
    assert result.reason_code == "missing_field"
    assert result.missing_fields == ("$missing",)


def test_expression_admission_accepts_explicit_non_canonical_field_when_present() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression(
        "TS_MEAN($daily_basic_turnover_rate, 2)",
        available_fields=["$daily_basic_turnover_rate"],
    )

    assert result.accepted


def test_expression_admission_classifies_parse_error() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression("TS_MEAN($close", available_fields=["close"])

    assert not result.accepted
    assert result.reason_code == "parse_error"


def test_expression_admission_classifies_scalar_value_mismatch() -> None:
    from quantaalpha.backtest.expression import admit_expression

    result = admit_expression("MEAN(1, 2)", available_fields=["close"])

    assert not result.accepted
    assert result.reason_code == "scalar_value_mismatch"


def test_operator_signature_extractor_collects_arities_sets_and_aliases() -> None:
    from quantaalpha.backtest.expression import extract_operator_signatures

    signatures = extract_operator_signatures()

    assert signatures["SMA"].arities == (2, 3)
    assert signatures["PERCENTILE"].arities == (2, 3)
    assert signatures["TS_ZSCORE"].arities == (1, 2)
    assert signatures["DELTA"].arities == (2,)
    assert signatures["TS_DELTA"].arities == (2,)
    assert "Mean" in signatures["TS_MEAN"].aliases
    assert "ts_mean" in signatures["TS_MEAN"].aliases
