Status: draft
Owner: Codex
Created: 2026-03-16
Outcome: pending
Related-to: `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
Related-to: `docs/00-governance/agent.md`
Related-to: `docs/00-governance/rules.md`
Related-to: `docs/00-governance/doc-rules.md`
Related-to: `docs/00-governance/doc-standards.md`
Related-to: `docs/00-governance/development-workflow.md`

# Agent Documentation System Follow-up Todo

## Background

The repository already adopted the agent-oriented documentation system defined in ADR-002, but the main navigation and some supporting governance docs still have small alignment gaps.

This draft is intentionally written as an execution checklist for a normal coding agent. Prefer following the concrete instructions here over making broader design changes.

## Goal

Make a small set of governance-doc edits so the repository entry flow matches ADR-002 more closely and the workflow doc stops competing with `rules.md`.

## Non-Goals

- redesign the documentation system from scratch
- rewrite module docs
- migrate large batches of historical change docs
- edit ADR content for this task
- treat this draft as current truth

## Target Scope

Task type: documentation change

Working mode:
- make only small, local governance-doc edits
- do not create new governance files for this task
- prefer editing existing wording over adding new long sections
- when in doubt, delete duplicated wording instead of adding explanatory wording

Target doc families to check first:
- `docs/00-governance/*.md`
- `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
- `docs/03-changes/common/`

Primary target files:
- `docs/00-governance/agent.md`
- `docs/00-governance/development-workflow.md`
- optionally `docs/00-governance/doc-rules.md`

Allowed output files for this task:
- edit `docs/00-governance/agent.md`
- edit `docs/00-governance/development-workflow.md`
- edit `docs/00-governance/doc-rules.md` only if needed
- create one completion report under `docs/drafts/report/`

Do not edit:
- any module doc under `docs/02-modules/`
- any ADR content under `docs/04-decisions/`
- any playbook or reference doc
- code, config, tests, or files outside documentation scope

## Required Read Order

Read these files in this order before editing:
1. `docs/00-governance/agent.md`
2. `docs/00-governance/rules.md`
3. `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
4. `docs/00-governance/doc-rules.md`
5. `docs/00-governance/doc-standards.md`
6. `docs/00-governance/development-workflow.md`

Before editing, write down these four items:
- target files
- exact sections to change
- validation method
- whether human review is required under `rules.md`

## Execution Rules For A Normal Agent

- treat this draft as task guidance, not current truth
- do not claim completion unless each acceptance check below is verified against the final file contents
- keep `agent.md` short; prefer changing table rows over adding long prose
- in `development-workflow.md`, prefer replacing repeated rule lists with short references back to `rules.md`
- do not say a file was changed if it was only reviewed
- if `doc-rules.md` appears acceptable, leave it unchanged and say why in the report
- if you use a subagent or reviewer, require it to check file contents, not your own summary
- do not add a new explanatory subsection to `agent.md` unless this draft explicitly tells you to
- do not mark a duplication check as passed just because a section now contains both a reference to `rules.md` and the old list
- if repeated rule lists remain after editing, report partial completion rather than full completion

## Exact Edit Plan

### File 1: `docs/00-governance/agent.md`

Change only these areas:
- `## Task Routing`
- `## Do Not Assume`

Required edits:
- in `## Task Routing`, replace the vague `docs/03-changes/...` entry with module-plus-status guidance
- in `## Task Routing`, add routes for:
  - `docs/04-decisions/`
  - `docs/05-playbooks/`
  - `docs/06-references/`
- in `## Do Not Assume`, keep the point that module docs define current state
- if you mention `docs/03-changes/` in `## Do Not Assume`, keep it to one short bullet; do not add a long mini-spec there
- do not add a new section such as `### Change docs routing`

Preferred wording shape:
- route by task intent, not by theory
- mention `docs/03-changes/<module>/<status>/`
- avoid listing every module and every lifecycle status unless truly necessary
- keep all change-doc routing guidance inside existing bullets or table cells

Hard acceptance checks:
- `agent.md` includes routing entries for ADRs, playbooks, and references
- `agent.md` no longer uses only `docs/03-changes/...` as the change-doc route
- `agent.md` remains a short first-hop entrypoint
- no new subsection was added under `## Task Routing`

### File 2: `docs/00-governance/development-workflow.md`

Goal for this file:
- make it process-first
- remove duplicated rule definitions that already live in `rules.md`

Sections that must be reviewed:
- `## 3. 事实来源优先级（Source of Truth）`
- `## 4. 分支策略`
- `## 6. 人类与 AI 责任边界`
- `## 9. 测试规则`
- `## 10. 文档更新规则`
- `## 11. 临时文件和实验规则`
- `## 13. 最简化的日常研发单句要义（Practical One-Line Rules）`

Editing standard:
- if a section mostly restates mandatory rules already present in `rules.md`, compress it
- keep only workflow-specific explanation, project-local execution notes, or process sequence
- if a section still needs the rule, reference `rules.md` instead of re-listing the full mandatory matrix

Required compression targets:
- section 3 may keep a one-line reference to `rules.md` plus anti-assumption notes
- section 4.2 must not repeat the full branch-required list from `rules.md`; keep only project-specific additions such as exploratory AI work or throwaway branch scenarios
- section 6.2 must not restate the full "Human Review Required" list; replace it with a short reference to `rules.md`
- section 9 must not restate the low/medium/high validation matrix; keep at most one short sentence about leaving validation evidence in task docs
- section 10 must not restate the full documentation-update trigger list; keep at most the process note about updating change docs first, then higher-truth docs if needed
- section 11 must not keep the long example list; keep only the `.tmp/` rule and the note about promoting durable artifacts

Mandatory shape for section 4.2:
- first line: one short sentence pointing to `rules.md` for the main branch-policy list
- then keep at most two bullets, and both bullets must be project-specific additions not already fully covered by `rules.md`
- allowed examples:
  - implementation path is still uncertain and needs repeated AI exploration
  - the maintainer wants an easy-discard experimental branch
- not allowed:
  - retyping the full list of new interfaces, pagination, schema, storage, dedup, or concurrency changes from `rules.md`
- if more than two bullets remain in section 4.2 after editing, treat that as not complete

Minimum required outcomes:
- remove any conflicting source-of-truth ordering
- reduce repeated branch-policy lists
- reduce repeated validation policy lists
- reduce repeated documentation-update rules
- reduce repeated temp-file rules
- if section 13 remains, label it explicitly as a memory aid rather than a second source of authority

Hard acceptance checks:
- no section in `development-workflow.md` should redefine a full mandatory rule matrix that already exists in `rules.md`
- `development-workflow.md` should still explain workflow sequence and project-specific execution expectations
- the file must not contradict `rules.md`
- section 4.2 is a partial supplement, not a second full branch-policy list
- section 6.2 is a reference, not a retyped review checklist
- sections 9, 10, and 11 no longer contain long repeated rule lists
- section 4.2 contains at most two project-specific bullets after a short reference to `rules.md`

### File 3: `docs/00-governance/doc-rules.md`

Default action:
- do not edit this file unless a specific ambiguity remains after File 1 and File 2 are finished

If reviewing only, answer these questions in the report:
- does it already preserve a short entrypoint role
- does it already route readers to the next specific file or section
- is there any wording that materially causes over-reading

Acceptance rule:
- "no edit needed" is a valid outcome
- do not make cosmetic edits just to show activity

## Todo

### 1. Update `agent.md` task routing to expose all stable knowledge layers

Action:
- add routing entries for ADRs, playbooks, and reference docs
- make the routing table reflect the full promotion chain described in ADR-002

Primary basis:
- `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
- `docs/00-governance/agent.md`

Standard to apply:
- `docs/00-governance/doc-standards.md#truth-vs-history`
- `docs/00-governance/doc-standards.md#document-types`

Acceptance check:
- `agent.md` routes agents not only to module docs and technical docs, but also to `docs/04-decisions/`, `docs/05-playbooks/`, and `docs/06-references/`
- routing language stays short and navigation-oriented rather than turning `agent.md` into a long manual

### 2. Rewrite `agent.md` guidance for `docs/03-changes/` using module-plus-status routing

Action:
- replace vague wording such as `docs/03-changes/...`
- guide the reader to locate change docs by module first, then by lifecycle status

Primary basis:
- `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
- current directory structure under `docs/03-changes/`

Standard to apply:
- `docs/00-governance/doc-standards.md#placement`
- `docs/00-governance/doc-standards.md#naming-and-status`

Acceptance check:
- `agent.md` explicitly points users toward paths like `docs/03-changes/<module>/in_progress/`, `accepted/`, `draft/`, or `planned/`
- wording matches the actual directory structure already present in the repo
- wording stays concise and does not turn `Do Not Assume` into a detailed standard

### 3. Reduce duplicated rule content in `development-workflow.md`

Action:
- remove or compress repeated mandatory constraints that already belong to `rules.md`
- keep `development-workflow.md` focused on process and execution flow

Primary basis:
- `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`
- `docs/00-governance/rules.md`
- `docs/00-governance/development-workflow.md`

Standard to apply:
- ADR-002 section 3.1: navigation and rules are separated
- ADR-002 section 3.3: workflow docs should be process-first

Acceptance check:
- no conflicting source-of-truth ordering remains between `rules.md` and `development-workflow.md`
- review boundaries in workflow docs point back to `rules.md` instead of redefining the same mandates in full
- workflow-specific content is still preserved
- sections 4.2, 6.2, 9, 10, and 11 are visibly shorter than before if they previously duplicated rule lists
- section 4.2 no longer reads like a copied branch-policy checklist

### 4. Decide whether `doc-rules.md` needs a smaller wording tweak only

Action:
- verify whether the existing "read less, route better" language is already sufficient
- only edit if a small wording change materially improves routing discipline

Primary basis:
- `docs/00-governance/doc-rules.md`
- `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`

Standard to apply:
- keep first-hop docs short
- avoid redundant rewrites when intent is already expressed clearly

Acceptance check:
- if changed, the edit is minor and preserves `doc-rules.md` as a lightweight entrypoint
- if unchanged, the reason is documented in the associated change record or review notes

## Proposed Approach

1. Read and note the exact target sections before making any edit.
2. Update `agent.md` first because it is the highest-leverage navigation fix.
3. Then clean `development-workflow.md` so governance documents stop competing with each other.
4. Touch `doc-rules.md` only if a concrete ambiguity remains after the first two edits.
5. After edits, run a file-content review against the hard acceptance checks in this draft.
6. Write a completion report under `docs/drafts/report/` with evidence from the final file contents, not from memory.

## Validation

- manually review updated routing against the actual `docs/` directory layout
- compare final `agent.md` against ADR-002 and `doc-standards.md`
- compare final `development-workflow.md` against `rules.md` section by section for duplication or contradiction
- confirm `agent.md` remains short enough to serve as a first-hop entrypoint
- explicitly check whether any new subsection was added to `agent.md`; if yes, justify it or remove it
- explicitly check whether sections 4.2, 6.2, 9, 10, and 11 in `development-workflow.md` still contain long rule lists; if yes, the task is not fully complete
- explicitly count bullets in section 4.2 after editing; if there are more than two, the task is not fully complete
- if a report is written, make sure it distinguishes:
  - files changed
  - files reviewed but unchanged
  - residual risks or remaining duplication

## Required Review Step

After implementation, run a separate review pass or subagent review with this checklist:
- verify only allowed files were edited
- verify `agent.md` gained the missing route entries
- verify `agent.md` changed the `docs/03-changes/` route to module-plus-status guidance
- verify `agent.md` did not gain a new explanatory subsection under `## Task Routing`
- verify `development-workflow.md` no longer contains a conflicting truth-priority list
- verify `development-workflow.md` still contains process guidance, not only references
- verify sections 4.2, 6.2, 9, 10, and 11 are compressed rather than merely prefixed with "follow `rules.md`"
- verify section 4.2 has at most two bullets and both are project-specific supplements
- verify `doc-rules.md` was either left untouched for a stated reason or changed minimally for a stated reason
- verify the report does not over-claim completion

If the review finds remaining duplication or over-claiming, fix the files before closing the task.

## Report Template

The completion report under `docs/drafts/report/` should contain these sections:
- `Status`
- `Files Changed`
- `Files Reviewed But Not Changed`
- `What Was Actually Changed`
- `Acceptance Checks`
- `Review Findings`
- `Residual Gaps`

Report rules:
- do not mark a reviewed-but-unchanged file as modified
- do not say "all complete" if the reviewer still found unresolved duplication
- include at least one residual-risk line if the result is only a partial cleanup
- if any acceptance check is only partially satisfied, write `partial` or `not complete` instead of `pass`
- do not write `Residual Gaps: None` unless the reviewer explicitly checked the known weak spots in this draft and found none
- for section 4.2 specifically: if it still has more than two bullets or still mirrors the `rules.md` branch list, the report must mark that check as `not complete`

## Closure Standard

This draft is successful for a normal agent only if:
- the edits stay within the allowed files
- the final files satisfy the hard acceptance checks above
- the report is accurate about what changed and what did not
- the reviewer does not find unresolved contradictions being reported as finished
- `agent.md` was improved without growing a new routing mini-manual
- `development-workflow.md` removed repeated rule lists instead of merely adding cross-references above them
- `development-workflow.md` section 4.2 was reduced to a short reference plus at most two project-specific bullets

When actual implementation begins, this draft can be promoted to a planned or in-progress change doc.
