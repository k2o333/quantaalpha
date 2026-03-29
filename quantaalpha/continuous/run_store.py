"""
Run Persistence Layer for 24H Continuous Factor MVP.

Provides JSON-first persistence for run summaries, enabling:
- Cycle-by-cycle audit trail
- Diagnostics for failed runs
- Historical trending of validation/mining metrics

Artifact format (schema_version=1.0):
{
    "schema_version": "1.0",
    "cycle_timestamp": "<ISO8601>",
    "cycle_type": "once" | "start" | "revalidation" | "mining",
    "config_snapshot": {
        "min_ic": float,
        "max_revalidation_per_run": int,
        "max_mining_per_run": int,
    },
    "data_update": {
        "updated": bool,
        "updated_interfaces": list[str],
        "stale_interfaces": list[str],
        "latest_dates": dict[str, str],
        "freshness_delta": dict[str, int],   # Wave A/B: seconds since last update per interface
        "advanced_interfaces": list[str],    # Wave A/B: advanced interface names
        "unchanged_after_update": list[str], # Wave A/B: interfaces with no changes after update
    },
    "impact_groups": list[str],
    "candidate_factors": {
        "count": int,
        "source": "revalidation" | "mining",
    },
    "validation_summary": {
        "total": int,
        "passed": int,
        "failed": int,
        "errors": list[str],
    },
    "mining_summary": {
        "generated": int,
        "validated": int,
        "added": int,
        "errors": list[str],
    },
    "run_summary": {
        "duration_seconds": float,
        "errors": list[str],
        "budget_exhausted": bool,           # Wave A/B: budget fully consumed
        "budget_remaining_seconds": float,   # Wave A/B: remaining budget time
    },
}
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Schema version for run summary artifacts
SCHEMA_VERSION = "1.0"

# Default run store directory
DEFAULT_RUNS_DIR = "log/continuous/runs"


@dataclass
class ValidationSummary:
    """Summary of factor validation in a run."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class MiningSummary:
    """Summary of factor mining in a run."""

    generated: int = 0
    validated: int = 0
    added: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class DataUpdateSummary:
    """Summary of data update operations."""

    updated: bool = False
    updated_interfaces: list[str] = field(default_factory=list)
    stale_interfaces: list[str] = field(default_factory=list)
    latest_dates: dict[str, str] = field(default_factory=dict)
    # Wave A/B fields
    freshness_delta: dict[str, int] = field(default_factory=dict)
    advanced_interfaces: list[str] = field(default_factory=list)
    unchanged_after_update: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "updated": self.updated,
            "updated_interfaces": self.updated_interfaces,
            "stale_interfaces": self.stale_interfaces,
            "latest_dates": self.latest_dates,
            "freshness_delta": self.freshness_delta,
            "advanced_interfaces": self.advanced_interfaces,
            "unchanged_after_update": self.unchanged_after_update,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DataUpdateSummary":
        """Reconstruct from dictionary."""
        # Handle backward compatibility for Wave A/B schema changes
        fd = data.get("freshness_delta", {})
        if isinstance(fd, int):
            fd = {"_legacy_seconds": fd}  # old int format -> new dict format
        ua = data.get("unchanged_after_update", [])
        if isinstance(ua, bool):
            ua = [] if not ua else ["_legacy"]  # old bool format -> new list format
        return cls(
            updated=data.get("updated", False),
            updated_interfaces=data.get("updated_interfaces", []),
            stale_interfaces=data.get("stale_interfaces", []),
            latest_dates=data.get("latest_dates", {}),
            freshness_delta=fd,
            advanced_interfaces=data.get("advanced_interfaces", []),
            unchanged_after_update=ua,
        )


@dataclass
class RunSummary:
    """Full run summary artifact persisted to disk."""

    schema_version: str = SCHEMA_VERSION
    cycle_timestamp: str = ""
    cycle_type: str = ""  # "once", "start", "revalidation", "mining"
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    data_update: DataUpdateSummary = field(default_factory=DataUpdateSummary)
    impact_groups: list[str] = field(default_factory=list)
    candidate_factors_count: int = 0
    candidate_factors_source: str = ""  # "revalidation" or "mining"
    validation_summary: ValidationSummary = field(default_factory=ValidationSummary)
    mining_summary: MiningSummary = field(default_factory=MiningSummary)
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    # Wave A/B budget fields
    budget_exhausted: bool = False
    budget_remaining_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "schema_version": self.schema_version,
            "cycle_timestamp": self.cycle_timestamp,
            "cycle_type": self.cycle_type,
            "config_snapshot": self.config_snapshot,
            "data_update": self.data_update.to_dict(),
            "impact_groups": self.impact_groups,
            "candidate_factors": {
                "count": self.candidate_factors_count,
                "source": self.candidate_factors_source,
            },
            "validation_summary": {
                "total": self.validation_summary.total,
                "passed": self.validation_summary.passed,
                "failed": self.validation_summary.failed,
                "errors": self.validation_summary.errors,
            },
            "mining_summary": {
                "generated": self.mining_summary.generated,
                "validated": self.mining_summary.validated,
                "added": self.mining_summary.added,
                "errors": self.mining_summary.errors,
            },
            "run_summary": {
                "duration_seconds": self.duration_seconds,
                "errors": self.errors,
                "budget_exhausted": self.budget_exhausted,
                "budget_remaining_seconds": self.budget_remaining_seconds,
            },
        }
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> "RunSummary":
        """Reconstruct from dictionary."""
        data_update = DataUpdateSummary.from_dict(data.get("data_update", {}))
        validation_data = data.get("validation_summary", {})
        validation_summary = ValidationSummary(
            total=validation_data.get("total", 0),
            passed=validation_data.get("passed", 0),
            failed=validation_data.get("failed", 0),
            errors=validation_data.get("errors", []),
        )
        mining_data = data.get("mining_summary", {})
        mining_summary = MiningSummary(
            generated=mining_data.get("generated", 0),
            validated=mining_data.get("validated", 0),
            added=mining_data.get("added", 0),
            errors=mining_data.get("errors", []),
        )
        run_summary = data.get("run_summary", {})
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            cycle_timestamp=data.get("cycle_timestamp", ""),
            cycle_type=data.get("cycle_type", ""),
            config_snapshot=data.get("config_snapshot", {}),
            data_update=data_update,
            impact_groups=data.get("impact_groups", []),
            candidate_factors_count=data.get("candidate_factors", {}).get("count", 0),
            candidate_factors_source=data.get("candidate_factors", {}).get("source", ""),
            validation_summary=validation_summary,
            mining_summary=mining_summary,
            duration_seconds=run_summary.get("duration_seconds", 0.0),
            errors=run_summary.get("errors", []),
            budget_exhausted=run_summary.get("budget_exhausted", False),
            budget_remaining_seconds=run_summary.get("budget_remaining_seconds", 0.0),
        )


class RunStore:
    """
    Persists run summary artifacts to disk.

    Usage:
        store = RunStore("log/continuous/runs")

        # Persist a run
        summary = RunSummary(cycle_type="once", cycle_timestamp=datetime.now().isoformat())
        store.save(summary)

        # Load recent runs
        runs = store.list_runs(limit=10)
    """

    def __init__(self, runs_dir: str = DEFAULT_RUNS_DIR):
        """
        Initialize the run store.

        Args:
            runs_dir: Directory to store run JSON artifacts.
        """
        self.runs_dir = Path(runs_dir)
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure the runs directory exists."""
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def _run_filename(self, timestamp: datetime) -> Path:
        """Generate filename for a run artifact."""
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        return self.runs_dir / f"run_{ts_str}.json"

    def save(self, summary: RunSummary) -> str:
        """
        Persist a run summary to disk.

        Args:
            summary: RunSummary artifact to persist.

        Returns:
            Path to the saved artifact file.
        """
        self._ensure_dir()

        # Parse timestamp
        if summary.cycle_timestamp:
            try:
                ts = datetime.fromisoformat(summary.cycle_timestamp)
            except ValueError:
                ts = datetime.now()
        else:
            ts = datetime.now()
            summary.cycle_timestamp = ts.isoformat()

        filepath = self._run_filename(ts)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary.to_json())
            logger.info(f"Run summary saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save run summary to {filepath}: {e}")
            raise

        return str(filepath)

    def load(self, filepath: str) -> RunSummary:
        """
        Load a run summary from disk.

        Args:
            filepath: Path to the run JSON artifact.

        Returns:
            Reconstructed RunSummary instance.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RunSummary.from_dict(data)

    def list_runs(
        self,
        cycle_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[RunSummary]:
        """
        List recent run summaries.

        Args:
            cycle_type: Optional filter by cycle type.
            limit: Maximum number of runs to return.

        Returns:
            List of RunSummary instances, newest first.
        """
        if not self.runs_dir.exists():
            return []

        runs = []
        for filepath in sorted(self.runs_dir.glob("run_*.json"), reverse=True):
            try:
                summary = self.load(str(filepath))
                if cycle_type is None or summary.cycle_type == cycle_type:
                    runs.append(summary)
                    if len(runs) >= limit:
                        break
            except Exception as e:
                logger.warning(f"Failed to load run {filepath}: {e}")
                continue

        return runs

    def get_latest_run(self) -> Optional[RunSummary]:
        """
        Get the most recent run summary.

        Returns:
            Latest RunSummary or None if no runs exist.
        """
        runs = self.list_runs(limit=1)
        return runs[0] if runs else None

    def get_run_count(self) -> int:
        """Get total number of persisted runs."""
        if not self.runs_dir.exists():
            return 0
        return len(list(self.runs_dir.glob("run_*.json")))
