from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"


def _ensure_stubs():
    if "pandas" not in sys.modules:
        stub = types.ModuleType("pandas")
        stub.Series = type("Series", (), {})
        stub.DataFrame = type("DataFrame", (), {})
        stub.read_hdf = lambda *a, **k: None
        sys.modules["pandas"] = stub
    if "numpy" not in sys.modules:
        np_stub = types.ModuleType("numpy")
        np_stub.inf = float("inf")
        np_stub.nan = float("nan")
        np_stub.floating = (float,)
        np_stub.isnan = lambda x: False
        np_stub.isinf = lambda x: False
        sys.modules["numpy"] = np_stub
    if "quantaalpha" not in sys.modules:
        sys.modules["quantaalpha"] = types.ModuleType("quantaalpha")
    if "quantaalpha.factors" not in sys.modules:
        pkg = types.ModuleType("quantaalpha.factors")
        pkg.__path__ = [str(PKG_ROOT / "factors")]
        sys.modules["quantaalpha.factors"] = pkg


_ensure_stubs()

import importlib.util

spec = importlib.util.spec_from_file_location(
    "quantaalpha.factors.library", PKG_ROOT / "factors" / "library.py"
)
library_mod = importlib.util.module_from_spec(spec)
sys.modules["quantaalpha.factors.library"] = library_mod
spec.loader.exec_module(library_mod)


class TestSchedulerSummary(unittest.TestCase):
    def _write_fake_quantaalpha(self, bin_dir: Path, *, revalidate_exit: int = 0) -> Path:
        calls_file = bin_dir / "calls.txt"
        script_path = bin_dir / "quantaalpha"
        script_path.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    f'echo \"$@\" >> "{calls_file}"',
                    'if [ "$1" = "mine" ]; then exit 0; fi',
                    f'if [ "$1" = "revalidate" ]; then exit {revalidate_exit}; fi',
                    "exit 0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        script_path.chmod(0o755)
        return calls_file

    def test_get_summary_empty_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            summary = manager.get_summary()
            self.assertEqual(summary["total_factors"], 0)
            self.assertEqual(summary["status_distribution"], {})
            self.assertEqual(summary["stale_count"], 0)
            self.assertEqual(summary["active_count"], 0)
            self.assertEqual(summary["degraded_count"], 0)
            self.assertIsNotNone(summary["last_updated"])

    def test_get_summary_with_factors(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            factors = {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "FactorActive",
                    "factor_expression": "$close/$open",
                    "evaluation": {
                        "status": "active",
                        "stability_score": 0.75,
                        "last_validated": now.isoformat(),
                    },
                    "metadata": {
                        "evolution_phase": "original",
                        "created_at": now.isoformat(),
                    },
                },
                "f2": {
                    "factor_id": "f2",
                    "factor_name": "FactorPending",
                    "factor_expression": "$volume",
                    "evaluation": {
                        "status": "pending_validation",
                        "stability_score": None,
                    },
                    "metadata": {
                        "evolution_phase": "mutation",
                        "created_at": now.isoformat(),
                    },
                },
                "f3": {
                    "factor_id": "f3",
                    "factor_name": "FactorDegraded",
                    "factor_expression": "$open/$close",
                    "evaluation": {
                        "status": "degraded",
                        "stability_score": 0.2,
                        "last_validated": now.isoformat(),
                    },
                    "metadata": {
                        "evolution_phase": "original",
                        "created_at": now.isoformat(),
                    },
                },
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            summary = manager.get_summary()
            self.assertEqual(summary["total_factors"], 3)
            self.assertEqual(summary["status_distribution"]["active"], 1)
            self.assertEqual(summary["status_distribution"]["pending_validation"], 1)
            self.assertEqual(summary["status_distribution"]["degraded"], 1)
            self.assertEqual(summary["active_count"], 1)
            self.assertEqual(summary["degraded_count"], 1)
            self.assertEqual(summary["stale_count"], 0)
            self.assertEqual(summary["evolution_counts"]["original"], 2)
            self.assertEqual(summary["evolution_counts"]["mutation"], 1)
            self.assertEqual(summary["total_validated"], 2)
            self.assertEqual(summary["total_active"], 1)
            self.assertIsNotNone(summary["avg_stability_score"])
            self.assertAlmostEqual(
                summary["avg_stability_score"],
                round((0.75 + 0.2) / 2, 6),
                places=4,
            )

    def test_apply_validation_result_appends_audit_on_status_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            factors = {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "FactorOne",
                    "factor_expression": "$close",
                    "evaluation": {
                        "status": "pending_validation",
                        "last_validated": None,
                        "stability_score": None,
                    },
                    "metadata": {"created_at": now.isoformat()},
                }
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            updated = manager.apply_validation_result(
                manager.get_factor("f1"),
                {
                    "status": "success",
                    "period_results": [{"period": "2025Q4", "metrics": {"IC": 0.1}}],
                    "summary": {
                        "stability_score": 0.7,
                        "validation_summary": "status changed",
                    },
                },
            )
            self.assertEqual(updated["evaluation"]["status"], "active")

            reloaded = library_mod.FactorLibraryManager(str(lib_path))
            trail = reloaded.get_audit_trail()
            self.assertEqual(len(trail), 1)
            self.assertEqual(trail[0]["factor_id"], "f1")
            self.assertEqual(trail[0]["old_status"], "pending_validation")
            self.assertEqual(trail[0]["new_status"], "active")

    def test_apply_validation_result_does_not_append_audit_without_status_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            factors = {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "FactorOne",
                    "factor_expression": "$close",
                    "evaluation": {
                        "status": "active",
                        "last_validated": now.isoformat(),
                        "stability_score": 0.8,
                    },
                    "metadata": {"created_at": now.isoformat()},
                }
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            manager.apply_validation_result(
                manager.get_factor("f1"),
                {
                    "status": "success",
                    "period_results": [{"period": "2025Q4", "metrics": {"IC": 0.11}}],
                    "summary": {
                        "stability_score": 0.75,
                        "validation_summary": "still active",
                    },
                },
            )
            reloaded = library_mod.FactorLibraryManager(str(lib_path))
            self.assertEqual(reloaded.get_audit_trail(), [])

    def test_audit_trail_trimmed_to_recent_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            audit_entries = [
                {
                    "timestamp": (now - timedelta(minutes=i)).isoformat(),
                    "factor_id": f"f{i}",
                    "factor_name": f"Factor{i}",
                    "old_status": "pending_validation",
                    "new_status": "active",
                    "reason": "trim test",
                    "trigger": "validation",
                }
                for i in range(8)
            ]
            lib_path.write_text(
                json.dumps(
                    {"metadata": {"audit_trail": audit_entries}, "factors": {}}
                ),
                encoding="utf-8",
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            self.assertEqual(len(manager.get_audit_trail(limit=3)), 3)

    def test_get_audit_trail_returns_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            audit_trail = [
                {
                    "timestamp": now.isoformat(),
                    "factor_id": "f1",
                    "factor_name": "FactorOne",
                    "old_status": "pending_validation",
                    "new_status": "active",
                    "reason": "validated",
                    "trigger": "apply_validation_result",
                },
                {
                    "timestamp": (now - timedelta(days=5)).isoformat(),
                    "factor_id": "f2",
                    "factor_name": "FactorTwo",
                    "old_status": "active",
                    "new_status": "degraded",
                    "reason": "stability drop",
                    "trigger": "apply_validation_result",
                },
            ]
            lib_path.write_text(
                json.dumps({"metadata": {"audit_trail": audit_trail}, "factors": {}}),
                encoding="utf-8",
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            trail = manager.get_audit_trail()
            self.assertEqual(len(trail), 2)
            ids = {e["factor_id"] for e in trail}
            self.assertIn("f1", ids)
            self.assertIn("f2", ids)

    def test_get_audit_trail_filter_by_factor_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            audit_trail = [
                {
                    "timestamp": now.isoformat(),
                    "factor_id": "f1",
                    "factor_name": "FactorOne",
                    "old_status": "pending_validation",
                    "new_status": "active",
                    "reason": "validated",
                    "trigger": "apply_validation_result",
                },
                {
                    "timestamp": now.isoformat(),
                    "factor_id": "f2",
                    "factor_name": "FactorTwo",
                    "old_status": "pending_validation",
                    "new_status": "active",
                    "reason": "validated",
                    "trigger": "apply_validation_result",
                },
            ]
            lib_path.write_text(
                json.dumps({"metadata": {"audit_trail": audit_trail}, "factors": {}}),
                encoding="utf-8",
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            trail = manager.get_audit_trail(factor_id="f1")
            self.assertEqual(len(trail), 1)
            self.assertEqual(trail[0]["factor_id"], "f1")

    def test_get_audit_trail_since_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            audit_trail = [
                {
                    "timestamp": now.isoformat(),
                    "factor_id": "f1",
                    "factor_name": "Recent",
                    "old_status": "degraded",
                    "new_status": "active",
                    "reason": "recovered",
                    "trigger": "apply_validation_result",
                },
                {
                    "timestamp": (now - timedelta(days=30)).isoformat(),
                    "factor_id": "f2",
                    "factor_name": "Old",
                    "old_status": "active",
                    "new_status": "stale",
                    "reason": "aged out",
                    "trigger": "apply_validation_result",
                },
            ]
            lib_path.write_text(
                json.dumps({"metadata": {"audit_trail": audit_trail}, "factors": {}}),
                encoding="utf-8",
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            since = (now - timedelta(days=7)).isoformat()
            trail = manager.get_audit_trail(since=since)
            self.assertEqual(len(trail), 1)
            self.assertEqual(trail[0]["factor_id"], "f1")

    def test_get_audit_trail_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            audit_trail = [
                {
                    "timestamp": (now - timedelta(minutes=i)).isoformat(),
                    "factor_id": f"f{i}",
                    "factor_name": f"Factor{i}",
                    "old_status": "pending_validation",
                    "new_status": "active",
                    "reason": "validated",
                    "trigger": "apply_validation_result",
                }
                for i in range(10)
            ]
            lib_path.write_text(
                json.dumps({"metadata": {"audit_trail": audit_trail}, "factors": {}}),
                encoding="utf-8",
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            trail = manager.get_audit_trail(limit=3)
            self.assertEqual(len(trail), 3)

    def test_upsert_factor(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            new_entry = {
                "factor_id": "upserted_f1",
                "factor_name": "UpsertedFactor",
                "factor_expression": "$close/$open",
                "evaluation": {"status": "active", "stability_score": 0.9},
                "metadata": {"evolution_phase": "original"},
            }
            result = manager.upsert_factor(new_entry)
            self.assertEqual(result["factor_id"], "upserted_f1")
            self.assertEqual(result["evaluation"]["status"], "active")
            stored = manager.get_factor("upserted_f1")
            self.assertIsNotNone(stored)
            self.assertEqual(stored["factor_name"], "UpsertedFactor")

    def test_list_factor_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            now = datetime.now()
            factors = {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "Active",
                    "factor_expression": "$close",
                    "evaluation": {"status": "active"},
                    "metadata": {},
                },
                "f2": {
                    "factor_id": "f2",
                    "factor_name": "Pending",
                    "factor_expression": "$volume",
                    "evaluation": {"status": "pending_validation"},
                    "metadata": {},
                },
            }
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": factors}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            all_ids = manager.list_factor_ids()
            self.assertEqual(len(all_ids), 2)
            active_ids = manager.list_factor_ids(status="active")
            self.assertEqual(active_ids, ["f1"])
            pending_ids = manager.list_factor_ids(status="pending_validation")
            self.assertEqual(pending_ids, ["f2"])

    def test_continuous_mine_uses_project_root_default_library_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            calls_file = self._write_fake_quantaalpha(bin_dir)

            project_root = PKG_ROOT.parent
            script_path = project_root / "scripts" / "continuous_mine.sh"
            suffix = f"smoke_{os.getpid()}"
            library_path = (
                project_root / "data" / "factorlib" / f"all_factors_library_{suffix}.json"
            )
            library_path.parent.mkdir(parents=True, exist_ok=True)
            library_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["MAX_ITERATIONS"] = "1"
            env["FACTOR_LIBRARY_SUFFIX"] = suffix
            env["PYTHON_BIN"] = sys.executable

            try:
                result = subprocess.run(
                    ["bash", str(script_path), "test-direction"],
                    cwd=str(project_root),
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = calls_file.read_text(encoding="utf-8")
                self.assertIn(
                    f"revalidate {library_path} --dry_run True --no_write True",
                    calls,
                )
            finally:
                library_path.unlink(missing_ok=True)

    def test_continuous_mine_exits_nonzero_when_revalidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            self._write_fake_quantaalpha(bin_dir, revalidate_exit=9)

            project_root = PKG_ROOT.parent
            script_path = project_root / "scripts" / "continuous_mine.sh"
            library_path = Path(tmp) / "lib.json"
            library_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            env["MAX_ITERATIONS"] = "1"
            env["LIBRARY_PATH"] = str(library_path)
            env["PYTHON_BIN"] = sys.executable

            result = subprocess.run(
                ["bash", str(script_path), "test-direction"],
                cwd=str(project_root),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 9)
            self.assertIn("Revalidate exited with code 9", result.stdout)


if __name__ == "__main__":
    unittest.main()
