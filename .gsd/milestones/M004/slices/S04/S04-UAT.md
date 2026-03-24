---
id: S04
parent: M004
milestone: M004
---

# S04: 数据能力注册表扩展 — UAT

**UAT mode:** artifact-driven (unit tests + py_compile — no live runtime required)
**Why this mode is sufficient:** This slice adds structured fields to a data registry; the contract is verifiable via deterministic unit tests and syntax checking. No live data pipeline or LLM is needed.

## Preconditions

- Python 3.12+ with polars installed (`pip install polars`) for Parquet inference tests
- `quantaalpha` module importable (via symlink to `third_party/quantaalpha`)

## Smoke Test

```bash
python -c "from quantaalpha.factors.data_capability import render_data_capabilities; print(render_data_capabilities())"
```
**Expected:** Output contains `available_from=` and `join_mode=` for each capability entry.

---

## Test Cases

### 1. available_from field normalization

1. Run: `pytest quantaalpha/tests/test_data_capability_extensions.py::TestAvailableFromField -v`
2. **Expected:** 3 passed — valid date string preserved, missing → None, explicit None → None

### 2. join_mode inferred from freq

1. Run: `pytest quantaalpha/tests/test_data_capability_extensions.py::TestJoinModeInference -v`
2. **Expected:** 6 passed
   - daily/weekly → same_day
   - quarterly/monthly/annual → forward_fill
   - explicit join_mode overrides freq inference

### 3. Rendered output includes both new fields

1. Run: `pytest quantaalpha/tests/test_data_capability_extensions.py::TestRenderDataCapabilities -v`
2. **Expected:** 5 passed — `available_from=` and `join_mode=` appear in rendered text

### 4. Existing registry entries have correct values

1. Run: `pytest quantaalpha/tests/test_data_capability_extensions.py::TestDataCapabilitiesRegistry -v`
2. **Expected:** 4 passed
   - price_volume: available_from=2010-01-01, join_mode=same_day
   - financial: available_from=2008-01-01, join_mode=forward_fill

### 5. auto_discover_capabilities is defensive on bad inputs

1. Run: `pytest quantaalpha/tests/test_data_capability_extensions.py::TestAutoDiscoverCapabilities -v`
2. **Expected:** 4 passed — returns existing registry for nonexistent path, preserves hardcoded dates, JSON serializable

### 6. Parquet date inference is defensive

1. Run: `pytest quantaalpha/tests/test_data_capability_extensions.py::TestInferAvailableFrom -v`
2. **Expected:** 2 passed — returns None for nonexistent file and corrupted file

### 7. Syntax check

1. Run: `python -m py_compile quantaalpha/factors/data_capability.py && python -m py_compile quantaalpha/tests/test_data_capability_extensions.py`
2. **Expected:** Both exit 0, no output

---

## Edge Cases

### Unknown available_from shows as "(unknown)"

- Pass a spec without `available_from` to `render_data_capabilities()`.
- **Expected:** Output contains `available_from=(unknown)` for that entry.

### Corrupted parquet file

- Create a `.parquet` file containing plain text, pass to `infer_available_from_from_parquet()`.
- **Expected:** Returns None, does not raise.

### Unknown freq value

- Pass `freq="minutely"` (not in `_FREQ_TO_JOIN_MODE`).
- **Expected:** Falls back to `DEFAULT_CAPABILITY_SPEC["join_mode"]` = `same_day`.

---

## Failure Signals

- `pytest` exits non-zero → test failure in one of the 6 test classes
- `AttributeError` on import → module-level syntax error or missing dependency
- Rendered output missing `available_from=` or `join_mode=` → `render_data_capabilities()` not updated

---

## Not Proven By This UAT

- Live Parquet file discovery (polars available at runtime with real data files)
- End-to-end: LLM actually receiving and using the available_from/join_mode in prompts
- Integration with M003 S01's data pipeline startup flow

---

## Notes for Tester

- Tests use `pytest` fixtures only within individual test classes; no cross-test state.
- All tests are fast (< 0.2s total) — no network calls or file I/O beyond temp files.
- The `polars` import is inside `infer_available_from_from_parquet()` — if polars is not installed, only that one function returns None and tests still pass.
