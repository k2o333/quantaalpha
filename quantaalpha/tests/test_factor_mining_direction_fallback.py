"""Tests for factor mining direction fallback: generic exploration when initial_direction is None."""
import pytest
from unittest.mock import patch, MagicMock


def _get_direction_helper():
    """Import the real helper from factor_mining.py."""
    try:
        from quantaalpha.pipeline.factor_mining import _resolve_initial_directions
        return _resolve_initial_directions
    except ImportError:
        pytest.fail("Cannot import _resolve_initial_directions from factor_mining.py")


class TestPlanningEnabledWithoutInitialDirectionUsesGenericDirectionMarker:
    """Planning enabled with initial_direction=None must yield [None, None] with source 'generic'."""

    def test_planning_enabled_without_initial_direction_uses_generic_direction_marker(self):
        """When planning_enabled=True, initial_direction=None, num_directions=2,
        must return directions [None, None] and source 'generic'.

        This test exercises the real helper in factor_mining.py, not a copied implementation."""
        resolve_fn = _get_direction_helper()

        directions, source = resolve_fn(
            planning_enabled=True,
            initial_direction=None,
            num_directions=2,
        )

        assert directions == [None, None], f"Expected [None, None], got {directions}"
        assert source == "generic", f"Expected source 'generic', got {source}"

    def test_planning_enabled_with_initial_direction_uses_llm(self):
        """When planning_enabled=True and initial_direction is provided,
        the source should not be 'generic'."""
        resolve_fn = _get_direction_helper()

        directions, source = resolve_fn(
            planning_enabled=True,
            initial_direction="momentum factors",
            num_directions=2,
        )

        assert len(directions) == 2
        assert source != "generic"

    def test_planning_disabled_with_initial_direction(self):
        """When planning_enabled=False with initial_direction, use single direction."""
        resolve_fn = _get_direction_helper()

        directions, source = resolve_fn(
            planning_enabled=False,
            initial_direction="mean reversion",
            num_directions=2,
        )

        assert directions == ["mean reversion"]
        assert source != "generic"

    def test_planning_disabled_without_initial_direction(self):
        """When planning_enabled=False without initial_direction, use [None]."""
        resolve_fn = _get_direction_helper()

        directions, source = resolve_fn(
            planning_enabled=False,
            initial_direction=None,
            num_directions=2,
        )

        assert directions == [None]

    def test_generic_direction_source_is_explicit(self):
        """The generic direction source must be explicit as 'generic' string."""
        resolve_fn = _get_direction_helper()

        _, source = resolve_fn(
            planning_enabled=True,
            initial_direction=None,
            num_directions=3,
        )

        assert source == "generic"

    def test_generic_directions_count_matches_num_directions(self):
        """Generic exploration must produce exactly num_directions None entries."""
        resolve_fn = _get_direction_helper()

        for n in [1, 2, 5]:
            directions, source = resolve_fn(
                planning_enabled=True,
                initial_direction=None,
                num_directions=n,
            )
            assert len(directions) == n, f"For num_directions={n}, got {len(directions)} directions"
            assert all(d is None for d in directions), f"For num_directions={n}, expected all None"
            assert source == "generic"

    def test_run_evolution_loop_logs_generic_source_for_none_direction(self, tmp_path, monkeypatch):
        """run_evolution_loop must use the real fallback path and log source=generic."""
        from quantaalpha.pipeline import factor_mining
        from quantaalpha.pipeline.factor_mining import run_evolution_loop

        messages = []

        class CapturingLogger:
            storage = type("Storage", (), {"path": str(tmp_path)})()

            def info(self, message):
                messages.append(str(message))

            def warning(self, message):
                messages.append(str(message))

            def error(self, message):
                messages.append(str(message))

        monkeypatch.setattr(factor_mining, "logger", CapturingLogger())

        result = run_evolution_loop(
            initial_direction=None,
            evolution_cfg={"max_rounds": 0},
            exec_cfg={"steps_per_loop": 1},
            planning_cfg={"enabled": True, "num_directions": 2},
            log_root=str(tmp_path),
        )

        assert result["status"] == "success"
        joined = "\n".join(messages)
        assert "Generated 2 exploration directions (source: generic)" in joined
        assert "Direction 0: None" in joined
        assert "Direction 1: None" in joined
