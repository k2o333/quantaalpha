from __future__ import annotations

import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.pipeline.evolution.controller import EvolutionConfig, EvolutionController
from quantaalpha.pipeline.evolution.trajectory import RoundPhase, StrategyTrajectory


class TestEvolutionControllerRoundLimits(unittest.TestCase):
    def test_mutation_only_stops_at_max_rounds_after_empty_next_round(self):
        controller = EvolutionController(
            EvolutionConfig(
                num_directions=1,
                max_rounds=2,
                mutation_enabled=True,
                crossover_enabled=False,
            )
        )
        controller.pool.add(
            StrategyTrajectory(
                trajectory_id="original-0",
                direction_id=0,
                round_idx=0,
                phase=RoundPhase.ORIGINAL,
                backtest_metrics={"RankIC": 0.1},
            )
        )
        controller._current_round = 1
        controller._current_phase = RoundPhase.MUTATION

        first_task = controller.get_next_task()
        self.assertIsNotNone(first_task)
        self.assertEqual(first_task["phase"], RoundPhase.MUTATION)
        self.assertEqual(first_task["round_idx"], 1)

        next_task = controller.get_next_task()
        self.assertIsNone(next_task)
        self.assertEqual(controller.get_current_state()["round"], 2)

    def test_mutation_phase_without_targets_terminates(self):
        controller = EvolutionController(
            EvolutionConfig(
                num_directions=1,
                max_rounds=100,
                mutation_enabled=True,
                crossover_enabled=False,
            )
        )
        controller._current_round = 1
        controller._current_phase = RoundPhase.MUTATION

        self.assertIsNone(controller.get_next_task())
        self.assertEqual(controller.get_current_state()["round"], 1)

    def test_parallel_mutation_phase_without_targets_terminates(self):
        controller = EvolutionController(
            EvolutionConfig(
                num_directions=1,
                max_rounds=100,
                mutation_enabled=True,
                crossover_enabled=False,
            )
        )
        controller._current_round = 1
        controller._current_phase = RoundPhase.MUTATION

        self.assertEqual(controller.get_all_tasks_for_current_phase(), [])
        self.assertEqual(controller.get_current_state()["round"], 1)


if __name__ == "__main__":
    unittest.main()
