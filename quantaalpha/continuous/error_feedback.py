from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Iterable


def normalize_factor_error(error: dict) -> dict:
    """Return a stable, prompt-safe factor error event."""
    normalized = {
        "expression": str(error.get("expression", "")),
        "error_type": str(error.get("error_type", "")),
        "error_message": str(error.get("error_message", "")),
        "source": str(error.get("source", "")),
        "created_at": str(error.get("created_at") or datetime.now(UTC).isoformat(timespec="seconds")),
    }
    factor_id = error.get("factor_id")
    if factor_id:
        normalized["factor_id"] = str(factor_id)
    return normalized


def factor_error_key(error: dict) -> tuple[str, str, str, str]:
    """Build a deduplication key that ignores source and timestamp."""
    return (
        str(error.get("factor_id", "")),
        str(error.get("expression", "")),
        str(error.get("error_type", "")),
        str(error.get("error_message", "")),
    )


def merge_factor_errors(*groups: Iterable[dict]) -> list[dict]:
    """Merge error groups while preserving first occurrence order."""
    merged: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for group in groups:
        for raw_error in group or []:
            error = normalize_factor_error(raw_error)
            key = factor_error_key(error)
            if key in seen:
                continue
            seen.add(key)
            merged.append(error)
    return merged


class FactorErrorFeedbackSink:
    """Bounded in-process store for continuous factor errors."""

    def __init__(self, max_errors: int = 100):
        self.max_errors = max(1, int(max_errors))
        self._errors: deque[dict] = deque(maxlen=self.max_errors)

    def add(self, error: dict) -> None:
        normalized = normalize_factor_error(error)
        key = factor_error_key(normalized)
        self._errors = deque(
            [existing for existing in self._errors if factor_error_key(existing) != key],
            maxlen=self.max_errors,
        )
        self._errors.append(normalized)

    def extend(self, errors: Iterable[dict]) -> None:
        for error in errors or []:
            self.add(error)

    def select(
        self,
        *,
        max_errors: int = 5,
        sources: set[str] | None = None,
    ) -> list[dict]:
        selected: list[dict] = []
        for error in reversed(self._errors):
            if sources is not None and error.get("source") not in sources:
                continue
            selected.append(dict(error))
            if len(selected) >= max_errors:
                break
        return selected
