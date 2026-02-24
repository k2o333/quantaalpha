import pytest
from unittest.mock import Mock, patch
from app4.core.pagination import PaginationComposer, PaginationContext

def test_date_anchor_pagination_filters_non_trading_days():
    """Test that date anchor pagination only uses trading days."""
    # Mock interface config for date anchor
    interface_config = {
        "name": "cyq_perf",
        "parameters": {
            "trade_date": {
                "type": "string",
                "required": False,
                "description": "交易日期",
                "is_date_anchor": True
            }
        },
        "pagination": {
            "mode": "reverse_date_range"
        }
    }

    context = PaginationContext(
        interface_config=interface_config,
        trade_calendar=[
            {"cal_date": "20260220", "is_open": 1},  # Friday - trading day
            {"cal_date": "20260221", "is_open": 0},  # Saturday - non-trading day
            {"cal_date": "20260222", "is_open": 0},  # Sunday - non-trading day
            {"cal_date": "20260223", "is_open": 1}   # Monday - trading day
        ]
    )

    composer = PaginationComposer(context)

    # Test the _apply_date_anchor_range method with mocked trade days
    base_params = {"start_date": "20260220", "end_date": "20260223"}
    result_params = list(composer._apply_date_anchor_range([base_params]))

    # After fix: should only have trading days (not include weekend dates)
    # The dates should be in reverse order due to reverse_date_range mode
    expected_dates = ["20260223", "20260220"]  # reversed order: Monday, then Friday
    actual_dates = [p["trade_date"] for p in result_params]

    assert actual_dates == expected_dates, f"Expected only trading days {expected_dates}, got {actual_dates}"