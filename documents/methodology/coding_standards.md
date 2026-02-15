# documents/methodology/coding_standards.md

## When this applies (RAG triggers)

This document applies whenever you:
- Write or refactor production code.
- Introduce a new class/function/module.
- Change interfaces, dependencies, or responsibility boundaries.
- Encounter a design choice about structure, naming, or abstraction.
- Feel tempted to write a “monolithic” implementation to finish quickly.

If you are uncertain whether this applies, assume it applies.

## Core contract

Maintainability and correctness are non-negotiable. Code must be written to best practices, but “best practices” here includes architectural consequences:
- Responsibilities must be isolated.
- Dependencies must be injectable where testing and decoupling require it.
- Failure must be loud rather than hidden.

This is a programmer’s API. Default handlers that hide issues are typically correctness violations unless explicitly contracted.

## Required properties of code

### Decomposition and responsibility isolation

- Complex logic must not hide inside orchestration methods.
- If a method grows complex enough that it cannot be tested via public behavior without friction, extract logic to a testable component.
- Prefer small, composable units with clear contracts.

### Naming and readability

- Variable and method names must communicate intent.
- Avoid cleverness that obscures invariants.
- Prefer explicit types and clear boundaries over implicit “magic”.

### Comments

- Comments explain WHY, not WHAT.
- If the “what” needs explanation, rewrite the code for clarity.

### Type hints

- All public methods must have type hints.
- Internal methods should have type hints when it improves clarity and refactor safety.

### Error handling

- Fail fast, fail loud.
- Validate at initialization when possible (especially for programmer-facing APIs).
- Do not add default config handlers that hide issues unless the contract explicitly requires it.

### Formatting and linting

- black formatting (line length 100).
- ruff linting.
- Avoid numbered step enumerations in comments (brittle under reorder).

## Import conventions

- Tests: use `from src.<package>.<module> import X` style absolute imports.
- Package modules: use relative imports for internal helpers (`from .utilities import ...`).
- __init__.py: order exports from primitives upward to avoid circular imports.

## The mandatory refactor pass

LLM coding often fails because it tries to write code and critique structure simultaneously. Therefore:

- A refactor/isolation pass is mandatory for any non-trivial change.
- You must actively check: “Did I accidentally build a monolith?”
- If yes, stop and restructure responsibilities before proceeding.

This is not optional. “Working code” that is not maintainable fails audit.

## Compliance checklist (self-audit)

Before presenting work as finished, confirm:
- Responsibilities are separated and testable via public contracts.
- Dependencies are injectable where needed for testing and decoupling.
- No hidden defaults or silent fallbacks were added.
- Type hints exist for all public interfaces.
- Formatting and linting constraints are satisfied.
