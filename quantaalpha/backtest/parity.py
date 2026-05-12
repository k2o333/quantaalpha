"""Dual and triple backend parity report helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BACKEND_PAIRS = {
    "qlib_vs_noqlib": ("qlib", "noqlib"),
    "qlib_vs_vnpy": ("qlib", "vnpy"),
    "noqlib_vs_vnpy": ("noqlib", "vnpy"),
}
LAYERS = ["data", "feature", "label", "prediction", "portfolio", "metrics"]


class ParityBacktestBackend:
    """同跑多个 backend，并写出 layer-by-layer 差异报告。"""

    def __init__(self, config_path: str, config: dict[str, Any], mode: str = "dual_parity") -> None:
        self.config_path = config_path
        self.config = config
        self.mode = mode

    def run(self, *args, **kwargs) -> dict:
        """运行 parity backend。"""
        results = self._run_backends(*args, **kwargs)
        report = build_parity_report(results, mode=self._parity_mode())
        self._write_report(report)
        winner = self._output_winner()
        if winner:
            return results[winner]
        return {"parity_report": report, "results": results}

    def run_from_library(self, *args, **kwargs) -> dict:
        """从因子库运行 parity backend。"""
        results = {
            backend: _extract_metrics(delegate.run_from_library(*args, **kwargs))
            for backend, delegate in self._delegates().items()
        }
        report = build_parity_report(results, mode=self._parity_mode())
        self._write_report(report)
        winner = self._output_winner()
        if winner:
            return results[winner]
        return {"parity_report": report, "results": results}

    def _run_backends(self, *args, **kwargs) -> dict[str, dict[str, Any]]:
        return {backend: delegate.run(*args, **kwargs) for backend, delegate in self._delegates().items()}

    def _delegates(self) -> dict[str, Any]:
        backends = _backends_for_mode(self._parity_mode())
        return {backend: _build_backend(backend, self.config_path, self.config) for backend in backends}

    def _parity_mode(self) -> str:
        parity_cfg = self.config.get("backtest_runtime", {}).get("parity", {})
        if self.mode == "triple_parity":
            return "triple"
        return str(parity_cfg.get("mode", "qlib_vs_noqlib")).lower()

    def _output_winner(self) -> str | None:
        parity_cfg = self.config.get("backtest_runtime", {}).get("parity", {})
        winner = parity_cfg.get("output_winner")
        if winner is None and self.mode == "dual_parity":
            return "qlib"
        if winner is None:
            return None
        winner = str(winner).lower()
        if winner not in _backends_for_mode(self._parity_mode()):
            raise ValueError(f"parity output_winner is not part of mode: {winner}")
        return winner

    def _write_report(self, report: dict[str, Any]) -> None:
        output_dir = Path(self.config.get("experiment", {}).get("output_dir", "./backtest_v2_results"))
        output_dir.mkdir(parents=True, exist_ok=True)
        name = "triple_parity_report.json" if self._parity_mode() == "triple" else "dual_parity_report.json"
        (output_dir / name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parity_report(results: dict[str, dict[str, Any]], mode: str = "qlib_vs_noqlib") -> dict[str, Any]:
    """构建双路或三路 parity 报告，不默认选择生产 winner。"""
    backends = _backends_for_mode(mode)
    missing = [backend for backend in backends if backend not in results]
    if missing:
        raise ValueError(f"parity results missing backends: {missing}")
    pairs = list(BACKEND_PAIRS.items()) if mode == "triple" else [(mode, BACKEND_PAIRS[mode])]
    pair_reports = {
        pair_name: {
            layer: _compare_metrics(results[left], results[right]) if layer == "metrics" else {"status": "not_collected"}
            for layer in LAYERS
        }
        for pair_name, (left, right) in pairs
        if left in results and right in results
    }
    return {
        "mode": mode,
        "backends": backends,
        "layers": LAYERS,
        "pairs": pair_reports,
        "output_winner": None,
    }


def _build_backend(backend: str, config_path: str, config: dict[str, Any]) -> Any:
    if backend == "qlib":
        from quantaalpha.backtest.runner import BacktestRunner

        return BacktestRunner(config_path)
    if backend == "noqlib":
        from quantaalpha.backtest.noqlib.backend import NoQlibBacktestBackend

        return NoQlibBacktestBackend(config_path, dict(config))
    if backend == "vnpy":
        from quantaalpha.backtest.vnpy.backend import VnpyBacktestBackend

        return VnpyBacktestBackend(config_path, dict(config))
    raise ValueError(f"unsupported parity backend: {backend}")


def _backends_for_mode(mode: str) -> tuple[str, ...]:
    if mode == "triple":
        return ("qlib", "noqlib", "vnpy")
    if mode not in BACKEND_PAIRS:
        raise ValueError(f"unsupported parity mode: {mode}")
    return BACKEND_PAIRS[mode]


def _compare_metrics(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(left) | set(right))
    return {
        key: {
            "left": left.get(key),
            "right": right.get(key),
            "abs_diff": _abs_diff(left.get(key), right.get(key)),
            "passed": left.get(key) == right.get(key) if _abs_diff(left.get(key), right.get(key)) is None else _abs_diff(left.get(key), right.get(key)) == 0,
        }
        for key in keys
    }


def _extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return result.get("metrics", result)


def _abs_diff(left: Any, right: Any) -> float | None:
    try:
        return abs(float(left) - float(right))
    except (TypeError, ValueError):
        return None
