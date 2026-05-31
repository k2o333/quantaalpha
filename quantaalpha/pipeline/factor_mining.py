"""
Factor workflow with session control and evolution support.

Supports three round phases:
- Original: Initial exploration in each direction
- Mutation: Orthogonal exploration from parent trajectories
- Crossover: Hybrid strategies from multiple parents

Supports parallel execution within each phase when enabled.
"""

from collections import Counter
from typing import Any, Optional
from pathlib import Path
import fire
import signal
import sys
import threading
from multiprocessing import Process, Queue
from functools import wraps
import time
import ctypes
import os
import pickle
from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
from quantaalpha.pipeline.planning import generate_parallel_directions
from quantaalpha.pipeline.planning import load_run_config
from quantaalpha.pipeline.evolution import (
    EvolutionController,
    EvolutionConfig,
    StrategyTrajectory,
    RoundPhase,
)
from quantaalpha.core.exception import FactorEmptyError
from quantaalpha.log import logger
from quantaalpha.log.time import measure_time
from quantaalpha.llm.config import LLM_SETTINGS


def _resolve_initial_directions(
    planning_enabled: bool,
    initial_direction: str | None,
    num_directions: int,
) -> tuple[list[str | None], str]:
    """Resolve initial exploration directions based on planning config.

    When planning is enabled but no initial direction is provided, produces
    generic exploration markers represented as ``[None] * num_directions``
    with source labelled as ``'generic'``.

    Args:
        planning_enabled: Whether planning mode is enabled.
        initial_direction: The user-provided initial direction string, or None.
        num_directions: Number of parallel directions to generate.

    Returns:
        A tuple of (directions_list, source_string).
        When planning_enabled=True and initial_direction=None, returns
        ``([None, None, ...], 'generic')``.
    """
    if planning_enabled and initial_direction is None:
        directions = [None] * num_directions
        return directions, "generic"

    if planning_enabled and initial_direction:
        # Will be resolved by generate_parallel_directions at runtime
        # Return a placeholder; the caller handles the actual LLM call
        return [initial_direction] * num_directions, "llm_planning"

    # Planning disabled: use single direction or [None]
    if initial_direction:
        return [initial_direction], "user"
    return [None], "user"


def _resolve_quality_gate_config(run_cfg: dict[str, Any] | None) -> dict[str, Any]:
    """Merge legacy quality_gate config with quality_overlay defaults."""
    run_cfg = run_cfg or {}
    quality_gate_cfg = dict(run_cfg.get("quality_gate") or {})
    overlay_source = run_cfg.get("quality_overlay")
    if overlay_source is not None:
        from quantaalpha.pipeline.quality_overlay import load_quality_overlay_config

        quality_gate_cfg["quality_overlay"] = load_quality_overlay_config(overlay_source)
    elif "quality_overlay" in quality_gate_cfg:
        from quantaalpha.pipeline.quality_overlay import load_quality_overlay_config

        quality_gate_cfg["quality_overlay"] = load_quality_overlay_config(quality_gate_cfg.get("quality_overlay"))
    return quality_gate_cfg


def force_timeout():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            seconds = LLM_SETTINGS.factor_mining_timeout

            def handle_timeout(signum, frame):
                logger.error(f"Process terminated: timeout exceeded ({seconds}s)")
                sys.exit(1)

            signal.signal(signal.SIGALRM, handle_timeout)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return wrapper

    return decorator


def _run_branch(
    direction: str | None,
    step_n: int,
    use_local: bool,
    idx: int,
    log_root: str,
    log_prefix: str,
    quality_gate_cfg: dict = None,
    factor_store_kwargs: dict | None = None,
):
    from quantaalpha.pipeline.loop import AlphaAgentLoop

    if log_root:
        branch_name = f"{log_prefix}_{idx:02d}"
        branch_log = Path(log_root) / branch_name
        branch_log.mkdir(parents=True, exist_ok=True)
        logger.set_storages_path(branch_log)
    model_loop = AlphaAgentLoop(
        ALPHA_AGENT_FACTOR_PROP_SETTING,
        potential_direction=direction,
        stop_event=None,
        use_local=use_local,
        quality_gate_config=quality_gate_cfg or {},
        **(factor_store_kwargs or {}),
    )
    model_loop.user_initial_direction = direction
    model_loop.run(step_n=step_n, stop_event=None)


def _run_evolution_task(
    task: dict[str, Any],
    directions: list[str],
    step_n: int,
    use_local: bool,
    user_direction: str | None,
    log_root: str,
    stop_event: threading.Event | None,
    quality_gate_cfg: dict[str, Any] | None = None,
    factor_store_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run a single evolution task (one small loop).

    Args:
        task: Evolution task descriptor
        directions: List of original directions
        step_n: Steps per round
        use_local: Use local backtest
        user_direction: User initial direction
        log_root: Log root directory
        stop_event: Stop event
        quality_gate_cfg: Quality gate config

    Returns:
        Dict containing trajectory data
    """
    from quantaalpha.pipeline.loop import AlphaAgentLoop

    phase = task["phase"]
    direction_id = task["direction_id"]
    strategy_suffix = task.get("strategy_suffix", "")
    round_idx = task["round_idx"]
    parent_trajectories = task.get("parent_trajectories", [])

    # Resolve direction by phase
    if phase == RoundPhase.ORIGINAL:
        direction = directions[direction_id] if direction_id < len(directions) else None
    elif phase == RoundPhase.MUTATION:
        direction = directions[direction_id] if direction_id < len(directions) else None
    else:  # CROSSOVER
        direction = None

    trajectory_id = StrategyTrajectory.generate_id(direction_id, round_idx, phase)
    parent_ids = [p.trajectory_id for p in parent_trajectories]

    if log_root:
        branch_name = f"{phase.value}_{round_idx:02d}_{direction_id:02d}"
        branch_log = Path(log_root) / branch_name
        branch_log.mkdir(parents=True, exist_ok=True)
        logger.set_storages_path(branch_log)

    logger.info(f"Starting evolution task: phase={phase.value}, round={round_idx}, direction={direction_id}")

    # Create and run loop
    model_loop = AlphaAgentLoop(
        ALPHA_AGENT_FACTOR_PROP_SETTING,
        potential_direction=direction,
        stop_event=stop_event,
        use_local=use_local,
        strategy_suffix=strategy_suffix,
        evolution_phase=phase.value,
        trajectory_id=trajectory_id,
        parent_trajectory_ids=parent_ids,
        direction_id=direction_id,
        round_idx=round_idx,
        quality_gate_config=quality_gate_cfg or {},
        **(factor_store_kwargs or {}),
    )
    model_loop.user_initial_direction = user_direction

    # Run one small loop (5 steps)
    model_loop.run(step_n=step_n, stop_event=stop_event)

    traj_data = model_loop._get_trajectory_data()
    traj_data["task"] = task

    return traj_data


def _advance_controller_after_failed_task(controller: EvolutionController, task: dict[str, Any]) -> None:
    """Advance controller state so a failed task is not retried indefinitely."""
    phase = task.get("phase")
    if phase == RoundPhase.ORIGINAL:
        controller._directions_completed.add(task.get("direction_id", 0))
        return
    if phase == RoundPhase.MUTATION:
        controller._mutation_idx += 1
        return
    if phase == RoundPhase.CROSSOVER:
        controller._crossover_idx += 1


def _is_bounded_llm_task_failure(error: Exception) -> bool:
    """Return True for known LLM exhaustions that are already bounded by retry policy."""
    text = str(error)
    bounded_markers = (
        "Failed to create call_structured after",
        "Multi-hypothesis construct failed after",
        "Factor proposal failed after",
        "expression acceptability failure",
        "Feedback generation failed",
    )
    return any(marker in text for marker in bounded_markers)


def _aggregate_quality_gate_lifecycle(save_results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"evaluated": 0, "active_promoted": 0, "candidate_only": 0, "rejected": 0}
    for result in save_results:
        lifecycle = result.get("quality_gate_lifecycle") or {}
        for key in counts:
            counts[key] += int(lifecycle.get(key, 0) or 0)
        if lifecycle.get("quarantine"):
            counts["quarantine"] = int(counts.get("quarantine", 0)) + int(lifecycle.get("quarantine", 0) or 0)
    return counts


def _best_metric_payload(save_results: list[dict[str, Any]]) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_rank_ic = None
    for result in save_results:
        metrics = result.get("best_metrics") or {}
        rank_ic = metrics.get("Rank IC")
        try:
            rank_ic_value = float(rank_ic)
        except (TypeError, ValueError):
            rank_ic_value = None
        if best_rank_ic is None or (rank_ic_value is not None and rank_ic_value > best_rank_ic):
            best = dict(metrics)
            best_rank_ic = rank_ic_value
    return best


def _parallel_task_worker(
    task: dict[str, Any],
    directions: list[str],
    step_n: int,
    use_local: bool,
    user_direction: str | None,
    log_root: str,
    result_queue: Queue,
    task_idx: int,
    factor_store_kwargs: dict[str, Any] | None = None,
):
    """
    Worker for parallel evolution tasks. Runs one evolution task in a separate process and puts result in queue.
    Args: task, directions, step_n, use_local, user_direction, log_root, result_queue, task_idx.
    """
    try:
        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        RD_AGENT_SETTINGS.use_file_lock = False
        RD_AGENT_SETTINGS.pickle_cache_folder_path_str = str(Path(log_root) / f"pickle_cache_{task_idx}")

        traj_data = _run_evolution_task(
            task=task,
            directions=directions,
            step_n=step_n,
            use_local=use_local,
            user_direction=user_direction,
            log_root=log_root,
            stop_event=None,
            factor_store_kwargs=factor_store_kwargs,
        )
        result_queue.put(
            {
                "success": True,
                "task_idx": task_idx,
                "task": task,
                "traj_data": traj_data,
            }
        )
    except Exception as e:
        import traceback

        result_queue.put(
            {
                "success": False,
                "task_idx": task_idx,
                "task": task,
                "error": str(e),
                "traceback": traceback.format_exc(),
            }
        )


def _serialize_task_for_parallel(task: dict[str, Any]) -> dict[str, Any]:
    """Serialize task for use in child process (parent_trajectories are complex objects)."""
    serialized = task.copy()

    # RoundPhase -> string
    if "phase" in serialized and isinstance(serialized["phase"], RoundPhase):
        serialized["phase"] = serialized["phase"]

    # Convert parent_trajectories to serializable info
    if "parent_trajectories" in serialized:
        serialized["parent_trajectory_ids"] = [p.trajectory_id for p in serialized.get("parent_trajectories", [])]
        # Child process does not need full trajectory objects; strategy_suffix has required info
        serialized["parent_trajectories"] = []

    return serialized


def _run_tasks_parallel(
    tasks: list[dict[str, Any]],
    directions: list[str],
    step_n: int,
    use_local: bool,
    user_direction: str | None,
    log_root: str,
    factor_store_kwargs: dict[str, Any] | None = None,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    """
    Run multiple evolution tasks in parallel.
    Returns list of results, each with task and traj_data.
    """
    if not tasks:
        return []

    result_queue = Queue()
    worker_limit = max(1, int(max_workers or len(tasks)))

    logger.info(f"Starting {len(tasks)} parallel evolution tasks with max_workers={worker_limit}")

    results = []
    for batch_start in range(0, len(tasks), worker_limit):
        processes = []
        batch = list(enumerate(tasks[batch_start : batch_start + worker_limit], start=batch_start))
        for idx, task in batch:
            serialized_task = _serialize_task_for_parallel(task)

            p = Process(
                target=_parallel_task_worker,
                args=(
                    serialized_task,
                    directions,
                    step_n,
                    use_local,
                    user_direction,
                    log_root,
                    result_queue,
                    idx,
                    factor_store_kwargs,
                ),
            )
            p.start()
            processes.append(p)
            logger.info(f"Started task {idx}: phase={task['phase'].value}, direction={task['direction_id']}")

        for _ in batch:
            result = result_queue.get()
            if result["success"]:
                original_task = tasks[result["task_idx"]]
                result["task"] = original_task
                result["traj_data"]["task"] = original_task
                logger.info(f"Task {result['task_idx']} completed")
            else:
                logger.error(f"Task {result['task_idx']} failed: {result['error']}")
                logger.error(result.get("traceback", ""))
            results.append(result)

        for p in processes:
            p.join()

    successful_results = sum(1 for result in results if result["success"])
    logger.info(f"Parallel tasks done: {successful_results}/{len(tasks)} succeeded")

    return results


def _build_task_failure_record(task: dict[str, Any], error: str) -> dict[str, Any]:
    phase = task.get("phase")
    phase_name = phase.value if hasattr(phase, "value") else str(phase)
    return {
        "phase": phase_name,
        "round_idx": task.get("round_idx"),
        "direction_id": task.get("direction_id"),
        "error": error,
    }


def _log_failure_summary(
    failures: list[dict[str, Any]],
    total_tasks: int,
    skipped: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    skipped = skipped or []
    summary = {
        "total_tasks": total_tasks,
        "failed_tasks": len(failures),
        "skipped_tasks": len(skipped),
        "successful_tasks": max(total_tasks - len(failures), 0),
        "status": "success" if not failures else "degraded",
        "failures": failures,
        "skipped": skipped,
    }

    logger.info("=" * 60)
    if not failures:
        logger.info("Task failure summary: 0 failures")
        if skipped:
            logger.info(f"Task skip summary: {len(skipped)}/{total_tasks} skipped after bounded LLM exhaustion")
        logger.info("=" * 60)
        return summary

    phase_counter = Counter(failure["phase"] for failure in failures)
    logger.warning(f"Task failure summary: {len(failures)}/{total_tasks} failed ({summary['successful_tasks']} succeeded)")
    logger.warning(f"Failed tasks by phase: {dict(phase_counter)}")
    for failure in failures:
        logger.warning(f"Failed task detail: phase={failure['phase']}, round={failure['round_idx']}, direction={failure['direction_id']}, error={failure['error']}")
    logger.info("=" * 60)
    return summary


def _resolve_factor_store_kwargs(run_cfg: dict[str, Any], exec_cfg: dict[str, Any]) -> dict[str, Any]:
    """Resolve AlphaAgentLoop runtime kwargs from experiment config."""
    kwargs = dict(exec_cfg.get("factor_store_kwargs", {}) or {})
    backtest_cfg = (run_cfg.get("backtest") or {}) if isinstance(run_cfg, dict) else {}
    backend = (
        backtest_cfg.get("backend")
        or run_cfg.get("backtest_backend")
        or os.environ.get("QUANTAALPHA_BACKTEST_BACKEND")
    )
    if backend:
        kwargs.setdefault("backtest_backend", str(backend).strip().lower())
    noqlib_cfg = backtest_cfg.get("noqlib") or backtest_cfg.get("backtest_noqlib") or run_cfg.get("backtest_noqlib")
    if noqlib_cfg:
        kwargs.setdefault("backtest_noqlib_config", dict(noqlib_cfg))
    return kwargs


def run_evolution_action(
    initial_direction: str | None,
    evolution_cfg: dict[str, Any],
    exec_cfg: dict[str, Any],
    planning_cfg: dict[str, Any],
    mutation_enabled: bool = True,
    crossover_enabled: bool = False,
    quality_gate_cfg: dict[str, Any] | None = None,
    budget_seconds: Optional[int] = None,
    log_root: str | None = None,
) -> dict[str, Any]:
    """
    Runtime adapter entrypoint for evolution actions.

    Delegates to run_evolution_loop with per-action evolution flags:
    - mutation => mutation_enabled=True, crossover_enabled=False
    - crossover => mutation_enabled=False, crossover_enabled=True

    Args:
        initial_direction: Initial exploration direction.
        evolution_cfg: Evolution configuration.
        exec_cfg: Execution configuration.
        planning_cfg: Planning configuration.
        mutation_enabled: Whether to enable mutation phase.
        crossover_enabled: Whether to enable crossover phase.
        quality_gate_cfg: Quality gate thresholds for factor lifecycle promotion.
        budget_seconds: Maximum seconds for this evolution run.
        log_root: Log root directory.

    Returns:
        Dict with status, failed_tasks, total_tasks, successful_tasks.
    """
    # Merge action-specific flags into evolution_cfg for run_evolution_loop
    effective_evolution_cfg = {
        **evolution_cfg,
        "mutation_enabled": mutation_enabled,
        "crossover_enabled": crossover_enabled,
    }

    return run_evolution_loop(
        initial_direction=initial_direction,
        evolution_cfg=effective_evolution_cfg,
        exec_cfg=exec_cfg,
        planning_cfg=planning_cfg,
        stop_event=None,
        quality_gate_cfg=quality_gate_cfg,
        budget_seconds=budget_seconds,
        log_root=log_root,
    )


def run_evolution_loop(
    initial_direction: str | None,
    evolution_cfg: dict[str, Any],
    exec_cfg: dict[str, Any],
    planning_cfg: dict[str, Any],
    stop_event: threading.Event | None = None,
    quality_gate_cfg: dict[str, Any] | None = None,
    budget_seconds: Optional[int] = None,
    log_root: str | None = None,
):
    """
    Run evolution loop: Original -> Mutation -> Crossover -> Mutation -> ...
    Supports parallel execution per phase.
    """
    loop_start_time = time.time()
    quality_gate_cfg = quality_gate_cfg or {}
    from quantaalpha.core.conf import RD_AGENT_SETTINGS

    RD_AGENT_SETTINGS.use_file_lock = False
    logger.info("Evolution mode: file lock disabled to avoid deadlock")

    # Parse config
    num_directions = int(planning_cfg.get("num_directions", 2))
    max_rounds = int(evolution_cfg.get("max_rounds", 10))
    crossover_size = int(evolution_cfg.get("crossover_size", 2))
    crossover_n = int(evolution_cfg.get("crossover_n", 3))
    steps_per_loop = int(exec_cfg.get("steps_per_loop", 5))
    use_local = bool(exec_cfg.get("use_local", True))
    factor_store_kwargs = exec_cfg.get("factor_store_kwargs", {}) or {}
    max_tasks_per_run = int(exec_cfg.get("max_tasks_per_run", 0) or 0)

    mutation_enabled = bool(evolution_cfg.get("mutation_enabled", True))
    crossover_enabled = bool(evolution_cfg.get("crossover_enabled", True))
    parent_selection_strategy = str(evolution_cfg.get("parent_selection_strategy", "best"))
    top_percent_threshold = float(evolution_cfg.get("top_percent_threshold", 0.3))
    parquet_library_dir = evolution_cfg.get("parquet_library_dir")
    historical_active_parent_count = int(evolution_cfg.get("historical_active_parent_count", 0) or 0)
    historical_parent_min_rank_ic = float(evolution_cfg.get("historical_parent_min_rank_ic", 0.0) or 0.0)
    historical_parent_statuses = evolution_cfg.get("historical_parent_statuses") or ["active"]
    historical_parent_sources = evolution_cfg.get("historical_parent_sources") or {}
    mutation_mode_weights = evolution_cfg.get("mutation_mode_weights") or {"exploit": 0.75, "explore": 0.25}
    mutation_mode_schedule = str(evolution_cfg.get("mutation_mode_schedule", "fixed") or "fixed")
    adaptive_cfg = evolution_cfg.get("adaptive_mutation") or {}
    diversity_cfg = evolution_cfg.get("diversity_enforcement") or {}
    # 优先使用显式参数,fallback 到 logger 状态(向后兼容)
    if log_root is None:
        log_root = str(logger.storage.path)
    parallel_enabled = bool(evolution_cfg.get("parallel_enabled", False))
    raw_max_factor_workers = evolution_cfg.get("max_factor_workers")
    max_factor_workers = int(raw_max_factor_workers) if raw_max_factor_workers else None
    fresh_start = bool(evolution_cfg.get("fresh_start", True))
    cleanup_on_finish = bool(evolution_cfg.get("cleanup_on_finish", False))
    raw_failure_threshold = evolution_cfg.get("failed_task_threshold")
    failure_threshold = None if raw_failure_threshold in (None, "") else int(raw_failure_threshold)
    failures: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    save_results: list[dict[str, Any]] = []
    total_tasks = 0

    # Generate initial directions using the resolution helper
    planning_enabled = bool(planning_cfg.get("enabled", False))
    prompt_file = planning_cfg.get("prompt_file") or "planning_prompts.yaml"
    prompt_path = Path(__file__).parent / "prompts" / str(prompt_file)

    directions, direction_source = _resolve_initial_directions(
        planning_enabled=planning_enabled,
        initial_direction=initial_direction,
        num_directions=num_directions,
    )

    # When planning is enabled with an initial direction, call the LLM planner
    if planning_enabled and initial_direction and direction_source == "llm_planning":
        try:
            directions = generate_parallel_directions(
                initial_direction=initial_direction,
                n=num_directions,
                prompt_file=prompt_path,
                max_attempts=int(planning_cfg.get("max_attempts", 5)),
                use_llm=bool(planning_cfg.get("use_llm", True)),
                allow_fallback=bool(planning_cfg.get("allow_fallback", True)),
            )
            direction_source = "llm_planning"
        except Exception as exc:
            logger.warning(f"Planning LLM failed, falling back to generic directions: {exc}")
            directions = [None] * num_directions
            direction_source = "generic"

    logger.info(f"Generated {len(directions)} exploration directions (source: {direction_source})")
    for i, d in enumerate(directions):
        logger.info(f"  Direction {i}: {d}")

    pool_save_path = Path(log_root) / "trajectory_pool.json"
    mutation_prompt_path = Path(__file__).parent / "prompts" / "evolution_prompts.yaml"

    logger.info(f"Trajectory pool path: {pool_save_path} (fresh_start={fresh_start})")

    config = EvolutionConfig(
        num_directions=len(directions),
        steps_per_loop=steps_per_loop,
        max_rounds=max_rounds,
        mutation_enabled=mutation_enabled,
        crossover_enabled=crossover_enabled,
        crossover_size=crossover_size,
        crossover_n=crossover_n,
        prefer_diverse_crossover=True,
        parent_selection_strategy=parent_selection_strategy,
        top_percent_threshold=top_percent_threshold,
        parallel_enabled=parallel_enabled,
        pool_save_path=str(pool_save_path),
        mutation_prompt_path=str(mutation_prompt_path) if mutation_prompt_path.exists() else None,
        crossover_prompt_path=str(mutation_prompt_path) if mutation_prompt_path.exists() else None,
        fresh_start=fresh_start,
        parquet_library_dir=str(parquet_library_dir) if parquet_library_dir else None,
        historical_active_parent_count=historical_active_parent_count,
        historical_parent_min_rank_ic=historical_parent_min_rank_ic,
        historical_parent_statuses=list(historical_parent_statuses),
        historical_parent_sources=dict(historical_parent_sources),
        mutation_mode_weights=dict(mutation_mode_weights),
        mutation_mode_schedule=mutation_mode_schedule,
        adaptive_min_rounds=int(adaptive_cfg.get("min_rounds", 3) or 3),
        adaptive_stagnation_rounds=int(adaptive_cfg.get("stagnation_rounds", 3) or 3),
        adaptive_min_active_rate=float(adaptive_cfg.get("min_active_rate", 0.01) or 0.0),
        adaptive_explore_boost=float(adaptive_cfg.get("explore_boost", 0.15) or 0.0),
        adaptive_min_explore_weight=float(adaptive_cfg.get("min_explore_weight", 0.10) or 0.0),
        adaptive_max_explore_weight=float(adaptive_cfg.get("max_explore_weight", 0.60) or 1.0),
        diversity_enforcement_enabled=bool(diversity_cfg.get("enabled", False)),
        diversity_similarity_threshold=float(diversity_cfg.get("similarity_threshold", 0.90) or 0.90),
        diversity_penalty=float(diversity_cfg.get("penalty", 0.10) or 0.10),
    )

    controller = EvolutionController(config)

    logger.info("=" * 60)
    logger.info("Starting evolution loop")
    logger.info(f"Config: directions={len(directions)}, max_rounds={max_rounds}, crossover_size={crossover_size}, crossover_n={crossover_n}")
    logger.info(f"Phases: mutation={'on' if mutation_enabled else 'off'}, crossover={'on' if crossover_enabled else 'off'}")
    if mutation_enabled and not crossover_enabled:
        logger.info("Mode: mutation only (Original -> Mutation -> ...)")
    elif crossover_enabled and not mutation_enabled:
        logger.info("Mode: crossover only (Original -> Crossover -> ...)")
    elif mutation_enabled and crossover_enabled:
        logger.info("Mode: full evolution (Original -> Mutation -> Crossover -> ...)")
    else:
        logger.info("Mode: original only (no evolution)")
    logger.info(f"Parent selection: {parent_selection_strategy}" + (f" (top_percent={top_percent_threshold})" if parent_selection_strategy == "top_percent_plus_random" else ""))
    logger.info(f"Parallel execution: {'on' if parallel_enabled else 'off'}")
    logger.info("=" * 60)

    if parallel_enabled:
        while not controller.is_complete():
            # Budget check
            if budget_seconds is not None:
                elapsed = time.time() - loop_start_time
                if elapsed >= budget_seconds:
                    logger.info(f"Evolution budget exhausted: {elapsed:.0f}s / {budget_seconds}s")
                    break
            if max_tasks_per_run and total_tasks >= max_tasks_per_run:
                logger.info(f"Evolution task cap reached: {total_tasks}/{max_tasks_per_run}")
                break
            if stop_event and stop_event.is_set():
                logger.info("Stop signal received, ending evolution loop")
                break

            tasks = controller.get_all_tasks_for_current_phase()
            if not tasks:
                logger.info("Evolution complete: no more tasks")
                break

            current_phase = tasks[0]["phase"]
            current_round = tasks[0]["round_idx"]
            logger.info(f"Parallel phase: phase={current_phase.value}, round={current_round}, tasks={len(tasks)}")
            total_tasks += len(tasks)

            results = _run_tasks_parallel(
                tasks=tasks,
                directions=directions,
                step_n=steps_per_loop,
                use_local=use_local,
                user_direction=initial_direction,
                log_root=log_root,
                factor_store_kwargs=factor_store_kwargs,
                max_workers=max_factor_workers,
            )

            completed_pairs = []
            for result in results:
                if result["success"]:
                    task = result["task"]
                    traj_data = result["traj_data"]
                    trajectory = controller.create_trajectory_from_loop_result(
                        task=task,
                        hypothesis=traj_data.get("hypothesis"),
                        experiment=traj_data.get("experiment"),
                        feedback=traj_data.get("feedback"),
                    )
                    completed_pairs.append((task, trajectory))
                    save_result = traj_data.get("save_result")
                    if isinstance(save_result, dict):
                        save_results.append(save_result)
                    logger.info(f"Trajectory done: {trajectory.trajectory_id}, RankIC={trajectory.get_primary_metric()}")
            controller.apply_same_round_diversity_penalty([trajectory for _task, trajectory in completed_pairs])
            completed_tasks = []
            for task, trajectory in completed_pairs:
                controller.report_task_complete(task, trajectory)
                completed_tasks.append(task)
            result_by_task_idx = {result["task_idx"]: result for result in results}
            for task_idx, task in enumerate(tasks):
                result = result_by_task_idx.get(task_idx)
                if result is not None and result["success"]:
                    continue
                error = result.get("error", "Task failed in parallel worker") if result is not None else "Task result missing"
                failures.append(_build_task_failure_record(task, error))

            controller.advance_phase_after_parallel_completion(completed_tasks)

    else:
        while not controller.is_complete():
            # Budget check
            if budget_seconds is not None:
                elapsed = time.time() - loop_start_time
                if elapsed >= budget_seconds:
                    logger.info(f"Evolution budget exhausted: {elapsed:.0f}s / {budget_seconds}s")
                    break
            if stop_event and stop_event.is_set():
                logger.info("Stop signal received, ending evolution loop")
                break
            if max_tasks_per_run and total_tasks >= max_tasks_per_run:
                logger.info(f"Evolution task cap reached: {total_tasks}/{max_tasks_per_run}")
                break

            task = controller.get_next_task()
            if task is None:
                logger.info("Evolution complete: no more tasks")
                break

            logger.info(f"Running task: phase={task['phase'].value}, round={task['round_idx']}, direction={task['direction_id']}")
            total_tasks += 1

            try:
                traj_data = _run_evolution_task(
                    task=task,
                    directions=directions,
                    step_n=steps_per_loop,
                    use_local=use_local,
                    user_direction=initial_direction,
                    log_root=log_root,
                    stop_event=stop_event,
                    quality_gate_cfg=quality_gate_cfg,
                    factor_store_kwargs=factor_store_kwargs,
                )
                trajectory = controller.create_trajectory_from_loop_result(
                    task=task,
                    hypothesis=traj_data.get("hypothesis"),
                    experiment=traj_data.get("experiment"),
                    feedback=traj_data.get("feedback"),
                )
                controller.report_task_complete(task, trajectory)
                save_result = traj_data.get("save_result")
                if isinstance(save_result, dict):
                    save_results.append(save_result)
                logger.info(f"Task done: trajectory_id={trajectory.trajectory_id}, RankIC={trajectory.get_primary_metric()}")
            except Exception as e:
                if _is_bounded_llm_task_failure(e):
                    logger.warning(f"Task skipped after bounded LLM failure: {e}")
                    skipped.append(_build_task_failure_record(task, str(e)))
                else:
                    logger.error(f"Task failed: {e}")
                    import traceback

                    logger.error(traceback.format_exc())
                    failures.append(_build_task_failure_record(task, str(e)))
                _advance_controller_after_failed_task(controller, task)
                continue

    state_path = Path(log_root) / "evolution_state.json"
    controller.save_state(state_path)
    best_trajs = controller.get_best_trajectories(top_n=5)
    logger.info("=" * 60)
    logger.info(f"Evolution complete. Top {len(best_trajs)} trajectories:")
    for i, t in enumerate(best_trajs):
        metric = t.get_primary_metric()
        metric_str = f"{metric:.4f}" if metric is not None else "N/A"
        logger.info(f"  {i + 1}. {t.trajectory_id}: phase={t.phase.value}, RankIC={metric_str}")
    logger.info(f"Pool stats: {controller.pool.get_statistics()}")
    logger.info("=" * 60)
    summary = _log_failure_summary(failures, total_tasks, skipped)
    summary["quality_gate_lifecycle"] = _aggregate_quality_gate_lifecycle(save_results)
    summary["best_metrics"] = _best_metric_payload(save_results)
    summary["historical_parent_injection_counts"] = getattr(controller, "_historical_parent_injection_counts", {})
    summary["trajectory_pool"] = controller.pool.get_statistics()
    logger.info(
        "Quality gate lifecycle summary: "
        f"{summary['quality_gate_lifecycle']}; best_metrics={summary['best_metrics']}; "
        f"historical_parent_injection_counts={summary['historical_parent_injection_counts']}"
    )
    if failure_threshold is not None and summary["failed_tasks"] >= failure_threshold:
        summary["status"] = "failed"
        if cleanup_on_finish:
            logger.info("Cleaning up trajectory pool file...")
            controller.pool.cleanup_file()
        raise RuntimeError(f"Evolution finished with {summary['failed_tasks']} failed tasks, meeting threshold {failure_threshold}.")
    if cleanup_on_finish:
        logger.info("Cleaning up trajectory pool file...")
        controller.pool.cleanup_file()
    return summary


@force_timeout()
def main(path=None, step_n=100, direction=None, stop_event=None, config_path=None, evolution_mode=None):
    """
    Autonomous alpha factor mining with optional evolution support.

    Args:
        path: Session path (for resume)
        step_n: Number of steps (default 100 = 20 loops * 5 steps/loop)
        direction: Initial direction
        stop_event: Stop event
        config_path: Run config file path
        evolution_mode: Enable evolution (None=from config, True/False=override)

    Evolution flow: Original -> Mutation -> Crossover -> Mutation -> ...

    You can continue running session by

    .. code-block:: python

        quantaalpha mine --direction "[Initial Direction]" --config_path configs/experiment.yaml

    """
    try:
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        logger.info("=" * 60)
        logger.info("Experiment config")
        logger.info(f"  Workspace: {RD_AGENT_SETTINGS.workspace_path}")
        logger.info(f"  Cache dir: {RD_AGENT_SETTINGS.pickle_cache_folder_path_str}")
        logger.info(f"  Cache enabled: {RD_AGENT_SETTINGS.cache_with_pickle}")
        logger.info("=" * 60)

        # Config file default: project_root/configs/
        _project_root = Path(__file__).resolve().parents[2]
        config_default = _project_root / "configs" / "experiment.yaml"
        config_file = Path(config_path) if config_path else config_default
        run_cfg = load_run_config(config_file)
        planning_cfg = (run_cfg.get("planning") or {}) if isinstance(run_cfg, dict) else {}
        exec_cfg = (run_cfg.get("execution") or {}) if isinstance(run_cfg, dict) else {}
        evolution_cfg = (run_cfg.get("evolution") or {}) if isinstance(run_cfg, dict) else {}
        quality_gate_cfg = _resolve_quality_gate_config(run_cfg if isinstance(run_cfg, dict) else {})
        factor_store_kwargs = _resolve_factor_store_kwargs(run_cfg, exec_cfg)
        if factor_store_kwargs:
            exec_cfg["factor_store_kwargs"] = factor_store_kwargs

        if evolution_mode is not None:
            use_evolution = evolution_mode
        else:
            use_evolution = bool(evolution_cfg.get("enabled", False))

        if step_n is None or step_n == 100:
            if exec_cfg.get("step_n") is not None:
                step_n = exec_cfg.get("step_n")
            else:
                max_loops = int(exec_cfg.get("max_loops", 10))
                steps_per_loop = int(exec_cfg.get("steps_per_loop", 5))
                step_n = max_loops * steps_per_loop

        use_local = os.getenv("USE_LOCAL", "True").lower()
        use_local = True if use_local in ["true", "1"] else False
        if exec_cfg.get("use_local") is not None:
            use_local = bool(exec_cfg.get("use_local"))
        exec_cfg["use_local"] = use_local

        logger.info(f"Use {'Local' if use_local else 'Docker container'} to execute factor backtest")

        if use_evolution and path is None:
            logger.info("=" * 60)
            logger.info("Evolution mode: Original -> Mutation -> Crossover loop")
            logger.info("=" * 60)

            summary = run_evolution_loop(
                initial_direction=direction,
                evolution_cfg=evolution_cfg,
                exec_cfg=exec_cfg,
                planning_cfg=planning_cfg,
                stop_event=stop_event,
                quality_gate_cfg=quality_gate_cfg,
            )
            if summary.get("failed_tasks", 0) > 0:
                logger.warning(f"Evolution run completed with degraded status: {summary['failed_tasks']}/{summary['total_tasks']} tasks failed")

        elif path is None:
            planning_enabled = bool(planning_cfg.get("enabled", False))
            n_dirs = int(planning_cfg.get("num_directions", 1))
            max_attempts = int(planning_cfg.get("max_attempts", 5))
            use_llm = bool(planning_cfg.get("use_llm", True))
            allow_fallback = bool(planning_cfg.get("allow_fallback", True))
            prompt_file = planning_cfg.get("prompt_file") or "planning_prompts.yaml"
            prompt_path = Path(__file__).parent / "prompts" / str(prompt_file)

            directions, direction_source = _resolve_initial_directions(
                planning_enabled=planning_enabled,
                initial_direction=direction,
                num_directions=n_dirs,
            )
            if planning_enabled and direction and direction_source == "llm_planning":
                try:
                    directions = generate_parallel_directions(
                        initial_direction=direction,
                        n=n_dirs,
                        prompt_file=prompt_path,
                        max_attempts=max_attempts,
                        use_llm=use_llm,
                        allow_fallback=allow_fallback,
                    )
                except Exception as exc:
                    logger.warning(f"Planning LLM failed, falling back to generic: {exc}")
                    directions = [None] * n_dirs

            log_root = exec_cfg.get("branch_log_root") or "log"
            log_prefix = exec_cfg.get("branch_log_prefix") or "branch"
            use_branch_logs = planning_enabled and len(directions) > 1
            parallel_execution = bool(exec_cfg.get("parallel_execution", False))

            if parallel_execution and len(directions) > 1:
                procs: list[Process] = []
                for idx, dir_text in enumerate(directions, start=1):
                    if dir_text:
                        logger.info(f"[Planning] Branch {idx}/{len(directions)} direction: {dir_text}")
                    p = Process(
                        target=_run_branch,
                        args=(
                            dir_text,
                            step_n,
                            use_local,
                            idx,
                            log_root if use_branch_logs else "",
                            log_prefix,
                            quality_gate_cfg,
                            factor_store_kwargs,
                        ),
                    )
                    p.start()
                    procs.append(p)
                for p in procs:
                    p.join()
            else:
                for idx, dir_text in enumerate(directions, start=1):
                    if dir_text:
                        logger.info(f"[Planning] Branch {idx}/{len(directions)} direction: {dir_text}")
                    if use_branch_logs:
                        branch_name = f"{log_prefix}_{idx:02d}"
                        branch_log = Path(log_root) / branch_name
                        branch_log.mkdir(parents=True, exist_ok=True)
                        logger.set_storages_path(branch_log)
                    model_loop = AlphaAgentLoop(
                        ALPHA_AGENT_FACTOR_PROP_SETTING,
                        potential_direction=dir_text,
                        stop_event=stop_event,
                        use_local=use_local,
                        quality_gate_config=quality_gate_cfg,
                        **factor_store_kwargs,
                    )
                    model_loop.user_initial_direction = direction
                    model_loop.run(step_n=step_n, stop_event=stop_event)
        else:
            model_loop = AlphaAgentLoop.load(path, use_local=use_local)
            model_loop.run(step_n=step_n, stop_event=stop_event)
    except Exception as e:
        logger.error(f"Error during execution: {str(e)}")
        raise
    finally:
        logger.info("Run finished or terminated")


if __name__ == "__main__":
    fire.Fire(main)
