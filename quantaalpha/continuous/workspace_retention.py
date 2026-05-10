"""Workspace scratch retention planner and cleaner."""

from __future__ import annotations

import fnmatch
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event, Thread


@dataclass(frozen=True)
class RetentionRootConfig:
    """Single retention root and include patterns."""

    root: Path | str
    include_patterns: list[str]


@dataclass(frozen=True)
class RetentionItem:
    """A deletion candidate."""

    path: Path
    root: Path
    bytes: int
    mtime: datetime
    reason: str
    is_dir: bool = False


@dataclass(frozen=True)
class RetentionPlan:
    """Deletion plan."""

    items: list[RetentionItem]
    cutoff: datetime


@dataclass(frozen=True)
class RetentionResult:
    """Deletion result."""

    deleted_count: int
    deleted_bytes: int
    manifest_path: Path
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkspaceRetentionConfig:
    """Runtime retention config parsed from pipeline.yaml."""

    enabled: bool = False
    retention_hours: int = 72
    cleanup_interval_hours: int = 72
    manifest_dir: str = "log/retention"
    dry_run: bool = True
    roots: list[RetentionRootConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> "WorkspaceRetentionConfig":
        if not data:
            return cls()
        roots = [
            RetentionRootConfig(
                root=item.get("root", ""),
                include_patterns=list(item.get("include_patterns", [])),
            )
            for item in data.get("roots", [])
        ]
        return cls(
            enabled=data.get("enabled", False),
            retention_hours=data.get("retention_hours", 72),
            cleanup_interval_hours=data.get("cleanup_interval_hours", 72),
            manifest_dir=data.get("manifest_dir", "log/retention"),
            dry_run=data.get("dry_run", True),
            roots=roots,
        )


class WorkspaceRetentionCleaner:
    """Plan and delete old scratch files under configured roots."""

    def __init__(
        self,
        *,
        roots: list[RetentionRootConfig],
        retention_hours: int = 72,
        now: datetime | None = None,
        manifest_dir: str | Path = "log/retention",
    ):
        self.roots = [RetentionRootConfig(root=Path(root.root), include_patterns=root.include_patterns) for root in roots]
        self.retention_hours = retention_hours
        self.now = now or datetime.now()
        self.manifest_dir = Path(manifest_dir)

    def plan(self) -> RetentionPlan:
        """Build a deterministic deletion plan."""

        cutoff = self.now - timedelta(hours=self.retention_hours)
        items: list[RetentionItem] = []
        for root_cfg in self.roots:
            root = root_cfg.root.resolve()
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    continue
                if not path.exists():
                    continue
                rel = path.relative_to(root).as_posix()
                matched_pattern = self._matched_pattern(rel, root_cfg.include_patterns)
                if not matched_pattern:
                    continue
                stat = path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if mtime >= cutoff:
                    continue
                items.append(
                    RetentionItem(
                        path=path,
                        root=root,
                        bytes=self._path_size(path),
                        mtime=mtime,
                        reason=f"matched {matched_pattern}; older than {self.retention_hours}h",
                        is_dir=path.is_dir(),
                    )
                )
        return RetentionPlan(items=items, cutoff=cutoff)

    def apply(self, *, dry_run: bool = False) -> RetentionResult:
        """Write manifest and delete planned paths unless dry-run is requested."""

        plan = self.plan()
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.manifest_dir / f"workspace-cleanup-{self.now.strftime('%Y%m%d-%H%M%S')}.jsonl"
        with manifest_path.open("w", encoding="utf-8") as fh:
            for item in plan.items:
                fh.write(
                    json.dumps(
                        {
                            "path": str(item.path),
                            "root": str(item.root),
                            "bytes": item.bytes,
                            "mtime": item.mtime.isoformat(),
                            "reason": item.reason,
                            "is_dir": item.is_dir,
                            "dry_run": dry_run,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )

        if dry_run:
            return RetentionResult(
                deleted_count=0,
                deleted_bytes=0,
                manifest_path=manifest_path,
            )

        errors: list[str] = []
        deleted_count = 0
        deleted_bytes = 0
        for item in sorted(plan.items, key=lambda candidate: len(candidate.path.parts), reverse=True):
            try:
                if not item.path.exists() or item.path.is_symlink():
                    continue
                if item.is_dir:
                    shutil.rmtree(item.path)
                else:
                    item.path.unlink()
                deleted_count += 1
                deleted_bytes += item.bytes
            except Exception as exc:  # pragma: no cover - defensive logging path
                errors.append(f"{item.path}: {exc}")

        self._remove_empty_dirs()
        return RetentionResult(
            deleted_count=deleted_count,
            deleted_bytes=deleted_bytes,
            manifest_path=manifest_path,
            errors=errors,
        )

    @staticmethod
    def _matched_pattern(rel_path: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(Path(rel_path).name, pattern):
                return pattern
        return None

    @staticmethod
    def _path_size(path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            return sum(child.stat().st_size for child in path.rglob("*") if child.is_file() and not child.is_symlink())
        return 0

    def _remove_empty_dirs(self) -> None:
        for root_cfg in self.roots:
            root = root_cfg.root.resolve()
            if not root.exists():
                continue
            for path in sorted((child for child in root.rglob("*") if child.is_dir()), key=lambda p: len(p.parts), reverse=True):
                try:
                    path.rmdir()
                except OSError:
                    pass


class WorkspaceRetentionScheduler:
    """Run workspace retention periodically in the continuous runtime."""

    def __init__(self, config: WorkspaceRetentionConfig):
        self.config = config
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._last_run: datetime | None = None
        self.last_result: RetentionResult | None = None

    def start(self) -> None:
        if not self.config.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def run_if_due(self, now: datetime | None = None) -> RetentionResult | None:
        if not self.config.enabled:
            return None
        now = now or datetime.now()
        if self._last_run is not None:
            elapsed_hours = (now - self._last_run).total_seconds() / 3600
            if elapsed_hours < self.config.cleanup_interval_hours:
                return None
        manifest_dir = Path(self.config.manifest_dir)
        manifest_dir.mkdir(parents=True, exist_ok=True)
        lock_path = manifest_dir / "workspace-cleanup.lock"
        try:
            from filelock import FileLock, Timeout

            with FileLock(str(lock_path), timeout=0):
                result = self._run_cleanup(now)
        except Timeout:
            return None
        except ImportError:
            result = self._run_cleanup(now)
        self._last_run = now
        self.last_result = result
        return result

    def _run_cleanup(self, now: datetime) -> RetentionResult:
        cleaner = WorkspaceRetentionCleaner(
            roots=self.config.roots,
            retention_hours=self.config.retention_hours,
            now=now,
            manifest_dir=self.config.manifest_dir,
        )
        return cleaner.apply(dry_run=self.config.dry_run)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_if_due()
            self._stop_event.wait(timeout=300)
