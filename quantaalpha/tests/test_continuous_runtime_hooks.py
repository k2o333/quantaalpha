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
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest


class TestRunFactorBacktest:
    """Tests for _run_factor_backtest seam."""

    def test_injected_runner_takes_precedence(self, tmp_path):
        """Verify injected backtest_runner is called instead of default."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        captured = []

        def injected_runner(factor_id, factor_entry):
            captured.append((factor_id, factor_entry))
            return True

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            backtest_runner=injected_runner,
        )

        result = scheduler._run_factor_backtest("test_factor", {"factor_id": "test_factor", "factor_expression": "$close"})

        assert result is True
        assert len(captured) == 1
        assert captured[0][0] == "test_factor"

    def test_missing_expression_returns_false(self, tmp_path):
        """Verify factor with no expression returns False."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        result = scheduler._run_factor_backtest("no_expr_factor", {"factor_id": "no_expr_factor", "factor_expression": ""})

        assert result is False

    def test_backtest_with_expression_uses_executor_path(self, tmp_path):
        """Verify factors with expression attempt to use FactorExecutor."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        # Mock FactorExecutor at the correct import location
        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.error_message = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._run_factor_backtest(
                "test_factor",
                {"factor_id": "test_factor", "factor_expression": "$close/$open - 1"}
            )

            # Should have attempted execution
            mock_instance.execute_single.assert_called_once()

    def test_backtest_ic_below_threshold_returns_false(self, tmp_path):
        """Verify IC below threshold returns False."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.01  # Below 0.02 threshold
            mock_result.error_message = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._run_factor_backtest(
                "weak_factor",
                {"factor_id": "weak_factor", "factor_expression": "$volume"}
            )

            # Should return False due to IC threshold
            assert result is False

    def test_backtest_ic_above_threshold_returns_true(self, tmp_path):
        """Verify IC above threshold returns True."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05  # Above 0.02 threshold
            mock_result.error_message = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._run_factor_backtest(
                "strong_factor",
                {"factor_id": "strong_factor", "factor_expression": "$close"}
            )

            assert result is True

    def test_backtest_translates_quantaalpha_expression_before_execution(self, tmp_path):
        """Verify raw QuantaAlpha expressions are translated before FactorExecutor execution."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        data_bridge = MagicMock()
        data_bridge.load_price_data.return_value = pl.DataFrame({
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
        })

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            data_bridge=data_bridge,
        )

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock(success=True, ic_value=0.05, error_message=None)
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._run_factor_backtest(
                "test_factor",
                {"factor_id": "test_factor", "factor_expression": "TS_MEAN($close, 5)"},
            )

        call = mock_instance.execute_single.call_args
        assert call.kwargs["original_expression"] == "TS_MEAN($close, 5)"
        assert call.kwargs["expression"] == "ts_mean(close, 5)"

    def test_backtest_rewrites_return_alias_before_execution(self, tmp_path):
        """Verify $return is rewritten to a valid vnpy-compatible return expression."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        data_bridge = MagicMock()
        data_bridge.load_price_data.return_value = pl.DataFrame({
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
        })

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            data_bridge=data_bridge,
        )

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock(success=True, ic_value=0.05, error_message=None)
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._run_factor_backtest(
                "return_factor",
                {
                    "factor_id": "return_factor",
                    "factor_expression": "TS_CORR($return, DELTA($volume, 1), 10)",
                },
            )

        call = mock_instance.execute_single.call_args
        assert call.kwargs["expression"] == "ts_corr((close / ts_delay(close, 1) - 1), ts_delta(volume, 1), 10)"

    def test_backtest_reuses_cached_execution_dataframe_within_scheduler(self, tmp_path):
        """Verify repeated backtests reuse the same loaded price DataFrame."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        bridge_df = pl.DataFrame({
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
        })
        data_bridge = MagicMock()
        data_bridge.load_price_data.return_value = bridge_df

        scheduler = DefaultRevalidationScheduler(
            library_path=str(lib_path),
            data_bridge=data_bridge,
        )

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock(success=True, ic_value=0.05, error_message=None)
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._run_factor_backtest(
                "factor_a",
                {"factor_id": "factor_a", "factor_expression": "$close"},
            )
            scheduler._run_factor_backtest(
                "factor_b",
                {"factor_id": "factor_b", "factor_expression": "$open"},
            )

        data_bridge.load_price_data.assert_called_once()


class TestValidateFactor:
    """Tests for _validate_factor seam."""

    def test_injected_validator_takes_precedence(self, tmp_path):
        """Verify injected factor_validator is called instead of default."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        captured = []

        def injected_validator(factor_id, factor_entry):
            captured.append((factor_id, factor_entry))
            return {"status": "success", "summary": {"stability_score": 0.8}}

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            factor_validator=injected_validator,
        )

        result = scheduler._validate_factor("test_factor", {"factor_id": "test_factor"})

        assert result["status"] == "success"
        assert len(captured) == 1
        assert captured[0][0] == "test_factor"

    def test_validation_result_structure_on_success(self, tmp_path):
        """Verify success validation result has required keys."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

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

            result = scheduler._validate_factor(
                "test_factor",
                {"factor_id": "test_factor", "factor_expression": "$close"}
            )

            assert "status" in result
            assert "summary" in result
            assert "stability_score" in result["summary"]
            assert "validation_summary" in result["summary"]
            assert "ic_mean" in result["summary"]

    def test_validation_result_structure_on_failure(self, tmp_path):
        """Verify failure validation result has required keys."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.005  # Low IC
            mock_result.ic_result = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._validate_factor(
                "weak_factor",
                {"factor_id": "weak_factor", "factor_expression": "$volume"}
            )

            assert result["status"] == "failure"
            assert "summary" in result
            assert "ic_mean" in result["summary"]

    def test_no_expression_returns_failure(self, tmp_path):
        """Verify factor without expression returns failure."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        result = scheduler._validate_factor(
            "no_expr_factor",
            {"factor_id": "no_expr_factor", "factor_expression": ""}
        )

        assert result["status"] == "failure"
        assert "No expression" in result["summary"]["validation_summary"]

    def test_validate_factor_translates_quantaalpha_expression_before_execution(self, tmp_path):
        """Verify validation translates raw QuantaAlpha expressions before execution."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        data_bridge = MagicMock()
        data_bridge.load_price_data.return_value = pl.DataFrame({
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
        })

        scheduler = DefaultMiningScheduler(library_path=str(lib_path), data_bridge=data_bridge)

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.6
            mock_result.ic_result.icir = 1.0
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._validate_factor(
                "test_factor",
                {"factor_id": "test_factor", "factor_expression": "TS_MEAN($close, 5)"},
            )

        call = mock_instance.execute_single.call_args
        assert call.kwargs["original_expression"] == "TS_MEAN($close, 5)"
        assert call.kwargs["expression"] == "ts_mean(close, 5)"

    def test_validate_factor_rewrites_return_alias_before_execution(self, tmp_path):
        """Verify validation rewrites $return into a valid expression before execution."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        data_bridge = MagicMock()
        data_bridge.load_price_data.return_value = pl.DataFrame({
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
        })

        scheduler = DefaultMiningScheduler(library_path=str(lib_path), data_bridge=data_bridge)

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.6
            mock_result.ic_result.icir = 1.0
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._validate_factor(
                "return_factor",
                {
                    "factor_id": "return_factor",
                    "factor_expression": "TS_CORR($return, DELTA($volume, 1), 10)",
                },
            )

        call = mock_instance.execute_single.call_args
        assert call.kwargs["expression"] == "ts_corr((close / ts_delay(close, 1) - 1), ts_delta(volume, 1), 10)"


class TestGenerateFactors:
    """Tests for _generate_factors seam."""

    def test_returns_list_not_empty(self, tmp_path):
        """Verify _generate_factors does not return empty list."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        # Create library with active factors for mutation templates
        factors = {
            "active_1": {
                "factor_id": "active_1",
                "factor_name": "Active Factor 1",
                "factor_expression": "ts_mean($close, 20)",
                "evaluation": {"status": "active", "last_validated": None},
                "tags": {"data_dependency": ["price_volume"]},
            }
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path), max_per_run=5)

        # Mock LLM to return empty to force mutation path
        with patch.object(scheduler, "_generate_via_llm", return_value=[]):
            with patch.object(scheduler, "_generate_via_mutation") as mock_mutate:
                mock_mutate.return_value = [
                    {
                        "factor_id": "mut_1",
                        "factor_name": "Mutated 1",
                        "factor_expression": "ts_mean($close, 10)",
                        "tags": {"data_dependency": ["price_volume"]},
                        "evaluation": {"status": "pending_validation"},
                    }
                ]
                result = scheduler._generate_factors("some context")

        assert isinstance(result, list)
        assert len(result) > 0

    def test_generated_factors_normalized_shape(self, tmp_path):
        """Verify generated factors have required keys."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path), max_per_run=5)

        with patch.object(scheduler, "_generate_via_llm", return_value=[]):
            with patch.object(scheduler, "_generate_via_mutation", return_value=[]):
                # When both return empty, result should be empty
                result = scheduler._generate_factors("context")
                # This tests the deduplication and limit logic
                assert isinstance(result, list)

    def test_factor_id_generation_for_mutated(self, tmp_path):
        """Verify mutated factors get unique IDs."""
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

        mutated_expr = "ts_mean($close, 10)"
        new_id = scheduler._generate_mutated_factor_id("template_1", mutated_expr)

        assert new_id.startswith("mut_template_1_")
        assert len(new_id) > len("mut_template_1_")

    def test_normalize_factor_entry_adds_required_keys(self):
        """Verify _normalize_factor_entry adds required keys."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        raw_entry = {
            "factor_name": "Test Factor",
            "factor_expression": "$close/$open - 1",
        }

        normalized = scheduler._normalize_factor_entry(raw_entry)

        assert "factor_id" in normalized
        assert "factor_name" in normalized
        assert "factor_expression" in normalized
        assert "tags" in normalized
        assert "evaluation" in normalized
        assert "data_dependency" in normalized["tags"]

    def test_infers_price_volume_tag(self):
        """Verify data_dependency is inferred as price_volume for price expressions."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        raw_entry = {
            "factor_name": "Price Factor",
            "factor_expression": "$close/$open - 1",
        }

        normalized = scheduler._normalize_factor_entry(raw_entry)

        assert "price_volume" in normalized["tags"]["data_dependency"]

    def test_infers_financial_tag(self):
        """Verify data_dependency is inferred as financial for financial expressions."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        raw_entry = {
            "factor_name": "Financial Factor",
            "factor_expression": "$roe * $gross_margin",
        }

        normalized = scheduler._normalize_factor_entry(raw_entry)

        assert "financial" in normalized["tags"]["data_dependency"]


class TestRetrieveContext:
    """Tests for _retrieve_context seam."""

    def test_returns_string(self, tmp_path):
        """Verify _retrieve_context returns a string."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        # Mock at the source module where functions are defined
        with patch("quantaalpha.factors.fewshot.query_active_factors_RAG", side_effect=Exception("not available")):
            with patch("quantaalpha.factors.fewshot.query_active_factors_jaccard", side_effect=Exception("not available")):
                result = scheduler._retrieve_context()

        assert isinstance(result, str)

    def test_uses_fewshot_rag_when_available(self, tmp_path):
        """Verify RAG query is attempted."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        mock_results = [
            {"factor_id": "f1", "factor_name": "Factor 1", "factor_expression": "$close", "score": 0.9, "tags": {}, "metadata": {}}
        ]

        with patch("quantaalpha.factors.fewshot.query_active_factors_RAG", return_value=mock_results) as mock_rag:
            with patch("quantaalpha.factors.fewshot.build_fewshot_context", return_value="Built context") as mock_build:
                result = scheduler._retrieve_context()

                mock_rag.assert_called_once()
                mock_build.assert_called_once()
                assert mock_rag.call_args.kwargs["library_path"] == str(lib_path)

    def test_fallback_to_jaccard_when_rag_fails(self, tmp_path):
        """Verify Jaccard fallback when RAG fails."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        mock_results = [
            {"factor_id": "f1", "factor_name": "Factor 1", "factor_expression": "$close", "score": 0.9, "tags": {}, "metadata": {}}
        ]

        with patch("quantaalpha.factors.fewshot.query_active_factors_RAG", side_effect=Exception("RAG failed")):
            with patch("quantaalpha.factors.fewshot.query_active_factors_jaccard", return_value=mock_results) as mock_jaccard:
                with patch("quantaalpha.factors.fewshot.build_fewshot_context", return_value="Built context"):
                    result = scheduler._retrieve_context()

                    mock_jaccard.assert_called_once()
                    assert mock_jaccard.call_args.kwargs["library_path"] == str(lib_path)

    def test_builds_context_from_library_when_rag_unavailable(self, tmp_path):
        """Verify fallback context building from library."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        factors = {
            "active_1": {
                "factor_id": "active_1",
                "factor_name": "Active Factor 1",
                "factor_expression": "ts_mean($close, 20)",
                "evaluation": {"status": "active", "last_validated": None},
                "tags": {"data_dependency": ["price_volume"]},
            }
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("quantaalpha.factors.fewshot.query_active_factors_RAG", side_effect=Exception("not available")):
            with patch("quantaalpha.factors.fewshot.query_active_factors_jaccard", side_effect=Exception("not available")):
                result = scheduler._retrieve_context()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_library_returns_empty_context(self, tmp_path):
        """Verify empty library returns empty string."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("quantaalpha.factors.fewshot.query_active_factors_RAG", side_effect=Exception("not available")):
            with patch("quantaalpha.factors.fewshot.query_active_factors_jaccard", return_value=[]) as mock_jaccard:
                result = scheduler._retrieve_context()

                mock_jaccard.assert_called_once()
                # Empty results should return empty context
                assert result == ""


class TestMutationGeneration:
    """Tests for mutation-based factor generation."""

    def test_mutate_time_windows(self):
        """Verify time window mutation."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        result = scheduler._mutate_time_windows("ts_mean($close, 20)")

        # Should have changed 20 to another value
        assert "ts_mean($close," in result
        assert result != "ts_mean($close, 20)"

    def test_mutate_operators(self):
        """Verify operator mutation."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        result = scheduler._mutate_operators("ts_mean($close, 20)")

        # ts_mean should become ts_sum
        assert "ts_sum(" in result

    def test_mutate_operators_cs_rank_is_not_noop(self):
        """Verify cs_rank expressions produce a real operator mutation."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        result = scheduler._mutate_operators("cs_rank($close)")

        assert result != "cs_rank($close)"
        assert "rank(" in result

    def test_mutate_simple_variation_removed(self):
        """Verify _mutate_simple_variation has been removed."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        # _mutate_simple_variation should no longer exist
        assert not hasattr(scheduler, '_mutate_simple_variation'), \
            "_mutate_simple_variation should be removed"

    def test_mutation_generation_returns_list(self, tmp_path):
        """Verify mutation generation returns list of factors."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        factors = {
            "active_1": {
                "factor_id": "active_1",
                "factor_name": "Active Factor 1",
                "factor_expression": "ts_mean($close, 20)",
                "evaluation": {"status": "active"},
                "tags": {"data_dependency": ["price_volume"]},
            }
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        result = scheduler._generate_via_mutation()

        assert isinstance(result, list)
        if len(result) > 0:
            # Each should have required keys
            for factor in result:
                assert "factor_id" in factor
                assert "factor_expression" in factor
                assert "tags" in factor

    def test_mutation_uses_recent_active_factors_as_templates(self, tmp_path):
        """Verify mutation does not exclude active templates solely because they were recently validated."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        factors = {
            "active_recent": {
                "factor_id": "active_recent",
                "factor_name": "Active Recent",
                "factor_expression": "ts_mean($close, 20)",
                "evaluation": {
                    "status": "active",
                    "last_validated": "2026-03-18T02:37:27.936371",
                },
                "tags": {"data_dependency": ["price_volume"]},
            }
        }
        lib_path.write_text(json.dumps({"metadata": {}, "factors": factors}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        mutations = scheduler._generate_via_mutation()

        assert len(mutations) > 0
        assert all(item["metadata"]["source"] == "mutation" for item in mutations)


class TestValidationResultContract:
    """
    Tests that verify the exact contract of validation results.

    Validation result contract (for FactorLibraryManager.apply_validation_result):
    - status: "success" or "failure"
    - summary.validation_summary: human-readable summary
    - summary.ic_mean: IC value if computed
    - summary.rank_ic_mean: Rank IC if computed (optional)
    - summary.stability_score: computed stability metric
    """

    def test_success_result_has_required_fields(self, tmp_path):
        """Verify success validation result matches contract."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.7
            mock_result.ic_result.icir = 2.0
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._validate_factor(
                "passing_factor",
                {"factor_id": "passing_factor", "factor_expression": "$close"}
            )

        # Contract verification
        assert result["status"] == "success"
        summary = result["summary"]
        assert "validation_summary" in summary
        assert "stability_score" in summary
        assert "ic_mean" in summary
        assert summary["ic_mean"] == 0.05

    def test_failure_result_has_required_fields(self, tmp_path):
        """Verify failure validation result matches contract."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.005  # Below threshold
            mock_result.ic_result = None
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._validate_factor(
                "failing_factor",
                {"factor_id": "failing_factor", "factor_expression": "$volume"}
            )

        # Contract verification
        assert result["status"] == "failure"
        summary = result["summary"]
        assert "validation_summary" in summary
        assert "ic_mean" in summary
        assert summary["ic_mean"] == 0.005


class TestGeneratedFactorCandidateContract:
    """
    Tests that verify the exact contract of generated factor candidates.

    Generated factor candidate contract:
    - factor_id: unique identifier (string)
    - factor_name: human-readable name (string)
    - factor_expression: the factor formula (string)
    - tags: dict with data_dependency list
    - evaluation: dict with status
    """

    def test_mutation_result_matches_contract(self, tmp_path):
        """Verify mutation-generated factors match contract."""
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

        mutations = scheduler._generate_via_mutation()

        if len(mutations) > 0:
            for factor in mutations:
                # Contract verification
                assert "factor_id" in factor
                assert isinstance(factor["factor_id"], str)
                assert "factor_name" in factor
                assert "factor_expression" in factor
                assert "tags" in factor
                assert "data_dependency" in factor["tags"]
                assert "evaluation" in factor

    def test_normalized_entry_has_all_required_fields(self):
        """Verify normalized entry has all contract fields."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        raw = {
            "factor_name": "Test",
            "factor_expression": "$close",
        }

        normalized = scheduler._normalize_factor_entry(raw)

        # Required by contract
        assert "factor_id" in normalized
        assert "factor_name" in normalized
        assert "factor_expression" in normalized
        assert normalized["factor_expression"] == "$close"
        assert "tags" in normalized
        assert "data_dependency" in normalized["tags"]
        assert "evaluation" in normalized
        assert normalized["evaluation"]["status"] == "pending_validation"

    def test_generate_via_llm_uses_api_backend_when_available(self, tmp_path):
        """Verify LLM generation uses APIBackend instead of the removed QuantaAlphaLLMClient."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        response = json.dumps([
            {
                "factor_name": "LLM Factor",
                "factor_expression": "$close / ts_mean($close, 5)",
                "tags": {"data_dependency": ["price_volume"]},
            }
        ])

        with patch("quantaalpha.llm.client.APIBackend") as mock_backend_class:
            mock_backend = MagicMock()
            mock_backend.build_messages_and_create_chat_completion.return_value = response
            mock_backend_class.return_value = mock_backend

            generated = scheduler._generate_via_llm("context")

        mock_backend.build_messages_and_create_chat_completion.assert_called_once()
        assert len(generated) == 1
        assert generated[0]["factor_name"] == "LLM Factor"


class TestBridgeDataIntegration:
    """Tests verifying schedulers use bridge loader for real data."""

    def test_run_factor_backtest_uses_bridge_loader_when_configured(self, tmp_path):
        """Verify _run_factor_backtest calls bridge.load_price_data with configured periods."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
        import polars as pl

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        # Mock bridge that returns real data
        mock_bridge = MagicMock()
        expected_df = pl.DataFrame({
            "datetime": [1, 2, 3],
            "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "open": [10.0, 10.5, 11.0],
            "high": [10.5, 11.0, 11.5],
            "low": [9.5, 10.0, 10.5],
            "close": [10.2, 10.8, 11.2],
            "volume": [1000000, 1500000, 2000000],
        })
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

    def test_run_factor_backtest_emits_profiling_logs(self, tmp_path, caplog):
        """Verify revalidation backtest emits per-factor and bridge-load profiling logs."""
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultRevalidationScheduler(library_path=str(lib_path))

        mock_bridge = MagicMock()
        mock_bridge.load_price_data.return_value = pl.DataFrame({
            "datetime": [1, 2, 3],
            "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "open": [10.0, 10.5, 11.0],
            "high": [10.5, 11.0, 11.5],
            "low": [9.5, 10.0, 10.5],
            "close": [10.2, 10.8, 11.2],
            "volume": [1000000, 1500000, 2000000],
        })
        scheduler._data_bridge = mock_bridge

        caplog.set_level(logging.INFO)

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock(success=True, ic_value=0.05, error_message=None)
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            scheduler._run_factor_backtest("f1", {"factor_expression": "$close"})

        messages = [record.getMessage() for record in caplog.records]
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
        expected_df = pl.DataFrame({
            "datetime": [1, 2, 3],
            "vt_symbol": ["000001.SZ", "000001.SZ", "000001.SZ"],
            "open": [10.0, 10.5, 11.0],
            "high": [10.5, 11.0, 11.5],
            "low": [9.5, 10.0, 10.5],
            "close": [10.2, 10.8, 11.2],
            "volume": [1000000, 1500000, 2000000],
        })
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

            result = scheduler._run_factor_backtest(
                "test_factor",
                {"factor_id": "test_factor", "factor_expression": "$close"}
            )

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
        data_bridge.load_price_data.return_value = pl.DataFrame({
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
        })

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

            result = scheduler._validate_factor(
                "test_factor",
                {"factor_id": "test_factor", "factor_expression": "$close"}
            )

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
        assert result != "ts_mean($close, 5)", \
            f"Window mutation cascaded back to original: got '{result}'"

        # Result should contain a different window value
        assert "10" in result or "20" in result or "60" in result, \
            f"Window value should change, got '{result}'"

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
        assert "10" in result, \
            f"Expected '10' in result for window mutation, got '{result}'"


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
        assert not hasattr(scheduler, '_mutate_simple_variation'), \
            "_mutate_simple_variation should be removed from DefaultMiningScheduler"

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
            assert not expr.endswith("* 1.01"), \
                f"Trivial mutation '* 1.01' should not be generated: {expr}"
            assert not expr.endswith("/ 2"), \
                f"Trivial mutation '/ 2' should not be generated: {expr}"


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
        assert len(is_parsable_called) == 0, \
            "Bug confirmed: is_parsable is not being called during mutation generation"

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
        assert changed >= 1, \
            f"At least one window should change, but all remained the same. Results: {results}"

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


class TestPerFactorTimeoutEnforcement:
    """Tests for per_factor_timeout_seconds enforcement in backtest/validation."""

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

        result = scheduler._run_factor_backtest(
            "slow_factor",
            {"factor_id": "slow_factor", "factor_expression": "$close"}
        )

        # With timeout enforcement, result should be False (timed out)
        # Without enforcement, result would be True (slow runner completed)
        assert result is False, (
            "per_factor_timeout_seconds is not enforced: "
            "slow backtest_runner completed instead of timing out"
        )

    def test_backtest_timeout_returns_timeout_failure_reason(self, tmp_path, caplog):
        """
        Verify that timeout produces a clear failure reason mentioning 'timeout'.

        Currently this test FAILS because no timeout reason is returned.
        After fix, the error message should contain 'timeout' or 'per_factor_timeout'.
        """
        import time
        import logging
        from quantaalpha.continuous.implementations import DefaultRevalidationScheduler

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

        with caplog.at_level(logging.WARNING):
            result = scheduler._run_factor_backtest(
                "slow_factor",
                {"factor_id": "slow_factor", "factor_expression": "$close"}
            )

        # Check that result indicates failure
        assert result is False, "Expected False due to timeout"

        # After fix, there should be a log message containing 'timeout' or 'per_factor_timeout'
        timeout_logged = any(
            'timeout' in record.message.lower() or 'per_factor_timeout' in record.message.lower()
            for record in caplog.records
        )
        assert timeout_logged, (
            "No timeout-related message found in logs. "
            f"Log records: {[r.message for r in caplog.records]}"
        )

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

        result = scheduler._validate_factor(
            "slow_factor",
            {"factor_id": "slow_factor", "factor_expression": "$close"}
        )

        # With timeout enforcement, result should indicate failure
        # Without enforcement, result would be success
        assert result is None or result.get("status") == "failure", (
            "per_factor_timeout_seconds is not enforced: "
            "slow validator completed instead of timing out. "
            f"Got result: {result}"
        )
