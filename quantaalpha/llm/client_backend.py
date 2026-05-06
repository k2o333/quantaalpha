from __future__ import annotations

from .client_backend_completion import BackendCompletionMixin
from .client_backend_init import BackendInitMixin
from .client_backend_retry import BackendRetryMixin
from .client_backend_tokens import BackendTokenMixin


class APIBackend(
    BackendInitMixin,
    BackendRetryMixin,
    BackendCompletionMixin,
    BackendTokenMixin,
):
    """Unified interface for LLM chat, embedding, retry, and provider routing."""
