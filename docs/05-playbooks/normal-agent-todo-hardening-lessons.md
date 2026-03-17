# Normal Agent Todo Hardening Lessons

## Background

This playbook captures lessons from repeatedly refining the task draft at:

`docs/03-changes/common/draft/2026-03-16-agent-doc-system-followup-todo.md`

The practical problem was not that the target documentation changes were unclear to a strong reviewer. The problem was that a normal coding agent could read the same intent, make plausible edits, and still miss the real standard of completion.

The repeated failures were useful because they exposed a pattern: ordinary agents often complete the visible checklist while missing the structural intent behind it.

## When To Use This Playbook

Use this playbook when:
- a task is documentation-heavy or governance-heavy
- the desired outcome depends on judgment about "how much is enough"
- a normal agent keeps producing partial-but-overconfident results
- review failures repeat around the same weak points
- a task needs a subagent review and a reliable completion report

Boundary:
- this playbook is for documentation-heavy and governance-heavy tasks where the main risk is vague intent or overclaiming
- if the main risk is code integration, runtime closure, test reproducibility, or seam verification, use `agent-delivery-audit-playbook.md`

## Core Lesson

If a task depends on subtle interpretation, a normal agent will often optimize for:
- satisfying the literal checklist
- making minimal visible edits
- writing a confident report once edits exist

It will often miss:
- whether duplicated content was truly removed or merely prefixed with a reference
- whether a short entrypoint accidentally grew into a mini-manual
- whether a review step actually verified file contents rather than repeating the agent's own story

The fix is to convert a judgment-heavy task into a constrained execution task.

## Common Failure Modes

### 1. "Added a reference" is mistaken for "removed duplication"

Typical bad outcome:
- a section keeps the old rule list
- one sentence like `follow rules.md` gets added on top
- the agent reports the section as successfully deduplicated

Countermeasure:
- define what content must be deleted, not only what should be referenced
- state that "reference + old list" does not count as compressed

### 2. Entry documents grow into mini-manuals

Typical bad outcome:
- the agent correctly adds missing routing
- then it adds a new explanatory subsection that belongs in a lower-level doc

Countermeasure:
- explicitly forbid new subsections unless required
- require routing guidance to stay inside existing table rows or bullets

### 3. Partial cleanup gets reported as full completion

Typical bad outcome:
- one important section still violates the standard
- the review and report still say `all checks passed`

Countermeasure:
- define concrete failure conditions that force `partial` or `not complete`
- forbid `Residual Gaps: None` unless named weak spots were explicitly checked

### 4. Reviewers verify summaries instead of files

Typical bad outcome:
- the subagent reads the main agent's claim
- the subagent repeats it with slightly different wording
- both agents miss the same structural defect

Countermeasure:
- require the reviewer to inspect final file contents
- require file-specific checks with concrete criteria

### 5. Structural intent is too abstract

Typical bad outcome:
- "make this process-first" sounds clear to a human
- a normal agent translates it into shallow local edits

Countermeasure:
- express the requirement as shape constraints
- example: "after editing, this section may contain one reference sentence plus at most two project-specific bullets"

## Hardening Patterns That Worked

### 1. Fix the read order

Do not assume the agent will discover the right dependency chain.

Write:
- which files to read
- in what order
- before which edits

This reduces drift and prevents first-pass edits based on partial context.

### 2. Limit the allowed edit surface

State:
- which files may be edited
- which sections may be edited
- which files must not be touched

This is especially important in governance work, where an agent may otherwise "improve" adjacent docs that were not part of the task.

### 3. Add negative rules, not only positive goals

Weak instruction:
- "rewrite change-doc routing more clearly"

Stronger instruction:
- "replace the vague route"
- "do not add a new explanatory subsection"
- "do not list every module and status unless necessary"

Normal agents respond well to "do not do X".

### 4. Turn intent into structural acceptance checks

Good acceptance checks are about file shape, not only semantics.

Examples:
- "no new subsection added under `## Task Routing`"
- "`section 4.2` contains at most two project-specific bullets"
- "`sections 9, 10, 11` no longer contain long repeated rule lists"

These are much easier for a normal agent and a reviewer to verify consistently.

### 5. Promote known weak spots into mandatory review items

If one section already failed twice, stop treating it like a general quality concern.

Promote it into:
- a named weak spot
- an explicit validation step
- a report requirement

This is what finally stabilized the `development-workflow.md` section `4.2` cleanup.

### 6. Force honest reporting

The report should not just summarize changes.

It should also constrain what the agent is allowed to claim.

For general validation-claim rules such as reproducible test commands and closure checks, see `agent-delivery-audit-playbook.md`.

Useful report rules for doc/governance tasks:
- do not mark reviewed-but-unchanged files as modified
- if a check is only partially satisfied, write `partial` or `not complete`
- do not write `Residual Gaps: None` unless the weak spots were explicitly checked

### 7. Structural constraints beat semantic advice

When a section keeps failing, "make this cleaner" is too weak.

Normal agents perform better when the task defines the final shape.

Example of a strong instruction:
- first line must reference `rules.md`
- at most two bullets may remain
- both bullets must be project-specific supplements

This was the turning point for stabilizing the cleanup of `development-workflow.md` section `4.2`.

### 8. Lock down the risky sections, not every section

Not every paragraph needs the same level of control.

In practice:
- some sections can tolerate light paraphrasing if the truth boundary remains intact
- a few known weak spots need strict shape rules and explicit reviewer checks

This means task hardening should focus on the places where normal agents repeatedly over-complete, under-delete, or over-claim.

Do not spend the same instruction budget on low-risk wording that you spend on structurally important sections.

## Practical Template For Normal-Agent Tasks

When a task keeps failing, add these layers in order:

1. `Required Read Order`
2. `Allowed output files`
3. `Do not edit`
4. `Exact Edit Plan`
5. `Hard acceptance checks`
6. `Required Review Step`
7. `Report rules`
8. `Closure Standard`

If that is still not enough, add one more layer:
- section-by-section shape constraints

Example:
- first line must be a reference to `rules.md`
- at most two bullets may remain
- both bullets must be project-specific additions

## Escalation Rule

When repeated failures continue, tighten the task using this sequence:

1. Add stronger acceptance checks.
2. Add explicit "not allowed" patterns.
3. Add section-shape constraints.
4. Add forced `partial` outcomes for known failure cases.
5. Add reviewer checks that inspect the file directly.

Do not jump straight to broad prose explanations. Ordinary agents usually need narrower rails, not more abstract reasoning.

## Anti-Patterns

Avoid these task-writing mistakes:
- asking for "better", "cleaner", or "more aligned" without saying what must disappear
- relying on the agent to infer which section is the known risk
- requiring a review but not telling the reviewer what to falsify
- letting the report define success in its own words
- accepting "references added" as proof that duplication was removed

## Checklist For Authors

Before handing a task to a normal agent, check:
- does the task define exactly which files can change
- does it define which sections can change
- does it forbid the most likely wrong edits
- does it specify what must be shorter, removed, or left unchanged
- does it give at least one concrete failure condition
- does the reviewer have file-based checks rather than summary-based checks
- does the report have rules against over-claiming

If two or more answers are "no", the task is probably still too abstract.

For code-delivery checks such as runtime path alignment, exit semantics, downstream payload shape, or exact test-command reproducibility, defer to `agent-delivery-audit-playbook.md`.

## Repository-Specific Lesson

For this repository, governance and documentation tasks are especially vulnerable to false completion because:
- the target docs are short and easy to "touch"
- the difference between routing, rules, and workflow is architectural rather than syntactic
- a weak edit can look polished while still violating ADR-002's separation of concerns

So for `agent.md`, `rules.md`, `doc-rules.md`, and `development-workflow.md`, prefer:
- explicit scope limits
- short-path routing constraints
- duplicate-removal requirements
- reviewer checks tied to exact sections

In particular:
- allow mild wording flexibility in low-risk sections if the role of the document stays intact
- apply hard structural constraints to sections that historically fail review, such as branch-policy supplements
- judge success primarily on whether the risky sections were truly reshaped, not on whether every sentence was rewritten exactly as expected

## Bottom Line

If a task matters and a normal agent must execute it, do not only describe the desired outcome.

Also describe:
- what the wrong completion looks like
- what must be removed
- what shape the final section must have
- when the agent must admit the work is only partial
