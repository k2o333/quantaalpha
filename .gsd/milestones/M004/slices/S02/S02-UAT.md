# S02: 因子重验候选选择 — UAT

**Milestone:** M004
**Written:** 2026-03-24
**UAT Mode:** Contract verification (no live runtime required)
**Proof Level:** Contract — unit tests, type checks

## Preconditions

- Python 3.12+ with quantaalpha importable
- `quantaalpha/factors/library.py` and `quantaalpha/factors/status_rules.py` compile without errors
- `tests/test_revalidation_candidates.py` exists and is runnable with pytest

## Smoke Test

```bash
# 1. Verify syntax
python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/status_rules.py

# 2. Verify method exists
grep -c "select_revalidation_candidates" third_party/quantaalpha/quantaalpha/factors/library.py
# Expected: 1 (or more — the method definition)

# 3. Run unit tests
cd third_party/quantaalpha && python -m pytest tests/test_revalidation_candidates.py -v
# Expected: 15 passed
```

## Test Cases

### 1. last_validated field is initialized on new factor entries

**Steps:**
1. Instantiate a `FactorLibraryManager` with a temp path
2. Call `_normalize_factor_entry({})` with an empty dict
3. Check `entry["evaluation"]["last_validated"]`

**Expected:** Value is a non-empty string matching ISO 8601 format (e.g. `"2026-03-24T01:28:14.123456"`), not `None`

**Verification:**
```python
manager = FactorLibraryManager.__new__(FactorLibraryManager)
entry = manager._normalize_factor_entry({})
from datetime import datetime
dt = datetime.fromisoformat(entry["evaluation"]["last_validated"])
assert dt.year == 2026
```

---

### 2. select_revalidation_candidates(days=N) returns overdue active factors

**Setup:** Create a library with two active factors — one validated 10 days ago, one validated 2 days ago — and call `select_revalidation_candidates(days=7, status="active")`.

**Steps:**
1. Create temp library with known `last_validated` timestamps
2. Call `manager.select_revalidation_candidates(days=7, status="active")`
3. Check returned factor IDs

**Expected:** Factor validated 10 days ago is included; factor validated 2 days ago is excluded. Total count = 1.

**Verification:**
```python
from datetime import datetime, timedelta
now = datetime(2026, 3, 24)
# factor_validated_10d_ago = (now - timedelta(days=10)).isoformat()
# factor_validated_2d_ago = (now - timedelta(days=2)).isoformat()
candidates = manager.select_revalidation_candidates(days=7, status="active")
assert len(candidates) == 1
assert candidates[0]["factor_id"] == "factor_validated_10d_ago"
```

---

### 3. status filter AND-composes with days filter

**Setup:** Library with one active factor (10d old) and one stale factor (60d old).

**Steps:**
1. Call `select_revalidation_candidates(days=7, status="active")`
2. Call `select_revalidation_candidates(days=7, status="stale")`

**Expected:** First call returns only the active factor. Second call returns only the stale factor. Neither returns both.

---

### 4. factor_ids filter returns only specified factors

**Steps:**
1. Call `select_revalidation_candidates(days=7, factor_ids=["factor_001"])`
2. Check that only factor_001 is in the result

**Expected:** `len(candidates) == 1`, `candidates[0]["factor_id"] == "factor_001"`

---

### 5. None last_validated is always included (bypasses days filter)

**Setup:** A factor with `last_validated=None`.

**Steps:**
1. Call `select_revalidation_candidates(days=999)` — a very large threshold
2. Check which factors are returned

**Expected:** The factor with `last_validated=None` is included even though it is not "overdue by 999 days" (it has no date at all). This is the current behavior and is intentional.

**Note for tester:** This is a design choice — a factor with unknown validation history should be considered for revalidation.

---

### 6. apply_validation_result() updates last_validated timestamp

**Setup:** A factor entry with known `last_validated`.

**Steps:**
1. Load a factor with `last_validated = "2025-01-01T00:00:00"`
2. Call `manager.apply_validation_result(entry, validation_result, persist=False)`
3. Check `result["evaluation"]["last_validated"]`

**Expected:** `last_validated` is updated to current time (ISO 8601, year 2026).

---

### 7. get_audit_trail() records apply_validation_result events

**Steps:**
1. Call `apply_validation_result()` with `persist=True`
2. Call `manager.get_audit_trail(trigger="apply_validation_result")`
3. Check the last entry

**Expected:** Latest audit entry has `trigger="apply_validation_result"`, `old_status` and `new_status` populated.

---

## Edge Cases

### Edge Case 1: Malformed last_validated string

**Setup:** A factor with `"last_validated": "not-a-date"`.

**Expected:** The factor is treated as overdue (ValueError caught, defaults to `now - timedelta(days=days+1)` making it appear as overdue). Included in candidate list.

### Edge Case 2: Empty library

**Steps:** Call `select_revalidation_candidates(days=7)` on a brand-new empty library.

**Expected:** Returns empty list `[]`, no errors.

### Edge Case 3: No days filter (days=None)

**Steps:** Call `select_revalidation_candidates(days=None)` — no time-based filtering.

**Expected:** All factors in the library are returned (only filtered by `status` and `factor_ids` if provided).

### Edge Case 4: Status filter with no matches

**Steps:** Call `select_revalidation_candidates(days=7, status="archived")` — no archived factors exist.

**Expected:** Returns empty list `[]`.

---

## Failure Signals

- `AttributeError: 'NoneType' object has no attribute 'isoformat'` → `last_validated` initialization not applied
- `ValueError: Invalid isoformat string` → test data has non-ISO timestamp
- `pytest` exit code non-zero → regression in filtering logic
- `len(candidates) == 0` for `days=None` on a non-empty library → method broken

---

## Not Proven By This UAT

- **Live runtime integration** — the full revalidation pipeline (scheduling → backtest → apply_validation_result → schedule again) is not end-to-end tested here. S08 covers this.
- **Performance at scale** — behavior on a library with 10,000+ factors is not tested.
- **Concurrent access** — locking behavior during concurrent `apply_validation_result()` calls.

---

## Notes for Tester

1. All tests are automated via `pytest tests/test_revalidation_candidates.py`. Run the full suite before declaring S02 done.
2. The `None` bypass behavior (Edge Case above) is intentional and documented — do not treat it as a bug.
3. Timestamps are stored as ISO 8601 strings, not datetime objects. If comparing, always parse with `datetime.fromisoformat()` first.
4. `persist=False` is used in integration tests to avoid writing to disk during test execution.
