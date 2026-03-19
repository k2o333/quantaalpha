# Data Capability Registry Reintegration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reintegrate the data capability registry into the quantaalpha factor-mining scenario with a controlled config gate, fallback behavior, and regression tests.

**Architecture:** Keep `data_capability.py` as the single source for normalized registry metadata and rendering. Extend `experiment.py` to append a compact registry description onto the existing `source_data` text only when enabled by config, while swallowing registry/render errors and falling back to the original source-data intro.

**Tech Stack:** Python, pytest, YAML config loading, unittest-style isolated module stubs

---

### Task 1: Lock Registry Behavior

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/factors/data_capability.py`
- Test: `third_party/quantaalpha/tests/test_data_capability_registry.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run `test_data_capability_registry.py` to verify the new assertions fail**
- [ ] **Step 3: Implement normalization helpers and stable rendering**
- [ ] **Step 4: Re-run the targeted registry tests to verify they pass**

### Task 2: Reconnect Scenario Injection

**Files:**
- Modify: `third_party/quantaalpha/quantaalpha/factors/experiment.py`
- Modify: `third_party/quantaalpha/configs/experiment.yaml`
- Test: `third_party/quantaalpha/tests/test_data_capability_registry.py`

- [ ] **Step 1: Write the failing scenario injection and fallback tests**
- [ ] **Step 2: Run the targeted scenario tests to verify the expected failures**
- [ ] **Step 3: Implement config-gated source-data merging with fallback**
- [ ] **Step 4: Re-run the targeted scenario tests to verify they pass**

### Task 3: Verify End-to-End Scope

**Files:**
- Test: `third_party/quantaalpha/tests/test_data_capability_registry.py`

- [ ] **Step 1: Run the full targeted test file with `/root/miniforge3/envs/mining/bin/python -m pytest`**
- [ ] **Step 2: Run a compile or import sanity check if needed**
- [ ] **Step 3: Summarize exact verification evidence and any remaining risk**
