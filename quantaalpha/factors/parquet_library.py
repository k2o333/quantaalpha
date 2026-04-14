"""
Parquet-native factor library storage.

Provides atomic delta writes, compacted + delta reads, deduplication,
and short-lock compaction for QuantaAlpha factor persistence.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "factor_id",
    "factor_name",
    "factor_expression",
    "factor_expression_normalized",
    "expression_hash",
    "evaluation_status",
    "created_at",
    "updated_at",
    "sequence",
    "op",
    "tags_json",
    "metadata_json",
    "backtest_results_json",
]


class ParquetFactorLibrary:
    """Manage Parquet-native factor library with delta shards and compaction."""

    def __init__(self, store_path: str):
        """Initialize Parquet factor library store.

        Args:
            store_path: Absolute path to the factor library store directory.
        """
        self.store_path = Path(store_path)
        self.compacted_dir = self.store_path / "compacted"
        self.delta_dir = self.store_path / "delta"
        self.staging_dir = self.store_path / "staging"
        self.archive_dir = self.store_path / "archive"
        self.locks_dir = self.store_path / "locks"
        self.lock_path = self.locks_dir / "library.lock"

        self._ensure_dirs()
        self._simulate_compact_failure = False

    def _ensure_dirs(self):
        """Create all required subdirectories."""
        for d in [self.compacted_dir, self.delta_dir, self.staging_dir, self.archive_dir, self.locks_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _acquire_lock(self):
        """Acquire file lock for atomic operations."""
        lock_fd = open(self.lock_path, "w")
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        return lock_fd

    def _release_lock(self, lock_fd):
        """Release file lock."""
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()

    def write_factor_delta(self, entry: Dict[str, Any]):
        """Write a single factor as a Parquet delta shard.

        Uses staging -> delta atomic publication pattern:
        1. Write to staging/<factor_id>.<uuid>.parquet.tmp
        2. Atomic rename to delta/<factor_id>.<uuid>.parquet

        Args:
            entry: Dict with factor fields matching required schema.
        """
        self._validate_entry(entry)

        factor_id = entry["factor_id"]
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{factor_id}.{unique_id}.parquet"

        staging_path = self.staging_dir / f"{filename}.tmp"
        delta_path = self.delta_dir / filename

        df = self._entry_to_dataframe(entry)

        lock_fd = self._acquire_lock()
        try:
            df.write_parquet(str(staging_path))
            os.replace(str(staging_path), str(delta_path))
            logger.debug(f"Factor delta published: {delta_path.name}")
        except Exception:
            if staging_path.exists():
                staging_path.unlink(missing_ok=True)
            raise
        finally:
            self._release_lock(lock_fd)

    def _validate_entry(self, entry: Dict[str, Any]):
        """Validate factor entry has all required fields."""
        missing = [col for col in REQUIRED_COLUMNS if col not in entry]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    def _entry_to_dataframe(self, entry: Dict[str, Any]) -> pl.DataFrame:
        """Convert factor entry dict to Polars DataFrame with fixed schema."""
        # Build schema with correct types
        schema = {
            "factor_id": pl.String,
            "factor_name": pl.String,
            "factor_expression": pl.String,
            "factor_expression_normalized": pl.String,
            "expression_hash": pl.String,
            "evaluation_status": pl.String,
            "created_at": pl.String,
            "updated_at": pl.String,
            "sequence": pl.Int64,
            "op": pl.String,
            "tags_json": pl.String,
            "metadata_json": pl.String,
            "backtest_results_json": pl.String,
        }

        # Ensure sequence is int
        data = {col: [entry.get(col, "")] for col in REQUIRED_COLUMNS}
        data["sequence"] = [int(entry.get("sequence", 0))]

        df = pl.DataFrame(data, schema=schema)
        return df

    def read_factor_library(self) -> Optional[pl.DataFrame]:
        """Read effective factor library from compacted + delta shards.

        Returns deduplicated factors keeping latest sequence per expression_hash.
        Filters out op == delete records.

        Returns:
            DataFrame with effective factors, or None if store is empty.
        """
        lock_fd = self._acquire_lock()
        try:
            frames = []

            compacted_path = self.compacted_dir / "factors.parquet"
            if compacted_path.exists():
                df_compacted = pl.read_parquet(str(compacted_path))
                # Select and reorder columns to match expected schema
                df_compacted = df_compacted.select(REQUIRED_COLUMNS)
                frames.append(df_compacted)

            delta_files = sorted(self.delta_dir.glob("*.parquet"))
            for delta_file in delta_files:
                df_delta = pl.read_parquet(str(delta_file))
                # Select and reorder columns to match expected schema
                df_delta = df_delta.select(REQUIRED_COLUMNS)
                frames.append(df_delta)

            if not frames:
                return None

            combined = pl.concat(frames)
            return self._deduplicate_and_filter(combined)
        finally:
            self._release_lock(lock_fd)

    def _deduplicate_and_filter(self, df: pl.DataFrame) -> pl.DataFrame:
        """Deduplicate by expression_hash keeping latest sequence, then filter deletes.

        Uses stable tie-break ordering: expression_hash -> sequence -> updated_at -> created_at
        """
        if df.is_empty():
            return df

        # Fix empty expression_hash by computing from factor_expression
        import hashlib

        df = df.with_columns(pl.when(pl.col("expression_hash") == "").then(pl.col("factor_expression").map_elements(lambda x: hashlib.sha256(x.encode()).hexdigest()[:16] if x else "")).otherwise(pl.col("expression_hash")).alias("expression_hash"))

        df_sorted = df.sort(
            ["expression_hash", "sequence", "updated_at", "created_at"],
            descending=[False, True, True, True],
        )
        df_deduped = df_sorted.group_by("expression_hash").first()
        return df_deduped.filter(pl.col("op") != "delete")

    def compact(self, *, archive_retention: int | None = None):
        """Merge compacted + delta into new compacted/factors.parquet.

        Uses atomic write pattern:
        1. Read compacted + delta
        2. Deduplicate
        3. Write to compacted/factors.tmp.parquet
        4. Atomic rename to compacted/factors.parquet
        5. Archive delta files
        """
        lock_fd = self._acquire_lock()
        try:
            if getattr(self, "_simulate_compact_failure", False):
                raise RuntimeError("Simulated compact failure for testing")

            frames = []

            compacted_path = self.compacted_dir / "factors.parquet"
            if compacted_path.exists():
                df_compacted = pl.read_parquet(str(compacted_path))
                # Select and reorder columns to match expected schema
                df_compacted = df_compacted.select(REQUIRED_COLUMNS)
                frames.append(df_compacted)

            delta_files = sorted(self.delta_dir.glob("*.parquet"))
            for delta_file in delta_files:
                df_delta = pl.read_parquet(str(delta_file))
                # Select and reorder columns to match expected schema
                df_delta = df_delta.select(REQUIRED_COLUMNS)
                frames.append(df_delta)

            if not frames:
                logger.info("No data to compact")
                return

            combined = pl.concat(frames)
            effective = self._deduplicate_and_filter(combined)

            # Ensure column order matches required schema before writing
            effective = effective.select(REQUIRED_COLUMNS)

            tmp_path = self.compacted_dir / "factors.tmp.parquet"
            final_path = self.compacted_dir / "factors.parquet"

            effective.write_parquet(str(tmp_path))
            os.replace(str(tmp_path), str(final_path))

            self._archive_delta_files(delta_files)
            if archive_retention is not None:
                self._cleanup_archive_dirs(archive_retention)

            logger.info(f"Compact complete: {len(effective)} effective factors")
        except Exception:
            tmp_path = self.compacted_dir / "factors.tmp.parquet"
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise
        finally:
            self._release_lock(lock_fd)

    def _archive_delta_files(self, delta_files: List[Path]):
        """Move delta files to archive directory."""
        archive_subdir = self.archive_dir / f"compact_at={datetime.now().strftime('%Y%m%d_%H%M%S')}"
        archive_subdir.mkdir(parents=True, exist_ok=True)

        for delta_file in delta_files:
            if delta_file.exists():
                target = archive_subdir / delta_file.name
                os.replace(str(delta_file), str(target))

    def _cleanup_archive_dirs(self, archive_retention: int):
        """Keep only the newest compact archive directories."""
        if archive_retention < 0:
            return
        archive_dirs = sorted(
            [p for p in self.archive_dir.iterdir() if p.is_dir() and p.name.startswith("compact_at=")],
            key=lambda p: p.name,
        )
        to_delete = archive_dirs[: max(0, len(archive_dirs) - archive_retention)]
        for archive_path in to_delete:
            shutil.rmtree(archive_path, ignore_errors=True)
