from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_dual_parity_report_supports_vnpy_pairs() -> None:
    from quantaalpha.backtest.parity import build_parity_report

    report = build_parity_report(
        {
            "qlib": {"IC": 0.1},
            "vnpy": {"IC": 0.2},
        },
        mode="qlib_vs_vnpy",
    )
    assert report["mode"] == "qlib_vs_vnpy"
    assert set(report["pairs"]) == {"qlib_vs_vnpy"}
    assert set(report["pairs"]["qlib_vs_vnpy"]) == {"data", "feature", "label", "prediction", "portfolio", "metrics"}
    assert report["output_winner"] is None


def test_triple_parity_report_compares_all_backend_pairs_without_winner() -> None:
    from quantaalpha.backtest.parity import build_parity_report

    report = build_parity_report(
        {
            "qlib": {"IC": 0.1, "Rank IC": 0.1},
            "noqlib": {"IC": 0.1, "Rank IC": 0.11},
            "vnpy": {"IC": 0.2, "Rank IC": 0.1},
        },
        mode="triple",
    )
    assert report["backends"] == ("qlib", "noqlib", "vnpy")
    assert set(report["pairs"]) == {"qlib_vs_noqlib", "qlib_vs_vnpy", "noqlib_vs_vnpy"}
    assert report["pairs"]["noqlib_vs_vnpy"]["metrics"]["IC"]["abs_diff"] == 0.1
    assert report["output_winner"] is None
