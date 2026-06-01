from __future__ import annotations

import threading

import polars as pl
import pytest


def test_standard_frame_source_readiness_rejects_missing_open_market_date() -> None:
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    calls: list[tuple[str, dict]] = []

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            calls.append((interface_name, kwargs))
            if interface_name == "trade_cal":
                return pl.DataFrame(
                    {
                        "cal_date": ["20240102", "20240103", "20240104"],
                        "is_open": [1, 1, 1],
                    }
                )
            return pl.DataFrame({"trade_date": ["20240102", "20240104"]})

    builder = App5StandardFrameBuilder(adapter=FakeAdapter())

    with pytest.raises(
        ValueError,
        match=r"open-market dates missing from standard frame source: interface=stk_factor_pro missing_dates=1",
    ):
        builder.validate_source_readiness(
            StandardFrameRequest(
                start_date="2024-01-02",
                end_date="2024-01-04",
                daily_interface="stk_factor_pro",
            )
        )

    assert calls[0] == (
        "stk_factor_pro",
        {
            "start_date": "2024-01-02",
            "end_date": "2024-01-04",
            "columns": ["trade_date"],
            "unique": True,
        },
    )


def test_pipeline_preflight_validates_configured_standard_frame(monkeypatch) -> None:
    from quantaalpha.pipeline import preflight

    calls: list[tuple[str, object]] = []

    class FakeBuilder:
        def __init__(self, *, storage_root):
            calls.append(("storage_root", storage_root))

        def validate_source_readiness(self, request):
            calls.append(("request", request))

    monkeypatch.setattr(preflight, "App5StandardFrameBuilder", FakeBuilder)

    preflight.run_standard_frame_source_preflight(
        {
            "app5_storage_root": "/tmp/app5",
            "standard_frame": {
                "daily_interface": "stk_factor_pro",
                "start_date": "2024-01-02",
                "end_date": "2024-01-04",
            },
        }
    )

    assert calls[0] == ("storage_root", "/tmp/app5")
    assert calls[1][0] == "request"
    assert calls[1][1].daily_interface == "stk_factor_pro"
    assert calls[1][1].storage_root == "/tmp/app5"


def test_loop_runs_source_preflight_before_standard_frame_materialization(monkeypatch) -> None:
    from quantaalpha.pipeline import loop

    events: list[str] = []

    def fake_preflight(_config):
        events.append("preflight")

    def stop_at_materialization(_backtest_config, _quality_config):
        events.append("materialize")
        raise RuntimeError("stop after ordering assertion")

    monkeypatch.setattr(loop, "_run_standard_frame_source_preflight", fake_preflight)
    monkeypatch.setattr(loop, "_configure_standard_frame_capabilities", stop_at_materialization)

    with pytest.raises(RuntimeError, match="stop after ordering assertion"):
        loop.AlphaAgentLoop(
            PROP_SETTING=None,
            potential_direction=None,
            stop_event=threading.Event(),
            backtest_noqlib_config={"standard_frame": {"daily_interface": "stk_factor_pro"}},
        )

    assert events == ["preflight", "materialize"]
