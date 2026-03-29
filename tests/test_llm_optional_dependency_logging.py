from __future__ import annotations

import builtins
import importlib

from quantaalpha import log as qa_log
from quantaalpha.llm import client as llm_client


def test_missing_llama_logs_debug_not_warning(monkeypatch) -> None:
    original_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "llama":
            raise ImportError("llama unavailable for test")
        return original_import(name, globals, locals, fromlist, level)

    info_messages: list[str] = []
    warning_messages: list[str] = []

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    monkeypatch.setattr(qa_log.logger, "info", lambda message, *args, **kwargs: info_messages.append(str(message)))
    monkeypatch.setattr(qa_log.logger, "warning", lambda message, *args, **kwargs: warning_messages.append(str(message)))

    importlib.reload(llm_client)

    assert any("llama is not installed." in message for message in info_messages)
    assert not any("llama is not installed." in message for message in warning_messages)
