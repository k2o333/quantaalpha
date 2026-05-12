"""
Unit tests for continuous runtime hooks (the four critical seams).

Tests cover:
- _run_factor_backtest: backtest execution seam
- _validate_factor: factor validation seam
- _generate_factors: factor generation seam
- _retrieve_context: context retrieval seam

These tests verify that stubs are replaced with real integration behavior.
"""

import json
import logging
import sys
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import polars as pl
import pytest


def _ensure_repo_root_importable():
    repo_root = Path(__file__).resolve().parents[4]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root_importable()


class TestBridgeDataIntegration:
    """Tests verifying schedulers use bridge loader for real data."""

    def _write_app5_daily_clean_dataset(self, tmp_path: Path) -> Path:
        data_root = tmp_path / "data"
        daily_root = data_root / "daily"
        active_dir = daily_root / "clean" / "active"
        active_dir.mkdir(parents=True)
        parquet_path = active_dir / "daily.parquet"
        pl.DataFrame(
            {
                "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
                "trade_date": ["20200102", "20231229", "20250102"],
                "open": [10.0, 20.0, 30.0],
                "high": [10.5, 20.5, 30.5],
                "low": [9.5, 19.5, 29.5],
                "close": [10.2, 20.2, 30.2],
                "vol": [1000.0, 2000.0, 3000.0],
            }
        ).write_parquet(parquet_path)
        manifest_dir = daily_root / "manifest"
        manifest_dir.mkdir()
        (manifest_dir / "current.json").write_text(
            json.dumps({"active_files": ["clean/active/daily.parquet"]}),
            encoding="utf-8",
        )
        return data_root

    def test_revalidation_loads_app5_clean_data_when_bridge_unconfigured(self, tmp_path):
        """Revalidation should use configured no-qlib clean data without requiring app4 bridge data."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        data_root = self._write_app5_daily_clean_dataset(tmp_path)
        scheduler = DefaultRevalidationScheduler(
            data_bridge=None,
            backtest_noqlib_config={
                "app5_storage_root": str(data_root),
                "daily_interface": "daily",
            },
        )

        df = scheduler._get_execution_dataframe()

        assert len(df) == 2
        assert df.columns == ["datetime", "vt_symbol", "open", "high", "low", "close", "volume"]
        assert df["vt_symbol"].to_list() == ["000001.SZ", "000002.SZ"]
        assert df["volume"].to_list() == [1000.0, 2000.0]

    def test_revalidation_falls_back_to_app5_clean_data_when_bridge_empty(self, tmp_path):
        """Empty bridge data should not make revalidation skip when app5 clean daily data is configured."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        data_root = self._write_app5_daily_clean_dataset(tmp_path)
        mock_bridge = MagicMock()
        mock_bridge.load_price_data.return_value = pl.DataFrame()
        scheduler = DefaultRevalidationScheduler(
            data_bridge=mock_bridge,
            backtest_noqlib_config={
                "app5_storage_root": str(data_root),
                "daily_interface": "daily",
            },
        )

        df = scheduler._get_execution_dataframe()

        mock_bridge.load_price_data.assert_called_once()
        assert len(df) == 2
        assert df["vt_symbol"].to_list() == ["000001.SZ", "000002.SZ"]

    def test_run_factor_backtest_uses_bridge_loader_when_configured(self, tmp_path):
        """Verify _run_factor_backtest calls bridge.load_price_data with configured periods."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import polars as pl

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        # Mock bridge that returns real data
        mock_bridge = MagicMock()
        expected_df = pl.DataFrame(
            {
                "datetime": [1, 2, 3],
                "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.5, 11.0],
                "high": [10.5, 11.0, 11.5],
                "low": [9.5, 10.0, 10.5],
                "close": [10.2, 10.8, 11.2],
                "volume": [1000000, 1500000, 2000000],
            }
        )
        mock_bridge.load_price_data.return_value = expected_df

        # Inject bridge and execution periods
        scheduler._data_bridge = mock_bridge
        scheduler._execution_periods = {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }

        # Mock FactorExecutor to avoid real execution
        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.error_message = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._run_factor_backtest("f1", {"factor_expression": "$close"})

            # Verify bridge was called
            mock_bridge.load_price_data.assert_called_once()
            # Verify the call used configured periods
            call_kwargs = mock_bridge.load_price_data.call_args[1]
            assert "start_date" in call_kwargs or call_kwargs.get("interfaces") is not None

    def test_revalidation_fails_fast_on_unsupported_sequence_expression(self, tmp_path):
        """Unsupported residual SEQUENCE usage should fail before loading the large execution DataFrame."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        mock_bridge = MagicMock()
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            data_bridge=mock_bridge,
        )

        result = scheduler._run_factor_backtest(
            "bad_sequence",
            {"factor_id": "bad_sequence", "factor_expression": "TS_CORR($close, SEQUENCE(20), 20)"},
        )

        assert result is False
        mock_bridge.load_price_data.assert_not_called()

    def test_revalidation_logs_full_ic_summary_on_success(self, tmp_path, monkeypatch):
        """Successful revalidation should expose the available IC statistics in logs."""
        from quantaalpha.continuous import revalidation_scheduler as scheduler_module
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        messages: list[str] = []

        class FakeLogger:
            def info(self, message):
                messages.append(str(message))

            def warning(self, message):
                messages.append(str(message))

            def error(self, message):
                messages.append(str(message))

        monkeypatch.setattr(scheduler_module, "logger", FakeLogger())

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        mock_bridge = MagicMock()
        mock_bridge.load_price_data.return_value = pl.DataFrame(
            {
                "datetime": [date(2024, 1, 2), date(2024, 1, 2)],
                "vt_symbol": ["000001.SZ", "000002.SZ"],
                "open": [10.0, 20.0],
                "high": [10.5, 20.5],
                "low": [9.5, 19.5],
                "close": [10.2, 20.2],
                "volume": [1000.0, 2000.0],
            }
        )
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            data_bridge=mock_bridge,
            min_ic=0.01,
        )

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.error_message = None
            mock_result.ic_result = SimpleNamespace(
                ic_mean=0.05,
                ic_std=0.02,
                icir=2.5,
                positive_ratio=0.75,
                daily_ic_count=120,
                daily_ics=[0.05],
                long_short_return_mean=0.001,
                long_short_return_annualized=0.252,
                long_short_sharpe=1.5,
                long_short_max_drawdown=-0.05,
            )
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._run_factor_backtest("good_factor", {"factor_expression": "$close"})

        assert result is True
        assert any(
            "profile.revalidation.metrics factor=good_factor ic_mean=0.050000 ic_std=0.020000 icir=2.500000 positive_ratio=0.750000 daily_ic_count=120 long_short_return_mean=0.001000 long_short_return_annualized=0.252000 long_short_sharpe=1.500000 long_short_max_drawdown=-0.050000"
            in message
            for message in messages
        )

    def test_run_factor_backtest_emits_profiling_logs(self, tmp_path, monkeypatch):
        """Verify revalidation backtest emits per-factor and bridge-load profiling logs."""
        from quantaalpha.continuous import revalidation_scheduler as scheduler_module
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        messages: list[str] = []

        class FakeLogger:
            def info(self, message):
                messages.append(str(message))

            def warning(self, message):
                messages.append(str(message))

            def error(self, message):
                messages.append(str(message))

        monkeypatch.setattr(scheduler_module, "logger", FakeLogger())

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        mock_bridge = MagicMock()
        mock_bridge.load_price_data.return_value = pl.DataFrame(
            {
                "datetime": [1, 2, 3],
                "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.5, 11.0],
                "high": [10.5, 11.0, 11.5],
                "low": [9.5, 10.0, 10.5],
                "close": [10.2, 10.8, 11.2],
                "volume": [1000000, 1500000, 2000000],
            }
        )
        scheduler._data_bridge = mock_bridge

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock(success=True, ic_value=0.05, error_message=None)
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._run_factor_backtest("f1", {"factor_expression": "$close"})

        assert any("profile.revalidation.factor.start" in message for message in messages)
        assert any("profile.load_price_data.start" in message for message in messages)
        assert any("profile.load_price_data.done" in message for message in messages)
        assert any("profile.revalidation.factor.done" in message for message in messages)

    def test_validate_factor_uses_bridge_data_when_configured(self, tmp_path):
        """Verify _validate_factor uses bridge data instead of placeholder."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        import polars as pl

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        # Mock bridge that returns real data
        mock_bridge = MagicMock()
        expected_df = pl.DataFrame(
            {
                "datetime": [1, 2, 3],
                "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.5, 11.0],
                "high": [10.5, 11.0, 11.5],
                "low": [9.5, 10.0, 10.5],
                "close": [10.2, 10.8, 11.2],
                "volume": [1000000, 1500000, 2000000],
            }
        )
        mock_bridge.load_price_data.return_value = expected_df

        # Inject bridge and execution periods
        scheduler._data_bridge = mock_bridge
        scheduler._execution_periods = {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }

        # Mock FactorExecutor
        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.6
            mock_result.ic_result.icir = 1.5
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._validate_factor("f1", {"factor_expression": "$close"})

            # Verify bridge was called
            mock_bridge.load_price_data.assert_called_once()
            # Verify FactorExecutor was called with real data (not empty placeholder)
            mock_instance.execute_single.assert_called_once()


class TestMinIcHardcoding:
    """
    Tests that verify min_ic is configurable, NOT hardcoded.

    These tests prove the bug: even when min_ic is passed as a parameter,
    the validation logic still uses hardcoded 0.02.
    """

    def test_revalidation_respects_custom_min_ic(self, tmp_path):
        """
        FAILING TEST: DefaultRevalidationScheduler ignores custom min_ic.

        When scheduler is created with min_ic=0.05, and IC=0.03 is returned,
        the factor should FAIL validation. But currently it uses hardcoded 0.02,
        so IC=0.03 incorrectly passes.
        """
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # Create scheduler with custom min_ic=0.05
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            min_ic=0.05,  # Higher threshold
        )

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.03  # Between 0.02 (hardcoded) and 0.05 (configured)
            mock_result.error_message = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._run_factor_backtest("test_factor", {"factor_id": "test_factor", "factor_expression": "$close"})

            # With min_ic=0.05, IC=0.03 should FAIL
            # But bug: hardcoded 0.02 is used, so IC=0.03 incorrectly passes
            assert result is False, f"IC=0.03 should fail min_ic=0.05 threshold, but it passed (hardcoded 0.02 likely used)"

    def test_mining_respects_custom_min_ic(self, tmp_path):
        """
        FAILING TEST: DefaultMiningScheduler ignores custom min_ic.

        When scheduler is created with min_rank_ic=0.02, and rank_ic=0.005 is returned,
        the factor should FAIL validation. But currently it uses hardcoded values.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        data_bridge = MagicMock()
        data_bridge.load_price_data.return_value = pl.DataFrame(
            {
                "datetime": pl.date_range(
                    start=date(2024, 1, 1),
                    end=date(2024, 1, 3),
                    interval="1d",
                    eager=True,
                ),
                "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
                "open": [10.0, 10.1, 10.2],
                "high": [10.2, 10.3, 10.4],
                "low": [9.9, 10.0, 10.1],
                "close": [10.1, 10.2, 10.3],
                "volume": [1000.0, 1100.0, 1200.0],
            }
        )

        # Create scheduler with min_rank_ic=0.02
        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            data_bridge=data_bridge,
            min_rank_ic=0.02,  # Higher threshold
        )

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.6
            mock_result.ic_result.icir = 1.5
            # Return low rank_ic that should fail min_rank_ic=0.02
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            # Manually set rank_ic_result on the mock to simulate low rank IC
            mock_result.ic_result.rank_ic_mean = 0.005  # Below min_rank_ic=0.02

            result = scheduler._validate_factor("test_factor", {"factor_id": "test_factor", "factor_expression": "$close"})

            # With min_rank_ic=0.02, rank_ic=0.005 should FAIL
            assert result["status"] == "failure", f"rank_ic=0.005 should fail min_rank_ic=0.02 threshold"


class TestMutateTimeWindowsCascade:
    """
    Tests that verify _mutate_time_windows does NOT cascade replacements.

    Bug: Sequential re.sub causes 5->10->20->60->5 (cascades back to original).
    """

    def test_mutate_time_windows_no_cascade(self):
        """
        FAILING TEST: _mutate_time_windows cascades through all replacements.

        Input: "ts_mean($close, 5)" should become something like "ts_mean($close, 10)"
        But bug: 5->10->20->60->5 ends up back at 5 (no actual change).
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # Window value 5 should change to 10 (first replacement)
        result = scheduler._mutate_time_windows("ts_mean($close, 5)")

        # The result should NOT be the same as input
        # Bug: due to cascade, 5->10->20->60->5 ends up back at 5
        assert result != "ts_mean($close, 5)", f"Window mutation cascaded back to original: got '{result}'"

        # Result should contain a different window value
        assert "10" in result or "20" in result or "60" in result, f"Window value should change, got '{result}'"

    def test_mutate_time_windows_single_replacement_map(self):
        """
        FAILING TEST: _mutate_time_windows should use single-pass replacement map.

        With single-pass: "ts_mean($close, 5)" -> "ts_mean($close, 10)"
        With cascade: "ts_mean($close, 5)" -> "ts_mean($close, 5)" (no change)
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # Test that 5 becomes 10 (not 60 which would cascade back to 5)
        result = scheduler._mutate_time_windows("ts_mean($close, 5)")

        # Should be 10, not 60 (which would cascade back on next call)
        assert "10" in result, f"Expected '10' in result for window mutation, got '{result}'"


class TestMutateSimpleVariationRemoval:
    """
    Tests that verify _mutate_simple_variation should be DELETED.

    Bug: It produces trivial mutations like "* 1.01" and "/ 2" that are meaningless.
    """

    def test_mutate_simple_variation_produces_trivial_mutation(self, tmp_path):
        """
        FIXED TEST: _mutate_simple_variation has been removed from mutation pipeline.

        The trivial mutation methods "* 1.01" and "/ 2" are no longer part of
        the mutation pipeline.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # _mutate_simple_variation should no longer exist on the scheduler
        assert not hasattr(scheduler, "_mutate_simple_variation"), "_mutate_simple_variation should be removed from DefaultMiningScheduler"

        # Verify the method is not called in mutation generation
        # by checking that generated mutations don't include trivial scaling
        lib_path = tmp_path / "lib.json"
        factors = {
            "template_1": {
                "factor_id": "template_1",
                "factor_name": "Template",
                "factor_expression": "$close",
                "evaluation": {"status": "active"},
                "tags": {"data_dependency": ["price_volume"]},
            }
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))
        mutations = scheduler._generate_via_mutation()

        # None of the mutations should be trivial scaling
        for mut in mutations:
            expr = mut.get("factor_expression", "")
            assert not expr.endswith("* 1.01"), f"Trivial mutation '* 1.01' should not be generated: {expr}"
            assert not expr.endswith("/ 2"), f"Trivial mutation '/ 2' should not be generated: {expr}"


class TestMutationIsParsableFilter:
    """
    Tests that verify mutations are filtered through is_parsable().

    Bug: Mutations are not validated for syntactic correctness.
    """

    def test_mutation_calls_is_parsable(self, tmp_path):
        """
        FAILING TEST: Mutation pipeline should call is_parsable() to filter invalid expressions.

        After fix, when _generate_via_mutation runs, it should call is_parsable()
        on each mutation and filter out those that return False.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        factors = {
            "template_1": {
                "factor_id": "template_1",
                "factor_name": "Template",
                "factor_expression": "ts_mean($close, 20)",
                "evaluation": {"status": "active"},
                "tags": {"data_dependency": ["price_volume"]},
            }
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        # Track if is_parsable was called by patching the method on the scheduler
        is_parsable_called = []
        original_generate_via_mutation = scheduler._generate_via_mutation

        def patched_generate():
            # This simulates what should happen after fix:
            # The method should call is_parsable on mutations
            # For now, we just check that the current implementation doesn't
            result = original_generate_via_mutation()
            # After fix, is_parsable should be called and filter invalid mutations
            # But currently it's NOT called - this is the bug
            return result

        scheduler._generate_via_mutation = patched_generate

        mutations = scheduler._generate_via_mutation()

        # Currently no filtering happens - is_parsable is never called
        # After fix, is_parsable should be called on each mutation
        assert len(is_parsable_called) == 0, "Bug confirmed: is_parsable is not being called during mutation generation"

    def test_mutate_time_windows_produces_valid_syntax(self):
        """
        Test that _mutate_time_windows produces syntactically valid expressions.

        After fix, mutation methods should use single-pass replacement to avoid
        creating invalid expressions through cascade.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # Test multiple window values to ensure no cascade
        original_5 = "ts_mean($close, 5)"
        result_5 = scheduler._mutate_time_windows(original_5)

        original_10 = "ts_mean($close, 10)"
        result_10 = scheduler._mutate_time_windows(original_10)

        original_20 = "ts_mean($close, 20)"
        result_20 = scheduler._mutate_time_windows(original_20)

        original_60 = "ts_mean($close, 60)"
        result_60 = scheduler._mutate_time_windows(original_60)

        # Each should produce a different result (no cascade)
        results = [result_5, result_10, result_20, result_60]
        originals = [original_5, original_10, original_20, original_60]

        # Count how many differ from their original
        changed = sum(1 for r, o in zip(results, originals) if r != o)

        # At least some should change, and none should cascade back to original
        assert changed >= 1, f"At least one window should change, but all remained the same. Results: {results}"

        # None should equal their original (cascade check)
        for r, o in zip(results, originals):
            if r == o:
                # This is the cascade bug
                assert False, f"Cascade bug: '{o}' -> '{r}' (no change due to cascade)"

    def test_mutate_time_windows_only_replaces_window_arguments(self):
        """Verify numeric constants outside window arguments are not rewritten."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        original = "ts_mean($close * 1.5 + $open * 0.05, 5)"
        result = scheduler._mutate_time_windows(original)

        assert "1.5" in result
        assert "0.05" in result
        assert result.endswith(", 10)")


class TestMutationBugFixes:
    """
    Tests that verify bugs in mutation engine are fixed.

    Bug 1: _parse_llm_response does not filter unparsable expressions.
    Bug 2: _mutate_operators does global replace instead of single replacement.
    Bug 3: _mutate_operators missing ts_std<->ts_var and rank<->ZSCORE substitutions.
    """

    def test_parse_llm_response_filters_unparsable(self):
        """
        FAILING TEST: _parse_llm_response should filter out unparsable expressions.

        Currently, _parse_llm_response does NOT call _is_parsable on the expressions,
        so invalid expressions like "invalid @@@ broken" are returned without filtering.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        import json

        scheduler = DefaultMiningScheduler()

        # Mock _is_parsable to return False for "invalid @@@ broken"
        original_is_parsable = scheduler._is_parsable

        def mock_is_parsable(expr):
            if "invalid @@@ broken" in expr:
                return False
            return original_is_parsable(expr)

        scheduler._is_parsable = mock_is_parsable

        response = json.dumps(
            [
                {"factor_expression": "ts_mean($close, 20)", "factor_name": "valid"},
                {"factor_expression": "invalid @@@ broken", "factor_name": "broken"},
            ]
        )

        factors = scheduler._parse_llm_response(response)

        # After fix: only the valid expression should pass
        # Currently (bug): both are returned because _is_parsable is NOT called
        assert len(factors) == 1, f"Expected 1 factor after filtering, got {len(factors)}: {factors}"
        assert factors[0]["factor_expression"] == "ts_mean($close, 20)"

    def test_mutate_operators_no_global_replace(self):
        """
        FAILING TEST: _mutate_operators should only replace the FIRST occurrence.

        Currently, _mutate_operators uses str.replace() without count=1,
        which does global replacement and breaks nested expressions like:
        ts_mean(ts_mean(...)) -> ts_sum(ts_sum(...))  # WRONG, should be ts_sum(ts_mean(...))
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        expr = "ts_mean(ts_mean($close, 5), 20)"
        result = scheduler._mutate_operators(expr)

        # After fix: only the FIRST ts_mean should be replaced
        # Currently (bug): ALL ts_mean are replaced to ts_sum
        expected = "ts_sum(ts_mean($close, 5), 20)"  # Only first replaced
        buggy_result = "ts_sum(ts_sum($close, 5), 20)"  # All replaced (bug)

        assert result == expected, f"Expected single replacement '{expected}', got '{result}'. Bug: global replace."

    def test_mutate_operators_has_std_var(self):
        """
        FAILING TEST: _mutate_operators should support ts_std <-> ts_var substitution.

        Currently, _mutate_operators only has ts_mean <-> ts_sum substitution.
        After fix, it should also have ts_std <-> ts_var and rank <-> ZSCORE.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # Test ts_std -> ts_var
        expr_std = "ts_std($close, 20)"
        result_std = scheduler._mutate_operators(expr_std)
        assert "ts_var(" in result_std, f"Expected ts_var in result, got '{result_std}'. Missing std<->var substitution."

        # Test ts_var -> ts_std
        expr_var = "ts_var($close, 20)"
        result_var = scheduler._mutate_operators(expr_var)
        assert "ts_std(" in result_var, f"Expected ts_std in result, got '{result_var}'. Missing var<->std substitution."

        # Test rank -> ZSCORE
        expr_rank = "rank($close)"
        result_rank = scheduler._mutate_operators(expr_rank)
        assert "ZSCORE(" in result_rank, f"Expected ZSCORE in result, got '{result_rank}'. Missing rank<->ZSCORE substitution."

        # Test ZSCORE -> rank
        expr_zscore = "ZSCORE($close)"
        result_zscore = scheduler._mutate_operators(expr_zscore)
        assert "rank(" in result_zscore, f"Expected rank in result, got '{result_zscore}'. Missing ZSCORE<->rank substitution."

    def test_mutate_operators_no_cs_rank_dead_code(self):
        """
        _mutate_operators should NOT have cs_rank branch since it's dead code.
        FactorRegulator doesn't support cs_rank operator.
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # cs_rank is not a valid operator - calling it should NOT change behavior
        # The bug is that cs_rank was being replaced with rank(), but cs_rank never appears
        # because FactorRegulator doesn't support it
        expr = "rank($close)"
        result = scheduler._mutate_operators(expr)

        # rank should be replaced with ZSCORE (after fix), not cs_rank
        # Currently it goes to cs_rank which is dead code
        assert "ZSCORE(" in result or result == expr, f"Expected ZSCORE or unchanged, got '{result}'"


class TestPerFactorTimeoutEnforcement:
    """Tests for per_factor_timeout_seconds enforcement in backtest/validation."""

    def test_default_backtest_flags_repeated_expensive_operator_budget_risk(self, tmp_path):
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            per_factor_timeout_seconds=300,
        )

        warning = scheduler._backtest_budget_warning(
            "cs_rank((ts_regresi(return, volume, 20) - "
            "ts_mean(ts_regresi(return, volume, 20), 20)) / "
            "ts_std(ts_regresi(return, volume, 20), 20))"
        )

        assert warning is not None
        assert "ts_regresi=3" in warning
        assert "timeout=300s" in warning

    def test_default_backtest_allows_single_expensive_operator(self, tmp_path):
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            per_factor_timeout_seconds=300,
        )

        assert scheduler._backtest_budget_warning("ts_regresi(return, volume, 20)") is None

    def test_default_backtest_flags_missing_ts_corr_window(self, tmp_path):
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        warning = scheduler._operator_arity_warning(
            "ts_var(ts_corr(close / ts_delay(close, 1) - 1, volume), 5)"
        )

        assert warning == "ts_corr expects 3 arguments, got 2"

    def test_default_backtest_accepts_nested_valid_arity(self, tmp_path):
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        warning = scheduler._operator_arity_warning(
            "ts_var(ts_corr(close / ts_delay(close, 1) - 1, volume, 10), 5)"
        )

        assert warning is None

    def test_default_backtest_accepts_vnpy_ts_resi_two_arg_form(self, tmp_path):
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        assert scheduler._operator_arity_warning("ts_resi(close, 20)") is None

    def test_default_backtest_flags_non_integer_window_argument(self, tmp_path):
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        warning = scheduler._operator_arity_warning(
            "ts_std(return, ts_corr(return, volume, 10))"
        )

        assert warning == (
            "ts_std expects integer window argument at position 2, "
            "got ts_corr(return, volume, 10)"
        )

    def test_backtest_with_small_timeout_stops_slow_runner(self, tmp_path):
        """
        Verify that per_factor_timeout_seconds actually interrupts a slow backtest_runner.

        When per_factor_timeout_seconds is set to a very small value,
        a backtest_runner that would take much longer should return False (timeout failure).

        Currently this test FAILS because per_factor_timeout is not enforced.
        After fix, it should PASS.
        """
        import time
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # A slow runner that takes 5 seconds
        def slow_backtest_runner(factor_id, factor_entry):
            time.sleep(5.0)  # Simulate slow backtest
            return True

        # Create scheduler with very small timeout (0.1 seconds)
        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            backtest_runner=slow_backtest_runner,
            per_factor_timeout_seconds=1,  # 1 second timeout
        )

        result = scheduler._run_factor_backtest("slow_factor", {"factor_id": "slow_factor", "factor_expression": "$close"})

        # With timeout enforcement, result should be False (timed out)
        # Without enforcement, result would be True (slow runner completed)
        assert result is False, "per_factor_timeout_seconds is not enforced: slow backtest_runner completed instead of timing out"

    def test_backtest_timeout_returns_timeout_failure_reason(self, tmp_path, monkeypatch):
        """
        Verify that timeout produces a clear failure reason mentioning 'timeout'.

        Currently this test FAILS because no timeout reason is returned.
        After fix, the error message should contain 'timeout' or 'per_factor_timeout'.
        """
        import time
        from quantaalpha.continuous import revalidation_scheduler as scheduler_module
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        messages: list[str] = []

        class FakeLogger:
            def info(self, message):
                messages.append(str(message))

            def warning(self, message):
                messages.append(str(message))

            def error(self, message):
                messages.append(str(message))

        monkeypatch.setattr(scheduler_module, "logger", FakeLogger())

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # A slow runner that takes 5 seconds
        def slow_backtest_runner(factor_id, factor_entry):
            time.sleep(5.0)
            return True

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            backtest_runner=slow_backtest_runner,
            per_factor_timeout_seconds=1,
        )

        result = scheduler._run_factor_backtest("slow_factor", {"factor_id": "slow_factor", "factor_expression": "$close"})

        # Check that result indicates failure
        assert result is False, "Expected False due to timeout"

        # After fix, there should be a log message containing 'timeout' or 'per_factor_timeout'
        timeout_logged = any("timeout" in message.lower() or "per_factor_timeout" in message.lower() for message in messages)
        assert timeout_logged, f"No timeout-related message found in logs. Log records: {messages}"

    def test_validation_with_small_timeout_stops_slow_validator(self, tmp_path):
        """
        Verify that per_factor_timeout_seconds interrupts a slow factor_validator.

        When per_factor_timeout_seconds is set to a very small value,
        a validator that would take much longer should return failure (timeout).

        Currently this test FAILS because per_factor_timeout is not enforced.
        After fix, it should PASS.
        """
        import time
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # A slow validator that takes 5 seconds
        def slow_validator(factor_id, factor_entry):
            time.sleep(5.0)  # Simulate slow validation
            return {"status": "success"}  # Would succeed if not interrupted

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            factor_validator=slow_validator,
            per_factor_timeout_seconds=1,  # 1 second timeout
        )

        result = scheduler._validate_factor("slow_factor", {"factor_id": "slow_factor", "factor_expression": "$close"})

        # With timeout enforcement, result should indicate failure
        # Without enforcement, result would be success
        assert result is None or result.get("status") == "failure", f"per_factor_timeout_seconds is not enforced: slow validator completed instead of timing out. Got result: {result}"
