# Parallel Agent Development Documentation System (PADDS)

## 1. Overview

This document outlines the necessary changes to the `docs/` system to support a **Parallel Agent Development Workflow**.

**Goal:** Enable a Master Coding Agent to split a complex requirement into 4 independent sub-tasks (shards), execute them in parallel via sub-agents, test them in parallel, debug them in parallel, and finally integrate them.

**Key Constraint:** To make parallel development safe, **Shared State** must be minimized, and **Interfaces** must be frozen before coding starts.

## 2. Directory Structure Changes

The current linear `docs/03-changes` structure is insufficient. We need a hierarchical task structure.

### Proposed Structure

```text
docs/tasks/
  <task-id>/                  # Unique ID for the high-level feature (e.g., 2026-03-18-feature-x)
    00-master-plan.md         # The original requirement + High-level architecture + Interface Definitions
    01-shard-ui.md            # Spec for Subagent 1 (UI)
    02-shard-backend.md       # Spec for Subagent 2 (Backend)
    03-shard-db.md            # Spec for Subagent 3 (DB)
    04-shard-cli.md           # Spec for Subagent 4 (CLI)
    05-integration-plan.md    # Spec for the final integration step
```

**Status Tracking:**
Instead of moving files between folders, use a header in `00-master-plan.md`:
```markdown
Status: Sharding | Implementation | Testing | Debugging | Integration | Complete
```

## 3. Workflow Phases & Documentation Role

### Phase 1: Partitioning (The Architect Agent)

**Role:** The Main Agent reads the user request and:
1.  Creates `docs/tasks/<task-id>/`.
2.  Writes `00-master-plan.md`:
    *   Defines the **Strict Interfaces** (e.g., Python `Protocol`, Data Classes, JSON Schemas) that all shards must adhere to.
    *   **Crucial Rule:** These interfaces are the "Contract". They cannot be changed by sub-agents.
3.  Generates `01-shard-*.md` to `04-shard-*.md`.
    *   Each shard doc MUST explicitly list:
        *   **Allowed Write Paths:** (e.g., `src/ui/`, `tests/ui/`) - Subagents MUST NOT touch files outside this list.
        *   **Read-Only Inputs:** The Interface Definitions from the Master Plan.

### Phase 2: Parallel Implementation (4 Coding Subagents)

**Role:** 4 Subagents run in parallel.
1.  **Input:** Each reads *only* its assigned `shard-*.md` and `00-master-plan.md` (read-only).
2.  **Action:**
    *   Writes code in **Allowed Write Paths**.
    *   Writes unit tests in `tests/<shard-name>/`.
    *   **Mocking:** Mocks the *other* 3 shards based on the Interface Definitions in `00-master-plan.md`.
3.  **Output:** Code files and Test files.

### Phase 3: Parallel Testing (4 Testing Subagents)

**Role:** 4 Subagents run in parallel.
1.  **Input:** `shard-*.md` and the implementation.
2.  **Action:**
    *   Runs the unit tests created in Phase 2.
    *   Verifies that the code adheres to the **Interface Contract**.
3.  **Output:** A test report (e.g., `shard-01-report.json`).

### Phase 4: Parallel Debugging (4 Debugging Subagents)

**Role:** 4 Subagents run in parallel (triggered only for failed shards).
1.  **Input:** `shard-*.md`, the implementation, and the Test Report.
2.  **Action:**
    *   Fixes the code in **Allowed Write Paths** to pass the tests.
    *   **Constraint:** CANNOT change the Interface Definitions.

### Phase 5: Integration (The Wrap-Up Agent)

**Role:** The Main Agent returns.
1.  **Input:** All 4 completed shards + `05-integration-plan.md`.
2.  **Action:**
    *   Writes the "Glue Code" (wiring the shards together).
    *   Runs the `Integration Test` (defined in Phase 1).
    *   Verifies end-to-end functionality.
3.  **Output:** Final `Status: Complete` in `00-master-plan.md`.

## 4. Documentation Templates

### Template: `00-master-plan.md`

```markdown
# Master Plan: <Feature Name>

## 1. High-Level Goal
...

## 2. Shared Interfaces (The Contract)
**FROZEN SECTION - DO NOT EDIT**
*   `class User(BaseModel): ...`
*   `def calculate_metrics(data: List[int]) -> float: ...`

## 3. Shard Definitions
*   Shard 1: UI (Files: `src/ui/*`)
*   Shard 2: Backend (Files: `src/backend/*`)
...
```

### Template: `XX-shard-name.md`

```markdown
# Shard Task: <Shard Name>

## 1. Your Objective
Implement the <Shard Name> component.

## 2. Constraints (STRICT)
*   **Write ONLY to:** `src/<shard>/*`, `tests/<shard>/*`
*   **Read ONLY from:** `src/common/interfaces.py` (The Contract)
*   **DO NOT modify:** `src/common/interfaces.py`

## 3. Expected Output
*   A functioning module that passes `tests/<shard>/test_*.py`.
*   Adherence to the Interface defined in `00-master-plan.md`.
```

## 5. Summary of Required Changes to `docs/`

1.  **Create `docs/tasks/`** directory.
2.  **Deprecate** the complex `docs/03-changes/{draft,planned,...}` structure for this workflow.
3.  **Update `docs/00-governance/agent.md`** to recognize this "Master/Shard" pattern.
