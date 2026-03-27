"""
QuantaAlpha CLI entry.

Commands:
  quantaalpha mine       - run factor mining
  quantaalpha backtest   - run backtest
  quantaalpha ui         - start log Web UI
  quantaalpha health_check - environment health check
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env (prefer project root, fallback to cwd)
_project_root = Path(__file__).resolve().parents[1]
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv(".env")

import fire
from quantaalpha.pipeline.factor_mining import main as mine
from quantaalpha.pipeline.factor_backtest import main as backtest
from quantaalpha.app.utils.health_check import health_check
from quantaalpha.app.utils.info import collect_info
from quantaalpha.factors.library import FactorLibraryManager


def _default_backtest_config_path() -> str | None:
    config_path = _project_root / "configs" / "backtest.yaml"
    if config_path.exists():
        return str(config_path)
    return None


def _build_validation_result_from_metrics(metrics: dict) -> dict:
    multi_period = metrics.get("multi_period_validation") or {}
    period_results = multi_period.get("period_results", [])
    summary = multi_period.get("summary") or {}
    stability_score = summary.get("stability_score", metrics.get("stability_score"))
    validation_summary = summary.get("validation_summary", "real_backtest")
    return {
        "status": "success",
        "period_results": period_results,
        "summary": {
            **summary,
            "stability_score": stability_score,
            "validation_summary": validation_summary,
        },
    }


def _cli_result_failed(result) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("mode") == "error":
        return True
    if result.get("success") is False:
        return True
    if int(result.get("failed", 0) or 0) > 0:
        return True
    return False


def _error_report(report: dict, error: str) -> dict:
    return {
        **report,
        "mode": "error",
        "error": error,
    }


def revalidate(
    library_path: str,
    days: int | None = None,
    status: str | None = None,
    factor_ids: str | None = None,
    dry_run: bool = False,
    real_backtest: bool = False,
    no_write: bool = False,
    backtest_config: str | None = None,
):
    """
    Revalidate factors in the library.

    Three mutually exclusive modes:
    - Default (dry_run=False, real_backtest=False): Refresh factor status from existing evaluation results.
    - --dry-run: Select candidates only, no execution. Output includes candidate details.
    - --real-backtest: Execute actual backtest validation via factor_backtest.main.

    Args:
        library_path: Path to factor library JSON file.
        days: Select factors not validated within this many days.
        status: Filter by evaluation status (e.g., 'active', 'stale', 'degraded').
        factor_ids: Comma-separated list of factor IDs to revalidate.
        dry_run: If True, only select candidates without execution.
        real_backtest: If True, execute actual backtest validation.
        no_write: If True, do not persist changes to library.

    Returns:
        dict with mode-specific fields:
        - dry-run: {mode, total_candidates, candidates: [...]}
        - status_refresh: {mode, total_candidates, success, failed, skipped, used_existing_results, details: [...]}
        - real-backtest: {mode, total_candidates, success, failed, errors: [...], details: [...]}
    """
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    # Mode validation: dry_run and real_backtest are mutually exclusive
    if dry_run and real_backtest:
        return {
            "mode": "error",
            "error": "Mutually exclusive flags: --dry-run and --real-backtest cannot be used together",
            "success": False,
        }

    # Determine mode
    if dry_run:
        mode = "dry_run"
    elif real_backtest:
        mode = "real_backtest"
    else:
        mode = "status_refresh"

    # Initialize base report with mode
    report = {
        "mode": mode,
        "total_candidates": 0,
    }

    try:
        manager = FactorLibraryManager(library_path)
    except Exception as e:
        return {
            "mode": mode,
            "error": f"Failed to load library: {library_path}",
            "error_detail": str(e),
            "success": False,
        }

    requested_ids = [item.strip() for item in (factor_ids or "").split(",") if item.strip()]
    candidates = manager.select_revalidation_candidates(days=days, status=status, factor_ids=requested_ids)
    report["total_candidates"] = len(candidates)

    # DRY-RUN MODE: Select candidates only, return detailed candidate info
    if dry_run:
        return {
            **report,
            "candidates": [
                {
                    "factor_id": entry.get("factor_id"),
                    "factor_name": entry.get("factor_name"),
                    "status": entry.get("evaluation", {}).get("status"),
                    "last_validated": entry.get("evaluation", {}).get("last_validated"),
                    "stability_score": entry.get("evaluation", {}).get("stability_score"),
                    "factor_expression": entry.get("factor_expression"),
                }
                for entry in candidates
            ],
            "success": True,
        }

    # Initialize counters for execution modes
    report["success"] = 0
    report["failed"] = 0
    report["skipped"] = 0
    report["used_existing_results"] = not real_backtest
    report["details"] = []

    # REAL-BACKTEST MODE: Execute actual backtest validation
    if real_backtest:
        report["errors"] = []
        config_path = backtest_config or _default_backtest_config_path()
        if not config_path:
            return _error_report(
                report,
                "Missing backtest configuration: provide --backtest_config or add configs/backtest.yaml",
            )

        for entry in candidates:
            factor_id = entry.get("factor_id")
            factor_expr = entry.get("factor_expression", "")
            before_status = entry.get("evaluation", {}).get("status")

            if not factor_expr:
                report["skipped"] += 1
                report["details"].append({
                    "factor_id": factor_id,
                    "status": "skipped",
                    "reason": "missing_factor_expression",
                    "before_status": before_status,
                    "after_status": before_status,
                    "revalidation_source": "real_backtest",
                })
                continue

            try:
                from quantaalpha.pipeline.factor_backtest import run_real_backtest

                runner_result = run_real_backtest(
                    config_path=config_path,
                    library_path=library_path,
                    factor_ids=factor_id,
                )
                if runner_result.get("error"):
                    raise RuntimeError(runner_result["error"])

                validation_result = _build_validation_result_from_metrics(
                    runner_result.get("metrics", {})
                )
                updated = manager.apply_validation_result(
                    entry, validation_result, persist=not no_write
                )
                report["success"] += 1
                report["details"].append({
                    "factor_id": factor_id,
                    "before_status": before_status,
                    "after_status": updated.get("evaluation", {}).get("status"),
                    "status": updated.get("evaluation", {}).get("status"),
                    "stability_score": updated.get("evaluation", {}).get("stability_score"),
                    "validation_summary": updated.get("evaluation", {}).get("validation_summary"),
                    "revalidation_source": "real_backtest",
                })

            except Exception as e:
                report["failed"] += 1
                error_msg = str(e)
                tb = traceback.format_exc()
                logger.error(f"Real backtest failed for factor {factor_id}: {error_msg}\n{tb}")
                report["errors"].append({
                    "factor_id": factor_id,
                    "error": error_msg,
                    "traceback": tb,
                })
                report["details"].append({
                    "factor_id": factor_id,
                    "status": "failed",
                    "error": error_msg,
                    "before_status": before_status,
                    "after_status": before_status,
                    "revalidation_source": "real_backtest",
                })

        return report

    # STATUS-REFRESH MODE: Reuse existing evaluation results
    for entry in candidates:
        factor_id = entry.get("factor_id")
        evaluation = entry.get("evaluation", {})
        before_status = evaluation.get("status")

        try:
            summary = {
                "stability_score": evaluation.get("stability_score"),
                "validation_summary": "status_refresh_reused_existing_summary",
            }
            validation_result = {
                "status": "success",
                "period_results": evaluation.get("period_results", []),
                "summary": summary,
            }
            updated = manager.apply_validation_result(entry, validation_result, persist=not no_write)
            report["success"] += 1
            report["details"].append({
                "factor_id": factor_id,
                "status": updated.get("evaluation", {}).get("status"),
                "before_status": before_status,
                "after_status": updated.get("evaluation", {}).get("status"),
                "stability_score": updated.get("evaluation", {}).get("stability_score"),
                "validation_summary": "reused_existing",
                "revalidation_source": "existing_results",
            })
        except Exception as e:
            report["failed"] += 1
            error_msg = str(e)
            logger.error(f"Failed to apply validation for factor {factor_id}: {error_msg}")
            report["details"].append({
                "factor_id": factor_id,
                "status": "failed",
                "error": error_msg,
                "before_status": before_status,
                "after_status": before_status,
                "revalidation_source": "existing_results",
            })

    return report


def _continuous_start(
    config: str = "config/pipeline.yaml",
    verbose: bool = False,
    **kwargs,
) -> None:
    """
    Start the continuous runtime in foreground loop.

    Args:
        config: Path to the pipeline configuration file.
        verbose: Enable verbose debug logging.
    """
    # Filter out Fire help flags
    kwargs.pop("help", None)
    kwargs.pop("h", None)
    from quantaalpha.continuous.main import start as continuous_start
    continuous_start(config=config, verbose=verbose, run_once=False)


def _continuous_once(
    config: str = "config/pipeline.yaml",
    verbose: bool = False,
    **kwargs,
) -> None:
    """
    Run a single deterministic cycle and exit.

    Args:
        config: Path to the pipeline configuration file.
        verbose: Enable verbose debug logging.
    """
    # Filter out Fire help flags
    kwargs.pop("help", None)
    kwargs.pop("h", None)
    from quantaalpha.continuous.main import once as continuous_once
    continuous_once(config=config, verbose=verbose)


def continuous(command: str = None, **kwargs):
    """
    Continuous runtime commands for 24H factor operations.

    Commands:
        start - Start continuous runtime in foreground loop
        once  - Run a single deterministic cycle and exit

    Usage:
        quantaalpha continuous start --config config/pipeline.yaml
        quantaalpha continuous once --config config/pipeline.yaml
    """
    if command == "start":
        _continuous_start(**kwargs)
    elif command == "once":
        _continuous_once(**kwargs)
    else:
        raise ValueError(
            "continuous command requires 'start' or 'once' subcommand. "
            "Usage: quantaalpha continuous start --config config/pipeline.yaml"
        )


def app(argv=None):
    result = fire.Fire(
        {
            "mine": mine,
            "backtest": backtest,
            "revalidate": revalidate,
            "health_check": health_check,
            "collect_info": collect_info,
            "continuous": continuous,
        },
        command=argv,
    )
    if _cli_result_failed(result):
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    app()
