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
