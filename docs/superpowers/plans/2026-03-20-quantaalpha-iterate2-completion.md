# QuantaAlpha Iterate2 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete iterate 2.1 through 2.5 against the planned acceptance criteria for revalidation semantics, failed-factor retry filtering, quality gating, scheduler summary and audit behavior, and factor-library write protection.

**Architecture:** Keep the current module boundaries and repair the missing runtime wiring instead of introducing a parallel implementation path. The main changes tighten three integration seams: `revalidate` consumes real backtest results and exposes caller-visible failure semantics, `AlphaAgentLoop` consumes the failed-factor set across rounds, and `FactorLibraryManager` becomes the source of truth for summary, audit, and transactional merge-save behavior.

**Tech Stack:** Python, unittest/pytest, shell script, JSON file persistence

---

### Task 1: Revalidate Semantics

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/cli.py`
- Modify: `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`
- Modify: `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- Test: `third_party/quantaalpha/tests/test_revalidate_cli.py`

- [ ] Write a failing test for `mode=status_refresh`, `used_existing_results`, and non-polluting real-backtest failure handling.
- [ ] Run the focused test to verify the current implementation fails for the expected reason.
- [ ] Implement minimal code so default revalidate is explicit status refresh and real backtest consumes real runner output.
- [ ] Add CLI entry failure semantics without breaking the Python return contract.
- [ ] Re-run the focused test group and keep the scope green.

### Task 2: Failed-Factor Retry Wiring

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- Modify: `third_party/quantaalpha/quantaalpha/factors/failure_tracker.py`
- Test: `third_party/quantaalpha/tests/test_debug_failure_filter.py`

- [ ] Write a failing test that proves the second round only sends failed factors into high-cost stages.
- [ ] Run the focused test to verify the failure is in runtime wiring, not test setup.
- [ ] Implement round start/finalize behavior and filter the next-round working set to failed factors only.
- [ ] Re-run the focused failure-filter tests.

### Task 3: Quality Gate and Status Thresholds

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
- Modify: `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
- Test: `third_party/quantaalpha/tests/test_quality_gate.py`
- Test: `third_party/quantaalpha/tests/test_status_transition.py`

- [ ] Write a failing test for data-quality bad samples and planned threshold defaults.
- [ ] Run the focused test to verify the current gate allows bad samples or exposes wrong thresholds.
- [ ] Implement minimal bad-sample checks and align default status thresholds with the plan.
- [ ] Re-run the focused gate and status tests.

### Task 4: Summary, Audit, and Scheduler Script

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/factors/library.py`
- Modify: `third_party/quantaalpha/quantaalpha/cli.py`
- Modify: `third_party/quantaalpha/scripts/continuous_mine.sh`
- Test: `third_party/quantaalpha/tests/test_scheduler_summary.py`

- [ ] Write a failing test for persisted audit entries and summary fields required by the plan.
- [ ] Run the focused tests to verify the current implementation only reconstructs views from factor metadata.
- [ ] Implement persisted audit entries, summary fields, and script path/exit semantics.
- [ ] Re-run the focused summary tests and a script smoke check.

### Task 5: Merge-Save Write Protection

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/factors/library.py`
- Test: `third_party/quantaalpha/tests/test_factor_library_locking.py`

- [ ] Write or reuse a failing concurrency test that demonstrates lost updates with multiple managers.
- [ ] Run the focused test to confirm the lost-update failure.
- [ ] Implement lock-scoped reload-and-merge atomic saving.
- [ ] Re-run the focused locking tests.

### Task 6: Verification

**Files:**
- Test: `third_party/quantaalpha/tests/test_revalidate_cli.py`
- Test: `third_party/quantaalpha/tests/test_debug_failure_filter.py`
- Test: `third_party/quantaalpha/tests/test_status_transition.py`
- Test: `third_party/quantaalpha/tests/test_quality_gate.py`
- Test: `third_party/quantaalpha/tests/test_scheduler_summary.py`
- Test: `third_party/quantaalpha/tests/test_factor_library_locking.py`

- [ ] Run the focused verification commands for each touched area.
- [ ] Record which acceptance points now have direct evidence and which still require broader test coverage by the separate test agent.
