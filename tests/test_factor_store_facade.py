"""
Tests for FactorStoreFacade - thin storage facade over ParquetFactorLibrary.
"""

import uuid
import shutil
from datetime import datetime
from pathlib import Path

import pytest
import pandas as pd

from quantaalpha.factors.parquet_library import ParquetFactorLibrary


@pytest.fixture
def tmp_store(tmp_path):
    """Create a temporary Parquet store directory."""
    store_dir = tmp_path / "parquet_store"
    store_dir.mkdir(parents=True, exist_ok=True)
    yield str(store_dir)
    shutil.rmtree(store_dir, ignore_errors=True)


def _make_factor_entry(factor_id=None, factor_name="test_factor", factor_expression="STD($close, 20)",
                     expression_hash=None, sequence=1, op="upsert"):
    """Helper to create a factor entry dict."""
    fid = factor_id or f"factor_{uuid.uuid4().hex[:8]}"
    expr_hash = expression_hash or f"hash_{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now().isoformat()
    return {
        "factor_id": fid,
        "factor_name": factor_name,
        "factor_expression": factor_expression,
        "factor_expression_normalized": factor_expression,
        "expression_hash": expr_hash,
        "evaluation_status": "active",
        "created_at": now_iso,
        "updated_at": now_iso,
        "sequence": sequence,
        "op": op,
        "tags_json": "[]",
        "metadata_json": "{}",
        "backtest_results_json": "{}",
    }


class TestFactorStoreFacadeReadWrite:
    """Test FactorStoreFacade basic read/write operations."""

    def test_facade_reads_effective_factors_from_compacted_and_delta(self, tmp_store):
        """Facade writes at least two complete schema entries, reads them back as a pandas DataFrame,
        returns a non-empty factor zoo frame, and the temporary store contains no .json file."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        entry1 = _make_factor_entry(
            factor_name="alpha_001",
            factor_expression="STD($close, 20)",
            expression_hash="hash_a",
            sequence=1000,
        )
        entry2 = _make_factor_entry(
            factor_name="alpha_002",
            factor_expression="MEAN($volume, 10)",
            expression_hash="hash_b",
            sequence=1001,
        )

        facade.write_factor(entry1)
        facade.write_factor(entry2)

        # Read effective factors - should return pandas DataFrame
        df = facade.read_effective_factors()
        assert isinstance(df, pd.DataFrame), "read_effective_factors should return pandas DataFrame"
        assert len(df) == 2, f"Should read 2 factors, got {len(df)}"
        assert "factor_name" in df.columns
        assert "factor_expression" in df.columns

        # Read factor zoo frame
        zoo = facade.to_factor_zoo_frame()
        assert isinstance(zoo, pd.DataFrame), "to_factor_zoo_frame should return pandas DataFrame"
        assert not zoo.empty, "Factor zoo frame should not be empty"
        assert "factor_name" in zoo.columns
        assert "factor_expression" in zoo.columns

        # Assert no JSON files anywhere in store
        store_path = Path(tmp_store)
        json_files = list(store_path.rglob("*.json"))
        assert len(json_files) == 0, f"No JSON files should exist in store, found: {json_files}"


class TestFactorStoreFacadeCompact:
    """Test FactorStoreFacade delta_file_count and compact."""

    def test_facade_delta_file_count_and_compact(self, tmp_store):
        """Facade reports delta file count before compact, compacts, then
        compacted/factors.parquet exists and effective factor count is preserved."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        entry1 = _make_factor_entry(
            factor_name="compact_001",
            factor_expression="STD($close, 20)",
            expression_hash="hash_c",
            sequence=2000,
        )
        entry2 = _make_factor_entry(
            factor_name="compact_002",
            factor_expression="MEAN($volume, 10)",
            expression_hash="hash_d",
            sequence=2001,
        )

        facade.write_factor(entry1)
        facade.write_factor(entry2)

        # Delta file count before compact
        delta_count_before = facade.delta_file_count()
        assert delta_count_before == 2, f"Should have 2 delta files, got {delta_count_before}"

        # Compact
        facade.compact()

        # Compacted file exists
        compacted_path = Path(tmp_store) / "compacted" / "factors.parquet"
        assert compacted_path.exists(), "compacted/factors.parquet should exist after compact"

        # Effective factor count preserved
        df = facade.read_effective_factors()
        assert len(df) == 2, f"Effective factor count should be preserved after compact, got {len(df)}"


class TestFactorStoreFacadeEncapsulation:
    """Test that FactorStoreFacade does not expose business methods."""

    def test_facade_does_not_expose_business_methods(self, tmp_store):
        """Facade does not expose check_redundancy, select_revalidation_candidates,
        or build_fewshot_context_records."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        assert not hasattr(facade, "check_redundancy"), "Facade should not expose check_redundancy"
        assert not hasattr(facade, "select_revalidation_candidates"), "Facade should not expose select_revalidation_candidates"
        assert not hasattr(facade, "build_fewshot_context_records"), "Facade should not expose build_fewshot_context_records"
