"""Dual parity backend。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DualParityBacktestBackend:
    """同跑 qlib 和 noqlib，并输出差异报告。"""

    def __init__(self, config_path: str, config: dict[str, Any]) -> None:
        self.config_path = config_path
        self.config = config

    def run(self, *args, **kwargs) -> dict:
        """运行双 backend。默认返回 qlib 结果。"""
        from quantaalpha.backtest.noqlib.backend import NoQlibBacktestBackend
        from quantaalpha.backtest.runner import BacktestRunner

        qlib_result = BacktestRunner(self.config_path).run(*args, **kwargs)
        noqlib_result = NoQlibBacktestBackend(self.config_path, dict(self.config)).run(*args, **kwargs)
        self._write_report(qlib_result, noqlib_result)
        return noqlib_result if self._output_winner() == "noqlib" else qlib_result

    def run_from_library(self, *args, **kwargs) -> dict:
        """从因子库运行双 backend。默认返回 qlib 结果。"""
        from quantaalpha.backtest.noqlib.backend import NoQlibBacktestBackend
        from quantaalpha.backtest.runner import BacktestRunner

        qlib_result = BacktestRunner(self.config_path).run_from_library(*args, **kwargs)
        noqlib_result = NoQlibBacktestBackend(self.config_path, dict(self.config)).run_from_library(*args, **kwargs)
        self._write_report(qlib_result.get("metrics", qlib_result), noqlib_result.get("metrics", noqlib_result))
        return noqlib_result if self._output_winner() == "noqlib" else qlib_result

    def _output_winner(self) -> str:
        return str(self.config.get("backtest_runtime", {}).get("parity", {}).get("output_winner", "qlib")).lower()

    def _write_report(self, qlib_result: dict[str, Any], noqlib_result: dict[str, Any]) -> None:
        output_dir = Path(self.config.get("experiment", {}).get("output_dir", "./backtest_v2_results"))
        output_dir.mkdir(parents=True, exist_ok=True)
        keys = sorted(set(qlib_result) | set(noqlib_result))
        diff = {
            key: {
                "qlib": qlib_result.get(key),
                "noqlib": noqlib_result.get(key),
                "abs_diff": _abs_diff(qlib_result.get(key), noqlib_result.get(key)),
            }
            for key in keys
        }
        (output_dir / "dual_parity_report.json").write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")


def _abs_diff(left: Any, right: Any) -> float | None:
    try:
        return abs(float(left) - float(right))
    except (TypeError, ValueError):
        return None

