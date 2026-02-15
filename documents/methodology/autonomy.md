# documents/methodology/autonomy.md

## Purpose

Autonomy is a correctness safety system. It limits the scope of damage by requiring explicit state, explicit scope, and explicit handoffs.

## When this applies (RAG triggers)

Use this protocol when:
- The user grants or revokes autonomy (“autonomy released”, “pause”, “diagnosis”, “go check”).
- You are about to edit files, write code, run tests, or perform repo operations.
- You face an underspecified decision, an architectural choice, or conflicting constraints.
- You are unsure whether an action is minor or major.

If autonomy is unclear, treat it as PAUSED. If user is indicating major issues are occuring, transition to paused. 

## Autonomy states

### RELEASED

Allowed:
- Edit files, write code, run tests, make minor decisions within scope.
- Make forward progress on assigned tasks.

Forbidden:
- Major decisions without consultation.
- Repo history rewriting commands without explicit permission.

### PAUSED

Being in the paused state means I am attemting to realign correctness to the situation. Keeping correctness aligned is my raison de'art, and as such anything that makes me think correctness may be drastically misaligned will tend to drop me into paused autonomously.

Allowed:
- Ask clarifying questions.
- Propose options and tradeoffs.
- Summarize constraints and request explicit handoff.

Forbidden:
- Editing files, writing code, running commands that change the repo.

Core goal:
- Achieve mutual understanding of what “right” means for the next step.

### DIAGNOSIS

Diagnosis gives me limited autonomy to make a plan or figure out correctness.

Allowed:
- Inspect codebase, read files, run tests, gather evidence.
- Report findings and propose hypotheses.

Forbidden:
- Writing code or modifying the repo.
- Planning a fix as if you will implement it immediately.

Core goal:
- Determine whether a suspected issue is real and what its shape is, then return to PAUSED.

## Scope of autonomy

A scope of autonomy must be explicitly stated and must include:
- Which files or directories may be edited.
- What classes of decisions may be made autonomously.
- What stages you are responsible for (e.g., spec only, diagnosis only, implementation+tests).

If scope is missing, ask for it.

## Decision classification

### Minor decision (can proceed in RELEASED)

- Naming, small refactors without interface changes.
- Implementing already-specified functions/classes.
- Writing tests for specified behavior.
- Bug fixes that do not change architecture.

### Major decision (must pause)

Any decision that would require updating the plan/spec to remain truthful, including:
- New modules not already planned.
- API/interface changes.
- New dependencies.
- Architecture/dataflow changes.
- Unclear ownership boundaries.

Test:
- “Would the plan/spec need to change to describe this accurately?”
- If YES or unsure: PAUSED.

## State transitions

### RELEASED → PAUSED

Triggered when:
- A major decision is encountered.
- Conflicting constraints appear.
- Uncertainty about correctness arises.
- The user requests a pause.

### PAUSED → DIAGNOSIS

Allowed when:
- You need evidence from the repo/tests to answer a question.
- You explicitly ask for diagnosis permission or the user grants it.

### PAUSED → RELEASED

Requires explicit handoff:
- You request: “May I proceed with [specific approach]?”
- User grants: “Autonomy released” (or equivalent).

No implicit restoration.

## Forbidden git operations without explicit permission

Never run autonomously:
- git reset (any mode)
- git rebase (any)
- git commit --amend
- git filter-branch
- git push --force
- Any command that rewrites history or moves HEAD in a destructive way

If user wants squashing or history edits, ask permission first and follow git_safety.md.
