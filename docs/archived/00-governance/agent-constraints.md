# Agent Constraints

## Purpose

This file defines the operating boundary for AI agents working in this repository.

Use it together with:
- `docs/00-governance/agent.md`
- `docs/00-governance/rules.md`

## Default Permission Model

Allowed without special approval:
- read repository files needed for the task
- edit files inside the explicit task scope
- create or update change docs required by the workflow
- run local validation commands
- update metadata and links required by the task

Require explicit human approval:
- modifying system configuration or runtime environments
- changing storage paths or data write semantics
- changing repository-wide governance rules outside the assigned task
- bulk moving or deleting documentation files
- editing protected third-party paths unless the task explicitly requires it

## Hard Prohibitions

- do not modify files outside the explicit task scope
- do not create new formal docs unless the task or workflow requires them
- do not treat `docs/drafts/` as current truth
- do not create new status subdirectories under `docs/03-changes/`
- do not move files just to reflect a status update
- do not manually edit generated files unless the workflow explicitly requires it
- do not silently rewrite naming conventions or metadata schema
- do not claim completion without running the required validation
- do not edit `third_party/vnpy/` or `third_party/glue/` unless explicitly required

## Mandatory Pre-Edit Check

Before editing, identify:
1. target module
2. target files
3. truth docs consulted
4. validation plan
5. whether human review is required

## Completion Gate

Do not report completion unless you can state:
1. what changed
2. which files changed
3. which truth docs were consulted
4. which validation was run
5. which risks or review requirements remain
