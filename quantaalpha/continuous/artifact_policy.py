"""持续挖掘产物策略。

本模块只定义运行时产物保留语义，不负责删除历史文件。删除由候选
生命周期或 workspace retention 处理。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactPolicyConfig:
    """持续挖掘产物策略配置。"""

    mode: str = "default"
    pickle_cache: str = "enabled"
    debug_artifacts: str = "enabled"
    parity_artifacts: str = "enabled"
    failed_workspace_retention: str = "full"
    passed_workspace_retention: str = "keep"
    publish_factor_values_on_pass: bool = False

    @classmethod
    def from_dict(cls, data: dict | None) -> "ArtifactPolicyConfig":
        """从 YAML dict 解析产物策略。"""

        if not data:
            return cls()
        mode = str(data.get("mode", "default")).strip().lower()
        default_pickle_cache = "disabled" if mode == "minimal" else "enabled"
        default_debug_artifacts = "disabled" if mode == "minimal" else "enabled"
        default_parity_artifacts = "disabled" if mode == "minimal" else "enabled"
        default_failed_retention = "summary_only" if mode == "minimal" else "full"
        default_passed_retention = "delete_after_publish" if mode == "minimal" else "keep"
        default_publish_values = mode == "minimal"

        return cls(
            mode=mode,
            pickle_cache=str(data.get("pickle_cache", default_pickle_cache)).strip().lower(),
            debug_artifacts=str(data.get("debug_artifacts", default_debug_artifacts)).strip().lower(),
            parity_artifacts=str(data.get("parity_artifacts", default_parity_artifacts)).strip().lower(),
            failed_workspace_retention=str(data.get("failed_workspace_retention", default_failed_retention)).strip().lower(),
            passed_workspace_retention=str(data.get("passed_workspace_retention", default_passed_retention)).strip().lower(),
            publish_factor_values_on_pass=bool(data.get("publish_factor_values_on_pass", default_publish_values)),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可记录的 dict。"""

        return {
            "mode": self.mode,
            "pickle_cache": self.pickle_cache,
            "debug_artifacts": self.debug_artifacts,
            "parity_artifacts": self.parity_artifacts,
            "failed_workspace_retention": self.failed_workspace_retention,
            "passed_workspace_retention": self.passed_workspace_retention,
            "publish_factor_values_on_pass": self.publish_factor_values_on_pass,
        }


_RUNTIME_ARTIFACT_POLICY = ArtifactPolicyConfig()


def apply_artifact_policy_to_runtime(
    config: ArtifactPolicyConfig,
    *,
    settings: Any | None = None,
) -> None:
    """将产物策略应用到进程内 RD-Agent 运行时设置。"""

    global _RUNTIME_ARTIFACT_POLICY
    _RUNTIME_ARTIFACT_POLICY = config

    if settings is None:
        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        settings = RD_AGENT_SETTINGS

    if config.pickle_cache == "disabled":
        settings.cache_with_pickle = False
    _set_optional_runtime_attr(settings, "artifact_debug_artifacts_enabled", config.debug_artifacts != "disabled")
    _set_optional_runtime_attr(settings, "artifact_parity_artifacts_enabled", config.parity_artifacts != "disabled")
    _set_optional_runtime_attr(settings, "artifact_failed_workspace_retention", config.failed_workspace_retention)
    _set_optional_runtime_attr(settings, "artifact_passed_workspace_retention", config.passed_workspace_retention)
    _set_optional_runtime_attr(settings, "artifact_publish_factor_values_on_pass", config.publish_factor_values_on_pass)


def _set_optional_runtime_attr(settings: Any, name: str, value: Any) -> None:
    """Best-effort test-double support without extending strict RD-Agent settings."""

    if settings.__class__.__name__ == "RDAgentSettings":
        return
    try:
        setattr(settings, name, value)
    except (AttributeError, ValueError, TypeError):
        return


def runtime_parity_artifacts_enabled(*, settings: Any | None = None) -> bool:
    """返回当前运行时是否允许写入 parity 诊断产物。"""

    if settings is None:
        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        settings = RD_AGENT_SETTINGS
        default = _RUNTIME_ARTIFACT_POLICY.parity_artifacts != "disabled"
    else:
        default = True
    return bool(getattr(settings, "artifact_parity_artifacts_enabled", default))


def runtime_publish_factor_values_on_pass(*, settings: Any | None = None) -> bool:
    """返回当前运行时是否在因子通过后发布 durable factor values。"""

    if settings is None:
        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        settings = RD_AGENT_SETTINGS
        default = _RUNTIME_ARTIFACT_POLICY.publish_factor_values_on_pass
    else:
        default = False
    return bool(getattr(settings, "artifact_publish_factor_values_on_pass", default))


def runtime_failed_workspace_retention(*, settings: Any | None = None) -> str:
    """返回失败候选 workspace 的运行时保留策略。"""

    if settings is None:
        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        settings = RD_AGENT_SETTINGS
        default = _RUNTIME_ARTIFACT_POLICY.failed_workspace_retention
    else:
        default = "full"
    return str(getattr(settings, "artifact_failed_workspace_retention", default))


def runtime_passed_workspace_retention(*, settings: Any | None = None) -> str:
    """返回通过候选 workspace 的运行时保留策略。"""

    if settings is None:
        from quantaalpha.core.conf import RD_AGENT_SETTINGS

        settings = RD_AGENT_SETTINGS
        default = _RUNTIME_ARTIFACT_POLICY.passed_workspace_retention
    else:
        default = "keep"
    return str(getattr(settings, "artifact_passed_workspace_retention", default))
