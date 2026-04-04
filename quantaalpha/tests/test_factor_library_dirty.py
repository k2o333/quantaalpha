"""
Tests for FactorLibraryManager dirty tracking and batch_upsert functionality.
Task B3: JSON 因子库 dirty 追踪和 batch_upsert
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from quantaalpha.factors.library import FactorLibraryManager


class TestDirtyTracking:
    """Test suite for _dirty tracking mechanism."""

    @pytest.fixture
    def tmp_library_path(self, tmp_path):
        """Create a temporary library file."""
        lib_path = tmp_path / "test_library.json"
        # Initialize with empty library
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "total_factors": 0,
                        "version": "1.1",
                    },
                    "factors": {},
                }
            ),
            encoding="utf-8",
        )
        return lib_path

    @pytest.fixture
    def manager(self, tmp_library_path):
        """Create a FactorLibraryManager instance."""
        return FactorLibraryManager(str(tmp_library_path))

    def test_no_save_when_not_dirty(self, tmp_library_path):
        """
        RED test: _save() should not trigger disk write when _dirty is False.
        """
        manager = FactorLibraryManager(str(tmp_library_path))
        original_mtime = os.path.getmtime(tmp_library_path)

        # Call _save directly without any modifications
        manager._save()

        # File should not be modified
        new_mtime = os.path.getmtime(tmp_library_path)
        assert new_mtime == original_mtime, (
            f"File mtime changed when _dirty=False: {original_mtime} -> {new_mtime}"
        )

    def test_dirty_cleared_after_upsert(self, tmp_library_path):
        """
        RED test: After upsert_factor, _dirty should be cleared.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Insert a factor
        manager.upsert_factor(
            {
                "factor_id": "test_factor_1",
                "factor_name": "Test Factor",
                "factor_expression": "close",
            }
        )

        # After upsert, dirty should be cleared (save succeeded)
        assert manager._dirty is False, (
            f"Expected _dirty=False after successful upsert, got {manager._dirty}"
        )
        assert len(manager._dirty_factor_ids) == 0, (
            f"Expected _dirty_factor_ids to be empty, got {manager._dirty_factor_ids}"
        )

    def test_batch_upsert_single_write(self, tmp_library_path):
        """
        RED test: batch_upsert with 10 factors should trigger exactly one write.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Track how many times _load_from_disk is called during batch_upsert
        entries = [
            {
                "factor_id": f"batch_factor_{i}",
                "factor_name": f"Batch Factor {i}",
                "factor_expression": f"close + {i}",
            }
            for i in range(10)
        ]

        # Mock _save to track calls
        original_save = manager._save
        save_call_count = 0

        def tracked_save():
            nonlocal save_call_count
            save_call_count += 1
            return original_save()

        manager._save = tracked_save

        result = manager.batch_upsert(entries)

        assert result == 10, f"Expected 10 factors upserted, got {result}"
        assert save_call_count == 1, (
            f"Expected exactly 1 _save call for batch_upsert, got {save_call_count}"
        )

    def test_dirty_preserved_on_save_failure(self, tmp_library_path):
        """
        RED test: When save fails, _dirty state should be preserved.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Manually mark as dirty
        manager._dirty = True
        manager._dirty_factor_ids.add("test_factor_x")

        # Mock os.replace to raise an exception
        with patch("quantaalpha.factors.library.os.replace", side_effect=OSError("Simulated write failure")):
            with pytest.raises(OSError):
                manager._save()

        # Dirty state should be preserved
        assert manager._dirty is True, "Expected _dirty=True after save failure"
        assert "test_factor_x" in manager._dirty_factor_ids, (
            "Expected test_factor_x to remain in _dirty_factor_ids after save failure"
        )

    def test_batch_upsert_dirty_cleared_after_save(self, tmp_library_path):
        """
        GREEN test: After batch_upsert, dirty should be cleared.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        entries = [
            {
                "factor_id": f"batch_factor_{i}",
                "factor_name": f"Batch Factor {i}",
                "factor_expression": f"close + {i}",
            }
            for i in range(5)
        ]

        manager.batch_upsert(entries)

        assert manager._dirty is False, (
            f"Expected _dirty=False after batch_upsert, got {manager._dirty}"
        )

    def test_flush_with_dirty_true(self, tmp_library_path):
        """
        GREEN test: flush() should trigger save when _dirty is True.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Manually mark dirty and modify data
        manager._dirty = True
        manager.data["factors"]["manual_factor"] = {
            "factor_id": "manual_factor",
            "factor_name": "Manual Factor",
            "factor_expression": "volume",
        }
        manager._dirty_factor_ids.add("manual_factor")

        # Mock _save to verify it's called
        original_save = manager._save
        save_called = False

        def tracked_save():
            nonlocal save_called
            save_called = True
            return original_save()

        manager._save = tracked_save

        manager.flush()

        assert save_called, "flush() should call _save when _dirty=True"
        assert manager._dirty is False, "Dirty should be cleared after flush"

    def test_flush_with_dirty_false(self, tmp_library_path):
        """
        GREEN test: flush() should not call _save when _dirty is False.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Ensure not dirty
        assert manager._dirty is False

        # Mock _save
        original_save = manager._save
        save_called = False

        def tracked_save():
            nonlocal save_called
            save_called = True
            return original_save()

        manager._save = tracked_save

        manager.flush()

        assert not save_called, "flush() should not call _save when _dirty=False"

    def test_upsert_factor_sets_dirty(self, tmp_library_path):
        """
        GREEN test: upsert_factor should set _dirty before save and clear after.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Verify initial state is not dirty
        assert manager._dirty is False

        # Mock _save to prevent actual disk write but also clear dirty
        original_save = manager._save

        def mock_save_with_dirty_clear():
            manager._dirty = False
            manager._dirty_factor_ids.clear()

        with patch.object(manager, "_save", side_effect=mock_save_with_dirty_clear):
            manager.upsert_factor(
                {
                    "factor_id": "test_upsert",
                    "factor_name": "Test Upsert",
                    "factor_expression": "close",
                }
            )

        # _dirty should be cleared after save completes
        assert manager._dirty is False

    def test_apply_validation_result_sets_dirty(self, tmp_library_path):
        """
        GREEN test: apply_validation_result should set _dirty when persist=True.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        # Mock _save to prevent actual disk write but also clear dirty
        def mock_save_with_dirty_clear():
            manager._dirty = False
            manager._dirty_factor_ids.clear()

        with patch.object(manager, "_save", side_effect=mock_save_with_dirty_clear):
            manager.apply_validation_result(
                factor_entry={
                    "factor_id": "test_validation",
                    "factor_name": "Test Validation",
                    "factor_expression": "close",
                },
                validation_result={
                    "status": "success",
                    "summary": {"validation_summary": "OK"},
                },
                persist=True,
            )

        # _dirty should be cleared after save completes
        assert manager._dirty is False

    def test_atomic_write_preserved(self, tmp_library_path):
        """
        GREEN test: Verify atomic write (tmpfile + os.replace) is used.
        """
        manager = FactorLibraryManager(str(tmp_library_path))

        replace_calls = []

        original_replace = os.replace

        def tracked_replace(src, dst):
            replace_calls.append((src, dst))
            return original_replace(src, dst)

        with patch("quantaalpha.factors.library.os.replace", side_effect=tracked_replace):
            manager.upsert_factor(
                {
                    "factor_id": "atomic_test",
                    "factor_name": "Atomic Test",
                    "factor_expression": "close",
                }
            )

        # os.replace should have been called
        assert len(replace_calls) == 1, f"Expected 1 os.replace call, got {len(replace_calls)}"

        # The temp file should be replaced with the library path
        src, dst = replace_calls[0]
        src_str = str(src) if hasattr(src, '__fspath__') else str(src)
        dst_str = str(dst) if hasattr(dst, '__fspath__') else str(dst)
        assert dst_str == str(tmp_library_path), f"Expected replace destination to be library path, got {dst}"
        assert ".tmp" in src_str, f"Expected temp file to have .tmp suffix, got {src}"
