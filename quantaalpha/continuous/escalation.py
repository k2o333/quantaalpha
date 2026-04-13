"""
Model escalation state machine for continuous mining.

Tracks consecutive failures and triggers tier escalation when thresholds are met.
"""

from __future__ import annotations

import logging
from typing import Any

from quantaalpha.continuous.scheduler import EscalationConfig

logger = logging.getLogger(__name__)


class EscalationState:
    """State machine for model escalation."""

    def __init__(self, config: EscalationConfig):
        self.current_tier = config.start_with_tier
        self.consecutive_failures = 0
        self.total_escalations = 0
        self.failed_trajectories: list[dict[str, Any]] = []

    def should_escalate(self, config: EscalationConfig) -> bool:
        """Check if escalation conditions are met."""
        if not config.enabled:
            return False
        if self.total_escalations >= config.max_escalations_per_cycle:
            return False
        if self.current_tier >= config.escalate_to_max_tier:
            return False
        return self.consecutive_failures >= config.trigger_after_failed_attempts

    def record_success(self) -> None:
        """Record a successful mining run. Resets failure counter."""
        self.consecutive_failures = 0
        self.failed_trajectories.clear()
        logger.info("Escalation: success recorded, failures reset")

    def record_failure(self, trajectory_data: dict[str, Any]) -> None:
        """Record a failed mining run. Stores trajectory for injection."""
        self.consecutive_failures += 1
        self.failed_trajectories.append(trajectory_data)
        logger.info(f"Escalation: failure recorded ({self.consecutive_failures} consecutive)")

    def escalate(self, config: EscalationConfig) -> bool:
        """
        Perform escalation to next tier.

        Returns True if escalation was performed, False if not possible.
        """
        if not self.should_escalate(config):
            return False

        new_tier = self.current_tier + 1
        if new_tier > config.escalate_to_max_tier:
            return False

        self.current_tier = new_tier
        self.total_escalations += 1
        self.consecutive_failures = 0
        self.failed_trajectories.clear()  # Reset trajectories along with counter for semantic consistency
        logger.info(f"Escalation: tier increased to {self.current_tier} (total escalations: {self.total_escalations})")
        return True

    def reset(self, config: EscalationConfig) -> None:
        """Reset state to initial values (e.g., at start of new cycle)."""
        self.current_tier = config.start_with_tier
        self.consecutive_failures = 0
        self.total_escalations = 0
        self.failed_trajectories.clear()

    def get_escalation_context_prompt(self) -> str:
        """
        Build a prompt string with failed trajectory context for injection.

        Returns empty string if no failures.
        """
        if not self.failed_trajectories:
            return ""

        lines = [
            "## Previous Failed Attempts",
            "The following factor generation attempts failed. Please learn from them:",
            "",
        ]
        for i, traj in enumerate(self.failed_trajectories, 1):
            lines.append(f"### Attempt {i}")
            if "error" in traj:
                lines.append(f"Error: {traj['error']}")
            if "factor_expression" in traj:
                lines.append(f"Factor: {traj['factor_expression']}")
            if "feedback" in traj:
                lines.append(f"Feedback: {traj['feedback']}")
            lines.append("")

        return "\n".join(lines)
