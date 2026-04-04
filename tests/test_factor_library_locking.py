from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
import threading
import time
import unittest.mock
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


class TestFactorLibraryLocking(unittest.TestCase):
    def test_save_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            manager = library_mod.FactorLibraryManager(str(lib_path))
            manager.data["factors"]["test_f1"] = {
                "factor_id": "test_f1",
                "factor_name": "TestFactor",
                "factor_expression": "$close/$open",
                "evaluation": {"status": "active", "stability_score": 0.5},
                "metadata": {"evolution_phase": "original"},
            }
            manager._save()
            with open(lib_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertIn("test_f1", loaded["factors"])
            no_tmp = list(Path(tmp).glob(".*lib.json*.tmp"))
            self.assertEqual(len(no_tmp), 0, "No temp files should remain after save")

    def test_concurrent_save_from_multiple_managers(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            errors = []
            saved_count = [0]
            count_lock = threading.Lock()

            def writer(manager_idx):
                try:
                    mgr = library_mod.FactorLibraryManager(str(lib_path))
                    mgr.data["factors"][f"concurrent_f{manager_idx}"] = {
                        "factor_id": f"concurrent_f{manager_idx}",
                        "factor_name": f"ConcurrentFactor{manager_idx}",
                        "factor_expression": f"$close/$(manager_idx)",
                        "evaluation": {"status": "active", "stability_score": 0.5},
                        "metadata": {"evolution_phase": "original"},
                    }
                    mgr._save()
                    with count_lock:
                        saved_count[0] += 1
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"Errors during concurrent writes: {errors}")
            self.assertEqual(saved_count[0], 5)
            with open(lib_path, "r", encoding="utf-8") as f:
                final = json.load(f)
            self.assertEqual(len(final["factors"]), 5)

    def test_lock_acquire_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            mgr = library_mod.FactorLibraryManager(str(lib_path))
            lock_fd = mgr._acquire_lock()
            try:
                self.assertIsNotNone(lock_fd)
                self.assertTrue(hasattr(lock_fd, "fileno"))
            finally:
                mgr._release_lock(lock_fd)

    def test_lock_released_after_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            mgr = library_mod.FactorLibraryManager(str(lib_path))
            mgr.data["factors"]["locktest"] = {
                "factor_id": "locktest",
                "factor_name": "LockTest",
                "factor_expression": "$close",
                "evaluation": {"status": "active"},
                "metadata": {"evolution_phase": "original"},
            }
            mgr._save()
            second_fd = mgr._acquire_lock()
            try:
                self.assertIsNotNone(second_fd)
            finally:
                mgr._release_lock(second_fd)

    def test_upsert_is_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib_path = Path(tmp) / "lib.json"
            lib_path.write_text(
                json.dumps({"metadata": {}, "factors": {}}), encoding="utf-8"
            )
            mgr = library_mod.FactorLibraryManager(str(lib_path))
            entry = {
                "factor_id": "upsert_protected",
                "factor_name": "UpsertProtected",
                "factor_expression": "$close/$open",
                "evaluation": {"status": "active", "stability_score": 0.7},
                "metadata": {"evolution_phase": "mutation"},
            }
            result = mgr.upsert_factor(entry)
            self.assertEqual(result["factor_id"], "upsert_protected")
            reupsert = {
                "factor_id": "upsert_protected",
                "factor_name": "UpsertProtectedUpdated",
                "factor_expression": "$volume",
                "evaluation": {"status": "active", "stability_score": 0.8},
                "metadata": {"evolution_phase": "mutation"},
            }
            result2 = mgr.upsert_factor(reupsert)
            self.assertEqual(result2["factor_name"], "UpsertProtectedUpdated")
            with open(lib_path, "r", encoding="utf-8") as f:
                persisted = json.load(f)
            self.assertEqual(
                persisted["factors"]["upsert_protected"]["factor_name"],
                "UpsertProtectedUpdated",
            )


if __name__ == "__main__":
    unittest.main()
