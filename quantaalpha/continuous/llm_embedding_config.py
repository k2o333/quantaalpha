"""Embedding runtime configuration for continuous mining."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMEmbeddingConfig:
    """远程 embedding 的显式请求和降级语义。"""

    version: int = 1
    remote_enabled: bool = True
    use_cache: bool = True
    dump_cache: bool = True
    fatal_on_failure: bool = False
    max_attempts: int = 1
    model: str = ""
    base_url: str = ""
    fallback: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(
        cls,
        d: dict | None,
        *,
        legacy_model: str = "",
        legacy_base_url: str = "",
    ) -> "LLMEmbeddingConfig":
        if not d:
            return cls(model=legacy_model, base_url=legacy_base_url)
        fallback = d.get("fallback", [])
        if isinstance(fallback, str):
            fallback = [fallback]
        return cls(
            version=d.get("version", 1),
            remote_enabled=d.get("remote_enabled", True),
            use_cache=d.get("use_cache", True),
            dump_cache=d.get("dump_cache", True),
            fatal_on_failure=d.get("fatal_on_failure", False),
            max_attempts=d.get("max_attempts", 1),
            model=d.get("model", legacy_model),
            base_url=d.get("base_url", legacy_base_url),
            fallback=list(fallback or []),
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "remote_enabled": self.remote_enabled,
            "use_cache": self.use_cache,
            "dump_cache": self.dump_cache,
            "fatal_on_failure": self.fatal_on_failure,
            "max_attempts": self.max_attempts,
            "model": self.model,
            "base_url": self.base_url,
            "fallback": list(self.fallback),
        }
