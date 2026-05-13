from quantaalpha.factors.coder.expr_parser import (
    bind_expression_columns,
    parse_expression,
    parse_symbol,
)


def test_bind_expression_columns_does_not_replace_substrings():
    columns = [
        "$low",
        "$return",
        "$moneyflow_buy_sm_amount",
        "$daily_basic_turnover_rate",
    ]
    expression = (
        "TS_ZSCORE($moneyflow_buy_sm_amount / "
        "TS_MEAN($daily_basic_turnover_rate, 20), 20) - TS_PCTCHANGE($return, 5)"
    )

    parsed = parse_expression(parse_symbol(expression, columns))
    bound = bind_expression_columns(parsed, columns)

    assert "moneyfdf" not in bound
    assert "df['$moneyflow_buy_sm_amount']" in bound
    assert "df['$daily_basic_turnover_rate']" in bound
    assert "df['$return']" in bound
    assert "df['$low']_buy_sm_amount" not in bound
