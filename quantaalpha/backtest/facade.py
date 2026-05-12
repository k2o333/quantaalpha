"""回测 backend facade。

本模块只负责选择 qlib / noqlib / vnpy / parity 路线，并保持旧调用方
`run()` / `run_from_library()` 的返回 contract。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def resolve_backend(config: dict[str, Any], explicit_backend: str | None = None) -> str:
    """解析 backend 覆盖链：显式参数 > 环境变量 > YAML > 默认 qlib。"""
    backend = (
        explicit_backend
        or os.environ.get("QUANTAALPHA_BACKTEST_BACKEND")
        or config.get("backtest_runtime", {}).get("backend")
        or "qlib"
    )
    backend = str(backend).strip().lower()
    if backend not in {"qlib", "noqlib", "vnpy", "dual_parity", "triple_parity"}:
        raise ValueError(f"unsupported backtest backend: {backend}")
    return backend


class BacktestFacade:
    """兼容旧 BacktestRunner contract 的 backend 选择入口。"""

    def __init__(self, config_path: str, backend: str | None = None) -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.backend = resolve_backend(self.config, backend)
        self._delegate = self._build_delegate(self.backend)

    def _load_config(self) -> dict[str, Any]:
        with self.config_path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def _build_delegate(self, backend: str):
        if backend == "qlib":
            from quantaalpha.backtest.runner import BacktestRunner

            return BacktestRunner(str(self.config_path))
        if backend == "noqlib":
            from quantaalpha.backtest.noqlib.backend import NoQlibBacktestBackend

            return NoQlibBacktestBackend(str(self.config_path), self.config)
        if backend == "vnpy":
            from quantaalpha.backtest.vnpy.backend import VnpyBacktestBackend

            return VnpyBacktestBackend(str(self.config_path), self.config)
        from quantaalpha.backtest.parity import ParityBacktestBackend

        return ParityBacktestBackend(str(self.config_path), self.config, mode=backend)

    def run(self, *args, **kwargs) -> dict:
        """运行所选 backend。"""
        return self._delegate.run(*args, **kwargs)

    def run_from_library(self, *args, **kwargs) -> dict:
        """从因子库运行所选 backend。"""
        return self._delegate.run_from_library(*args, **kwargs)
