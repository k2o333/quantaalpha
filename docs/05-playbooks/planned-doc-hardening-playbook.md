# Planned Doc Hardening Playbook

## Background

This playbook is for a specific problem:

- the repository already has governance rules
- a change task already has a `planned` document
- but a normal agent still delivers partial work while sounding complete

In these cases, the root problem is often not coding skill.
The root problem is that the `planned` document describes the desired feature, but does not yet constrain how completion must be proved.

This playbook is about raising the standard of `planned` documents so that ordinary agents are less likely to:

- misunderstand the real target
- optimize for local plausibility
- overclaim completion
- move a document to `tested` too early

## When To Use This Playbook

Use this playbook when:

- a task will be executed from a `docs/03-changes/<module>/YYYY-MM-DD-topic.md` document with `status: planned` in metadata
- a normal agent is likely to implement the task
- the task touches behavior, validation, state changes, scheduling, persistence, or test claims
- previous executions looked plausible but failed real acceptance

Boundary:

- this playbook is about writing stronger `planned` documents
- it is not a replacement for governance rules
- it is not a code-delivery audit guide; for that use `agent-delivery-audit-playbook.md`

## Core Lesson

A weak `planned` document tells the agent:

- what feature to add
- which files to change
- what tests to write

A strong `planned` document also tells the agent:

- what must be true for the task to count as complete
- what would disprove completion
- what evidence is primary and what evidence is only supportive
- what does not count as done

The main shift is:

- from implementation description
- to completion contract

## What A Good Planned Doc Must Do

Every good `planned` document should do all of the following:

### 1. Define the problem, not only the intended feature

The document should state:

- what is wrong now
- why the current behavior is insufficient
- what ambiguity or failure must be removed

If the document only describes the target feature, agents tend to optimize for surface completion.

### 2. Define scope and non-goals

The document should explicitly separate:

- what is in scope
- what is out of scope

This prevents agents from:

- doing adjacent work and claiming progress
- compensating for incomplete delivery with unrelated cleanup

### 3. Define the seam being changed

The document should identify the relevant system seam.

Examples of seams:

- entrypoint to downstream consumer
- writer to source-of-truth file
- state producer to state consumer
- CLI output to scheduler-visible failure surface

If the seam is not named, agents often change one side only.

### 4. Define how completion can be disproved

A `planned` document should not only say how success looks.
It should also say what result would prove the task is not complete.

This is the role of a `Disproof Command` or equivalent falsification step.

Without that, agents can accumulate positive-looking signals without ever facing a hard check.

### 5. Define evidence levels

A `planned` document should distinguish:

- primary evidence
- secondary evidence

Primary evidence is what can justify `tested`.
Secondary evidence is useful, but cannot justify `tested` on its own.

Typical examples:

- primary: real CLI invocation, real parser invocation, real public boundary test
- secondary: helper unit tests, mirrored-logic tests, mocked internal shape checks

This distinction matters because ordinary agents often treat any passing test as acceptance proof.

### 6. Define what does not count as done

Good `planned` docs need explicit negative rules.

Examples of useful negative forms:

- logging does not count as behavior change
- tracking does not count as control-flow integration
- mock-only verification does not count as boundary proof
- a report field does not count as operator-visible failure semantics

If this is omitted, agents will satisfy the visible checklist with the cheapest plausible implementation.

### 7. Define the move-to-tested gate

`planned` documents should say when they are allowed to become `tested`.

This gate should be based on proof, not on implementation effort.

At minimum, the document should define:

- what command must be rerun
- what boundary must be exercised
- what conditions block the move to `tested`

## Standard Sections To Include

For normal engineering tasks, a hardened `planned` document should usually include these sections or their equivalents:

- `Goal`
- `Scope`
- `Non-goals`
- `Code Touchpoints`
- `Downstream Consumer` or equivalent seam description
- `Write Target / Source of Truth` when persistence matters
- `Failure Semantics` when caller-visible failure matters
- `Required Boundary Test`
- `Disproof Command`
- `What Does Not Count As Done`
- `Acceptance Criteria`

Not every task needs every label literally, but every task should cover the underlying slots.

## How To Decide Which Slots Are Mandatory

Not every task needs the same level of hardening.

Use this rule of thumb.

### Low-risk task

Usually enough:

- goal
- scope
- code touchpoints
- acceptance criteria

### Medium-risk task

Also add:

- non-goals
- seam definition
- disproof command
- what does not count as done

### High-risk task

Also add:

- downstream consumer
- write target or source-of-truth path
- failure semantics
- required boundary test
- evidence-level distinction
- explicit move-to-tested gate

High-risk usually includes:

- new CLI modes
- scheduling
- persistence
- state transitions
- retries
- external side effects
- claims about validation or test passing

## Common Weak Planned-Doc Patterns

### 1. Feature-only planning

Typical bad form:

- "add X mode"
- "support Y behavior"
- "write tests"

What is missing:

- seam
- failure surface
- falsification condition

### 2. File list mistaken for task definition

Typical bad form:

- a good list of files
- but no statement of what must be true across those files

Agents can then make coherent local edits while missing the system contract.

### 3. Acceptance criteria that are only positive

Typical bad form:

- "tests pass"
- "output looks correct"
- "CLI works"

What is missing:

- what would prove the task failed
- what kind of passing test is insufficient

### 4. No distinction between primary and secondary evidence

Typical bad form:

- mocked tests and real CLI validation are treated as equally strong

This lets weak evidence carry too much weight.

### 5. `tested` treated as a development milestone

Typical bad form:

- once code and tests exist, the doc moves to `tested`

This is exactly the behavior a hardened `planned` document should prevent.

## Hardening Moves That Work

### 1. Convert vague intent into named slots

Instead of:

- "make revalidation clearer"

Write:

- problem
- downstream consumer
- required boundary test
- disproof command

Named slots reduce interpretation drift.

### 2. Add negative rules early

Do not wait for repeated failure before adding:

- what does not count as done

Normal agents respond much better when forbidden shortcuts are visible from the start.

### 3. Require one falsification step

Every medium/high-risk `planned` document should include at least one command or check whose failure clearly blocks completion.

This keeps the task anchored in disprovable reality.

### 4. Separate proof of implementation from proof of acceptance

A task can have:

- evidence that code changed
- evidence that tests were written

and still lack:

- evidence that the task is actually complete

The document should force these to remain separate.

### 5. Define the boundary in the language of the consumer

Do not define completion only in the language of the producer.

Examples:

- not just "we write a JSON"
- but "the existing parser can read it"

- not just "we track failed items"
- but "the next round input set is derived from that result"

This is often the single most important hardening move.

## Practical Template For Future Planned Docs

When writing a `planned` document for a normal agent, use this sequence:

1. `Goal`
2. `Current Problem`
3. `Scope`
4. `Non-goals`
5. `Code Touchpoints`
6. `Seam / Downstream Consumer`
7. `Failure Semantics` if relevant
8. `Required Boundary Test`
9. `Disproof Command`
10. `What Does Not Count As Done`
11. `Acceptance Criteria`
12. `Move-to-Tested Conditions`

If the task is simple, some sections can be short.
But skipping these ideas entirely is what usually causes later ambiguity.

## Review Standard For Planned Docs

Before a `planned` document is considered ready for execution, ask:

- Does it describe a real current problem, not only a desired future?
- Does it say what is out of scope?
- Does it identify the system seam being changed?
- Does it define at least one falsification step?
- Does it say what evidence is strong enough for acceptance?
- Does it say what shortcuts do not count as done?
- Does it make clear when the doc may move to `tested`?

If any answer is "no", the document is probably still too weak for a normal agent.

## Closure Standard

A `planned` document is strong enough when:

1. a normal agent can tell what to implement
2. a reviewer can tell what would disprove completion
3. the move to `tested` depends on evidence, not narration

If only the first item is true, the document is still an implementation brief, not a hardened execution contract.
