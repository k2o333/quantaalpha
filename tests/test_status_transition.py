from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add PKG_ROOT to sys.path
ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.factors.status_rules import (
    DEFAULT_FACTOR_STATUS_CONFIG,
    update_factor_status,
)


class TestStatusTransition(unittest.TestCase):
    def test_default_thresholds_match_plan(self):
        self.assertEqual(DEFAULT_FACTOR_STATUS_CONFIG["active_stability_threshold"], 0.5)
        self.assertEqual(DEFAULT_FACTOR_STATUS_CONFIG["degraded_stability_threshold"], 0.3)
        self.assertEqual(DEFAULT_FACTOR_STATUS_CONFIG["stale_threshold_days"], 30)

    def test_active_to_stale(self):
        now = datetime(2026, 3, 19)
        last_validated = (now - timedelta(days=31)).isoformat()
        entry = {
            "factor_id": "f1",
            "evaluation": {
                "status": "active",
                "last_validated": last_validated,
                "stability_score": 0.6,
                "consecutive_failures": 0
            }
        }
        updated = update_factor_status(entry, None, now=now)
        self.assertEqual(updated["evaluation"]["status"], "stale")

    def test_active_to_degraded_low_stability(self):
        now = datetime(2026, 3, 19)
        entry = {
            "factor_id": "f2",
            "evaluation": {
                "status": "active",
                "last_validated": now.isoformat(),
                "stability_score": 0.8,
                "consecutive_failures": 0
            }
        }
        # Planned threshold for degraded is 0.3 by default
        validation_result = {
            "status": "success",
            "summary": {"stability_score": 0.29, "validation_summary": "low stability"},
            "period_results": []
        }
        updated = update_factor_status(entry, validation_result, now=now)
        self.assertEqual(updated["evaluation"]["status"], "degraded")

    def test_degraded_to_active_boundary(self):
        now = datetime(2026, 3, 19)
        entry = {
            "factor_id": "f5",
            "evaluation": {
                "status": "degraded",
                "last_validated": now.isoformat(),
                "stability_score": 0.2,
                "consecutive_failures": 1
            }
        }
        # Planned threshold for active is 0.5 by default
        validation_result = {
            "status": "success",
            "summary": {"stability_score": 0.51, "validation_summary": "good stability now"},
            "period_results": []
        }
        updated = update_factor_status(entry, validation_result, now=now)
        self.assertEqual(updated["evaluation"]["status"], "active")
        self.assertEqual(updated["evaluation"]["consecutive_failures"], 0)


    def test_degraded_to_deprecated(self):
        now = datetime(2026, 3, 19)
        entry = {
            "factor_id": "f4",
            "evaluation": {
                "status": "degraded",
                "last_validated": now.isoformat(),
                "stability_score": 0.2,
                "consecutive_failures": 2
            }
        }
        # Threshold for deprecated is consecutive_failures >= 3
        validation_result = {
            "status": "failure",
            "summary": {"stability_score": 0.1, "validation_summary": "failed again"},
            "period_results": []
        }
        updated = update_factor_status(entry, validation_result, now=now)
        self.assertEqual(updated["evaluation"]["status"], "deprecated")
        self.assertEqual(updated["evaluation"]["consecutive_failures"], 3)

    def test_degraded_to_active_high_stability(self):
        now = datetime(2026, 3, 19)
        entry = {
            "factor_id": "f5",
            "evaluation": {
                "status": "degraded",
                "last_validated": now.isoformat(),
                "stability_score": 0.2,
                "consecutive_failures": 1
            }
        }
        validation_result = {
            "status": "success",
            "summary": {"stability_score": 0.7, "validation_summary": "good stability now"},
            "period_results": []
        }
        updated = update_factor_status(entry, validation_result, now=now)
        self.assertEqual(updated["evaluation"]["status"], "active")
        self.assertEqual(updated["evaluation"]["consecutive_failures"], 0)

if __name__ == "__main__":
    unittest.main()
