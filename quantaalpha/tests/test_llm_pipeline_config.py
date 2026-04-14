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
    try:
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
    finally:
        for key, value in old_values.items():
            setattr(LLM_SETTINGS, key, value)
