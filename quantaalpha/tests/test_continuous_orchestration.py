"""
Phase 2: Unit tests for single-cycle orchestration decision layer.

Tests cover:
- Condition evaluation (threshold, flag, all_of, any_of)
- Config validation
- SingleCycleOrchestrator behavior
- apply_result() context updates
"""

import pytest

from quantaalpha.continuous.orchestration import (
    ActionSpec,
    ActionResult,
    AllOfCondition,
    AnyOfCondition,
    FlagCondition,
    OrchestrationConfigError,
    OrchestrationContext,
    SingleCycleOrchestrator,
    ThresholdCondition,
    _compare,
    evaluate_condition,
    validate_orchestration_config,
)


# ============================================================================
# Condition Evaluation Tests
# ============================================================================


class TestConditionEvaluation:
    """Tests for the condition evaluation system."""

    def test_threshold_condition_true(self):
        """Threshold condition returns True when metric meets threshold."""
        context = OrchestrationContext(cycle_id="test", current_node="start", pass_rate=0.5)
        cond = ThresholdCondition(
            name="test_threshold",
            metric="pass_rate",
            operator="gte",
            value=0.3,
        )
        assert cond.evaluate(context, {}) is True

    def test_threshold_condition_false(self):
        """Threshold condition returns False when metric doesn't meet threshold."""
        context = OrchestrationContext(cycle_id="test", current_node="start", pass_rate=0.1)
        cond = ThresholdCondition(
            name="test_threshold",
            metric="pass_rate",
            operator="gte",
            value=0.3,
        )
        assert cond.evaluate(context, {}) is False

    def test_threshold_condition_gt_operator(self):
        """Test gt operator."""
        context = OrchestrationContext(cycle_id="test", current_node="start", generated_factors=5)
        cond = ThresholdCondition(
            name="test_gt",
            metric="generated_factors",
            operator="gt",
            value=3,
        )
        assert cond.evaluate(context, {}) is True

        context2 = OrchestrationContext(cycle_id="test", current_node="start", generated_factors=3)
        assert cond.evaluate(context2, {}) is False

    def test_threshold_condition_lt_operator(self):
        """Test lt operator."""
        context = OrchestrationContext(cycle_id="test", current_node="start", consecutive_failures=2)
        cond = ThresholdCondition(
            name="test_lt",
            metric="consecutive_failures",
            operator="lt",
            value=3,
        )
        assert cond.evaluate(context, {}) is True

    def test_threshold_condition_lte_operator(self):
        """Test lte operator."""
        context = OrchestrationContext(cycle_id="test", current_node="start", consecutive_failures=3)
        cond = ThresholdCondition(
            name="test_lte",
            metric="consecutive_failures",
            operator="lte",
            value=3,
        )
        assert cond.evaluate(context, {}) is True

    def test_threshold_condition_eq_operator(self):
        """Test eq operator."""
        context = OrchestrationContext(cycle_id="test", current_node="start", active_parents=5)
        cond = ThresholdCondition(
            name="test_eq",
            metric="active_parents",
            operator="eq",
            value=5,
        )
        assert cond.evaluate(context, {}) is True

    def test_threshold_condition_neq_operator(self):
        """Test neq operator."""
        context = OrchestrationContext(cycle_id="test", current_node="start", active_parents=3)
        cond = ThresholdCondition(
            name="test_neq",
            metric="active_parents",
            operator="neq",
            value=5,
        )
        assert cond.evaluate(context, {}) is True

    def test_threshold_condition_unsupported_operator(self):
        """Threshold condition raises error for unsupported operator."""
        context = OrchestrationContext(cycle_id="test", current_node="start", pass_rate=0.5)
        cond = ThresholdCondition(
            name="test_invalid",
            metric="pass_rate",
            operator="invalid_op",
            value=0.3,
        )
        with pytest.raises(ValueError, match="Unsupported operator"):
            cond.evaluate(context, {})

    def test_threshold_condition_unknown_metric(self):
        """Threshold condition raises error for unknown metric."""
        context = OrchestrationContext(cycle_id="test", current_node="start")
        cond = ThresholdCondition(
            name="test_invalid",
            metric="nonexistent_metric",
            operator="gte",
            value=0.3,
        )
        with pytest.raises(ValueError, match="Unknown metric"):
            cond.evaluate(context, {})

    def test_flag_condition_true(self):
        """Flag condition returns True when flag is set."""
        context = OrchestrationContext(cycle_id="test", current_node="start", llm_available=True)
        cond = FlagCondition(
            name="test_flag",
            metric="llm_available",
        )
        assert cond.evaluate(context, {}) is True

    def test_flag_condition_false(self):
        """Flag condition returns False when flag is not set."""
        context = OrchestrationContext(cycle_id="test", current_node="start", llm_available=False)
        cond = FlagCondition(
            name="test_flag",
            metric="llm_available",
        )
        assert cond.evaluate(context, {}) is False

    def test_all_of_condition_true(self):
        """AllOf condition returns True when all sub-conditions are true."""
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            pass_rate=0.5,
            consecutive_failures=1,
        )

        cond1 = ThresholdCondition(name="cond1", metric="pass_rate", operator="gte", value=0.3)
        cond2 = ThresholdCondition(name="cond2", metric="consecutive_failures", operator="lte", value=2)

        condition_map = {"cond1": cond1, "cond2": cond2}

        all_of = AllOfCondition(name="test_all_of", conditions=["cond1", "cond2"])
        assert all_of.evaluate(context, condition_map) is True

    def test_all_of_condition_false(self):
        """AllOf condition returns False when any sub-condition is false."""
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            pass_rate=0.1,  # This will fail the first condition
            consecutive_failures=1,
        )

        cond1 = ThresholdCondition(name="cond1", metric="pass_rate", operator="gte", value=0.3)
        cond2 = ThresholdCondition(name="cond2", metric="consecutive_failures", operator="lte", value=2)

        condition_map = {"cond1": cond1, "cond2": cond2}

        all_of = AllOfCondition(name="test_all_of", conditions=["cond1", "cond2"])
        assert all_of.evaluate(context, condition_map) is False

    def test_any_of_condition_true(self):
        """AnyOf condition returns True when any sub-condition is true."""
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            pass_rate=0.5,
            consecutive_failures=5,
        )

        cond1 = ThresholdCondition(name="cond1", metric="pass_rate", operator="gte", value=0.3)
        cond2 = ThresholdCondition(name="cond2", metric="consecutive_failures", operator="lte", value=2)

        condition_map = {"cond1": cond1, "cond2": cond2}

        any_of = AnyOfCondition(name="test_any_of", conditions=["cond1", "cond2"])
        assert any_of.evaluate(context, condition_map) is True

    def test_any_of_condition_false(self):
        """AnyOf condition returns False when all sub-conditions are false."""
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            pass_rate=0.1,  # This will fail
            consecutive_failures=5,  # This will fail
        )

        cond1 = ThresholdCondition(name="cond1", metric="pass_rate", operator="gte", value=0.3)
        cond2 = ThresholdCondition(name="cond2", metric="consecutive_failures", operator="lte", value=2)

        condition_map = {"cond1": cond1, "cond2": cond2}

        any_of = AnyOfCondition(name="test_any_of", conditions=["cond1", "cond2"])
        assert any_of.evaluate(context, condition_map) is False

    def test_all_of_unknown_condition(self):
        """AllOf raises error for unknown condition reference."""
        context = OrchestrationContext(cycle_id="test", current_node="start")
        all_of = AllOfCondition(name="test_all_of", conditions=["nonexistent"])
        with pytest.raises(ValueError, match="Unknown condition"):
            all_of.evaluate(context, {})

    def test_any_of_unknown_condition(self):
        """AnyOf raises error for unknown condition reference."""
        context = OrchestrationContext(cycle_id="test", current_node="start")
        any_of = AnyOfCondition(name="test_any_of", conditions=["nonexistent"])
        with pytest.raises(ValueError, match="Unknown condition"):
            any_of.evaluate(context, {})


# ============================================================================
# Config Validation Tests
# ============================================================================


class TestConfigValidation:
    """Tests for orchestration config validation."""

    def _make_valid_config(self):
        """Create a valid base configuration."""
        return {
            "start_node": "start",
            "max_steps_per_cycle": 6,
            "nodes": [
                {
                    "id": "start",
                    "kind": "action",
                    "action": "original",
                    "next": [{"if": "high_pass_rate", "goto": "crossover"}],
                    "allowed_next": ["crossover", "mutation"],
                    "fallback_next": "mutation",
                },
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [],
                    "allowed_next": ["stop"],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [],
                    "allowed_next": ["stop"],
                },
            ],
            "conditions": [
                {
                    "name": "high_pass_rate",
                    "type": "threshold",
                    "metric": "pass_rate",
                    "operator": "gte",
                    "value": 0.3,
                }
            ],
        }

    def test_valid_config_passes(self):
        """Valid config passes validation."""
        config = self._make_valid_config()
        # Should not raise
        validate_orchestration_config(
            start_node=config["start_node"],
            nodes=config["nodes"],
            conditions=config["conditions"],
            max_steps_per_cycle=config["max_steps_per_cycle"],
        )

    def test_missing_start_node(self):
        """Validation fails when start_node doesn't exist."""
        config = self._make_valid_config()
        config["start_node"] = "nonexistent"

        with pytest.raises(OrchestrationConfigError, match="start_node"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_duplicate_node_id(self):
        """Validation fails when node ids are duplicated."""
        config = self._make_valid_config()
        config["nodes"].append({
            "id": "start",  # Duplicate
            "kind": "action",
            "action": "mutation",
            "next": [],
        })

        with pytest.raises(OrchestrationConfigError, match="Duplicate node id"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_illegal_kind(self):
        """Validation fails when kind is invalid."""
        config = self._make_valid_config()
        config["nodes"][0]["kind"] = "invalid_kind"

        with pytest.raises(OrchestrationConfigError, match="invalid kind"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_illegal_action(self):
        """Validation fails when action is invalid."""
        config = self._make_valid_config()
        config["nodes"][0]["action"] = "invalid_action"

        with pytest.raises(OrchestrationConfigError, match="invalid action"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_missing_action_for_action_node(self):
        """Validation fails when an action node is missing required action."""
        config = self._make_valid_config()
        del config["nodes"][0]["action"]

        with pytest.raises(OrchestrationConfigError, match="missing required action"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_missing_decision_mode_for_decision_node(self):
        """Validation fails when a decision node is missing required decision_mode."""
        config = self._make_valid_config()
        config["nodes"][0] = {
            "id": "start",
            "kind": "decision",
            "allowed_next": ["mutation", "crossover"],
            "fallback_next": "mutation",
            "next": [],
        }

        with pytest.raises(OrchestrationConfigError, match="missing required decision_mode"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_missing_goto_target(self):
        """Validation fails when goto target doesn't exist."""
        config = self._make_valid_config()
        config["nodes"][0]["next"][0]["goto"] = "nonexistent_node"

        with pytest.raises(OrchestrationConfigError, match="unknown node"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_missing_condition_reference(self):
        """Validation fails when condition reference doesn't exist."""
        config = self._make_valid_config()
        config["nodes"][0]["next"][0]["if"] = "nonexistent_condition"

        with pytest.raises(OrchestrationConfigError, match="unknown condition"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_multiple_unconditional_transitions(self):
        """Validation fails when node has multiple unconditional transitions."""
        config = self._make_valid_config()
        config["nodes"][0]["next"] = [
            {"goto": "mutation"},
            {"goto": "crossover"},
        ]

        with pytest.raises(OrchestrationConfigError, match="multiple unconditional transitions"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )


# ============================================================================
# SingleCycleOrchestrator Tests
# ============================================================================


class TestSingleCycleOrchestrator:
    """Tests for SingleCycleOrchestrator decision logic."""

    def _make_orchestrator(self):
        """Create a base orchestrator for testing."""
        return SingleCycleOrchestrator(
            start_node="start",
            nodes=[
                {
                    "id": "start",
                    "kind": "action",
                    "action": "original",
                    "params": {"param1": "value1"},
                    "next": [{"if": "high_pass_rate", "goto": "crossover"}],
                    "allowed_next": ["crossover", "mutation"],
                    "fallback_next": "mutation",
                },
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [{"goto": "stop"}],
                    "allowed_next": ["stop"],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "stop"}],
                    "allowed_next": ["stop"],
                },
                {
                    "id": "stop",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            conditions=[
                {
                    "name": "high_pass_rate",
                    "type": "threshold",
                    "metric": "pass_rate",
                    "operator": "gte",
                    "value": 0.3,
                }
            ],
            max_steps_per_cycle=6,
        )

    def test_next_action_returns_action_spec(self):
        """next_action() returns ActionSpec for current node."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")

        action = orch.next_action(context)

        assert isinstance(action, ActionSpec)
        assert action.node_id == "start"
        assert action.kind == "action"
        assert action.action == "original"
        assert action.params == {"param1": "value1"}
        assert action.allowed_next == ["crossover", "mutation"]
        assert action.fallback_next == "mutation"

    def test_terminal_node_stop(self):
        """should_stop() returns True for terminal node."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="stop")

        assert orch.should_stop(context) is True

    def test_max_steps_stop(self):
        """should_stop() returns True when max_steps_per_cycle reached."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            step_index=6,  # Equal to max_steps_per_cycle
        )

        assert orch.should_stop(context) is True

    def test_should_stop_false(self):
        """should_stop() returns False for non-terminal node with steps remaining."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            step_index=2,
        )

        assert orch.should_stop(context) is False

    def test_correct_transition_selection(self):
        """select_next_node() selects correct node based on condition."""
        orch = self._make_orchestrator()

        # Condition is true - should select crossover
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            pass_rate=0.5,
        )
        next_node = orch.select_next_node(context)
        assert next_node == "crossover"

        # Condition is false - should select fallback (mutation)
        context2 = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            pass_rate=0.1,
        )
        next_node2 = orch.select_next_node(context2)
        assert next_node2 == "mutation"

    def test_unconditional_transition(self):
        """select_next_node() takes unconditional transition immediately."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="mutation")

        next_node = orch.select_next_node(context)
        assert next_node == "stop"

    def test_next_action_for_terminal_node(self):
        """next_action() returns ActionSpec for terminal node."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="stop")

        action = orch.next_action(context)

        assert isinstance(action, ActionSpec)
        assert action.node_id == "stop"
        assert action.kind == "terminal"
        assert action.action is None


# ============================================================================
# apply_result() Tests
# ============================================================================


class TestApplyResult:
    """Tests for apply_result() context updates."""

    def test_validated_factors_zero_gives_pass_rate_zero(self):
        """pass_rate is 0.0 when validated_factors is 0."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")
        result = ActionResult(
            action="original",
            status="success",
            generated_factors=10,
            validated_factors=0,
            added_factors=0,
        )

        updated = orch.apply_result(context, result)

        assert updated.pass_rate == 0.0

    def test_pass_rate_calculation(self):
        """pass_rate is calculated correctly when validated_factors > 0."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")
        result = ActionResult(
            action="original",
            status="success",
            generated_factors=10,
            validated_factors=10,
            added_factors=3,
        )

        updated = orch.apply_result(context, result)

        assert updated.pass_rate == pytest.approx(0.3)

    def test_added_factors_gt_0_resets_consecutive_failures(self):
        """consecutive_failures is reset when added_factors > 0."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            consecutive_failures=5,
        )
        result = ActionResult(
            action="original",
            status="success",
            added_factors=2,
        )

        updated = orch.apply_result(context, result)

        assert updated.consecutive_failures == 0

    def test_added_factors_eq_0_increments_consecutive_failures(self):
        """consecutive_failures is incremented when added_factors == 0."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(
            cycle_id="test",
            current_node="start",
            consecutive_failures=3,
        )
        result = ActionResult(
            action="original",
            status="success",
            added_factors=0,
        )

        updated = orch.apply_result(context, result)

        assert updated.consecutive_failures == 4

    def test_last_action_updated(self):
        """last_action is updated from result."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")
        result = ActionResult(
            action="mutation",
            status="success",
        )

        updated = orch.apply_result(context, result)

        assert updated.last_action == "mutation"

    def test_last_action_status_updated(self):
        """last_action_status is updated from result."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")
        result = ActionResult(
            action="original",
            status="failed",
        )

        updated = orch.apply_result(context, result)

        assert updated.last_action_status == "failed"

    def test_last_error_updated(self):
        """last_error is updated from result."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")
        result = ActionResult(
            action="original",
            status="error",
            error="Something went wrong",
        )

        updated = orch.apply_result(context, result)

        assert updated.last_error == "Something went wrong"

    def test_metrics_updated(self):
        """active_parents, diversity_score, llm_available are updated."""
        orch = self._make_orchestrator()
        context = OrchestrationContext(cycle_id="test", current_node="start")
        result = ActionResult(
            action="original",
            status="success",
            active_parents=5,
            diversity_score=0.75,
            llm_available=False,
        )

        updated = orch.apply_result(context, result)

        assert updated.active_parents == 5
        assert updated.diversity_score == pytest.approx(0.75)
        assert updated.llm_available is False

    def _make_orchestrator(self):
        """Helper to create orchestrator for tests."""
        return SingleCycleOrchestrator(
            start_node="start",
            nodes=[
                {
                    "id": "start",
                    "kind": "action",
                    "action": "original",
                    "next": [{"if": "high_pass_rate", "goto": "crossover"}],
                    "allowed_next": ["crossover", "mutation"],
                    "fallback_next": "mutation",
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [],
                },
            ],
            conditions=[
                {
                    "name": "high_pass_rate",
                    "type": "threshold",
                    "metric": "pass_rate",
                    "operator": "gte",
                    "value": 0.3,
                }
            ],
            max_steps_per_cycle=6,
        )


# ============================================================================
# Phase 6: LLM Advisor Config Validation Tests
# ============================================================================


class TestLLMAdvisorConfigValidation:
    """Phase 6: Tests for llm_advisor decision node config validation."""

    def _make_decision_config(self, **node_overrides):
        """Create a valid base config with a decision node."""
        base_node = {
            "id": "decider",
            "kind": "decision",
            "decision_mode": "llm_advisor",
            "allowed_next": ["mutation", "crossover"],
            "fallback_next": "mutation",
            "next": [],
        }
        base_node.update(node_overrides)
        return {
            "start_node": "decider",
            "max_steps_per_cycle": 6,
            "nodes": [
                base_node,
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [],
                },
            ],
            "conditions": [],
        }

    def test_valid_llm_advisor_decision_passes(self):
        """Valid llm_advisor decision node passes validation."""
        config = self._make_decision_config()
        validate_orchestration_config(
            start_node=config["start_node"],
            nodes=config["nodes"],
            conditions=config["conditions"],
            max_steps_per_cycle=config["max_steps_per_cycle"],
        )

    def test_llm_advisor_decision_missing_allowed_next_fails(self):
        """Validation fails when decision node has no allowed_next."""
        config = self._make_decision_config(allowed_next=None)
        with pytest.raises(OrchestrationConfigError, match="requires non-empty allowed_next"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_llm_advisor_decision_empty_allowed_next_fails(self):
        """Validation fails when decision node has empty allowed_next list."""
        config = self._make_decision_config(allowed_next=[])
        with pytest.raises(OrchestrationConfigError, match="requires non-empty allowed_next"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_llm_advisor_decision_missing_fallback_next_fails(self):
        """Validation fails when decision node has no fallback_next."""
        config = self._make_decision_config(fallback_next=None)
        with pytest.raises(OrchestrationConfigError, match="requires non-empty fallback_next"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_llm_advisor_decision_empty_fallback_next_fails(self):
        """Validation fails when decision node has empty string fallback_next."""
        config = self._make_decision_config(fallback_next="")
        with pytest.raises(OrchestrationConfigError, match="requires non-empty fallback_next"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_llm_advisor_decision_allowed_next_unknown_node_fails(self):
        """Validation fails when allowed_next references a node that does not exist."""
        config = self._make_decision_config(allowed_next=["mutation", "nonexistent"])
        with pytest.raises(OrchestrationConfigError, match="allowed_next target.*does not exist"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )

    def test_llm_advisor_decision_fallback_next_unknown_node_fails(self):
        """Validation fails when fallback_next references a node that does not exist."""
        config = self._make_decision_config(fallback_next="nonexistent")
        with pytest.raises(OrchestrationConfigError, match="fallback_next.*does not exist"):
            validate_orchestration_config(
                start_node=config["start_node"],
                nodes=config["nodes"],
                conditions=config["conditions"],
                max_steps_per_cycle=config["max_steps_per_cycle"],
            )
