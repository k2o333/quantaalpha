from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def _ensure_repo_root_importable():
    repo_root = Path(__file__).resolve().parents[4]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root_importable()


def test_factor_error_event_contract_preserves_identity_and_timestamp():
    from quantaalpha.continuous.expression_quality import build_factor_error

    error = build_factor_error(
        factor_id="factor_a",
        expression="cs_mean($close, $volume)",
        error_type="arity",
        error_message="cs_mean expects 1 arguments, got 2",
        source="revalidation",
        created_at="2026-05-18T21:17:50",
    )

    assert error == {
        "factor_id": "factor_a",
        "expression": "cs_mean($close, $volume)",
        "error_type": "arity",
        "error_message": "cs_mean expects 1 arguments, got 2",
        "source": "revalidation",
        "created_at": "2026-05-18T21:17:50",
    }


def test_revalidation_error_is_visible_to_mining_feedback(tmp_path):
    from quantaalpha.continuous.error_feedback import FactorErrorFeedbackSink
    from quantaalpha.continuous.implementations import (
        DefaultMiningScheduler,
        DefaultRevalidationScheduler,
    )

    lib_path = tmp_path / "lib.json"
    lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8")
    sink = FactorErrorFeedbackSink()
    revalidation = DefaultRevalidationScheduler(
        library_path=str(lib_path),
        error_feedback_sink=sink,
    )
    mining = DefaultMiningScheduler(
        library_path=str(lib_path),
        error_feedback_sink=sink,
    )

    result = revalidation._run_factor_backtest(
        "bad_revalidation_factor",
        {
            "factor_id": "bad_revalidation_factor",
            "factor_expression": "cs_mean($close, $volume, $open)",
        },
    )

    assert result is False
    shared_errors = mining.get_shared_factor_errors()
    assert len(shared_errors) == 1
    assert shared_errors[0]["factor_id"] == "bad_revalidation_factor"
    assert shared_errors[0]["source"] == "revalidation"
    assert shared_errors[0]["error_message"] == "cs_mean expects 1 arguments, got 3"


def test_generation_retry_feedback_includes_bounded_shared_errors():
    from quantaalpha.continuous.error_feedback import FactorErrorFeedbackSink
    from quantaalpha.continuous.expression_quality import build_factor_error
    from quantaalpha.continuous.implementations import DefaultMiningScheduler

    sink = FactorErrorFeedbackSink(max_errors=5)
    sink.add(
        build_factor_error(
            factor_id="old_factor",
            expression="cs_mean($close, $volume, $open)",
            error_type="arity",
            error_message="cs_mean expects 1 arguments, got 3",
            source="revalidation",
            created_at="2026-05-18T21:17:50",
        )
    )
    scheduler = DefaultMiningScheduler(error_feedback_sink=sink)
    current_errors = [
        build_factor_error(
            expression="invalid @@@ broken",
            error_type="parse",
            error_message="Expression is not parsable",
            source="llm_generation",
            created_at="2026-05-18T21:19:54",
        )
    ]

    feedback = scheduler._build_generation_retry_feedback(
        "raw response",
        1,
        current_errors,
    )

    assert "--- Current Attempt Errors ---" in feedback
    assert "Expression is not parsable" in feedback
    assert "--- Shared Error Context ---" in feedback
    assert "old_factor" in feedback
    assert "cs_mean expects 1 arguments, got 3" in feedback


def test_generation_retry_feedback_bounds_shared_errors():
    from quantaalpha.continuous.error_feedback import FactorErrorFeedbackSink
    from quantaalpha.continuous.expression_quality import build_factor_error
    from quantaalpha.continuous.implementations import DefaultMiningScheduler

    sink = FactorErrorFeedbackSink(max_errors=10)
    for idx in range(5):
        sink.add(
            build_factor_error(
                factor_id=f"factor_{idx}",
                expression="x" * 200,
                error_type="arity",
                error_message="m" * 200,
                source="revalidation",
                created_at=f"2026-05-18T21:17:5{idx}",
            )
        )
    scheduler = DefaultMiningScheduler(error_feedback_sink=sink)

    feedback = scheduler._build_generation_retry_feedback(
        "raw response",
        1,
        [],
        shared_error_limit=2,
        max_error_text_length=40,
    )

    assert "factor_4" in feedback
    assert "factor_3" in feedback
    assert "factor_2" not in feedback
    assert "x" * 80 not in feedback
    assert "m" * 80 not in feedback


def test_llm_correct_merges_action_and_shared_errors_without_duplicates():
    from quantaalpha.continuous.error_feedback import FactorErrorFeedbackSink
    from quantaalpha.continuous.expression_quality import build_factor_error
    from quantaalpha.continuous.implementations import DefaultMiningScheduler

    duplicate_error = build_factor_error(
        factor_id="factor_dup",
        expression="cs_mean($close, $volume)",
        error_type="arity",
        error_message="cs_mean expects 1 arguments, got 2",
        source="mining_validation",
        created_at="2026-05-18T21:19:54",
    )
    shared_only_error = build_factor_error(
        factor_id="factor_shared",
        expression="cs_mean($close, $volume, $open)",
        error_type="arity",
        error_message="cs_mean expects 1 arguments, got 3",
        source="revalidation",
        created_at="2026-05-18T21:17:50",
    )
    sink = FactorErrorFeedbackSink()
    sink.add(duplicate_error)
    sink.add(shared_only_error)

    scheduler = DefaultMiningScheduler(error_feedback_sink=sink)
    provider = MagicMock()
    provider.correct.return_value = []
    scheduler._llm_correct_provider = provider

    result = scheduler._execute_llm_correct_action(
        {
            "factor_errors": [duplicate_error],
            "cycle_id": "cycle_1",
            "step_index": 1,
            "source_action": "mutation",
        },
        "llm_correct",
    )

    sent_errors = provider.correct.call_args.args[0]
    assert result.status == "malformed"
    assert [error["factor_id"] for error in sent_errors] == [
        "factor_dup",
        "factor_shared",
    ]


def test_orchestrator_injects_same_error_sink_into_lazy_schedulers(tmp_path):
    from quantaalpha.continuous.orchestrator import MiningOrchestrator
    from quantaalpha.continuous.scheduler import SchedulerConfig

    config = SchedulerConfig(
        enable_data_monitor=False,
        enable_revalidation=True,
        enable_mining=True,
    )
    orchestrator = MiningOrchestrator(
        config=config,
        library_path=str(tmp_path / "library.json"),
    )

    revalidation = orchestrator.revalidation_scheduler
    mining = orchestrator.mining_scheduler

    assert revalidation._error_feedback_sink is mining._error_feedback_sink


def test_generation_llm_retry_prompt_receives_shared_errors(tmp_path):
    from quantaalpha.continuous.error_feedback import FactorErrorFeedbackSink
    from quantaalpha.continuous.expression_quality import build_factor_error
    from quantaalpha.continuous.implementations import DefaultMiningScheduler

    lib_path = tmp_path / "lib.json"
    lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8")
    sink = FactorErrorFeedbackSink()
    sink.add(
        build_factor_error(
            factor_id="old_bad_factor",
            expression="cs_mean($close, $volume, $open)",
            error_type="arity",
            error_message="cs_mean expects 1 arguments, got 3",
            source="revalidation",
            created_at="2026-05-18T21:17:50",
        )
    )
    scheduler = DefaultMiningScheduler(library_path=str(lib_path), error_feedback_sink=sink)
    scheduler._is_parsable = lambda expr: "invalid @@@" not in expr

    invalid_response = json.dumps(
        [
            {
                "factor_name": "BrokenParse",
                "factor_expression": "invalid @@@ broken",
                "tags": {"data_dependency": ["price_volume"]},
            }
        ]
    )
    valid_response = json.dumps(
        [
            {
                "factor_name": "Fixed",
                "factor_expression": "$close / ts_mean($close, 5)",
                "tags": {"data_dependency": ["price_volume"]},
            }
        ]
    )

    with patch("quantaalpha.llm.client.APIBackend") as mock_backend_class:
        mock_backend = MagicMock()
        mock_backend.build_messages_and_create_chat_completion.side_effect = [
            invalid_response,
            valid_response,
        ]
        mock_backend_class.return_value = mock_backend

        generated = scheduler._generate_via_llm("context")

    assert len(generated) == 1
    second_prompt = mock_backend.build_messages_and_create_chat_completion.call_args_list[1].kwargs["user_prompt"]
    assert "old_bad_factor" in second_prompt
    assert "cs_mean expects 1 arguments, got 3" in second_prompt
