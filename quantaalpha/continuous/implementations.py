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

RETURN_ALIAS_EXPRESSION = "(close / ts_delay(close, 1) - 1)"


def _translate_factor_expression(expression: str) -> tuple[str, list[str]]:
    """Translate QuantaAlpha factor syntax into the vnpy-compatible expression dialect."""
    if not expression:
        return "", []

    try:
        import re
        from third_party.glue.expression_translator import ExpressionTranslator

        translator = ExpressionTranslator()
        translated, warnings = translator.translate(expression)
        translated = re.sub(r"\breturn\b", RETURN_ALIAS_EXPRESSION, translated)
        return translated, warnings
    except Exception as exc:
        logger.warning(f"Expression translation failed, using raw expression: {exc}")
        return expression, [str(exc)]


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
        data_bridge=None,
        execution_periods: Optional[dict] = None,
    ):
        import os

        self.days_threshold = days_threshold
        self.max_per_run = max_per_run
        self.interval_hours = interval_hours
        self.library_path = library_path or os.environ.get(
            "FACTOR_LIBRARY_PATH", "third_party/quantaalpha/data/factorlib/all_factors_library.json"
        )
        self._backtest_runner = backtest_runner
        self._data_bridge = data_bridge
        self._execution_periods = execution_periods or {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }
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
            from quantaalpha.factors.library import FactorLibraryManager

            library = FactorLibraryManager(self.library_path)

            # Use provided candidates or query library
            if candidates is None:
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

        # Use injected runner if provided
        if self._backtest_runner is not None:
            return self._backtest_runner(factor_id, factor_entry)

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
                logger.debug(
                    "Translation warnings for %s: %s",
                    factor_id,
                    "; ".join(translation_warnings),
                )

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

            if result.success and result.ic_value is not None:
                # Check against validation thresholds
                min_ic = 0.02  # From pipeline.yaml validation.min_ic
                if result.ic_value >= min_ic:
                    logger.info(f"Factor {factor_id} passed backtest with IC={result.ic_value:.4f}")
                    return True
                else:
                    logger.info(f"Factor {factor_id} failed IC threshold: {result.ic_value:.4f} < {min_ic}")
                    return False
            else:
                error_msg = result.error_message or "IC unavailable after execution"
                logger.warning(f"Factor {factor_id} backtest failed: {error_msg}")
                return False

        except ImportError as e:
            logger.warning(f"FactorExecutor not available: {e}, backtest returning False")
            return False
        except Exception as e:
            logger.error(f"Error running backtest for {factor_id}: {e}")
            return False

    def _get_execution_dataframe(self):
        """
        Get execution DataFrame from bridge if available.

        Returns:
            pl.DataFrame with price data, or empty DataFrame if bridge unavailable.
        """
        import polars as pl

        if self._data_bridge is None:
            logger.debug("No data bridge configured, using empty DataFrame")
            return pl.DataFrame({
                "datetime": pl.Series(dtype=pl.Date),
                "vt_symbol": pl.Series(dtype=pl.String),
                "open": pl.Series(dtype=pl.Float64),
                "high": pl.Series(dtype=pl.Float64),
                "low": pl.Series(dtype=pl.Float64),
                "close": pl.Series(dtype=pl.Float64),
                "volume": pl.Series(dtype=pl.Float64),
            })

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

            df = self._data_bridge.load_price_data(
                interfaces=["daily"],
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )

            if df is None or df.is_empty():
                logger.warning("Bridge returned empty DataFrame")
                # Return empty DataFrame with correct schema for backward compatibility
                return pl.DataFrame({
                    "datetime": pl.Series(dtype=pl.Date),
                    "vt_symbol": pl.Series(dtype=pl.String),
                    "open": pl.Series(dtype=pl.Float64),
                    "high": pl.Series(dtype=pl.Float64),
                    "low": pl.Series(dtype=pl.Float64),
                    "close": pl.Series(dtype=pl.Float64),
                    "volume": pl.Series(dtype=pl.Float64),
                })

            logger.info(f"Loaded {len(df)} rows from bridge for backtest")
            return df

        except Exception as e:
            logger.error(f"Error loading data from bridge: {e}")
            return pl.DataFrame({
                "datetime": pl.Series(dtype=pl.Date),
                "vt_symbol": pl.Series(dtype=pl.String),
                "open": pl.Series(dtype=pl.Float64),
                "high": pl.Series(dtype=pl.Float64),
                "low": pl.Series(dtype=pl.Float64),
                "close": pl.Series(dtype=pl.Float64),
                "volume": pl.Series(dtype=pl.Float64),
            })


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
        data_bridge=None,
        execution_periods: Optional[dict] = None,
    ):
        import os

        self.max_per_run = max_per_run
        self.interval_hours = interval_hours
        self.library_path = library_path or os.environ.get(
            "FACTOR_LIBRARY_PATH", "third_party/quantaalpha/data/factorlib/all_factors_library.json"
        )
        self._factor_validator = factor_validator
        self._data_bridge = data_bridge
        self._execution_periods = execution_periods or {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }
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
        Retrieve context via RAG or fallback to library-based context.

        Returns:
            Context string for factor generation.
        """
        try:
            from quantaalpha.factors.fewshot import (
                query_active_factors_RAG,
                query_active_factors_jaccard,
                build_fewshot_context,
            )

            # Try RAG first, fall back to Jaccard
            try:
                results = query_active_factors_RAG(
                    query="",
                    top_k=10,
                    library_path=self.library_path,
                )
            except Exception:
                # Fallback to Jaccard similarity
                results = query_active_factors_jaccard(
                    query="",
                    top_k=10,
                    library_path=self.library_path,
                )

            if results and len(results) > 0:
                context = build_fewshot_context(
                    factors=results,
                    include_expression=True,
                    include_tags=True,
                    include_ic=True,
                )
                logger.debug(f"Retrieved context from {len(results)} active factors")
                return context
            else:
                logger.debug("No active factors found for context, using empty context")
                return ""

        except ImportError as e:
            logger.warning(f"RAG/fewshot module not available: {e}, building fallback context")
            return self._build_fallback_context()
        except Exception as e:
            logger.error(f"Error retrieving RAG context: {e}")
            return self._build_fallback_context()

    def _build_fallback_context(self) -> str:
        """
        Build context from recent active factors in the library without RAG.

        Returns:
            Context string from recent active factors.
        """
        try:
            from quantaalpha.factors.library import FactorLibraryManager

            library = FactorLibraryManager(self.library_path)

            # Get active factors sorted by last_validated
            candidates = library.select_revalidation_candidates(
                status="active",
            )

            if not candidates:
                # Fall back to any non-failed factors
                candidates = library.select_revalidation_candidates()

            if not candidates:
                return ""

            # Build simple context string
            lines = ["Recent active factors from the library:\n"]

            for i, factor in enumerate(candidates[:10], 1):
                lines.append(f"--- Factor {i} ---")
                lines.append(f"Name: {factor.get('factor_name', 'Unknown')}")
                expr = factor.get('factor_expression', '')
                if expr:
                    lines.append(f"Expression: {expr}")
                tags = factor.get('tags', {})
                if tags:
                    lines.append(f"Tags: {tags}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Error building fallback context: {e}")
            return ""

    def _generate_factors(self, context: str) -> list[dict]:
        """
        Generate new factors via bounded mutation or template-based approach.

        MVP strategy:
        1. If LLM client is available and configured, use it for generation
        2. Otherwise, use bounded mutation over recent active factors
           - Take active factor expressions as templates
           - Apply simple transformations (parameter variation, combination)
           - Normalize to library-compatible shape

        Args:
            context: RAG context from existing factors.

        Returns:
            List of generated factor entry dicts with keys:
            - factor_id: unique identifier
            - factor_name: human-readable name
            - factor_expression: the factor expression
            - tags: factor tags including data_dependency
            - evaluation: initial evaluation dict with status
        """
        logger.info("Generating new factors")

        generated_factors = []

        # Try LLM-based generation first
        llm_candidates = self._generate_via_llm(context)
        if llm_candidates:
            generated_factors.extend(llm_candidates)
            logger.info(f"Generated {len(llm_candidates)} factors via LLM")

        # Fallback to bounded mutation if no LLM candidates
        if not generated_factors:
            mutation_candidates = self._generate_via_mutation()
            generated_factors.extend(mutation_candidates)
            logger.info(f"Generated {len(mutation_candidates)} factors via mutation")

        # Deduplicate by expression
        seen_expressions = set()
        unique_factors = []
        for factor in generated_factors:
            expr = factor.get('factor_expression', '')
            if expr and expr not in seen_expressions:
                seen_expressions.add(expr)
                unique_factors.append(factor)

        return unique_factors[:self.max_per_run]

    def _generate_via_llm(self, context: str) -> list[dict]:
        """
        Generate factors via LLM client if available.

        Returns:
            List of generated factor dicts, or empty list if LLM unavailable.
        """
        try:
            from quantaalpha.llm.client import APIBackend

            client = APIBackend()

            # Build generation prompt
            prompt = self._build_generation_prompt(context)

            response = client.build_messages_and_create_chat_completion(
                user_prompt=prompt,
                system_prompt="You are a quantitative factor researcher. Generate novel alpha factors.",
            )

            if response:
                # Parse LLM response into factor dicts
                return self._parse_llm_response(response)
            return []

        except ImportError:
            logger.debug("LLM client not available")
            return []
        except Exception as e:
            logger.warning(f"LLM generation failed: {e}")
            return []

    def _build_generation_prompt(self, context: str) -> str:
        """Build prompt for factor generation."""
        prompt_parts = [
            "You are a quantitative factor researcher.",
            "",
            "Generate new factors that are different from existing ones.",
            "",
            "Existing similar factors:\n" + (context or "No existing factors available."),
            "",
            "Generate 3-5 new factors following these rules:",
            "1. Use $field syntax for data fields (e.g., $close, $volume, $open)",
            "2. Use operators: +, -, *, /, ts_, cs_, rank, delta, log",
            "3. Factors should be novel, not direct copies",
            "4. Return as JSON array of objects with keys: factor_name, factor_expression, tags",
            "",
            "Example: {\"factor_name\": \"volume_strength\", \"factor_expression\": \"$volume/ts_mean($volume,20)\", \"tags\": {\"data_dependency\": [\"price_volume\"]}}",
        ]
        return "\n".join(prompt_parts)

    def _parse_llm_response(self, response: str) -> list[dict]:
        """Parse LLM response into factor dicts."""
        import json
        import re

        factors = []

        try:
            # Try direct JSON parsing
            # Find JSON array in response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'factor_expression' in item:
                            factor = self._normalize_factor_entry(item)
                            factors.append(factor)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")

        return factors

    def _generate_via_mutation(self) -> list[dict]:
        """
        Generate factors via bounded mutation over recent active factors.

        Mutations applied:
        - Parameter variation: change time windows (5, 10, 20, 60)
        - Operator substitution: ts_mean -> ts_sum, rank -> cs_rank
        - Expression combination: blend two expressions

        Returns:
            List of mutated factor dicts.
        """
        try:
            from quantaalpha.factors.library import FactorLibraryManager

            library = FactorLibraryManager(self.library_path)

            # Get recent active factors as templates
            candidates = library.select_revalidation_candidates(
                status="active",
            )

            if not candidates:
                return []

            # Take up to 5 templates
            templates = candidates[:5]

            mutated = []
            import hashlib
            import time

            for template in templates:
                template_expr = template.get('factor_expression', '')
                if not template_expr:
                    continue

                # Generate mutations
                mutations = [
                    self._mutate_time_windows(template_expr),
                    self._mutate_operators(template_expr),
                    self._mutate_simple_variation(template_expr),
                ]

                for mutated_expr in mutations:
                    if mutated_expr and mutated_expr != template_expr:
                        # Create factor entry
                        factor_id = self._generate_mutated_factor_id(
                            template.get('factor_id', 'unknown'),
                            mutated_expr
                        )

                        mutated.append({
                            "factor_id": factor_id,
                            "factor_name": f"Mutated_{template.get('factor_name', 'Factor')}",
                            "factor_expression": mutated_expr,
                            "tags": template.get('tags', {}).copy(),
                            "evaluation": {
                                "status": "pending_validation",
                                "last_validated": None,
                                "stability_score": None,
                            },
                            "metadata": {
                                "source": "mutation",
                                "template_factor_id": template.get('factor_id'),
                            },
                        })

            return mutated

        except ImportError:
            logger.warning("Factor library not available for mutation")
            return []
        except Exception as e:
            logger.error(f"Error in mutation generation: {e}")
            return []

    def _mutate_time_windows(self, expression: str) -> str:
        """Replace time windows with variations."""
        import re

        # Replace common window sizes
        replacements = [
            (r'\b5\b', '10'),
            (r'\b10\b', '20'),
            (r'\b20\b', '60'),
            (r'\b60\b', '5'),
        ]

        result = expression
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)
        return result

    def _mutate_operators(self, expression: str) -> str:
        """Substitute operators."""
        # Only do one substitution pass to avoid undoing changes
        if 'ts_mean(' in expression:
            return expression.replace('ts_mean(', 'ts_sum(')
        elif 'ts_sum(' in expression:
            return expression.replace('ts_sum(', 'ts_mean(')
        elif 'cs_rank(' in expression:
            # cs_rank -> cs_rank is a no-op, try a different operator
            if 'ts_mean(' in expression:
                return expression.replace('ts_mean(', 'ts_sum(')
        return expression

    def _mutate_simple_variation(self, expression: str) -> str:
        """Apply simple variations."""
        # Add scaling factor
        if '$close' in expression:
            return f"({expression}) * 1.01"
        return f"{expression} / 2"

    def _generate_mutated_factor_id(self, template_id: str, expression: str) -> str:
        """Generate unique factor ID for mutated factor."""
        import hashlib

        content = f"{template_id}:{expression}"
        hash_val = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:8]
        return f"mut_{template_id}_{hash_val}"

    def _normalize_factor_entry(self, raw_entry: dict) -> dict:
        """
        Normalize a raw factor entry to library-compatible shape.

        Args:
            raw_entry: Raw factor dict potentially from LLM or mutation

        Returns:
            Normalized factor dict with required keys.
        """
        # Ensure required keys exist
        normalized = {
            "factor_id": raw_entry.get("factor_id", ""),
            "factor_name": raw_entry.get("factor_name", "Generated Factor"),
            "factor_expression": raw_entry.get("factor_expression", ""),
            "tags": raw_entry.get("tags", {}),
            "evaluation": raw_entry.get("evaluation", {
                "status": "pending_validation",
                "last_validated": None,
                "stability_score": None,
            }),
            "metadata": raw_entry.get("metadata", {}),
        }

        # Ensure factor_id is set
        if not normalized["factor_id"]:
            import uuid
            normalized["factor_id"] = f"gen_{uuid.uuid4().hex[:12]}"

        # Ensure tags have data_dependency
        if "data_dependency" not in normalized["tags"]:
            # Infer from expression
            expr = normalized["factor_expression"].lower()
            if any(k in expr for k in ["roe", "revenue", "profit", "margin"]):
                normalized["tags"]["data_dependency"] = ["financial"]
            elif any(k in expr for k in ["moneyflow", "margin", "净流入"]):
                normalized["tags"]["data_dependency"] = ["moneyflow"]
            elif any(k in expr for k in ["chip", "holder", "float"]):
                normalized["tags"]["data_dependency"] = ["chip"]
            else:
                normalized["tags"]["data_dependency"] = ["price_volume"]

        return normalized

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

        # Use injected validator if provided
        if self._factor_validator is not None:
            return self._factor_validator(factor_id, factor_entry)

        # Default validation path using FactorExecutor
        try:
            from third_party.glue.factor_executor import FactorExecutor

            expression = factor_entry.get("factor_expression", "")
            if not expression:
                return {
                    "status": "failure",
                    "summary": {
                        "stability_score": None,
                        "validation_summary": f"No expression for {factor_id}",
                        "ic_mean": None,
                        "rank_ic_mean": None,
                    },
                }
            translated_expression, translation_warnings = _translate_factor_expression(expression)
            if translation_warnings:
                logger.debug(
                    "Translation warnings for %s: %s",
                    factor_id,
                    "; ".join(translation_warnings),
                )

            # Validation thresholds from pipeline.yaml
            min_ic = 0.02
            min_rank_ic = 0.01

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
                return {
                    "status": "failure",
                    "summary": {
                        "stability_score": None,
                        "validation_summary": f"No data available for validation of {factor_id}",
                        "ic_mean": None,
                        "rank_ic_mean": None,
                    },
                }

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

            if result.success and result.ic_value is not None:
                ic_mean = result.ic_value
                ic_result = result.ic_result

                # Determine if IC passes threshold
                passes_ic = ic_mean >= min_ic

                # Compute stability score (simple heuristic)
                stability_score = 0.5
                if ic_result:
                    # Use ICIR as stability indicator
                    icir = ic_result.icir
                    stability_score = min(1.0, max(0.0, (icir + 1) / 2))

                if passes_ic:
                    return {
                        "status": "success",
                        "summary": {
                            "stability_score": stability_score,
                            "validation_summary": f"Factor {factor_id} passed with IC={ic_mean:.4f}",
                            "ic_mean": ic_mean,
                            "rank_ic_mean": None,  # Rank IC not computed in current executor
                            "positive_ratio": ic_result.positive_ratio if ic_result else None,
                        },
                    }
                else:
                    return {
                        "status": "failure",
                        "summary": {
                            "stability_score": stability_score,
                            "validation_summary": f"Factor {factor_id} failed IC={ic_mean:.4f} < {min_ic}",
                            "ic_mean": ic_mean,
                            "rank_ic_mean": None,
                        },
                    }
            else:
                error_msg = result.error_message or "IC unavailable after execution"
                return {
                    "status": "failure",
                    "summary": {
                        "stability_score": None,
                        "validation_summary": f"Execution error: {error_msg}",
                        "ic_mean": None,
                        "rank_ic_mean": None,
                    },
                }

        except ImportError as e:
            logger.warning(f"FactorExecutor not available: {e}, validation returning failure")
            return {
                "status": "failure",
                "summary": {
                    "stability_score": None,
                    "validation_summary": f"Validation unavailable: {e}",
                    "ic_mean": None,
                    "rank_ic_mean": None,
                },
            }
        except Exception as e:
            logger.error(f"Error validating factor {factor_id}: {e}")
            return {
                "status": "failure",
                "summary": {
                    "stability_score": None,
                    "validation_summary": f"Validation error: {str(e)}",
                    "ic_mean": None,
                    "rank_ic_mean": None,
                },
            }

    def _get_execution_dataframe(self):
        """
        Get execution DataFrame from bridge if available.

        Returns:
            pl.DataFrame with price data, or empty DataFrame if bridge unavailable.
        """
        import polars as pl

        if self._data_bridge is None:
            logger.debug("No data bridge configured, using empty DataFrame")
            return pl.DataFrame({
                "datetime": pl.Series(dtype=pl.Date),
                "vt_symbol": pl.Series(dtype=pl.String),
                "open": pl.Series(dtype=pl.Float64),
                "high": pl.Series(dtype=pl.Float64),
                "low": pl.Series(dtype=pl.Float64),
                "close": pl.Series(dtype=pl.Float64),
                "volume": pl.Series(dtype=pl.Float64),
            })

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

            df = self._data_bridge.load_price_data(
                interfaces=["daily"],
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )

            if df is None or df.is_empty():
                logger.warning("Bridge returned empty DataFrame")
                return df if df is not None else pl.DataFrame()

            logger.info(f"Loaded {len(df)} rows from bridge for validation")
            return df

        except Exception as e:
            logger.error(f"Error loading data from bridge: {e}")
            return pl.DataFrame({
                "datetime": pl.Series(dtype=pl.Date),
                "vt_symbol": pl.Series(dtype=pl.String),
                "open": pl.Series(dtype=pl.Float64),
                "high": pl.Series(dtype=pl.Float64),
                "low": pl.Series(dtype=pl.Float64),
                "close": pl.Series(dtype=pl.Float64),
                "volume": pl.Series(dtype=pl.Float64),
            })

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
