"""
Tests for FactorRegulator with Parquet factor zoo.
"""

import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import uuid

import pytest
import polars as pl
import pandas as pd


@pytest.fixture
def tmp_parquet_store():
    """Create a temporary Parquet factor store."""
    tmpdir = tempfile.mkdtemp(prefix="parquet_zoo_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _write_parquet_factor(store_path, factor_name, factor_expression, sequence=1, expression_hash=None):
    """Helper to write a factor to a Parquet store."""
    from quantaalpha.factors.parquet_library import ParquetFactorLibrary
    library = ParquetFactorLibrary(store_path=store_path)
    fid = f"factor_{uuid.uuid4().hex[:8]}"
    expr_hash = expression_hash or f"hash_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now().isoformat()
    entry = {
        "factor_id": fid,
        "factor_name": factor_name,
        "factor_expression": factor_expression,
        "factor_expression_normalized": factor_expression,
        "expression_hash": expr_hash,
        "evaluation_status": "active",
        "created_at": now_iso,
        "updated_at": now_iso,
        "sequence": sequence,
        "op": "upsert",
        "tags_json": "[]",
        "metadata_json": "{}",
        "backtest_results_json": "{}",
    }
    library.write_factor_delta(entry)
    return entry


class TestFactorRegulatorParquetZoo:
    """Test FactorRegulator loading Parquet factor zoo."""

    def test_factor_regulator_loads_parquet_factor_zoo(self, tmp_parquet_store):
        """FactorRegulator can load a test Parquet store and has non-empty alphazoo
        with factor_name and factor_expression."""
        _write_parquet_factor(
            tmp_parquet_store,
            factor_name="test_alpha_001",
            factor_expression="STD($close, 20)",
        )

        # Import here to avoid circular import at module load time
        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
        regulator = FactorRegulator(factor_zoo_path=tmp_parquet_store)
        assert regulator.alphazoo is not None, "alphazoo should not be None"
        assert not regulator.alphazoo.empty, "alphazoo should not be empty after loading Parquet store"
        assert "factor_name" in regulator.alphazoo.columns, "alphazoo should have factor_name column"
        assert "factor_expression" in regulator.alphazoo.columns, "alphazoo should have factor_expression column"
        assert regulator.alphazoo["factor_name"].iloc[0] == "test_alpha_001"

    def test_factor_regulator_parquet_duplicate_size_nonzero(self, tmp_parquet_store):
        """Evaluating an expression already present in the Parquet store returns ok is True
        and eval_dict["duplicated_subtree_size"] > 0."""
        existing_expression = "STD($close, 20)"
        _write_parquet_factor(
            tmp_parquet_store,
            factor_name="existing_factor",
            factor_expression=existing_expression,
        )

        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
        regulator = FactorRegulator(factor_zoo_path=tmp_parquet_store)
        ok, eval_dict = regulator.evaluate(existing_expression)

        assert ok is True, "evaluate should return ok=True"
        assert eval_dict is not None, "eval_dict should not be None"
        assert eval_dict["duplicated_subtree_size"] > 0, (
            f"duplicated_subtree_size should be > 0 for existing expression, got {eval_dict['duplicated_subtree_size']}"
        )

    def test_match_alphazoo_uses_explicit_factor_expression_column(self, tmp_parquet_store):
        """A DataFrame with columns ordered as factor_expression, then factor_name,
        still returns a nonzero match."""
        existing_expression = "MEAN($volume, 10)"
        _write_parquet_factor(
            tmp_parquet_store,
            factor_name="volume_factor",
            factor_expression=existing_expression,
        )

        from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
        regulator = FactorRegulator(factor_zoo_path=tmp_parquet_store)

        df = regulator.alphazoo
        cols = list(df.columns)
        assert "factor_expression" in cols, "factor_expression column must exist"

        from quantaalpha.factors.coder.factor_ast import match_alphazoo

        max_size, matched_subtree, matched_alpha = match_alphazoo(existing_expression, df)
        assert max_size > 0, f"match_alphazoo should find a match (size > 0), got {max_size}"
