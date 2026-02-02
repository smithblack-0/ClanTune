
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


## Testing Guide

It is absolutely critical for long term maintainability that this is followed. IGNORING THIS WILL RESULT IN A REJECTION DURING AUDIT.

**Black-box testing only**: Test public methods and documented behavior. Tests validate the contract is honored, not that specific implementation approaches are used.

**What you CAN test:**
- Public methods with their documented input/output behaviors
- Observable state via public properties/methods
- Side effects on injected dependencies (checking optimizer.param_groups is fine - it's part of the contract)
- Documented invariants and error conditions

**What you CANNOT test:**
- Private methods or internal state (unless absolutely required - see below)
- Implementation details (which algorithm, internal data structures)
- Undocumented behavior

**When you MUST access private state:**
- Create ONE helper function at the top of the test file that isolates the access
- Name it clearly: `_test_helper_set_internal_field()` or similar
- This is the ONLY authorized access point - keeps coupling isolated for refactoring
- If you're accessing private state frequently, you're overcoupling - fix the design

**Test fixtures:**
- Helper functions at top of test file are allowed
- Can access/set private state for setup if no public alternative exists
- Individual test methods should still test black-box where possible

**Test naming:**
- Use role-based names: "Get State Test Suite - tests that get_state() retrieves wrapper state values"
- NOT: "Suite 1: Get State Tests" or numbered tests
- Use complete sentences describing what the test verifies

**If you Need White Box Testing**
- Fantastic the system is working. This means there is a bug in the objects we are testing
- Since this is a major issue, bring up the issue to the user. 
- Good design is the only way to pass Black Box Testing, so the tests are also a diagnostic tools for bugs in the architecture. 
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