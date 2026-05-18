"""Shared backtest contracts for the qlib/noqlib/vnpy routes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

STANDARD_FRAME_KEY_COLUMNS = ("datetime", "instrument")
STANDARD_FRAME_FACTOR_FIELDS = ("$open", "$high", "$low", "$close", "$volume", "$vwap", "$return")
STANDARD_FRAME_REQUIRED_COLUMNS = (*STANDARD_FRAME_KEY_COLUMNS, *STANDARD_FRAME_FACTOR_FIELDS)

APP5_INTERFACE_CLASSES = {
    "daily_panel",
    "pit_panel",
    "event_state",
    "dimension",
    "tradability",
    "benchmark",
    "unsupported_for_backtest",
}

METRIC_NAMESPACES = {
    "signal_ic": ("IC", "ICIR", "Rank IC", "Rank ICIR"),
    "diagnostic_long_short": (
        "long_short_return_mean",
        "long_short_return_annualized",
        "long_short_sharpe",
        "long_short_max_drawdown",
    ),
    "long_only_portfolio": ("return", "bench", "cost", "turnover", "cash", "equity"),
    "excess_vs_benchmark": (
        "daily_excess_return",
        "annualized_return",
        "information_ratio",
        "max_drawdown",
        "calmar_ratio",
    ),
    "portfolio_diagnostics": (
        "missing_close_valuation_count",
        "missing_open_buy_skip_count",
        "missing_open_sell_skip_count",
        "missing_price_example_count",
    ),
}

EXPLICIT_APP5_INTERFACE_CLASSIFICATION: dict[str, tuple[str, str]] = {
    "daily": ("daily_panel", "OHLCV daily bar source for the standard frame."),
    "daily_basic": ("daily_panel", "Daily valuation/liquidity panel joined by trade date and instrument."),
    "stk_factor_pro": ("daily_panel", "Daily technical factor panel joined by trade date and instrument."),
    "moneyflow": ("daily_panel", "Daily instrument money-flow panel."),
    "moneyflow_dc": ("daily_panel", "Daily Eastmoney instrument money-flow panel."),
    "moneyflow_ths": ("daily_panel", "Daily THS instrument money-flow panel."),
    "moneyflow_ind_dc": ("daily_panel", "Daily industry money-flow panel for market context."),
    "moneyflow_ind_ths": ("daily_panel", "Daily THS industry money-flow panel for market context."),
    "moneyflow_mkt_dc": ("daily_panel", "Daily market-level money-flow context."),
    "moneyflow_cnt_ths": ("daily_panel", "Daily THS concept money-flow context."),
    "cyq_chips": ("daily_panel", "Daily chip-distribution panel joined by trade date and instrument."),
    "cyq_perf": ("daily_panel", "Daily chip-performance panel joined by trade date and instrument."),
    "stock_hsgt": ("daily_panel", "Daily northbound/southbound holding panel."),
    "index_weight": ("benchmark", "Index constituent weight source for benchmark/universe construction."),
    "trade_cal": ("tradability", "Exchange calendar source for tradable days."),
    "suspend_d": ("tradability", "Suspension state constrains tradable instruments."),
    "stock_st": ("tradability", "ST state constrains production trading eligibility."),
    "stock_basic": ("dimension", "Static/listing dimension keyed by instrument."),
    "stock_company": ("dimension", "Static company dimension keyed by instrument."),
    "share_float": ("dimension", "Float-share dimension with effective-date semantics."),
    "namechange": ("event_state", "Name-change events require effective-date/asof handling."),
    "new_share": ("event_state", "IPO/new-share events require event-date handling."),
    "dividend": ("event_state", "Corporate-action events require ex-date/record-date handling."),
    "repurchase": ("event_state", "Repurchase events require announcement/event-date handling."),
    "block_trade": ("event_state", "Block-trade events require trade-date event handling."),
    "pledge_detail": ("event_state", "Pledge detail events require event-date/asof handling."),
    "pledge_stat": ("event_state", "Pledge state summary requires date-aware event handling."),
    "stk_holdertrade": ("event_state", "Holder-trade events require announcement/event-date handling."),
    "stk_managers": ("event_state", "Manager-change events require effective-date handling."),
    "stk_rewards": ("event_state", "Reward events require announcement/effective-date handling."),
    "stk_surv": ("event_state", "Survey events require event-date/asof handling."),
    "top10_holders": ("pit_panel", "Holder reports require report-period plus announcement asof semantics."),
    "top10_floatholders": ("pit_panel", "Float-holder reports require report-period plus announcement asof semantics."),
    "income_vip": ("pit_panel", "Financial statement data requires report-period plus disclosure asof semantics."),
    "balancesheet_vip": ("pit_panel", "Financial statement data requires report-period plus disclosure asof semantics."),
    "cashflow_vip": ("pit_panel", "Financial statement data requires report-period plus disclosure asof semantics."),
    "fina_indicator_vip": ("pit_panel", "Financial indicators require report-period plus disclosure asof semantics."),
    "fina_audit": ("pit_panel", "Audit data requires report-period plus disclosure asof semantics."),
    "fina_mainbz_vip": ("pit_panel", "Main-business financial data requires report-period plus disclosure asof semantics."),
    "forecast_vip": ("pit_panel", "Forecast data requires announcement-date asof semantics."),
    "express_vip": ("pit_panel", "Express financial data requires announcement-date asof semantics."),
    "disclosure_date": ("pit_panel", "Disclosure calendar defines PIT availability for financial reports."),
    "report_rc": ("pit_panel", "Research consensus requires report-date/asof semantics."),
    "broker_recommend": ("pit_panel", "Broker recommendations require publish-date/asof semantics."),
}


@dataclass(frozen=True)
class App5InterfaceAdmission:
    """A classified App5 clean/active interface."""

    interface: str
    primary_class: str
    reason: str
    active_path: str | None = None


@dataclass(frozen=True)
class OptionalStandardFrameField:
    """Admission metadata required for a non-minimal standard-frame field."""

    source_interface: str
    source_field: str
    feature_name: str
    dtype: str
    join_key: tuple[str, ...]
    time_policy: str
    missing_policy: str
    allowed_usage: tuple[str, ...]


@dataclass(frozen=True)
class QlibReturnProvenance:
    """Provenance for a qlib summary return metric."""

    recorder_object: str
    dataframe_path: str
    column_name: str
    transformation: str
    risk_analyzer_input: str
    daily_series_name: str
    source_series_proven_identical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_app5_interface(interface: str, active_path: str | None = None) -> App5InterfaceAdmission:
    """Return the frozen primary class for an App5 interface."""
    if interface not in EXPLICIT_APP5_INTERFACE_CLASSIFICATION:
        raise ValueError(f"App5 interface is not classified for backtest admission: {interface}")
    primary_class, reason = EXPLICIT_APP5_INTERFACE_CLASSIFICATION[interface]
    if primary_class not in APP5_INTERFACE_CLASSES:
        raise ValueError(f"Invalid App5 interface class {primary_class!r} for {interface!r}")
    return App5InterfaceAdmission(
        interface=interface,
        primary_class=primary_class,
        reason=reason,
        active_path=active_path,
    )


def inventory_clean_active_interfaces(storage_root: str | Path = "data") -> tuple[App5InterfaceAdmission, ...]:
    """Classify every App5 ``data/<interface>/clean/active`` directory."""
    root = Path(storage_root)
    admissions: list[App5InterfaceAdmission] = []
    for active_dir in sorted(root.glob("*/clean/active")):
        if not active_dir.is_dir():
            continue
        has_parquet = any(active_dir.glob("*.parquet"))
        if not has_parquet:
            continue
        interface = active_dir.parents[1].name
        admissions.append(classify_app5_interface(interface, str(active_dir)))
    return tuple(admissions)


def validate_standard_frame_columns(columns: Iterable[str]) -> None:
    """Fail fast when the minimal backtest standard frame is incomplete."""
    present = {str(column) for column in columns}
    missing = [column for column in STANDARD_FRAME_REQUIRED_COLUMNS if column not in present]
    if missing:
        raise ValueError(f"backtest standard frame missing required columns: {missing}")


def validate_optional_standard_frame_field(field: OptionalStandardFrameField) -> None:
    """Validate admission metadata for a non-minimal standard-frame field."""
    if field.source_interface not in EXPLICIT_APP5_INTERFACE_CLASSIFICATION:
        raise ValueError(f"optional field source interface is not classified: {field.source_interface}")
    if not field.source_field or not field.feature_name:
        raise ValueError("optional standard-frame fields require source_field and feature_name")
    if not field.join_key:
        raise ValueError("optional standard-frame fields require an explicit join_key")
    if not field.time_policy:
        raise ValueError("optional standard-frame fields require an explicit time/asof policy")
    if not field.missing_policy:
        raise ValueError("optional standard-frame fields require an explicit missing policy")
    if not field.allowed_usage:
        raise ValueError("optional standard-frame fields require explicit allowed_usage")


def build_metric_namespaces(
    *,
    signal_metrics: Mapping[str, Any] | None = None,
    portfolio_metrics: Mapping[str, Any] | None = None,
    daily_report_columns: Iterable[str] = (),
    qlib_return_provenance: QlibReturnProvenance | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build namespaced metrics while preserving legacy flat metrics elsewhere."""
    signal_metrics = signal_metrics or {}
    portfolio_metrics = portfolio_metrics or {}
    daily_columns = set(daily_report_columns)
    namespaces: dict[str, Any] = {
        "signal_ic": {key: signal_metrics[key] for key in METRIC_NAMESPACES["signal_ic"] if key in signal_metrics},
        "diagnostic_long_short": {
            key: signal_metrics[key]
            for key in METRIC_NAMESPACES["diagnostic_long_short"]
            if key in signal_metrics
        },
        "long_only_portfolio": {
            "daily_report_columns": sorted(daily_columns.intersection(METRIC_NAMESPACES["long_only_portfolio"])),
        },
        "excess_vs_benchmark": {
            key: portfolio_metrics[key]
            for key in METRIC_NAMESPACES["excess_vs_benchmark"][1:]
            if key in portfolio_metrics
        },
        "portfolio_diagnostics": {
            key: portfolio_metrics[key]
            for key in METRIC_NAMESPACES["portfolio_diagnostics"]
            if key in portfolio_metrics
        },
    }
    if "return" in daily_columns and {"bench", "cost"}.issubset(daily_columns):
        namespaces["excess_vs_benchmark"]["daily_series"] = "return - bench - cost"
    if qlib_return_provenance is not None:
        if isinstance(qlib_return_provenance, QlibReturnProvenance):
            provenance_payload = qlib_return_provenance.to_dict()
        else:
            provenance_payload = dict(qlib_return_provenance)
        namespaces["excess_vs_benchmark"]["qlib_return_provenance"] = provenance_payload
    return namespaces
