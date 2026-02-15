# documents/methodology/writing_specifications.md

## When this applies (RAG triggers)

This document applies whenever you:
- Write or revise a specification, proposal, contract, or methodology doc.
- Add or modify interfaces, responsibilities, or invariants.
- Notice duplication, verbosity, or ambiguity in docs.
- Need to place facts across documents without repetition.
- Are tempted to “just dump” details to be safe.

If you are uncertain whether this applies, assume it applies.

## Core contract

Minimal wording to unambiguous intent.
Every word must reduce ambiguity.
If removing a word does not reduce clarity, remove it.

This requires synthesis, not linear writing.

## The Block model

A “Block” is any piece of documentation with a single abstract responsibility. All content within a block must be at the same abstraction level. If you need multiple abstraction levels, nest blocks.

Blocks can be:
- A class specification.
- A method specification.
- An algorithm description.
- An introductory paragraph.
- A technique explanation.

There is no fixed block length. The block is as long as needed to satisfy its responsibility.

## Fractal descent order (required)

Every block reveals information in this order:

1) Contextualization
   - Why this exists and what it enables.
   - How it works is excluded here.

2) Core technical artifact
   - The actual contract: signature, data structure, list, algorithm, or other primary content.

3) Explain how it exists
   - Consequences, behavior, interactions, and how it fulfills contracts.
   - Keep abstraction level consistent; split into sub-blocks if overloaded.

4) Variadic additional details
   - Edge cases, usage guidance, adapter strategies, nuance.
   - Only include what is needed to be unambiguous.

This order dictates information sequence, not rigid formatting. It may be one paragraph or many sections.

## Meta-rules (required)

1) Progressive disclosure
   - Start broad, narrow progressively, stop when unambiguous.

2) DRY everything
   - State common patterns once in the correct home location.
   - Refer elsewhere, do not repeat.
   - Duplication is a synthesis failure.

3) Organize by contracts → relationships → invariants
   - Contracts: what exists and what it guarantees.
   - Relationships: delegation and ownership boundaries.
   - Invariants: rules that always hold.

4) Pointed philosophy
   - Say WHY concisely where it reduces ambiguity (“This enables X”).

5) Examples show primary responsibilities only
   - Minimal examples that show inputs/outputs, not full implementations.

6) Delegate where you delegate
   - If X delegates to Y, state “delegates to Y, passing Z”.
   - Do not explain Y internals in X’s spec.

7) Organization is fractal
   - Headings emerge from satisfying all constraints, not from templates.

## Operational consequences (how to work)

You cannot write linearly. The process is:

1) Synthesize first
   - Read all related specs completely.
   - Map contract graph and ownership boundaries.
   - Identify common patterns to DRY.

2) Place, don’t generate
   - Each fact belongs in exactly one location.
   - Reference it elsewhere.

3) Edit by re-synthesizing
   - Remove duplication by finding the shared pattern and relocating it once.
   - If you cannot be minimal and unambiguous, you do not understand it yet or the design is ambiguous.

4) Examples last
   - Only after you know the primary responsibility and have eliminated non-primary detail.

Verbosity is usually a synthesis gap. Duplication is incomplete synthesis.

## Compliance checklist (self-audit)

Before presenting a spec as finished, confirm:
- Each block follows contextualization → artifact → consequences → details order.
- No duplication of common patterns across docs.
- Facts are placed once, referenced elsewhere.
- Contracts/relationships/invariants are clear and minimal.
- Examples are minimal and only demonstrate primary responsibility.
