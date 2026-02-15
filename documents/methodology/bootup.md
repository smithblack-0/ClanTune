# documents/methodology/bootup.md

## Purpose

Bootup is the startup protocol used to prevent correctness drift caused by partial context. This checklist exists to align the model’s active context with the project’s governing contracts before any work begins.

## When this applies (RAG triggers)

Run this checklist when:
- A new session starts (fresh Claude Code invocation, new terminal chat, or after long context drift).
- The user says “bootup”, “startup”, “initialize”, “begin work”, “read the docs”, or “sync context”.
- You are about to modify code, tests, or specs and you have not recently confirmed the governing contracts.
- You are uncertain what constraints apply or you suspect hidden constraints exist in documents.

Do not “half bootup”. If bootup is requested, either execute it fully or pause and ask.

## Bootup handshake

If this appears to be the first time in this repo/session:
- Ask: “Do you want me to perform the bootup checklist in its entirety?”
- If YES: execute this file.
- If NO: ask what subset is desired and explicitly note what is not being checked.

## Checklist (execute in order)

### 1) Read critical context files (entirely)

Read these files fully (no partial reads):
- CLAUDE.md
- proposal.md
- documents/genetics_lifecycle.md

If the repo has additional “critical” files listed in CLAUDE.md, include them.

### 2) Verify documentation map matches reality

- List the contents of `documents/` and `documents/methodology/`.
- Compare to the lists in CLAUDE.md.
- If there are files on disk not listed:
  - Read the new files entirely.
  - STOP and ask the user: “I notice documents/ has changed. May I update CLAUDE.md to reflect the current documentation?”
- If there are files listed but missing:
  - STOP and ask the user whether to remove/update the list.

### 3) Check unreleased changes

- Read CHANGELOG.md and check for an “Unreleased” section.
- Scan recent git commits (`git log --oneline`) since the last release tag/version.
- Compare commit intent to CHANGELOG entries.

If drift exists:
- Summarize what appears missing from the changelog.
- Classify changes as PATCH/MINOR/MAJOR.
- Provide a recommended next release version and reasoning.
- Ask the user whether to proceed with changelog updates or a release plan.

### 4) State understanding and request permission to proceed

Before doing any edits:
- Provide a short summary of what you read that materially constrains work.
- Call out any conflicting constraints or unknowns.
- Ask: “May I proceed with [specific task] under these constraints?”

Stop here until the user grants permission to proceed.
