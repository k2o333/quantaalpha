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


def revalidate(
    library_path: str,
    days: int | None = None,
    status: str | None = None,
    factor_ids: str | None = None,
    dry_run: bool = False,
    no_write: bool = False,
):
    manager = FactorLibraryManager(library_path)
    requested_ids = [item.strip() for item in (factor_ids or "").split(",") if item.strip()]
    candidates = manager.select_revalidation_candidates(days=days, status=status, factor_ids=requested_ids)
    report = {
        "total_candidates": len(candidates),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }
    if dry_run:
        return report | {"details": [entry["factor_id"] for entry in candidates]}

    for entry in candidates:
        evaluation = entry.get("evaluation", {})
        summary = {
            "stability_score": evaluation.get("stability_score"),
            "validation_summary": "revalidate_cli_reused_existing_summary",
        }
        validation_result = {
            "status": "success",
            "period_results": evaluation.get("period_results", []),
            "summary": summary,
        }
        updated = manager.apply_validation_result(entry, validation_result, persist=not no_write)
        report["success"] += 1
        report["details"].append(
            {
                "factor_id": updated.get("factor_id"),
                "status": updated.get("evaluation", {}).get("status"),
                "stability_score": updated.get("evaluation", {}).get("stability_score"),
            }
        )
    return report


def app():
    fire.Fire(
        {
            "mine": mine,
            "backtest": backtest,
            "revalidate": revalidate,
            "health_check": health_check,
            "collect_info": collect_info,
        }
    )


if __name__ == "__main__":
    app()
