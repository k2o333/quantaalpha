"""Tests for FactorStoreFacade - thin storage facade over ParquetFactorLibrary."""

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
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
        returns a non-empty factor zoo frame, and the temporary store contains no .json file.
        """
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
        compacted/factors.parquet exists and effective factor count is preserved.
        """
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


class TestFactorStoreFacadeFieldExtensions:
    """Test field extension defaults and preservation in FactorStoreFacade."""

    def test_write_status_update_persists_field_extension_defaults(self, tmp_store):
        """A validation status update writes default field extension keys to both
        backtest_results_json and metadata_json when they are not already present.
        """
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)
        entry = _make_factor_entry(
            factor_id="field_ext_factor",
            factor_name="field_ext_factor",
            factor_expression="STD($close, 20)",
            expression_hash="field_ext_hash",
            sequence=10,
        )
        facade.write_factor(entry)

        validation_result = {
            "status": "success",
            "summary": {
                "stability_score": 0.7,
                "validation_summary": "test validation",
                "ic_mean": 0.12,
                "rank_ic_mean": 0.08,
                "positive_ratio": 0.6,
            },
        }

        facade.write_status_update(entry, validation_result, sequence=11)

        records = facade.read_effective_factor_records()
        assert len(records) == 1
        record = records[0]

        backtest = json.loads(record["backtest_results_json"])
        metadata = json.loads(record["metadata_json"])

        # backtest_results_json should have default field extension keys
        assert "IC" in backtest
        assert "ICIR" in backtest
        assert "Rank IC" in backtest
        assert "Rank ICIR" in backtest
        assert "positive_ratio" in backtest
        assert "turnover_rate" in backtest
        assert "lag_ic_1d" in backtest
        assert "lag_ic_2d" in backtest
        assert "validation_elapsed_ms" in backtest

        # metadata_json should have default field extension keys
        assert metadata["field_schema_version"] == "1.0"
        assert "data_requirements" in metadata
        assert "dimensions" in metadata["data_requirements"]
        assert "fields" in metadata["data_requirements"]
        assert "data_frequency" in metadata["data_requirements"]
        assert "llm_model_version" in metadata
        assert "prompt_template_hash" in metadata
        assert "parent_factor_id" in metadata
        assert "source" in metadata

    def test_write_status_update_preserves_existing_field_extension_values(self, tmp_store):
        """A validation status update does NOT overwrite existing field extension values."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)
        entry = _make_factor_entry(
            factor_id="preserve_factor",
            factor_name="preserve_factor",
            factor_expression="STD($close, 20)",
            expression_hash="preserve_hash",
            sequence=20,
        )
        facade.write_factor(entry)

        validation_result = {
            "status": "success",
            "summary": {
                "stability_score": 0.8,
                "validation_summary": "test",
                "ic_mean": 0.15,
                "rank_ic_mean": 0.10,
                "positive_ratio": 0.7,
            },
            "IC": 0.15,
            "ICIR": 0.5,
            "Rank IC": 0.10,
            "Rank ICIR": 0.4,
            "positive_ratio": 0.7,
            "turnover_rate": 0.3,
            "lag_ic_1d": 0.05,
            "lag_ic_2d": 0.04,
            "validation_elapsed_ms": 250,
        }

        facade.write_status_update(entry, validation_result, sequence=21)

        records = facade.read_effective_factor_records()
        assert len(records) == 1
        record = records[0]

        backtest = json.loads(record["backtest_results_json"])
        json.loads(record["metadata_json"])

        # Existing values should be preserved
        assert backtest["IC"] == 0.15
        assert backtest["ICIR"] == 0.5
        assert backtest["Rank IC"] == 0.10
        assert backtest["Rank ICIR"] == 0.4
        assert backtest["positive_ratio"] == 0.7
        assert backtest["turnover_rate"] == 0.3
        assert backtest["lag_ic_1d"] == 0.05
        assert backtest["lag_ic_2d"] == 0.04
        assert backtest["validation_elapsed_ms"] == 250

        # summary should still exist
        assert "summary" in backtest


class TestFactorStoreFacadeEncapsulation:
    """Test that FactorStoreFacade does not expose business methods."""

    def test_facade_does_not_expose_business_methods(self, tmp_store):
        """Facade does not expose check_redundancy, select_revalidation_candidates,
        or build_fewshot_context_records.
        """
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        assert not hasattr(facade, "check_redundancy"), "Facade should not expose check_redundancy"
        assert not hasattr(facade, "select_revalidation_candidates"), "Facade should not expose select_revalidation_candidates"
        assert not hasattr(facade, "build_fewshot_context_records"), "Facade should not expose build_fewshot_context_records"


class TestExpressionHashRobustness:
    """Test expression_hash computation and validation - DESIGN.md 2026-04-15."""

    def test_compute_expression_hash_is_static_method(self, tmp_store):
        """FactorStoreFacade has _compute_expression_hash as a static method."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        assert hasattr(FactorStoreFacade, "_compute_expression_hash"), \
            "FactorStoreFacade should have _compute_expression_hash static method"
        assert isinstance(FactorStoreFacade.__dict__["_compute_expression_hash"], staticmethod), \
            "_compute_expression_hash should be a static method"

    def test_compute_expression_hash_produces_consistent_hash(self, tmp_store):
        """_compute_expression_hash produces consistent 16-char hex hash for same expression."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        expr = "STD($close, 20)"
        hash1 = FactorStoreFacade._compute_expression_hash(expr)
        hash2 = FactorStoreFacade._compute_expression_hash(expr)

        assert hash1 == hash2, "Same expression should produce same hash"
        assert len(hash1) == 16, "Hash should be 16 characters"
        assert all(c in "0123456789abcdef" for c in hash1), "Hash should be hex string"

    def test_compute_expression_hash_empty_string(self, tmp_store):
        """_compute_expression_hash returns empty string for empty/None expression."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        assert FactorStoreFacade._compute_expression_hash("") == "", \
            "Empty expression should return empty hash"
        assert FactorStoreFacade._compute_expression_hash(None) == "", \
            "None expression should return empty hash"

    def test_parquet_event_from_legacy_entry_recomputes_hash_when_missing(self, tmp_store):
        """When expression_hash is missing, _parquet_event_from_legacy_entry recomputes from factor_expression."""
        import hashlib

        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        # Simulate old record without expression_hash
        legacy_entry = {
            "factor_id": "test_factor",
            "factor_name": "test",
            "factor_expression": "STD($close, 20)",
            "metadata": {},
            "tags": {},
            "backtest_results": {},
            "evaluation": {"status": "active"},
        }
        source_record = {}  # No expression_hash

        event = facade._parquet_event_from_legacy_entry(
            legacy_entry,
            source_record=source_record,
            op="upsert",
            sequence=1,
        )

        expected_hash = hashlib.sha256("STD($close, 20)".encode()).hexdigest()[:16]
        assert event["expression_hash"] == expected_hash, \
            f"expression_hash should be computed from factor_expression, expected {expected_hash}, got {event['expression_hash']}"

    def test_parquet_event_from_legacy_entry_preserves_existing_hash(self, tmp_store):
        """When expression_hash exists, it should be preserved."""
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        legacy_entry = {
            "factor_id": "test_factor",
            "factor_name": "test",
            "factor_expression": "STD($close, 20)",
            "expression_hash": "existing_hash_123",
            "metadata": {},
            "tags": {},
            "backtest_results": {},
            "evaluation": {"status": "active"},
        }
        source_record = {"expression_hash": "source_hash_456"}

        event = facade._parquet_event_from_legacy_entry(
            legacy_entry,
            source_record=source_record,
            op="upsert",
            sequence=1,
        )

        # Should prefer source_record's hash
        assert event["expression_hash"] == "source_hash_456", \
            "Should preserve source_record's expression_hash"

    def test_write_factor_delta_rejects_empty_hash_with_expression(self, tmp_store):
        """write_factor_delta should reject entries with non-empty factor_expression but empty expression_hash."""
        library = ParquetFactorLibrary(store_path=tmp_store)

        # Entry with factor_expression but no expression_hash should fail
        now_iso = datetime.now().isoformat()
        entry = {
            "factor_id": "test_factor",
            "factor_name": "test",
            "factor_expression": "STD($close, 20)",
            "factor_expression_normalized": "STD($close, 20)",
            "expression_hash": "",  # Empty hash!
            "evaluation_status": "active",
            "created_at": now_iso,
            "updated_at": now_iso,
            "sequence": 1,
            "op": "upsert",
            "tags_json": "[]",
            "metadata_json": "{}",
            "backtest_results_json": "{}",
        }

        with pytest.raises(ValueError, match="expression_hash.*factor_expression"):
            library.write_factor_delta(entry)

    def test_write_factor_delta_accepts_valid_entry(self, tmp_store):
        """write_factor_delta should accept entries with valid expression_hash."""
        import hashlib

        library = ParquetFactorLibrary(store_path=tmp_store)

        expr = "STD($close, 20)"
        expr_hash = hashlib.sha256(expr.encode()).hexdigest()[:16]

        entry = _make_factor_entry(
            factor_id="test_factor",
            factor_name="test",
            factor_expression=expr,
            expression_hash=expr_hash,
            sequence=1,
        )

        # Should not raise
        library.write_factor_delta(entry)

        df = library.read_factor_library()
        assert df is not None
        assert df.shape[0] == 1
        assert df["expression_hash"][0] == expr_hash

    def test_deduplicate_emits_warning_for_empty_hash(self, tmp_store, caplog):
        """_deduplicate_and_filter emits WARNING when encountering empty expression_hash."""
        import hashlib
        import logging

        import polars as pl
        from quantaalpha.factors.parquet_library import ParquetFactorLibrary

        library = ParquetFactorLibrary(store_path=tmp_store)

        # Build a DataFrame with empty expression_hash
        now_iso = datetime.now().isoformat()
        data = {
            "factor_id": ["dirty_factor"],
            "factor_name": ["dirty"],
            "factor_expression": ["STD($close, 20)"],
            "factor_expression_normalized": ["STD($close, 20)"],
            "expression_hash": [""],  # Empty hash
            "evaluation_status": ["active"],
            "created_at": [now_iso],
            "updated_at": [now_iso],
            "sequence": [1],
            "op": ["upsert"],
            "tags_json": ["{}"],
            "metadata_json": ["{}"],
            "backtest_results_json": ["{}"],
        }
        df = pl.DataFrame(data)

        # Capture log output
        logger = logging.getLogger("quantaalpha.factors.parquet_library")
        with caplog.at_level(logging.WARNING, logger="quantaalpha.factors.parquet_library"):
            result = library._deduplicate_and_filter(df)

        # Verify WARNING was emitted
        assert "empty expression_hash" in caplog.text, \
            "WARNING message should mention 'empty expression_hash'"

        # Verify hash was fixed
        expected_hash = hashlib.sha256("STD($close, 20)".encode()).hexdigest()[:16]
        assert result["expression_hash"][0] == expected_hash, \
            f"Empty hash should be replaced with computed hash, got {result['expression_hash'][0]}"

    def test_deduplicate_fallback_fixes_empty_hash_correctly(self, tmp_store):
        """Two records with empty expression_hash and same expression deduplicate to 1 after fix."""
        import hashlib

        import polars as pl
        from quantaalpha.factors.parquet_library import ParquetFactorLibrary

        library = ParquetFactorLibrary(store_path=tmp_store)

        now_iso = datetime.now().isoformat()
        expr = "STD($close, 20)"
        expected_hash = hashlib.sha256(expr.encode()).hexdigest()[:16]

        # Two records with same expression but both have empty hash
        data = {
            "factor_id": ["factor_v1", "factor_v2"],
            "factor_name": ["v1", "v2"],
            "factor_expression": [expr, expr],
            "factor_expression_normalized": [expr, expr],
            "expression_hash": ["", ""],  # Both empty
            "evaluation_status": ["active", "active"],
            "created_at": [now_iso, now_iso],
            "updated_at": ["2026-01-01T00:00:00", "2026-01-02T00:00:00"],
            "sequence": [1, 2],
            "op": ["upsert", "upsert"],
            "tags_json": ["{}", "{}"],
            "metadata_json": ["{}", "{}"],
            "backtest_results_json": ["{}", "{}"],
        }
        df = pl.DataFrame(data)

        result = library._deduplicate_and_filter(df)

        # Should deduplicate to 1 record
        assert result.shape[0] == 1, f"Should deduplicate to 1 record, got {result.shape[0]}"
        assert result["expression_hash"][0] == expected_hash, \
            "Deduplicated record should have correct computed hash"
        assert result["factor_name"][0] == "v2", "Should keep the latest version"

    def test_write_status_update_with_legacy_record_missing_hash(self, tmp_store):
        """write_status_update computes correct hash when source_record has no expression_hash."""
        import hashlib

        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        facade = FactorStoreFacade(store_path=tmp_store)

        # Simulate an old-style record without expression_hash (the original bug scenario)
        old_record = {
            "factor_id": "legacy_factor",
            "factor_name": "legacy",
            "factor_expression": "STD($close, 20)",
            "factor_expression_normalized": "STD($close, 20)",
            "expression_hash": "",  # Old records have empty hash
            "evaluation_status": "pending_validation",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "sequence": 10,
            "op": "upsert",
            "tags_json": "{}",
            "metadata_json": "{}",
            "backtest_results_json": "{}",
            "metadata": {},
            "tags": {},
            "backtest_results": {},
            "evaluation": {"status": "pending_validation"},
        }

        validation_result = {
            "status": "success",
            "summary": {
                "stability_score": 0.7,
                "validation_summary": "passed",
            },
        }

        # This should NOT raise - hash should be recomputed from expression
        updated = facade.write_status_update(old_record, validation_result, sequence=11)

        # Verify the updated record has correct hash
        records = facade.read_effective_factor_records()
        assert len(records) == 1
        record = records[0]

        expected_hash = hashlib.sha256("STD($close, 20)".encode()).hexdigest()[:16]
        assert record["expression_hash"] == expected_hash, \
            f"Status update should have correct hash, expected {expected_hash}, got {record['expression_hash']}"
        assert record["sequence"] == 11
        assert not list(Path(tmp_store).rglob("*.json"))

    def test_compact_cleans_dirty_hash_in_compacted_file(self, tmp_store, caplog):
        """Dirty delta with empty hash → compact → compacted file has fixed hash, no WARNING on next read."""
        import hashlib
        import logging

        import polars as pl
        from quantaalpha.factors.parquet_library import ParquetFactorLibrary

        library = ParquetFactorLibrary(store_path=tmp_store)

        # Write a delta file with empty expression_hash (simulating pre-fix data)
        now_iso = datetime.now().isoformat()
        expr = "MEAN($volume, 10)"
        expected_hash = hashlib.sha256(expr.encode()).hexdigest()[:16]

        dirty_entry = {
            "factor_id": "dirty_compact_factor",
            "factor_name": "dirty",
            "factor_expression": expr,
            "factor_expression_normalized": expr,
            "expression_hash": "",  # Dirty: empty hash
            "evaluation_status": "active",
            "created_at": now_iso,
            "updated_at": now_iso,
            "sequence": 1,
            "op": "upsert",
            "tags_json": "{}",
            "metadata_json": "{}",
            "backtest_results_json": "{}",
        }

        # Write dirty data directly to delta (bypassing validation to simulate historical data)
        delta_dir = Path(tmp_store) / "delta"
        dirty_df = pl.DataFrame({
            "factor_id": [dirty_entry["factor_id"]],
            "factor_name": [dirty_entry["factor_name"]],
            "factor_expression": [dirty_entry["factor_expression"]],
            "factor_expression_normalized": [dirty_entry["factor_expression_normalized"]],
            "expression_hash": [dirty_entry["expression_hash"]],
            "evaluation_status": [dirty_entry["evaluation_status"]],
            "created_at": [dirty_entry["created_at"]],
            "updated_at": [dirty_entry["updated_at"]],
            "sequence": [dirty_entry["sequence"]],
            "op": [dirty_entry["op"]],
            "tags_json": [dirty_entry["tags_json"]],
            "metadata_json": [dirty_entry["metadata_json"]],
            "backtest_results_json": [dirty_entry["backtest_results_json"]],
        })
        dirty_df.write_parquet(str(delta_dir / "dirty.12345678.parquet"))

        # Compact - should fix the empty hash via Layer 3
        logger = logging.getLogger("quantaalpha.factors.parquet_library")
        with caplog.at_level(logging.WARNING, logger="quantaalpha.factors.parquet_library"):
            library.compact()

        # Compact should have emitted WARNING for empty hash
        assert "empty expression_hash" in caplog.text, \
            "Compact should have emitted WARNING for empty hash"

        # Read compacted file directly - should have correct hash
        compacted_path = Path(tmp_store) / "compacted" / "factors.parquet"
        assert compacted_path.exists(), "Compacted file should exist"
        compacted_df = pl.read_parquet(compacted_path)

        assert compacted_df.shape[0] == 1, "Compacted file should contain 1 record"
        assert compacted_df["expression_hash"][0] == expected_hash, \
            f"Compacted record should have correct hash, expected {expected_hash}, got {compacted_df['expression_hash'][0]}"

        # Now read the library again - should NOT trigger WARNING (hash is already fixed)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="quantaalpha.factors.parquet_library"):
            result_df = library.read_factor_library()

        assert "empty expression_hash" not in caplog.text, \
            "Reading after compact should NOT trigger empty expression_hash WARNING"
        assert result_df is not None
        assert result_df["expression_hash"][0] == expected_hash

