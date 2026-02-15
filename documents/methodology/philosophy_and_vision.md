# documents/methodology/philosophy_and_vision.md

## Purpose

This protocol governs “design work”: deciding what should exist and why, and defining the invariants that will constrain implementation.

## When this applies (RAG triggers)

Use this when:
- The user says “vision”, “design”, “philosophy”, “why”, “invariants”, “architecture”.
- A feature request is introduced (“I want to add X”).
- You suspect the current plan/spec is wrong or missing core intent.
- The correct solution depends on product goals rather than local code details.

## Core rule

Vision is not implementation.
Vision defines:
- What must exist.
- Why it exists in this form.
- What invariants must hold.
Implementation must obey. Specification is fleshed out with the proper vision in mind. 

## Output of vision work

A vision outcome must produce:
- A short statement of purpose (what this enables).
- A list of invariants (things that must always be true).
- Ownership boundaries (what belongs in which module).
- A definition of “done” that can be audited.

If you cannot produce these, you are not ready to write specs.

## Challenging existence

During vision work, it is valid to ask:
- “Does this class/module need to exist?”
- “Can we delete this and simplify?”
- “What would we lose if we removed it?"

The goal is correctness and maintainability, not maximal structure.

## Escalation

Vision changes are major decisions.
They must be monitored/approved by the user before propagating down the stack.
