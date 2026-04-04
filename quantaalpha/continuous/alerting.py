"""
Alerting Module - Circuit Breaker and Degradation Alert Dispatcher.

Provides AlertDispatcher for sending alerts when:
1. Circuit breaker triggers (consecutive zero-pass cycles)
2. Factor degradation is detected (IC below threshold)

Supports webhook integration for enterprise IM platforms:
- WeChat Work (企业微信)
- Feishu (飞书)
- DingTalk (钉钉)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert event types."""

    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    CIRCUIT_BREAKER_CRITICAL = "circuit_breaker_critical"
    DEGRADATION_DETECTED = "degradation_detected"
    ZERO_PASS_CYCLE = "zero_pass_cycle"


@dataclass
class AlertEvent:
    """An alert event to be dispatched."""

    alert_type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
        }


class AlertDispatcher:
    """
    Dispatcher for alerting events.

    Sends webhook notifications for circuit breaker and degradation events.

    Usage:
        dispatcher = AlertDispatcher()
        dispatcher.dispatch(
            AlertType.CIRCUIT_BREAKER_TRIGGERED,
            AlertSeverity.WARNING,
            "Circuit breaker triggered after 3 consecutive zero-pass cycles",
            payload={"consecutive_zero_pass": 3, "cooldown_count": 1}
        )
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        enabled: bool = True,
        circuit_breaker_threshold: int = 3,
        degradation_ic_threshold: float = 0.005,
    ):
        """
        Initialize the AlertDispatcher.

        Args:
            webhook_url: Optional webhook URL for notifications.
            enabled: Whether alerts are enabled.
            circuit_breaker_threshold: Number of consecutive zero-pass cycles
                before sending circuit breaker alert.
            degradation_ic_threshold: IC threshold below which degradation is flagged.
        """
        self.webhook_url = webhook_url
        self.enabled = enabled
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.degradation_ic_threshold = degradation_ic_threshold
        self._dispatch_history: list[AlertEvent] = []

    def dispatch(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Dispatch an alert event.

        Args:
            alert_type: Type of the alert.
            severity: Severity level.
            message: Human-readable alert message.
            payload: Additional payload data.

        Returns:
            True if dispatch succeeded (or is mock/simulated), False otherwise.
        """
        if not self.enabled:
            logger.debug("Alerts disabled, skipping dispatch")
            return True

        event = AlertEvent(
            alert_type=alert_type,
            severity=severity,
            message=message,
            payload=payload or {},
        )

        self._dispatch_history.append(event)
        logger.info(
            f"Alert dispatched: [{severity.value}] {alert_type.value} - {message}"
        )

        # Send webhook if configured
        if self.webhook_url:
            return self._send_webhook(event)
        else:
            # No webhook configured - consider it success (for testing)
            logger.debug("No webhook_url configured, alert logged only")
            return True

    def _send_webhook(self, event: AlertEvent) -> bool:
        """
        Send alert event via webhook.

        Args:
            event: AlertEvent to send.

        Returns:
            True if successful, False otherwise.
        """
        try:
            import json
            import urllib.request

            payload = json.dumps(event.to_dict()).encode("utf-8")
            req = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Webhook sent successfully: {event.alert_type.value}")
                    return True
                else:
                    logger.warning(
                        f"Webhook returned status {response.status}: {event.alert_type.value}"
                    )
                    return False

        except urllib.error.URLError as e:
            logger.error(f"Webhook URL error: {e}")
            return False
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return False

    def dispatch_circuit_breaker(
        self,
        consecutive_zero_pass: int,
        cooldown_count: int,
        is_critical: bool = False,
    ) -> bool:
        """
        Dispatch circuit breaker alert.

        Args:
            consecutive_zero_pass: Number of consecutive zero-pass cycles.
            cooldown_count: Number of cooldown cycles.
            is_critical: Whether this is a critical (max cooldown) alert.

        Returns:
            True if dispatch succeeded.
        """
        if is_critical:
            alert_type = AlertType.CIRCUIT_BREAKER_CRITICAL
            severity = AlertSeverity.CRITICAL
            message = (
                f"CIRCUIT BREAKER CRITICAL: {cooldown_count} consecutive cooldowns "
                f"without recovery. System may need manual inspection."
            )
        else:
            alert_type = AlertType.CIRCUIT_BREAKER_TRIGGERED
            severity = AlertSeverity.WARNING
            message = (
                f"Circuit breaker triggered after {consecutive_zero_pass} "
                f"consecutive zero-pass cycles (cooldown #{cooldown_count})"
            )

        return self.dispatch(
            alert_type=alert_type,
            severity=severity,
            message=message,
            payload={
                "consecutive_zero_pass": consecutive_zero_pass,
                "cooldown_count": cooldown_count,
                "is_critical": is_critical,
            },
        )

    def dispatch_degradation(
        self,
        factor_id: str,
        factor_name: str,
        current_ic: float,
        threshold: float,
        reason: str,
    ) -> bool:
        """
        Dispatch degradation alert for a factor.

        Args:
            factor_id: Factor identifier.
            factor_name: Factor display name.
            current_ic: Current IC value.
            threshold: Threshold that was breached.
            reason: Degradation reason description.

        Returns:
            True if dispatch succeeded.
        """
        return self.dispatch(
            alert_type=AlertType.DEGRADATION_DETECTED,
            severity=AlertSeverity.WARNING,
            message=(
                f"Factor degradation detected: {factor_name} (IC={current_ic:.4f} "
                f"< threshold={threshold:.4f}) - {reason}"
            ),
            payload={
                "factor_id": factor_id,
                "factor_name": factor_name,
                "current_ic": current_ic,
                "threshold": threshold,
                "reason": reason,
            },
        )

    def get_dispatch_history(self) -> list[AlertEvent]:
        """Get the history of dispatched alerts."""
        return self._dispatch_history.copy()

    def clear_history(self) -> None:
        """Clear dispatch history."""
        self._dispatch_history.clear()
