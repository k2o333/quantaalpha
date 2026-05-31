from __future__ import annotations

import json
import re
import ast

from .expression_quality import (
    build_factor_error,
    iter_call_args,
    operator_arity_warning,
    split_top_level_args,
    unsupported_translation_warning,
)
from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


def _record_last_validated(record: dict) -> Optional[datetime]:
    value = None
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        value = metadata.get("last_validated")
    if value is None and record.get("metadata_json"):
        try:
            metadata = json.loads(record.get("metadata_json") or "{}")
            value = metadata.get("last_validated")
        except Exception:
            value = None
    value = value or record.get("last_validated")
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def select_revalidation_candidates_by_lifecycle(
    records: list[dict],
    *,
    days_threshold: int,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Select automatic revalidation candidates by lifecycle state."""
    now = now or datetime.now()
    allowed_statuses = {"active", "candidate", "degraded"}
    reasons = {
        "active": "active_periodic",
        "candidate": "candidate_confirmation",
        "degraded": "degraded_observation",
    }
    selected: list[dict] = []
    for record in records:
        status = str(record.get("evaluation_status") or record.get("evaluation", {}).get("status") or "").lower()
        if status not in allowed_statuses:
            continue
        last_validated = _record_last_validated(record)
        if last_validated is not None and (now - last_validated).days < days_threshold:
            continue
        candidate = {
            "factor_id": record.get("factor_id", ""),
            "factor_name": record.get("factor_name", ""),
            "factor_expression": record.get("factor_expression", ""),
            "evaluation": {"status": status},
            "lifecycle_revalidation_reason": reasons[status],
        }
        selected.append(candidate)
    return selected


def _vnpy_expression_compatibility_warning(expression: str, columns: set[str]) -> str:
    """Return a warning if an expression references unavailable vnpy symbols."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"

    allowed_functions = {
        "abs",
        "cs_kurt",
        "cs_mean",
        "cs_median",
        "cs_rank",
        "cs_scale",
        "cs_skew",
        "cs_std",
        "cs_sum",
        "exp",
        "floor",
        "greater",
        "inv",
        "less",
        "log",
        "pow1",
        "pow2",
        "quesval",
        "quesval2",
        "sign",
        "sqrt",
        "ta_atr",
        "ta_bb_lower",
        "ta_bb_middle",
        "ta_bb_upper",
        "ta_macd",
        "ta_rsi",
        "ts_abs",
        "ts_argmax",
        "ts_argmin",
        "ts_corr",
        "ts_count",
        "ts_cov",
        "ts_decay_linear",
        "ts_delta",
        "ts_delay",
        "ts_ema",
        "ts_greater",
        "ts_kurt",
        "ts_less",
        "ts_log",
        "ts_max",
        "ts_mean",
        "ts_min",
        "ts_pctchange",
        "ts_percentile",
        "ts_product",
        "ts_quantile",
        "ts_rank",
        "ts_regbeta",
        "ts_regresi",
        "ts_resi",
        "ts_rsquare",
        "ts_skew",
        "ts_slope",
        "ts_std",
        "ts_sum",
        "ts_sumif",
        "ts_var",
        "ts_wma",
        "ts_zscore",
    }
    called_functions: set[str] = set()
    variables: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_functions.add(node.func.id)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            variables.add(node.id)

    unknown_functions = sorted(name for name in called_functions if name not in allowed_functions)
    unknown_variables = sorted(name for name in variables - called_functions if name not in columns)
    issues = []
    if unknown_variables:
        issues.append("unknown variables: " + ", ".join(unknown_variables))
    if unknown_functions:
        issues.append("unknown functions: " + ", ".join(unknown_functions))
    return "; ".join(issues)


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
        performance_history_config: Optional[dict] = None,
        backtest_noqlib_config: Optional[dict] = None,
        error_feedback_sink=None,
        resource_governor_config: Optional[dict] = None,
        continuous_lock_dir: Optional[str] = None,
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
        self._performance_history_config = performance_history_config or {}
        self._backtest_noqlib_config = dict(backtest_noqlib_config or {})
        self._error_feedback_sink = error_feedback_sink
        self._resource_governor_config = resource_governor_config or {}
        self._continuous_lock_dir = continuous_lock_dir or "log/continuous/locks"
        from quantaalpha.continuous.resource_governor import FileLock

        self._resource_lock_factory = FileLock
        self._performance_history_store = None
        if self._performance_history_config.get("enabled", False):
            try:
                from quantaalpha.factor_ops.performance_history import PerformanceHistoryStore

                self._performance_history_store = PerformanceHistoryStore(
                    self._performance_history_config.get(
                        "root",
                        "third_party/quantaalpha/data/factorlib/performance_history",
                    ),
                    compression=self._performance_history_config.get("compression", "zstd"),
                )
            except Exception as e:
                logger.warning(f"Failed to initialize PerformanceHistoryStore: {e}")

    def _try_acquire_global_compute_lock(self, scheduler: str, run_id: str):
        from pathlib import Path

        from quantaalpha.continuous.resource_governor import (
            GovernorConfig,
            ResourceRequest,
            ResourceState,
            current_memory_usage_gb,
            evaluate_resource_request,
        )

        config = GovernorConfig.from_dict(getattr(self, "_resource_governor_config", {}))
        if not config.enabled:
            return None, None
        memory_usage_probe = getattr(self, "_memory_usage_probe", current_memory_usage_gb)
        decision = evaluate_resource_request(
            ResourceRequest(scheduler=scheduler, run_id=run_id),
            ResourceState(memory_usage_gb=memory_usage_probe()),
            config,
        )
        if not decision.allowed:
            return None, {"event": "resource_decision", **decision.to_dict()}
        lock_path = Path(getattr(self, "_continuous_lock_dir", "log/continuous/locks")) / "global_compute_lock.lock"
        lock_factory = getattr(self, "_resource_lock_factory", None)
        if lock_factory is None:
            from quantaalpha.continuous.resource_governor import FileLock

            lock_factory = FileLock
        lock = lock_factory(
            lock_path,
            timeout_seconds=0,
            owner=scheduler,
            run_id=run_id,
        )
        if lock.acquire():
            return lock, {
                "event": "resource_decision",
                "allowed": True,
                "action": "acquire",
                "reason": "resource_envelope_available",
                "scheduler": scheduler,
                "run_id": run_id,
                "lock_name": "global_compute_lock",
            }
        return None, {
            "event": "resource_decision",
            "allowed": False,
            "action": "defer",
            "reason": "global_compute_lock_held",
            "scheduler": scheduler,
            "run_id": run_id,
            "lock_name": "global_compute_lock",
        }

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
        import uuid

        start_time = dt.now()
        result = RevalidationResult(timestamp=start_time)
        lock, governance_event = self._try_acquire_global_compute_lock(
            scheduler="revalidation",
            run_id=str(uuid.uuid4())[:8],
        )
        if governance_event:
            result.governance_events.append(governance_event)
        if governance_event and not governance_event["allowed"]:
            if governance_event["reason"] == "memory_soft_limit_exceeded":
                result.errors.append("memory soft limit exceeded")
            else:
                result.errors.append("global compute lock held")
            result.duration_seconds = (dt.now() - start_time).total_seconds()
            self._update_next_run()
            return result

        try:
            facade = None
            library = None

            # Use provided candidates or query library
            if candidates is None:
                if getattr(self, "library_backend", "json") == "parquet":
                    # Parquet backend: read through FactorStoreFacade
                    from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                    facade = FactorStoreFacade(
                        store_path=self.parquet_library_dir,
                        lock_dir=self._continuous_lock_dir,
                    )
                    all_records = facade.read_effective_factor_records()
                    candidates = select_revalidation_candidates_by_lifecycle(
                        all_records,
                        days_threshold=self.days_threshold,
                    )
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

                            facade = FactorStoreFacade(
                                store_path=self.parquet_library_dir,
                                lock_dir=self._continuous_lock_dir,
                            )
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
        finally:
            if lock is not None:
                lock.release()

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
            passed = self._run_with_timeout(
                self._backtest_runner,
                factor_id,
                factor_entry,
                self._per_factor_timeout_seconds,
            )
            self._record_performance_history(
                factor_id=factor_id,
                factor_entry=factor_entry,
                status="success" if passed else "failure",
                error_message=None if passed else "Injected backtest_runner returned failure",
            )
            return passed

        # Default path: use FactorExecutor from glue if available
        try:
            try:
                from third_party.glue.factor_executor import FactorExecutor
            except ImportError:
                from glue.factor_executor import FactorExecutor

            # Get factor expression
            expression = factor_entry.get("factor_expression", "")
            if not expression:
                logger.warning(f"Factor {factor_id} has no expression, skipping backtest")
                return False
            translated_expression, translation_warnings = _translate_factor_expression(expression)
            if translation_warnings:
                logger.info(f"Translation warnings for {factor_id}: {'; '.join(translation_warnings)}")
            unsupported_warning = self._unsupported_translation_warning(translation_warnings)
            if unsupported_warning:
                logger.warning(f"Factor {factor_id} has unsupported expression after translation: {unsupported_warning}")
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    status="failure",
                    translated_expression=translated_expression,
                    error_message=f"Unsupported expression after translation: {unsupported_warning}",
                )
                return False
            arity_warning = self._operator_arity_warning(translated_expression)
            if arity_warning:
                logger.warning(f"Factor {factor_id} has invalid expression arity after translation: {arity_warning}")
                factor_errors = [
                    build_factor_error(
                        factor_id=factor_id,
                        expression=expression,
                        error_type="arity",
                        error_message=arity_warning,
                        source="revalidation",
                    )
                ]
                self._last_factor_errors = factor_errors
                if self._error_feedback_sink is not None:
                    self._error_feedback_sink.extend(factor_errors)
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    status="failure",
                    translated_expression=translated_expression,
                    error_message=f"Invalid expression arity after translation: {arity_warning}",
                )
                return False
            budget_warning = self._backtest_budget_warning(translated_expression)
            if budget_warning:
                logger.warning(f"Factor {factor_id} skipped before backtest: {budget_warning}")
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    status="failure",
                    translated_expression=translated_expression,
                    error_message=budget_warning,
                )
                return False

            # Get periods from configured execution periods
            train_period = self._execution_periods.get("train", ("2020-01-01", "2022-12-31"))
            valid_period = self._execution_periods.get("valid", ("2023-01-01", "2023-12-31"))
            test_period = self._execution_periods.get("test", ("2024-01-01", "2024-12-31"))

            df = self._get_execution_dataframe()

            if self._data_bridge is not None and (df is None or df.is_empty()):
                logger.warning(f"No data available for backtest of {factor_id}")
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    status="failure",
                    translated_expression=translated_expression,
                    error_message=f"No data available for backtest of {factor_id}",
                )
                return False

            compatibility_warning = _vnpy_expression_compatibility_warning(
                translated_expression,
                set(df.columns) if df is not None else set(),
            )
            if compatibility_warning:
                logger.warning(
                    f"Factor {factor_id} skipped before backtest: expression incompatible with current execution frame: "
                    f"{compatibility_warning}"
                )
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    status="failure",
                    translated_expression=translated_expression,
                    error_message=f"Expression incompatible with current execution frame: {compatibility_warning}",
                )
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
                    self._log_revalidation_metrics(factor_id, result.ic_result)
                    logger.info(f"Factor {factor_id} passed backtest with IC={result.ic_value:.4f}")
                    self._record_performance_history(
                        factor_id=factor_id,
                        factor_entry=factor_entry,
                        status="success",
                        translated_expression=translated_expression,
                        ic_result=result.ic_result,
                        ic_mean=result.ic_value,
                        computation_time_seconds=total_seconds,
                    )
                    return True
                else:
                    logger.info(f"profile.revalidation.factor.done factor={factor_id} success=False total_seconds={total_seconds:.3f} ic_value={result.ic_value:.6f}")
                    self._log_revalidation_metrics(factor_id, result.ic_result)
                    logger.info(f"Factor {factor_id} did not meet IC threshold: {result.ic_value:.4f} < {self.min_ic}")
                    self._record_performance_history(
                        factor_id=factor_id,
                        factor_entry=factor_entry,
                        status="failure",
                        translated_expression=translated_expression,
                        ic_result=result.ic_result,
                        ic_mean=result.ic_value,
                        computation_time_seconds=total_seconds,
                        error_message=f"IC={result.ic_value:.4f} < {self.min_ic}",
                    )
                    return False
            else:
                error_msg = result.error_message or "IC unavailable after execution"
                logger.info(f"profile.revalidation.factor.done factor={factor_id} success=False total_seconds={total_seconds:.3f} error={error_msg}")
                logger.warning(f"Factor {factor_id} backtest failed: {error_msg}")
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    status="failure",
                    translated_expression=translated_expression,
                    computation_time_seconds=total_seconds,
                    error_message=error_msg,
                )
                return False

        except ImportError as e:
            logger.warning(f"FactorExecutor not available: {e}, backtest returning False")
            self._record_performance_history(
                factor_id=factor_id,
                factor_entry=factor_entry,
                status="failure",
                error_message=f"FactorExecutor not available: {e}",
            )
            return False
        except Exception as e:
            logger.error(f"Error running backtest for {factor_id}: {e}")
            self._record_performance_history(
                factor_id=factor_id,
                factor_entry=factor_entry,
                status="failure",
                error_message=str(e),
            )
            return False

    def _unsupported_translation_warning(self, translation_warnings: list[str]) -> Optional[str]:
        return unsupported_translation_warning(translation_warnings)

    def _backtest_budget_warning(self, translated_expression: str) -> Optional[str]:
        if self._per_factor_timeout_seconds <= 0:
            return None
        expensive_counts = {
            operator: len(re.findall(rf"\b{operator}\(", translated_expression))
            for operator in ("ts_regresi", "ts_regbeta", "ts_slope", "ts_resi")
        }
        repeated = {operator: count for operator, count in expensive_counts.items() if count > 1}
        if not repeated:
            return None
        repeated_text = ", ".join(f"{operator}={count}" for operator, count in sorted(repeated.items()))
        return (
            "per-factor budget risk: repeated expensive operator(s) "
            f"{repeated_text}; timeout={self._per_factor_timeout_seconds}s"
        )

    def _operator_arity_warning(self, translated_expression: str) -> Optional[str]:
        return operator_arity_warning(translated_expression)

    def _iter_call_args(self, expression: str, operator: str) -> list[list[str]]:
        return iter_call_args(expression, operator)

    def _split_top_level_args(self, args_text: str) -> list[str]:
        return split_top_level_args(args_text)

    def _log_revalidation_metrics(self, factor_id: str, ic_result: object | None) -> None:
        if ic_result is None:
            return
        ic_mean = self._metric_float(ic_result, "ic_mean")
        ic_std = self._metric_float(ic_result, "ic_std")
        icir = self._metric_float(ic_result, "icir")
        positive_ratio = self._metric_float(ic_result, "positive_ratio")
        daily_ic_count = getattr(ic_result, "daily_ic_count", None)
        if None in {ic_mean, ic_std, icir, positive_ratio} or not isinstance(daily_ic_count, int):
            return
        logger.info(
            "profile.revalidation.metrics "
            f"factor={factor_id} "
            f"ic_mean={ic_mean:.6f} "
            f"ic_std={ic_std:.6f} "
            f"icir={icir:.6f} "
            f"positive_ratio={positive_ratio:.6f} "
            f"daily_ic_count={daily_ic_count}"
            f"{self._return_metric_log_suffix(ic_result)}"
        )

    def _metric_float(self, obj: object, name: str) -> float | None:
        value = getattr(obj, name, None)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _return_metric_log_suffix(self, ic_result: object) -> str:
        metrics = {
            "long_short_return_mean": self._metric_float(ic_result, "long_short_return_mean"),
            "long_short_return_annualized": self._metric_float(ic_result, "long_short_return_annualized"),
            "long_short_sharpe": self._metric_float(ic_result, "long_short_sharpe"),
            "long_short_max_drawdown": self._metric_float(ic_result, "long_short_max_drawdown"),
        }
        if any(value is None for value in metrics.values()):
            return ""
        return "".join(f" {name}={value:.6f}" for name, value in metrics.items())

    def _record_performance_history(
        self,
        *,
        factor_id: str,
        factor_entry: dict,
        status: str,
        translated_expression: str = "",
        ic_result: object | None = None,
        ic_mean: float | None = None,
        computation_time_seconds: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Append one revalidation result to the performance history store."""

        store = getattr(self, "_performance_history_store", None)
        if store is None:
            return

        try:
            from quantaalpha.factor_ops.performance_history import build_summary_row

            factor_expression = factor_entry.get("factor_expression", "")
            row = build_summary_row(
                factor_id=factor_id,
                factor_name=factor_entry.get("factor_name", factor_id),
                factor_expression=factor_expression,
                translated_expression=translated_expression or factor_expression,
                source="revalidation",
                validated_at=None,
                execution_periods=self._execution_periods,
                status=status,
                passed=status == "success",
                ic_mean=ic_mean,
                ic_std=getattr(ic_result, "ic_std", None) if ic_result is not None else None,
                icir=getattr(ic_result, "icir", None) if ic_result is not None else None,
                rank_ic_mean=getattr(ic_result, "rank_ic_mean", None) if ic_result is not None else None,
                rank_icir=getattr(ic_result, "rank_icir", None) if ic_result is not None else None,
                positive_ratio=getattr(ic_result, "positive_ratio", None) if ic_result is not None else None,
                daily_ic_count=getattr(ic_result, "daily_ic_count", None) if ic_result is not None else None,
                min_ic=self.min_ic,
                min_rank_ic=None,
                computation_time_seconds=computation_time_seconds,
                error_message=error_message,
            )
            store.append_summary(row)
            daily_ics = getattr(ic_result, "daily_ics", None) if ic_result is not None else None
            if daily_ics and self._performance_history_config.get("write_series", True):
                store.append_series(
                    factor_id=factor_id,
                    validation_id=row["validation_id"],
                    metric_name="daily_ic",
                    values=list(daily_ics),
                )
            if self._performance_history_config.get("update_latest_snapshot", True):
                store.refresh_latest_by_factor()
        except Exception as exc:
            logger.warning(f"Performance history write failed for {factor_id}: {exc}")

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
        Get execution DataFrame from bridge or configured app5 clean daily data.

        Returns:
            pl.DataFrame with price data, or empty DataFrame if no source is available.
        """

        if self._execution_dataframe_cache is not None:
            logger.info("Using cached execution DataFrame for backtest")
            return self._execution_dataframe_cache

        start_date, end_date = self._execution_date_window()

        if self._data_bridge is not None:
            try:
                logger.info(f"profile.load_price_data.start context=backtest source=bridge interfaces={['daily']} start_date={start_date} end_date={end_date}")
                load_start = time.time()
                df = self._data_bridge.load_price_data(
                    interfaces=["daily"],
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                )
                load_seconds = time.time() - load_start

                if df is not None and not df.is_empty():
                    logger.info(f"profile.load_price_data.done context=backtest source=bridge rows={len(df)} seconds={load_seconds:.3f}")
                    logger.info(f"Loaded {len(df)} rows from bridge for backtest")
                    self._execution_dataframe_cache = df
                    return self._execution_dataframe_cache

                logger.info(f"profile.load_price_data.done context=backtest source=bridge rows=0 seconds={load_seconds:.3f}")
                if self._resolve_app5_clean_daily_files():
                    logger.info("Bridge returned empty DataFrame; continuing with app5 clean daily data")
                else:
                    logger.warning("Bridge returned empty DataFrame")
            except Exception as e:
                logger.error(f"Error loading data from bridge: {e}")

        app5_df = self._load_app5_clean_execution_dataframe(start_date, end_date)
        if app5_df is not None and not app5_df.is_empty():
            self._execution_dataframe_cache = app5_df
            return self._execution_dataframe_cache

        logger.info("No execution price data available, using empty DataFrame")
        self._execution_dataframe_cache = self._empty_execution_dataframe()
        return self._execution_dataframe_cache

    def _execution_date_window(self) -> tuple[str, str]:
        """Return the widest configured train/valid/test date window."""
        train_period = self._execution_periods.get("train", ("2020-01-01", "2022-12-31"))
        valid_period = self._execution_periods.get("valid", ("2023-01-01", "2023-12-31"))
        test_period = self._execution_periods.get("test", ("2024-01-01", "2024-12-31"))
        return min(train_period[0], valid_period[0], test_period[0]), max(train_period[1], valid_period[1], test_period[1])

    def _empty_execution_dataframe(self):
        """Return the FactorExecutor-compatible empty price schema."""
        import polars as pl

        return pl.DataFrame(
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

    def _load_app5_clean_execution_dataframe(self, start_date: str, end_date: str):
        """Load app5 clean daily parquet data for revalidation backtests."""
        import polars as pl

        parquet_files = self._resolve_app5_clean_daily_files()
        if not parquet_files:
            return None

        load_start = time.time()
        logger.info(
            "profile.load_price_data.start "
            f"context=backtest source=app5_clean interface={self._backtest_noqlib_config.get('daily_interface', 'daily')} "
            f"start_date={start_date} end_date={end_date}"
        )
        try:
            scan_kwargs = {"missing_columns": "insert", "extra_columns": "ignore"}
            schema = pl.scan_parquet([str(path) for path in parquet_files], **scan_kwargs).collect_schema()
            date_col = self._first_existing_column(schema, ("datetime", "date", "trade_date", "cal_date", "trade_date_dt"))
            symbol_col = self._first_existing_column(schema, ("vt_symbol", "ts_code", "instrument", "symbol", "code"))
            volume_col = self._first_existing_column(schema, ("volume", "vol"))
            adjustment = str(
                self._backtest_noqlib_config.get("standard_frame", {}).get(
                    "adjustment",
                    self._backtest_noqlib_config.get("adjustment", "raw"),
                )
            ).lower()
            price_source_cols = {
                field: field if adjustment == "raw" else f"{field}_{adjustment}"
                for field in ("open", "high", "low", "close")
            }
            missing = [col for col in price_source_cols.values() if col not in schema]
            if date_col is None:
                missing.append("datetime/trade_date")
            if symbol_col is None:
                missing.append("vt_symbol/ts_code")
            if volume_col is None:
                missing.append("volume/vol")
            if missing:
                logger.warning(f"App5 clean daily data missing required columns: {missing}")
                return None

            from datetime import datetime as dt

            start_bound = dt.strptime(start_date, "%Y-%m-%d").date()
            end_bound = dt.strptime(end_date, "%Y-%m-%d").date()
            date_text = pl.col(date_col).cast(pl.Utf8)
            date_expr = pl.coalesce(
                date_text.str.strptime(pl.Date, "%Y-%m-%d", strict=False),
                date_text.str.strptime(pl.Date, "%Y%m%d", strict=False),
            )
            df = (
                pl.scan_parquet([str(path) for path in parquet_files], **scan_kwargs)
                .select(
                    date_expr.alias("datetime"),
                    pl.col(symbol_col).cast(pl.Utf8).alias("vt_symbol"),
                    pl.col(price_source_cols["open"]).cast(pl.Float64).alias("open"),
                    pl.col(price_source_cols["high"]).cast(pl.Float64).alias("high"),
                    pl.col(price_source_cols["low"]).cast(pl.Float64).alias("low"),
                    pl.col(price_source_cols["close"]).cast(pl.Float64).alias("close"),
                    pl.col(volume_col).cast(pl.Float64).alias("volume"),
                )
                .filter(pl.col("datetime").is_between(start_bound, end_bound))
                .sort(["datetime", "vt_symbol"])
                .collect()
            )
            load_seconds = time.time() - load_start
            logger.info(
                f"profile.load_price_data.done context=backtest source=app5_clean rows={len(df)} "
                f"seconds={load_seconds:.3f} files={len(parquet_files)}"
            )
            if df.is_empty():
                logger.warning("App5 clean daily data returned empty DataFrame for execution window")
                return None
            logger.info(f"Loaded {len(df)} rows from app5 clean daily data for backtest")
            return df
        except Exception as e:
            logger.error(f"Error loading app5 clean daily data: {e}")
            return None

    def _resolve_app5_clean_daily_files(self) -> list[Path]:
        """Resolve active app5 clean daily parquet files from manifest/current.json."""
        cfg = self._backtest_noqlib_config
        app5_storage_root = cfg.get("app5_storage_root")
        if not app5_storage_root:
            return []

        daily_interface = cfg.get("daily_interface", "daily")
        daily_root = Path(app5_storage_root) / daily_interface
        manifest_path = daily_root / "manifest" / "current.json"
        active_files: list[str] = []
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                active_files = [str(item) for item in manifest.get("active_files", [])]
            except Exception as exc:
                logger.warning(f"Failed to read app5 daily manifest {manifest_path}: {exc}")
        else:
            active_dir = daily_root / "clean" / "active"
            if active_dir.exists():
                active_files = [str(path.relative_to(daily_root)) for path in sorted(active_dir.glob("*.parquet"))]

        parquet_files = [(daily_root / item).resolve() for item in active_files]
        existing_files = [path for path in parquet_files if path.exists()]
        missing_files = [str(path) for path in parquet_files if not path.exists()]
        if missing_files:
            logger.warning(f"App5 clean daily manifest references missing files: {missing_files}")
        return existing_files

    def _first_existing_column(self, schema, candidates: tuple[str, ...]) -> Optional[str]:
        for candidate in candidates:
            if candidate in schema:
                return candidate
        return None
