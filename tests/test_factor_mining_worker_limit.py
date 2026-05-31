from types import SimpleNamespace


def test_parallel_evolution_tasks_respect_max_factor_workers(monkeypatch) -> None:
    from quantaalpha.pipeline import factor_mining

    active = 0
    max_active = 0

    class FakeQueue:
        def __init__(self) -> None:
            self.results = [
                {
                    "success": False,
                    "task_idx": idx,
                    "error": "fixture",
                }
                for idx in range(5)
            ]

        def get(self):
            return self.results.pop(0)

    class FakeProcess:
        def __init__(self, *, target, args) -> None:
            del target
            self.args = args
            self.started = False

        def start(self) -> None:
            nonlocal active, max_active
            self.started = True
            active += 1
            max_active = max(max_active, active)

        def join(self) -> None:
            nonlocal active
            if self.started:
                active -= 1
                self.started = False

    monkeypatch.setattr(factor_mining, "Queue", FakeQueue)
    monkeypatch.setattr(factor_mining, "Process", FakeProcess)
    tasks = [
        {
            "phase": SimpleNamespace(value="original"),
            "direction_id": idx,
        }
        for idx in range(5)
    ]

    factor_mining._run_tasks_parallel(
        tasks=tasks,
        directions=["fixture"],
        step_n=1,
        use_local=True,
        user_direction=None,
        log_root=".",
        max_workers=2,
    )

    assert max_active == 2
