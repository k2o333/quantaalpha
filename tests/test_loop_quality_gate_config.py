from __future__ import annotations

from types import SimpleNamespace

from quantaalpha.pipeline import loop as loop_module


def test_loop_passes_full_quality_gate_config_to_factor_constructor(monkeypatch) -> None:
    captured_kwargs = {}

    class DummyScenario:
        background = "bg"

        def __init__(self, *args, **kwargs):
            pass

    class DummyHypothesisGen:
        def __init__(self, *args, **kwargs):
            pass

    class DummyFactorConstructor:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

    class DummyDeveloper:
        def __init__(self, *args, **kwargs):
            pass

    class DummySummarizer:
        def __init__(self, *args, **kwargs):
            pass

    mapping = {
        "ScenarioCls": DummyScenario,
        "HypGenCls": DummyHypothesisGen,
        "FactorCtorCls": DummyFactorConstructor,
        "CoderCls": DummyDeveloper,
        "RunnerCls": DummyDeveloper,
        "SummarizerCls": DummySummarizer,
    }

    monkeypatch.setattr(loop_module, "import_class", lambda path: mapping[path])
    monkeypatch.setattr(loop_module, "logger", SimpleNamespace(info=lambda *a, **k: None, log_object=lambda *a, **k: None, tag=lambda *_a, **_k: __import__("contextlib").nullcontext()))

    prop_setting = SimpleNamespace(
        scen="ScenarioCls",
        hypothesis_gen="HypGenCls",
        hypothesis2experiment="FactorCtorCls",
        coder="CoderCls",
        runner="RunnerCls",
        summarizer="SummarizerCls",
    )

    loop_module.AlphaAgentLoop(
        prop_setting,
        potential_direction=None,
        stop_event=None,
        quality_gate_config={
            "consistency_enabled": True,
            "complexity_enabled": False,
            "redundancy_enabled": False,
            "consistency_strict_mode": True,
            "max_correction_attempts": 9,
        },
    )

    assert captured_kwargs == {
        "consistency_enabled": True,
        "complexity_enabled": False,
        "redundancy_enabled": False,
        "consistency_strict_mode": True,
        "max_correction_attempts": 9,
    }
