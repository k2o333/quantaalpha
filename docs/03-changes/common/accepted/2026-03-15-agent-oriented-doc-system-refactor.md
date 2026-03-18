Status: accepted
Owner: AI Assistant
Created: 2026-03-15
Updated: 2026-03-16
Outcome: accepted
Related-to: `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`

# Agent-Oriented Documentation System Refactor

## Background

The repository had substantial documentation, but it was not optimized for agent routing:
- no clear repository entrypoint
- `rules.md` mixed navigation, technical details, and hard constraints
- `doc-rules.md` was too long for task-oriented document cleanup
- `docs/03-changes/` used mixed directory styles, making change-doc placement less predictable

## Goal

Restructure the documentation system so agents can:
- enter through one navigation doc
- find hard rules quickly
- route document-cleanup tasks by workflow
- follow a default documentation promotion path:
  `draft -> change doc -> module doc / ADR / playbook / reference doc`

## Non-goals

- full migration of all legacy change docs in one pass
- rewriting all historical documentation
- introducing new agent-specific directories beyond the minimal entry layer

## Acceptance Criteria

1. The repo has a clear agent entrypoint.
2. Rules are separated from navigation.
3. Documentation cleanup work can route through a short doc-rules entry.
4. The target lifecycle-based `docs/03-changes/<module>/<status>/YYYY-MM-DD-topic.md` structure is documented.
5. Module docs expose quick-start sections for routing and validation.
6. Module change docs clearly distinguish `draft`, `planned`, and active/completed task records.

## Implementation

### Completed

- added root `AGENTS.md` pointing to the repository entry doc
- created `docs/00-governance/agent.md`
- refactored `docs/00-governance/rules.md` into a concise hard-rules document
- created `docs/01-overview/system-overview.md`
- replaced the old long `doc-rules.md` with a short routing entry
- created `docs/00-governance/doc-workflows.md`
- created `docs/00-governance/doc-standards.md`
- added quick-routing sections to:
  - `docs/02-modules/app4.md`
  - `docs/02-modules/quantaalpha.md`
  - `docs/02-modules/backtest.md`
- created `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
- aligned governance docs with the target module-based change-doc structure
- added `draft/` and `planned/` subdirectories under module change-doc directories
- migrated legacy year-based change docs from `docs/03-changes/2026/` into:
  - `docs/03-changes/app4/`
  - `docs/03-changes/quantaalpha/`
- removed the now-empty legacy `docs/03-changes/2026/` directory
- promoted quantaalpha iterate2 task docs from `docs/drafts/.../iterate2/` into `docs/03-changes/quantaalpha/planned/`
- flattened the legacy nested directory `docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/` into `docs/03-changes/quantaalpha/`

### Not yet done

 - add any missing governance docs referenced by the new entry layer if they become necessary

## Validation

Manual validation completed:
- checked the new entry flow: `AGENTS.md -> agent.md -> rules.md`
- checked the documentation routing flow: `agent.md -> doc-rules.md -> doc-workflows.md / doc-standards.md`
- checked that module docs now expose quick routing and validation sections
- checked that ADR-002 and doc standards agree on the target change-doc structure
- checked that legacy files from `docs/03-changes/2026/` now resolve under module-based directories
- checked that not-yet-started quantaalpha iterate2 tasks now live under `docs/03-changes/quantaalpha/planned/`
- checked that the old nested quantaalpha checklist directory was flattened and its internal links updated

## Risks

- some historical status headers and older change-doc conventions may still vary across legacy documents
- future edits could drift if new docs ignore the module-based path and status subdirectories

## Next Step

Apply the new module-based `draft/` and `planned/` paths to all newly created change docs, and keep older quantaalpha root-level task records as the active/completed layer.
