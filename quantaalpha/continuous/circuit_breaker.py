"""Continuous mining circuit breaker state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class ContinuousCircuitBreaker:
    """Mining 前置 cooldown 状态。"""

    state: Literal["closed", "open", "half_open"] = "closed"
    open_until: datetime | None = None
    reason: str = ""
    half_open_probe_limit: int = 1
    half_open_probe_count: int = 0

    @classmethod
    def open_until(cls, open_until: datetime, *, reason: str) -> "ContinuousCircuitBreaker":
        return cls(state="open", open_until=open_until, reason=reason)

    def should_skip_mining(self, now: datetime | None = None) -> tuple[bool, str]:
        now = now or datetime.now()
        if self.state == "open":
            if self.open_until is not None and now >= self.open_until:
                self.state = "half_open"
            else:
                return True, self.reason or "circuit_breaker_open"
        if self.state == "half_open":
            if self.half_open_probe_count >= self.half_open_probe_limit:
                return True, self.reason or "half_open_probe_limit"
            self.half_open_probe_count += 1
        return False, ""
