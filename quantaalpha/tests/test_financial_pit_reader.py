"""Tests for minimal financial PIT reader behavior."""

import json
import tempfile
from pathlib import Path

import polars as pl
import pytest

from quantaalpha.factors.data_capability import (
    load_financial_pit_frame,
    query_financial_pit_asof,
    query_financial_pit_panel_asof,
)


def _write_report(storage_root: str, pit_path: str | None = None, layer: str = "financial_pit") -> Path:
    report = {
        "_meta": {
            "schema_version": 2,
            "storage_root": storage_root,
        },
        "interfaces": {
            "income_vip": {
                "semantic": {
                    "field_aliases": ["$basic_eps", "$n_income"],
                    "freq": "quarterly",
                    "lag_days": 45,
                    "join_mode": "forward_fill",
                    "factor_hints": ["fundamental"],
                    "layer": layer,
                    "is_auxiliary": False,
                },
                "runtime": {},
            }
        },
    }
    if pit_path is not None:
        report["interfaces"]["income_vip"]["runtime"]["financial_pit_path"] = pit_path

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(report, tmp)
    tmp.close()
    return Path(tmp.name)


def _write_pit_parquet(path: Path) -> None:
    df = pl.DataFrame(
        {
            "instrument": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "report_period": ["20231231", "20231231", "20240630"],
            "disclosure_date": ["2024-03-28", "2024-04-12", "2024-08-29"],
            "alias": ["$basic_eps", "$basic_eps", "$n_income"],
            "value": [1.2, 1.3, 10.0],
            "source_interface": ["income_vip", "income_vip", "income_vip"],
            "source_field": ["basic_eps", "basic_eps", "n_income"],
            "revision_seq": [0, 1, 0],
            "next_disclosure_date": ["2024-04-12", None, None],
            "is_latest": [False, True, True],
        }
    )
    df.write_parquet(path)


class TestFinancialPitReader:
    def test_load_financial_pit_uses_runtime_storage_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = load_financial_pit_frame("income_vip", report_path=report_path)
                assert df.height == 2
                assert set(df["alias"].to_list()) == {"$basic_eps", "$n_income"}
                assert df["is_latest"].to_list() == [True, True]
            finally:
                report_path.unlink()

    def test_load_financial_pit_falls_back_to_storage_root_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_dir = storage_root / ".financial_pit"
            pit_dir.mkdir()
            pit_path = pit_dir / "income_vip.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=None)
            try:
                df = load_financial_pit_frame("income_vip", report_path=report_path)
                assert df.height == 2
                assert df["instrument"].to_list() == ["000001.SZ", "000001.SZ"]
            finally:
                report_path.unlink()

    def test_load_financial_pit_can_return_all_versions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = load_financial_pit_frame("income_vip", report_path=report_path, latest_only=False)
                assert df.height == 3
                assert sorted(df["revision_seq"].to_list()) == [0, 0, 1]
            finally:
                report_path.unlink()

    def test_load_financial_pit_rejects_non_financial_layer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path), layer="main_daily")
            try:
                with pytest.raises(ValueError, match="financial_pit"):
                    load_financial_pit_frame("income_vip", report_path=report_path)
            finally:
                report_path.unlink()


class TestFinancialPitAsOfQuery:
    def test_query_financial_pit_asof_picks_latest_visible_revision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = query_financial_pit_asof("income_vip", "2024-04-15", report_path=report_path)
                row = df.filter((pl.col("alias") == "$basic_eps") & (pl.col("report_period") == "20231231"))
                assert row.height == 1
                assert row["value"].to_list() == [1.3]
                assert row["revision_seq"].to_list() == [1]
            finally:
                report_path.unlink()


class TestFinancialPitPanelAsOfQuery:
    def test_query_financial_pit_panel_asof_returns_wide_panel(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = query_financial_pit_panel_asof("income_vip", "2024-09-01", report_path=report_path)
                assert df.columns == ["instrument", "$basic_eps", "$n_income"]
                assert df.height == 1
                assert df["instrument"].to_list() == ["000001.SZ"]
                assert df["$basic_eps"].to_list() == [1.3]
                assert df["$n_income"].to_list() == [10.0]
            finally:
                report_path.unlink()

    def test_query_financial_pit_panel_asof_respects_alias_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = query_financial_pit_panel_asof(
                    "income_vip",
                    "2024-09-01",
                    report_path=report_path,
                    aliases=["$n_income"],
                )
                assert df.columns == ["instrument", "$n_income"]
                assert df["$n_income"].to_list() == [10.0]
            finally:
                report_path.unlink()

    def test_query_financial_pit_asof_excludes_future_disclosures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = query_financial_pit_asof("income_vip", "2024-03-30", report_path=report_path)
                assert "$n_income" not in df["alias"].to_list()
                row = df.filter((pl.col("alias") == "$basic_eps") & (pl.col("report_period") == "20231231"))
                assert row["value"].to_list() == [1.2]
                assert row["revision_seq"].to_list() == [0]
            finally:
                report_path.unlink()

    def test_query_financial_pit_asof_can_filter_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_root = Path(tmpdir)
            pit_path = storage_root / "custom-income.parquet"
            _write_pit_parquet(pit_path)
            report_path = _write_report(str(storage_root), pit_path=str(pit_path))
            try:
                df = query_financial_pit_asof(
                    "income_vip",
                    "2024-09-01",
                    report_path=report_path,
                    aliases=["$n_income"],
                )
                assert df.height == 1
                assert df["alias"].to_list() == ["$n_income"]
                assert df["value"].to_list() == [10.0]
            finally:
                report_path.unlink()
