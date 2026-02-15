# documents/methodology/git_safety.md

## Purpose

Git protocol prevents irreversible loss and preserves auditability.
Additive > destructive.

## When this applies (RAG triggers)

Use this when:
- Committing, releasing, or editing CHANGELOG.md.
- Considering history edits (squash, rebase, reset).
- You see failing tests and feel tempted to “patch it later”.

## Commit as you go

Workflow:
1) Edit
2) Fix tests
3) Run tests
4) If pass: commit
5) If fail: fix or rollback
6) Repeat

Commits are safety checkpoints.

## CHANGELOG discipline

- All changes go into “Unreleased” first.
- Use standard categories: Added/Changed/Deprecated/Removed/Fixed/Security.
- Do not bump version unless user approves release.

## Release recommendation requirement

If unreleased work exists:
- Summarize what changed.
- Compare commits vs changelog.
- Recommend PATCH/MINOR/MAJOR with reasoning.
- Ask user permission before performing release steps.

## Forbidden without explicit permission

Never run autonomously:
- git reset (any)
- git rebase (any)
- git commit --amend
- git filter-branch
- git push --force
- Any destructive HEAD-moving operation

If squashing is requested, ask permission first and keep working tree clean.
