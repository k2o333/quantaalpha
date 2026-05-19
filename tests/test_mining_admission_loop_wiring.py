from __future__ import annotations


def test_standard_frame_capability_wiring_uses_mining_admission_profile(tmp_path, monkeypatch) -> None:
    from quantaalpha.pipeline import loop

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
    calls: list[dict] = []

    def fake_prepare(config):
        calls.append(config)

    monkeypatch.setattr(loop, "prepare_data_folder_from_standard_frame", fake_prepare, raising=False)

    quality_gate_config: dict = {}
    backtest_config = {
        "standard_frame": {
            "daily_interface": "daily",
            "admission_profile_path": str(profile_path),
            "admission_profile": "mini",
        }
    }

    loop._configure_standard_frame_capabilities(backtest_config, quality_gate_config)

    standard_frame = backtest_config["standard_frame"]
    assert standard_frame["admitted_fields"][0]["base"]["feature_name"] == "$daily_basic_pe"
    assert quality_gate_config["data_capabilities"]["daily_panel_features"]["fields"] == ["$daily_basic_pe"]
    assert calls == [backtest_config]
