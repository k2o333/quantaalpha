from __future__ import annotations

from .implementation_shared import *


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
