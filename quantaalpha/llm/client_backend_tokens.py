from __future__ import annotations

from .client_shared import *
from .client_shared import (
    _ProviderAttempt,
    _coerce_int_setting,
    _escape_common_json_sequences,
    _is_tool_call_capability_failure,
)
from .client_sessions import ChatSession, SQliteLazyCache


class BackendTokenMixin:
    """Responsibility slice for APIBackend."""

    def calculate_token_from_messages(self, messages: list[dict]) -> int:
        if self.use_llama2 or self.use_gcr_endpoint:
            logger.warning("num_tokens_from_messages() is not implemented for model llama2.")
            return 0  # TODO implement this function for llama2

        if "gpt4" in self.chat_model or "gpt-4" in self.chat_model:
            tokens_per_message = 3
            tokens_per_name = 1
        else:
            tokens_per_message = 4  # every message follows <start>{role/name}\n{content}<end>\n
            tokens_per_name = -1  # if there's a name, the role is omitted
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                if self.encoder is not None:
                    num_tokens += len(self.encoder.encode(value))
                else:
                    num_tokens += max(1, len(value) // 4)
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <start>assistant<message>
        return num_tokens

    def build_messages_and_calculate_token(
        self,
        user_prompt: str,
        system_prompt: str | None,
        former_messages: list[dict] | None = None,
        *,
        shrink_multiple_break: bool = False,
    ) -> int:
        if former_messages is None:
            former_messages = []
        messages = self.build_messages(user_prompt, system_prompt, former_messages, shrink_multiple_break=shrink_multiple_break)
        return self.calculate_token_from_messages(messages)
