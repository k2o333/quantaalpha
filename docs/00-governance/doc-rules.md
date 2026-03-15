


# doc-rules.md

# Documentation Rules

## 1. Purpose

This document defines how documentation is created, stored, updated, and used in this repository.

Goals:

- keep a single reliable source of truth for current project knowledge
- separate current truth from discussion history
- make every change traceable
- make documents easy for both humans and AI tools to read and execute
- keep framework / open-source references manageable and reusable

Core principles:

1. formal docs are centrally managed
2. process docs are separated from formal docs
3. current truth is separated from history
4. rules, facts, changes, decisions, playbooks, and references are stored separately
5. documentation must help delivery, not create noise

---

## 2. Document Types

We use the following document types.

### 2.1 Governance Docs
Describe global rules, workflows, and conventions.

Examples:

- `documentation-rules.md`
- `development-workflow.md`
- `testing-strategy.md`

Use for:

- repo-wide rules
- process definitions
- documentation conventions
- testing conventions

---

### 2.2 Overview Docs
Describe the whole system and module map.

Examples:

- `system-overview.md`
- `module-map.md`

Use for:

- overall architecture understanding
- major boundaries
- key subsystem relationships

---

### 2.3 Module Docs
Describe the **current valid state** of a module.

Examples:

- `auth.md`
- `editor.md`
- `search.md`

Should include:

- responsibility
- external interfaces
- key data structures
- dependencies
- constraints
- known risks
- test entry points

Rules:

- only document current state
- do not accumulate history here
- do not store brainstorming here

---

### 2.4 Change Docs
One document for one concrete change.

Examples:

- `app4/2026-03-15-offset-atomic-fix.md`
- `quantaalpha/2026-03-14-factor-implementation.md`
- `common/2026-03-13-dependency-upgrade.md`

Should include:

- background
- goal
- non-goals
- acceptance criteria
- test plan
- implementation plan
- risk points
- rollback plan
- final result
- validation evidence
- lessons learned

Rules:

- every meaningful change should have a change doc
- acceptance and testing must be defined before implementation
- update final results after the task is complete
- change docs are organized by module (app4, quantaalpha, vnpy, etc.)
- cross-module changes go to `common/` subdirectory

---

### 2.5 Draft Docs
Used for exploration, comparisons, and temporary thinking.

Examples:

- `2026-03-13-auth-rate-limit-options.md`
- `2026-03-14-search-refactor-exploration.md`

Rules:

- drafts are not formal requirements
- drafts are for discussion and exploration
- drafts cannot be used as the source of truth
- drafts should carry explicit status

---

### 2.6 Archive Docs
Used for outdated or rejected docs that still have reference value.

Examples:

- rejected proposals
- outdated designs
- abandoned directions
- superseded docs

Rules:

- archived docs are for history only
- archived docs must not be treated as current truth

---

### 2.7 Decision Docs / ADRs
Used for important long-term decisions.

Examples:

- session strategy
- module boundary decisions
- storage strategy changes
- testing policy changes

Rules:

- explain why the decision was made
- do not use ADRs for one-off implementation details
- do not replace change docs with ADRs

---

### 2.8 Playbooks / Retrospectives
Used to capture reusable experience, common failure modes, and recommended patterns.

Examples:

- `ai-change-workflow.md`
- `safe-refactor-playbook.md`
- `regression-checklist.md`

Use for:

- repeatable engineering patterns
- AI / Codex collaboration practices
- common mistakes and prevention
- review checklists

Rules:

- only cross-task reusable knowledge belongs here
- one-off lessons should stay in change docs first

---

### 2.9 Reference Docs
Used to document heavy-use frameworks, libraries, platforms, and important open-source repositories that the project depends on repeatedly.

Examples:

- `nextjs-reference.md`
- `react-reference.md`
- `fastapi-reference.md`
- `rails-reference.md`
- `redis-reference.md`
- `openai-sdk-reference.md`
- `tanstack-query-reference.md`
- `vite-reference.md`

For open-source repositories:

- `react-router-reference.md`
- `langgraph-reference.md`
- `vercel-ai-sdk-reference.md`
- `open-webui-reference.md`

Use for:

- project-specific usage conventions
- known supported patterns
- forbidden or discouraged patterns
- version-sensitive behavior relevant to this repo
- common commands and debugging entry points
- links to official docs and source repo locations
- repo-specific lessons from repeated use

Rules:

- reference docs are not copies of external docs
- reference docs must summarize only what is relevant to this repo
- reference docs should focus on “how we use it here”
- reference docs must note the version or version range when relevant
- reference docs should distinguish between official behavior and local conventions
- if upstream changes materially affect usage, reference docs should be updated

Reference docs should preferably contain:

- what it is used for in this repo
- version / edition / runtime assumptions
- approved patterns
- discouraged patterns
- common pitfalls
- project-specific examples
- debugging notes
- related module docs
- official documentation links
- important upstream repo links

---

### 2.10 Technical Docs
Used for detailed implementation flows, call chains, and architecture diagrams that complement module docs.

Examples:

- `app4-main-flow.md`
- `quantaalpha-factor-mining-flow.md`
- `backtest-alpha101-flow.md`

Use for:

- detailed mermaid flowcharts
- step-by-step call chains
- internal implementation details
- code-level execution sequences

Rules:

- technical docs complement module docs, not replace them
- module docs provide concise interface/constraint summaries
- technical docs provide detailed flow/diagram explanations
- technical docs should be updated when implementation changes
- each technical doc should reference its corresponding module doc

Technical docs should contain:

- mermaid flowcharts
- detailed execution chains
- key code paths with line references
- important implementation notes

---

## 3. Recommended Directory Structure

All formal docs live under a central `docs/` directory by default.

Recommended structure:

```text
docs/
  00-governance/
    doc-rules.md
    development-workflow.md
    testing-strategy.md

  01-overview/
    system-overview.md
    module-map.md

  02-modules/
    auth.md
    billing.md
    editor.md
    search.md

  03-changes/
    app4/
      2026-03-15-offset-atomic-fix.md
    quantaalpha/
      2026-03-14-factor-implementation.md
    vnpy/
    common/                    # 跨模块的通用变更
      2026-03-13-dependency-upgrade.md

  04-decisions/
    ADR-001-session-strategy.md
    ADR-002-search-indexing.md

  05-playbooks/
    ai-change-workflow.md
    regression-checklist.md
    safe-refactor-playbook.md

  06-references/
    react-reference.md
    nextjs-reference.md
    fastapi-reference.md
    redis-reference.md
    tanstack-query-reference.md

  07-technical/
    app4-main-flow.md
    quantaalpha-factor-mining-flow.md
    backtest-alpha101-flow.md

  drafts/
    2026-03-13-auth-rate-limit-options.md
    2026-03-14-editor-autosave-exploration.md

  archive/
    2026/
      rejected-auth-session-plan.md
      abandoned-editor-redesign.md
````

---

## 4. Placement Rules

### 4.1 Formal docs go to `docs/`

The following must live in the central `docs/` tree:

- governance docs

- overview docs

- module docs

- change docs

- decision docs

- playbooks

- reference docs

- technical docs

- drafts

- archive docs
    

---

### 4.2 Module-local README is allowed

A module may contain a local `README.md` for code-adjacent information such as:

- local setup
    
- local development commands
    
- local debugging tips
    
- directory layout
    
- implementation-near notes
    

Rules:

- module-local README is not the main source of truth for product/module behavior
    
- formal module behavior still belongs in `docs/02-modules/`
    
- do not create a separate `doc/` directory under every module by default
    

Only large subsystem-level modules may have their own nested `docs/` directory.

---

## 5. Current Truth vs History

### 5.1 Current Truth

The following are treated as current reliable sources:

- governance docs
    
- overview docs
    
- module docs
    
- currently valid ADRs
    
- current playbooks
    
- current reference docs
    

These should represent the latest approved truth.

---

### 5.2 Historical / Process Materials

The following are history or process materials:

- drafts
    
- archive docs
    
- completed change docs
    
- superseded ADRs
    
- obsolete reference docs
    

These exist for traceability and learning, not as the default implementation source.

---

## 6. Naming Rules

### 6.1 General

- use lowercase file names
    
- separate words with `-`
    
- names must clearly indicate topic
    
- avoid vague names like `final`, `new`, `latest`, `v2`, `try2`
    

---

### 6.2 Change Docs

Format:

```text
docs/03-changes/<module>/YYYY-MM-DD-topic.md
```

Modules:

- `app4/` - Tushare 数据下载模块
- `quantaalpha/` - 因子挖掘模块
- `vnpy/` - 交易模块
- `common/` - 跨模块通用变更

Examples:

- `docs/03-changes/app4/2026-03-15-offset-atomic-fix.md`
- `docs/03-changes/quantaalpha/2026-03-14-factor-implementation.md`
- `docs/03-changes/common/2026-03-13-dependency-upgrade.md`

Rules:

- place change docs in the corresponding module subdirectory
- use `common/` for changes affecting multiple modules
- file name follows `YYYY-MM-DD-topic.md` format
    

---

### 6.3 Draft Docs

Format:

```text
YYYY-MM-DD-topic-type.md
```

Examples:

- `2026-03-13-auth-rate-limit-options.md`
    
- `2026-03-14-search-refactor-exploration.md`
    

---

### 6.4 ADRs

Format:

```text
ADR-XXX-topic.md
```

Examples:

- `ADR-001-session-strategy.md`
    
- `ADR-002-search-indexing.md`
    

---

### 6.5 Reference Docs

Format:

```text
<framework-or-repo>-reference.md
```

Examples:

- `react-reference.md`
    
- `nextjs-reference.md`
    
- `fastapi-reference.md`
    
- `langgraph-reference.md`
    

If needed, use a scoped name:

- `openai-python-reference.md`
    
- `github-actions-reference.md`
    
- `postgres-reference.md`
    

---

## 7. Status Header Rules

Drafts, change docs, archive docs, and references should preferably include a status header.

Recommended fields:

```md
Status: draft | validated | in_progress | implemented | tested | accepted | archived | active | superseded
Owner: <name>
Created: YYYY-MM-DD
Outcome: pending | accepted | rejected | superseded
```

Optional fields:

```md
Version: <version or range>
Superseded-by: <path>
Related-to: <path>
Updated: YYYY-MM-DD
```

For reference docs, add:

```md
Upstream: <official doc or repo>
Applies-to: <repo/module/path>
```

---

## 8. Change Doc Update Rules

After each task, perform documentation closure in this order:

1. update the final result in the change doc
    
2. decide whether module docs must be updated
    
3. decide whether an ADR must be created or updated
    
4. decide whether lessons should be promoted to a playbook
    
5. decide whether framework / repo usage knowledge should be promoted to a reference doc
    
6. attach validation evidence and links
    

---

## 9. Module Doc Update Rules

Update module docs only when one of the following changes:

- module responsibility
    
- external interface
    
- data structure
    
- dependency relationship
    
- module boundary
    
- risk model
    
- test entry point
    

A small local bug fix does not automatically require a module doc update.

---

## 10. Draft Management Rules

### 10.1 Drafts may be kept

Keep drafts when they provide value such as:

- useful exploration
    
- future reuse
    
- design alternatives worth remembering
    
- explanation of why a path was rejected
    
- lessons that help AI tools avoid repeated mistakes
    

---

### 10.2 Drafts are not formal truth

Anything in `docs/drafts/`:

- is not the implementation source of truth
    
- is not the acceptance criteria source
    
- is not a formal requirement unless promoted
    

---

### 10.3 Draft lifecycle

A draft should end in one of three states:

1. promoted into a formal doc
    
2. moved to archive
    
3. deleted if low-value and non-reusable
    

---

## 11. Archive Rules

Archive docs that are:

- explicitly rejected but still informative
    
- superseded by newer docs
    
- historically useful but no longer valid
    

Archived docs should ideally note:

- original purpose
    
- why they were retired
    
- what replaced them
    

---

## 12. Lessons Learned Promotion Rules

When AI-assisted development fails and a better implementation path is found:

### 12.1 If it only matters for one task

Keep it in that change doc’s `lessons learned`

### 12.2 If it applies to multiple tasks

Promote it into a playbook

### 12.3 If it changes a long-term design principle

Write or update an ADR

### 12.4 If it becomes a stable framework / repo usage rule

Promote it into a reference doc

### 12.5 If it becomes a repeatable workflow

Consider turning it into a skill or command, not just a document

---

## 13. Reference Doc Rules

Reference docs exist because some frameworks or open-source repositories are used heavily enough that repeated project-specific guidance is needed.

### 13.1 When to create a reference doc

Create one when at least one of the following is true:

- the framework/repo is used in multiple modules
    
- developers repeatedly ask the same usage questions
    
- upstream docs are broad, but the project only allows specific patterns
    
- version-sensitive behavior matters to this repo
    
- AI tools repeatedly make the same mistakes around this dependency
    
- there are local conventions worth standardizing
    

---

### 13.2 What a reference doc must not be

A reference doc must not be:

- a full copy of upstream docs
    
- a dumping ground for random notes
    
- a substitute for module docs
    
- a substitute for ADRs
    
- a list of unverified tips
    

---

### 13.3 What a reference doc should include

Recommended sections:

- purpose in this repo
    
- supported version / assumptions
    
- approved usage patterns
    
- discouraged / forbidden patterns
    
- integration notes
    
- common pitfalls
    
- debug checklist
    
- migration notes if relevant
    
- official links
    
- source repo links
    
- related internal docs
    

---

### 13.4 Ownership

Every heavily used framework or open-source dependency with a reference doc should have a practical owner or maintaining team.

---

## 14. Git / GitHub Rules

### 14.1 Formal docs should be committed

The following should usually be in Git:

- governance docs
    
- overview docs
    
- module docs
    
- change docs
    
- decision docs
    
- playbooks
    
- reference docs
    

---

### 14.2 Drafts may be committed, but must stay isolated

`docs/drafts/` may be committed if they:

- have a clear topic
    
- have understandable context
    
- have explicit status
    
- are not pretending to be formal docs
    

Do not commit every tiny fragment of low-value temporary notes.

---

## 15. AI / Codex Usage Rules

AI tools working on this repo must follow this priority order:

1. formal docs first
    
2. governance docs and module docs before drafts
    
3. reference docs are valid guidance for heavy-use frameworks and repos in this project
    
4. drafts are reference-only unless explicitly promoted
    
5. archive is for history only
    
6. implementation and acceptance decisions must come from approved formal docs or approved change docs
    

AI tools must not:

- treat drafts as requirements by default
    
- treat archives as active design
    
- copy upstream reference content into internal docs without filtering for repo relevance
    

---

## 16. When to Write Which Doc

Write a change doc when:

- making a concrete change
    

Write a module doc update when:

- current module truth changes
    

Write a draft when:

- exploring, comparing, or discussing
    

Write an archive doc when:

- a doc is obsolete but still worth keeping
    

Write an ADR when:

- a long-term design decision changes
    

Write a playbook when:

- a lesson becomes reusable across tasks
    

Write a reference doc when:

- a framework or open-source repo is used heavily and needs repo-specific guidance
    

---

## 17. Minimum Enforcement Rules

At minimum, this repo should always enforce:

1. all formal docs live under `docs/`
    
2. module docs only describe current state
    
3. meaningful changes should have change docs
    
4. change docs are organized by module under `docs/03-changes/<module>/`
    
5. drafts are isolated from formal docs
    
6. obsolete but useful docs go to archive
    
7. long-term design choices go to ADRs
    
8. repeatable engineering experience goes to playbooks
    
9. heavy-use framework / repo usage knowledge goes to references
    
10. task completion requires documentation closure
    

---

## 18. One-Line Summary

Governance docs define how we work, overview docs define the system map, module docs define current local truth, change docs define what changed, drafts define what is still being explored, archive preserves historical context, ADRs explain why major decisions were made, playbooks capture repeatable lessons, and reference docs define how this repo uses heavily relied-on frameworks and open-source repositories.