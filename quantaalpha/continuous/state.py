"""
Cross-cycle state persistence for continuous mining.

Manages TrajectoryPool and FailureTracker lifecycle:
- Atomic save (write-temp-then-rename) to prevent file corruption
- Startup validation (detect corrupted pool files)
- Automatic purging of lowest-ranking trajectories when pool exceeds max size
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from quantaalpha.pipeline.evolution.trajectory import TrajectoryPool
from quantaalpha.factors.failure_tracker import FactorFailureTracker

logger = logging.getLogger(__name__)


class ContinuousStateManager:
    """Manages cross-cycle state for continuous mining."""

    def __init__(
        self,
        pool_save_path: str,
        max_pool_size: int = 500,
    ):
        self._pool_save_path = Path(pool_save_path)
        self._max_pool_size = max_pool_size
        self._pool: Optional[TrajectoryPool] = None

    def load_pool(self) -> TrajectoryPool:
        """
        Load trajectory pool from disk.

        Returns empty pool if file doesn't exist or is corrupted.
        Uses fresh_start=False (reuses existing data for continuous mode).
        """
        if self._pool is not None:
            return self._pool

        if not self._pool_save_path.exists():
            logger.info(f"Trajectory pool file not found: {self._pool_save_path}, starting fresh")
            self._pool = TrajectoryPool(save_path=self._pool_save_path, fresh_start=False)
            return self._pool

        if not self._validate_pool_file():
            logger.warning(f"Corrupted trajectory pool file: {self._pool_save_path}, starting fresh")
            backup_path = self._pool_save_path.with_suffix(".json.corrupted")
            try:
                os.rename(str(self._pool_save_path), str(backup_path))
                logger.info(f"Backed up corrupted pool to {backup_path}")
            except OSError as e:
                logger.error(f"Failed to backup corrupted pool: {e}")

            self._pool = TrajectoryPool(save_path=self._pool_save_path, fresh_start=True)
            return self._pool

        try:
            self._pool = TrajectoryPool(save_path=self._pool_save_path, fresh_start=False)
            logger.info(f"Loaded trajectory pool: {len(self._pool.get_all())} trajectories")
        except Exception as e:
            logger.error(f"Failed to load trajectory pool: {e}")
            self._pool = TrajectoryPool(save_path=self._pool_save_path, fresh_start=True)

        return self._pool

    def save_pool(self, pool: Optional[TrajectoryPool] = None) -> None:
        """
        Save trajectory pool to disk atomically.

        Uses write-temp-then-rename to prevent file corruption.
        """
        pool_to_save = pool if pool is not None else self._pool
        if pool_to_save is None:
            logger.warning("No trajectory pool to save")
            return

        try:
            self._pool_save_path.parent.mkdir(parents=True, exist_ok=True)

            dir_name = str(self._pool_save_path.parent)
            fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=dir_name)
            os.close(fd)

            try:
                original_save_path = pool_to_save.save_path
                pool_to_save.save_path = Path(tmp_path)
                pool_to_save._save()
                os.replace(tmp_path, str(self._pool_save_path))
                pool_to_save.save_path = original_save_path
                logger.info(f"Saved trajectory pool: {len(pool_to_save.get_all())} trajectories")
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                pool_to_save.save_path = original_save_path
                raise
        except Exception as e:
            logger.error(f"Failed to save trajectory pool: {e}")

    def purge_pool(self) -> int:
        """
        Remove lowest-ranking trajectories when pool exceeds max size.

        Returns number of trajectories removed.
        """
        pool = self.load_pool()
        current_size = len(pool.get_all())
        if current_size <= self._max_pool_size:
            return 0

        sorted_trajectories = sorted(
            pool.get_all(),
            key=lambda t: t.get_primary_metric() or 0.0,
            reverse=True,
        )

        to_remove = sorted_trajectories[self._max_pool_size :]
        removed_count = 0

        for traj in to_remove:
            if pool.remove(traj.trajectory_id):
                removed_count += 1

        logger.info(f"Purged {removed_count} trajectories from pool ({current_size} -> {len(pool.get_all())})")
        return removed_count

    def get_failure_tracker(self) -> FactorFailureTracker:
        """Create a FailureTracker for continuous mining use."""
        return FactorFailureTracker(max_debug_rounds=10)

    def _validate_pool_file(self) -> bool:
        """Check if pool file is valid JSON."""
        try:
            with open(self._pool_save_path, "r") as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, OSError):
            return False

    @property
    def pool(self) -> TrajectoryPool:
        """Lazy access to the trajectory pool."""
        return self.load_pool()
