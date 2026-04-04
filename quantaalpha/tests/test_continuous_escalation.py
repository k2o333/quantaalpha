"""Tests for EscalationState - model escalation state machine."""

import pytest


class TestEscalationState:
    """Tests for EscalationState state machine."""

    def _make_config(self):
        from quantaalpha.continuous.scheduler import EscalationConfig

        return EscalationConfig(
            enabled=True,
            trigger_after_failed_attempts=2,
            start_with_tier=1,
            escalate_to_max_tier=3,
            max_escalations_per_cycle=2,
        )

    def test_initial_state(self):
        """EscalationState starts at start_tier with zero failures."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        assert state.current_tier == 1
        assert state.consecutive_failures == 0
        assert state.total_escalations == 0

    def test_should_not_escalate_below_threshold(self):
        """Does not escalate when failures < threshold."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "test"})
        assert state.should_escalate(config) is False

    def test_should_escalate_at_threshold(self):
        """Escalates when failures >= threshold."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "fail1"})
        state.record_failure({"error": "fail2"})
        assert state.should_escalate(config) is True

    def test_escalate_increases_tier(self):
        """Escalation increases tier by 1 (up to max)."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "fail1"})
        state.record_failure({"error": "fail2"})
        state.escalate(config)
        assert state.current_tier == 2
        assert state.total_escalations == 1
        assert state.consecutive_failures == 0

    def test_escalate_respects_max_tier(self):
        """Tier does not exceed escalate_to_max_tier."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.current_tier = 3
        assert state.escalate(config) is False
        assert state.current_tier == 3

    def test_escalate_respects_max_escalations(self):
        """Total escalations do not exceed max_escalations_per_cycle."""
        from quantaalpha.continuous.escalation import EscalationState
        from quantaalpha.continuous.scheduler import EscalationConfig

        config = EscalationConfig(
            enabled=True,
            trigger_after_failed_attempts=1,
            start_with_tier=1,
            escalate_to_max_tier=3,
            max_escalations_per_cycle=1,
        )
        state = EscalationState(config)
        state.record_failure({"error": "fail1"})
        state.escalate(config)
        assert state.total_escalations == 1

        state.record_failure({"error": "fail2"})
        assert state.should_escalate(config) is False

    def test_record_success_resets_failures(self):
        """Success resets consecutive failures."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "fail"})
        state.record_success()
        assert state.consecutive_failures == 0

    def test_disabled_config_never_escalates(self):
        """When escalation is disabled, should_escalate always returns False."""
        from quantaalpha.continuous.escalation import EscalationState
        from quantaalpha.continuous.scheduler import EscalationConfig

        config = EscalationConfig(enabled=False)
        state = EscalationState(config)
        state.record_failure({"error": "fail"})
        state.record_failure({"error": "fail"})
        assert state.should_escalate(config) is False

    def test_failed_trajectories_stored(self):
        """Failed trajectories are stored for injection."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "fail1", "factor": "test1"})
        state.record_failure({"error": "fail2", "factor": "test2"})
        assert len(state.failed_trajectories) == 2
        assert state.failed_trajectories[0]["error"] == "fail1"

    def test_get_escalation_context_prompt(self):
        """get_escalation_context_prompt returns formatted string."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "fail1", "factor_expression": "ts_mean(close, 5)"})

        prompt = state.get_escalation_context_prompt()
        assert "Previous Failed Attempts" in prompt
        assert "fail1" in prompt
        assert "ts_mean(close, 5)" in prompt

    def test_get_escalation_context_prompt_empty(self):
        """get_escalation_context_prompt returns empty string when no failures."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        assert state.get_escalation_context_prompt() == ""

    def test_reset(self):
        """reset() restores initial state."""
        from quantaalpha.continuous.escalation import EscalationState

        config = self._make_config()
        state = EscalationState(config)
        state.record_failure({"error": "fail"})
        state.record_failure({"error": "fail"})
        state.escalate(config)
        state.reset(config)
        assert state.current_tier == 1
        assert state.consecutive_failures == 0
        assert state.total_escalations == 0
        assert len(state.failed_trajectories) == 0


class TestEscalationIntegration:
    """Tests for escalation integration in DefaultMiningScheduler."""

    def test_scheduler_accepts_escalation_cfg(self):
        """DefaultMiningScheduler accepts escalation_cfg parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            escalation_cfg={"enabled": True, "trigger_after_failed_attempts": 2},
        )
        assert scheduler._escalation_cfg["enabled"] is True
        assert scheduler._escalation_cfg["trigger_after_failed_attempts"] == 2

    def test_scheduler_escalation_defaults(self):
        """DefaultMiningScheduler defaults escalation to disabled."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=True)
        assert scheduler._escalation_cfg.get("enabled") is False
