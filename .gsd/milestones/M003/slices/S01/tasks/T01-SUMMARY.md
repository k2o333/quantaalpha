---
id: T01
parent: S01
milestone: M003
provides:
  - auto_discover_capabilities() public function; JSON cache at ~/.cache/quantaalpha/data_capability_registry.json; _scan_dir_schema(), _infer_freq_and_lag(), _generate_factor_hints() helpers
key_files:
  - third_party/quantaalpha/quantaalpha/factors/data_capability.py
  - scripts/verify_s01_discovery.py
key_decisions:
  - Package root is third_party/quantaalpha (not third_party/); sys.path must point there for direct imports
patterns_established:
  - Polars scan wrapped in try/except so module still loads when polars is absent
observability_surfaces:
  - INFO/WARN logs via logging.getLogger; JSON cache at ~/.cache/quantaalpha/data_capability_registry.json
duration: ~10 min
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T01: 实现 auto_discover_capabilities() 动态扫描函数

**Added `auto_discover_capabilities()` to `data_capability.py` and created `scripts/verify_s01_discovery.py`.**

## What Happened

Read the existing `data_capability.py` which contained only a 2-source hardcoded `DATA_CAPABILITIES` dict and the existing `render_data_capabilities()` / `get_data_capabilities()` functions. Added a polars-optional import block, then implemented four new helpers (`_scan_dir_schema`, `_infer_freq_and_lag`, `_generate_factor_hints`, `_cache_is_valid`) and the public `auto_discover_capabilities()` function. The function scans every subdirectory of `/home/quan/testdata/aspipe_v4/data`, reads the first Parquet file's schema with `polars.scan_parquet()`, infers frequency/lag from the presence of `ann_date`, excludes metadata fields, maps directory names to domain factor hints, and writes a 24-hour JSON cache to `~/.cache/quantaalpha/`. Existing functions were not modified. Created the standalone verification script at `scripts/verify_s01_discovery.py` using the correct package root (`third_party/quantaalpha`). All existing unit tests still pass.

## Verification

All 7 checks in `scripts/verify_s01_discovery.py` passed: ≥ 20 sources (got 24), all entries have required keys, metadata fields excluded, non-empty rendered text, JSON cache written. All 6 existing pytest tests pass. Both `py_compile` checks (data_capability.py and proposal.py) return zero errors.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py` | 0 | ✅ pass | <1s |
| 2 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` | 0 | ✅ pass | <1s |
| 3 | `python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v` | 0 | ✅ pass (6/6) | 0.17s |
| 4 | `python scripts/verify_s01_discovery.py` | 0 | ✅ pass (24 sources, cache written) | ~5s |

## Diagnostics

- Inspect cache: `cat ~/.cache/quantaalpha/data_capability_registry.json`
- Re-scan (bypass cache): `python -c "from quantaalpha.factors.data_capability import auto_discover_capabilities; print(auto_discover_capabilities(use_cache=False))"`
- Logs appear on stdout/stderr when `logging` is configured; search for `auto_discover_capabilities` log lines.

## Deviations

None — implemented exactly as specified in T01-PLAN.md.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — added polars import, `DEFAULT_DATA_DIR`, `_METADATA_FIELDS`, `_CACHE_FILE`, `_log`, `_scan_dir_schema()`, `_infer_freq_and_lag()`, `_FACTOR_HINT_MAP`, `_generate_factor_hints()`, `_cache_is_valid()`, `auto_discover_capabilities()`, and updated `__all__`
- `scripts/verify_s01_discovery.py` — new standalone verification script
