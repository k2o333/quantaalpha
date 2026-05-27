from quantaalpha.factors.factor_store_facade import FactorStoreFacade


class RecordingLock:
    events = []

    def __init__(self, lock_path, timeout_seconds=0, owner="", run_id=""):
        self.lock_path = str(lock_path)
        self.owner = owner
        self.run_id = run_id

    def acquire(self):
        self.events.append(("acquire", self.owner, self.lock_path))
        return True

    def release(self):
        self.events.append(("release", self.owner, self.lock_path))


class FakeParquetStore:
    def __init__(self):
        self.writes = []
        self.compacted = False

    def write_factor_delta(self, entry):
        self.writes.append(entry)

    def compact(self, archive_retention=None):
        self.compacted = True


def test_facade_write_factor_uses_factor_store_write_lock(tmp_path):
    RecordingLock.events = []
    facade = FactorStoreFacade(
        store_path=tmp_path / "store",
        lock_dir=tmp_path / "locks",
        lock_factory=RecordingLock,
    )
    facade._parquet = FakeParquetStore()

    facade.write_factor({"factor_id": "f1"})

    assert facade._parquet.writes == [{"factor_id": "f1"}]
    assert RecordingLock.events[0][0:2] == ("acquire", "factor_store")
    assert RecordingLock.events[-1][0:2] == ("release", "factor_store")
    assert RecordingLock.events[0][2].endswith("factor_store_write.lock")


def test_facade_compact_uses_factor_store_write_lock(tmp_path):
    RecordingLock.events = []
    facade = FactorStoreFacade(
        store_path=tmp_path / "store",
        lock_dir=tmp_path / "locks",
        lock_factory=RecordingLock,
    )
    facade._parquet = FakeParquetStore()
    facade.delta_file_count = lambda: 1

    facade.compact()

    assert facade._parquet.compacted is True
    assert RecordingLock.events == [
        ("acquire", "factor_store", str(tmp_path / "locks" / "factor_store_write.lock")),
        ("release", "factor_store", str(tmp_path / "locks" / "factor_store_write.lock")),
    ]
