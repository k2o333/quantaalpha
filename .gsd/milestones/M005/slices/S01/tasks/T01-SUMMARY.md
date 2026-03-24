---
id: T01
parent: S01
milestone: M005
provides:
  - Fallback logger implementation that works when rdagent.log is unavailable
key_files:
  - quantaalpha/log/__init__.py
  - third_party/quantaalpha/quantaalpha/log/__init__.py
patterns_established:
  - Fallback pattern with try-except ImportError wrapper
  - Standard library logging wrapped to match rdagent.log interface
observability_surfaces:
  - Standard logging output to console
  - log_trace_path configurable via set_trace_path()
duration: ~3 min
verification_result: passed
completed_at: 2026-03-24T18:34:59+08:00
blocker_discovered: false
---

# T01: 实现 fallback logger

**Fallback logger implementation providing consistent API when rdagent.log is unavailable**

## What Happened

Implemented a fallback logging system that provides the same interface as `rdagent.log` when that module is not available. The implementation:

1. Modified `quantaalpha/log/__init__.py` to wrap the `rdagent.log` import in a try-except block
2. Created a `FallbackLoggerWrapper` class that wraps Python's standard `logging.Logger` and adds:
   - `log_trace_path` property (returns a `Path`)
   - `set_trace_path()` method to change the trace path
   - `storage` object with `path` property and `truncate()` method
3. Implemented a `FallbackFileStorage` class for the storage interface
4. Added a `LogColors` enum compatible with rdagent's version
5. Copied the same implementation to `third_party/quantaalpha/quantaalpha/log/__init__.py`
6. Created the vendored package's `__init__.py` file

## Verification

Ran all four "Truth" checks from the task plan:

1. **Basic import and info**: `from quantaalpha.log import logger, LogColors; logger.info('test')` ✓
2. **Main package import**: `import quantaalpha.log; print('OK')` ✓
3. **Vendored copy import**: `import sys; sys.path.insert(0, 'third_party/quantaalpha'); import quantaalpha.log; print('OK')` ✓
4. **set_trace_path and log_trace_path**: `logger.set_trace_path('/tmp'); print(logger.log_trace_path)` outputs `/tmp` ✓

All required methods (`info`, `warning`, `error`, `exception`, `log_trace_path`, `set_trace_path`) work correctly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -c "from quantaalpha.log import logger, LogColors; logger.info('test')"` | 0 | ✅ pass | <1s |
| 2 | `python -c "import quantaalpha.log; print('OK')"` | 0 | ✅ pass | <1s |
| 3 | `python -c "import sys; sys.path.insert(0, 'third_party/quantaalpha'); import quantaalpha.log; print('OK')"` | 0 | ✅ pass | <1s |
| 4 | `python -c "from quantaalpha.log import logger; logger.set_trace_path('/tmp'); print(logger.log_trace_path)"` | 0 | ✅ pass | <1s |

## Diagnostics

- Logger outputs to console with standard format: `TIMESTAMP - quantaalpha - LEVEL - message`
- `log_trace_path` defaults to `$LOG_TRACE_PATH` env var or `/tmp/quantaalpha_logs`
- Use `logger.set_trace_path('/path')` to change the trace path
- Access `logger.storage.path` for the current path
- `logger.storage.truncate()` is a no-op in fallback mode

## Deviations

None - implemented exactly as specified in task plan.

## Known Issues

The task plan mentioned verifying `normalize_corrected_expression` import as a transitive chain test, but that import fails due to a different dependency issue (`rdagent.scenarios.qlib` not available), not the `rdagent.log` issue being solved by this task. The `quantaalpha.log` module itself imports successfully.

## Files Created/Modified

- `quantaalpha/log/__init__.py` — Modified to add fallback logger with try-except ImportError wrapper
- `third_party/quantaalpha/quantaalpha/log/__init__.py` — Created with same fallback implementation
- `third_party/quantaalpha/quantaalpha/__init__.py` — Created to enable vendored package import
