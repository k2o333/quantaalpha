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

    def test_facade_compact_honors_archive_retention(self, tmp_store):
        """Compaction keeps only the newest archive_retention archive directories."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        store_path = Path(tmp_store)
        archive_dir = store_path / "archive"
        (archive_dir / "compact_at=20000101_000001").mkdir(parents=True)
        (archive_dir / "compact_at=20000101_000002").mkdir(parents=True)

        facade = FactorStoreFacade(store_path=tmp_store)
        facade.write_factor(
            _make_factor_entry(
                factor_name="retention_factor",
                factor_expression="STD($close, 20)",
                expression_hash="retention_hash",
                sequence=3000,
            )
        )

        facade.compact(archive_retention=1)

        archives = sorted(p.name for p in archive_dir.iterdir() if p.is_dir())
        assert len(archives) == 1
        assert archives[0].startswith("compact_at=")


class TestFactorStoreFacadeStatusAndDelete:
    """Test append-only status updates and tombstone deletes."""

    def test_facade_status_update_writes_parquet_event(self, tmp_store):
        """A validation status update writes a new Parquet delta event and keeps only the latest status effective."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)
        entry = _make_factor_entry(
            factor_id="status_factor",
            factor_name="status_factor",
            factor_expression="STD($close, 20)",
            expression_hash="status_hash",
            sequence=10,
        )
        facade.write_factor(entry)

        updated = facade.write_status_update(
            entry,
            {
                "status": "failure",
                "summary": {
                    "stability_score": 0.1,
                    "validation_summary": "failed regression",
                },
            },
            sequence=11,
        )

        records = facade.read_effective_factor_records()
        assert len(records) == 1
        assert updated["evaluation"]["status"] == "degraded"
        assert records[0]["evaluation_status"] == "degraded"
        assert records[0]["sequence"] == 11
        assert not list(Path(tmp_store).rglob("*.json"))

    def test_facade_delete_factor_writes_tombstone(self, tmp_store):
        """Deleting a factor writes an append-only tombstone and removes it from effective reads."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)
        entry = _make_factor_entry(
            factor_id="delete_factor",
            factor_name="delete_factor",
            factor_expression="MEAN($volume, 10)",
            expression_hash="delete_hash",
            sequence=20,
        )
        facade.write_factor(entry)

        facade.delete_factor("delete_factor", sequence=21)

        assert facade.read_effective_factor_records() == []
        assert facade.delta_file_count() == 2
        assert not list(Path(tmp_store).rglob("*.json"))


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
