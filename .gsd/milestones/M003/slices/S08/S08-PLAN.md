# S08: ResourceManager 资源管理 (S7/D018) — Slice Plan

**Triggering Decision:** D018 — ResourceManager 实现 Token/磁盘/内存资源边界约束

**Goal:** Implement ResourceManager for 24H autonomous operation with D018 constraints:
1. Daily Token Budget hard cap (default 5M tokens) with circuit-breaking
2. Disk Space Monitoring with WARNING/CRITICAL thresholds (<5GB warning, <2GB stop)
3. result.h5 Auto-cleanup (30-day retention)
4. Factor Library Entry Count Limits

**Demo:** A Python script can import `ResourceManager`, call `check_and_enforce()`, and observe:
- Token budget tracking with daily reset
- Disk space status (ok/warning/critical)
- Cleanup of result.h5 files older than 30 days
- Factor library entry count

## Must-Haves

- `resource_manager.py:ResourceManager` class with `ResourceConfig`, `ResourceStatus` dataclasses
- Daily token budget enforcement with automatic reset at midnight UTC
- Disk space monitoring using `shutil.disk_usage()` with configurable thresholds
- result.h5 cleanup function with age-based filtering
- Factor library entry count enforcement in `library.py`
- Integration with `loop.py` run() for pre-iteration resource checks
- `experiment.yaml` configuration section for all D018 parameters
- 20+ unit tests covering all enforcement mechanisms
- **Runtime inspection surfaces:** `get_status()` returns structured `ResourceStatus` snapshot
- **Failure visibility:** When budget exceeded or disk critical, `check_and_enforce()` returns `(False, reason)` with logged WARNING

## Proof Level

- **Contract verification:** Python syntax validation, YAML parse validation
- **Unit verification:** 20+ pytest tests covering all ResourceManager methods
- **Integration verification:** ResourceManager integrates with loop.py run() and library.py
- **Real runtime required:** No (component-level verification sufficient for slice)
- **Human/UAT required:** No (code review via PR optional)

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py`
- `python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v`
- `python -c "import yaml; yaml.safe_load(open('third_party/quantaalpha/configs/experiment.yaml'))"`
- `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/library.py`
- **Failure-path verification:** Run `ResourceManager().get_status()` and verify `ResourceStatus` dataclass fields:
  ```bash
  python -c "
  from quantaalpha.pipeline.resource_manager import ResourceManager
  mgr = ResourceManager()
  status = mgr.get_status()
  print(f'tokens_today={status.total_tokens_today}, disk_gb={status.disk_space_gb}, disk_status={status.disk_space_status}, entries={status.factor_library_entries}, within_budget={status.within_budget}')
  "
  ```

## Observability / Diagnostics

- **Runtime signals:**
  - `ResourceManager.get_status()` returns structured `ResourceStatus` dataclass
  - `ResourceManager.check_and_enforce()` returns `(allowed: bool, reason: str)` for budget enforcement
  - `ResourceManager.get_token_usage_report()` surfaces ProviderPool token data
  - `ResourceManager.get_disk_space_report()` surfaces disk space per path
- **Inspection surfaces:**
  - `python -c "from quantaalpha.pipeline.resource_manager import ResourceManager; print(ResourceManager().get_status())"`
  - `~/.cache/quantaalpha/daily_tokens.json` for daily token persistence
- **Failure visibility:**
  - Budget exceeded: WARNING log + `check_and_enforce()` returns `(False, "Daily token budget exceeded: {X} / {Y}")`
  - Disk critical: WARNING log + `disk_space_status="critical"` in status
  - ProviderPool unavailable: graceful fallback, status shows `within_budget=None`
- **Redaction constraints:** No secrets in status output; API keys stay in environment

## Integration Closure

- **Upstream surfaces consumed:**
  - `quantaalpha.llm.provider_pool:provider_pool` singleton for token tracking
  - `quantaalpha.factors.library:FactorLibraryManager` for entry count
  - `configs/experiment.yaml` for configuration
- **New wiring introduced:**
  - `loop.py:AlphaAgentLoop.run()` calls `resource_manager.check_and_enforce()` at iteration start
  - `library.py:add_factors_from_experiment()` checks `factor_library_max_entries`
- **What remains before milestone usable end-to-end:**
  - S09 (M001 lessons) and S10 (ADR-003 orchestration) build on ResourceManager
  - 72-hour UAT in M003 final verification

## Tasks

- [x] **T01: Create ResourceManager core class** `est:2h`
  - Why: Core implementation is the slice foundation; all other tasks depend on it
  - Files: `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py`
  - Do: Implement ResourceConfig, ResourceStatus dataclasses, ResourceManager class with all D018 constraints
  - Verify: `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py`
  - Done when: ResourceManager class exists with check_and_enforce(), get_status(), cleanup_old_results() methods

- [x] **T02: Add experiment.yaml config and factor library integration** `est:1h`
  - Why: Configuration must be in place before ResourceManager can be fully tested
  - Files: `third_party/quantaalpha/configs/experiment.yaml`, `third_party/quantaalpha/quantaalpha/factors/library.py`
  - Do: Add resource_management section to experiment.yaml; add entry count check to library.py
  - Verify: YAML parse + py_compile validation
  - Done when: experiment.yaml has resource_management section; library.py checks entry limits

- [x] **T03: Integrate ResourceManager with loop.py** `est:1h`
  - Why: loop.py run() is the entry point for 24H autonomous operation; resource checks must gate iterations
  - Files: `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
  - Do: Add resource_mgr initialization and check_and_enforce() call in run()
  - Verify: `python -m py_compile third_party/quantaalpha/quantaalpha/pipeline/loop.py`
  - Done when: loop.py imports and calls ResourceManager.check_and_enforce() before each iteration

- [x] **T04: Create unit tests and final verification** `est:2h`
  - Why: 20+ tests ensure all enforcement mechanisms work correctly
  - Files: `third_party/quantaalpha/tests/test_resource_manager.py`
  - Do: Implement test_resource_manager.py with all test classes following S04 patterns
  - Verify: `python -m pytest third_party/quantaalpha/tests/test_resource_manager.py -v`
  - Done when: All 20+ tests pass

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/pipeline/resource_manager.py` — Create
- `third_party/quantaalpha/tests/test_resource_manager.py` — Create
- `third_party/quantaalpha/configs/experiment.yaml` — Modify (add section)
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py` — Modify (add integration)
- `third_party/quantaalpha/quantaalpha/factors/library.py` — Modify (add entry limit)

---
estimated_steps: 18
estimated_files: 5
skills_used:
  - test
  - lint
  - systematic-debugging
