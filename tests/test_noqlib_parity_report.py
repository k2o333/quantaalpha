from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.backtest.noqlib.parity_report import build_parity_report, main


def test_build_parity_report_marks_numeric_threshold_failures() -> None:
    report = build_parity_report(
        qlib_result={"IC": 0.10, "Rank IC": 0.20, "status": "ok"},
        noqlib_result={"IC": 0.100001, "Rank IC": 0.25, "status": "ok"},
        tolerance=1e-4,
    )

    assert report.passed is False
    assert report.metrics["IC"]["passed"] is True
    assert report.metrics["Rank IC"]["passed"] is False
    assert report.metrics["Rank IC"]["abs_diff"] == 0.04999999999999999
    assert report.metrics["status"]["passed"] is True


def test_parity_report_cli_compares_metric_json_and_returns_failure(tmp_path: Path, capsys) -> None:
    qlib_path = tmp_path / "qlib.json"
    noqlib_path = tmp_path / "noqlib.json"
    output_path = tmp_path / "parity.json"
    qlib_path.write_text(json.dumps({"IC": 0.1, "annualized_return": 0.2}), encoding="utf-8")
    noqlib_path.write_text(json.dumps({"IC": 0.1, "annualized_return": 0.25}), encoding="utf-8")

    exit_code = main(
        [
            "--qlib-result",
            str(qlib_path),
            "--noqlib-result",
            str(noqlib_path),
            "--tolerance",
            "0.001",
            "--output-path",
            str(output_path),
            "--format",
            "json",
        ]
    )

    assert exit_code == 1
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert stdout_payload["passed"] is False
    assert stdout_payload["metrics"]["annualized_return"]["passed"] is False
