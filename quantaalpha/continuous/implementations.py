"""
Default implementations for the continuous orchestration module.

These implementations use:
- APScheduler for task scheduling
- Polling for data monitoring
- Factor library integration for revalidation
- RAG + LLM for mining
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from threading import Thread, Event
from typing import Callable, Optional

from .scheduler import (
    DataMonitorTrigger,
    MiningResult,
    MiningScheduler,
    RevalidationResult,
    RevalidationScheduler,
    SchedulerContext,
    SchedulerEvent,
)

logger = logging.getLogger(__name__)


class DefaultDataMonitor(DataMonitorTrigger):
    """
    Default data monitor using file system polling.

    Tracks modification times of configured directories and emits
    DATA_UPDATE events when new/modified files are detected.
    """

    def __init__(
        self,
        check_interval: int = 300,
        data_dirs: Optional[list[str]] = None,
    ):
        self.check_interval = check_interval
        self.data_dirs = data_dirs or []
        self._last_check_time: Optional[datetime] = None
        self._file_mtimes: dict[str, float] = {}
        self._stop_event = Event()
        self._monitor_thread: Optional[Thread] = None

    def start(self) -> None:
        """Start monitoring in background thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Data monitor already running")
            return

        self._stop_event.clear()
        self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Data monitor started, checking every {self.check_interval}s")

    def stop(self) -> None:
        """Stop monitoring."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Data monitor stopped")

    def check_for_updates(self) -> list[SchedulerContext]:
        """
        Check for data updates.

        Returns:
            List of SchedulerContext with DATA_UPDATE events.
        """
        events = []
        current_time = datetime.now()

        for data_dir in self.data_dirs:
            try:
                path = Path(data_dir)
                if not path.exists():
                    continue

                for file_path in path.rglob("*.parquet"):
                    try:
                        mtime = file_path.stat().st_mtime
                        key = str(file_path)

                        if key not in self._file_mtimes:
                            # New file
                            self._file_mtimes[key] = mtime
                            events.append(
                                SchedulerContext(
                                    event=SchedulerEvent.DATA_UPDATE,
                                    timestamp=current_time,
                                    payload={
                                        "file_path": str(file_path),
                                        "file_name": file_path.name,
                                        "change_type": "new",
                                    },
                                    source_module="data_monitor",
                                )
                            )
                        elif self._file_mtimes[key] < mtime:
                            # Modified file
                            self._file_mtimes[key] = mtime
                            events.append(
                                SchedulerContext(
                                    event=SchedulerEvent.DATA_UPDATE,
                                    timestamp=current_time,
                                    payload={
                                        "file_path": str(file_path),
                                        "file_name": file_path.name,
                                        "change_type": "modified",
                                    },
                                    source_module="data_monitor",
                                )
                            )
                    except (OSError, PermissionError):
                        continue

            except Exception as e:
                logger.error(f"Error checking data dir {data_dir}: {e}")

        self._last_check_time = current_time
        return events

    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last check."""
        return self._last_check_time

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            self.check_for_updates()
            self._stop_event.wait(timeout=self.check_interval)


class DefaultRevalidationScheduler(RevalidationScheduler):
    """
    Default revalidation scheduler using APScheduler.

    Integrates with FactorLibraryManager to:
    1. Query candidates needing revalidation
    2. Run backtest for each candidate
    3. Update factor status
    """

    def __init__(
        self,
        days_threshold: int = 21,
        max_per_run: int = 10,
        interval_hours: int = 24,
        library_path: Optional[str] = None,
        backtest_runner: Optional[Callable[[str, dict], bool]] = None,
    ):
        import os

        self.days_threshold = days_threshold
        self.max_per_run = max_per_run
        self.interval_hours = interval_hours
        self.library_path = library_path or os.environ.get(
            "FACTOR_LIBRARY_PATH", "data/results/factor_library.json"
        )
        self._backtest_runner = backtest_runner
        self._next_run: Optional[datetime] = None
        self._running = False
        self._stop_event = Event()
        self._scheduler_thread: Optional[Thread] = None

    def start(self) -> None:
        """Start the scheduler with background timer loop."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Revalidation scheduler already running")
            return
        self._running = True
        self._stop_event.clear()
        self._update_next_run()
        self._scheduler_thread = Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info(f"Revalidation scheduler started, next run at {self._next_run}")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10)
        self._running = False
        logger.info("Revalidation scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Background scheduler loop that triggers revalidation."""
        while not self._stop_event.is_set():
            now = datetime.now()
            if self._next_run and now >= self._next_run:
                try:
                    self.run_revalidation()
                except Exception as e:
                    logger.error(f"Error in revalidation cycle: {e}")
            self._stop_event.wait(timeout=60)

    def run_revalidation(self) -> RevalidationResult:
        """Run one revalidation cycle."""
        from datetime import datetime as dt

        start_time = dt.now()
        result = RevalidationResult(timestamp=start_time)

        try:
            from quantaalpha.factors.library import FactorLibraryManager

            library = FactorLibraryManager(self.library_path)

            candidates = library.select_revalidation_candidates(
                days=self.days_threshold,
            )

            result.total_candidates = len(candidates)
            candidates_to_run = candidates[: self.max_per_run]

            logger.info(
                f"Revalidation: {len(candidates_to_run)} of {len(candidates)} "
                f"candidates selected for revalidation"
            )

            for factor_entry in candidates_to_run:
                factor_id = factor_entry.get("factor_id", "")
                try:
                    backtest_result = self._run_factor_backtest(factor_id, factor_entry)

                    if backtest_result is True:
                        validation_result = {
                            "status": "success",
                            "summary": {
                                "stability_score": 0.6,
                                "validation_summary": f"Backtest passed for {factor_id}",
                            },
                        }
                        result.revalidated_count += 1
                    else:
                        validation_result = {
                            "status": "failure",
                            "summary": {
                                "stability_score": None,
                                "validation_summary": f"Backtest failed for {factor_id}",
                            },
                        }

                    updated_entry = library.apply_validation_result(
                        factor_entry, validation_result
                    )
                    new_status = updated_entry.get("evaluation", {}).get(
                        "status", "unknown"
                    )
                    result.status_changes[factor_id] = new_status

                except Exception as e:
                    logger.error(f"Error revalidating factor {factor_id}: {e}")
                    result.errors.append(f"{factor_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in revalidation cycle: {e}")
            result.errors.append(str(e))

        result.duration_seconds = (dt.now() - start_time).total_seconds()
        self._update_next_run()

        return result

    def get_next_scheduled_run(self) -> Optional[datetime]:
        """Get next scheduled run time."""
        return self._next_run

    def _update_next_run(self) -> None:
        """Update next run timestamp."""
        self._next_run = datetime.now() + timedelta(hours=self.interval_hours)

    def _run_factor_backtest(self, factor_id: str, factor_entry: dict) -> bool:
        """
        Run backtest for a single factor.

        This is a seam for backtest module integration.

        Args:
            factor_id: ID of the factor to backtest
            factor_entry: Full factor entry dict from library

        Returns:
            True if factor passed backtest, False if failed.
            None indicates error/uncertain result.
        """
        logger.info(f"Running backtest for factor {factor_id}")
        if self._backtest_runner is not None:
            return self._backtest_runner(factor_id, factor_entry)
        return False


class DefaultMiningScheduler(MiningScheduler):
    """
    Default mining scheduler using RAG + LLM.

    Workflow:
    1. Query active factors via RAG for context
    2. Invoke LLM to generate new factors
    3. Run backtest validation
    4. Add successful factors to library
    """

    def __init__(
        self,
        max_per_run: int = 5,
        interval_hours: int = 12,
        library_path: Optional[str] = None,
        factor_validator: Optional[Callable[[str, dict], Optional[dict]]] = None,
    ):
        import os

        self.max_per_run = max_per_run
        self.interval_hours = interval_hours
        self.library_path = library_path or os.environ.get(
            "FACTOR_LIBRARY_PATH", "data/results/factor_library.json"
        )
        self._factor_validator = factor_validator
        self._next_run: Optional[datetime] = None
        self._running = False
        self._stop_event = Event()
        self._scheduler_thread: Optional[Thread] = None

    def start(self) -> None:
        """Start the scheduler with background timer loop."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Mining scheduler already running")
            return
        self._running = True
        self._stop_event.clear()
        self._update_next_run()
        self._scheduler_thread = Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info(f"Mining scheduler started, next run at {self._next_run}")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10)
        self._running = False
        logger.info("Mining scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Background scheduler loop that triggers mining."""
        while not self._stop_event.is_set():
            now = datetime.now()
            if self._next_run and now >= self._next_run:
                try:
                    self.run_mining()
                except Exception as e:
                    logger.error(f"Error in mining cycle: {e}")
            self._stop_event.wait(timeout=60)

    def run_mining(self) -> MiningResult:
        """Run one mining cycle."""
        from datetime import datetime as dt

        start_time = dt.now()
        result = MiningResult(timestamp=start_time)

        try:
            context = self._retrieve_context()
            generated = self._generate_factors(context)

            result.factors_generated = len(generated)

            for factor_entry in generated[: self.max_per_run]:
                factor_id = factor_entry.get("factor_id", "")
                try:
                    validation_result = self._validate_factor(factor_id, factor_entry)

                    if (
                        validation_result is not None
                        and validation_result.get("status") == "success"
                    ):
                        result.factors_validated += 1
                        result.factor_ids.append(factor_id)
                        self._add_factor_to_library(factor_entry)
                        result.factors_added += 1

                except Exception as e:
                    logger.error(f"Error validating factor {factor_id}: {e}")
                    result.errors.append(f"{factor_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in mining cycle: {e}")
            result.errors.append(str(e))

        result.duration_seconds = (dt.now() - start_time).total_seconds()
        self._update_next_run()

        return result

    def get_next_scheduled_run(self) -> Optional[datetime]:
        """Get next scheduled run time."""
        return self._next_run

    def _update_next_run(self) -> None:
        """Update next run timestamp."""
        self._next_run = datetime.now() + timedelta(hours=self.interval_hours)

    def _retrieve_context(self) -> str:
        """
        Retrieve context via RAG.

        Returns:
            Context string for factor generation.
        """
        try:
            from quantaalpha.factors.fewshot import query_active_factors_RAG

            results = query_active_factors_RAG(query="", top_k=10)
            return results.get("context", "")

        except ImportError:
            logger.warning("RAG module not available, using empty context")
            return ""
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {e}")
            return ""

    def _generate_factors(self, context: str) -> list[dict]:
        """
        Generate new factors via LLM.

        Args:
            context: RAG context from existing factors.

        Returns:
            List of generated factor entry dicts.
        """
        logger.info("Generating new factors via LLM")
        return []

    def _validate_factor(self, factor_id: str, factor_entry: dict) -> Optional[dict]:
        """
        Validate a single factor via backtest.

        This is a seam for backtest module integration.

        Args:
            factor_id: ID of the factor to validate
            factor_entry: Full factor entry dict

        Returns:
            Validation result dict with 'status' key ('success' or 'failure').
            None indicates error/uncertain result.
        """
        logger.info(f"Validating factor {factor_id}")
        if self._factor_validator is not None:
            return self._factor_validator(factor_id, factor_entry)
        return {
            "status": "failure",
            "summary": {
                "stability_score": 0.0,
                "validation_summary": f"Validation not implemented for {factor_id}",
            },
        }

    def _add_factor_to_library(self, factor_entry: dict) -> None:
        """
        Add validated factor to library.

        Args:
            factor_entry: Factor entry dict to add.
        """
        try:
            from quantaalpha.factors.library import FactorLibraryManager

            library = FactorLibraryManager(self.library_path)
            factor_id = factor_entry.get("factor_id", "")
            validation_result = {
                "status": "success",
                "summary": {
                    "stability_score": 0.6,
                    "validation_summary": f"Factor {factor_id} activated after mining",
                },
            }
            library.apply_validation_result(factor_entry, validation_result)
            logger.info(f"Factor {factor_id} added to library")

        except ImportError:
            logger.error("Factor library module not available")
        except Exception as e:
            logger.error(f"Error adding factor {factor_id} to library: {e}")
