from quantaalpha.continuous.resource_governor import FileLock


def test_file_lock_nonblocking_busy_returns_false(tmp_path):
    lock_path = tmp_path / "global_compute.lock"

    first = FileLock(lock_path, timeout_seconds=0, owner="mining", run_id="run-1")
    second = FileLock(lock_path, timeout_seconds=0, owner="revalidation", run_id="run-2")

    assert first.acquire() is True
    try:
        assert second.acquire() is False
    finally:
        first.release()


def test_file_lock_writes_owner_metadata(tmp_path):
    lock_path = tmp_path / "factor_store_write.lock"
    lock = FileLock(lock_path, timeout_seconds=0, owner="mining", run_id="run-1")

    assert lock.acquire() is True
    try:
        metadata = lock.read_metadata()
        assert metadata["owner"] == "mining"
        assert metadata["run_id"] == "run-1"
        assert metadata["pid"] > 0
        assert metadata["created_at"]
    finally:
        lock.release()
