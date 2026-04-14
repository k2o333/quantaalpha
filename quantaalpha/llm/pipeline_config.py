from __future__ import annotations

from typing import Any

from quantaalpha.llm.config import LLM_SETTINGS


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def apply_pipeline_llm_config(llm_cfg: Any) -> None:
    if llm_cfg is None:
        return

    scalar_map = {
        "openai_base_url": "openai_base_url",
        "chat_model": "chat_model",
        "reasoning_model": "reasoning_model",
        "embedding_model": "embedding_model",
        "embedding_base_url": "embedding_base_url",
        "chat_max_tokens": "chat_max_tokens",
        "chat_temperature": "chat_temperature",
        "factor_mining_timeout": "factor_mining_timeout",
    }
    for cfg_name, settings_name in scalar_map.items():
        value = getattr(llm_cfg, cfg_name, None)
        if _has_value(value):
            setattr(LLM_SETTINGS, settings_name, value)

    retry = getattr(llm_cfg, "retry", None)
    if retry is not None:
        retry_map = {
            "max_attempts": "max_retry",
            "wait_seconds": "retry_wait_seconds",
            "model_switch_threshold": "model_switch_threshold",
        }
        for cfg_name, settings_name in retry_map.items():
            value = getattr(retry, cfg_name, None)
            if _has_value(value):
                setattr(LLM_SETTINGS, settings_name, max(1, value) if cfg_name != "wait_seconds" else value)
