"""Resource governance primitives for continuous mining.

This module keeps decision logic pure and leaves file locking in a small
adapter so scheduler tests can exercise resource policy without filesystem
fixtures.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GovernorConfig:
    """Runtime resource-governor configuration."""

    enabled: bool = False
    max_concurrent_mining_jobs: int = 1
    max_concurrent_revalidation_jobs: int = 1
    max_factor_workers: int = 8
    max_memory_soft_limit_gb: float | None = None
    max_disk_usage_ratio: float | None = None
    pause_when_data_updating: bool = True
    pause_when_compaction_running: bool = True

    @classmethod
    def from_dict(cls, data: dict | None) -> "GovernorConfig":
        """Parse the mining.resource_governor config block."""
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            max_concurrent_mining_jobs=int(data.get("max_concurrent_mining_jobs", 1)),
            max_concurrent_revalidation_jobs=int(data.get("max_concurrent_revalidation_jobs", 1)),
            max_factor_workers=int(data.get("max_factor_workers", 8)),
            max_memory_soft_limit_gb=data.get("max_memory_soft_limit_gb"),
            max_disk_usage_ratio=data.get("max_disk_usage_ratio"),
            pause_when_data_updating=bool(data.get("pause_when_data_updating", True)),
            pause_when_compaction_running=bool(data.get("pause_when_compaction_running", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize back to pipeline config snapshots."""
        return {
            "enabled": self.enabled,
            "max_concurrent_mining_jobs": self.max_concurrent_mining_jobs,
            "max_concurrent_revalidation_jobs": self.max_concurrent_revalidation_jobs,
            "max_factor_workers": self.max_factor_workers,
            "max_memory_soft_limit_gb": self.max_memory_soft_limit_gb,
            "max_disk_usage_ratio": self.max_disk_usage_ratio,
            "pause_when_data_updating": self.pause_when_data_updating,
            "pause_when_compaction_running": self.pause_when_compaction_running,
        }


@dataclass(frozen=True)
class ResourceRequest:
    """A scheduler request to enter a governed section."""

    scheduler: str
    run_id: str
    lock_name: str = "global_compute_lock"


@dataclass(frozen=True)
class ResourceState:
    """Observed resource state used by the pure governor decision."""

    active_compute_owner: str | None = None
    data_ready: bool = True
    failed_readiness_probes: list[str] = field(default_factory=list)
    compaction_running: bool = False
    data_updating: bool = False


def _snapshot_marker_ready(marker_path: str | Path | None) -> bool | None:
    if marker_path is None:
        return None
    try:
        marker = Path(marker_path)
        if not marker.exists():
            return False
        payload = json.loads(marker.read_text(encoding="utf-8"))
        return bool(payload.get("ready", False))
    except Exception:
        return False


def build_resource_state_from_readiness(
    *,
    app5_freshness: dict[str, Any] | None = None,
    snapshot_marker_path: str | Path | None = None,
    data_monitor_ready: bool = True,
    compaction_running: bool = False,
    data_updating: bool = False,
    active_compute_owner: str | None = None,
) -> ResourceState:
    """Aggregate readiness probes into the ResourceGovernor state model."""
    failed: list[str] = []

    if app5_freshness is not None and app5_freshness.get("status") != "passed":
        failed.append("app5_freshness")

    marker_ready = _snapshot_marker_ready(snapshot_marker_path)
    if marker_ready is False:
        failed.append("snapshot_marker")

    if not data_monitor_ready:
        failed.append("data_monitor")

    return ResourceState(
        active_compute_owner=active_compute_owner,
        data_ready=not failed,
        failed_readiness_probes=failed,
        compaction_running=compaction_running,
        data_updating=data_updating,
    )


@dataclass(frozen=True)
class ResourceDecision:
    """Decision returned by the resource governor."""

    allowed: bool
    action: str
    reason: str
    scheduler: str
    run_id: str
    lock_name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for run-store governance events."""
        return {
            "allowed": self.allowed,
            "action": self.action,
            "reason": self.reason,
            "scheduler": self.scheduler,
            "run_id": self.run_id,
            "lock_name": self.lock_name,
            "metadata": self.metadata,
        }


def evaluate_resource_request(
    request: ResourceRequest,
    state: ResourceState,
    config: GovernorConfig,
) -> ResourceDecision:
    """Return the scheduler decision for a resource request."""
    if not config.enabled:
        return ResourceDecision(
            allowed=True,
            action="allow",
            reason="resource_governor_disabled",
            scheduler=request.scheduler,
            run_id=request.run_id,
            lock_name=request.lock_name,
        )

    if not state.data_ready:
        return ResourceDecision(
            allowed=False,
            action="defer",
            reason="deferred_data_not_ready",
            scheduler=request.scheduler,
            run_id=request.run_id,
            lock_name=request.lock_name,
            metadata={"failed_readiness_probes": list(state.failed_readiness_probes)},
        )

    if config.pause_when_data_updating and state.data_updating:
        return ResourceDecision(
            allowed=False,
            action="defer",
            reason="data_update_in_progress",
            scheduler=request.scheduler,
            run_id=request.run_id,
            lock_name=request.lock_name,
        )

    if config.pause_when_compaction_running and state.compaction_running:
        return ResourceDecision(
            allowed=False,
            action="defer",
            reason="factor_store_compaction_running",
            scheduler=request.scheduler,
            run_id=request.run_id,
            lock_name=request.lock_name,
        )

    if state.active_compute_owner and state.active_compute_owner != request.scheduler:
        return ResourceDecision(
            allowed=False,
            action="defer",
            reason="global_compute_lock_held",
            scheduler=request.scheduler,
            run_id=request.run_id,
            lock_name=request.lock_name,
            metadata={"active_compute_owner": state.active_compute_owner},
        )

    return ResourceDecision(
        allowed=True,
        action="acquire",
        reason="resource_envelope_available",
        scheduler=request.scheduler,
        run_id=request.run_id,
        lock_name=request.lock_name,
    )


@dataclass(frozen=True)
class LockEvent:
    """Observable lock event for run summaries."""

    event: str
    lock_name: str
    owner: str
    run_id: str
    path: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "lock_name": self.lock_name,
            "owner": self.owner,
            "run_id": self.run_id,
            "path": self.path,
            "timestamp": self.timestamp,
        }


class FileLock:
    """Small `fcntl.flock()` based exclusive file lock."""

    def __init__(
        self,
        lock_path: str | Path,
        *,
        timeout_seconds: float = 0,
        owner: str = "",
        run_id: str = "",
    ) -> None:
        self.lock_path = Path(lock_path)
        self.timeout_seconds = float(timeout_seconds)
        self.owner = owner
        self.run_id = run_id
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Acquire the lock, returning False when a nonblocking attempt is busy."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o664)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fd = fd
                self._write_metadata()
                return True
            except BlockingIOError:
                if self.timeout_seconds <= 0 or time.monotonic() >= deadline:
                    os.close(fd)
                    return False
                time.sleep(0.05)

    def release(self) -> None:
        """Release the lock if currently held."""
        if self._fd is None:
            return
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

    def read_metadata(self) -> dict[str, Any]:
        """Read lock owner metadata."""
        if not self.lock_path.exists():
            return {}
        raw = self.lock_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        return json.loads(raw)

    def _write_metadata(self) -> None:
        metadata = {
            "owner": self.owner,
            "run_id": self.run_id,
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        os.ftruncate(self._fd, 0)
        os.write(self._fd, json.dumps(metadata, ensure_ascii=False).encode("utf-8"))
