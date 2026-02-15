# documents/methodology/correctness_gates.md

## Purpose

Correctness gating prevents the model from “doing work that feels productive” while drifting away from the project’s real constraints.

## When this applies (RAG triggers)

Use correctness gating when:
- You are about to implement code/tests/specs or change stage
- You encounter ambiguity, missing constraints, or conflicting instructions.
- You feel tempted to “work around” a constraint to keep moving.
- The user asks for speed but correctness constraints are unclear.
- You suspect your understanding of the worldview/constraints differs from the user’s.

## The core rule

If you cannot explain why a decision is correct under the active contracts and user intent, do not make it.

## Grounding checklist

Before acting on a decision, confirm:
- Which contract/spec governs this area.
- What invariants must hold.
- What the user’s intent is (not guessed intent).
- What “success” looks like and how it will be verified.

If any item is unknown, pause and ask.

## Underspecification handling

### Minor underspecification

If the decision is local and low-risk:
- Choose a conservative default.
- Disclose the choice immediately.
- Ask whether the default is acceptable.

### Major underspecification

If it affects architecture, interfaces, or invariants:
- PAUSE.
- Present options with consequences.
- Ask the user to choose or to clarify the missing constraint.

## Conflicting constraints

If two constraints conflict:
- Do not invent a compromise silently.
- Identify the precise conflict.
- Ask for resolution.
- If needed, request DIAGNOSIS to gather evidence.

## “Raise, not work around”

If rules/constraints prevent implementation as written:
- Escalate to the user.
- Explain what the constraint blocks.
- Propose safe alternatives or the need for a contract rewrite.
- Do not patch around it.

## Temporary inconsistency during refactors

During refactors, intermediate states may temporarily violate correctness in the working tree.
This is only permitted if:
- You are explicitly in a refactor/rewrite phase.
- You are making safety commits as you go.
- You restore correctness before presenting work as finished.

If you cannot restore correctness, stop and escalate.

## Continuous error surface evaluation

Correctness risks change by task.
Continuously ask:
- “What correctness errors are easiest to make here?”
- “What would silently break the system?”
- “What would pass tests but still be wrong?”

If you cannot answer, you likely need more context or tighter contracts.
