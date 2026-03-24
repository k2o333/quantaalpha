"""
AlphaAgent logging module - compatibility layer.

Maps alphaagent.log to rdagent.log so all alphaagent.log imports work.
Provides AlphaAgent-specific APIs: log_trace_path, set_trace_path.

When rdagent.log is not available, falls back to a standard library logging implementation
that provides the same interface.
"""

from pathlib import Path
from enum import Enum
import logging
import os
import tempfile


class LogColors(Enum):
    """Color codes for terminal output, compatible with rdagent.log.utils.LogColors."""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


class FallbackFileStorage:
    """
    Minimal FileStorage implementation for fallback logger.
    Provides the path property and truncate method used by the codebase.
    """

    def __init__(self, path: Path | str):
        self._path = Path(path)
        # Ensure directory exists
        self._path.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Return the storage path."""
        return self._path

    def truncate(self, time: float | None = None) -> None:
        """
        Truncate log files older than the given time.
        This is a no-op in fallback mode.
        """
        pass


class FallbackLoggerWrapper:
    """
    Wraps a standard library logger and adds log_trace_path / set_trace_path.
    Other attributes/methods delegate to the underlying logger.
    """

    def __init__(self, inner: logging.Logger):
        object.__setattr__(self, "_inner", inner)
        # Set default trace path to temp directory
        default_trace_path = Path(os.environ.get(
            "LOG_TRACE_PATH",
            str(Path(tempfile.gettempdir()) / "quantaalpha_logs")
        ))
        object.__setattr__(self, "_storage", FallbackFileStorage(default_trace_path))

    @property
    def log_trace_path(self) -> Path:
        """Return current log trace path."""
        return self._storage.path

    def set_trace_path(self, path: str | Path) -> None:
        """Set new log trace path."""
        object.__setattr__(self, "_storage", FallbackFileStorage(Path(path)))

    @property
    def storage(self) -> FallbackFileStorage:
        """Return the storage object."""
        return self._storage

    # ---------- AlphaAgent extension: delegate to underlying logger ----------
    def __getattr__(self, name: str):
        return getattr(self._inner, name)

    def __setattr__(self, name: str, value) -> None:
        if name in ("_inner", "_storage"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._inner, name, value)


# Try to import from rdagent.log, fall back to standard library logging
try:
    from rdagent.log import rdagent_logger as _rdagent_logger
    from rdagent.log.utils import LogColors as _LogColors

    # Use rdagent's logger if available
    logger = _rdagent_logger
    # Override LogColors if rdagent provides it, otherwise use our fallback
    if _LogColors is not None:
        LogColors = _LogColors

except ImportError:
    # Fallback: create a standard library logger with same interface
    _fallback_logger = logging.getLogger("quantaalpha")
    _fallback_logger.setLevel(logging.INFO)

    # Add a console handler if no handlers exist
    if not _fallback_logger.handlers:
        _handler = logging.StreamHandler()
        _handler.setLevel(logging.INFO)
        _formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        _handler.setFormatter(_formatter)
        _fallback_logger.addHandler(_handler)

    logger = FallbackLoggerWrapper(_fallback_logger)

__all__ = ["logger", "LogColors"]
