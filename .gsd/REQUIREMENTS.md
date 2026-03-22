# Requirements

This file is the explicit capability and coverage contract for the project.

Use it to track what is actively in scope, what has been validated by completed work, what is intentionally deferred, and what is explicitly out of scope.

Guidelines:
- Keep requirements capability-oriented, not a giant feature wishlist.
- Requirements should be atomic, testable, and stated in plain language.
- Every **Active** requirement should be mapped to a slice, deferred, blocked with reason, or moved out of scope.
- Each requirement should have one accountable primary owner and may have supporting slices.
- Research may suggest requirements, but research does not silently make them binding.
- Validation means the requirement was actually proven by completed work and verification, not just discussed.

## Active

(none yet — to be defined with first milestone)

## Validated

(none yet)

## Deferred

(none yet)

## Out of Scope

(none yet)

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|

## Coverage Summary

- Active requirements: 0
- Mapped to slices: 0
- Validated: 0
- Unmapped active requirements: 0

---

## Project Context (from existing docs/)

**Inferred from `docs/02-modules/*.md` and `docs/03-changes/`:**

### Module: app4
- Data pipeline for TuShare Pro
- 43 interfaces, 7 pagination modes
- Config-driven YAML approach

### Module: quantaalpha
- Factor mining and evaluation
- CLI-driven workflow
- LLM-assisted factor generation

### Module: backtest
- Alpha101 factor validation
- Polars-based computation
- Performance metrics and analysis

### Documentation Inventory
- 197 docs in `docs/`
- 77 change documents
- 3 ADRs recorded
- 4 completed tasks
- 12 active tasks

**Note**: Requirements will be formally tracked here as milestones are defined. Historical requirements exist in `docs/03-changes/<module>/` files.
