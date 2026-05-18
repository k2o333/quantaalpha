from __future__ import annotations

from .expression_quality import build_factor_error, operator_arity_warning, unsupported_translation_warning
from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


class MiningValidationMixin:
    """Responsibility slice for DefaultMiningScheduler."""

    def _run_monitor_hook(
        self,
        factor_id: str,
        factor_entry: dict,
        ic_result,
        df,
    ) -> None:
        """
        Post-validation monitor hook: automatically generate IC/Quantile/Turnover analysis
        and write to storage.

        Design principles:
        - fail-safe: any exception only logs, does not raise
        - Reuses already-loaded df and ic_result, no re-computation
        - Writes to monitor_output_path under Parquet partition

        Args:
            factor_id: Factor ID
            factor_entry: Complete factor entry dict
            ic_result: Pre-computed IC result object
            df: Pre-loaded price DataFrame
        """
        if self._monitor_engine is None:
            return

        try:
            from factor_monitor.core import FactorMonitorEngine, FactorMonitorConfig

            monitor_config = FactorMonitorConfig(
                factor_name=factor_id,
            )

            # Re-use existing IC result to avoid re-computation
            self._monitor_engine.analyze_and_save(
                factor_data=None,  # Let engine extract from ic_result
                price_data=df,
                ic_result=ic_result,
                config=monitor_config,
                save=True,
            )

            logger.info(f"Monitor hook completed for {factor_id}")
        except Exception as e:
            # Monitor failure does not block main pipeline
            import traceback

            logger.warning(f"Monitor hook failed for {factor_id}: {e}\n{traceback.format_exc()}")

    def _enrich_validation_result(
        self,
        result: dict | None,
        *,
        elapsed_ms: int | None = None,
        ic_result: object | None = None,
    ) -> dict | None:
        """Enrich validation result with flat field metrics for consumers.

        Adds top-level IC, ICIR, Rank IC, Rank ICIR, positive_ratio, and
        validation_elapsed_ms while preserving the existing summary structure.
        """
        if result is None:
            return None
        enriched = dict(result)
        summary = dict(enriched.get("summary", {}) or {})

        ic_mean = summary.get("ic_mean")
        rank_ic_mean = summary.get("rank_ic_mean")
        positive_ratio = summary.get("positive_ratio")
        if positive_ratio is None and ic_result is not None:
            positive_ratio = getattr(ic_result, "positive_ratio", None)

        enriched.setdefault("IC", ic_mean)
        enriched.setdefault("ICIR", getattr(ic_result, "icir", None) if ic_result is not None else None)
        enriched.setdefault("Rank IC", rank_ic_mean)
        if ic_result is not None and hasattr(ic_result, "rank_icir"):
            enriched.setdefault("Rank ICIR", getattr(ic_result, "rank_icir"))
        enriched.setdefault("positive_ratio", positive_ratio)
        if elapsed_ms is not None:
            enriched.setdefault("validation_elapsed_ms", elapsed_ms)
        return enriched

    def _record_performance_history(
        self,
        *,
        factor_id: str,
        factor_entry: dict,
        validation_result: dict | None,
        source: str,
        translated_expression: str = "",
        ic_result: object | None = None,
        computation_time_seconds: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Append single-factor validation result to the performance history store."""

        store = getattr(self, "_performance_history_store", None)
        if store is None or validation_result is None:
            return

        try:
            from quantaalpha.factor_ops.performance_history import build_summary_row

            summary = validation_result.get("summary", {}) or {}
            status = validation_result.get("status", "failure")
            factor_expression = factor_entry.get("factor_expression", "")
            row = build_summary_row(
                factor_id=factor_id,
                factor_name=factor_entry.get("factor_name", factor_id),
                factor_expression=factor_expression,
                translated_expression=translated_expression or factor_expression,
                source=source,
                validated_at=None,
                execution_periods=self._execution_periods,
                status=status,
                passed=status == "success",
                ic_mean=summary.get("ic_mean"),
                ic_std=getattr(ic_result, "ic_std", None) if ic_result is not None else None,
                icir=getattr(ic_result, "icir", None) if ic_result is not None else validation_result.get("ICIR"),
                rank_ic_mean=summary.get("rank_ic_mean", validation_result.get("Rank IC")),
                rank_icir=getattr(ic_result, "rank_icir", None) if ic_result is not None else validation_result.get("Rank ICIR"),
                positive_ratio=summary.get("positive_ratio", validation_result.get("positive_ratio")),
                daily_ic_count=getattr(ic_result, "daily_ic_count", None) if ic_result is not None else None,
                min_ic=self.min_ic,
                min_rank_ic=self.min_rank_ic,
                computation_time_seconds=computation_time_seconds,
                error_message=error_message,
                extra={"validation_result": validation_result},
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
        except Exception as e:
            logger.warning(f"Performance history write failed for {factor_id}: {e}")

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
        validation_started = time.time()
        logger.info(f"Validating factor {factor_id}")

        # Use injected validator if provided
        if self._factor_validator is not None:
            result = self._validate_with_timeout(
                self._factor_validator,
                factor_id,
                factor_entry,
                self._per_factor_timeout_seconds,
            )

            # Monitor Hook (fail-safe) - called on validation success in injected path
            if result and result.get("status") == "success" and self._monitor_engine is not None:
                try:
                    self._run_monitor_hook(
                        factor_id=factor_id,
                        factor_entry=factor_entry,
                        ic_result=None,
                        df=None,
                    )
                except Exception as e:
                    import traceback

                    logger.warning(f"Monitor hook failed for {factor_id}: {e}\n{traceback.format_exc()}")

            # Enrich injected validator result with timing
            elapsed_ms = int((time.time() - validation_started) * 1000)
            validation_result = self._enrich_validation_result(result, elapsed_ms=elapsed_ms)
            self._record_performance_history(
                factor_id=factor_id,
                factor_entry=factor_entry,
                validation_result=validation_result,
                source="mining_validation",
                error_message=None if validation_result and validation_result.get("status") == "success" else "Injected validator returned failure",
            )
            return validation_result

        # Default validation path using FactorExecutor
        try:
            try:
                from third_party.glue.factor_executor import FactorExecutor
            except ImportError:
                from glue.factor_executor import FactorExecutor

            factor_start = time.time()
            logger.info(f"profile.validation.factor.start factor={factor_id}")

            expression = factor_entry.get("factor_expression", "")
            if not expression:
                elapsed_ms = int((time.time() - validation_started) * 1000)
                return self._enrich_validation_result(
                    {
                        "status": "failure",
                        "summary": {
                            "stability_score": None,
                            "validation_summary": f"No expression for {factor_id}",
                            "ic_mean": None,
                            "rank_ic_mean": None,
                        },
                    },
                    elapsed_ms=elapsed_ms,
                )
            translated_expression, translation_warnings = _translate_factor_expression(expression)
            if translation_warnings:
                logger.info(f"Translation warnings for {factor_id}: {'; '.join(translation_warnings)}")
            unsupported_warning = unsupported_translation_warning(translation_warnings)
            if unsupported_warning:
                elapsed_ms = int((time.time() - validation_started) * 1000)
                validation_result = self._enrich_validation_result(
                    {
                        "status": "failure",
                        "summary": {
                            "stability_score": None,
                            "validation_summary": f"Unsupported expression after translation: {unsupported_warning}",
                            "ic_mean": None,
                            "rank_ic_mean": None,
                        },
                    },
                    elapsed_ms=elapsed_ms,
                )
                factor_errors = [
                    build_factor_error(
                        factor_id=factor_id,
                        expression=expression,
                        error_type="translate",
                        error_message=unsupported_warning,
                        source="mining_validation",
                    )
                ]
                self._last_factor_errors = factor_errors
                if getattr(self, "_error_feedback_sink", None) is not None:
                    self._error_feedback_sink.extend(factor_errors)
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    validation_result=validation_result,
                    source="mining_validation",
                    translated_expression=translated_expression,
                    error_message=f"Unsupported expression after translation: {unsupported_warning}",
                )
                return validation_result

            arity_warning = operator_arity_warning(translated_expression)
            if arity_warning:
                elapsed_ms = int((time.time() - validation_started) * 1000)
                validation_result = self._enrich_validation_result(
                    {
                        "status": "failure",
                        "summary": {
                            "stability_score": None,
                            "validation_summary": f"Invalid expression arity after translation: {arity_warning}",
                            "ic_mean": None,
                            "rank_ic_mean": None,
                        },
                    },
                    elapsed_ms=elapsed_ms,
                )
                factor_errors = [
                    build_factor_error(
                        factor_id=factor_id,
                        expression=expression,
                        error_type="arity",
                        error_message=arity_warning,
                        source="mining_validation",
                    )
                ]
                self._last_factor_errors = factor_errors
                if getattr(self, "_error_feedback_sink", None) is not None:
                    self._error_feedback_sink.extend(factor_errors)
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    validation_result=validation_result,
                    source="mining_validation",
                    translated_expression=translated_expression,
                    error_message=f"Invalid expression arity after translation: {arity_warning}",
                )
                return validation_result

            # Validation thresholds - use instance configuration
            min_ic = self.min_ic
            min_rank_ic = self.min_rank_ic

            # Get periods from configured execution periods
            train_period = self._execution_periods.get("train", ("2020-01-01", "2022-12-31"))
            valid_period = self._execution_periods.get("valid", ("2023-01-01", "2023-12-31"))
            test_period = self._execution_periods.get("test", ("2024-01-01", "2024-12-31"))

            import polars as pl

            # Load data from bridge if available
            df = self._get_execution_dataframe()

            # Only fail if bridge was configured but returned empty/no data
            # When bridge is not configured, use empty placeholder for backward compatibility
            if self._data_bridge is not None and (df is None or df.is_empty()):
                logger.warning(f"No data available from bridge for validation of {factor_id}")
                elapsed_ms = int((time.time() - validation_started) * 1000)
                validation_result = self._enrich_validation_result(
                    {
                        "status": "failure",
                        "summary": {
                            "stability_score": None,
                            "validation_summary": f"No data available for validation of {factor_id}",
                            "ic_mean": None,
                            "rank_ic_mean": None,
                        },
                    },
                    elapsed_ms=elapsed_ms,
                )
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    validation_result=validation_result,
                    source="mining_validation",
                    translated_expression=translated_expression,
                    error_message=f"No data available for validation of {factor_id}",
                )
                return validation_result

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
                ic_mean = result.ic_value
                ic_result = result.ic_result

                # Determine if IC passes threshold
                passes_ic = abs(ic_mean) >= min_ic

                # Check rank IC if available and is a valid number
                rank_ic_mean = None
                passes_rank_ic = True
                if ic_result and hasattr(ic_result, "rank_ic_mean"):
                    raw_rank_ic = ic_result.rank_ic_mean
                    if raw_rank_ic is not None and isinstance(raw_rank_ic, (int, float)):
                        rank_ic_mean = raw_rank_ic
                        passes_rank_ic = rank_ic_mean >= min_rank_ic

                # Compute stability score (simple heuristic)
                stability_score = 0.5
                if ic_result:
                    # Use ICIR as stability indicator
                    icir = ic_result.icir
                    stability_score = min(1.0, max(0.0, (icir + 1) / 2))

                passes_validation = passes_ic and passes_rank_ic

                if passes_validation:
                    logger.info(f"profile.validation.factor.done factor={factor_id} success=True total_seconds={total_seconds:.3f} ic_value={ic_mean:.6f}")

                    # Monitor Hook (fail-safe) - does not block validation
                    if self._monitor_engine is not None:
                        try:
                            self._run_monitor_hook(
                                factor_id=factor_id,
                                factor_entry=factor_entry,
                                ic_result=ic_result,
                                df=df,
                            )
                        except Exception as e:
                            import traceback

                            logger.warning(f"Monitor hook failed for {factor_id}: {e}\n{traceback.format_exc()}")

                    elapsed_ms = int((time.time() - validation_started) * 1000)
                    validation_result = self._enrich_validation_result(
                        {
                            "status": "success",
                            "summary": {
                                "stability_score": stability_score,
                                "validation_summary": f"Factor {factor_id} passed with IC={ic_mean:.4f}",
                                "ic_mean": ic_mean,
                                "rank_ic_mean": rank_ic_mean,
                                "positive_ratio": ic_result.positive_ratio if ic_result else None,
                            },
                        },
                        elapsed_ms=elapsed_ms,
                        ic_result=ic_result,
                    )
                    self._record_performance_history(
                        factor_id=factor_id,
                        factor_entry=factor_entry,
                        validation_result=validation_result,
                        source="mining_validation",
                        translated_expression=translated_expression,
                        ic_result=ic_result,
                        computation_time_seconds=total_seconds,
                    )
                    return validation_result
                else:
                    logger.info(f"profile.validation.factor.done factor={factor_id} success=False total_seconds={total_seconds:.3f} ic_value={ic_mean:.6f}")
                    # Build failure reason
                    if not passes_ic:
                        failure_reason = f"IC={ic_mean:.4f} < {min_ic}"
                    else:
                        failure_reason = f"rank_ic={rank_ic_mean:.4f} < {min_rank_ic}"
                    elapsed_ms = int((time.time() - validation_started) * 1000)
                    validation_result = self._enrich_validation_result(
                        {
                            "status": "failure",
                            "summary": {
                                "stability_score": stability_score,
                                "validation_summary": f"Factor {factor_id} failed {failure_reason}",
                                "ic_mean": ic_mean,
                                "rank_ic_mean": rank_ic_mean,
                            },
                        },
                        elapsed_ms=elapsed_ms,
                        ic_result=ic_result,
                    )
                    self._record_performance_history(
                        factor_id=factor_id,
                        factor_entry=factor_entry,
                        validation_result=validation_result,
                        source="mining_validation",
                        translated_expression=translated_expression,
                        ic_result=ic_result,
                        computation_time_seconds=total_seconds,
                        error_message=failure_reason,
                    )
                    return validation_result
            else:
                error_msg = result.error_message or "IC unavailable after execution"
                logger.info(f"profile.validation.factor.done factor={factor_id} success=False total_seconds={total_seconds:.3f} error={error_msg}")
                elapsed_ms = int((time.time() - validation_started) * 1000)
                validation_result = self._enrich_validation_result(
                    {
                        "status": "failure",
                        "summary": {
                            "stability_score": None,
                            "validation_summary": f"Execution error: {error_msg}",
                            "ic_mean": None,
                            "rank_ic_mean": None,
                        },
                    },
                    elapsed_ms=elapsed_ms,
                )
                self._record_performance_history(
                    factor_id=factor_id,
                    factor_entry=factor_entry,
                    validation_result=validation_result,
                    source="mining_validation",
                    translated_expression=translated_expression,
                    computation_time_seconds=total_seconds,
                    error_message=error_msg,
                )
                return validation_result

        except ImportError as e:
            logger.warning(f"FactorExecutor not available: {e}, validation returning failure")
            elapsed_ms = int((time.time() - validation_started) * 1000)
            validation_result = self._enrich_validation_result(
                {
                    "status": "failure",
                    "summary": {
                        "stability_score": None,
                        "validation_summary": f"Validation unavailable: {e}",
                        "ic_mean": None,
                        "rank_ic_mean": None,
                    },
                },
                elapsed_ms=elapsed_ms,
            )
            self._record_performance_history(
                factor_id=factor_id,
                factor_entry=factor_entry,
                validation_result=validation_result,
                source="mining_validation",
                error_message=f"Validation unavailable: {e}",
            )
            return validation_result
        except Exception as e:
            logger.error(f"Error validating factor {factor_id}: {e}")
            elapsed_ms = int((time.time() - validation_started) * 1000)
            validation_result = self._enrich_validation_result(
                {
                    "status": "failure",
                    "summary": {
                        "stability_score": None,
                        "validation_summary": f"Validation error: {str(e)}",
                        "ic_mean": None,
                        "rank_ic_mean": None,
                    },
                },
                elapsed_ms=elapsed_ms,
            )
            self._record_performance_history(
                factor_id=factor_id,
                factor_entry=factor_entry,
                validation_result=validation_result,
                source="mining_validation",
                error_message=str(e),
            )
            return validation_result

    def _validate_with_timeout(
        self,
        validator: Callable,
        factor_id: str,
        factor_entry: dict,
        timeout_seconds: int,
    ) -> Optional[dict]:
        """
        Run a validator with timeout enforcement.

        Args:
            validator: Validator function to run
            factor_id: Factor ID for logging
            factor_entry: Factor entry dict
            timeout_seconds: Maximum seconds to allow

        Returns:
            Validation result dict if completed before timeout, failure dict if timed out.
            None indicates uncertain result.
        """
        from threading import Thread, Event

        result = {"value": None, "exception": None}
        done_event = Event()

        def run_validator():
            try:
                result["value"] = validator(factor_id, factor_entry)
            except Exception as e:
                result["exception"] = e
            finally:
                done_event.set()

        thread = Thread(target=run_validator, daemon=True)
        thread.start()

        if not done_event.wait(timeout=timeout_seconds):
            logger.warning(
                f"per_factor_timeout: {factor_id} exceeded {timeout_seconds}s limit, interrupting validation",
            )
            return {
                "status": "failure",
                "summary": {
                    "stability_score": None,
                    "validation_summary": f"Validation timeout after {timeout_seconds}s (per_factor_timeout)",
                    "ic_mean": None,
                    "rank_ic_mean": None,
                },
            }

        if result["exception"] is not None:
            logger.error(f"Exception in validator for {factor_id}: {result['exception']}")
            return {
                "status": "failure",
                "summary": {
                    "stability_score": None,
                    "validation_summary": f"Validation error: {str(result['exception'])}",
                    "ic_mean": None,
                    "rank_ic_mean": None,
                },
            }

        return result["value"]

    def _get_execution_dataframe(self):
        """
        Get execution DataFrame from bridge if available.

        Returns:
            pl.DataFrame with price data, or empty DataFrame if bridge unavailable.
        """
        import polars as pl

        if self._execution_dataframe_cache is not None:
            logger.info("Using cached execution DataFrame for validation")
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

            logger.info(f"profile.load_price_data.start context=validation interfaces={['daily']} start_date={start_date} end_date={end_date}")
            load_start = time.time()
            df = self._data_bridge.load_price_data(
                interfaces=["daily"],
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            load_seconds = time.time() - load_start

            if df is None or df.is_empty():
                logger.info(f"profile.load_price_data.done context=validation rows=0 seconds={load_seconds:.3f}")
                logger.warning("Bridge returned empty DataFrame")
                self._execution_dataframe_cache = df if df is not None else pl.DataFrame()
                return self._execution_dataframe_cache

            logger.info(f"profile.load_price_data.done context=validation rows={len(df)} seconds={load_seconds:.3f}")
            logger.info(f"Loaded {len(df)} rows from bridge for validation")
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
