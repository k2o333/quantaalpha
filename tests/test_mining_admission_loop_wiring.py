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
        semantic_type: valuation_ratio
        unit: ratio
        scale: 1
        source_methodology: tushare_daily_basic
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
    assert quality_gate_config["data_capability_source"] == "admission"
    assert quality_gate_config["data_capabilities"]["daily_panel_features"]["fields"] == ["$daily_basic_pe"]
    assert calls == [backtest_config]


def test_standard_frame_capability_wiring_resolves_profile_relative_to_project_root(tmp_path, monkeypatch) -> None:
    from quantaalpha.pipeline import loop

    project_root = tmp_path / "project"
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "factor_mining_data_admission.yaml").write_text(
        """
version: 1
profiles:
  mini:
    fields:
      - feature_name: "$daily_basic_pe"
        semantic_type: valuation_ratio
        unit: ratio
        scale: 1
        source_methodology: tushare_daily_basic
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
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loop, "prepare_data_folder_from_standard_frame", lambda _config: None, raising=False)
    backtest_config = {
        "project_root": str(project_root),
        "standard_frame": {
            "admission_profile_path": "config/factor_mining_data_admission.yaml",
            "admission_profile": "mini",
        },
    }
    quality_gate_config: dict = {}

    loop._configure_standard_frame_capabilities(backtest_config, quality_gate_config)

    assert backtest_config["standard_frame"]["admission_profile_path"] == str(config_dir / "factor_mining_data_admission.yaml")
    assert quality_gate_config["data_capabilities"]["daily_panel_features"]["fields"] == ["$daily_basic_pe"]


def test_standard_frame_capability_wiring_keeps_optional_fields_and_reuses_admitted_fields(monkeypatch) -> None:
    from quantaalpha.backtest.contracts import OptionalStandardFrameField
    from quantaalpha.backtest.mining_admission import MiningAdmissionField
    from quantaalpha.pipeline import loop

    field = MiningAdmissionField(
        base=OptionalStandardFrameField(
            source_interface="daily_basic",
            source_field="pe",
            feature_name="$daily_basic_pe",
            dtype="float64",
            join_key=("datetime", "instrument"),
            time_policy="same_trade_date_no_lookahead",
            missing_policy="nan",
            allowed_usage=("expression", "backtest_standard_frame"),
        ),
        source_kind="daily_panel",
        payload={"source_interface": "daily_basic", "source_field": "pe"},
    )
    monkeypatch.setattr(loop, "prepare_data_folder_from_standard_frame", lambda _config: None, raising=False)
    monkeypatch.setattr(
        "quantaalpha.backtest.mining_admission.load_mining_admission_profile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("profile should not be reloaded")),
    )
    backtest_config = {
        "standard_frame": {
            "admission_profile_path": "unused.yaml",
            "admission_profile": "mini",
            "admission_profile_hash": "sha256:test",
            "optional_fields": [{"feature_name": "$legacy"}],
            "admitted_fields": [field.identity()],
        },
    }
    quality_gate_config: dict = {}

    loop._configure_standard_frame_capabilities(backtest_config, quality_gate_config)

    assert backtest_config["standard_frame"]["optional_fields"] == [{"feature_name": "$legacy"}]
    assert quality_gate_config["data_capabilities"]["daily_panel_features"]["fields"] == ["$daily_basic_pe"]
