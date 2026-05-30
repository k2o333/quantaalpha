from __future__ import annotations

from pathlib import Path

import polars as pl


def test_mini_mining_admission_yaml_builds_frame_and_prompt_capabilities(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import (
        capabilities_from_mining_admission_profile,
        load_mining_admission_profile,
    )
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest
    from quantaalpha.factors.data_capability import render_data_capabilities

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    profile_path.write_text(
        """
version: 1
profiles:
  test:
    base_standard_frame:
      daily_interface: daily
      adjustment: raw
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
        missing_policy: required
        allowed_usage: [expression, backtest_standard_frame]
      - feature_name: "$daily_basic_pb_context"
        source_kind: daily_panel
        source_interface: daily_basic
        source_field: pb
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: [context, backtest_standard_frame]
""",
        encoding="utf-8",
    )
    profile = load_mining_admission_profile(profile_path, "test")
    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "vol": [1000.0, 1100.0],
            "amount": [1020.0, 1232.0],
            "pct_chg": [1.0, 9.8039],
        }
    )
    daily_basic_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "turnover_rate": [1.2, 1.3],
            "pb": [0.9, 1.1],
        }
    )

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            del kwargs
            return {"daily": daily_frame, "daily_basic": daily_basic_frame}[interface_name]

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(
        StandardFrameRequest(
            storage_root=str(tmp_path),
            **profile.base_standard_frame,
            admitted_fields=profile.fields,
        )
    )
    rendered = render_data_capabilities(capabilities_from_mining_admission_profile(profile))

    assert "$daily_basic_turnover_rate" in result.frame.columns
    assert "$daily_basic_pb_context" in result.frame.columns
    assert "$daily_basic_turnover_rate" in rendered
    assert "$daily_basic_pb_context" not in rendered


def test_runtime_context_source_kinds_materialize_without_prompt_expression_visibility(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import (
        capabilities_from_mining_admission_profile,
        load_mining_admission_profile,
    )
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest
    from quantaalpha.factors.data_capability import render_data_capabilities

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    profile_path.write_text(
        """
version: 1
profiles:
  test:
    base_standard_frame:
      daily_interface: daily
      adjustment: raw
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
        encoding="utf-8",
    )
    profile = load_mining_admission_profile(profile_path, "test")
    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "vol": [1000.0, 1100.0],
            "amount": [1020.0, 1232.0],
            "pct_chg": [1.0, 9.8039],
        }
    )
    trade_cal = pl.DataFrame({"cal_date": ["20240102", "20240103"], "is_open": [1, 1]})
    suspend = pl.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20240103"], "suspend_type": ["S"]})
    index_daily = pl.DataFrame(
        {
            "ts_code": ["000300.SH", "000905.SH", "000300.SH"],
            "trade_date": ["20240102", "20240102", "20240103"],
            "pct_chg": [0.5, 0.7, -0.2],
        }
    )
    market_flow = pl.DataFrame({"trade_date": ["20240102", "20240103"], "net_amount": [100.0, -50.0]})

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            del kwargs
            return {
                "daily": daily_frame,
                "trade_cal": trade_cal,
                "suspend_d": suspend,
                "index_daily": index_daily,
                "moneyflow_mkt_dc": market_flow,
            }[interface_name]

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(
        StandardFrameRequest(
            storage_root=str(tmp_path),
            **profile.base_standard_frame,
            admitted_fields=profile.fields,
        )
    )
    rendered = render_data_capabilities(capabilities_from_mining_admission_profile(profile))

    rows = result.frame.select(
        "datetime",
        "instrument",
        "$is_suspended_external",
        "$benchmark_hs300_return",
        "$mkt_moneyflow_net_amount",
    ).to_dicts()
    assert rows == [
        {
            "datetime": rows[0]["datetime"],
            "instrument": "000001.SZ",
            "$is_suspended_external": 0.0,
            "$benchmark_hs300_return": 0.5,
            "$mkt_moneyflow_net_amount": 100.0,
        },
        {
            "datetime": rows[1]["datetime"],
            "instrument": "000001.SZ",
            "$is_suspended_external": 1.0,
            "$benchmark_hs300_return": -0.2,
            "$mkt_moneyflow_net_amount": -50.0,
        },
    ]
    assert "$is_suspended_external" not in rendered
    assert "$benchmark_hs300_return" not in rendered
    assert "$mkt_moneyflow_net_amount" not in rendered


def test_company_dimension_and_hsgt_mask_materialize_without_prompt_expression_visibility(tmp_path: Path) -> None:
    from quantaalpha.backtest.mining_admission import (
        capabilities_from_mining_admission_profile,
        load_mining_admission_profile,
    )
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest
    from quantaalpha.factors.data_capability import render_data_capabilities

    profile_path = tmp_path / "factor_mining_data_admission.yaml"
    profile_path.write_text(
        """
version: 1
profiles:
  test:
    base_standard_frame:
      daily_interface: daily
      adjustment: raw
    fields:
      - feature_name: "$stock_company_reg_capital_asof"
        source_kind: dimension_asof
        source_interface: stock_company
        source_field: reg_capital
        effective_date_column: setup_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: effective_date_asof_no_lookahead
        missing_policy: nan
        allowed_usage: [context, backtest_standard_frame]
      - feature_name: "$stock_company_employees_asof"
        source_kind: dimension_asof
        source_interface: stock_company
        source_field: employees
        effective_date_column: setup_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: effective_date_asof_no_lookahead
        missing_policy: nan
        allowed_usage: [context, backtest_standard_frame]
      - feature_name: "$is_hsgt_external"
        source_kind: tradability_mask
        source_interface: stock_hsgt
        source_field: type
        date_column: trade_date
        dtype: float64
        join_key: [datetime, instrument]
        time_policy: tradability_state_no_lookahead
        missing_policy: zero
        allowed_usage: [tradability, context, backtest_standard_frame]
""",
        encoding="utf-8",
    )
    profile = load_mining_admission_profile(profile_path, "test")
    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "vol": [1000.0, 1100.0],
            "amount": [1020.0, 1232.0],
            "pct_chg": [1.0, 9.8039],
        }
    )
    stock_company = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "setup_date": ["19871222"],
            "reg_capital": [1940591.8198],
            "employees": [45000],
        }
    )
    stock_hsgt = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240103"],
            "type": ["HK_SZ"],
        }
    )

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            del kwargs
            return {
                "daily": daily_frame,
                "stock_company": stock_company,
                "stock_hsgt": stock_hsgt,
            }[interface_name]

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(
        StandardFrameRequest(
            storage_root=str(tmp_path),
            **profile.base_standard_frame,
            admitted_fields=profile.fields,
        )
    )
    rendered = render_data_capabilities(capabilities_from_mining_admission_profile(profile))

    rows = result.frame.select(
        "datetime",
        "instrument",
        "$stock_company_reg_capital_asof",
        "$stock_company_employees_asof",
        "$is_hsgt_external",
    ).to_dicts()
    assert rows == [
        {
            "datetime": rows[0]["datetime"],
            "instrument": "000001.SZ",
            "$stock_company_reg_capital_asof": 1940591.8198,
            "$stock_company_employees_asof": 45000.0,
            "$is_hsgt_external": 0.0,
        },
        {
            "datetime": rows[1]["datetime"],
            "instrument": "000001.SZ",
            "$stock_company_reg_capital_asof": 1940591.8198,
            "$stock_company_employees_asof": 45000.0,
            "$is_hsgt_external": 1.0,
        },
    ]
    assert "$stock_company_reg_capital_asof" not in rendered
    assert "$stock_company_employees_asof" not in rendered
    assert "$is_hsgt_external" not in rendered
