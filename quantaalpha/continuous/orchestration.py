"""
Phase 2: Single-cycle orchestration decision layer.

Pure decision logic with no runtime action execution.
Defines core data structures, condition evaluation, config validation,
and SingleCycleOrchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ============================================================================
# Core Data Structures
# ============================================================================


@dataclass
class OrchestrationContext:
    """Context for a single orchestration cycle."""

    cycle_id: str
    current_node: str
    step_index: int = 0

    generated_factors: int = 0
    validated_factors: int = 0
    added_factors: int = 0
    pass_rate: float = 0.0

    active_parents: int = 0
    diversity_score: float = 0.0
    consecutive_failures: int = 0

    llm_available: bool = True
    degraded_mode: bool = False

    last_action: str | None = None
    last_action_status: str | None = None
    last_error: str | None = None


@dataclass
class ActionSpec:
    """Specification of the next action to execute."""

    node_id: str
    kind: str
    action: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    allowed_next: list[str] = field(default_factory=list)
    fallback_next: str | None = None


@dataclass
class ActionResult:
    """Result from executing an action."""

    action: str
    status: str
    generated_factors: int = 0
    validated_factors: int = 0
    added_factors: int = 0
    active_parents: int = 0
    diversity_score: float = 0.0
    llm_available: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Condition System
# ============================================================================


SUPPORTED_OPERATORS = {"gt", "gte", "lt", "lte", "eq", "neq"}


def _compare(value: float, operator: str, threshold: float) -> bool:
    """Compare a value against a threshold using the specified operator."""
    if operator == "gt":
        return value > threshold
    elif operator == "gte":
        return value >= threshold
    elif operator == "lt":
        return value < threshold
    elif operator == "lte":
        return value <= threshold
    elif operator == "eq":
        return value == threshold
    elif operator == "neq":
        return value != threshold
    else:
        raise ValueError(f"Unsupported operator: {operator}")


@dataclass
class ThresholdCondition:
    """A condition that checks a metric against a threshold."""

    name: str
    type: str = "threshold"
    metric: str = ""
    operator: str = "gte"
    value: float = 0.0

    def evaluate(self, context: OrchestrationContext, condition_map: dict[str, Any] | None = None) -> bool:
        """Evaluate this condition against the context."""
        if self.operator not in SUPPORTED_OPERATORS:
            raise ValueError(f"Unsupported operator: {self.operator}")

        metric_value = getattr(context, self.metric, None)
        if metric_value is None:
            raise ValueError(f"Unknown metric: {self.metric}")

        return _compare(float(metric_value), self.operator, self.value)


@dataclass
class FlagCondition:
    """A condition that checks a boolean flag."""

    name: str
    type: str = "flag"
    metric: str = ""

    def evaluate(self, context: OrchestrationContext, condition_map: dict[str, Any] | None = None) -> bool:
        """Evaluate this condition against the context."""
        metric_value = getattr(context, self.metric, None)
        if metric_value is None:
            raise ValueError(f"Unknown metric: {self.metric}")

        return bool(metric_value)


@dataclass
class AllOfCondition:
    """A condition that is true only if all referenced conditions are true."""

    name: str
    type: str = "all_of"
    conditions: list[str] = field(default_factory=list)

    def evaluate(self, context: OrchestrationContext, condition_map: dict[str, Any]) -> bool:
        """Evaluate all sub-conditions."""
        for cond_name in self.conditions:
            if cond_name not in condition_map:
                raise ValueError(f"Unknown condition: {cond_name}")
            cond = condition_map[cond_name]
            if not cond.evaluate(context, condition_map):
                return False
        return True


@dataclass
class AnyOfCondition:
    """A condition that is true if any referenced condition is true."""

    name: str
    type: str = "any_of"
    conditions: list[str] = field(default_factory=list)

    def evaluate(self, context: OrchestrationContext, condition_map: dict[str, Any]) -> bool:
        """Evaluate any sub-conditions."""
        for cond_name in self.conditions:
            if cond_name not in condition_map:
                raise ValueError(f"Unknown condition: {cond_name}")
            cond = condition_map[cond_name]
            if cond.evaluate(context, condition_map):
                return True
        return False


def evaluate_condition(
    condition: Any,
    context: OrchestrationContext,
    condition_map: dict[str, Any],
) -> bool:
    """Evaluate a condition against the context."""
    return condition.evaluate(context, condition_map)


# ============================================================================
# Config Validation
# ============================================================================


VALID_KINDS = {"action", "decision", "terminal"}
VALID_ACTIONS = {"original", "mutation", "crossover"}
VALID_DECISION_MODES = {"llm_advisor"}


class OrchestrationConfigError(Exception):
    """Raised when orchestration config is invalid."""

    pass


def validate_orchestration_config(
    start_node: str,
    nodes: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    max_steps_per_cycle: int,
) -> None:
    """
    Validate orchestration configuration.

    Checks:
    - start_node exists
    - node ids are unique
    - kind is valid
    - action is valid (for action nodes)
    - decision_mode is valid (for decision nodes)
    - all goto targets exist
    - all condition references exist
    - at most one unconditional transition per node
    """
    # Check start_node exists
    node_ids = {n["id"] for n in nodes}
    if start_node not in node_ids:
        raise OrchestrationConfigError(f"start_node '{start_node}' not found in nodes")

    # Check for duplicate node ids
    if len(node_ids) != len(nodes):
        seen = set()
        for n in nodes:
            if n["id"] in seen:
                raise OrchestrationConfigError(f"Duplicate node id: {n['id']}")
            seen.add(n["id"])

    # Build condition map for validation
    condition_names = {c["name"] for c in conditions}

    # Validate each node
    for node in nodes:
        node_id = node["id"]
        kind = node.get("kind", "action")

        # Check kind is valid
        if kind not in VALID_KINDS:
            raise OrchestrationConfigError(
                f"Node '{node_id}' has invalid kind: '{kind}'. Must be one of {VALID_KINDS}"
            )

        # Check action is valid for action nodes
        if kind == "action":
            action = node.get("action")
            if action is None:
                raise OrchestrationConfigError(
                    f"Node '{node_id}' is missing required action"
                )
            if action not in VALID_ACTIONS:
                raise OrchestrationConfigError(
                    f"Node '{node_id}' has invalid action: '{action}'. Must be one of {VALID_ACTIONS}"
                )

        # Check decision_mode is valid for decision nodes
        if kind == "decision":
            decision_mode = node.get("decision_mode")
            if decision_mode is None:
                raise OrchestrationConfigError(
                    f"Node '{node_id}' is missing required decision_mode"
                )
            if decision_mode not in VALID_DECISION_MODES:
                raise OrchestrationConfigError(
                    f"Node '{node_id}' has invalid decision_mode: '{decision_mode}'. Must be one of {VALID_DECISION_MODES}"
                )

        # Check transitions
        transitions = node.get("next", [])
        unconditional_count = 0
        for trans in transitions:
            condition_ref = trans.get("if")
            goto_target = trans.get("goto")

            # Check goto target exists
            if goto_target is not None and goto_target not in node_ids:
                raise OrchestrationConfigError(
                    f"Node '{node_id}' has transition to unknown node: '{goto_target}'"
                )

            # Check condition reference exists
            if condition_ref is not None and condition_ref not in condition_names:
                raise OrchestrationConfigError(
                    f"Node '{node_id}' references unknown condition: '{condition_ref}'"
                )

            # Count unconditional transitions
            if condition_ref is None:
                unconditional_count += 1

        # Check at most one unconditional transition
        if unconditional_count > 1:
            raise OrchestrationConfigError(
                f"Node '{node_id}' has multiple unconditional transitions"
            )


# ============================================================================
# SingleCycleOrchestrator
# ============================================================================


class SingleCycleOrchestrator:
    """
    Pure decision orchestrator for a single cycle.

    Does not execute actions, only decides what to do next.
    """

    def __init__(
        self,
        start_node: str,
        nodes: list[dict[str, Any]],
        conditions: list[dict[str, Any]],
        max_steps_per_cycle: int = 6,
    ):
        """
        Initialize the orchestrator.

        Args:
            start_node: ID of the starting node
            nodes: List of node configurations
            conditions: List of condition configurations
            max_steps_per_cycle: Maximum steps per cycle
        """
        self.start_node = start_node
        self.max_steps_per_cycle = max_steps_per_cycle
        self._nodes = {n["id"]: n for n in nodes}
        self._condition_map = self._build_condition_map(conditions)

    def _build_condition_map(self, conditions: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a map of condition name to condition object."""
        condition_map = {}
        for cond_cfg in conditions:
            cond_type = cond_cfg.get("type", "threshold")
            if cond_type == "threshold":
                cond = ThresholdCondition(
                    name=cond_cfg["name"],
                    type=cond_type,
                    metric=cond_cfg.get("metric", ""),
                    operator=cond_cfg.get("operator", "gte"),
                    value=cond_cfg.get("value", 0.0),
                )
            elif cond_type == "flag":
                cond = FlagCondition(
                    name=cond_cfg["name"],
                    type=cond_type,
                    metric=cond_cfg.get("metric", ""),
                )
            elif cond_type == "all_of":
                cond = AllOfCondition(
                    name=cond_cfg["name"],
                    type=cond_type,
                    conditions=cond_cfg.get("conditions", []),
                )
            elif cond_type == "any_of":
                cond = AnyOfCondition(
                    name=cond_cfg["name"],
                    type=cond_type,
                    conditions=cond_cfg.get("conditions", []),
                )
            else:
                raise ValueError(f"Unknown condition type: {cond_type}")
            condition_map[cond_cfg["name"]] = cond
        return condition_map

    def should_stop(self, context: OrchestrationContext) -> bool:
        """Check if the orchestration cycle should stop."""
        # Stop if current node is terminal
        node = self._nodes.get(context.current_node)
        if node and node.get("kind") == "terminal":
            return True

        # Stop if max steps reached
        if context.step_index >= self.max_steps_per_cycle:
            return True

        return False

    def next_action(self, context: OrchestrationContext) -> ActionSpec:
        """
        Determine the next action to execute.

        Returns ActionSpec for the current node.
        """
        node = self._nodes.get(context.current_node)
        if node is None:
            raise ValueError(f"Unknown node: {context.current_node}")

        kind = node.get("kind", "action")
        action = node.get("action")
        params = node.get("params", {})
        allowed_next = node.get("allowed_next", [])
        fallback_next = node.get("fallback_next")

        return ActionSpec(
            node_id=node["id"],
            kind=kind,
            action=action,
            params=params,
            allowed_next=allowed_next,
            fallback_next=fallback_next,
        )

    def select_next_node(self, context: OrchestrationContext) -> str | None:
        """
        Select the next node based on transition conditions.

        Returns the ID of the next node, or None if no transition matches.
        """
        node = self._nodes.get(context.current_node)
        if node is None:
            return None

        transitions = node.get("next", [])
        fallback = node.get("fallback_next")

        for trans in transitions:
            condition_ref = trans.get("if")
            goto_target = trans.get("goto")

            if condition_ref is None:
                # Unconditional transition - take it immediately
                return goto_target

            # Evaluate condition
            if condition_ref in self._condition_map:
                cond = self._condition_map[condition_ref]
                if evaluate_condition(cond, context, self._condition_map):
                    return goto_target

        return fallback

    def apply_result(
        self, context: OrchestrationContext, result: ActionResult
    ) -> OrchestrationContext:
        """
        Update the context with the action result.

        Returns updated context.
        """
        context.last_action = result.action
        context.last_action_status = result.status
        context.last_error = result.error

        context.generated_factors = result.generated_factors
        context.validated_factors = result.validated_factors
        context.added_factors = result.added_factors

        # Calculate pass_rate
        if result.validated_factors == 0:
            context.pass_rate = 0.0
        else:
            context.pass_rate = result.added_factors / result.validated_factors

        # Update consecutive_failures
        if result.added_factors > 0:
            context.consecutive_failures = 0
        else:
            context.consecutive_failures += 1

        # Update metrics
        context.active_parents = result.active_parents
        context.diversity_score = result.diversity_score
        context.llm_available = result.llm_available

        return context
