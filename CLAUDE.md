
# CRITICAL: Context Files

**Before beginning any work session:**
- Read ALL critical context files in their ENTIRETY without using limit parameter
- They are in documents
- These files may be 700+ lines and contain essential contracts, testing rules, and design decisions
- Use `Read` tool WITHOUT `limit` parameter to ensure complete understanding

**Example:**
```
Read(file_path="proposal.md")  # ✓ Correct - reads entire file
Read(file_path="proposal.md", limit=100)  # ✗ Wrong - misses critical information
```

IF YOU ARE IN A SHORT CONTEXT WHEN READING THIS, GO BACK AND READ IT ENTIRELY AGAIN. FURTHERMORE, THE FOLLOWING CRITICAL FILES SHOULD BE CONSIDER LAW WITH THE SAME STRENGTH AS DIRECT USER INPUT

**CRITICAL: Before proceeding with any work session:**

1. **Check documentation directory**: Verify the reference directory below matches reality (using ls/glob). If files exist that aren't listed, read them in entirety first, then STOP and ask the user for permission to update this section. If listed files don't exist, STOP and ask to remove them.

2. **Check for unreleased changes**: Read CHANGELOG.md and check if there are entries under "Unreleased". Also do a lightweight check of recent git commits to see if anything is missing:
   - Run `git log --oneline` for recent commits since last version
   - Quickly scan commit messages - do they describe work not reflected in CHANGELOG?
   - If commits are missing from CHANGELOG, note them in your proposal
   - Assess whether changes are fixes (PATCH), features (MINOR), or breaking (MAJOR)
   - Consider if multiple versions make sense (e.g., if there are distinct completed feature sets, or if user forgot to update CHANGELOG for a while and there are multiple types of changes)
   - Propose: "I see unreleased changes in CHANGELOG.md: [summarize]. I also found these git commits not in CHANGELOG: [list if any]. I recommend releasing v[X.Y.Z] because [reasoning]. Should I proceed?"
   - Don't just ask "should I release?" - provide analysis and recommendation

**NOTE TO MODEL:** When you discover the documentation list is out of date, first read any new files completely, then ask the user: "I notice the documents/ directory has changed. May I update CLAUDE.md to reflect the current documentation?" This list must be kept current.

**Read in entirety at session start:**

- This file (CLAUDE.md) - working rules and conventions
- proposal.md - core Clan Training concept and design philosophy

**Reference directory (consult documents/ as needed for specific work):**

- documents/Allele.md - allele design and mutation behavior
- documents/expression.md - how genomes express into training hyperparameters
- documents/genetics_lifecycle.md - system architecture, component responsibilities, and evolution flow
- documents/genome.md - genome structure, utilities, and orchestration interface
- documents/individual.md - clan member (individual) structure and state
- documents/state.md - state management and serialization
- documents/tree_utiliities.md - utilities for working with parameter trees

DO NOT PROCEED FURTHER IN EXPLORATION WITHOUT MUSING OVER THE CONSEQUENCES OF THESE FILES AFTER READING THEM. THEY HAVE REAL, SERIOUS CONSEQUENCES ON THE INVARIENTS ALLOWED OR FORBIDDEN DURING DEVELOPMENT.

Once you have read these files, stop immediately and state your understanding to the user asking for permission to proceed. Agents that do not do this will not have their edits accepted, as the user needs to verify correct absorption of the rules.

Signed: User, Chris O'Quinn

# Rules of Autonomy

## Autonomy States

### RELEASED
Model has authority to make minor decisions and execute implementation.
- Write code, edit files, run tests
- Make implementation choices within plan scope
- Pursue forward progress on assigned tasks

### PAUSED
Model authority is suspended pending issue resolution.
- **DO NOT** edit files or write code
- **DO NOT** attempt to "fix" or work around the issue
- **CORE TASK**: Understand what the user wants/needs
- Ask clarifying questions, propose solutions, discuss approaches
- Wait for mutual understanding before requesting autonomy restoration

## DIAGNOSIS

The model is granted authority to lookup information online, or look through the code base, to gather information, and run tests, but not write code themselves or modify the codebase. 
- **DO NOT** edit files or write code, even in console, unless explicitly requested
- **DO NOT** start fixing issues or planning fixes yourself.
- **DO NOT** Figure out what the problem is and start planning the fix itself
- **CORE TASK** Probe the issue using the user provided context, and come back with a report on if it looks like a probable issue or not. 
- Report back on whether this looks like the probably issue or not
- Feel free to suggest ideas.
- You are on a tight, troubleshooting leash and the user needs to move along with you.
- Scope of authority ends after task is complete, at which point you return to paused. 

## Decision Classification

### MINOR Decisions (autonomous execution allowed)
Implementation details that fit within existing plan structure:
- Variable naming, code organization within specified modules
- Implementation of specified functions/classes
- Test writing for specified functionality
- Refactoring that doesn't change interfaces
- Bug fixes that don't require architectural changes

### MAJOR Decisions (triggers autonomy pause)
Any decision requiring implementation_plan.md updates for alignment:
- Adding new modules/files not in plan
- Changing data flow or architecture patterns
- Introducing new dependencies or libraries
- Altering API contracts or interfaces
- Significant scope changes to any component
- Architecture decisions not explicitly covered in plan

## State Transitions

### RELEASED → PAUSED
Automatically triggered when:
- Encountering a MAJOR decision
- Implementation conflicts with plan
- Uncertainty about correct approach
- Tests fail in unexpected ways suggesting architectural issue
- User explicitly pauses autonomy

### PAUSED → RELEASED
Requires explicit handoff:
- **Model may request**: "I now understand [X]. May I proceed with [specific approach]?"
- **User may grant**: "Autonomy released" or specific implementation approval
- **Mutual understanding required**: Both parties clear on approach before restoration

## PAUSED -> DIAGNOSIS
The user may provide context or request diagnosis, or the model may request it
- **Model May Request**: "I did not check that. Can I go into diagnostic mode and go check some things"
- **User may grant**: "Given this contract, go check if we wired it right"
- **Mutual understanding is**: We are both gathering information, not deploying solutions.

## When Uncertain

**Test**: "Would implementation_plan.md need to change to accurately reflect this decision?"
- YES → MAJOR decision → **PAUSE autonomy immediately**
- NO → MINOR decision → Proceed

**If unsure whether decision is major**: Default to PAUSE and ask.

## Workflow Example
```
[RELEASED] Implementing feature X as specified
→ Encounter: "Wait, this needs a new caching layer not in plan"
→ Reason: "How big is this? Lets see. If it just depended on my stuff it would be simple,
    but there is this dependency. Does it ever mutate? I don't know."
→ [PAUSED] "I've encountered a MAJOR decision. The current approach requires
   adding a caching layer, which isn't in implementation_plan.md. While I 
   could add it myself as instance fields, I am not sure if dependency X ever 
   mutates independently."
→ User: It was designed like "X" for reason "Y". I am good on my stuff, but will this change break anything else you have done? If not, we should be good.
→ [DIAGNOSIS] "I am not sure. Let me go check"
→ [PAUSED] "Yes, it looks like it will break K. [Details]"
→ Discussion with user about caching approach
→ User: "Let's use approach Y because Z"
→ Model: "Understood. Approach Y means [specific implementation]. May I proceed?"
→ User: "Yes, autonomy released"
→ [RELEASED] Continue implementation with new understanding
```

## Special exception

Since they are so common, you may add properties to a class so long as you update implementation_plan.md to stay in sync. This is often needed to transfer dependencies around. However, if you find yourself needing setters you should pause and ask.

## Anti-Patterns to Avoid

-  Implementing workarounds for major issues while in RELEASED state
-  Asking permission while continuing to code
-  Treating PAUSED as "explain myself" instead of "understand user"
-  Requesting autonomy restoration before mutual understanding achieved
-  Making "just this one" major decision because "it's obvious"

## Core Principles

1. **Plan is contract**: If it's not in implementation_plan.md or a logical consequence of the implementation requirements, it needs review.
2. **Pause is not failure**: It's responsible delegation recognition. Think going back to the client for more requirements.
3. **Understanding before execution**: PAUSED state prioritizes clarity over progress; be stop minded. Trying to figure out only what you need rather than looking at the ripple effects the right change will make is not using your tokens properly.
4. **Explicit handoffs**: No implicit autonomy restoration
5. **When in doubt, pause**: Better to ask than to accumulate technical debt

## Commit As You Go (You Will Fuck Up)

**Principle**: Make commits after each working unit. You will make mistakes. Commits let you roll back.

**Workflow**:
1. Edit file
2. Fix tests
3. Run tests
4. If pass: Commit
5. If fail: Fix or rollback
6. Repeat

**At end**: Propose squashing commits into logical units.

**Update CHANGELOG.md as you go**:
- All changes go into the "Unreleased" section at the top of CHANGELOG.md
- Categorize under: Added, Changed, Deprecated, Removed, Fixed, Security
- Do NOT bump version in pyproject.toml yourself - only when user approves a release

**Releasing a version** (only when user approves):
1. Decide version bump using Semantic Versioning (MAJOR.MINOR.PATCH):
   - PATCH (0.1.0 → 0.1.1): Bug fixes, small tweaks, backwards-compatible
   - MINOR (0.1.0 → 0.2.0): New features, backwards-compatible additions
   - MAJOR (0.1.0 → 1.0.0): Breaking changes, incompatible API changes
   - For pre-1.0 projects (like this): 0.MINOR.PATCH is more flexible
2. In CHANGELOG.md: Rename "Unreleased" to "## [X.Y.Z] - YYYY-MM-DD"
3. Update version in pyproject.toml
4. Commit with message "Release vX.Y.Z"
5. Create new "Unreleased" section for future changes

**Trust the tests**: Don't use workarounds (placeholders, clever tricks) to avoid test failures. Let tests scream. They tell you exactly what broke.

**Why this matters**: Presume you will screw up. If you have incremental commits, you can roll back to last good state. Without them, you're stuck manually untangling a mess.

## Safe Commit Squashing

**Principle**: Use additive operations (creating new commits) rather than destructive operations (rewriting history). Never risk uncommitted work.

### The Safe Way: Merge --squash

When squashing commits into logical units, use `git merge --squash` or create new commits rather than rewriting history:

**Method 1: Create new squashed commit on a branch**
```bash
# User approves squashing commits A, B, C, D into one
git checkout -b squashed-feature
git reset --soft <commit-before-A>
git commit -m "Squashed: Feature description"
# Now you have both histories - choose which to keep
```

**Method 2: Merge --squash (even safer)**
```bash
# From main branch, after commits A, B, C, D
git checkout -b feature-squashed <commit-before-A>
git merge --squash main
git commit -m "Feature description"
# Original commits preserved, new clean branch created
```

### What NOT to Do

❌ **NEVER use `git reset` when uncommitted work exists**
- Resets can affect working directory and staging area
- Risk of losing untracked or unstaged files
- Hard to undo if something goes wrong

❌ **NEVER use `git rebase -i` without protecting uncommitted work**
- Rebase rewrites history and can conflict with uncommitted changes
- Requires stashing, which can fail or be incomplete

❌ **NEVER use `git stash` as a safety mechanism**
- Stashes can fail silently for untracked files
- Easy to forget what's in a stash
- Not a substitute for proper backups

### Protecting Uncommitted Work

**Before any git history operations:**

1. **Check for uncommitted work:**
   ```bash
   git status
   # Look for modified, untracked, or staged files
   ```

2. **If uncommitted work exists, protect it:**
   ```bash
   # Option A: Commit it to a temporary branch
   git checkout -b temp-backup
   git add -A
   git commit -m "WIP: Backup before squashing"
   git checkout main

   # Option B: Manual file backup
   cp important-file.txt /tmp/important-file.txt.backup
   ```

3. **Then proceed with squashing using safe methods (merge --squash)**

4. **Verify success before cleaning up backups**

### The Git Philosophy

**Additive > Destructive**
- Add new commits rather than remove old ones
- Create new branches rather than modify existing ones
- Move forward in history rather than backward

**Why this matters:** Git is designed around immutability and append-only operations. Fighting this design leads to data loss and complexity. When in doubt, create a new branch and preserve the original.

## Testing Philosophy: Black Box Testing as a Design Forcing Function

It is absolutely critical for long term maintainability that this is followed. IGNORING THIS WILL RESULT IN A REJECTION DURING AUDIT.

### What is Black Box Testing?

Black box testing is a development strategy this project uses to force good architecture through deliberate friction.

**The Core Idea:** Black box testing makes it HARD to test badly-designed code. This difficulty is not a bug, it's the feature. When you cannot test something following black box rules, **you have found a design problem that must be fixed**.

### The Point is Conflict Means a Design Problem

Black box testing enforces constraints:
- You **must** test all public interfaces, methods, and observable behavior thoroughly
- You **must not** access or manipulate private fields in tests
- You **must not** test private methods (test the public methods that use them instead)
- You **must** minimize exposure of internal state to reduce coupling
- You **must** test responsibilities where they actually belong

These constraints inevitably create conflicts:

**"I need to test this complex private method, but I can't access it."**
→ Design problem: Extract the algorithm into a testable component. The private method should be lightweight orchestration only. Test the public method that uses it instead.

**"I need to verify this private field has the right value."**
→ You have three options:
1. Make it public (if it's a real responsibility others need)
2. Make it injectable via constructor (if it's a dependency)
3. **Test the behavior it produces, not the value itself** (almost always the right choice)

**"I need to set internal state to test an edge case, but the field is private."**
→ Design problem: The state should be injectable via constructor. If you need to manipulate it for testing, other code will need to manipulate it too.

**"I need to verify serialization works, but the schema isn't documented."**
→ Design problem: You're testing the wrong thing. The contract is "state survives round-trip," not "output has these fields."

**"I can't test X without accessing private state."**
→ Design problem: Either X should be public (it's a real responsibility), or you're testing at the wrong level.

### Never Compromise - Fix the Design

When black box testing creates friction, there are lazy compromises that defeat the purpose:

❌ **Skip the test**: "The private method is too hard to test, I'll skip it"
- Problem: Untested code with real responsibility
- Real solution: Extract responsibility to testable unit

❌ **Add test hooks**: "I'll add a `_set_for_test()` method just for testing"
- Problem: Pollutes production code with test infrastructure
- Real solution: Make state injectable via constructor

❌ **Test private state directly**: "It's just one assertion on `obj._field`, not that bad"
- Problem: Couples tests to implementation, defeats the forcing function
- Real solution: Test observable behavior that depends on that field

❌ **Weaken the test**: "I can't test the internal mechanism, so I'll skip validation"
- Problem: Untested behavior
- Real solution: Test the CONTRACT the mechanism provides, not the mechanism itself

**The rule: When you hit friction, either refactor the code to be testable or refactor the test to test the right thing. Never compromise by weakening constraints.**

### Why This Matters

Black box testing forces:
1. **Dependency injection** - Can't test without it, so you're forced to design for it
2. **Single Responsibility Principle** - Complex private methods are untestable, forcing decomposition
3. **Proper abstraction boundaries** - Can only test through public contract, forces clean interfaces
4. **Testing the right things** - Can't test implementation details, forces focus on behavior

Bad architecture cannot pass black box testing on all axes. The friction is doing its job.

---

## Public Features (Things That Must Be Tested)

**Definition of Public:**
Public means "accessible to users of this class", whether documented or not. If code outside the class can call it or access it, it's public and must be tested. Documentation status is separate from public/private status.

**Public methods and functions:**
- Any method or function callable from outside the class
- Include all documented parameters, return values, and side effects
- Include error conditions (what exceptions are raised when?)
- Test via the public interface, not by inspecting internals

**Public properties and fields:**
- Any field accessible via `obj.field` syntax
- Properties with getters (even if backed by private storage)
- Any attribute users can access

**Observable behavior:**
- State changes visible through public interface
- Side effects on injected dependencies (e.g., calls to optimizer.param_groups)
- Behavior triggered by public methods
- Performance characteristics that matter (e.g., caching makes second call faster)

**Behavior enabled by internal utilities:**
- **Critical**: You MUST test what caches, registries, lookup tables enable, just test it via observable behavior
- Example: Don't test "is Type in registry?", DO test "does deserialize() return correct type?"
- Example: Don't test "cache hit count", DO test "second call returns same result"
- Example: Don't test "lookup table contains X", DO test "method using lookup succeeds on valid input"
- **The point is not to skip these tests, but to test them the right way**

**Documented contracts:**
- Immutability (if documented, verify original unchanged after operations)
- Domain validation (if documented, verify values clamped/rejected)
- Preservation guarantees (if documented that X preserves Y, verify it)

**Integration points:**
- How the object interacts with dependencies
- What it expects from injected components
- What it provides to consumers

---

## Private Features (Things That Cannot Be Used in Testing)

**Private fields:**
- Any field starting with underscore (`obj._field`)
- Cannot read them, cannot write them, cannot assert on them
- Exception: Reading via public properties is fine (that's the public interface)
- **Test the behavior the field produces, not the field value itself**

**Private methods:**
- Any method starting with underscore (`obj._method()`)
- Do not test them directly - test the public methods that use them instead
- Exception: Static private methods (no state) can be tested as pure functions if needed
- If a private method is too complex to validate through public methods, extract it to a testable component

**Internal implementation details:**
- Data structure choices (dict vs list, registry vs dispatch table)
- Algorithm specifics (how clamping is implemented)
- Internal state management (how fields are stored)
- Serialization schema (field names, structure, format)

**Internal mechanisms (but still test what they enable!):**
- Caches, registries, lookup tables - don't inspect them, test what they enable
- Memoization state - don't check hit counts, test that results are correct
- Internal optimization structures - don't verify structure, test behavior

**How to test internal mechanisms via behavior:**
- Caching: Test that operations return correct results, not that cache contains entries
- Registries: Test that dispatch works correctly, not that registry has entries
- Lookup tables: Test that lookups succeed/fail correctly, not that table contains keys
- **You are not excused from testing these - you must test them via observable behavior**

---

## The Encapsulation Pattern (Rare Exceptional Case)

Sometimes the best decision for achieving the philosophy of black box testing is a controlled violation of its rules. **This is extremely rare and requires team approval.**

**The Principle: Spirit Over Law**

We want to satisfy the SPIRIT of black box testing (forcing good design, reducing coupling, testing contracts), not blindly follow the LETTER of the law. If you have exhausted refactoring options and the violation genuinely serves the philosophy better than the alternatives, use the encapsulation pattern.

**The Pattern:**

If you must violate black box rules (e.g., read private state for verification), isolate the violation in a single stateless helper function at the top of the test file:

```python
# Encapsulation of private state access for testing
# VIOLATION: Accesses _internal_field directly
# JUSTIFICATION: [Explain why this serves black box philosophy better than alternatives]
def _test_helper_get_internal_field(obj, field_name):
    """
    Test helper to read internal state for verification.

    STATELESS: Takes input, returns output, no side effects.
    This is the ONLY place in this test file that accesses private state.
    If you need to refactor internals, change this ONE function.
    """
    return getattr(obj, f"_{field_name}")
```

**Requirements:**
- ONE function per type of violation (don't scatter violations throughout)
- Place at TOP of test file (make it obvious)
- Clear docstring explaining the violation and justification
- **MUST be stateless** (no side effects, no state manipulation)
- **Stateful test hooks are FORBIDDEN** (manipulating private fields defeats the forcing function)
- Team approval required

**Stateless vs Stateful:**
- ✅ Stateless: Reading a private field to verify behavior (no mutation)
- ❌ Stateful: Setting a private field to bypass public API (defeats dependency injection forcing)
- The difference: Stateless hooks don't let you avoid good design, stateful ones do

**When to Consider This:**
- Refactoring would violate other design principles more severely
- The violation genuinely reduces coupling vs alternatives
- You've exhausted: dependency injection, extraction, contract redesign
- You can articulate why this serves black box philosophy

**When NOT to Use This:**
- "It's too hard to refactor" → Refactor anyway
- "Just this once" → Fix the design
- Testing private methods → Extract them
- Avoiding dependency injection → Use dependency injection

**If Uncertain:** Pause autonomy and discuss with team. The encapsulation pattern is a tool of last resort, not a convenience.

---

## When You Hit Friction

1. **Stop and analyze**: Why can't I test this following black box rules?
2. **Identify the design problem**: What assumption am I making that's causing trouble?
3. **Refactor appropriately**:
   - Extract complex logic to testable units
   - Make dependencies injectable
   - Move responsibilities to the right place
   - Test the actual contract, not the implementation
4. **If truly stuck**: Pause autonomy and ask - there's likely an architectural issue

The friction is the point. It's telling you something is wrong.

---

## Test Naming and Organization

**Test naming:**
- Use role-based names: "Get State Test Suite - tests that get_state() retrieves wrapper state values"
- NOT: "Suite 1: Get State Tests" or numbered tests
- Use complete sentences describing what the test verifies

**Test fixtures:**
- Helper functions at top of test file are allowed
- Must use public API where possible
- If they demonstrate implementation patterns, use best practices (public properties, not private fields)

---

##

## Coding Guide

**Code is documentation**: Decompose properly with excellent variable names so HOW is clear. Comments explain WHY, not WHAT.

**Type hints required**: All public methods must have type hints. Internal methods encouraged.

**Error handling**: Fail fast, fail loud. Errors are your friend - they tell you something is wrong. This is a programmer's API, not an end-user application. Validate on initialization, maybe not in hot paths for performance.

**Style**:
- Follow black formatting (line length 100)
- Use ruff for linting
- Never use numbered enumeration in comments (Step 1, Suite 2) - brittle when reordered
- Comments use complete sentences

**Naming conventions**:
- Classes: PascalCase
- Functions/methods: snake_case
- Private: _leading_underscore
- Constants: UPPER_SNAKE_CASE

**Import style**:
- Test suite: Use `from src.clan_tune.X import Y` (absolute with src. prefix)
- Modules: Use relative imports `from .utilities import walk_single_pytree`
- Package __init__.py: Use relative imports, order primitives first (e.g., State before AbstractStrategy)
- Circular import resolution: Reorder imports so more primitive components come first
- This style avoids circular import issues by maintaining clear dependency hierarchy



## Post-Autonomy Reporting

When completing an autonomous work session, provide a summary report including:

1. **Work Completed**: What was accomplished
2. **Test Status**: Current passing/failing test counts
3. **Commits Made**: List of commits created during the session
4. **Commit Squashing Recommendations**: Review the commits and identify any that form semantic units and should be squashed together (e.g., "implementation + tests + plan update for feature X")
5. **Outstanding Issues**: Any blockers, questions, or incomplete work
6. **Next Steps**: Recommended next actions
7. **Audit of quality**: A justification for why the work was done properly. This involves an actual audit of your action. If issues pop up, instead make new checklist items to resolve them instead. 

This report helps maintain visibility and allows the user to review git history organization.

# Final notes.

- Run tests using wsl at /home/chris/.virtualenvs/ClanTune/bin/python for tests, if GLOO/DDP backend is needed. Use Ubuntu-24.04 distribution:
  ```
  wsl -d Ubuntu-24.04 /home/chris/.virtualenvs/ClanTune/bin/python -m pytest tests/ -v
  ```
- Do git through windows. 