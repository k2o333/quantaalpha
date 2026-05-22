from __future__ import annotations

from quantaalpha.factors.proposal_generation import qa_prompt_dict


def test_construct_prompt_forbids_sparse_optional_fields() -> None:
    prompt = qa_prompt_dict["hypothesis2experiment"]["user_prompt"]

    assert "$daily_basic_turnover_rate" in prompt
    assert "MUST use only the variables listed above" in prompt
    assert "$moneyflow_*" in prompt
    assert "$*_asof" in prompt
    assert "$report_rc_*" in prompt


def test_construct_prompt_forbids_overcomplex_retry_patterns() -> None:
    system_prompt = qa_prompt_dict["hypothesis2experiment"]["system_prompt"]
    retry_prompt = qa_prompt_dict["expression_duplication"]

    assert "Forbidden Complexity Patterns" in system_prompt
    assert "weighted multi-window blends" in system_prompt
    assert "Do not repeat the same long denominator" in system_prompt
    assert "under 150 characters" in retry_prompt
    assert "RANK(...) + ZSCORE(...)" in retry_prompt


def test_construct_prompt_disambiguates_cross_sectional_and_rolling_arity() -> None:
    system_prompt = qa_prompt_dict["hypothesis2experiment"]["system_prompt"]

    assert "Use TS_MEAN(A, n), TS_STD(A, n), and TS_MEDIAN(A, n) for rolling windows" in system_prompt
    assert "Do NOT write MEAN(A, n), STD(A, n), or MEDIAN(A, n)" in system_prompt
    assert "TS_DELTA($close, 5)" in system_prompt
    assert "TS_STD($volume * $daily_basic_turnover_rate, 20)" in system_prompt
