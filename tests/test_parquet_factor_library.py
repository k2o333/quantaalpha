"""
Tests for ParquetFactorLibrary: write, read, compact, and no-JSON guarantees.
"""

import os
import tempfile
import shutil
import uuid
from pathlib import Path
from datetime import datetime

import pytest
import polars as pl

from quantaalpha.factors.parquet_library import ParquetFactorLibrary


@pytest.fixture
def tmp_store():
    """Create a temporary Parquet store directory."""
    tmpdir = tempfile.mkdtemp(prefix="parquet_store_test_")
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


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


class TestParquetFactorLibraryWrite:
    """Test write_factor_delta and atomic publication."""

    def test_write_factor_delta_creates_only_parquet_delta(self, tmp_store):
        """Writing one factor creates a .parquet file under delta/, creates no .json factor library file,
        and leaves no .tmp file in delta/."""
        library = ParquetFactorLibrary(store_path=tmp_store)
        entry = _make_factor_entry(factor_name="alpha_001", factor_expression="STD($close, 20)")
        library.write_factor_delta(entry)

        delta_dir = Path(tmp_store) / "delta"
        assert delta_dir.exists(), "delta/ directory should exist"

        parquet_files = list(delta_dir.glob("*.parquet"))
        assert len(parquet_files) == 1, f"Expected 1 parquet file in delta/, found {len(parquet_files)}"

        tmp_files = list(delta_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, "No .tmp files should remain in delta/"

        # Assert no JSON files anywhere in the store (recursive check)
        json_files = list(Path(tmp_store).rglob("*.json"))
        assert len(json_files) == 0, f"No JSON files should exist anywhere in store, found: {json_files}"

    def test_delta_write_uses_staging_then_atomic_publish(self, tmp_store):
        """The writer uses a staging/ temp path and publishes a complete Parquet file to delta/.
        Assert no reader-visible file has .tmp suffix and the final delta file can be read as Parquet."""
        library = ParquetFactorLibrary(store_path=tmp_store)
        entry = _make_factor_entry(factor_name="alpha_002", factor_expression="MEAN($volume, 10)")
        library.write_factor_delta(entry)

        staging_dir = Path(tmp_store) / "staging"
        delta_dir = Path(tmp_store) / "delta"

        tmp_in_staging = list(staging_dir.glob("*.tmp")) if staging_dir.exists() else []
        assert len(tmp_in_staging) == 0, "No .tmp files should remain in staging/ after publish"

        parquet_files = list(delta_dir.glob("*.parquet"))
        assert len(parquet_files) == 1, "One parquet file should exist in delta/"

        df = pl.read_parquet(parquet_files[0])
        assert df.shape[0] == 1, "Parquet file should contain 1 row"
        assert "factor_name" in df.columns
        assert df["factor_name"][0] == "alpha_002"


class TestParquetFactorLibraryRead:
    """Test read_factor_library with compacted + delta and deduplication."""

    def test_read_factor_library_reads_compacted_and_delta(self, tmp_store):
        """A store with both compacted/factors.parquet and delta/*.parquet reads both sets."""
        library = ParquetFactorLibrary(store_path=tmp_store)

        entry1 = _make_factor_entry(factor_name="factor_in_compacted", factor_expression="STD($close, 20)", sequence=1)
        entry2 = _make_factor_entry(factor_name="factor_in_delta", factor_expression="MEAN($volume, 10)", sequence=1)

        library.write_factor_delta(entry1)
        library.compact()

        library.write_factor_delta(entry2)

        df = library.read_factor_library()
        assert df is not None, "read_factor_library should return a DataFrame"
        assert df.shape[0] >= 2, f"Should read at least 2 rows, got {df.shape[0]}"
        factor_names = df["factor_name"].to_list()
        assert "factor_in_compacted" in factor_names
        assert "factor_in_delta" in factor_names

    def test_read_factor_library_tie_breaks_same_sequence_by_updated_at(self, tmp_store):
        """Same expression_hash and same sequence keeps the row with later updated_at."""
        library = ParquetFactorLibrary(store_path=tmp_store)

        common_expr_hash = "shared_hash_tiebreak"

        # Entry v1 with earlier updated_at
        entry_v1 = _make_factor_entry(
            factor_name="factor_v1",
            factor_expression="STD($close, 20)",
            expression_hash=common_expr_hash,
            sequence=1000,
        )
        entry_v1["updated_at"] = "2026-01-01T00:00:00"

        # Entry v2 with later updated_at (same sequence)
        entry_v2 = _make_factor_entry(
            factor_name="factor_v2",
            factor_expression="MEAN($volume, 10)",
            expression_hash=common_expr_hash,
            sequence=1000,  # Same sequence
        )
        entry_v2["updated_at"] = "2026-01-02T00:00:00"

        library.write_factor_delta(entry_v1)
        library.write_factor_delta(entry_v2)

        df = library.read_factor_library()
        assert df is not None
        effective_factors = df.filter(pl.col("expression_hash") == common_expr_hash)
        assert effective_factors.shape[0] == 1, "Should deduplicate to 1 effective factor by expression_hash"
        assert effective_factors["factor_name"][0] == "factor_v2", "Should keep the row with later updated_at"

    def test_read_factor_library_deduplicates_by_expression_hash(self, tmp_store):
        """Duplicate expression_hash entries produce one effective factor, using the latest sequence."""
        library = ParquetFactorLibrary(store_path=tmp_store)

        common_expr_hash = "shared_hash_001"
        entry_v1 = _make_factor_entry(
            factor_name="factor_v1",
            factor_expression="STD($close, 20)",
            expression_hash=common_expr_hash,
            sequence=1,
        )
        entry_v2 = _make_factor_entry(
            factor_name="factor_v2",
            factor_expression="STD($close, 20)",
            expression_hash=common_expr_hash,
            sequence=2,
        )

        library.write_factor_delta(entry_v1)
        library.write_factor_delta(entry_v2)

        df = library.read_factor_library()
        assert df is not None
        effective_factors = df.filter(pl.col("expression_hash") == common_expr_hash)
        assert effective_factors.shape[0] == 1, "Should deduplicate to 1 effective factor by expression_hash"
        assert effective_factors["factor_name"][0] == "factor_v2", "Should keep the latest sequence"


class TestParquetFactorLibraryCompact:
    """Test compact merges delta and preserves effective set."""

    def test_compact_merges_delta_and_preserves_effective_set(self, tmp_store):
        """Compact writes compacted/factors.parquet, removes or archives merged delta,
        and preserves the effective factor set."""
        library = ParquetFactorLibrary(store_path=tmp_store)

        entry1 = _make_factor_entry(factor_name="compact_test_1", factor_expression="STD($close, 20)", sequence=1)
        entry2 = _make_factor_entry(factor_name="compact_test_2", factor_expression="MEAN($volume, 10)", sequence=1)

        library.write_factor_delta(entry1)
        library.write_factor_delta(entry2)

        library.compact()

        compacted_path = Path(tmp_store) / "compacted" / "factors.parquet"
        assert compacted_path.exists(), "compacted/factors.parquet should exist after compact"

        df_compacted = pl.read_parquet(compacted_path)
        assert df_compacted.shape[0] == 2, "Compacted file should contain 2 factors"

        delta_dir = Path(tmp_store) / "delta"
        remaining_deltas = list(delta_dir.glob("*.parquet")) if delta_dir.exists() else []
        assert len(remaining_deltas) == 0, "Delta files should be archived or removed after compact"

        df_read = library.read_factor_library()
        assert df_read is not None
        assert df_read.shape[0] == 2, "Effective factor count should be preserved after compact"

    def test_compact_failure_does_not_delete_delta(self, tmp_store):
        """If compact write fails, existing compacted data remains readable and delta files are not deleted."""
        library = ParquetFactorLibrary(store_path=tmp_store)

        entry1 = _make_factor_entry(factor_name="failure_test_1", factor_expression="STD($close, 20)", sequence=1)
        library.write_factor_delta(entry1)

        compacted_dir = Path(tmp_store) / "compacted"
        compacted_dir.mkdir(parents=True, exist_ok=True)
        compacted_file = compacted_dir / "factors.parquet"
        compacted_file.write_bytes(b"valid_placeholder")

        delta_files_before = list((Path(tmp_store) / "delta").glob("*.parquet"))
        assert len(delta_files_before) == 1, "Should have 1 delta file before compact"

        try:
            library._simulate_compact_failure = True
            library.compact()
        except Exception:
            pass

        delta_files_after = list((Path(tmp_store) / "delta").glob("*.parquet"))
        assert len(delta_files_after) >= 1, "Delta files should not be deleted on compact failure"

        compacted_file = Path(tmp_store) / "compacted" / "factors.parquet"
        assert compacted_file.exists(), "Existing compacted file should still exist"
