from __future__ import annotations

from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


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
        library_backend: str = "json",
        parquet_library_dir: Optional[str] = None,
        backtest_runner: Optional[Callable[[str, dict], bool]] = None,
        data_bridge=None,
        execution_periods: Optional[dict] = None,
        min_ic: float = 0.02,
        per_factor_timeout_seconds: int = 300,
    ):
        import os

        self.days_threshold = days_threshold
        self.max_per_run = max_per_run
        self.interval_hours = interval_hours
        self.library_path = library_path or os.environ.get("FACTOR_LIBRARY_PATH", "third_party/quantaalpha/data/factorlib/all_factors_library.json")
        self.library_backend = library_backend
        self.parquet_library_dir = parquet_library_dir
        self._backtest_runner = backtest_runner
        self._data_bridge = data_bridge
        self._execution_periods = execution_periods or {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }
        self.min_ic = min_ic
        self._per_factor_timeout_seconds = per_factor_timeout_seconds
        self._next_run: Optional[datetime] = None
        self._running = False
        self._stop_event = Event()
        self._scheduler_thread: Optional[Thread] = None
        self._execution_dataframe_cache = None

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

    def run_revalidation(self, candidates: list = None) -> RevalidationResult:
        """
        Run one revalidation cycle.

        Args:
            candidates: Optional list of pre-selected factor candidates.
                      If None, queries library for candidates needing revalidation.
        """
        from datetime import datetime as dt

        start_time = dt.now()
        result = RevalidationResult(timestamp=start_time)

        try:
            facade = None
            library = None

            # Use provided candidates or query library
            if candidates is None:
                if getattr(self, "library_backend", "json") == "parquet":
                    # Parquet backend: read through FactorStoreFacade
                    from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                    facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                    all_records = facade.read_effective_factor_records()
                    # Simple candidate selection: take all active factors
                    candidates = [
                        {
                            "factor_id": r.get("factor_id", ""),
                            "factor_name": r.get("factor_name", ""),
                            "factor_expression": r.get("factor_expression", ""),
                            "evaluation": {"status": r.get("evaluation_status", "unknown")},
                        }
                        for r in all_records
                    ]
                else:
                    # JSON fallback
                    from quantaalpha.factors.library import FactorLibraryManager

                    library = FactorLibraryManager(self.library_path)
                    candidates = library.select_revalidation_candidates(
                        days=self.days_threshold,
                    )

            result.total_candidates = len(candidates)
            candidates_to_run = candidates[: self.max_per_run]

            logger.info(f"Revalidation: {len(candidates_to_run)} of {len(candidates)} candidates selected for revalidation")

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

                    if getattr(self, "library_backend", "json") == "parquet":
                        if facade is None:
                            from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                            facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                        updated_entry = facade.write_status_update(factor_entry, validation_result)
                    else:
                        updated_entry = library.apply_validation_result(factor_entry, validation_result)
                    new_status = updated_entry.get("evaluation", {}).get("status", "unknown")
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

    def clear_execution_dataframe_cache(self) -> None:
        """Clear per-cycle cached execution data."""
        self._execution_dataframe_cache = None

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
        factor_start = time.time()
        logger.info(f"profile.revalidation.factor.start factor={factor_id}")
        logger.info(f"Running backtest for factor {factor_id}")

        # Use injected runner if provided
        if self._backtest_runner is not None:
            return self._run_with_timeout(
                self._backtest_runner,
                factor_id,
                factor_entry,
                self._per_factor_timeout_seconds,
            )

        # Default path: use FactorExecutor from glue if available
        try:
            from third_party.glue.factor_executor import FactorExecutor

            # Get factor expression
            expression = factor_entry.get("factor_expression", "")
            if not expression:
                logger.warning(f"Factor {factor_id} has no expression, skipping backtest")
                return False
            translated_expression, translation_warnings = _translate_factor_expression(expression)
            if translation_warnings:
                logger.info(f"Translation warnings for {factor_id}: {'; '.join(translation_warnings)}")

            # Get periods from configured execution periods
            train_period = self._execution_periods.get("train", ("2020-01-01", "2022-12-31"))
            valid_period = self._execution_periods.get("valid", ("2023-01-01", "2023-12-31"))
            test_period = self._execution_periods.get("test", ("2024-01-01", "2024-12-31"))

            # Load data from bridge if available, otherwise use empty placeholder
            import polars as pl

            df = self._get_execution_dataframe()

            # Only fail if bridge was configured but returned empty/no data
            # When bridge is not configured, use empty placeholder for backward compatibility
            if self._data_bridge is not None and (df is None or df.is_empty()):
                logger.warning(f"No data available from bridge for backtest of {factor_id}")
                return False

            executor = FactorExecutor(
                df=df,
                train_period=train_period,
                valid_period=valid_period,
                test_period=test_period,
            )

            result = executor.execute_single(
                factor_name=factor_id,
                expression=translated_expression,
                original_expression=expression,
            )
            total_seconds = time.time() - factor_start

            if result.success and result.ic_value is not None:
                # Check against validation thresholds
                if result.ic_value >= self.min_ic:
                    logger.info(f"profile.revalidation.factor.done factor={factor_id} success=True total_seconds={total_seconds:.3f} ic_value={result.ic_value:.6f}")
                    logger.info(f"Factor {factor_id} passed backtest with IC={result.ic_value:.4f}")
                    return True
                else:
                    logger.info(f"profile.revalidation.factor.done factor={factor_id} success=False total_seconds={total_seconds:.3f} ic_value={result.ic_value:.6f}")
                    logger.info(f"Factor {factor_id} failed IC threshold: {result.ic_value:.4f} < {self.min_ic}")
                    return False
            else:
                error_msg = result.error_message or "IC unavailable after execution"
                logger.info(f"profile.revalidation.factor.done factor={factor_id} success=False total_seconds={total_seconds:.3f} error={error_msg}")
                logger.warning(f"Factor {factor_id} backtest failed: {error_msg}")
                return False

        except ImportError as e:
            logger.warning(f"FactorExecutor not available: {e}, backtest returning False")
            return False
        except Exception as e:
            logger.error(f"Error running backtest for {factor_id}: {e}")
            return False

    def _run_with_timeout(self, func: Callable, factor_id: str, factor_entry: dict, timeout_seconds: int) -> bool:
        """
        Run a function with timeout enforcement.

        Args:
            func: Function to run (backtest_runner or factor_validator)
            factor_id: Factor ID for logging
            factor_entry: Factor entry dict
            timeout_seconds: Maximum seconds to allow

        Returns:
            True if func returned True before timeout, False otherwise.
        """
        from threading import Thread, Event

        result = {"value": None, "exception": None}
        done_event = Event()

        def run_func():
            try:
                result["value"] = func(factor_id, factor_entry)
            except Exception as e:
                result["exception"] = e
            finally:
                done_event.set()

        thread = Thread(target=run_func, daemon=True)
        thread.start()

        if not done_event.wait(timeout=timeout_seconds):
            logger.warning(
                f"per_factor_timeout: {factor_id} exceeded {timeout_seconds}s limit, interrupting",
            )
            return False

        if result["exception"] is not None:
            logger.error(f"Exception in backtest_runner for {factor_id}: {result['exception']}")
            return False

        return result["value"] is not None and result["value"] is True

    def _get_execution_dataframe(self):
        """
        Get execution DataFrame from bridge if available.

        Returns:
            pl.DataFrame with price data, or empty DataFrame if bridge unavailable.
        """
        import polars as pl

        if self._execution_dataframe_cache is not None:
            logger.info("Using cached execution DataFrame for backtest")
            return self._execution_dataframe_cache

        if self._data_bridge is None:
            logger.info("No data bridge configured, using empty DataFrame")
            self._execution_dataframe_cache = pl.DataFrame(
                {
                    "datetime": pl.Series(dtype=pl.Date),
                    "vt_symbol": pl.Series(dtype=pl.String),
                    "open": pl.Series(dtype=pl.Float64),
                    "high": pl.Series(dtype=pl.Float64),
                    "low": pl.Series(dtype=pl.Float64),
                    "close": pl.Series(dtype=pl.Float64),
                    "volume": pl.Series(dtype=pl.Float64),
                }
            )
            return self._execution_dataframe_cache

        try:
            # Get the maximum coverage window from execution periods
            train_period = self._execution_periods.get("train", ("2020-01-01", "2022-12-31"))
            valid_period = self._execution_periods.get("valid", ("2023-01-01", "2023-12-31"))
            test_period = self._execution_periods.get("test", ("2024-01-01", "2024-12-31"))

            # Use the earliest start and latest end for maximum coverage
            all_start_dates = [train_period[0], valid_period[0], test_period[0]]
            all_end_dates = [train_period[1], valid_period[1], test_period[1]]
            start_date = min(all_start_dates)
            end_date = max(all_end_dates)

            logger.info(f"profile.load_price_data.start context=backtest interfaces={['daily']} start_date={start_date} end_date={end_date}")
            load_start = time.time()
            df = self._data_bridge.load_price_data(
                interfaces=["daily"],
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            load_seconds = time.time() - load_start

            if df is None or df.is_empty():
                logger.info(f"profile.load_price_data.done context=backtest rows=0 seconds={load_seconds:.3f}")
                logger.warning("Bridge returned empty DataFrame")
                # Return empty DataFrame with correct schema for backward compatibility
                self._execution_dataframe_cache = pl.DataFrame(
                    {
                        "datetime": pl.Series(dtype=pl.Date),
                        "vt_symbol": pl.Series(dtype=pl.String),
                        "open": pl.Series(dtype=pl.Float64),
                        "high": pl.Series(dtype=pl.Float64),
                        "low": pl.Series(dtype=pl.Float64),
                        "close": pl.Series(dtype=pl.Float64),
                        "volume": pl.Series(dtype=pl.Float64),
                    }
                )
                return self._execution_dataframe_cache

            logger.info(f"profile.load_price_data.done context=backtest rows={len(df)} seconds={load_seconds:.3f}")
            logger.info(f"Loaded {len(df)} rows from bridge for backtest")
            self._execution_dataframe_cache = df
            return self._execution_dataframe_cache

        except Exception as e:
            logger.error(f"Error loading data from bridge: {e}")
            self._execution_dataframe_cache = pl.DataFrame(
                {
                    "datetime": pl.Series(dtype=pl.Date),
                    "vt_symbol": pl.Series(dtype=pl.String),
                    "open": pl.Series(dtype=pl.Float64),
                    "high": pl.Series(dtype=pl.Float64),
                    "low": pl.Series(dtype=pl.Float64),
                    "close": pl.Series(dtype=pl.Float64),
                    "volume": pl.Series(dtype=pl.Float64),
                }
            )
            return self._execution_dataframe_cache
