from dataclasses import dataclass, field


@dataclass
class RetryCfg:
    max_attempts: int = 5
    wait_seconds: int = 5
    model_switch_threshold: int = 3


@dataclass
class LLMCfg:
    openai_base_url: str = "http://litellm.local/v1"
    chat_model: str = "minimax-m2.7"
    reasoning_model: str = "minimax-m2.7"
    embedding_model: str = "codestral-embed"
    embedding_base_url: str = "http://litellm.local/v1"
    chat_max_tokens: int = 64000
    chat_temperature: float = 0.4
    factor_mining_timeout: int = 999999
    retry: RetryCfg = field(default_factory=RetryCfg)


def test_apply_pipeline_llm_config_updates_llm_settings(monkeypatch):
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    old_values = {
        "openai_base_url": LLM_SETTINGS.openai_base_url,
        "chat_model": LLM_SETTINGS.chat_model,
        "reasoning_model": LLM_SETTINGS.reasoning_model,
        "embedding_model": LLM_SETTINGS.embedding_model,
        "embedding_base_url": LLM_SETTINGS.embedding_base_url,
        "chat_max_tokens": LLM_SETTINGS.chat_max_tokens,
        "chat_temperature": LLM_SETTINGS.chat_temperature,
        "factor_mining_timeout": LLM_SETTINGS.factor_mining_timeout,
        "max_retry": LLM_SETTINGS.max_retry,
        "retry_wait_seconds": LLM_SETTINGS.retry_wait_seconds,
        "model_switch_threshold": LLM_SETTINGS.model_switch_threshold,
    }

    for key, value in old_values.items():
        monkeypatch.setattr(LLM_SETTINGS, key, value)

    apply_pipeline_llm_config(LLMCfg())

    assert LLM_SETTINGS.openai_base_url == "http://litellm.local/v1"
    assert LLM_SETTINGS.chat_model == "minimax-m2.7"
    assert LLM_SETTINGS.reasoning_model == "minimax-m2.7"
    assert LLM_SETTINGS.embedding_model == "codestral-embed"
    assert LLM_SETTINGS.embedding_base_url == "http://litellm.local/v1"
    assert LLM_SETTINGS.chat_max_tokens == 64000
    assert LLM_SETTINGS.chat_temperature == 0.4
    assert LLM_SETTINGS.factor_mining_timeout == 999999
    assert LLM_SETTINGS.max_retry == 5
    assert LLM_SETTINGS.retry_wait_seconds == 5
    assert LLM_SETTINGS.model_switch_threshold == 3


def test_apply_pipeline_llm_config_none_returns_early(monkeypatch):
    """Passing None should return immediately without modifying any settings."""
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    sentinel = "original-value"
    monkeypatch.setattr(LLM_SETTINGS, "chat_model", sentinel)

    apply_pipeline_llm_config(None)

    assert LLM_SETTINGS.chat_model == sentinel


def test_apply_pipeline_llm_config_partial_config(monkeypatch):
    """Fields not present in the config should NOT be overwritten."""
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    sentinel_url = "http://should-not-change.local/v1"
    sentinel_model = "should-not-change"
    monkeypatch.setattr(LLM_SETTINGS, "openai_base_url", sentinel_url)
    monkeypatch.setattr(LLM_SETTINGS, "chat_model", sentinel_model)

    @dataclass
    class PartialCfg:
        chat_model: str = "new-model"
        # openai_base_url is intentionally missing

    apply_pipeline_llm_config(PartialCfg())

    assert LLM_SETTINGS.chat_model == "new-model"
    assert LLM_SETTINGS.openai_base_url == sentinel_url


def test_apply_pipeline_llm_config_empty_string_skipped(monkeypatch):
    """Empty string values should be skipped, preserving the original setting."""
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    original = "original-model"
    monkeypatch.setattr(LLM_SETTINGS, "chat_model", original)

    @dataclass
    class EmptyStrCfg:
        chat_model: str = ""

    apply_pipeline_llm_config(EmptyStrCfg())

    assert LLM_SETTINGS.chat_model == original


def test_apply_pipeline_llm_config_warns_on_env_vars_present(monkeypatch, caplog):
    """When non-secret LLM env vars are present, a warning should be emitted."""
    import logging
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    # Set up conflicting env vars
    monkeypatch.setenv("CHAT_MODEL", "env-model")
    monkeypatch.setenv("MAX_RETRY", "10")

    caplog.set_level(logging.WARNING, logger="quantaalpha.llm.pipeline_config")

    apply_pipeline_llm_config(LLMCfg())

    # Verify warning was emitted
    assert len(caplog.records) == 1
    assert "Non-secret LLM environment variables are set but will be ignored" in caplog.text
    assert "CHAT_MODEL" in caplog.text
    assert "MAX_RETRY" in caplog.text


def test_apply_pipeline_llm_config_no_warning_when_no_env_vars(monkeypatch, caplog):
    """When no non-secret LLM env vars are present, no warning should be emitted."""
    import logging
    from quantaalpha.llm.config import LLM_SETTINGS
    from quantaalpha.llm.pipeline_config import apply_pipeline_llm_config

    # Ensure env vars are not set
    monkeypatch.delenv("CHAT_MODEL", raising=False)
    monkeypatch.delenv("MAX_RETRY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("REASONING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("RETRY_WAIT_SECONDS", raising=False)
    monkeypatch.delenv("FACTOR_MINING_TIMEOUT", raising=False)
    monkeypatch.delenv("CHAT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("CHAT_TEMPERATURE", raising=False)

    caplog.set_level(logging.WARNING, logger="quantaalpha.llm.pipeline_config")

    apply_pipeline_llm_config(LLMCfg())

    # Verify no warning was emitted
    assert len(caplog.records) == 0
