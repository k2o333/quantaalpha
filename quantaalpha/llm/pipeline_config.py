from __future__ import annotations

import logging
import os
from typing import Any

from quantaalpha.llm.config import LLM_SETTINGS

logger = logging.getLogger(__name__)

# Non-secret LLM environment variable names that should be migrated to pipeline.yaml
_NON_SECRET_ENV_NAMES = [
    "OPENAI_BASE_URL",
    "CHAT_MODEL",
    "REASONING_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_BASE_URL",
    "MAX_RETRY",
    "RETRY_WAIT_SECONDS",
    "FACTOR_MINING_TIMEOUT",
    "CHAT_MAX_TOKENS",
    "CHAT_TEMPERATURE",
    "OPENAI_REQUEST_TIMEOUT_SECONDS",
    "OPENAI_SDK_MAX_RETRIES",
    "MAX_ATTEMPTS_PER_PROVIDER",
]


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _warn_about_conflicting_env_vars(llm_cfg: Any) -> None:
    """Warn if non-secret LLM environment variables exist alongside pipeline.yaml config."""
    present_env_vars = []
    for env_name in _NON_SECRET_ENV_NAMES:
        if os.environ.get(env_name):
            present_env_vars.append(env_name)

    if present_env_vars:
        var_list = ", ".join(present_env_vars)
        logger.warning(
            "Non-secret LLM environment variables are set but will be ignored "
            "because pipeline.yaml contains an 'llm' section. "
            "These variables are deprecated in favor of pipeline.yaml config: %s",
            var_list,
        )


def apply_pipeline_llm_config(llm_cfg: Any) -> None:
    """Apply LLM configuration from a pipeline config object to the global LLM_SETTINGS.

    Copies scalar fields (API URLs, model names, hyperparameters) and retry
    settings from ``llm_cfg`` into ``LLM_SETTINGS``. Fields that are None or
    empty strings are skipped, leaving existing settings unchanged.

    If both pipeline.yaml and non-secret environment variables are present,
    a warning is emitted indicating that the pipeline.yaml values take precedence.

    Args:
        llm_cfg: A configuration object with LLM-related attributes, or None
            to perform a no-op.
    """
    if llm_cfg is None:
        return
    if getattr(llm_cfg, "configured", True) is False:
        return

    # Check for non-secret LLM env vars that may conflict with pipeline.yaml
    _warn_about_conflicting_env_vars(llm_cfg)

    scalar_map = {
        "openai_base_url": "openai_base_url",
        "chat_model": "chat_model",
        "reasoning_model": "reasoning_model",
        "embedding_model": "embedding_model",
        "embedding_base_url": "embedding_base_url",
        "chat_max_tokens": "chat_max_tokens",
        "chat_temperature": "chat_temperature",
        "openai_request_timeout_seconds": "openai_request_timeout_seconds",
        "openai_sdk_max_retries": "openai_sdk_max_retries",
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
            "max_attempts_per_provider": "max_attempts_per_provider",
        }
        for cfg_name, settings_name in retry_map.items():
            value = getattr(retry, cfg_name, None)
            if _has_value(value):
                setattr(LLM_SETTINGS, settings_name, max(1, value) if cfg_name != "wait_seconds" else value)
