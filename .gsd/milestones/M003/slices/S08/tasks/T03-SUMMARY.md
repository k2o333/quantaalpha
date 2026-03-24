---
id: T03
parent: S08
milestone: M003
provides:
  - ResourceManager integration in AlphaAgentLoop.run() with D018 budget enforcement
key_files:
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
patterns_established:
  - Lazy resource manager initialization pattern matching S06 checkpoint pattern
observability_surfaces:
  - WARNING log when resource budget exceeded (loop breaks gracefully)
  - ResourceManager.get_status() returns structured ResourceStatus dataclass
  - check_and_enforce() returns (allowed, reason) tuple for budget enforcement
duration: ~5 minutes
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: Integrate ResourceManager with loop.py

**Integrated ResourceManager into AlphaAgentLoop.run() with D018 budget enforcement and graceful loop termination.**

## What Happened

Added ResourceManager integration to `AlphaAgentLoop` following the checkpoint lazy-import pattern from S06. The `_get_resource_manager()` method lazily imports the module-level `resource_manager` singleton, and the `run()` method calls `check_and_enforce()` at the start of each iteration. When resources are exceeded, a WARNING is logged and the loop breaks gracefully instead of crashing.

## Verification

All slice verification checks passed:
- `python -m py_compile` validated syntax for loop.py, resource_manager.py, and library.py
- `pytest tests/test_resource_manager.py -v` — 33/33 tests passed
- YAML config loads correctly
- Failure-path verification confirmed `get_status()` returns expected `ResourceStatus` fields

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile quantaalpha/pipeline/loop.py` | 0 | ✅ pass | <1s |
| 2 | `python -m pytest tests/test_resource_manager.py -v` | 0 | ✅ pass | 0.59s |
| 3 | `python -c "import yaml; yaml.safe_load(open('configs/experiment.yaml'))"` | 0 | ✅ pass | <1s |
| 4 | `python -m py_compile quantaalpha/pipeline/resource_manager.py` | 0 | ✅ pass | <1s |
| 5 | `python -m py_compile quantaalpha/factors/library.py` | 0 | ✅ pass | <1s |
| 6 | `python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; ..."` | 0 | ✅ pass | <1s |

## Diagnostics

**Runtime inspection:**
```bash
# Get current resource status
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_status())"

# Check if operations allowed
python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().check_and_enforce())"
```

**Log signals:**
- WARNING when resource budget exceeded (loop breaks)
- WARNING when disk space critical
- WARNING when factor library entry limit reached

## Deviations

None — implementation matches task plan exactly.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — Added ResourceManager integration:
  - Added `from quantaalpha.pipeline.resource_manager import ResourceManager` import
  - Added `_get_resource_manager()` method with lazy import pattern
  - Modified `run()` to call `check_and_enforce()` before each iteration
  - Loop breaks gracefully with WARNING logs when budget exceeded
