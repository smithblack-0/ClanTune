# documents/methodology/testing_standards.md

## When this applies (RAG triggers)

This document applies whenever you:
- Write, modify, or review tests.
- Change production code in a way that requires new tests or test updates.
- Decide how to structure code to make it testable.
- Feel tempted to inspect or manipulate internal/private state in tests.
- Cannot test a behavior without “breaking encapsulation”.
- Consider adding test hooks or exposing internals “just for tests”.

If you are uncertain whether this applies, assume it applies.

## Core contract

Testing is a design forcing function. The project uses black box testing to make bad architecture painful. That pain is the signal: if you cannot test something without violating black box rules, you have found a design problem.

The rule is not “be clever in tests”. The rule is:
- Fix the design or fix the test level, but do not weaken constraints.

## Definitions

### Public

“Public” means accessible to users of a class/module, whether documented or not.

Public includes:
- Any callable method/function reachable outside the class.
- Any attribute accessible via `obj.field` or public properties.
- Any observable behavior: state changes visible via public interface, side effects on injected dependencies, performance characteristics that matter (e.g., caching makes a second call faster).

### Private

Private includes:
- Fields starting with `_` (e.g. `obj._field`).
- Methods starting with `_` (e.g. `obj._method()`).
- Internal implementation details: data structure choice, serialization schema field names, internal caches/registries/hit counts.

## What MUST be tested

You must test the contracts provided by:
- Public methods/functions:
  - Valid inputs and outputs.
  - Edge cases and error conditions (what exception occurs when?).
  - Side effects observable via public interface or injected dependencies.
- Public properties/fields:
  - Getter behavior and domain rules if documented.
- Documented contracts/invariants:
  - Immutability, preservation guarantees, domain validation.
- Internal mechanisms via behavior (not inspection):
  - Caches: verify repeated calls preserve correctness, optionally verify performance property only if contract requires it.
  - Registries/dispatch: verify correct type is produced by `deserialize()` or equivalent, not that a registry contains an entry.
  - Lookup tables: verify lookups succeed/fail correctly via the public method.

The rule is: you are not excused from testing internal mechanisms. You must test what they enable through public behavior.

## What is FORBIDDEN in tests

You must not:
- Read private fields (e.g. `obj._field`) to assert internal state.
- Write private fields to construct test states.
- Call private methods directly.
- Add stateful test hooks in production code (e.g. `_set_for_test()`).
- Weaken a test because the architecture is hard to test.

If you do any of these, you have broken the forcing function and your tests will be rejected in audit.

## The friction protocol (what to do when testing is hard)

When you hit friction, you must do this sequence:

1) Stop and identify the exact friction:
   - “I need to test X but it’s private.”
   - “I need to set internal state to hit edge case Y.”
   - “I need to verify serialization schema fields.”
   - “I need to check a cache/registry directly.”

2) Diagnose what design assumption caused it:
   - Responsibility is in a private method that is too complex.
   - Dependency is not injectable.
   - Interface is missing a necessary public contract.
   - You are trying to test implementation details rather than contract.

3) Fix the architecture or test level:
   - Extract complex logic to a testable component with a public interface.
   - Inject dependencies via constructor rather than hiding them.
   - Move responsibilities to where they belong.
   - Test the public contract rather than the internal mechanism.

4) If still stuck:
   - Pause autonomy and discuss with user. There is likely an architectural ambiguity or contract conflict.

## The Encapsulation Pattern (rare exception)

Sometimes the spirit of black box testing is best served by a controlled, isolated violation. This is rare and requires team approval.

If approved, you may:
- Create ONE stateless helper function at the top of the test file that reads private state for verification.

Requirements:
- The helper must be stateless (no mutation).
- The helper must contain a clear justification explaining why this violation better serves the black-box philosophy than alternatives.
- No stateful hooks or internal mutation are allowed.
- The violation must not be scattered; it must be centralized.

If uncertain, do not use this pattern. Pause and ask.

## Test naming and organization

- Use role-based suite names describing what the suite verifies.
- Avoid brittle numbered naming.
- Helper functions are allowed at top of test file if they use public API where possible.
- If an encapsulation helper exists, it must be obvious and singular.

## Compliance checklist (self-audit)

Before presenting work as finished, confirm:
- Every public interface touched is tested for behavior and errors.
- No tests depend on private state or private methods.
- Where friction occurred, architecture was improved rather than constraints weakened.
- Tests validate contracts (behavior), not implementation details.
