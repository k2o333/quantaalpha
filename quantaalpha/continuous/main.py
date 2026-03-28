"""
Runtime Entrypoint for 24H Continuous Factor MVP.

Provides two operational commands:
- `continuous start`: Long-running foreground loop with scheduling
- `continuous once`: Single deterministic cycle for testing/debugging

Both commands:
1. Load configuration from pipeline.yaml
2. Create orchestrator with wired app4 bridge and impact classifier
3. Execute cycle(s)
4. Persist run summary to log/continuous/runs/
"""

from __future__ import annotations

import logging
import math
import signal
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Global stop event for graceful shutdown
_stop_event = threading.Event()


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for the continuous runtime."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _load_config(config_path: str):
    """
    Load pipeline configuration.

    Args:
        config_path: Path to pipeline.yaml file.

    Returns:
        PipelineConfig instance.
    """
    from quantaalpha.continuous.scheduler import PipelineConfig

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    logger.info(f"Loading configuration from {config_path}")
    return PipelineConfig.from_yaml(str(path))


def _create_orchestrator(config, run_store):
    """
    Create orchestrator with wired app4 bridge and impact classifier.

    Args:
        config: PipelineConfig instance.
        run_store: RunStore instance for persistence.

    Returns:
        ContinuousOrchestrator instance.
    """
    from quantaalpha.continuous.main import ContinuousOrchestrator

    return ContinuousOrchestrator(config, run_store=run_store)


def _handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    sig_name = signal.Signals(signum).name
    logger.info(f"Received {sig_name}, initiating graceful shutdown...")
    _stop_event.set()


def start(
    config: str = "config/pipeline.yaml",
    verbose: bool = False,
    run_once: bool = False,
) -> None:
    """
    Start the continuous runtime in foreground loop.

    This command:
    1. Loads configuration from pipeline.yaml
    2. Starts the scheduling loop
    3. Runs until interrupted (Ctrl+C or SIGTERM)

    Args:
        config: Path to the pipeline configuration file.
        verbose: Enable verbose debug logging.
        run_once: If True, run only one cycle and exit (useful for testing).
    """
    _setup_logging(verbose)

    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("=" * 60)
    logger.info("24H Continuous Factor Runtime - Starting")
    logger.info("=" * 60)

    # Load configuration
    try:
        pipeline_config = _load_config(config)
        logger.info(f"Configuration loaded: data_check_interval={pipeline_config.data_check_interval_seconds}s")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Initialize run store
    from quantaalpha.continuous.run_store import RunStore

    runs_dir = Path("log/continuous/runs")
    run_store = RunStore(str(runs_dir))
    logger.info(f"Run store initialized at {runs_dir}")

    # Create orchestrator
    try:
        orchestrator = _create_orchestrator(pipeline_config, run_store)
    except Exception as e:
        logger.error(f"Failed to create orchestrator: {e}")
        sys.exit(1)

    # Start the orchestrator
    try:
        orchestrator.start()
        logger.info("Continuous runtime started")
    except Exception as e:
        logger.error(f"Failed to start orchestrator: {e}")
        sys.exit(1)

    # Main loop
    try:
        if run_once:
            logger.info("Running in single-cycle mode (run_once=True)")
            _run_once_cycle(orchestrator, pipeline_config)
        else:
            logger.info("Running in continuous loop mode")
            _run_continuous_loop(orchestrator, pipeline_config)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        logger.info("Stopping orchestrator...")
        orchestrator.stop()
        logger.info("Continuous runtime stopped")


def _run_once_cycle(orchestrator, pipeline_config) -> None:
    """Execute a single deterministic cycle."""
    from quantaalpha.continuous.run_store import DataUpdateSummary, MiningSummary, RunSummary, ValidationSummary

    start_time = datetime.now()
    logger.info(f"Starting once cycle at {start_time.isoformat()}")

    summary = RunSummary(
        schema_version="1.0",
        cycle_timestamp=start_time.isoformat(),
        cycle_type="once",
        config_snapshot={
            "min_ic": pipeline_config.validation.min_ic,
            "max_revalidation_per_run": pipeline_config.validation.max_revalidation_per_run,
            "max_mining_per_run": pipeline_config.validation.max_mining_per_run,
        },
    )

    try:
        # Execute the once cycle
        cycle_result = orchestrator.run_once_cycle()

        # Populate summary from cycle result
        if cycle_result.get("data_update"):
            du = cycle_result["data_update"]
            summary.data_update = DataUpdateSummary(
                updated=du.get("updated", False),
                updated_interfaces=du.get("updated_interfaces", []),
                stale_interfaces=du.get("stale_interfaces", []),
                latest_dates=du.get("latest_dates", {}),
            )

        if cycle_result.get("impact_groups"):
            summary.impact_groups = cycle_result["impact_groups"]

        if cycle_result.get("validation"):
            v = cycle_result["validation"]
            summary.validation_summary = ValidationSummary(
                total=v.get("total", 0),
                passed=v.get("passed", 0),
                failed=v.get("failed", 0),
                errors=v.get("errors", []),
            )

        if cycle_result.get("mining"):
            m = cycle_result["mining"]
            summary.mining_summary = MiningSummary(
                generated=m.get("generated", 0),
                validated=m.get("validated", 0),
                added=m.get("added", 0),
                errors=m.get("errors", []),
            )

        if cycle_result.get("candidate_factors") is not None:
            summary.candidate_factors_count = cycle_result["candidate_factors"]
            summary.candidate_factors_source = cycle_result.get("candidate_factors_source", "revalidation")

        if cycle_result.get("errors"):
            summary.errors = cycle_result["errors"]

    except Exception as e:
        logger.error(f"Error during once cycle: {e}")
        summary.errors.append(str(e))

    summary.duration_seconds = (datetime.now() - start_time).total_seconds()

    # Persist
    try:
        from quantaalpha.continuous.run_store import RunStore
        runs_dir = Path("log/continuous/runs")
        store = RunStore(str(runs_dir))
        store.save(summary)
        logger.info(f"Run summary persisted: {summary.cycle_timestamp}")
    except Exception as e:
        logger.error(f"Failed to persist run summary: {e}")

    end_time = datetime.now()
    logger.info(f"Once cycle completed in {summary.duration_seconds:.2f}s")
    logger.info(f"  Validation: {summary.validation_summary.total} total, {summary.validation_summary.passed} passed")
    logger.info(f"  Mining: {summary.mining_summary.generated} generated, {summary.mining_summary.added} added")


def _run_continuous_loop(orchestrator, pipeline_config) -> None:
    """Run the continuous foreground loop."""
    from quantaalpha.continuous.run_store import DataUpdateSummary, MiningSummary, RunSummary, ValidationSummary

    check_interval = pipeline_config.data_check_interval_seconds
    logger.info(f"Continuous loop check interval: {check_interval} seconds")

    cycle_count = 0
    while not _stop_event.is_set():
        cycle_count += 1
        cycle_start = datetime.now()
        logger.info(f"--- Cycle {cycle_count} started at {cycle_start.isoformat()} ---")

        summary = RunSummary(
            schema_version="1.0",
            cycle_timestamp=cycle_start.isoformat(),
            cycle_type="start",
            config_snapshot={
                "min_ic": pipeline_config.validation.min_ic,
                "max_revalidation_per_run": pipeline_config.validation.max_revalidation_per_run,
                "max_mining_per_run": pipeline_config.validation.max_mining_per_run,
            },
        )

        try:
            cycle_result = orchestrator.run_once_cycle()

            # Populate from cycle result
            if cycle_result.get("data_update"):
                du = cycle_result["data_update"]
                summary.data_update = DataUpdateSummary(
                    updated=du.get("updated", False),
                    updated_interfaces=du.get("updated_interfaces", []),
                    stale_interfaces=du.get("stale_interfaces", []),
                    latest_dates=du.get("latest_dates", {}),
                )

            if cycle_result.get("impact_groups"):
                summary.impact_groups = cycle_result["impact_groups"]

            if cycle_result.get("validation"):
                v = cycle_result["validation"]
                summary.validation_summary = ValidationSummary(
                    total=v.get("total", 0),
                    passed=v.get("passed", 0),
                    failed=v.get("failed", 0),
                    errors=v.get("errors", []),
                )

            if cycle_result.get("mining"):
                m = cycle_result["mining"]
                summary.mining_summary = MiningSummary(
                    generated=m.get("generated", 0),
                    validated=m.get("validated", 0),
                    added=m.get("added", 0),
                    errors=m.get("errors", []),
                )

            if cycle_result.get("candidate_factors") is not None:
                summary.candidate_factors_count = cycle_result["candidate_factors"]
                summary.candidate_factors_source = cycle_result.get("candidate_factors_source", "revalidation")

            if cycle_result.get("errors"):
                summary.errors = cycle_result["errors"]

        except Exception as e:
            logger.error(f"Error during cycle {cycle_count}: {e}")
            summary.errors.append(str(e))

        summary.duration_seconds = (datetime.now() - cycle_start).total_seconds()

        # Persist cycle summary
        try:
            from quantaalpha.continuous.run_store import RunStore
            runs_dir = Path("log/continuous/runs")
            store = RunStore(str(runs_dir))
            store.save(summary)
        except Exception as e:
            logger.error(f"Failed to persist run summary: {e}")

        cycle_end = datetime.now()
        logger.info(f"--- Cycle {cycle_count} completed in {summary.duration_seconds:.2f}s ---")

        # Wait for next cycle or stop signal
        _stop_event.wait(timeout=check_interval)


def once(
    config: str = "config/pipeline.yaml",
    verbose: bool = False,
) -> None:
    """
    Run a single deterministic cycle and exit.

    This command:
    1. Loads configuration from pipeline.yaml
    2. Runs one complete cycle (data check, revalidation, mining as needed)
    3. Persists run summary
    4. Exits

    Args:
        config: Path to the pipeline configuration file.
        verbose: Enable verbose debug logging.
    """
    _setup_logging(verbose)
    start(config=config, verbose=verbose, run_once=True)


class ContinuousOrchestrator:
    """
    Extended orchestrator that wires app4 bridge and impact classifier
    into the MiningOrchestrator base.

    This class integrates:
    - ContinuousUpdateBridge for data freshness inspection and updates
    - ImpactClassifier for selecting factor candidates by dependency buckets
    - Factor library integration via FactorLibraryManager

    Usage:
        config = PipelineConfig.from_yaml("config/pipeline.yaml")
        orchestrator = ContinuousOrchestrator(config)
        result = orchestrator.run_once_cycle()
    """

    def __init__(
        self,
        config,
        run_store=None,
    ):
        """
        Initialize the continuous orchestrator.

        Args:
            config: PipelineConfig instance.
            run_store: Optional RunStore instance for persistence.
        """
        from quantaalpha.continuous.orchestrator import MiningOrchestrator, SchedulerConfig
        from quantaalpha.continuous.run_store import RunStore

        self.config = config
        self.run_store = run_store or RunStore()

        # Wire app4 bridge first so runtime schedulers can consume it.
        self._bridge = None
        if config.app4_bridge.enabled:
            self._bridge = self._create_bridge(config)

        execution_periods = self._build_execution_periods(config)

        # Create scheduler config from pipeline config
        scheduler_config = SchedulerConfig.from_pipeline_config(config)

        # Create base orchestrator
        self._orchestrator = MiningOrchestrator(
            scheduler_config,
            data_bridge=self._bridge,
            execution_periods=execution_periods,
            library_path=config.factor.library_path,
        )

        # Wire impact classifier
        self._impact_classifier = None
        if config.enable_revalidation or config.enable_mining:
            from quantaalpha.continuous.impact import ImpactClassifier
            self._impact_classifier = ImpactClassifier(
                default_limit=config.validation.max_revalidation_per_run,
                fallback_limit=config.validation.max_mining_per_run,
            )

    def _build_execution_periods(self, config) -> dict[str, tuple[str, str]]:
        """Build execution period tuples from pipeline config."""
        return {
            "train": (config.execution.train.start, config.execution.train.end),
            "valid": (config.execution.valid.start, config.execution.valid.end),
            "test": (config.execution.test.start, config.execution.test.end),
        }

    def _create_bridge(self, config):
        """Create app4 bridge from config."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig

        app4_config = App4BridgeConfig(
            enabled=config.app4_bridge.enabled,
            interfaces=config.app4_bridge.interfaces,
            data_roots=config.app4_bridge.data_roots,
            freshness_threshold_hours=config.app4_bridge.freshness_threshold_hours,
        )

        # Use the bridge from continuous_bridge.py
        storage_dir = config.app4_bridge.data_roots[0] if config.app4_bridge.data_roots else None

        # Import bridge directly to avoid app4.update.__init__ import issues
        # (app4.update.__init__ imports from core.date_utils which may not be in path)
        try:
            import importlib.util
            import types

            bridge_path = "/home/quan/testdata/aspipe_v4/app4/update/continuous_bridge.py"
            spec = importlib.util.spec_from_file_location("continuous_bridge_file", bridge_path)
            if spec and spec.loader:
                bridge_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(bridge_module)
                ContinuousUpdateBridge = bridge_module.ContinuousUpdateBridge
            else:
                raise ImportError("Could not load ContinuousUpdateBridge spec")
        except Exception as e:
            logger.warning(f"Could not import ContinuousUpdateBridge: {e}. Bridge disabled.")
            return None

        return ContinuousUpdateBridge(
            storage_dir=storage_dir,
            monitored_interfaces=config.app4_bridge.interfaces,
            stale_threshold_days=max(1, math.ceil(config.app4_bridge.freshness_threshold_hours / 24)),
            update_timeout_seconds=config.app4_bridge.update_timeout_seconds,
            max_update_interfaces_per_cycle=config.app4_bridge.max_update_interfaces_per_cycle,
            python_executable=config.app4_bridge.python_executable,
        )

    def start(self) -> None:
        """Start the orchestrator."""
        self._orchestrator.start()

    def stop(self) -> None:
        """Stop the orchestrator gracefully."""
        self._orchestrator.stop()

    def run_once_cycle(self) -> dict:
        """
        Execute one complete cycle covering:
        1. Data freshness inspection
        2. Optional data update
        3. Revalidation (if stale interfaces detected)
        4. Mining (on schedule)

        Returns:
            Dict with cycle results including:
            - data_update: Data update summary
            - impact_groups: Selected impact groups
            - validation: Validation summary
            - mining: Mining summary
            - candidate_factors: Number of candidates selected
            - errors: List of errors encountered
        """
        result = {
            "data_update": {},
            "impact_groups": [],
            "validation": {"total": 0, "passed": 0, "failed": 0, "errors": []},
            "mining": {"generated": 0, "validated": 0, "added": 0, "errors": []},
            "candidate_factors": 0,
            "candidate_factors_source": "",
            "errors": [],
        }

        # Step 1: Data inspection
        if self._bridge:
            try:
                inspection = self._bridge.inspect()
                result["data_update"] = {
                    "updated": False,
                    "updated_interfaces": [],
                    "stale_interfaces": inspection.get("stale_interfaces", []),
                    "latest_dates": inspection.get("latest_dates", {}),
                }
                logger.info(f"Data inspection: {len(inspection.get('stale_interfaces', []))} stale interfaces")

                # Step 2: Data update if needed
                if self._bridge.should_update(inspection):
                    logger.info("Data is stale, running update...")
                    update_result = self._bridge.run_update(dry_run=False)
                    result["data_update"]["updated"] = update_result.get("updated", False)
                    result["data_update"]["updated_interfaces"] = update_result.get("updated_interfaces", [])
                    if update_result.get("errors"):
                        result["errors"].extend(update_result["errors"])

            except Exception as e:
                logger.error(f"Data inspection failed: {e}")
                result["errors"].append(f"data_inspection: {str(e)}")

        # Step 3: Impact-based revalidation
        if self.config.enable_revalidation:
            try:
                revalidation_result = self._run_revalidation()
                result["validation"]["total"] = revalidation_result.get("total_candidates", 0)
                result["validation"]["passed"] = revalidation_result.get("revalidated_count", 0)
                result["validation"]["failed"] = (
                    revalidation_result.get("total_candidates", 0)
                    - revalidation_result.get("revalidated_count", 0)
                )
                if revalidation_result.get("errors"):
                    result["validation"]["errors"] = revalidation_result["errors"]
                # Pass through impact and candidate info
                if revalidation_result.get("impact_groups"):
                    result["impact_groups"] = revalidation_result["impact_groups"]
                if revalidation_result.get("candidate_factors") is not None:
                    result["candidate_factors"] = revalidation_result["candidate_factors"]
                if revalidation_result.get("candidate_factors_source"):
                    result["candidate_factors_source"] = revalidation_result["candidate_factors_source"]
            except Exception as e:
                logger.error(f"Revalidation failed: {e}")
                result["errors"].append(f"revalidation: {str(e)}")

        # Step 4: Mining on schedule
        if self.config.enable_mining:
            try:
                mining_result = self._run_mining()
                result["mining"]["generated"] = mining_result.get("factors_generated", 0)
                result["mining"]["validated"] = mining_result.get("factors_validated", 0)
                result["mining"]["added"] = mining_result.get("factors_added", 0)
                if mining_result.get("errors"):
                    result["mining"]["errors"] = mining_result["errors"]
            except Exception as e:
                logger.error(f"Mining failed: {e}")
                result["errors"].append(f"mining: {str(e)}")

        return result

    def _run_revalidation(self) -> dict:
        """Run revalidation cycle with impact classifier integration."""
        from quantaalpha.continuous.scheduler import RevalidationResult

        # Get stale interfaces to determine impact groups
        stale_interfaces = []
        if self._bridge and hasattr(self._bridge, "_last_inspection") and self._bridge._last_inspection:
            stale_interfaces = self._bridge._last_inspection.get("stale_interfaces", [])

        # Classify interfaces into impact groups (even if stale_interfaces is empty,
        # impact classifier may return default groups)
        impact_groups = []
        if self._impact_classifier:
            impact_groups = self._impact_classifier.classify_interfaces(stale_interfaces)
            logger.info(f"Impact groups: {impact_groups}")

        # Get factor candidates via impact classifier
        candidates = None
        candidate_count = 0
        candidate_source = "fallback"

        if self._impact_classifier:
            try:
                from quantaalpha.factors.library import FactorLibraryManager
                library_manager = FactorLibraryManager(self.config.factor.library_path)
                candidates = self._impact_classifier.select_factor_candidates(
                    library_manager,
                    impact_groups,
                    limit=self.config.validation.max_revalidation_per_run,
                )
                candidate_count = len(candidates)
                candidate_source = "impact"
                logger.info(f"Impact-selected {candidate_count} revalidation candidates")
            except Exception as e:
                logger.warning(f"Impact classifier selection failed, using default: {e}")
                candidates = None
                candidate_source = "fallback"

        # Run via base orchestrator, passing candidates if available
        reval_result = self._orchestrator.run_revalidation_cycle(candidates=candidates)

        return {
            "total_candidates": candidate_count if candidate_count > 0 else reval_result.total_candidates,
            "revalidated_count": reval_result.revalidated_count,
            "status_changes": reval_result.status_changes,
            "errors": reval_result.errors,
            "duration_seconds": reval_result.duration_seconds,
            "impact_groups": impact_groups,
            "candidate_factors": candidate_count if candidate_count > 0 else reval_result.total_candidates,
            "candidate_factors_source": candidate_source,
        }

    def _run_mining(self) -> dict:
        """Run mining cycle."""
        mining_result = self._orchestrator.run_mining_cycle()

        return {
            "factors_generated": mining_result.factors_generated,
            "factors_validated": mining_result.factors_validated,
            "factors_added": mining_result.factors_added,
            "factor_ids": mining_result.factor_ids,
            "errors": mining_result.errors,
            "duration_seconds": mining_result.duration_seconds,
        }


def main():
    """CLI entry point for the continuous runtime."""
    import argparse

    parser = argparse.ArgumentParser(
        description="24H Continuous Factor Runtime",
        prog="python -m quantaalpha.continuous.main",
    )
    parser.add_argument(
        "command",
        choices=["start", "once"],
        help="Command: 'start' for continuous loop, 'once' for single cycle",
    )
    parser.add_argument(
        "--config",
        default="config/pipeline.yaml",
        help="Path to pipeline configuration file",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    if args.command == "start":
        start(config=args.config, verbose=args.verbose)
    elif args.command == "once":
        once(config=args.config, verbose=args.verbose)


if __name__ == "__main__":
    main()
